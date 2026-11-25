#!/usr/bin/env python3
"""Player win-loss records. Writes to Supabase.

The default walks ESPN box scores. --from-weeks rolls records up from stored
player_weeks and team_weeks instead. That rollup does not match the ESPN table
yet: playoff weeks are missing opponent_owner, including team-id 0 byes.
--diff prints the comparison. Consolation games do not count either way.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from espn_client import FIRST_SEASON, ROOT, get_league, season_id
from league import owner_name, owners_by_year
from nfl_teams import WeekTeams, espn_abbrev, load_week_teams
from revalidate import ping_revalidate
from supabase_client import fetch_all, get_service_client, upload_logo, upsert_chunks

MIN_STARTS = 30
_OMIT_TEAM = object()
WINNERS_BRACKET = "WINNERS_BRACKET"
REGULAR_TYPES = {"NONE", ""}

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


def player_nfl_team(player, year: int, week: int, teams: WeekTeams | None) -> str | None:
    """Week roster when ESPN's proTeam is a club he had not joined yet."""
    player_id = getattr(player, "playerId", None)
    if teams is not None and player_id is not None:
        found = teams.for_week(int(player_id), year, week)
        if found:
            return found
    return espn_abbrev(getattr(player, "proTeam", None))


def remember_player(players: dict[str, dict], player, nfl_team=_OMIT_TEAM) -> dict:
    rec = players.get(player.name)
    if rec is None:
        rec = empty_player(player.name, player.position)
        players[player.name] = rec
    if player.position:
        rec["pos"] = player.position
    team = espn_abbrev(getattr(player, "proTeam", None)) if nfl_team is _OMIT_TEAM else nfl_team
    if team and (not rec["teams"] or rec["teams"][-1] != team):
        rec["teams"].append(team)
    return rec


def update_player(players: dict[str, dict], player, outcome: int, playoff: bool) -> None:
    rec = remember_player(players, player, None)
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
    nfl_team: str | None = None,
) -> None:
    rec = remember_player(players, player, nfl_team)
    seasons = rec.setdefault("seasons", {})
    acc = seasons.get(year)
    if acc is None:
        acc = empty_year(year)
        seasons[year] = acc
    if owner or team_name:
        pair = {"owner": owner, "team": team_name}
        if pair not in acc["fantasy"]:
            acc["fantasy"].append(pair)
    if nfl_team and (not acc["nfl"] or acc["nfl"][-1] != nfl_team):
        acc["nfl"].append(nfl_team)
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
            remember_player(players, player, None)


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
    teams: WeekTeams | None = None,
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
                record_appearance(
                    players,
                    player,
                    year,
                    home_owner,
                    home_name,
                    count_start,
                    player_nfl_team(player, year, week, teams),
                )
            for player in box.away_lineup:
                record_appearance(
                    players,
                    player,
                    year,
                    away_owner,
                    away_name,
                    count_start,
                    player_nfl_team(player, year, week, teams),
                )
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
        upsert_chunks(client, "player_records", payload, "name")
    except Exception as exc:
        message = str(exc)
        if "seasons" not in message:
            raise
        print("player_records.seasons column missing; upserting without it")
        stripped = [{k: v for k, v in row.items() if k != "seasons"} for row in payload]
        upsert_chunks(client, "player_records", stripped, "name")


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


def _float(value) -> float:
    return float(value or 0)


def champions_by_season() -> dict[int, str]:
    payouts = json.loads((ROOT / "data" / "payouts.json").read_text(encoding="utf-8"))
    found: dict[int, str] = {}
    for year, places in (payouts.get("season_finish") or {}).items():
        owner = ((places or {}).get("1") or {}).get("owner")
        if owner:
            found[int(year)] = str(owner)
    return found


