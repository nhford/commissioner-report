#!/usr/bin/env python3
"""Archive ESPN Recent Activity for the current season.

The communication feed is not reliable year-over-year. Paginate the current
season, upsert by topic id, and keep the raw topic plus normalized actions.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from espn_client import get_league
from logo_utils import owner_for
from supabase_client import get_service_client

ACTIVITY_MSG_TYPES = [178, 180, 179, 239, 181, 244]
ACTION_MAP = {
    178: "FA ADDED",
    180: "WAIVER ADDED",
    179: "DROPPED",
    181: "DROPPED",
    239: "DROPPED",
    244: "TRADED",
}
PAGE_SIZE = 25


def fetch_activity_page(league, offset: int, size: int = PAGE_SIZE) -> list[dict]:
    params = {"view": "kona_league_communication"}
    filters = {
        "topics": {
            "filterType": {"value": ["ACTIVITY_TRANSACTIONS"]},
            "limit": size,
            "limitPerMessageSet": {"value": 25},
            "offset": offset,
            "sortMessageDate": {"sortPriority": 1, "sortAsc": False},
            "sortFor": {"sortPriority": 2, "sortAsc": False},
            "filterIncludeMessageTypeIds": {"value": ACTIVITY_MSG_TYPES},
        }
    }
    data = league.espn_request.league_get(
        extend="/communication/",
        params=params,
        headers={"x-fantasy-filter": json.dumps(filters)},
    )
    return data.get("topics") or []


def fetch_all_topics(league) -> list[dict]:
    topics: list[dict] = []
    offset = 0
    while True:
        page = fetch_activity_page(league, offset)
        if not page:
            break
        topics.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return topics


def player_name(league, player_id) -> str | None:
    if player_id is None:
        return None
    name = league.player_map.get(player_id)
    if isinstance(name, str):
        return name
    return None


def team_action(
    league,
    team_id,
    action: str,
    player_id,
    bid_amount: float = 0,
) -> dict:
    owner = owner_for(league.year, team_id) if team_id else None
    return {
        "owner": owner,
        "team_id": team_id,
        "action": action,
        "player_id": player_id,
        "player_name": player_name(league, player_id),
        "bid_amount": bid_amount,
    }


def actions_from_topic(league, topic: dict) -> list[dict]:
    actions: list[dict] = []
    for msg in topic.get("messages") or []:
        msg_id = msg.get("messageTypeId")
        player_id = msg.get("targetId")
        if msg_id == 244:
            from_id = msg.get("from")
            to_id = msg.get("to")
            actions.append(team_action(league, from_id, "TRADE_SENT", player_id))
            if to_id:
                actions.append(team_action(league, to_id, "TRADE_RECEIVED", player_id))
            continue
        if msg_id == 239:
            team_id = msg.get("for")
        else:
            team_id = msg.get("to")
        action = ACTION_MAP.get(msg_id, "UNKNOWN")
        bid = float(msg.get("from") or 0) if action == "WAIVER ADDED" else 0
        actions.append(team_action(league, team_id, action, player_id, bid))
    return actions


def occurred_at(topic: dict) -> str:
    raw = topic.get("date") or 0
    seconds = raw / 1000 if raw > 1e12 else raw
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def row_from_topic(league, topic: dict) -> dict | None:
    topic_id = topic.get("id")
    if topic_id is None:
        return None
    return {
        "id": str(topic_id),
        "season": league.year,
        "occurred_at": occurred_at(topic),
        "actions": actions_from_topic(league, topic),
        "raw": topic,
    }


def write_activity(client, league, rows: list[dict]) -> None:
    for i in range(0, len(rows), 200):
        client.table("league_activity").upsert(rows[i : i + 200]).execute()
    client.table("reports").upsert(
        {
            "id": "league-activity",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "season": league.year,
        }
    ).execute()
    print(f"Upserted {len(rows)} activity topics for {league.year}")


def main() -> None:
    league = get_league()
    topics = fetch_all_topics(league)
    rows = [row for topic in topics if (row := row_from_topic(league, topic))]
    client = get_service_client()
    write_activity(client, league, rows)


if __name__ == "__main__":
    main()
