#!/usr/bin/env python3
"""Player win-loss records from ESPN box scores. Writes to Supabase.

Regular season (matchup NONE) and winners-bracket playoffs are stored separately.
Consolation games do not count toward records, year-by-year starts, or average
starter points. Use --full to recompute from FIRST_SEASON through the current season.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from espn_client import FIRST_SEASON, ROOT, get_league, season_id
from revalidate import ping_revalidate
from supabase_client import get_service_client, upload_logo

MIN_STARTS = 30
WINNERS_BRACKET = "WINNERS_BRACKET"
REGULAR_TYPES = {"NONE", ""}

OWNERS_BY_YEAR = json.loads(
    (ROOT / "data" / "league.json").read_text(encoding="utf-8")
).get("owners_by_year") or {}


def empty_player(name: str, pos: str) -> dict:
    return {
        "name": name,
        "pos": pos,
        "teams": [],
        "g": 0,
        "w": 0,
        "gs": 0,
        "ws": 0,
        "pg": 0,
        "pw": 0,
        "pgs": 0,
        "pws": 0,
        "titles": 0,
        "seasons": {},
    }


def remember_player(players: dict[str, dict], player) -> dict:
    rec = players.get(player.name)
    if rec is None:
        rec = empty_player(player.name, player.position)
        players[player.name] = rec
    if player.position:
        rec["pos"] = player.position
    team = player.proTeam
    if team and team != "None" and (not rec["teams"] or rec["teams"][-1] != team):
        rec["teams"].append(team)
    return rec


def update_player(players: dict[str, dict], player, outcome: int, playoff: bool) -> None:
    rec = remember_player(players, player)
    starter = player.lineupSlot not in ("IR", "BE")
    if playoff:
        rec["pg"] += 1
        rec["pw"] += outcome
        if starter:
            rec["pgs"] += 1
            rec["pws"] += outcome
        return
    rec["g"] += 1
    rec["w"] += outcome
    if starter:
        rec["gs"] += 1
        rec["ws"] += outcome


def empty_year(year: int) -> dict:
    return {
        "year": year,
        "fantasy": [],
        "nfl": [],
        "gs": 0,
        "starter_pts": 0.0,
    }


def owner_name(year: int, team_id: int | None) -> str:
    if team_id is None:
        return "Unknown"
    owners = OWNERS_BY_YEAR.get(str(year)) or {}
    return owners.get(str(team_id)) or "Unknown"


def fantasy_team_name(side) -> str:
    if side is None:
        return ""
    name = getattr(side, "team_name", None)
    if name:
        return str(name)
    return ""


def counts_toward_record(kind: str, home_id: int | None, away_id: int | None) -> bool:
    return (
        home_id is not None
        and away_id is not None
        and (kind == WINNERS_BRACKET or kind in REGULAR_TYPES)
    )


def record_appearance(
    players: dict[str, dict],
    player,
    year: int,
    owner: str,
    team_name: str,
    count_start: bool,
) -> None:
    rec = remember_player(players, player)
    seasons = rec.setdefault("seasons", {})
    acc = seasons.get(year)
    if acc is None:
        acc = empty_year(year)
        seasons[year] = acc
    if owner or team_name:
        pair = {"owner": owner, "team": team_name}
        if pair not in acc["fantasy"]:
            acc["fantasy"].append(pair)
    nfl = player.proTeam
    if nfl and nfl != "None" and (not acc["nfl"] or acc["nfl"][-1] != nfl):
        acc["nfl"].append(nfl)
    if count_start and player.lineupSlot not in ("IR", "BE"):
        acc["gs"] += 1
        acc["starter_pts"] += float(getattr(player, "points", 0) or 0)


def finalize_seasons(seasons: dict) -> list[dict]:
    rows = []
    for year in sorted(seasons):
        acc = seasons[year]
        gs = int(acc.get("gs") or 0)
        pts = float(acc.get("starter_pts") or 0)
        rows.append(
            {
                "year": int(year),
                "fantasy": list(acc.get("fantasy") or []),
                "nfl": list(acc.get("nfl") or []),
                "gs": gs,
                "avgStarterPts": round(pts / gs, 1) if gs else None,
            }
        )
    return rows


def seasons_from_row(raw) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for item in raw or []:
        year = int(item["year"])
        gs = int(item.get("gs") or 0)
        avg = item.get("avgStarterPts")
        out[year] = {
            "year": year,
            "fantasy": list(item.get("fantasy") or []),
            "nfl": list(item.get("nfl") or []),
            "gs": gs,
            "starter_pts": float(avg) * gs if avg is not None else 0.0,
        }
    return out


def box_outcomes(box) -> tuple[int, int]:
    if box.home_score > box.away_score:
        return 1, 0
    if box.away_score > box.home_score:
        return 0, 1
    return 0, 0


def box_team_id(side) -> int | None:
    if side is None:
        return None
    tid = getattr(side, "team_id", None)
    if tid is not None:
        return int(tid)
    if isinstance(side, int):
        return side
    return None


def matchup_type(box) -> str:
    return getattr(box, "matchup_type", None) or "NONE"


def add_roster(
    rosters: dict[int, set[str]],
    team_id: int | None,
    lineup,
    players: dict[str, dict] | None = None,
) -> None:
    if team_id is None:
        return
    names = rosters.setdefault(team_id, set())
    for player in lineup or []:
        names.add(player.name)
        if players is not None:
            remember_player(players, player)


def season_complete(league) -> bool:
    return any(getattr(team, "final_standing", 0) == 1 for team in league.teams)


def champion_team_id(league) -> int | None:
    for team in league.teams:
        if getattr(team, "final_standing", None) == 1:
            return team.team_id
    return None


def collect_rosters(year: int, start_week: int, end_week: int) -> dict[int, set[str]]:
    league = get_league(year)
    rosters: dict[int, set[str]] = {}
    last = min(end_week, league.current_week)
    for week in range(start_week, last):
        for box in league.box_scores(week=week):
            add_roster(rosters, box_team_id(box.home_team), box.home_lineup)
            add_roster(rosters, box_team_id(box.away_team), box.away_lineup)
    return rosters


def scrape_weeks(
    players: dict[str, dict],
    year: int,
    start_week: int,
    end_week: int,
    season_rosters: dict[int, set[str]] | None = None,
) -> dict[int, set[str]]:
    league = get_league(year)
    rosters = season_rosters if season_rosters is not None else {}
    last = min(end_week, league.current_week)
    for week in range(start_week, last):
        print(f"  {year} week {week}")
        for box in league.box_scores(week=week):
            kind = matchup_type(box)
            home_id = box_team_id(box.home_team)
            away_id = box_team_id(box.away_team)
            add_roster(rosters, home_id, box.home_lineup)
            add_roster(rosters, away_id, box.away_lineup)
            home_owner = owner_name(year, home_id)
            away_owner = owner_name(year, away_id)
            home_name = fantasy_team_name(box.home_team)
            away_name = fantasy_team_name(box.away_team)
            count_start = counts_toward_record(kind, home_id, away_id)
            for player in box.home_lineup:
                record_appearance(players, player, year, home_owner, home_name, count_start)
            for player in box.away_lineup:
                record_appearance(players, player, year, away_owner, away_name, count_start)
            if not count_start:
                continue
            if kind == WINNERS_BRACKET:
                home_out, away_out = box_outcomes(box)
                for player in box.home_lineup:
                    update_player(players, player, home_out, True)
                for player in box.away_lineup:
                    update_player(players, player, away_out, True)
            elif kind in REGULAR_TYPES:
                home_out, away_out = box_outcomes(box)
                for player in box.home_lineup:
                    update_player(players, player, home_out, False)
                for player in box.away_lineup:
                    update_player(players, player, away_out, False)
    return rosters


def credit_titles(players: dict[str, dict], year: int, rosters: dict[int, set[str]]) -> None:
    league = get_league(year)
    if not season_complete(league):
        print(f"  {year}: season not complete, skipping titles")
        return
    champ_id = champion_team_id(league)
    if champ_id is None:
        print(f"  {year}: no champion standing, skipping titles")
        return
    names = rosters.get(champ_id, set())
    for name in names:
        rec = players.get(name)
        if rec is None:
            continue
        rec["titles"] = int(rec.get("titles") or 0) + 1
    print(f"  {year}: credited {len(names)} titles")


def row_from_db(row: dict) -> dict:
    return {
        "name": row["name"],
        "pos": row["pos"],
        "teams": list(row.get("teams") or []),
        "g": int(row["g"]),
        "w": int(row["w"]),
        "gs": int(row["gs"]),
        "ws": int(row["ws"]),
        "pg": int(row["pg"]),
        "pw": int(row["pw"]),
        "pgs": int(row["pgs"]),
        "pws": int(row["pws"]),
        "titles": int(row["titles"]),
        "seasons": seasons_from_row(row.get("seasons")),
    }


def load_from_db(client) -> tuple[dict[str, dict], dict]:
    rows = client.table("player_records").select("*").execute().data or []
    players = {row["name"]: row_from_db(row) for row in rows}
    report = (
        client.table("reports").select("*").eq("id", "player-records").execute().data
        or []
    )
    through = {"season": FIRST_SEASON, "week": 0, "titles_through_season": FIRST_SEASON - 1}
    if report:
        through = {
            "season": report[0].get("through_season") or FIRST_SEASON,
            "week": report[0].get("through_week") or 0,
            "titles_through_season": report[0].get("titles_through_season")
            or FIRST_SEASON - 1,
        }
    return players, through


SEASONS_STORAGE_PATH = "player-records/seasons.json"


def write_seasons_storage(client, players: dict[str, dict]) -> None:
    blob = {
        rec["name"]: finalize_seasons(rec.get("seasons") or {})
        for rec in players.values()
    }
    upload_logo(
        client,
        SEASONS_STORAGE_PATH,
        json.dumps(blob, separators=(",", ":")).encode("utf-8"),
        "application/json",
    )


def upsert_players(client, players: dict[str, dict]) -> None:
    payload = []
    for rec in players.values():
        payload.append(
            {
                "name": rec["name"],
                "pos": rec["pos"],
                "teams": rec["teams"],
                "g": rec["g"],
                "w": rec["w"],
                "gs": rec["gs"],
                "ws": rec["ws"],
                "pg": rec["pg"],
                "pw": rec["pw"],
                "pgs": rec["pgs"],
                "pws": rec["pws"],
                "titles": rec["titles"],
                "seasons": finalize_seasons(rec.get("seasons") or {}),
            }
        )
    try:
        for i in range(0, len(payload), 200):
            client.table("player_records").upsert(payload[i : i + 200]).execute()
    except Exception as exc:
        message = str(exc)
        if "seasons" not in message:
            raise
        print("player_records.seasons column missing; upserting without it")
        stripped = [{k: v for k, v in row.items() if k != "seasons"} for row in payload]
        for i in range(0, len(stripped), 200):
            client.table("player_records").upsert(stripped[i : i + 200]).execute()


def write_report(client, through: dict, current: int) -> None:
    client.table("reports").upsert(
        {
            "id": "player-records",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "season": current,
            "through_season": through["season"],
            "through_week": through["week"],
            "titles_through_season": through.get("titles_through_season"),
            "min_starts": MIN_STARTS,
        }
    ).execute()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full",
        action="store_true",
        help=f"Recompute every season from {FIRST_SEASON} through the current year.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    current = season_id()
    client = get_service_client()

    if args.full:
        players = {}
        titles_through = FIRST_SEASON - 1
        for year in range(FIRST_SEASON, current + 1):
            print(f"Season {year}")
            league = get_league(year)
            rosters = scrape_weeks(players, year, 1, league.current_week)
            if year < current or season_complete(league):
                credit_titles(players, year, rosters)
                titles_through = year
        through = {
            "season": current,
            "week": get_league(current).current_week - 1,
            "titles_through_season": titles_through,
        }
        client.table("player_records").delete().neq("name", "").execute()
    else:
        players, through = load_from_db(client)
        if not players:
            raise SystemExit("No player_records rows yet. Run with --full first.")
        start_year = int(through.get("season") or FIRST_SEASON)
        start_week = int(through.get("week") or 0) + 1
        titles_through = int(through.get("titles_through_season") or FIRST_SEASON - 1)
        for year in range(start_year, current + 1):
            league = get_league(year)
            week_from = start_week if year == start_year else 1
            print(f"Season {year} from week {week_from}")
            rosters = scrape_weeks(players, year, week_from, league.current_week)
            if titles_through < year and (year < current or season_complete(league)):
                full_rosters = collect_rosters(year, 1, league.current_week)
                credit_titles(players, year, full_rosters)
                titles_through = year
        through = {
            "season": current,
            "week": get_league(current).current_week - 1,
            "titles_through_season": titles_through,
        }

    write_seasons_storage(client, players)
    upsert_players(client, players)
    write_report(client, through, current)
    ping_revalidate()
    print(f"Wrote {len(players)} player records")


if __name__ == "__main__":
    main()
