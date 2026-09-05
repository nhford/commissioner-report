#!/usr/bin/env python3
"""Completed ESPN trades by owner. Writes to Supabase for Trade-o-gami.

Pulls every season from FIRST_SEASON through the current year. ESPN's
per-team transactionCounter.trades is the source of truth for how many
deals each owner completed. Partners come from bidirectional roster
swaps first, then leftover accepts / one-way moves, never exceeding
those official caps.
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
from revalidate import ping_revalidate
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


def team_ids_from_txn(txn: dict) -> set[int]:
    kind = (txn.get("type") or "").upper()
    team_ids: set[int] = set()
    raw_team = txn.get("teamId")
    if (
        isinstance(raw_team, int)
        and raw_team > 0
        and kind in {"TRADE_ACCEPT", "TRADE_PROPOSAL"}
    ):
        team_ids.add(raw_team)
    for item in txn.get("items") or []:
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


def infer_counterparty(
    snaps: dict[int, dict[int, int]], team_id: int, week: int
) -> int | None:
    counts: dict[int, int] = defaultdict(int)
    for later in range(max(week - 1, 0), week + 3):
        prev = snaps.get(later - 1)
        curr = snaps.get(later)
        if not prev or not curr:
            continue
        for player_id, team in curr.items():
            prev_team = prev.get(player_id)
            if not prev_team or prev_team == team:
                continue
            if team_id not in (prev_team, team):
                continue
            other = team if prev_team == team_id else prev_team
            counts[other] += 1
    if not counts:
        return None
    return max(counts, key=counts.get)


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


def collect_accept_pairs(
    league, last_week: int, snaps: dict[int, dict[int, int]]
) -> list[tuple[int, int, int, str]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    failures = 0
    for week in range(1, last_week + 1):
        try:
            rows = fetch_period_trades(league, week)
        except Exception as exc:
            failures += 1
            if failures == 1:
                print(f"  mTransactions2 week {week} failed: {exc}")
            continue
        for txn in rows:
            kind = (txn.get("type") or "").upper()
            if "TRADE" not in kind:
                continue
            group_id = txn.get("relatedTransactionId") or txn.get("id")
            if not group_id:
                continue
            groups[str(group_id)].append(
                {
                    "type": kind,
                    "week": int(txn.get("scoringPeriodId") or week),
                    "teamId": txn.get("teamId"),
                    "team_ids": team_ids_from_txn(txn),
                }
            )
    if failures > 1:
        print(f"  mTransactions2 failed for {failures} weeks")

    pairs: list[tuple[int, int, int, str]] = []
    for group_id, rows in groups.items():
        if not is_completed_group(rows):
            continue
        team_ids: set[int] = set()
        week = 0
        accept_team = None
        for row in rows:
            team_ids |= row["team_ids"]
            if row["type"] == "TRADE_ACCEPT":
                week = row["week"]
                if isinstance(row.get("teamId"), int) and row["teamId"] > 0:
                    accept_team = row["teamId"]
            elif not week:
                week = row["week"]
        if len(team_ids) < 2 and accept_team and week:
            other = infer_counterparty(snaps, accept_team, week)
            if other:
                team_ids.add(other)
        if len(team_ids) != 2:
            continue
        a, b = sorted(team_ids)
        pairs.append((week, a, b, group_id))
    return pairs


def select_to_official(
    official: dict[int, int],
    moves: dict[int, dict[tuple[int, int], list[int]]],
    accept_pairs: list[tuple[int, int, int, str]],
) -> list[dict]:
    counts: dict[int, int] = defaultdict(int)
    used: set[tuple] = set()
    selected: list[dict] = []

    def can_add(a: int, b: int) -> bool:
        return counts[a] < official.get(a, 0) and counts[b] < official.get(b, 0)

    def add(week: int, a: int, b: int, source: str, key: tuple) -> bool:
        if key in used or not can_add(a, b):
            return False
        used.add(key)
        counts[a] += 1
        counts[b] += 1
        selected.append({"week": week, "teams": (a, b), "source": source})
        return True

    for week, pairs in moves.items():
        for (a, b), (n_ab, n_ba) in pairs.items():
            if n_ab and n_ba:
                add(week, a, b, "bi", ("bi", week, a, b))

    for week, a, b, group_id in accept_pairs:
        add(week, a, b, "accept", ("acc", group_id))

    for week, pairs in moves.items():
        for (a, b), (n_ab, n_ba) in pairs.items():
            if (n_ab and not n_ba) or (n_ba and not n_ab):
                add(week, a, b, "oneway", ("ow", week, a, b))

    season_touch: dict[tuple[int, int], int] = defaultdict(int)
    for week, pairs in moves.items():
        for (a, b), (n_ab, n_ba) in pairs.items():
            season_touch[(a, b)] += n_ab + n_ba

    filling = True
    fill_i = 0
    while filling:
        filling = False
        short = [tid for tid, n in official.items() if counts[tid] < n]
        best: tuple[int, int, int] | None = None
        for i, a in enumerate(short):
            for b in short[i + 1 :]:
                lo, hi = (a, b) if a < b else (b, a)
                score = season_touch.get((lo, hi), 0)
                if best is None or score > best[0]:
                    best = (score, lo, hi)
        if best and can_add(best[1], best[2]):
            add(0, best[1], best[2], "fill", ("fill", fill_i, best[1], best[2]))
            fill_i += 1
            filling = True

    return selected


def scrape_transactions(league) -> list[dict]:
    last_week = max(int(getattr(league, "current_week", 1) or 1), 1)
    official = official_trade_counts(league)
    snaps = roster_snapshots(league, last_week)
    accept_pairs = collect_accept_pairs(league, last_week, snaps)
    selected = select_to_official(official, week_moves(snaps), accept_pairs)
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


def main() -> None:
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
