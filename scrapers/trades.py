#!/usr/bin/env python3
"""Completed ESPN trades by owner. Writes to Supabase for Trade-o-gami.

Pulls every season from FIRST_SEASON through the current year. When the
communication activity feed names both sides of a deal, those topics are
the season's trades. Otherwise partners come only from bidirectional roster
swaps and from transaction groups whose TRADE items name two teams. A short
ESPN trade counter is reported, never filled in with a guessed partner.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from espn_client import FIRST_SEASON, get_league, season_id
from logo_utils import owner_for
from recent_activity import actions_from_topic, fetch_all_topics, occurred_at
from revalidate import ping_revalidate
from superlative_ranks import activity_scoring_week
from supabase_client import get_service_client

TRADE_FILTER_TYPES = [
    "TRADE_ACCEPT",
    "TRADE_VETO",
    "TRADE_PROPOSAL",
    "TRADE_UPHOLD",
    "TRADE_DECLINE",
    "TRADE_ERROR",
]


def owners_from_team_ids(year: int, team_ids: set[int]) -> list[str]:
    names = []
    for team_id in team_ids:
        name = owner_for(year, team_id)
        if name:
            names.append(name)
    return sorted(set(names))


def fetch_period_trades(league, scoring_period: int) -> list[dict]:
    data = league.espn_request.league_get(
        params={"view": "mTransactions2", "scoringPeriodId": scoring_period},
        headers={
            "x-fantasy-filter": json.dumps(
                {"transactions": {"filterType": {"value": TRADE_FILTER_TYPES}}}
            )
        },
    )
    return data.get("transactions") or []


def trade_item_team_ids(txn: dict) -> set[int]:
    """Teams named on TRADE items. A drop, or the accepting team alone, is not a partner."""
    team_ids: set[int] = set()
    for item in txn.get("items") or []:
        if (item.get("type") or "").upper() != "TRADE":
            continue
        for key in ("fromTeamId", "toTeamId"):
            value = item.get(key)
            if isinstance(value, int) and value > 0:
                team_ids.add(value)
    return team_ids


def is_completed_group(rows: list[dict]) -> bool:
    types = {row["type"] for row in rows}
    if "TRADE_ACCEPT" not in types:
        return False
    if "TRADE_VETO" in types and "TRADE_UPHOLD" not in types:
        return False
    return True


def official_trade_counts(league) -> dict[int, int]:
    return {team.team_id: int(getattr(team, "trades", 0) or 0) for team in league.teams}


def draft_snapshot(league) -> dict[int, int]:
    snap: dict[int, int] = {}
    for pick in getattr(league, "draft", None) or []:
        team_id = getattr(pick.team, "team_id", None)
        if team_id and pick.playerId:
            snap[pick.playerId] = team_id
    return snap


def roster_snapshots(league, last_week: int) -> dict[int, dict[int, int]]:
    snaps: dict[int, dict[int, int]] = {}
    draft = draft_snapshot(league)
    if draft:
        snaps[0] = draft
    for week in range(1, last_week + 1):
        league.load_roster_week(week)
        snap: dict[int, int] = {}
        for team in league.teams:
            for player in team.roster:
                snap[player.playerId] = team.team_id
        snaps[week] = snap
    return snaps


def week_moves(
    snaps: dict[int, dict[int, int]],
) -> dict[int, dict[tuple[int, int], list[int]]]:
    """week -> (lo, hi) -> [moves lo->hi, moves hi->lo]."""
    out: dict[int, dict[tuple[int, int], list[int]]] = defaultdict(
        lambda: defaultdict(lambda: [0, 0])
    )
    weeks = sorted(snaps)
    for i in range(1, len(weeks)):
        prev, curr = snaps[weeks[i - 1]], snaps[weeks[i]]
        raw: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        for player_id, team in curr.items():
            prev_team = prev.get(player_id)
            if prev_team and prev_team != team:
                raw[prev_team][team] += 1
        for src, dests in raw.items():
            for dest, n in dests.items():
                lo, hi = (src, dest) if src < dest else (dest, src)
                if src < dest:
                    out[weeks[i]][(lo, hi)][0] += n
                else:
                    out[weeks[i]][(lo, hi)][1] += n
    return out


def pairs_from_transaction_rows(rows: list[dict]) -> list[tuple[int, int, int, str]]:
    """Completed groups whose TRADE items name exactly two teams.

    Each related-transaction group is one deal. An accept that only drops a
    player does not borrow a partner from the roster.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for txn in rows:
        kind = (txn.get("type") or "").upper()
        if "TRADE" not in kind:
            continue
        group_id = txn.get("relatedTransactionId") or txn.get("id")
        if not group_id:
            continue
        groups[str(group_id)].append(txn)

    pairs: list[tuple[int, int, int, str]] = []
    for group_id, group in groups.items():
        typed = [{"type": (txn.get("type") or "").upper()} for txn in group]
        if not is_completed_group(typed):
            continue
        team_ids: set[int] = set()
        week = 0
        for txn in group:
            kind = (txn.get("type") or "").upper()
            if kind == "TRADE_ACCEPT":
                week = int(txn.get("scoringPeriodId") or week or 0)
            elif not week:
                week = int(txn.get("scoringPeriodId") or 0)
            team_ids |= trade_item_team_ids(txn)
        if len(team_ids) != 2:
            continue
        a, b = sorted(team_ids)
        pairs.append((week, a, b, group_id))
    return pairs


