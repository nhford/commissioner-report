#!/usr/bin/env python3
"""Daily ESPN week-projection snapshot for rostered players and top free agents.

Inserts a dated pull: every rostered player, the top 50 FA by week projection,
and the top 50 FA by percent owned. ESPN does not keep this time series.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from espn_api.football.box_player import BoxPlayer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from espn_client import get_league
from logo_utils import owner_for
from supabase_client import get_service_client

FA_LIMIT = 50


def week_projection(player, week: int) -> float:
    stats = getattr(player, "stats", None) or {}
    from_stats = (stats.get(week) or {}).get("projected_points")
    if from_stats is not None:
        return float(from_stats)
    return float(getattr(player, "projected_points", 0) or 0)


def percent_owned(player) -> float | None:
    owned = getattr(player, "percent_owned", None)
    if owned is None or owned < 0:
        return None
    return float(owned)


def injury_status(player) -> str | None:
    status = getattr(player, "injuryStatus", None)
    return str(status) if status else None


def empty_row(player, week: int) -> dict:
    return {
        "player_id": int(player.playerId),
        "name": player.name,
        "pos": player.position or None,
        "nfl_team": getattr(player, "proTeam", None) or None,
        "injury_status": injury_status(player),
        "owner": None,
        "fantasy_team": None,
        "lineup_slot": None,
        "projected_points": week_projection(player, week),
        "percent_owned": percent_owned(player),
        "rostered": False,
        "fa_top_projected": False,
        "fa_top_owned": False,
    }


def merge_player(rows: dict[int, dict], player, week: int) -> dict:
    player_id = int(player.playerId)
    rec = rows.get(player_id)
    if rec is None:
        rec = empty_row(player, week)
        rows[player_id] = rec
        return rec
    rec["projected_points"] = week_projection(player, week)
    owned = percent_owned(player)
    if owned is not None:
        rec["percent_owned"] = owned
    if not rec["pos"] and player.position:
        rec["pos"] = player.position
    if not rec["nfl_team"] and getattr(player, "proTeam", None):
        rec["nfl_team"] = player.proTeam
    if not rec["injury_status"]:
        rec["injury_status"] = injury_status(player)
    return rec


def collect_rostered(league, week: int) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for team in league.teams:
        owner = owner_for(league.year, team.team_id)
        for player in team.roster:
            rec = merge_player(rows, player, week)
            rec["rostered"] = True
            rec["owner"] = owner
            rec["fantasy_team"] = team.team_name
            slot = getattr(player, "lineupSlot", None) or None
            rec["lineup_slot"] = slot or None
    return rows


def free_agents_by_owned(league, week: int) -> list:
    return league.free_agents(week=week, size=FA_LIMIT)


def free_agents_by_projection(league, week: int) -> list:
    """espn-api free_agents() sorts by % owned; this sorts by week projection."""
    stat_id = f"11{league.year}{week}"
    params = {
        "view": "kona_player_info",
        "scoringPeriodId": week,
    }
    filters = {
        "players": {
            "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
            "filterSlotIds": {"value": []},
            "limit": FA_LIMIT,
            "sortAppliedStatTotal": {
                "sortAsc": False,
                "sortPriority": 1,
                "value": stat_id,
            },
        }
    }
    data = league.espn_request.league_get(
        params=params,
        headers={"x-fantasy-filter": json.dumps(filters)},
    )
    players = data.get("players") or []
    pro_schedule = league._get_pro_schedule(week)
    positional_rankings = league._get_positional_ratings(week)
    return [
        BoxPlayer(player, pro_schedule, positional_rankings, week, league.year)
        for player in players
    ]


def collect_snapshot(league) -> tuple[int, list[dict]]:
    week = int(league.current_week)
    rows = collect_rostered(league, week)
    for player in free_agents_by_projection(league, week):
        rec = merge_player(rows, player, week)
        if not rec["rostered"]:
            rec["fa_top_projected"] = True
    for player in free_agents_by_owned(league, week):
        rec = merge_player(rows, player, week)
        if not rec["rostered"]:
            rec["fa_top_owned"] = True
    return week, list(rows.values())


def write_pull(client, league, week: int, rows: list[dict]) -> None:
    pulled_at = datetime.now(timezone.utc).isoformat()
    pull = (
        client.table("player_projection_pulls")
        .insert(
            {
                "pulled_at": pulled_at,
                "season": league.year,
                "week": week,
            }
        )
        .execute()
        .data[0]
    )
    payload = [{**row, "pull_id": pull["id"]} for row in rows]
    for i in range(0, len(payload), 200):
        client.table("player_projections").insert(payload[i : i + 200]).execute()
    client.table("reports").upsert(
        {
            "id": "player-projections",
            "last_updated": pulled_at,
            "season": league.year,
            "current_week": week,
        }
    ).execute()
    print(f"Inserted projection pull {pull['id']} ({len(payload)} players, week {week})")


def main() -> None:
    league = get_league()
    week, rows = collect_snapshot(league)
    client = get_service_client()
    write_pull(client, league, week, rows)


if __name__ == "__main__":
    main()