def _pair_games(team_weeks: list[dict]) -> list[dict]:
    """Non-consolation games with both scores. Each game is counted once."""
    by_week: dict[tuple[int, int], list[dict]] = {}
    for row in team_weeks:
        if row.get("is_consolation"):
            continue
        key = (int(row["season"]), int(row["week"]))
        by_week.setdefault(key, []).append(row)
    games = []
    for (season, week), rows in sorted(by_week.items()):
        by_owner: dict[str, list[dict]] = {}
        for row in rows:
            owner = row.get("owner")
            if owner:
                by_owner.setdefault(str(owner), []).append(row)
        seen: set[tuple[int, int]] = set()
        for row in rows:
            owner = row.get("owner")
            opp_name = row.get("opponent_owner")
            if not owner or not opp_name:
                continue
            partner = None
            for candidate in by_owner.get(str(opp_name), []):
                if int(candidate["team_id"]) == int(row["team_id"]):
                    continue
                if candidate.get("opponent_owner") == owner:
                    partner = candidate
                    break
            if partner is None:
                continue
            pair = tuple(sorted((int(row["team_id"]), int(partner["team_id"]))))
            if pair in seen:
                continue
            if bool(row.get("is_regular", True)) != bool(partner.get("is_regular", True)):
                continue
            seen.add(pair)
            left_points = _float(row.get("points"))
            right_points = _float(partner.get("points"))
            if left_points > right_points:
                left_win, right_win = 1, 0
            elif right_points > left_points:
                left_win, right_win = 0, 1
            else:
                left_win, right_win = 0, 0
            games.append(
                {
                    "season": season,
                    "week": week,
                    "playoff": not bool(row.get("is_regular", True)),
                    "sides": (
                        {**row, "win": left_win},
                        {**partner, "win": right_win},
                    ),
                }
            )
    games.sort(key=lambda game: (game["season"], game["week"], game["sides"][0]["team_id"]))
    return games


def _apply_appearance(
    players: dict[str, dict],
    row: dict,
    team_name: str,
    win: int,
    playoff: bool,
) -> None:
    name = str(row["name"])
    rec = players.get(name)
    if rec is None:
        rec = empty_player(name, row.get("pos") or "")
        players[name] = rec
    if row.get("pos"):
        rec["pos"] = row["pos"]
    nfl_team = row.get("nfl_team") or None
    if nfl_team and (not rec["teams"] or rec["teams"][-1] != nfl_team):
        rec["teams"].append(nfl_team)
    season = int(row["season"])
    seasons = rec.setdefault("seasons", {})
    acc = seasons.get(season)
    if acc is None:
        acc = empty_year(season)
        seasons[season] = acc
    owner = owner_name(season, int(row["team_id"]))
    if owner or team_name:
        pair = {"owner": owner, "team": team_name}
        if pair not in acc["fantasy"]:
            acc["fantasy"].append(pair)
    if nfl_team and (not acc["nfl"] or acc["nfl"][-1] != nfl_team):
        acc["nfl"].append(nfl_team)
    started = bool(row.get("started"))
    if started:
        acc["gs"] += 1
        acc["starter_pts"] += _float(row.get("points"))
    if playoff:
        rec["pg"] += 1
        rec["pw"] += win
        if started:
            rec["pgs"] += 1
            rec["pws"] += win
        return
    rec["g"] += 1
    rec["w"] += win
    if started:
        rec["gs"] += 1
        rec["ws"] += win


def _credit_champions(
    players: dict[str, dict],
    player_weeks: list[dict],
    champions: dict[int, str],
) -> None:
    blocks = owners_by_year()
    team_ids: dict[int, set[int]] = {}
    for season, owner in champions.items():
        block = blocks.get(str(season)) or {}
        team_ids[season] = {int(team_id) for team_id, name in block.items() if name == owner}
    credited: dict[int, set[str]] = {}
    for row in player_weeks:
        season = int(row["season"])
        if int(row["team_id"]) not in team_ids.get(season, set()):
            continue
        credited.setdefault(season, set()).add(str(row["name"]))
    for names in credited.values():
        for name in names:
            rec = players.get(name)
            if rec is None:
                continue
            rec["titles"] = int(rec.get("titles") or 0) + 1


def rollup_records(
    player_weeks: list[dict],
    team_weeks: list[dict],
    champions: dict[int, str] | None = None,
) -> dict[str, dict]:
    """Win-loss from stored weeks. Consolation games are left out."""
    names = {
        (int(row["season"]), int(row["week"]), int(row["team_id"])): row.get("team_name") or ""
        for row in team_weeks
    }
    lineup: dict[tuple[int, int, int], list[dict]] = {}
    for row in player_weeks:
        key = (int(row["season"]), int(row["week"]), int(row["team_id"]))
        lineup.setdefault(key, []).append(row)
    players: dict[str, dict] = {}
    for game in _pair_games(team_weeks):
        for side in game["sides"]:
            key = (game["season"], game["week"], int(side["team_id"]))
            team_name = names.get(key) or ""
            for row in lineup.get(key, []):
                _apply_appearance(players, row, team_name, int(side["win"]), game["playoff"])
    _credit_champions(players, player_weeks, champions if champions is not None else champions_by_season())
    return players