def collect_accept_pairs(league, last_week: int) -> list[tuple[int, int, int, str]]:
    rows: list[dict] = []
    failures = 0
    for week in range(1, last_week + 1):
        try:
            rows.extend(fetch_period_trades(league, week))
        except Exception as exc:
            failures += 1
            if failures == 1:
                print(f"  mTransactions2 week {week} failed: {exc}")
            continue
    if failures > 1:
        print(f"  mTransactions2 failed for {failures} weeks")
    return pairs_from_transaction_rows(rows)


def select_evidenced(
    official: dict[int, int],
    moves: dict[int, dict[tuple[int, int], list[int]]],
    accept_pairs: list[tuple[int, int, int, str]],
) -> list[dict]:
    """Bidirectional swaps, then accepts for a week and pair not already counted.

    One-direction roster moves are ignored. They are how a drop and a later
    waiver add look like a trade. Nothing is invented to meet the ESPN counter.
    """
    counts: dict[int, int] = defaultdict(int)
    selected: list[dict] = []
    covered: set[tuple[int, int, int]] = set()

    def can_add(a: int, b: int) -> bool:
        return counts[a] < official.get(a, 0) and counts[b] < official.get(b, 0)

    def add(week: int, a: int, b: int, source: str) -> bool:
        if not can_add(a, b):
            return False
        counts[a] += 1
        counts[b] += 1
        selected.append({"week": week, "teams": (a, b), "source": source})
        return True

    for week, pairs in moves.items():
        for (a, b), (n_ab, n_ba) in pairs.items():
            if n_ab and n_ba and add(week, a, b, "bi"):
                covered.add((week, a, b))

    seen_groups: set[str] = set()
    for week, a, b, group_id in accept_pairs:
        if group_id in seen_groups or (week, a, b) in covered:
            continue
        if add(week, a, b, "accept"):
            seen_groups.add(group_id)

    return selected


def trade_row_from_topic(league, topic: dict) -> dict | None:
    topic_id = topic.get("id")
    if topic_id is None:
        return None
    owners: list[str] = []
    for action in actions_from_topic(league, topic):
        if action.get("action") not in {"TRADE_SENT", "TRADE_RECEIVED"}:
            continue
        owner = action.get("owner")
        if owner and owner not in owners:
            owners.append(owner)
    if len(owners) < 2:
        return None
    return {
        "id": f"{league.year}:activity:{topic_id}",
        "season": league.year,
        "week": activity_scoring_week(occurred_at(topic), league.year),
        "owners": sorted(owners),
    }


def trades_from_topics(league, topics: list[dict]) -> list[dict]:
    """One row per activity topic. A repeated topic id is the same deal."""
    trades: list[dict] = []
    seen: set[str] = set()
    for topic in topics:
        row = trade_row_from_topic(league, topic)
        if not row or row["id"] in seen:
            continue
        seen.add(row["id"])
        trades.append(row)
    return trades


