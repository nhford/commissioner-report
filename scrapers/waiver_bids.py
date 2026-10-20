"""ESPN FAAB claims for the Superlatives precision and win-rate awards.

A claim ESPN never processed is conditional. It is not a loss, and it does
not set the price of the player.
"""

from __future__ import annotations

import json

from logo_utils import owner_for


def claim_result(status: str | None) -> str | None:
    if status == "EXECUTED":
        return "added"
    if status == "FAILED_INVALIDPLAYERSOURCE":
        return "lost"
    if isinstance(status, str) and status.startswith("FAILED"):
        return "conditional"
    return None


def added_player_id(txn: dict) -> int | None:
    items = txn.get("items") or []
    for item in items:
        if str(item.get("type") or "").upper() == "ADD" and item.get("playerId") is not None:
            return int(item["playerId"])
    if items and items[0].get("playerId") is not None:
        return int(items[0]["playerId"])
    return None


def _player_name(names: dict, player_id: int) -> str | None:
    raw = names.get(player_id)
    if isinstance(raw, str) and raw:
        return raw
    name = getattr(raw, "name", None)
    if isinstance(name, str) and name:
        return name
    return None


def rows_from_transactions(
    season: int,
    transactions: list[dict],
    names: dict,
    owner_lookup,
) -> list[dict]:
    """One row per waiver claim. Cancelled and pending claims are left out."""
    rows: list[dict] = []
    seen: set[str] = set()
    for txn in transactions:
        if str(txn.get("type") or "").upper() not in {"WAIVER", "WAIVER_ERROR"}:
            continue
        if txn.get("executionType") == "CANCEL" or txn.get("status") == "PENDING":
            continue
        result = claim_result(txn.get("status"))
        txn_id = txn.get("id")
        player_id = added_player_id(txn)
        team_id = txn.get("teamId")
        week = txn.get("scoringPeriodId")
        if result is None or txn_id is None or player_id is None or team_id is None or week is None:
            continue
        key = str(txn_id)
        if key in seen:
            continue
        seen.add(key)
        bid = txn.get("bidAmount")
        rows.append(
            {
                "season": int(season),
                "id": key,
                "week": int(week),
                "team_id": int(team_id),
                "owner": owner_lookup(int(season), int(team_id)),
                "player_id": player_id,
                "player_name": _player_name(names, player_id),
                "bid": float(bid or 0),
                "result": result,
            }
        )
    return rows


def fetch_period_transactions(league, scoring_period: int) -> list[dict]:
    data = league.espn_request.league_get(
        params={"view": "mTransactions2", "scoringPeriodId": scoring_period},
        headers={
            "x-fantasy-filter": json.dumps(
                {"transactions": {"filterType": {"value": ["WAIVER", "WAIVER_ERROR"]}}}
            )
        },
    )
    return data.get("transactions") or []


def fetch_waiver_bids(league, season: int, through_week: int) -> list[dict]:
    names = getattr(league, "player_map", None) or {}
    rows: list[dict] = []
    seen: set[str] = set()
    for week in range(1, max(int(through_week), 0) + 1):
        for row in rows_from_transactions(
            season,
            fetch_period_transactions(league, week),
            names,
            owner_for,
        ):
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            rows.append(row)
    return rows


def self_test() -> None:
    assert claim_result("EXECUTED") == "added"
    assert claim_result("FAILED_INVALIDPLAYERSOURCE") == "lost"
    assert claim_result("FAILED_ROSTERLIMIT") == "conditional"
    assert claim_result("PENDING") is None

    txn = {
        "id": 99,
        "type": "WAIVER",
        "status": "FAILED_INVALIDPLAYERSOURCE",
        "executionType": "PROCESS",
        "teamId": 4,
        "bidAmount": 12,
        "scoringPeriodId": 3,
        "items": [
            {"type": "ADD", "playerId": 7},
            {"type": "DROP", "playerId": 8},
        ],
    }
    skipped = [
        {**txn, "id": 1, "status": "PENDING"},
        {**txn, "id": 2, "executionType": "CANCEL", "status": "FAILED_INVALIDPLAYERSOURCE"},
        {**txn, "id": 3, "type": "TRADE_ACCEPT", "status": "EXECUTED"},
        {**txn, "id": 4, "status": "FAILED_INVALIDDROP"},
    ]
    rows = rows_from_transactions(2024, [txn, *skipped, txn], {7: "Puka"}, lambda _year, team: "Noah" if team == 4 else None)
    assert [row["id"] for row in rows] == ["99", "4"]
    assert rows[0]["result"] == "lost"
    assert rows[0]["player_name"] == "Puka"
    assert rows[0]["owner"] == "Noah"
    assert rows[0]["week"] == 3
    assert rows[0]["bid"] == 12
    assert rows[1]["result"] == "conditional"
    print("waiver bids ok")


if __name__ == "__main__":
    self_test()