def _stat_key(rec: dict) -> tuple:
    return (
        int(rec["g"]),
        int(rec["w"]),
        int(rec["gs"]),
        int(rec["ws"]),
        int(rec["pg"]),
        int(rec["pw"]),
        int(rec["pgs"]),
        int(rec["pws"]),
        int(rec["titles"]),
    )


def _season_starts(rec: dict) -> dict[int, int]:
    seasons = rec.get("seasons") or {}
    if isinstance(seasons, dict):
        return {int(year): int(acc.get("gs") or 0) for year, acc in seasons.items() if int(acc.get("gs") or 0)}
    return {}


def compare_records(stored: dict[str, dict], rolled: dict[str, dict]) -> list[str]:
    """Differences in wins, losses, starts, and titles."""
    mismatches = []
    for name in sorted(set(stored) | set(rolled)):
        left = stored.get(name)
        right = rolled.get(name)
        if left is None or right is None:
            mismatches.append(f"{name}: only in {'stored' if right is None else 'rollup'}")
            continue
        if _stat_key(left) != _stat_key(right):
            mismatches.append(f"{name}: stored {_stat_key(left)} rollup {_stat_key(right)}")
            continue
        if _season_starts(left) != _season_starts(right):
            mismatches.append(f"{name}: season starts stored {_season_starts(left)} rollup {_season_starts(right)}")
    return mismatches


def _column_ready(client, table: str, column: str) -> bool:
    try:
        client.table(table).select(column).limit(1).execute()
    except Exception:
        return False
    return True


def load_stored_weeks(client) -> tuple[list[dict], list[dict]]:
    if not _column_ready(client, "team_weeks", "opponent_owner"):
        raise SystemExit(
            "team_weeks.opponent_owner is missing. Apply the opponent migration before a records rollup."
        )
    team_columns = "season, week, team_id, owner, team_name, points, is_regular, opponent_owner"
    if _column_ready(client, "team_weeks", "is_consolation"):
        team_columns += ", is_consolation"
    player_weeks = fetch_all(
        client,
        "player_weeks",
        "season, week, player_id, name, pos, nfl_team, team_id, owner, started, points",
        ["season", "week", "player_id"],
    )
    team_weeks = fetch_all(
        client,
        "team_weeks",
        team_columns,
        ["season", "week", "team_id"],
    )
    return player_weeks, team_weeks


def records_self_test() -> None:
    players = rollup_records(
        [
            {"season": 2024, "week": 1, "player_id": 1, "name": "Alpha", "pos": "WR", "nfl_team": "SF", "team_id": 1, "started": True, "points": 20},
            {"season": 2024, "week": 1, "player_id": 2, "name": "Bench", "pos": "RB", "nfl_team": "DAL", "team_id": 1, "started": False, "points": 0},
            {"season": 2024, "week": 1, "player_id": 3, "name": "Gamma", "pos": "QB", "nfl_team": "BUF", "team_id": 2, "started": True, "points": 10},
            {"season": 2024, "week": 2, "player_id": 1, "name": "Alpha", "pos": "WR", "nfl_team": "SF", "team_id": 1, "started": True, "points": 15},
            {"season": 2024, "week": 3, "player_id": 4, "name": "OnlyConsolation", "pos": "TE", "nfl_team": "KC", "team_id": 1, "started": True, "points": 8},
        ],
        [
            {"season": 2024, "week": 1, "team_id": 1, "owner": "Noah", "team_name": "Noah", "points": 100, "is_regular": True, "opponent_owner": "Liam", "is_consolation": False},
            {"season": 2024, "week": 1, "team_id": 2, "owner": "Liam", "team_name": "Liam", "points": 90, "is_regular": True, "opponent_owner": "Noah", "is_consolation": False},
            {"season": 2024, "week": 2, "team_id": 1, "owner": "Noah", "team_name": "Noah", "points": 80, "is_regular": False, "opponent_owner": "Liam", "is_consolation": False},
            {"season": 2024, "week": 2, "team_id": 2, "owner": "Liam", "team_name": "Liam", "points": 110, "is_regular": False, "opponent_owner": "Noah", "is_consolation": False},
            {"season": 2024, "week": 3, "team_id": 1, "owner": "Noah", "team_name": "Noah", "points": 50, "is_regular": False, "opponent_owner": "Liam", "is_consolation": True},
            {"season": 2024, "week": 3, "team_id": 2, "owner": "Liam", "team_name": "Liam", "points": 40, "is_regular": False, "opponent_owner": "Noah", "is_consolation": True},
        ],
        {2024: "Noah"},
    )
    alpha = players["Alpha"]
    assert (alpha["g"], alpha["w"], alpha["gs"], alpha["ws"]) == (1, 1, 1, 1)
    assert (alpha["pg"], alpha["pw"], alpha["pgs"], alpha["pws"]) == (1, 0, 1, 0)
    assert alpha["titles"] == 1
    assert players["Bench"]["g"] == 1 and players["Bench"]["gs"] == 0 and players["Bench"]["titles"] == 1
    assert players["Gamma"]["w"] == 0 and players["Gamma"]["titles"] == 0
    assert "OnlyConsolation" not in players
    assert players["Alpha"]["seasons"][2024]["gs"] == 2
    print("records rollup ok")