def scrape_activity(league) -> list[dict] | None:
    """Trades named by the activity feed. None means the feed could not be read."""
    try:
        topics = fetch_all_topics(league)
    except Exception as exc:
        print(f"  activity feed failed: {exc}")
        return None
    return trades_from_topics(league, topics)


def scrape_transactions(league) -> list[dict]:
    last_week = max(int(getattr(league, "current_week", 1) or 1), 1)
    official = official_trade_counts(league)
    snaps = roster_snapshots(league, last_week)
    accept_pairs = collect_accept_pairs(league, last_week)
    selected = select_evidenced(official, week_moves(snaps), accept_pairs)
    trades: list[dict] = []
    for i, row in enumerate(selected):
        owners = owners_from_team_ids(league.year, set(row["teams"]))
        if len(owners) < 2:
            continue
        trades.append(
            {
                "id": f"{league.year}:{row['source']}:{row['week']}:{'-'.join(map(str, row['teams']))}:{i}",
                "season": league.year,
                "week": int(row["week"]),
                "owners": owners,
            }
        )
    return trades


def scrape_season(league) -> list[dict]:
    activity = scrape_activity(league)
    if activity:
        print(f"  activity feed: {len(activity)} trades")
        return activity
    if activity is not None:
        print("  activity feed has no trades; using roster swaps and named trades")
    return scrape_transactions(league)


def print_validation(league, trades: list[dict]) -> None:
    official = {
        owner_for(league.year, team.team_id): int(getattr(team, "trades", 0) or 0)
        for team in league.teams
    }
    official = {name: n for name, n in official.items() if name}
    got: dict[str, int] = defaultdict(int)
    for row in trades:
        for name in set(row["owners"]):
            got[name] += 1
    espn_n = sum(official.values()) // 2
    print(f"  {len(trades)} trades (ESPN counter {espn_n})")
    mismatches = []
    for name in sorted(set(official) | set(got), key=lambda n: (-official.get(n, 0), n)):
        o, g = official.get(name, 0), got.get(name, 0)
        if o != g:
            mismatches.append(f"{name} espn={o} got={g}")
    if mismatches:
        print("  counter mismatch: " + "; ".join(mismatches))


def replace_trades(client, trades: list[dict]) -> None:
    try:
        client.table("trades").delete().neq("id", "").execute()
    except Exception as exc:
        raise SystemExit(
            "Supabase is missing public.trades. Run "
            "supabase/migrations/20260903200000_trades.sql in the SQL editor, "
            f"then rerun this scraper. ({exc})"
        ) from exc
    for i in range(0, len(trades), 200):
        client.table("trades").upsert(trades[i : i + 200]).execute()


def write_report(client, current: int, trades: list[dict]) -> None:
    latest_season = max((row["season"] for row in trades), default=current)
    latest_week = max(
        (row["week"] for row in trades if row["season"] == latest_season),
        default=0,
    )
    client.table("reports").upsert(
        {
            "id": "trade-o-gami",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "season": current,
            "through_season": latest_season,
            "through_week": latest_week,
        }
    ).execute()


