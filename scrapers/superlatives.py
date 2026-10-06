#!/usr/bin/env python3
"""Weekly Superlatives backfill from ESPN box scores and drafts.

Writes player_weeks, team_weeks, draft_picks, player headshots, and the
superlatives podium. Rankings are recomputed for all-time and the current
season on every run. Use --full to rebuild every season from 2022.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from espn_client import FIRST_SEASON, ROOT, get_league, season_id
from player_records import (
    REGULAR_TYPES,
    box_team_id,
    counts_toward_record,
    fantasy_team_name,
    matchup_type,
    owner_name,
)
from revalidate import ping_revalidate
from superlative_ranks import build_superlatives, self_test, usable_owner
from supabase_client import get_service_client, upload_logo

PROJECTION_MIN = 50
HEADSHOT_URL = "https://a.espncdn.com/i/headshots/nfl/players/full/{player_id}.png"
_LINEUP_TOTALS = None


def add_efficiency_path() -> None:
    override = os.environ.get("LINEUP_EFFICIENCY_PATH")
    candidates = []
    if override:
        candidates.append(Path(override))
    candidates.append(ROOT.parent / "coding-projects" / "lineup-efficiency")
    candidates.append(ROOT / "lineup-efficiency")
    for path in candidates:
        if (path / "efficiency.py").is_file():
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
            return
    # CI cannot read the private lineup-efficiency repo. scrapers/efficiency.py
    # is the same module, and this directory is already on sys.path.
    if (Path(__file__).resolve().parent / "efficiency.py").is_file():
        return
    raise SystemExit(
        "Could not find lineup-efficiency/efficiency.py. "
        "Set LINEUP_EFFICIENCY_PATH or check the repo out next to this one."
    )


def lineup_totals(lineup, slots):
    global _LINEUP_TOTALS
    if _LINEUP_TOTALS is None:
        add_efficiency_path()
        from efficiency import lineup_totals as totals

        _LINEUP_TOTALS = totals
    return _LINEUP_TOTALS(lineup, slots)


def load_payouts() -> dict:
    return json.loads((ROOT / "data" / "payouts.json").read_text(encoding="utf-8"))


def last_completed_week(league, year: int, current_season: int) -> int:
    current_week = int(getattr(league, "current_week", 1) or 1)
    if year < current_season:
        return current_week
    return max(current_week - 1, 0)


def nfl_team(player) -> str | None:
    team = getattr(player, "proTeam", None)
    if not team or team == "None":
        return None
    return str(team)


def player_row(year: int, week: int, player, team_id: int, owner: str, team_name: str) -> dict | None:
    player_id = getattr(player, "playerId", None)
    name = getattr(player, "name", None)
    if player_id is None or not name:
        return None
    slot = getattr(player, "lineupSlot", None) or ""
    projected = getattr(player, "projected_points", None)
    return {
        "season": year,
        "week": week,
        "player_id": int(player_id),
        "name": str(name),
        "pos": getattr(player, "position", None),
        "nfl_team": nfl_team(player),
        "team_id": team_id,
        "owner": owner,
        "lineup_slot": slot or None,
        "started": slot not in ("IR", "BE", ""),
        "points": round(float(getattr(player, "points", 0) or 0), 2),
        "projected_points": None if projected is None else round(float(projected), 2),
    }


def side_rows(year: int, week: int, box, side: str, slots: dict, is_regular: bool) -> tuple[list[dict], dict | None, float]:
    team = getattr(box, f"{side}_team")
    lineup = list(getattr(box, f"{side}_lineup") or [])
    team_id = box_team_id(team)
    if team_id is None:
        return [], None, 0.0
    owner = owner_name(year, team_id)
    team_name = fantasy_team_name(team)
    players = []
    for player in lineup:
        row = player_row(year, week, player, team_id, owner, team_name)
        if row:
            players.append(row)
    metrics = lineup_totals(lineup, slots) if lineup else None
    projected_mass = float(metrics["projected_mass"]) if metrics else 0.0
    optimal = None
    projection_points = None
    anti = None
    starter_points = None
    if metrics:
        starter_points = metrics["starter_points"]
        if metrics["optimal_points"] > 0:
            optimal = metrics["optimal_points"]
        projection_points = metrics["projection_lineup_points"]
        anti = metrics["anti_projection_starts"]
    team_row = {
        "season": year,
        "week": week,
        "team_id": team_id,
        "owner": owner,
        "team_name": team_name or None,
        "points": round(float(getattr(box, f"{side}_score", 0) or 0), 2),
        "is_regular": is_regular,
        "starter_points": starter_points,
        "optimal_points": optimal,
        "projection_lineup_points": projection_points,
        "anti_projection_starts": anti,
        "projections_ok": False,
    }
    return players, team_row, projected_mass


def scrape_season(league, year: int, current_season: int) -> tuple[list[dict], list[dict], list[dict], int]:
    slots = dict(getattr(league.settings, "position_slot_counts", {}) or {})
    last_week = last_completed_week(league, year, current_season)
    player_rows: list[dict] = []
    team_rows: list[dict] = []
    for week in range(1, last_week + 1):
        try:
            boxes = league.box_scores(week=week)
        except Exception as exc:
            print(f"  {year} week {week} skipped: {exc}")
            continue
        if not boxes:
            print(f"  {year} week {week} empty")
            continue
        week_players: dict[int, dict] = {}
        week_teams: dict[int, dict] = {}
        projected_mass = 0.0
        for box in boxes:
            kind = matchup_type(box)
            home_id = box_team_id(box.home_team)
            away_id = box_team_id(box.away_team)
            if not counts_toward_record(kind, home_id, away_id):
                continue
            is_regular = kind in REGULAR_TYPES
            for side in ("home", "away"):
                players, team_row, mass = side_rows(year, week, box, side, slots, is_regular)
                projected_mass += mass
                for row in players:
                    week_players[row["player_id"]] = row
                if team_row:
                    week_teams[team_row["team_id"]] = team_row
        if not week_teams:
            continue
        projections_ok = projected_mass >= PROJECTION_MIN
        if not projections_ok:
            print(f"  {year} week {week}: projections ignored ({projected_mass:.0f} projected points)")
        for row in week_teams.values():
            row["projections_ok"] = projections_ok
            if not projections_ok:
                row["projection_lineup_points"] = None
                row["anti_projection_starts"] = None
        player_rows.extend(week_players.values())
        team_rows.extend(week_teams.values())
        print(f"  {year} week {week}: {len(week_teams)} teams")
    return player_rows, team_rows, draft_rows_from(league, year), last_week


def draft_rows_from(league, year: int) -> list[dict]:
    rows = []
    seen: set[int] = set()
    for pick in getattr(league, "draft", None) or []:
        player_id = getattr(pick, "playerId", None)
        if not player_id:
            continue
        player_id = int(player_id)
        if player_id in seen:
            continue
        seen.add(player_id)
        team_id = box_team_id(getattr(pick, "team", None))
        name = getattr(pick, "playerName", None) or str(player_id)
        rows.append(
            {
                "season": year,
                "player_id": player_id,
                "name": str(name),
                "pos": getattr(pick, "position", None),
                "team_id": team_id,
                "owner": owner_name(year, team_id) if team_id else None,
                "bid": round(float(getattr(pick, "bid_amount", 0) or 0), 2),
            }
        )
    return rows


def load_finishers(payouts: dict) -> dict[int, dict[int, str]]:
    finishers: dict[int, dict[int, str]] = {}
    for year in sorted(int(value) for value in (payouts.get("season_finish") or {})):
        league = get_league(year)
        places: dict[int, str] = {}
        for team in league.teams:
            place = getattr(team, "final_standing", None)
            if not place:
                continue
            places[int(place)] = owner_name(year, getattr(team, "team_id", None))
        finishers[year] = places
        print(f"  {year} final: {places.get(1) or '—'} / {places.get(2) or '—'}")
    return finishers


def fetch_all(client, table: str, columns: str, orders: list[str]) -> list[dict]:
    rows: list[dict] = []
    start = 0
    size = 1000
    while True:
        query = client.table(table).select(columns)
        for column in orders:
            query = query.order(column)
        batch = query.range(start, start + size - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < size:
            return rows
        start += size


def delete_season(client, table: str, season: int) -> None:
    previous = None
    for _ in range(40):
        probe = (
            client.table(table)
            .select("season", count="exact")
            .eq("season", season)
            .limit(1)
            .execute()
        )
        left = probe.count or 0
        if left == 0:
            return
        if previous is not None and left >= previous:
            raise SystemExit(f"Could not clear {table} for {season} ({left} rows left)")
        previous = left
        client.table(table).delete().eq("season", season).execute()


def insert_chunks(client, table: str, rows: list[dict]) -> None:
    for index in range(0, len(rows), 200):
        client.table(table).insert(rows[index : index + 200]).execute()


def write_season(client, year: int, player_rows: list[dict], team_rows: list[dict], draft_rows: list[dict]) -> None:
    delete_season(client, "player_weeks", year)
    delete_season(client, "team_weeks", year)
    insert_chunks(client, "player_weeks", player_rows)
    insert_chunks(client, "team_weeks", team_rows)
    if draft_rows:
        delete_season(client, "draft_picks", year)
        insert_chunks(client, "draft_picks", draft_rows)
    else:
        print(f"  {year}: no draft picks returned; leaving stored picks in place")


def load_logos(client) -> dict[tuple[int, str], str]:
    rows = fetch_all(client, "fantasy_logos", "season, owner, logo_path", ["season", "team_id"])
    logos: dict[tuple[int, str], str] = {}
    for row in rows:
        owner = usable_owner(row.get("owner"))
        path = row.get("logo_path")
        if owner and path:
            logos[(int(row["season"]), owner)] = path
    return logos


def normalize_player(row: dict) -> dict:
    return {
        "season": int(row["season"]),
        "week": int(row["week"]),
        "player_id": int(row["player_id"]),
        "name": row["name"],
        "pos": row.get("pos"),
        "nfl_team": row.get("nfl_team"),
        "team_id": int(row["team_id"]),
        "owner": row.get("owner"),
        "started": bool(row.get("started")),
        "points": float(row.get("points") or 0),
    }


def normalize_number(value):
    if value is None:
        return None
    return float(value)


def normalize_team(row: dict) -> dict:
    anti = row.get("anti_projection_starts")
    return {
        "season": int(row["season"]),
        "week": int(row["week"]),
        "team_id": int(row["team_id"]),
        "owner": row.get("owner"),
        "team_name": row.get("team_name"),
        "points": float(row.get("points") or 0),
        "is_regular": bool(row.get("is_regular")),
        "starter_points": float(row.get("starter_points") or 0),
        "optimal_points": normalize_number(row.get("optimal_points")),
        "projection_lineup_points": normalize_number(row.get("projection_lineup_points")),
        "anti_projection_starts": None if anti is None else int(anti),
        "projections_ok": bool(row.get("projections_ok")),
    }


def normalize_pick(row: dict) -> dict:
    team_id = row.get("team_id")
    return {
        "season": int(row["season"]),
        "player_id": int(row["player_id"]),
        "name": row["name"],
        "pos": row.get("pos"),
        "team_id": None if team_id is None else int(team_id),
        "bid": float(row.get("bid") or 0),
    }


def normalize_trade(row: dict) -> dict:
    return {
        "season": int(row["season"]),
        "owners": list(row.get("owners") or []),
    }


def _collect_photo_ids(detail: dict, found: dict[int, str], fallback: str) -> None:
    player_id = detail.get("player_id")
    if player_id is not None:
        found[int(player_id)] = detail.get("player_name") or fallback
    partner_id = detail.get("partner_id")
    if partner_id is not None:
        found[int(partner_id)] = detail.get("partner_name") or "Player"
    for alt in detail.get("alternates") or []:
        _collect_photo_ids(alt.get("detail") or {}, found, alt.get("subject_name") or "Player")


def photo_targets(rows: list[dict]) -> dict[int, str]:
    found: dict[int, str] = {}
    for row in rows:
        _collect_photo_ids(row.get("detail") or {}, found, row["subject_name"])
    return found


def download_headshot(client, player_id: int) -> str | None:
    url = HEADSHOT_URL.format(player_id=player_id)
    try:
        response = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "commissioner-report"},
        )
    except requests.RequestException as exc:
        print(f"  photo {player_id} failed: {exc}")
        return None
    content = response.content or b""
    if response.status_code != 200 or len(content) < 400:
        return None
    content_type = (response.headers.get("content-type") or "").lower()
    if "png" in content_type or content.startswith(b"\x89PNG"):
        ext, mime = "png", "image/png"
    elif "jpeg" in content_type or "jpg" in content_type or content.startswith(b"\xff\xd8"):
        ext, mime = "jpg", "image/jpeg"
    else:
        return None
    path = f"players/{player_id}.{ext}"
    try:
        upload_logo(client, path, content, mime)
    except Exception as exc:
        print(f"  photo {player_id} upload failed: {exc}")
        return None
    return path


def ensure_photos(client, players: dict[int, str]) -> dict[int, str | None]:
    if not players:
        return {}
    existing = fetch_all(client, "player_photos", "player_id, photo_path", ["player_id"])
    known = {int(row["player_id"]): row.get("photo_path") for row in existing}
    paths: dict[int, str | None] = {}
    for player_id, name in sorted(players.items()):
        if player_id in known:
            paths[player_id] = known[player_id]
            continue
        path = download_headshot(client, player_id)
        client.table("player_photos").upsert(
            {"player_id": player_id, "name": name, "photo_path": path}
        ).execute()
        paths[player_id] = path
        print(f"  photo {name}: {path or 'none'}")
    return paths


def _paint_photos(detail: dict, paths: dict[int, str | None]) -> None:
    player_id = detail.get("player_id")
    if player_id is not None and paths.get(int(player_id)):
        detail["photo_path"] = paths[int(player_id)]
    partner_id = detail.get("partner_id")
    if partner_id is not None and paths.get(int(partner_id)):
        detail["partner_photo_path"] = paths[int(partner_id)]
    for alt in detail.get("alternates") or []:
        _paint_photos(alt.get("detail") or {}, paths)


def apply_photos(rows: list[dict], paths: dict[int, str | None]) -> None:
    for row in rows:
        _paint_photos(row["detail"], paths)


def replace_rankings(client, rows: list[dict]) -> None:
    previous = None
    for _ in range(10):
        probe = client.table("superlatives").select("category", count="exact").limit(1).execute()
        left = probe.count or 0
        if left == 0:
            break
        if previous is not None and left >= previous:
            raise SystemExit(f"Could not clear superlatives ({left} rows left)")
        previous = left
        client.table("superlatives").delete().neq("category", "").execute()
    insert_chunks(client, "superlatives", rows)


def write_report(client, current: int, through_week: int) -> None:
    client.table("reports").upsert(
        {
            "id": "superlatives",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "season": current,
            "current_week": through_week + 1,
            "through_season": current,
            "through_week": through_week,
        }
    ).execute()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full",
        action="store_true",
        help=f"Rebuild every season from {FIRST_SEASON} through the current year.",
    )
    parser.add_argument("--self-test", action="store_true", help="Run ranking checks and exit.")
    parser.add_argument(
        "--ranks-only",
        action="store_true",
        help="Rebuild rankings from stored weeks without calling ESPN.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return

    current = season_id()
    years = (
        []
        if args.ranks_only
        else list(range(FIRST_SEASON, current + 1))
        if args.full
        else [current]
    )
    client = get_service_client()
    payouts = load_payouts()
    through_week = 0
    for year in years:
        print(f"Season {year}")
        league = get_league(year)
        player_rows, team_rows, draft_rows, last_week = scrape_season(league, year, current)
        if year == current:
            through_week = last_week
        if last_week >= 1 and not team_rows:
            raise SystemExit(f"{year}: no completed weeks scraped; existing rows left in place")
        if last_week < 1:
            print("  no completed weeks")
            continue
        write_season(client, year, player_rows, team_rows, draft_rows)
        print(
            f"  wrote {len(player_rows)} player-weeks, "
            f"{len(team_rows)} team-weeks, {len(draft_rows)} draft picks"
        )

    print("Rankings")
    finishers = load_finishers(payouts)
    logos = load_logos(client)
    player_weeks = [
        normalize_player(row)
        for row in fetch_all(
            client,
            "player_weeks",
            "season, week, player_id, name, pos, nfl_team, team_id, owner, started, points",
            ["season", "week", "player_id"],
        )
    ]
    team_weeks = [
        normalize_team(row)
        for row in fetch_all(
            client,
            "team_weeks",
            "season, week, team_id, owner, team_name, points, is_regular, starter_points, optimal_points, projection_lineup_points, anti_projection_starts, projections_ok",
            ["season", "week", "team_id"],
        )
    ]
    draft_picks = [
        normalize_pick(row)
        for row in fetch_all(
            client,
            "draft_picks",
            "season, player_id, name, pos, team_id, bid",
            ["season", "player_id"],
        )
    ]
    trades = [
        normalize_trade(row)
        for row in fetch_all(client, "trades", "season, owners", ["season", "id"])
    ]
    rows = build_superlatives(
        player_weeks,
        team_weeks,
        draft_picks,
        trades,
        payouts,
        finishers,
        logos,
        current,
    )
    apply_photos(rows, ensure_photos(client, photo_targets(rows)))
    replace_rankings(client, rows)
    if not args.ranks_only:
        write_report(client, current, through_week)
    ping_revalidate()
    print(f"Wrote {len(rows)} superlative rows")


if __name__ == "__main__":
    main()