def run_from_weeks(client, current: int) -> None:
    player_weeks, team_weeks = load_stored_weeks(client)
    if not player_weeks or not team_weeks:
        raise SystemExit("No stored weeks. Run the superlatives ingest, or pass --espn.")
    players = rollup_records(player_weeks, team_weeks)
    if not players:
        raise SystemExit("Records rollup produced no players. Pass --espn to walk box scores.")
    print(f"Rolled up {len(players)} players from {len(player_weeks)} player-weeks")
    client.table("player_records").delete().neq("name", "").execute()
    write_seasons_storage(client, players)
    upsert_players(client, players)
    current_weeks = [int(row["week"]) for row in team_weeks if int(row["season"]) == current and not row.get("is_consolation")]
    champions = [year for year in champions_by_season() if year <= current]
    through = {
        "season": current,
        "week": max(current_weeks) if current_weeks else 0,
        "titles_through_season": max(champions) if champions else FIRST_SEASON - 1,
    }
    write_report(client, through, current)
    ping_revalidate()
    print(f"Wrote {len(players)} player records")


def run_diff(client) -> None:
    player_weeks, team_weeks = load_stored_weeks(client)
    stored, _through = load_from_db(client)
    rolled = rollup_records(player_weeks, team_weeks)
    mismatches = compare_records(stored, rolled)
    print(f"Stored {len(stored)} players, rollup {len(rolled)} players, mismatches {len(mismatches)}")
    for line in mismatches[:40]:
        print(f"  {line}")
    if len(mismatches) > 40:
        print(f"  … {len(mismatches) - 40} more")
    if mismatches:
        raise SystemExit(1)
    print("Records rollup matches stored wins, losses, starts, and titles")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full",
        action="store_true",
        help=f"Recompute every season from {FIRST_SEASON} through the current year.",
    )
    parser.add_argument(
        "--from-weeks",
        action="store_true",
        help="Roll records up from stored weeks. Left off the schedule until --diff is empty.",
    )
    parser.add_argument("--diff", action="store_true", help="Compare the week rollup to stored player_records and exit.")
    parser.add_argument("--self-test", action="store_true", help="Run the rollup checks and exit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_test:
        records_self_test()
        return
    current = season_id()
    client = get_service_client()
    if args.diff:
        run_diff(client)
        return
    if args.from_weeks:
        run_from_weeks(client, current)
        return
    print("NFL teams")
    week_teams = load_week_teams(list(range(FIRST_SEASON, current + 1)))

    if args.full:
        players = {}
        titles_through = FIRST_SEASON - 1
        for year in range(FIRST_SEASON, current + 1):
            print(f"Season {year}")
            league = get_league(year)
            rosters = scrape_weeks(players, year, 1, league.current_week, teams=week_teams)
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
            rosters = scrape_weeks(players, year, week_from, league.current_week, teams=week_teams)
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