def self_test() -> None:
    assert select_evidenced({6: 1, 13: 1}, {}, []) == []
    assert (
        select_evidenced({6: 1, 13: 1}, {5: {(6, 13): [1, 0]}}, []) == []
    ), "a one-way roster move is not a trade"
    assert all(
        row["source"] != "fill"
        for row in select_evidenced({6: 1, 13: 1}, {5: {(6, 13): [3, 0]}}, [])
    )

    drop_only = [
        {
            "type": "TRADE_ACCEPT",
            "id": "acc",
            "relatedTransactionId": "grp",
            "scoringPeriodId": 5,
            "teamId": 13,
            "items": [{"type": "DROP", "playerId": 9, "fromTeamId": 13, "toTeamId": 0}],
        }
    ]
    assert pairs_from_transaction_rows(drop_only) == []
    assert select_evidenced({2: 1, 13: 1}, {5: {(2, 13): [0, 1]}}, []) == []

    named = [
        {
            "type": "TRADE_PROPOSAL",
            "id": "grp",
            "scoringPeriodId": 5,
            "teamId": 14,
            "items": [{"type": "TRADE", "playerId": 1, "fromTeamId": 14, "toTeamId": 13}],
        },
        {
            "type": "TRADE_ACCEPT",
            "id": "acc",
            "relatedTransactionId": "grp",
            "scoringPeriodId": 5,
            "teamId": 13,
            "items": [{"type": "DROP", "playerId": 9, "fromTeamId": 13, "toTeamId": 0}],
        },
    ]
    assert pairs_from_transaction_rows(named) == [(5, 13, 14, "grp")]

    vetoed = [
        {
            "type": "TRADE_ACCEPT",
            "id": "acc",
            "relatedTransactionId": "g",
            "scoringPeriodId": 1,
            "items": [{"type": "TRADE", "fromTeamId": 1, "toTeamId": 2}],
        },
        {
            "type": "TRADE_VETO",
            "id": "veto",
            "relatedTransactionId": "g",
            "scoringPeriodId": 1,
            "items": [],
        },
    ]
    assert pairs_from_transaction_rows(vetoed) == []

    bi = select_evidenced({1: 1, 12: 1}, {2: {(1, 12): [2, 1]}}, [])
    assert len(bi) == 1 and bi[0]["source"] == "bi" and bi[0]["teams"] == (1, 12)

    once = select_evidenced(
        {5: 1, 6: 1},
        {4: {(5, 6): [1, 1]}},
        [(4, 5, 6, "same-deal")],
    )
    assert len(once) == 1 and once[0]["source"] == "bi"

    twice = select_evidenced(
        {5: 2, 6: 2},
        {},
        [(4, 5, 6, "first"), (5, 5, 6, "second")],
    )
    assert [row["source"] for row in twice] == ["accept", "accept"]

    repeated = select_evidenced(
        {5: 2, 6: 2},
        {},
        [(4, 5, 6, "same"), (4, 5, 6, "same")],
    )
    assert len(repeated) == 1

    class _League:
        year = 2026
        player_map = {1: "Roman Wilson", 2: "Kyler Murray", 3: "Darren Waller"}

    when = int(datetime(2026, 10, 7, 15, 57, tzinfo=timezone.utc).timestamp() * 1000)
    keshav = {
        "id": "keshav-sam",
        "date": when,
        "messages": [{"messageTypeId": 244, "targetId": 1, "from": 14, "to": 13}],
    }
    stephen_a = {
        "id": "ajay-stephen-1",
        "date": when,
        "messages": [
            {"messageTypeId": 244, "targetId": 2, "from": 6, "to": 5},
            {"messageTypeId": 244, "targetId": 3, "from": 5, "to": 6},
        ],
    }
    stephen_b = {
        "id": "ajay-stephen-2",
        "date": when,
        "messages": [
            {"messageTypeId": 244, "targetId": 3, "from": 6, "to": 5},
            {"messageTypeId": 244, "targetId": 2, "from": 5, "to": 6},
        ],
    }
    league = _League()
    rows = trades_from_topics(league, [keshav, stephen_a, stephen_b, keshav])
    assert [row["owners"] for row in rows if "Keshav" in row["owners"]] == [
        ["Keshav", "Sam"]
    ]
    assert sum(1 for row in rows if row["owners"] == ["Ajay", "Stephen"]) == 2
    assert rows[0]["week"] == activity_scoring_week(occurred_at(keshav), 2026)
    assert rows[0]["id"] == "2026:activity:keshav-sam"

    print("trades ok")


def main() -> None:
    if "--self-test" in sys.argv:
        self_test()
        return
    current = season_id()
    client = get_service_client()
    trades: list[dict] = []
    for year in range(FIRST_SEASON, current + 1):
        print(f"Season {year}")
        league = get_league(year)
        found = scrape_season(league)
        print_validation(league, found)
        trades.extend(found)
    replace_trades(client, trades)
    write_report(client, current, trades)
    ping_revalidate()
    print(f"Wrote {len(trades)} trades")


if __name__ == "__main__":
    main()
