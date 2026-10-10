"""Pure Superlatives rankings. Category ids match lib/superlatives.ts."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from itertools import combinations
from pathlib import Path

PAYOUT_START = 2024
# Week-level median and payout awards start here. Team-week highs and lows do not.
FORMAT_START = 2024
TEAM_WEEK_AWARDS = {"lowest_team_week", "highest_team_week"}
TEAM_WEEK_VARIANTS = ("full_scores", "with_consolation", "full_with_consolation")


def usable_owner(name) -> str | None:
    if not name or name in {"Unknown", "N/A"}:
        return None
    return str(name)


def r2(value) -> float:
    return round(float(value or 0), 2)


def points_text(value: float) -> str:
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    return text


def money_text(amount: float) -> str:
    if abs(amount - round(amount)) < 0.001:
        return f"${amount:,.0f}"
    return f"${amount:,.2f}"


def _entry_age(item: dict) -> tuple[int, int, int, int]:
    """Start, then end. Undated rows share one key so the name still breaks those ties."""
    detail = item.get("detail") or {}
    start_season = detail.get("start_season", detail.get("season"))
    start_week = detail.get("start_week", detail.get("week"))
    if start_season is None:
        return (10**6, 10**6, 10**6, 10**6)
    end_season = detail.get("end_season", start_season)
    end_week = detail.get("end_week", start_week)
    return (
        int(start_season),
        int(start_week or 0),
        int(end_season or start_season),
        int(end_week or start_week or 0),
    )


def _rank_key(item: dict) -> tuple:
    return (-item["value"], *_entry_age(item), item["subject_name"])


def week_text(season: int, week: int) -> str:
    return f"{season} Wk {week}"


def span_text(start_season: int, start_week: int, end_season: int, end_week: int) -> str:
    if start_season == end_season:
        if start_week == end_week:
            return week_text(start_season, start_week)
        return f"{start_season} Wk {start_week}–{end_week}"
    return f"{week_text(start_season, start_week)}–{week_text(end_season, end_week)}"


def scope_bounds(scope: str) -> tuple[int, int] | None:
    """Inclusive season range. all_time is unbounded. An @owner suffix is ignored."""
    base = str(scope).split("@", 1)[0]
    if base == "all_time":
        return None
    if "-" in base:
        start, end = base.split("-", 1)
        return int(start), int(end)
    year = int(base)
    return year, year


def in_scope(season: int, scope: str) -> bool:
    bounds = scope_bounds(scope)
    if bounds is None:
        return True
    start, end = bounds
    return start <= int(season) <= end


def year_windows(current_season: int) -> list[str]:
    first = _first_season()
    windows = []
    for start in range(first, int(current_season) + 1):
        for end in range(start, int(current_season) + 1):
            windows.append(f"{start}-{end}")
    return windows


def _league_file() -> dict:
    path = Path(__file__).resolve().parent.parent / "data" / "league.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _first_season() -> int:
    years = [int(year) for year in _league_file().get("owners_by_year", {})]
    return min(years) if years else 2022


def league_owner_names() -> list[str]:
    names: set[str] = set()
    for block in _league_file().get("owners_by_year", {}).values():
        for name in block.values():
            if name and name != "N/A":
                names.add(str(name))
    return sorted(names)


# Awards sliced from the league list. Other one-owner boards are ranked again.
OWNER_AWARDS = {
    "lowest_start",
    "highest_start",
    "lowest_team_week",
    "highest_team_week",
    "payout_wins",
    "total_earnings",
    "median_streak",
    "median_misses",
    "most_trades",
    "projection_beater",
    "lineup_efficiency",
    "anti_projection_starts",
    "team_duo_trades",
}

HIDDEN_ON_OWNER = {
    "least_fantasy_teams",
    "highest_median",
    "lowest_median",
    "lowest_payout",
}


def _for_owner(category: str, items: list[dict], owner: str) -> list[dict] | None:
    """Rows for one team. None means this award stays the league-wide list."""
    if category not in OWNER_AWARDS:
        return None
    if category == "team_duo_trades":
        kept = []
        for item in items:
            detail = item.get("detail") or {}
            names = {detail.get("player_name"), detail.get("partner_name")}
            names.update(part.strip() for part in str(item.get("subject_name") or "").split("&"))
            if owner in names:
                kept.append(item)
        return kept
    if category in {"lowest_start", "highest_start"}:
        return [item for item in items if (item.get("detail") or {}).get("owner") == owner]
    return [item for item in items if item.get("subject_name") == owner]


def owner_for_team(season: int, team_id: int | None) -> str | None:
    if team_id is None:
        return None
    block = _league_file().get("owners_by_year", {}).get(str(int(season)), {})
    return usable_owner(block.get(str(int(team_id))))


def _present_for_owner(category: str, item: dict) -> dict:
    detail = item.get("detail") or {}
    if category in {"lowest_start", "highest_start"}:
        bits = [
            bit
            for bit in (
                detail.get("pos"),
                points_text(item["value"]),
                week_text(int(detail["season"]), int(detail["week"])),
            )
            if bit
        ]
        return {**item, "display": " · ".join(str(bit) for bit in bits)}
    if category in TEAM_WEEK_AWARDS:
        season = int(detail["season"])
        week = int(detail["week"])
        opponent = detail.get("opponent_owner")
        score = points_text(item["value"])
        display = f"{score} · vs {opponent}" if opponent else score
        if detail.get("consolation"):
            display = f"{display} · consolation"
        return {**item, "subject_name": week_text(season, week), "display": display}
    return item


def _store(
    rows: list[dict],
    scope: str,
    owners: list[str],
    category: str,
    items: list[dict],
    for_owner=None,
) -> None:
    rows.extend(emit(category, scope, items))
    if category in HIDDEN_ON_OWNER:
        return
    for owner in owners:
        if for_owner is not None:
            chosen = for_owner(owner)
        else:
            chosen = _for_owner(category, items, owner)
            if chosen is None:
                continue
            chosen = [_present_for_owner(category, item) for item in chosen]
        if not chosen:
            continue
        rows.extend(emit(category, f"{scope}@{owner}", chosen))


def _owned_team_weeks(category: str, items: list[dict], owner: str) -> list[dict]:
    return [
        _present_for_owner(category, item)
        for item in items
        if item.get("subject_name") == owner
    ]


def _emit_team_weeks(
    rows: list[dict],
    scope: str,
    category: str,
    items: list[dict],
    extras: dict[str, list[dict]],
) -> None:
    copied = []
    for item in items:
        copied.append({**item, "detail": dict(item.get("detail") or {})})
    if copied:
        copied[0]["detail"]["boards"] = {
            name: [_candidate(entry) for entry in (extras.get(name) or [])[:STORED]]
            for name in TEAM_WEEK_VARIANTS
        }
    rows.extend(emit(category, scope, copied))


def _store_team_weeks(
    rows: list[dict],
    scope: str,
    owners: list[str],
    category: str,
    boards: dict[str, list[dict]],
) -> None:
    extras = {name: boards.get(name) or [] for name in TEAM_WEEK_VARIANTS}
    _emit_team_weeks(rows, scope, category, boards.get("default") or [], extras)
    for owner in owners:
        owned_default = _owned_team_weeks(category, boards.get("default") or [], owner)
        if not owned_default:
            continue
        owned_extras = {
            name: _owned_team_weeks(category, boards.get(name) or [], owner)
            for name in TEAM_WEEK_VARIANTS
        }
        _emit_team_weeks(rows, f"{scope}@{owner}", category, owned_default, owned_extras)


_ABSENT = object()


def _prize_raw(places: dict | None, place: int):
    if not places:
        return _ABSENT
    if str(place) in places:
        return places[str(place)]
    if place in places:
        return places[place]
    return _ABSENT


def prize_amount(places: dict | None, place: int):
    raw = _prize_raw(places, place)
    if raw is _ABSENT or raw is None:
        return None
    if isinstance(raw, dict):
        amount = raw.get("amount")
        return None if amount is None else float(amount)
    return float(raw)


def prize_owner(places: dict | None, place: int) -> str | None:
    raw = _prize_raw(places, place)
    if isinstance(raw, dict):
        return usable_owner(raw.get("owner"))
    return None


def prizes_missing(payouts: dict, scope: str) -> bool:
    finishes = payouts.get("season_finish") or {}
    for year, places in finishes.items():
        bounds = scope_bounds(scope)
        if bounds is not None and not (bounds[0] <= int(year) <= bounds[1]):
            continue
        if not isinstance(places, dict):
            continue
        for raw in places.values():
            if raw is None or (isinstance(raw, dict) and raw.get("amount") is None):
                return True
    return False


def weekly_rate(payouts: dict, season: int) -> float:
    weekly = payouts.get("weekly") or {}
    keyed = weekly.get(str(season))
    if keyed is None:
        keyed = weekly.get(season)
    if keyed is not None:
        return float(keyed)
    if season >= PAYOUT_START:
        return float(weekly.get("default") or 75)
    return 0.0


def split_cents(rate: float, count: int) -> list[float]:
    cents = int(round(rate * 100))
    base, extra = divmod(cents, count)
    return [(base + (1 if index < extra else 0)) / 100 for index in range(count)]


def median_cutoff(scores: list[float]) -> float:
    """Score of the last team in the top half. 10 teams use 5th place; 12 use 6th."""
    ordered = sorted(scores, reverse=True)
    if not ordered:
        return 0.0
    place = max(len(ordered) // 2, 1)
    return ordered[place - 1]


def owner_logo(logos: dict, season: int, owner: str, fallback_season: int) -> str | None:
    return logos.get((season, owner)) or logos.get((fallback_season, owner))


STORED = 10
BENCH = 40


def _candidate(item: dict) -> dict:
    return {
        "subject_type": item["subject_type"],
        "subject_key": str(item["subject_key"]),
        "subject_name": item["subject_name"],
        "value": item["value"],
        "display": item["display"],
        "detail": dict(item.get("detail") or {}),
    }


def emit(
    category: str,
    scope: str,
    items: list[dict],
) -> list[dict]:
    chosen = items[: STORED + BENCH]
    rows = []
    for rank, item in enumerate(chosen[:STORED], start=1):
        detail = dict(item.get("detail") or {})
        if rank == 1:
            extras = [_candidate(extra) for extra in chosen[STORED:]]
            if extras:
                detail["alternates"] = extras
        rows.append(
            {
                "category": category,
                "scope": scope,
                "rank": rank,
                "subject_type": item["subject_type"],
                "subject_key": str(item["subject_key"]),
                "subject_name": item["subject_name"],
                "value": item["value"],
                "display": item["display"],
                "detail": detail,
            }
        )
    return rows


def _latest_player(rows: list[dict]) -> dict[int, dict]:
    latest: dict[int, dict] = {}
    for row in rows:
        pid = int(row["player_id"])
        current = latest.get(pid)
        if current is None or (int(row["season"]), int(row["week"])) >= (
            int(current["season"]),
            int(current["week"]),
        ):
            latest[pid] = row
    return latest


def season_movements(season: int, week_rows: list[dict], draft_rows: list[dict]) -> list[dict]:
    rosters: dict[int, dict[int, int]] = {}
    names: dict[int, str] = {}
    present: dict[int, set[int]] = {}
    draft: dict[int, int] = {}
    for pick in draft_rows:
        if int(pick["season"]) != season or pick.get("team_id") is None:
            continue
        pid = int(pick["player_id"])
        draft[pid] = int(pick["team_id"])
        names[pid] = pick.get("name") or str(pid)
    if draft:
        rosters[0] = draft
    by_week: dict[int, list[dict]] = {}
    for row in week_rows:
        if int(row["season"]) != season:
            continue
        by_week.setdefault(int(row["week"]), []).append(row)
    for week, rows in by_week.items():
        roster: dict[int, int] = {}
        teams: set[int] = set()
        for row in rows:
            pid = int(row["player_id"])
            tid = int(row["team_id"])
            roster[pid] = tid
            teams.add(tid)
            names[pid] = row.get("name") or names.get(pid) or str(pid)
        rosters[week] = roster
        present[week] = teams
    events = []
    for week in sorted(week for week in rosters if week != 0):
        if (week - 1) not in rosters:
            continue
        prev = rosters[week - 1]
        curr = rosters[week]
        played = present[week]
        moved: list[tuple[int, int, int]] = []
        for pid, tid in curr.items():
            old = prev.get(pid)
            if old is None:
                events.append(_move(season, pid, names, "add", [owner_for_team(season, tid)]))
            elif old != tid:
                moved.append((pid, old, tid))
        returning = {}
        for _pid, old, tid in moved:
            returning[(old, tid)] = returning.get((old, tid), 0) + 1
        for pid, old, tid in moved:
            # A drop and a later add land on different teams in the same
            # snapshot. Count that as a trade only when a player comes back
            # the other way. Seasons with an activity feed replace this.
            if returning.get((tid, old)):
                events.append(
                    _move(
                        season,
                        pid,
                        names,
                        "trade",
                        [owner_for_team(season, old), owner_for_team(season, tid)],
                    )
                )
            else:
                events.append(_move(season, pid, names, "drop", [owner_for_team(season, old)]))
                events.append(_move(season, pid, names, "add", [owner_for_team(season, tid)]))
        for pid, old_tid in prev.items():
            if pid not in curr and old_tid in played:
                events.append(_move(season, pid, names, "drop", [owner_for_team(season, old_tid)]))
    return events


def _move(season: int, pid: int, names: dict[int, str], kind: str, owners: list[str] | None = None) -> dict:
    named = []
    for owner in owners or []:
        usable = usable_owner(owner)
        if usable and usable not in named:
            named.append(usable)
    return {
        "season": season,
        "player_id": pid,
        "name": names.get(pid, str(pid)),
        "kind": kind,
        "owners": named,
    }


def activity_movements(rows: list[dict]) -> list[dict]:
    """Adds, drops, and trades from the ESPN activity feed.

    The feed names the player on a real trade, which a roster snapshot
    cannot do when the player coming back was claimed off waivers first.
    """
    events = []
    for row in rows:
        season = int(row["season"])
        traded: dict[int, dict] = {}
        for action in row.get("actions") or []:
            pid = action.get("player_id")
            if pid is None:
                continue
            pid = int(pid)
            name = action.get("player_name") or str(pid)
            kind = action.get("action")
            owner = usable_owner(action.get("owner"))
            if kind in {"TRADE_SENT", "TRADE_RECEIVED"}:
                event = traded.get(pid)
                if event is None:
                    event = {
                        "season": season,
                        "player_id": pid,
                        "name": name,
                        "kind": "trade",
                        "owners": [],
                    }
                    traded[pid] = event
                    events.append(event)
                if owner and owner not in event["owners"]:
                    event["owners"].append(owner)
                continue
            if kind in {"FA ADDED", "WAIVER ADDED"}:
                recorded = "add"
            elif kind == "DROPPED":
                recorded = "drop"
            else:
                continue
            events.append(
                {
                    "season": season,
                    "player_id": pid,
                    "name": name,
                    "kind": recorded,
                    "owners": [owner] if owner else [],
                }
            )
    return events


def _player_items(counts: dict[int, float], latest: dict[int, dict], suffix: str) -> list[dict]:
    items = []
    for pid, total in counts.items():
        if total <= 0:
            continue
        info = latest.get(pid) or {}
        name = info.get("name") or str(pid)
        shown = int(total) if float(total).is_integer() else total
        word = suffix[:-1] if shown == 1 and suffix.endswith("s") else suffix
        items.append(
            {
                "subject_type": "player",
                "subject_key": str(pid),
                "subject_name": name,
                "value": total,
                "display": f"{shown} {word}",
                "detail": {
                    "player_id": pid,
                    "player_name": name,
                    "pos": info.get("pos"),
                    "nfl_team": info.get("nfl_team"),
                },
            }
        )
    items.sort(key=_rank_key)
    return items


def most_fantasy_teams(rows: list[dict], scope: str) -> list[dict]:
    owners: dict[int, set[str]] = {}
    latest = _latest_player([row for row in rows if in_scope(int(row["season"]), scope)])
    for row in rows:
        if not in_scope(int(row["season"]), scope):
            continue
        owner = usable_owner(row.get("owner"))
        if not owner:
            continue
        owners.setdefault(int(row["player_id"]), set()).add(owner)
    counts = {pid: float(len(names)) for pid, names in owners.items()}
    items = _player_items(counts, latest, "teams")
    for item in items:
        item["display"] = f"{int(item['value'])} team" if item["value"] == 1 else f"{int(item['value'])} teams"
        item["detail"]["owners"] = sorted(owners.get(int(item["subject_key"]), []))
    return items


def _count_phrase(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def owner_roster_years(rows: list[dict], scope: str, owner: str) -> list[dict]:
    """Seasons a player spent a non-bye week on this roster. Bench weeks count."""
    byes = _bye_teams(rows, scope)
    seasons: dict[int, set[int]] = {}
    games: dict[int, dict[int, int]] = {}
    latest: dict[int, dict] = {}
    for row in rows:
        season = int(row["season"])
        if not in_scope(season, scope) or usable_owner(row.get("owner")) != owner:
            continue
        team = row.get("nfl_team")
        week = int(row["week"])
        if team and (season, week, str(team)) in byes:
            continue
        pid = int(row["player_id"])
        seasons.setdefault(pid, set()).add(season)
        games.setdefault(pid, {})
        games[pid][season] = games[pid].get(season, 0) + 1
        current = latest.get(pid)
        if current is None or (season, week) >= (int(current["season"]), int(current["week"])):
            latest[pid] = row
    items = []
    for pid, years in seasons.items():
        info = latest[pid]
        year_count = len(years)
        game_count = sum(games[pid].values())
        items.append(
            {
                "subject_type": "player",
                "subject_key": str(pid),
                "subject_name": info.get("name") or str(pid),
                "value": float(year_count),
                "display": f"{_count_phrase(year_count, 'year', 'years')} · {_count_phrase(game_count, 'game', 'games')}",
                "detail": {
                    "player_id": pid,
                    "player_name": info.get("name"),
                    "pos": info.get("pos"),
                    "nfl_team": info.get("nfl_team"),
                    "games": game_count,
                    "seasons": [
                        {"season": season, "amount": games[pid][season], "games": games[pid][season]}
                        for season in sorted(years)
                    ],
                },
            }
        )
    items.sort(key=lambda item: (-item["value"], -item["detail"]["games"], item["subject_name"]))
    return items


def _rostered_ids(player_weeks: list[dict], draft_picks: list[dict], scope: str) -> set[int]:
    rostered: set[int] = set()
    for row in player_weeks:
        if in_scope(int(row["season"]), scope):
            rostered.add(int(row["player_id"]))
    for row in draft_picks:
        if in_scope(int(row["season"]), scope):
            rostered.add(int(row["player_id"]))
    return rostered


def least_fantasy_teams(
    rows: list[dict],
    player_weeks: list[dict],
    draft_picks: list[dict],
    scope: str,
) -> list[dict]:
    """Most fantasy points from players never rostered or drafted in this window."""
    rostered = _rostered_ids(player_weeks, draft_picks, scope)
    totals: dict[int, float] = {}
    by_season: dict[int, dict[int, float]] = {}
    latest: dict[int, dict] = {}
    for row in rows:
        season = int(row["season"])
        if not in_scope(season, scope):
            continue
        pid = int(row["player_id"])
        if pid in rostered:
            continue
        points = float(row.get("points") or 0)
        if points <= 0:
            continue
        totals[pid] = totals.get(pid, 0) + points
        by_season.setdefault(pid, {})
        by_season[pid][season] = by_season[pid].get(season, 0) + points
        current = latest.get(pid)
        if current is None or season >= int(current["season"]):
            latest[pid] = row
    items = []
    for pid, total in totals.items():
        info = latest[pid]
        shown = r2(total)
        seasons = [
            {"season": season, "amount": r2(amount)}
            for season, amount in sorted(by_season[pid].items())
        ]
        items.append(
            {
                "subject_type": "player",
                "subject_key": str(pid),
                "subject_name": info["name"],
                "value": shown,
                "display": f"{points_text(shown)} pts",
                "detail": {
                    "player_id": pid,
                    "player_name": info["name"],
                    "pos": info.get("pos"),
                    "nfl_team": info.get("nfl_team"),
                    "seasons": seasons,
                },
            }
        )
    items.sort(key=_rank_key)
    return items


def started_scores(rows: list[dict], scope: str, highest: bool) -> list[dict]:
    chosen = []
    for row in rows:
        if not in_scope(int(row["season"]), scope) or not row.get("started"):
            continue
        if row.get("pos") in {"D/ST", "DST"}:
            continue
        chosen.append(row)

    def sort_key(row: dict):
        points = r2(row["points"])
        return (-points if highest else points, int(row["season"]), int(row["week"]), row["name"])

    chosen.sort(key=sort_key)
    items = []
    for row in chosen:
        pid = int(row["player_id"])
        season = int(row["season"])
        week = int(row["week"])
        points = r2(row["points"])
        pos = row.get("pos")
        owner = usable_owner(row.get("owner"))
        bits = [bit for bit in (pos, points_text(points), week_text(season, week), owner) if bit]
        items.append(
            {
                "subject_type": "player",
                "subject_key": f"{pid}:{season}:{week}",
                "subject_name": row["name"],
                "value": points,
                "display": " · ".join(bits),
                "detail": {
                    "player_id": pid,
                    "player_name": row["name"],
                    "pos": pos,
                    "nfl_team": row.get("nfl_team"),
                    "owner": owner,
                    "season": season,
                    "week": week,
                },
            }
        )
    return items


def lowest_starts(rows: list[dict], scope: str) -> list[dict]:
    return started_scores(rows, scope, False)


def highest_starts(rows: list[dict], scope: str) -> list[dict]:
    return started_scores(rows, scope, True)


def auction_totals(
    picks: list[dict],
    scope: str,
    players: dict | None = None,
    owner: str | None = None,
) -> list[dict]:
    totals: dict[int, float] = {}
    by_season: dict[int, dict[int, float]] = {}
    latest: dict[int, dict] = {}
    players = players or {}
    for pick in picks:
        season = int(pick["season"])
        if not in_scope(season, scope):
            continue
        if owner is not None and usable_owner(pick.get("owner")) != owner:
            continue
        pid = int(pick["player_id"])
        bid = float(pick.get("bid") or 0)
        totals[pid] = totals.get(pid, 0) + bid
        by_season.setdefault(pid, {})
        by_season[pid][season] = by_season[pid].get(season, 0) + bid
        latest[pid] = {
            "player_id": pid,
            "name": pick.get("name") or str(pid),
            "pos": pick.get("pos"),
            "season": season,
            "week": 0,
        }
    items = []
    for pid, total in totals.items():
        info = latest[pid]
        known = players.get(pid) or {}
        items.append(
            {
                "subject_type": "player",
                "subject_key": str(pid),
                "subject_name": info["name"],
                "value": round(total, 2),
                "display": money_text(total),
                "detail": {
                    "player_id": pid,
                    "player_name": info["name"],
                    "pos": info.get("pos") or known.get("pos"),
                    "nfl_team": known.get("nfl_team"),
                    "seasons": [
                        {"season": season, "amount": round(amount, 2)}
                        for season, amount in sorted(by_season.get(pid, {}).items())
                    ],
                },
            }
        )
    items.sort(key=_rank_key)
    return items


def movement_leaders(
    events: list[dict],
    latest: dict[int, dict],
    scope: str,
    kind: str,
    suffix: str,
    owner: str | None = None,
) -> list[dict]:
    counts: dict[int, float] = {}
    for event in events:
        if event["kind"] != kind or not in_scope(int(event["season"]), scope):
            continue
        if owner is not None and owner not in (event.get("owners") or []):
            continue
        pid = int(event["player_id"])
        counts[pid] = counts.get(pid, 0) + 1
        if pid not in latest:
            latest[pid] = {
                "player_id": pid,
                "name": event["name"],
                "pos": None,
                "season": event["season"],
                "week": 0,
            }
    return _player_items(counts, latest, suffix)


def defense_totals(player_weeks: list[dict]) -> dict[tuple[int, int, int], float]:
    totals: dict[tuple[int, int, int], float] = {}
    for row in player_weeks:
        if not row.get("started") or not _is_defense_text(row.get("name"), row.get("pos")):
            continue
        key = (int(row["season"]), int(row["week"]), int(row["team_id"]))
        totals[key] = totals.get(key, 0.0) + float(row.get("points") or 0)
    return {key: r2(value) for key, value in totals.items()}


def _team_week_points(row: dict, drop_dst: bool, defenses: dict[tuple[int, int, int], float]) -> float:
    points = r2(row["points"])
    if not drop_dst:
        return points
    key = (int(row["season"]), int(row["week"]), int(row["team_id"]))
    dst = defenses[key] if key in defenses else r2(row.get("dst_points") or 0)
    return r2(points - dst)


def _team_week_display(points: float, season: int, week: int, consolation: bool) -> str:
    label = week_text(season, week)
    if consolation:
        label = f"{label} consolation"
    return f"{points_text(points)} · {label}"


def team_week_extremes(
    rows: list[dict],
    scope: str,
    logos: dict,
    current_season: int,
    lowest: bool,
    defenses: dict[tuple[int, int, int], float] | None = None,
    drop_dst: bool = True,
    drop_consolation: bool = True,
) -> list[dict]:
    defenses = defenses or {}
    chosen = []
    for row in rows:
        if drop_consolation and row.get("is_consolation"):
            continue
        season = int(row["season"])
        if not in_scope(season, scope):
            continue
        owner = usable_owner(row.get("owner"))
        if not owner:
            continue
        chosen.append(row)
    chosen.sort(
        key=lambda row: (
            _team_week_points(row, drop_dst, defenses) if lowest else -_team_week_points(row, drop_dst, defenses),
            int(row["season"]),
            int(row["week"]),
            row.get("owner") or "",
        )
    )
    items = []
    for row in chosen:
        owner = usable_owner(row.get("owner"))
        season = int(row["season"])
        week = int(row["week"])
        points = _team_week_points(row, drop_dst, defenses)
        consolation = bool(row.get("is_consolation"))
        detail = {
            "season": season,
            "week": week,
            "team_name": row.get("team_name"),
            "logo_path": owner_logo(logos, season, owner, current_season),
            "opponent_owner": usable_owner(row.get("opponent_owner")),
        }
        if consolation:
            detail["consolation"] = True
        items.append(
            {
                "subject_type": "team",
                "subject_key": f"{owner}:{season}:{week}",
                "subject_name": owner,
                "value": points,
                "display": _team_week_display(points, season, week, consolation),
                "detail": detail,
            }
        )
    return items


def weekly_winners(rows: list[dict], scope: str) -> list[tuple[tuple[int, int], list[dict]]]:
    groups: dict[tuple[int, int], list[dict]] = {}
    for row in rows:
        season = int(row["season"])
        if (
            row.get("is_consolation")
            or not row.get("is_regular")
            or season < PAYOUT_START
            or not in_scope(season, scope)
        ):
            continue
        groups.setdefault((season, int(row["week"])), []).append(row)
    ordered = []
    for key in sorted(groups):
        week_rows = groups[key]
        best = max(r2(row["points"]) for row in week_rows)
        winners = [row for row in week_rows if r2(row["points"]) == best]
        winners.sort(key=lambda row: int(row["team_id"]))
        ordered.append((key, winners))
    return ordered


def payout_wins(rows: list[dict], scope: str, logos: dict, current_season: int) -> list[dict]:
    totals: dict[str, int] = {}
    for _key, winners in weekly_winners(rows, scope):
        for row in winners:
            owner = usable_owner(row.get("owner"))
            if owner:
                totals[owner] = totals.get(owner, 0) + 1
    items = []
    for owner, total in totals.items():
        noun = "week" if total == 1 else "weeks"
        items.append(
            {
                "subject_type": "team",
                "subject_key": owner,
                "subject_name": owner,
                "value": total,
                "display": f"{total} {noun}",
                "detail": {"logo_path": owner_logo(logos, current_season, owner, current_season)},
            }
        )
    items.sort(key=_rank_key)
    return items


def total_earnings(
    rows: list[dict],
    payouts: dict,
    finishers: dict,
    scope: str,
    logos: dict,
    current_season: int,
) -> list[dict]:
    totals: dict[str, float] = {}
    lines: dict[str, list[dict]] = {}
    payments: dict[str, list[dict]] = {}
    final_week: dict[int, int] = {}
    for row in rows:
        season = int(row["season"])
        if row.get("is_consolation") or not in_scope(season, scope):
            continue
        week = int(row["week"])
        if week > final_week.get(season, 0):
            final_week[season] = week
    finishes = payouts.get("season_finish") or {}
    for year in sorted(finishes, key=lambda value: int(value)):
        places = finishes[year]
        season = int(year)
        if not in_scope(season, scope):
            continue
        placed = finishers.get(season) or finishers.get(year) or {}
        for place in (1, 2):
            amount = prize_amount(places, place)
            owner = prize_owner(places, place) or usable_owner(
                placed.get(place) or placed.get(str(place))
            )
            if amount is None or not owner:
                continue
            totals[owner] = totals.get(owner, 0) + float(amount)
            label = f"{season} champion" if place == 1 else f"{season} runner-up"
            paid = round(float(amount), 2)
            lines.setdefault(owner, []).append({"label": label, "amount": paid})
            payments.setdefault(owner, []).append(
                {
                    "label": label,
                    "amount": paid,
                    "season": season,
                    "week": final_week.get(season, 17),
                }
            )
    weekly_totals: dict[str, float] = {}
    for (season, week), winners in weekly_winners(rows, scope):
        rate = weekly_rate(payouts, season)
        if rate <= 0 or not winners:
            continue
        shares = split_cents(rate, len(winners))
        for row, share in zip(winners, shares):
            owner = usable_owner(row.get("owner"))
            if not owner:
                continue
            paid = round(share, 2)
            totals[owner] = totals.get(owner, 0) + share
            weekly_totals[owner] = weekly_totals.get(owner, 0) + share
            payments.setdefault(owner, []).append(
                {
                    "label": "Weekly pay",
                    "amount": paid,
                    "season": season,
                    "week": int(week),
                }
            )
    for owner, weekly in weekly_totals.items():
        lines.setdefault(owner, []).append({"label": "Weekly pay", "amount": round(weekly, 2)})
    missing = prizes_missing(payouts, scope)
    items = []
    for owner, total in totals.items():
        items.append(
            {
                "subject_type": "team",
                "subject_key": owner,
                "subject_name": owner,
                "value": round(total, 2),
                "display": money_text(total),
                "detail": {
                    "logo_path": owner_logo(logos, current_season, owner, current_season),
                    "prizes_missing": missing,
                    "lines": lines.get(owner, []),
                    "payments": payments.get(owner, []),
                },
            }
        )
    items.sort(key=_rank_key)
    return items


def _regular_by_owner(rows: list[dict], scope: str) -> tuple[dict[str, list[dict]], dict[tuple[int, int], float]]:
    buckets: dict[tuple[int, int], list[dict]] = {}
    for row in rows:
        if not row.get("is_regular") or not in_scope(int(row["season"]), scope):
            continue
        if not usable_owner(row.get("owner")):
            continue
        buckets.setdefault((int(row["season"]), int(row["week"])), []).append(row)
    cutoffs = {
        key: median_cutoff([r2(row["points"]) for row in week_rows])
        for key, week_rows in buckets.items()
    }
    by_owner: dict[str, list[dict]] = {}
    for week_rows in buckets.values():
        for row in week_rows:
            owner = usable_owner(row.get("owner"))
            by_owner.setdefault(owner, []).append(row)
    for owner, owned in by_owner.items():
        owned.sort(key=lambda row: (int(row["season"]), int(row["week"])))
        by_owner[owner] = owned
    return by_owner, cutoffs


def _streak_hits(weeks: list[dict]) -> int:
    return sum(1 for week in weeks if not week.get("bye"))


def _bye_teams(rows: list[dict], scope: str) -> set[tuple[int, int, str]]:
    """NFL teams with no scorer in a week where several teams are dark.

    A real bye clears the whole roster. One idle player in a week other teams
    played is not a bye.
    """
    groups: dict[tuple[int, int, str], list[dict]] = {}
    for row in rows:
        if not in_scope(int(row["season"]), scope):
            continue
        team = row.get("nfl_team")
        if not team:
            continue
        groups.setdefault((int(row["season"]), int(row["week"]), str(team)), []).append(row)
    dark = [
        key
        for key, group in groups.items()
        if all(float(row.get("points") or 0) == 0 and float(row.get("projected_points") or 0) <= 0 for row in group)
    ]
    slate: dict[tuple[int, int], int] = {}
    for season, week, _team in dark:
        slate[(season, week)] = slate.get((season, week), 0) + 1
    return {key for key in dark if slate[(key[0], key[1])] >= 3}


def projection_streaks(rows: list[dict], scope: str, over: bool, owner: str | None = None) -> list[dict]:
    """Longest run of rostered weeks strictly over or under that week's projection.

    A bye is skipped. A tie, any other week without a projection, or a week
    missing from the roster ends the run.
    """
    byes = _bye_teams(rows, scope)
    calendar = sorted(
        {
            (int(row["season"]), int(row["week"]))
            for row in rows
            if in_scope(int(row["season"]), scope)
        }
    )
    order = {week: index for index, week in enumerate(calendar)}
    by_player: dict[int, list[dict]] = {}
    for row in rows:
        if not in_scope(int(row["season"]), scope):
            continue
        if owner is not None and usable_owner(row.get("owner")) != owner:
            continue
        by_player.setdefault(int(row["player_id"]), []).append(row)
    items = []
    for pid, owned in by_player.items():
        owned.sort(key=lambda row: (int(row["season"]), int(row["week"])))
        best: list[dict] = []
        current: list[dict] = []
        pending: list[dict] = []
        previous = None
        for row in owned:
            key = (int(row["season"]), int(row["week"]))
            if previous is not None and order[key] != previous + 1:
                current = []
                pending = []
            previous = order[key]
            team = row.get("nfl_team")
            if team and (key[0], key[1], str(team)) in byes:
                if current:
                    pending.append({"season": key[0], "week": key[1], "bye": True})
                continue
            projected = row.get("projected_points")
            if projected is None or float(projected) <= 0:
                current = []
                pending = []
                continue
            points = r2(row["points"])
            projected = r2(projected)
            hit = points > projected if over else points < projected
            if not hit:
                current = []
                pending = []
                continue
            current.extend(pending)
            pending = []
            current.append(
                {
                    "season": key[0],
                    "week": key[1],
                    "points": points,
                    "projected": projected,
                }
            )
            if _streak_hits(current) >= _streak_hits(best):
                best = list(current)
        if not best:
            continue
        counted = [week for week in best if not week.get("bye")]
        start, end = counted[0], counted[-1]
        active = bool(current) and [(week["season"], week["week"]) for week in current] == [
            (week["season"], week["week"]) for week in best
        ]
        label = span_text(start["season"], start["week"], end["season"], end["week"])
        noun = "week" if len(counted) == 1 else "weeks"
        display = f"{len(counted)} {noun} · {label}"
        if active:
            display += " · active"
        info = owned[-1]
        items.append(
            {
                "subject_type": "player",
                "subject_key": str(pid),
                "subject_name": info["name"],
                "value": float(len(counted)),
                "display": display,
                "detail": {
                    "player_id": pid,
                    "player_name": info["name"],
                    "pos": info.get("pos"),
                    "nfl_team": info.get("nfl_team"),
                    "start_season": start["season"],
                    "start_week": start["week"],
                    "end_season": end["season"],
                    "end_week": end["week"],
                    "active": active,
                    "weeks": best,
                },
            }
        )
    items.sort(key=_rank_key)
    return items


def streaks(rows: list[dict], scope: str, logos: dict, current_season: int, above: bool) -> list[dict]:
    by_owner, cutoffs = _regular_by_owner(rows, scope)
    items = []
    for owner, owned in by_owner.items():
        best_len = 0
        best_span = None
        current = 0
        start = None
        for row in owned:
            key = (int(row["season"]), int(row["week"]))
            hit = r2(row["points"]) >= cutoffs[key]
            if not above:
                hit = not hit
            if hit:
                if current == 0:
                    start = row
                current += 1
                if current > best_len:
                    best_len = current
                    best_span = (start, row)
            else:
                current = 0
        if not best_len or best_span is None:
            continue
        start_row, end_row = best_span
        latest = owned[-1]
        active = int(end_row["season"]) == int(latest["season"]) and int(end_row["week"]) == int(
            latest["week"]
        )
        label = span_text(
            int(start_row["season"]),
            int(start_row["week"]),
            int(end_row["season"]),
            int(end_row["week"]),
        )
        noun = "week" if best_len == 1 else "weeks"
        display = f"{best_len} {noun} · {label}"
        if active:
            display += " · active"
        items.append(
            {
                "subject_type": "team",
                "subject_key": owner,
                "subject_name": owner,
                "value": best_len,
                "display": display,
                "detail": {
                    "logo_path": owner_logo(logos, current_season, owner, current_season),
                    "start_season": int(start_row["season"]),
                    "start_week": int(start_row["week"]),
                    "end_season": int(end_row["season"]),
                    "end_week": int(end_row["week"]),
                    "active": active,
                },
            }
        )
    items.sort(key=_rank_key)
    return items


def trade_counts(trades: list[dict], scope: str) -> tuple[dict[tuple[str, str], int], dict[str, int]]:
    pairs: dict[tuple[str, str], int] = {}
    owners: dict[str, int] = {}
    for trade in trades:
        if not in_scope(int(trade["season"]), scope):
            continue
        involved: list[str] = []
        for name in trade.get("owners") or []:
            owner = usable_owner(name)
            if owner and owner not in involved:
                involved.append(owner)
        for owner in involved:
            owners[owner] = owners.get(owner, 0) + 1
        for left, right in combinations(involved, 2):
            key = tuple(sorted((left, right)))
            pairs[key] = pairs.get(key, 0) + 1
    return pairs, owners


def team_duo_trades(trades: list[dict], scope: str, logos: dict, current_season: int) -> list[dict]:
    pairs, _owners = trade_counts(trades, scope)
    items = []
    for (left, right), count in pairs.items():
        items.append(
            {
                "subject_type": "duo",
                "subject_key": f"{left}|{right}",
                "subject_name": f"{left} & {right}",
                "value": count,
                "display": f"{count} trade" if count == 1 else f"{count} trades",
                "detail": {
                    "player_name": left,
                    "partner_name": right,
                    "logo_path": owner_logo(logos, current_season, left, current_season),
                    "partner_logo_path": owner_logo(logos, current_season, right, current_season),
                },
            }
        )
    items.sort(key=_rank_key)
    return items


def most_trades(trades: list[dict], scope: str, logos: dict, current_season: int) -> list[dict]:
    _pairs, owners = trade_counts(trades, scope)
    items = []
    for owner, count in owners.items():
        items.append(
            {
                "subject_type": "team",
                "subject_key": owner,
                "subject_name": owner,
                "value": count,
                "display": f"{count} trade" if count == 1 else f"{count} trades",
                "detail": {"logo_path": owner_logo(logos, current_season, owner, current_season)},
            }
        )
    items.sort(key=_rank_key)
    return items


def rate_award(
    rows: list[dict],
    scope: str,
    logos: dict,
    current_season: int,
    numerator: str,
    denominator: str,
    require_projections: bool,
) -> list[dict]:
    sums: dict[str, list[float]] = {}
    for row in rows:
        if row.get("is_consolation") or not in_scope(int(row["season"]), scope):
            continue
        owner = usable_owner(row.get("owner"))
        if not owner:
            continue
        if require_projections and not row.get("projections_ok"):
            continue
        denom = row.get(denominator)
        if denom is None:
            continue
        bucket = sums.setdefault(owner, [0.0, 0.0])
        bucket[0] += float(row.get(numerator) or 0)
        bucket[1] += float(denom)
    items = []
    for owner, (num, den) in sums.items():
        if den <= 0:
            continue
        pct = round(100 * num / den, 1)
        items.append(
            {
                "subject_type": "team",
                "subject_key": owner,
                "subject_name": owner,
                "value": pct,
                "display": f"{pct:.1f}%",
                "detail": {"logo_path": owner_logo(logos, current_season, owner, current_season)},
            }
        )
    items.sort(key=_rank_key)
    return items


def anti_projection(rows: list[dict], scope: str, logos: dict, current_season: int) -> list[dict]:
    totals: dict[str, int] = {}
    for row in rows:
        if row.get("is_consolation") or not in_scope(int(row["season"]), scope) or not row.get("projections_ok"):
            continue
        owner = usable_owner(row.get("owner"))
        count = row.get("anti_projection_starts")
        if not owner or count is None:
            continue
        totals[owner] = totals.get(owner, 0) + int(count)
    items = []
    for owner, total in totals.items():
        noun = "start" if total == 1 else "starts"
        items.append(
            {
                "subject_type": "team",
                "subject_key": owner,
                "subject_name": owner,
                "value": total,
                "display": f"{total} {noun}",
                "detail": {"logo_path": owner_logo(logos, current_season, owner, current_season)},
            }
        )
    items.sort(key=_rank_key)
    return items


def player_duos(rows: list[dict], scope: str, owner: str | None = None) -> list[dict]:
    groups: dict[tuple, dict[int, dict]] = {}
    for row in rows:
        if not in_scope(int(row["season"]), scope) or not row.get("started"):
            continue
        if owner is not None and usable_owner(row.get("owner")) != owner:
            continue
        key = (int(row["season"]), int(row["week"]), int(row["team_id"]))
        groups.setdefault(key, {})[int(row["player_id"])] = row
    counts: dict[tuple[int, int], int] = {}
    sample: dict[tuple[int, int], tuple[dict, dict]] = {}
    for roster in groups.values():
        ids = sorted(roster)
        for left, right in combinations(ids, 2):
            pair = (left, right)
            counts[pair] = counts.get(pair, 0) + 1
            sample[pair] = (roster[left], roster[right])
    items = []
    for pair, count in counts.items():
        left, right = sample[pair]
        names = sorted((left["name"], right["name"]))
        first, second = (left, right) if left["name"] == names[0] else (right, left)
        items.append(
            {
                "subject_type": "duo",
                "subject_key": f"{pair[0]}|{pair[1]}",
                "subject_name": f"{names[0]} & {names[1]}",
                "value": count,
                "display": f"{count} week" if count == 1 else f"{count} weeks",
                "detail": {
                    "player_id": int(first["player_id"]),
                    "player_name": first["name"],
                    "pos": first.get("pos"),
                    "nfl_team": first.get("nfl_team"),
                    "partner_id": int(second["player_id"]),
                    "partner_name": second["name"],
                    "partner_pos": second.get("pos"),
                    "partner_nfl_team": second.get("nfl_team"),
                },
            }
        )
    items.sort(key=_rank_key)
    return items


def nfl_starter_weeks(rows: list[dict], scope: str, owner: str | None = None) -> list[dict]:
    groups: dict[tuple[str, int, int], list[dict]] = {}
    for row in rows:
        team = row.get("nfl_team")
        if not team or team == "None" or not row.get("started"):
            continue
        if not in_scope(int(row["season"]), scope):
            continue
        if owner is not None and usable_owner(row.get("owner")) != owner:
            continue
        key = (str(team), int(row["season"]), int(row["week"]))
        groups.setdefault(key, []).append(row)
    items = []
    for (team, season, week), starters in groups.items():
        listed = sorted(starters, key=lambda row: (-r2(row["points"]), row.get("name") or ""))
        count = len(listed)
        noun = "starter" if count == 1 else "starters"
        items.append(
            {
                "subject_type": "nfl",
                "subject_key": f"{team}:{season}:{week}",
                "subject_name": team,
                "value": count,
                "display": f"{count} {noun} · {week_text(season, week)}",
                "detail": {
                    "nfl_team": team,
                    "season": season,
                    "week": week,
                    "starters": [
                        {
                            "name": row.get("name"),
                            "pos": row.get("pos"),
                            "owner": usable_owner(row.get("owner")),
                            "points": r2(row["points"]),
                        }
                        for row in listed
                    ],
                },
            }
        )
    items.sort(key=_rank_key)
    return items


def _week_item(season: int, week: int, score: float, names: list[str], detail: dict) -> dict:
    label = " & ".join(names) if names else "—"
    return {
        "subject_type": "week",
        "subject_key": f"{season}:{week}",
        "subject_name": week_text(season, week),
        "value": score,
        "display": f"{points_text(score)} · {label}",
        "detail": detail,
    }


def median_weeks(rows: list[dict], scope: str, logos: dict, current_season: int, highest: bool) -> list[dict]:
    buckets: dict[tuple[int, int], list[dict]] = {}
    for row in rows:
        season = int(row["season"])
        if not row.get("is_regular") or season < FORMAT_START or not in_scope(season, scope):
            continue
        if not usable_owner(row.get("owner")):
            continue
        buckets.setdefault((season, int(row["week"])), []).append(row)
    items = []
    for (season, week), week_rows in buckets.items():
        cut = median_cutoff([r2(row["points"]) for row in week_rows])
        on_line = [row for row in week_rows if r2(row["points"]) == cut]
        on_line.sort(key=lambda row: int(row["team_id"]))
        names: list[str] = []
        for row in on_line:
            owner = usable_owner(row.get("owner"))
            if owner and owner not in names:
                names.append(owner)
        logo = owner_logo(logos, season, names[0], current_season) if len(names) == 1 else None
        items.append(
            _week_item(
                season,
                week,
                cut,
                names,
                {"season": season, "week": week, "logo_path": logo, "owners": names},
            )
        )
    if highest:
        items.sort(key=lambda item: (-item["value"], item["detail"]["season"], item["detail"]["week"]))
    else:
        items.sort(key=lambda item: (item["value"], item["detail"]["season"], item["detail"]["week"]))
    return items


def lowest_payout_weeks(rows: list[dict], scope: str, logos: dict, current_season: int) -> list[dict]:
    items = []
    for (season, week), winners in weekly_winners(rows, scope):
        score = r2(winners[0]["points"])
        packed = []
        names: list[str] = []
        for row in winners:
            owner = usable_owner(row.get("owner"))
            if not owner or owner in names:
                continue
            names.append(owner)
            packed.append(
                {
                    "owner": owner,
                    "logo_path": owner_logo(logos, season, owner, current_season),
                }
            )
        logo = packed[0]["logo_path"] if len(packed) == 1 else None
        items.append(
            _week_item(
                season,
                week,
                score,
                names,
                {"season": season, "week": week, "logo_path": logo, "winners": packed},
            )
        )
    items.sort(key=lambda item: (item["value"], item["detail"]["season"], item["detail"]["week"]))
    return items


def build_superlatives(
    player_weeks: list[dict],
    team_weeks: list[dict],
    draft_picks: list[dict],
    trades: list[dict],
    payouts: dict,
    finishers: dict,
    logos: dict,
    current_season: int,
    activity: list[dict] | None = None,
    free_agents: list[dict] | None = None,
    with_owners: bool = True,
) -> list[dict]:
    seasons = {int(row["season"]) for row in player_weeks}
    seasons.update(int(row["season"]) for row in draft_picks)
    activity_by_season: dict[int, list[dict]] = {}
    for row in activity or []:
        activity_by_season.setdefault(int(row["season"]), []).append(row)
    events: list[dict] = []
    for season in sorted(seasons):
        recorded = activity_by_season.get(season)
        if recorded:
            events.extend(activity_movements(recorded))
        else:
            events.extend(season_movements(season, player_weeks, draft_picks))
    latest = _latest_player(player_weeks)
    owners = league_owner_names() if with_owners else []
    defenses = defense_totals(player_weeks)
    rows: list[dict] = []
    for scope in year_windows(current_season):
        _store(
            rows,
            scope,
            owners,
            "most_fantasy_teams",
            most_fantasy_teams(player_weeks, scope),
            lambda owner, window=scope: owner_roster_years(player_weeks, window, owner),
        )
        _store(
            rows,
            scope,
            owners,
            "least_fantasy_teams",
            least_fantasy_teams(free_agents or [], player_weeks, draft_picks, scope),
        )
        _store(rows, scope, owners, "lowest_start", lowest_starts(player_weeks, scope))
        _store(rows, scope, owners, "highest_start", highest_starts(player_weeks, scope))
        _store(
            rows,
            scope,
            owners,
            "most_auction_dollars",
            auction_totals(draft_picks, scope, latest),
            lambda owner, window=scope: auction_totals(draft_picks, window, latest, owner),
        )
        _store(
            rows,
            scope,
            owners,
            "most_added",
            movement_leaders(events, latest, scope, "add", "adds"),
            lambda owner, window=scope: movement_leaders(events, latest, window, "add", "adds", owner),
        )
        _store(
            rows,
            scope,
            owners,
            "most_dropped",
            movement_leaders(events, latest, scope, "drop", "drops"),
            lambda owner, window=scope: movement_leaders(events, latest, window, "drop", "drops", owner),
        )
        _store(
            rows,
            scope,
            owners,
            "most_traded_player",
            movement_leaders(events, latest, scope, "trade", "trades"),
            lambda owner, window=scope: movement_leaders(events, latest, window, "trade", "trades", owner),
        )
        for category, lowest in (("lowest_team_week", True), ("highest_team_week", False)):
            _store_team_weeks(
                rows,
                scope,
                owners,
                category,
                {
                    "default": team_week_extremes(
                        team_weeks, scope, logos, current_season, lowest, defenses, True, True
                    ),
                    "full_scores": team_week_extremes(
                        team_weeks, scope, logos, current_season, lowest, defenses, False, True
                    ),
                    "with_consolation": team_week_extremes(
                        team_weeks, scope, logos, current_season, lowest, defenses, True, False
                    ),
                    "full_with_consolation": team_week_extremes(
                        team_weeks, scope, logos, current_season, lowest, defenses, False, False
                    ),
                },
            )
        _store(rows, scope, owners, "highest_median", median_weeks(team_weeks, scope, logos, current_season, True))
        _store(rows, scope, owners, "lowest_median", median_weeks(team_weeks, scope, logos, current_season, False))
        _store(
            rows,
            scope,
            owners,
            "player_duo_starts",
            player_duos(player_weeks, scope),
            lambda owner, window=scope: player_duos(player_weeks, window, owner),
        )
        _store(
            rows,
            scope,
            owners,
            "projection_over_streak",
            projection_streaks(player_weeks, scope, True),
            lambda owner, window=scope: projection_streaks(player_weeks, window, True, owner),
        )
        _store(
            rows,
            scope,
            owners,
            "projection_under_streak",
            projection_streaks(player_weeks, scope, False),
            lambda owner, window=scope: projection_streaks(player_weeks, window, False, owner),
        )
        _store(rows, scope, owners, "payout_wins", payout_wins(team_weeks, scope, logos, current_season))
        _store(rows, scope, owners, "lowest_payout", lowest_payout_weeks(team_weeks, scope, logos, current_season))
        _store(
            rows,
            scope,
            owners,
            "total_earnings",
            total_earnings(team_weeks, payouts, finishers, scope, logos, current_season),
        )
        _store(rows, scope, owners, "median_streak", streaks(team_weeks, scope, logos, current_season, True))
        _store(rows, scope, owners, "median_misses", streaks(team_weeks, scope, logos, current_season, False))
        _store(rows, scope, owners, "team_duo_trades", team_duo_trades(trades, scope, logos, current_season))
        _store(rows, scope, owners, "most_trades", most_trades(trades, scope, logos, current_season))
        _store(
            rows,
            scope,
            owners,
            "projection_beater",
            rate_award(
                team_weeks,
                scope,
                logos,
                current_season,
                "starter_points",
                "projection_lineup_points",
                True,
            ),
        )
        _store(
            rows,
            scope,
            owners,
            "lineup_efficiency",
            rate_award(
                team_weeks,
                scope,
                logos,
                current_season,
                "starter_points",
                "optimal_points",
                False,
            ),
        )
        _store(
            rows,
            scope,
            owners,
            "anti_projection_starts",
            anti_projection(team_weeks, scope, logos, current_season),
        )
        _store(
            rows,
            scope,
            owners,
            "nfl_starter_week",
            nfl_starter_weeks(player_weeks, scope),
            lambda owner, window=scope: nfl_starter_weeks(player_weeks, window, owner),
        )
    return rows


# Thursday of NFL week 1. Activity before that Thursday still belongs to week 1.
_WEEK1_THURSDAY = {
    2022: date(2022, 9, 8),
    2023: date(2023, 9, 7),
    2024: date(2024, 9, 5),
    2025: date(2025, 9, 4),
    2026: date(2026, 9, 10),
}
_DEFENSE_NAME = re.compile(r"\bD/ST\b")


def activity_scoring_week(occurred_at: str, season: int) -> int:
    text = occurred_at.replace("Z", "+00:00")
    moment = datetime.fromisoformat(text)
    start = _WEEK1_THURSDAY.get(int(season))
    if start is None:
        return 1
    day = moment.date()
    if day < start:
        return 1
    return (day - start).days // 7 + 1


def _is_defense_text(name, pos=None) -> bool:
    if pos in {"D/ST", "DST"}:
        return True
    return bool(name and _DEFENSE_NAME.search(str(name)))


def _is_defense_row(row: dict) -> bool:
    detail = row.get("detail") or {}
    if _is_defense_text(detail.get("player_name"), detail.get("pos")):
        return True
    if _is_defense_text(detail.get("partner_name"), detail.get("partner_pos")):
        return True
    return _is_defense_text(row.get("subject_name"))


def _expanded_board(rows: list[dict]) -> list[dict]:
    ranked = sorted(rows, key=lambda row: int(row["rank"]))
    if not ranked:
        return []
    extras = []
    alternates = (ranked[0].get("detail") or {}).get("alternates") or []
    for index, alt in enumerate(alternates, start=len(ranked) + 1):
        extras.append(
            {
                "rank": index,
                "subject_key": str(alt["subject_key"]),
                "subject_name": alt.get("subject_name") or "",
                "value": alt.get("value"),
                "detail": alt.get("detail") or {},
            }
        )
    return ranked + extras


def _variant_board(items: list[dict]) -> list[tuple]:
    return [
        (
            str(item.get("subject_key")),
            r2(item.get("value")),
            item.get("subject_name") or "",
            item.get("display") or "",
        )
        for item in items[:10]
    ]


def visible_board(rows: list[dict], hide_defense: bool, limit: int = 10) -> list[tuple]:
    """Top 10 as the page shows it, including the Hide D/ST recount."""
    if not rows:
        return []
    category = rows[0]["category"]
    pool = _expanded_board(rows) if hide_defense else sorted(rows, key=lambda row: int(row["rank"]))
    if hide_defense and category == "nfl_starter_week":
        adjusted = []
        for row in pool:
            starters = (row.get("detail") or {}).get("starters") or []
            count = sum(1 for starter in starters if not _is_defense_text(starter.get("name"), starter.get("pos")))
            if count <= 0:
                continue
            detail = row.get("detail") or {}
            adjusted.append(
                (
                    str(row["subject_key"]),
                    float(count),
                    row.get("subject_name") or "",
                    int(detail.get("season") or 0),
                    int(detail.get("week") or 0),
                )
            )
        adjusted.sort(key=lambda item: (-item[1], item[3], item[4], item[2]))
        return [
            (key, value, name, f"{int(value)} starters")
            for key, value, name, *_rest in adjusted[:limit]
        ]
    if hide_defense:
        pool = [row for row in pool if not _is_defense_row(row)]
    else:
        pool = pool[:limit]
    if hide_defense:
        pool = pool[:limit]
    return [
        (str(row["subject_key"]), r2(row["value"]), row.get("subject_name") or "", row.get("display") or "")
        for row in pool
    ]


def board_changes(
    previous: list[tuple],
    current: list[tuple],
    include_entrants: bool = True,
) -> set[str]:
    """Entries whose result changed, or that were not in the top 10 yet.

    A rank slide on an unchanged result is not included. The card still sorts
    by the week the ordered top 10 last moved.
    """
    prev_value = {item[0]: item[1] for item in previous}
    changed = set()
    for item in current:
        key, value = item[0], item[1]
        if key not in prev_value:
            if include_entrants:
                changed.add(key)
        elif prev_value[key] != value:
            changed.add(key)
    return changed


def _pool_values(rows: list[dict]) -> dict[str, float]:
    """Scores for the stored top 10 and the bench behind it."""
    return {str(row["subject_key"]): r2(row["value"]) for row in _expanded_board(rows)}


RATE_AWARDS = {"lineup_efficiency", "projection_beater"}


def _previous_rate(subject_key: str, prior: list[tuple], earlier: dict[str, float]) -> float | None:
    for item in prior:
        if item[0] == subject_key:
            return item[1]
    if subject_key in earlier:
        return earlier[subject_key]
    return None


def rising_entrants(previous: list[tuple], current: list[tuple], earlier: dict[str, float]) -> set[str]:
    """New top-10 names whose own score increased.

    A name that slides in at the same score, because someone else left, is not
    included. Least fantasy teams uses this instead of bolding every entrant.
    """
    already = {item[0] for item in previous}
    risen = set()
    for item in current:
        key, value = item[0], item[1]
        if key in already:
            continue
        old = earlier.get(key)
        if old is None or value > old:
            risen.add(key)
    return risen


def _departed(previous: list[tuple], current: list[tuple]) -> list[dict]:
    current_keys = {item[0] for item in current}
    left = []
    for index, item in enumerate(previous):
        if item[0] in current_keys:
            continue
        left.append(
            {
                "rank": index + 1,
                "subject_key": item[0],
                "subject_name": item[2] if len(item) > 2 else item[0],
                "value": item[1],
                "display": item[3] if len(item) > 3 else "",
            }
        )
    return left


def stamp_recency(final_rows: list[dict], snapshots: list[tuple[int, int, list[dict]]]) -> None:
    """Mark when each visible top-10 entry last moved, and the week the board runs through."""
    last: dict[tuple, tuple[int, int]] = {}
    board_last: dict[tuple, tuple[int, int]] = {}
    departed: dict[tuple, list[dict]] = {}
    previous: dict[tuple, list[tuple]] = {}
    earlier_scores: dict[tuple[str, str], dict[str, float]] = {}
    rate_from: dict[tuple, float] = {}
    as_of = (0, 0)
    for season, week, built in snapshots:
        as_of = (int(season), int(week))
        grouped: dict[tuple[str, str], list[dict]] = {}
        for row in built:
            grouped.setdefault((row["category"], row["scope"]), []).append(row)
        for key, group in grouped.items():
            earlier = earlier_scores.get(key, {})
            for hide in (False, True):
                board = visible_board(group, hide)
                slot = (*key, hide)
                prior = previous.get(slot, [])
                if board != prior:
                    board_last[slot] = as_of
                entrants = key[0] != "least_fantasy_teams"
                changed = board_changes(prior, board, entrants)
                if prior and key[0] == "least_fantasy_teams":
                    changed.update(rising_entrants(prior, board, earlier))
                for subject_key in changed:
                    last[(*slot, subject_key)] = as_of
                    if key[0] in RATE_AWARDS:
                        old = _previous_rate(subject_key, prior, earlier)
                        if old is not None:
                            rate_from[(*slot, subject_key)] = old
                if key[0] == "least_fantasy_teams":
                    departed[slot] = _departed(prior, board)
                previous[slot] = board
            if key[0] in TEAM_WEEK_AWARDS:
                leader = next((row for row in group if int(row["rank"]) == 1), None)
                nested = ((leader or {}).get("detail") or {}).get("boards") or {}
                for name in TEAM_WEEK_VARIANTS:
                    board = _variant_board(nested.get(name) or [])
                    slot = (*key, name)
                    prior = previous.get(slot, [])
                    if board != prior:
                        board_last[slot] = as_of
                    changed = board_changes(prior, board)
                    for subject_key in changed:
                        last[(*slot, subject_key)] = as_of
                    previous[slot] = board
            earlier_scores[key] = _pool_values(group)

    def write(detail: dict, category: str, scope: str, subject_key: str) -> None:
        plain = last.get((category, scope, False, str(subject_key)))
        hidden = last.get((category, scope, True, str(subject_key)))
        plain_board = board_last.get((category, scope, False))
        hidden_board = board_last.get((category, scope, True))
        if plain:
            detail["changed_season"], detail["changed_week"] = plain
        if hidden:
            detail["hide_changed_season"], detail["hide_changed_week"] = hidden
        if plain_board:
            detail["board_season"], detail["board_week"] = plain_board
        if hidden_board:
            detail["hide_board_season"], detail["hide_board_week"] = hidden_board
        if category == "least_fantasy_teams":
            detail["departed"] = departed.get((category, scope, False), [])
            detail["hide_departed"] = departed.get((category, scope, True), [])
        if category in RATE_AWARDS:
            plain_from = rate_from.get((category, scope, False, str(subject_key)))
            hidden_from = rate_from.get((category, scope, True, str(subject_key)))
            if plain_from is not None:
                detail["changed_from"] = plain_from
            if hidden_from is not None:
                detail["hide_changed_from"] = hidden_from
        detail["as_of_season"], detail["as_of_week"] = as_of

    for row in final_rows:
        detail = row.setdefault("detail", {})
        write(detail, row["category"], row["scope"], row["subject_key"])
        for alt in detail.get("alternates") or []:
            alt_detail = alt.setdefault("detail", {})
            write(alt_detail, row["category"], row["scope"], alt["subject_key"])
        if row["category"] in TEAM_WEEK_AWARDS:
            for name, board in (detail.get("boards") or {}).items():
                board_when = board_last.get((row["category"], row["scope"], name))
                for alt in board:
                    alt_detail = alt.setdefault("detail", {})
                    when = last.get((row["category"], row["scope"], name, str(alt["subject_key"])))
                    if when:
                        alt_detail["changed_season"], alt_detail["changed_week"] = when
                        alt_detail["hide_changed_season"], alt_detail["hide_changed_week"] = when
                    if board_when:
                        alt_detail["board_season"], alt_detail["board_week"] = board_when
                        alt_detail["hide_board_season"], alt_detail["hide_board_week"] = board_when
                    alt_detail["as_of_season"], alt_detail["as_of_week"] = as_of


def _at_or_before(season: int, week: int, cutoff: tuple[int, int]) -> bool:
    return (int(season), int(week)) <= cutoff


def rankings_through(
    cutoff: tuple[int, int],
    player_weeks: list[dict],
    team_weeks: list[dict],
    draft_picks: list[dict],
    trades: list[dict],
    payouts: dict,
    finishers: dict,
    logos: dict,
    current_season: int,
    activity: list[dict] | None,
    free_agents: list[dict] | None,
    with_owners: bool = False,
) -> list[dict]:
    season_limit, week_limit = cutoff
    players = [row for row in player_weeks if _at_or_before(row["season"], row["week"], cutoff)]
    teams = [row for row in team_weeks if _at_or_before(row["season"], row["week"], cutoff)]
    picks = [row for row in draft_picks if int(row["season"]) <= season_limit]
    kept_trades = []
    for row in trades:
        season = int(row["season"])
        week = row.get("week")
        if week is None or int(week) <= 0:
            if season <= season_limit:
                kept_trades.append(row)
        elif _at_or_before(season, week, cutoff):
            kept_trades.append(row)
    kept_activity = []
    for row in activity or []:
        season = int(row["season"])
        occurred = row.get("occurred_at")
        if season < season_limit or (season == season_limit and not occurred):
            kept_activity.append(row)
            continue
        if season > season_limit or not occurred:
            continue
        if activity_scoring_week(str(occurred), season) <= week_limit:
            kept_activity.append(row)
    agents = [row for row in free_agents or [] if int(row["season"]) <= season_limit]
    return build_superlatives(
        players,
        teams,
        picks,
        kept_trades,
        payouts,
        finishers,
        logos,
        current_season,
        kept_activity,
        agents,
        with_owners,
    )


def replay_recency(
    player_weeks: list[dict],
    team_weeks: list[dict],
    draft_picks: list[dict],
    trades: list[dict],
    payouts: dict,
    finishers: dict,
    logos: dict,
    current_season: int,
    activity: list[dict] | None = None,
    free_agents: list[dict] | None = None,
) -> list[dict]:
    weeks = {
        (int(row["season"]), int(row["week"]))
        for row in list(player_weeks) + list(team_weeks)
    }
    ordered = sorted(weeks)
    if not ordered:
        return build_superlatives(
            player_weeks,
            team_weeks,
            draft_picks,
            trades,
            payouts,
            finishers,
            logos,
            current_season,
            activity,
            free_agents,
        )
    snapshots = []
    built = []
    for index, cutoff in enumerate(ordered):
        print(f"  recency through {cutoff[0]} week {cutoff[1]}", flush=True)
        built = rankings_through(
            cutoff,
            player_weeks,
            team_weeks,
            draft_picks,
            trades,
            payouts,
            finishers,
            logos,
            current_season,
            activity,
            free_agents,
            index == len(ordered) - 1,
        )
        snapshots.append((cutoff[0], cutoff[1], [row for row in built if "@" not in str(row["scope"])]))
    league_rows = [row for row in built if "@" not in str(row["scope"])]
    stamp_recency(league_rows, snapshots)
    return built


def _tw(**kwargs) -> dict:
    base = {
        "season": 2024,
        "week": 1,
        "team_id": 1,
        "owner": "Noah",
        "team_name": "Noah",
        "points": 0,
        "is_regular": True,
        "starter_points": 0,
        "optimal_points": None,
        "projection_lineup_points": None,
        "anti_projection_starts": None,
        "projections_ok": False,
    }
    base.update(kwargs)
    return base


def _pw(**kwargs) -> dict:
    base = {
        "season": 2024,
        "week": 1,
        "player_id": 1,
        "name": "Player",
        "pos": "WR",
        "nfl_team": "SF",
        "team_id": 1,
        "owner": "Noah",
        "started": True,
        "points": 0,
    }
    base.update(kwargs)
    return base


def self_test() -> None:
    assert year_windows(2026)[0] == "2022-2022"
    assert year_windows(2026)[-1] == "2026-2026"
    assert "2022-2026" in year_windows(2026)
    assert len(year_windows(2026)) == 15
    assert in_scope(2024, "2023-2025")
    assert not in_scope(2022, "2023-2025")
    assert in_scope(2024, "2023-2025@Noah")
    pairs = [
        {"subject_name": "Noah & Ajay", "detail": {"player_name": "Noah", "partner_name": "Ajay"}},
        {"subject_name": "Liam & Sam", "detail": {"player_name": "Liam", "partner_name": "Sam"}},
    ]
    assert _for_owner("team_duo_trades", pairs, "Ajay") == [pairs[0]]
    assert _for_owner("most_trades", [{"subject_name": "Noah", "detail": {}}], "Liam") == []
    assert _for_owner("highest_median", [{"subject_name": "Noah", "detail": {}}], "Noah") is None

    sample = [
        {
            "subject_type": "player",
            "subject_key": str(index),
            "subject_name": f"P{index}",
            "value": index,
            "display": str(index),
            "detail": {},
        }
        for index in range(12)
    ]
    emitted = emit("most_added", "all_time", sample)
    assert len(emitted) == 10
    assert len(emitted[0]["detail"]["alternates"]) == 2
    assert "alternates" not in emitted[1]["detail"]

    payouts = {
        "weekly": {"2024": 50, "2025": 75, "default": 75},
        "season_finish": {"2022": {"1": 100, "2": 50}, "2023": {"1": None, "2": None}},
    }
    assert split_cents(50, 2) == [25.0, 25.0]
    assert split_cents(50, 3) == [16.67, 16.67, 16.66]
    assert abs(sum(split_cents(50, 3)) - 50) < 0.001
    assert median_cutoff([70, 60, 50, 40, 30, 20, 10]) == 50
    assert median_cutoff(list(range(10, 0, -1))) == 6
    assert median_cutoff(list(range(12, 0, -1))) == 7

    weeks = [
        _pw(player_id=1, name="A", owner="Noah", week=1, points=-2),
        _pw(player_id=1, name="A", owner="Noah", week=2, points=-5),
        _pw(player_id=2, name="B", owner="Liam", week=1, points=-3),
        _pw(player_id=3, name="D", pos="D/ST", owner="Noah", week=1, points=-20),
    ]
    low = lowest_starts(weeks, "all_time")
    assert [item["value"] for item in low] == [-5, -3, -2]
    assert low[0]["subject_name"] == "A" and low[2]["subject_name"] == "A"
    assert low[0]["display"].endswith(" · Noah")
    assert low[1]["display"].endswith(" · Liam")

    high_weeks = [
        _pw(player_id=1, name="A", week=2, points=30),
        _pw(player_id=1, name="A", week=3, points=40),
        _pw(player_id=2, name="B", season=2023, week=1, points=40),
        _pw(player_id=2, name="B", season=2024, week=1, points=40),
        _pw(player_id=3, name="D", pos="D/ST", week=1, points=99),
        _pw(player_id=4, name="Bench", week=1, points=80, started=False),
    ]
    high = highest_starts(high_weeks, "all_time")
    assert [item["value"] for item in high] == [40, 40, 40, 30]
    assert high[0]["detail"]["season"] == 2023
    assert high[0]["display"].endswith(" · Noah")
    assert [item["detail"]["week"] for item in high if item["subject_name"] == "A"] == [3, 2]
    assert all(item["subject_name"] != "D" for item in high)
    assert all(item["subject_name"] != "Bench" for item in high)

    teams = [
        _tw(owner="Noah", team_id=1, week=1, points=10, starter_points=10, optimal_points=20),
        _tw(owner="Noah", team_id=1, week=2, points=30, starter_points=30, optimal_points=40),
        _tw(owner="Liam", team_id=2, week=1, points=5, starter_points=5, optimal_points=10),
    ]
    efficiency = rate_award(teams, "all_time", {}, 2026, "starter_points", "optimal_points", False)
    noah = next(item for item in efficiency if item["subject_name"] == "Noah")
    assert noah["value"] == 66.7

    events = season_movements(
        2024,
        [
            _pw(player_id=1, name="Stay", team_id=1, owner="Noah", week=1, started=False),
            _pw(player_id=3, name="Added", team_id=1, owner="Noah", week=1, started=False),
            _pw(player_id=1, name="Stay", team_id=2, owner="Liam", week=2, started=False),
            _pw(player_id=3, name="Added", team_id=1, owner="Noah", week=2, started=False),
        ],
        [{"season": 2024, "player_id": 1, "name": "Stay", "team_id": 1, "bid": 10},
         {"season": 2024, "player_id": 2, "name": "Gone", "team_id": 1, "bid": 5}],
    )
    kinds = {(event["name"], event["kind"]) for event in events}
    assert ("Added", "add") in kinds
    assert ("Gone", "drop") in kinds
    assert ("Stay", "drop") in kinds
    assert ("Stay", "add") in kinds
    assert ("Stay", "trade") not in kinds
    swap = season_movements(
        2024,
        [
            _pw(player_id=1, name="Stay", team_id=1, week=1),
            _pw(player_id=4, name="Back", team_id=2, week=1),
            _pw(player_id=1, name="Stay", team_id=2, week=2),
            _pw(player_id=4, name="Back", team_id=1, week=2),
        ],
        [
            {"season": 2024, "player_id": 1, "name": "Stay", "team_id": 1, "bid": 1},
            {"season": 2024, "player_id": 4, "name": "Back", "team_id": 2, "bid": 1},
        ],
    )
    assert {(event["name"], event["kind"]) for event in swap} == {
        ("Stay", "trade"),
        ("Back", "trade"),
    }
    logged = activity_movements(
        [
            {
                "season": 2026,
                "actions": [
                    {"action": "DROPPED", "player_id": 1, "player_name": "Purdy"},
                    {"action": "WAIVER ADDED", "player_id": 1, "player_name": "Purdy"},
                    {"action": "TRADE_SENT", "player_id": 2, "player_name": "Murray"},
                    {"action": "TRADE_RECEIVED", "player_id": 2, "player_name": "Murray"},
                ],
            }
        ]
    )
    assert {(event["name"], event["kind"]) for event in logged} == {
        ("Purdy", "drop"),
        ("Purdy", "add"),
        ("Murray", "trade"),
    }

    gap = season_movements(
        2024,
        [
            _pw(player_id=1, name="Stay", team_id=1, week=1),
            _pw(player_id=1, name="Stay", team_id=1, week=3),
        ],
        [{"season": 2024, "player_id": 1, "name": "Stay", "team_id": 1, "bid": 1}],
    )
    assert gap == []

    scores = []
    for team_id, owner, points in (
        (1, "Noah", 70),
        (2, "Liam", 60),
        (3, "Sam", 50),
        (4, "Alex", 40),
        (5, "Ajay", 30),
        (6, "Dean", 20),
        (7, "Rikhav", 10),
    ):
        scores.append(_tw(team_id=team_id, owner=owner, season=2024, week=14, points=points))
        scores.append(_tw(team_id=team_id, owner=owner, season=2025, week=1, points=points))
    scores.append(_tw(team_id=1, owner="Noah", season=2024, week=16, points=0, is_regular=False))
    streak = streaks(scores, "all_time", {}, 2026, True)
    noah_streak = next(item for item in streak if item["subject_name"] == "Noah")
    assert noah_streak["value"] == 2
    dean = next(item for item in streaks(scores, "all_time", {}, 2026, False) if item["subject_name"] == "Rikhav")
    assert dean["value"] == 2

    tied = [
        _tw(owner="Noah", team_id=1, week=1, points=100),
        _tw(owner="Liam", team_id=2, week=1, points=100),
        _tw(owner="Sam", team_id=3, week=1, points=90),
    ]
    wins = payout_wins(tied, "all_time", {}, 2026)
    assert {item["subject_name"]: item["value"] for item in wins} == {"Liam": 1, "Noah": 1}
    earned = total_earnings(
        tied,
        payouts,
        {2022: {1: "Noah", 2: "Liam"}},
        "all_time",
        {},
        2026,
    )
    by_name = {item["subject_name"]: item["value"] for item in earned}
    assert by_name["Noah"] == 125
    assert by_name["Liam"] == 75
    assert earned[0]["detail"]["prizes_missing"] is True
    current = total_earnings(tied, payouts, {}, "2024", {}, 2024)
    assert next(item["value"] for item in current if item["subject_name"] == "Noah") == 25
    assert current[0]["detail"]["prizes_missing"] is False
    named = total_earnings(
        [],
        {"weekly": {}, "season_finish": {"2025": {"1": {"owner": "Keshav", "amount": 1350}}}},
        {},
        "all_time",
        {},
        2026,
    )
    assert named[0]["subject_name"] == "Keshav" and named[0]["value"] == 1350
    assert named[0]["detail"]["prizes_missing"] is False
    assert named[0]["detail"]["lines"] == [{"label": "2025 champion", "amount": 1350.0}]
    assert named[0]["detail"]["payments"] == [
        {"label": "2025 champion", "amount": 1350.0, "season": 2025, "week": 17}
    ]

    weeks_only = team_week_extremes(
        [
            _tw(owner="Noah", season=2022, week=1, points=1),
            _tw(owner="Liam", season=2024, week=1, points=50),
        ],
        "all_time",
        {},
        2026,
        True,
    )
    assert [item["detail"]["season"] for item in weeks_only] == [2022, 2024]

    defenses = {(2022, 1, 1): 40.0}
    compared = [
        _tw(owner="Noah", season=2022, week=1, team_id=1, points=100, dst_points=40),
        _tw(owner="Liam", season=2024, week=1, team_id=2, points=70),
    ]
    without_dst = team_week_extremes(compared, "all_time", {}, 2026, False, defenses, True, True)
    assert [item["value"] for item in without_dst] == [70, 60]
    with_dst = team_week_extremes(compared, "all_time", {}, 2026, False, defenses, False, True)
    assert with_dst[0]["value"] == 100 and with_dst[0]["detail"]["season"] == 2022
    assert _team_week_points(_tw(points=100, dst_points=40), True, {(2024, 1, 1): -4.0}) == 104

    consolation_rows = [
        _tw(
            owner="Noah",
            season=2022,
            week=16,
            points=200,
            is_regular=False,
            is_consolation=True,
            dst_points=50,
        ),
        _tw(owner="Liam", season=2024, week=1, team_id=2, points=80),
    ]
    no_consolation = team_week_extremes(consolation_rows, "all_time", {}, 2026, False, {}, True, True)
    assert [item["detail"]["season"] for item in no_consolation] == [2024]
    with_consolation = team_week_extremes(consolation_rows, "all_time", {}, 2026, False, {}, True, False)
    assert with_consolation[0]["value"] == 150
    assert "consolation" in with_consolation[0]["display"]
    stored_weeks: list[dict] = []
    _store_team_weeks(
        stored_weeks,
        "2022-2024",
        [],
        "highest_team_week",
        {
            "default": no_consolation,
            "full_scores": team_week_extremes(consolation_rows, "2022-2024", {}, 2026, False, {}, False, True),
            "with_consolation": with_consolation,
            "full_with_consolation": team_week_extremes(
                consolation_rows, "2022-2024", {}, 2026, False, {}, False, False
            ),
        },
    )
    assert stored_weeks[0]["detail"]["boards"]["with_consolation"][0]["value"] == 150
    presented = _present_for_owner("highest_team_week", with_consolation[0])
    assert presented["subject_name"] == "2022 Wk 16"
    assert "consolation" in presented["display"]

    efficiency = rate_award(
        [
            _tw(owner="Noah", starter_points=10, optimal_points=10, points=10),
            _tw(
                owner="Noah",
                week=2,
                starter_points=0,
                optimal_points=100,
                points=0,
                is_regular=False,
                is_consolation=True,
            ),
        ],
        "all_time",
        {},
        2026,
        "starter_points",
        "optimal_points",
        False,
    )
    assert efficiency[0]["value"] == 100
    prize_week = total_earnings(
        [
            _tw(owner="Noah", season=2025, week=14, points=10),
            _tw(
                owner="Noah",
                season=2025,
                week=17,
                points=10,
                is_regular=False,
                is_consolation=True,
            ),
        ],
        {"weekly": {}, "season_finish": {"2025": {"1": {"owner": "Noah", "amount": 100}}}},
        {},
        "all_time",
        {},
        2026,
    )
    assert prize_week[0]["detail"]["payments"][0]["week"] == 14

    high = median_weeks(scores, "all_time", {}, 2026, True)
    assert high and high[0]["subject_type"] == "week"
    assert high[0]["value"] == 50

    cheap = lowest_payout_weeks(tied, "all_time", {}, 2026)
    assert cheap[0]["value"] == 100
    assert cheap[0]["detail"]["winners"][0]["owner"] == "Noah"
    assert "Liam" in cheap[0]["display"]

    starters = nfl_starter_weeks(
        [
            _pw(name="A", nfl_team="SF", owner="Noah", points=10),
            _pw(player_id=2, name="B", nfl_team="SF", owner="Liam", points=4),
            _pw(player_id=3, name="C", nfl_team="KC", owner="Sam", points=8),
        ],
        "all_time",
    )
    sf = next(item for item in starters if item["subject_name"] == "SF")
    assert sf["value"] == 2
    assert [starter["name"] for starter in sf["detail"]["starters"]] == ["A", "B"]

    free_agents = [
        {"season": 2024, "player_id": 10, "name": "Ghost", "pos": "WR", "nfl_team": "SF", "points": 180},
        {"season": 2025, "player_id": 10, "name": "Ghost", "pos": "WR", "nfl_team": "SF", "points": 40},
        {"season": 2024, "player_id": 11, "name": "Rostered", "pos": "RB", "nfl_team": "KC", "points": 300},
        {"season": 2024, "player_id": 12, "name": "Drafted", "pos": "QB", "nfl_team": "BUF", "points": 250},
        {"season": 2024, "player_id": 13, "name": "Small", "pos": "TE", "nfl_team": "DAL", "points": 20},
        {"season": 2025, "player_id": 11, "name": "Rostered", "pos": "RB", "nfl_team": "KC", "points": 90},
    ]
    weeks = [_pw(player_id=11, name="Rostered", season=2024)]
    picks = [{"season": 2024, "player_id": 12, "name": "Drafted"}]
    unrostered = least_fantasy_teams(free_agents, weeks, picks, "all_time")
    assert unrostered[0]["subject_name"] == "Ghost"
    assert unrostered[0]["value"] == 220
    assert unrostered[0]["display"] == "220 pts"
    assert unrostered[0]["detail"]["seasons"] == [
        {"season": 2024, "amount": 180},
        {"season": 2025, "amount": 40},
    ]
    assert {item["subject_name"] for item in unrostered} == {"Ghost", "Small"}
    this_year = least_fantasy_teams(free_agents, weeks, picks, "2025")
    assert this_year[0]["subject_name"] == "Rostered" and this_year[0]["value"] == 90
    assert all(item["subject_name"] != "Drafted" for item in this_year)

    tied_streaks = []
    for season, week in ((2024, 1), (2024, 2)):
        tied_streaks.append(_tw(owner="Zoe", team_id=2, season=season, week=week, points=80))
        tied_streaks.append(_tw(owner="Aaron", team_id=1, season=season, week=week, points=10))
    for season, week in ((2025, 1), (2025, 2)):
        tied_streaks.append(_tw(owner="Aaron", team_id=1, season=season, week=week, points=80))
        tied_streaks.append(_tw(owner="Zoe", team_id=2, season=season, week=week, points=10))
    ordered = streaks(tied_streaks, "all_time", {}, 2026, True)
    assert [item["subject_name"] for item in ordered[:2]] == ["Zoe", "Aaron"]
    assert ordered[0]["detail"]["start_season"] == 2024

    same_count = nfl_starter_weeks(
        [
            _pw(name="A", nfl_team="SEA", season=2025, week=1, points=10),
            _pw(player_id=2, name="B", nfl_team="ARI", season=2024, week=3, points=10),
        ],
        "all_time",
    )
    assert [item["subject_name"] for item in same_count[:2]] == ["ARI", "SEA"]

    assert activity_scoring_week("2026-10-02T18:55:00+00:00", 2026) == 4
    assert activity_scoring_week("2026-09-09T16:00:15+00:00", 2026) == 1
    week_one = [
        {
            "category": "most_trades",
            "scope": "all_time",
            "rank": 1,
            "subject_key": "A",
            "subject_name": "A",
            "value": 2,
            "display": "2 trades",
            "detail": {},
            "subject_type": "team",
        }
    ]
    week_two = [
        {
            "category": "most_trades",
            "scope": "all_time",
            "rank": 1,
            "subject_key": "A",
            "subject_name": "A",
            "value": 3,
            "display": "3 trades",
            "detail": {"alternates": [{"subject_key": "B", "subject_name": "B", "value": 1, "display": "1 trade", "detail": {}}]},
            "subject_type": "team",
        },
        {
            "category": "most_trades",
            "scope": "all_time",
            "rank": 2,
            "subject_key": "C",
            "subject_name": "C",
            "value": 1,
            "display": "1 trade",
            "detail": {},
            "subject_type": "team",
        },
    ]
    stamp_recency(week_two, [(2026, 4, week_one), (2026, 5, week_two)])
    assert week_two[0]["detail"]["changed_week"] == 5
    assert week_two[1]["detail"]["changed_week"] == 5
    assert week_two[0]["detail"]["as_of_week"] == 5
    assert board_changes([("A", 2.0)], [("A", 2.0)]) == set()

    def _least(rank: int, key: str, name: str, value: float) -> dict:
        return {
            "category": "least_fantasy_teams",
            "scope": "all_time",
            "rank": rank,
            "subject_key": key,
            "subject_name": name,
            "value": value,
            "display": f"{value} pts",
            "detail": {},
            "subject_type": "player",
        }

    before = [_least(1, "zac", "Zaccheaus", 300), _least(2, "kalif", "Kalif Raymond", 200)]
    before[0]["detail"]["alternates"] = [
        {
            "subject_key": "nelson",
            "subject_name": "Nelson Agholor",
            "value": 150,
            "display": "150 pts",
            "detail": {},
        },
        {
            "subject_key": "riser",
            "subject_name": "Riser",
            "value": 100,
            "display": "100 pts",
            "detail": {},
        },
    ]
    after = [
        _least(1, "zac", "Zaccheaus", 300),
        _least(2, "nelson", "Nelson Agholor", 150),
        _least(3, "riser", "Riser", 140),
    ]
    stamp_recency(after, [(2026, 3, before), (2026, 4, after)])
    assert after[0]["detail"]["departed"] == [
        {
            "rank": 2,
            "subject_key": "kalif",
            "subject_name": "Kalif Raymond",
            "value": 200,
            "display": "200 pts",
        }
    ]
    assert "changed_week" not in after[1]["detail"]
    assert after[2]["detail"]["changed_week"] == 4

    def _rate(rank: int, key: str, value: float) -> dict:
        return {
            "category": "projection_beater",
            "scope": "all_time",
            "rank": rank,
            "subject_key": key,
            "subject_name": key,
            "value": value,
            "display": f"{value:.1f}%",
            "detail": {},
            "subject_type": "team",
        }

    rate_before = [_rate(1, "Rikhav", 100.0), _rate(2, "Ajay", 90.0)]
    rate_after = [_rate(1, "Rikhav", 100.1), _rate(2, "Ajay", 90.0)]
    stamp_recency(rate_after, [(2026, 3, rate_before), (2026, 4, rate_after)])
    assert rate_after[0]["detail"]["changed_from"] == 100.0
    assert rate_after[0]["detail"]["changed_week"] == 4
    assert "changed_from" not in rate_after[1]["detail"]

    streak_rows = [
        _pw(player_id=1, name="Deebo", week=1, points=10, projected_points=8),
        _pw(player_id=1, name="Deebo", week=2, points=9, projected_points=8),
        _pw(player_id=1, name="Deebo", week=3, points=8, projected_points=8),
        _pw(player_id=1, name="Deebo", week=4, points=12, projected_points=8),
        _pw(player_id=2, name="Gap", week=1, points=10, projected_points=5),
        _pw(player_id=2, name="Gap", week=3, points=10, projected_points=5),
        _pw(player_id=3, name="Bye", week=1, points=0, projected_points=0),
        _pw(player_id=3, name="Bye", week=2, points=10, projected_points=5),
        _pw(player_id=3, name="Bye", week=3, points=3, projected_points=5),
        _pw(player_id=4, name="Zero", week=1, points=10, projected_points=5),
        _pw(player_id=4, name="Zero", week=2, points=0, projected_points=0),
        _pw(player_id=4, name="Zero", week=3, points=10, projected_points=5),
    ]
    over = projection_streaks(streak_rows, "all_time", True)
    deebo = next(item for item in over if item["subject_name"] == "Deebo")
    assert deebo["value"] == 2
    assert deebo["detail"]["start_week"] == 1 and deebo["detail"]["end_week"] == 2
    assert deebo["detail"]["active"] is False
    gap = next(item for item in over if item["subject_name"] == "Gap")
    assert gap["value"] == 1
    zero = next(item for item in over if item["subject_name"] == "Zero")
    assert zero["value"] == 1
    bye_slate = [
        _pw(player_id=10, name="Through", nfl_team="NE", week=1, points=10, projected_points=5),
        _pw(player_id=10, name="Through", nfl_team="NE", week=2, points=0, projected_points=0),
        _pw(player_id=10, name="Through", nfl_team="NE", week=3, points=12, projected_points=5),
        _pw(player_id=11, name="Mate", nfl_team="NE", week=2, points=0, projected_points=0),
        _pw(player_id=12, name="A", nfl_team="KC", week=2, points=0, projected_points=0),
        _pw(player_id=13, name="B", nfl_team="KC", week=2, points=0, projected_points=0),
        _pw(player_id=14, name="C", nfl_team="DAL", week=2, points=0, projected_points=0),
        _pw(player_id=15, name="D", nfl_team="DAL", week=2, points=0, projected_points=0),
        _pw(player_id=20, name="Resting", nfl_team="KC", week=1, points=10, projected_points=5),
        _pw(player_id=20, name="Resting", nfl_team="KC", week=2, points=0, projected_points=0),
    ]
    through = projection_streaks(bye_slate, "all_time", True)
    bridged = next(item for item in through if item["subject_name"] == "Through")
    assert bridged["value"] == 2
    assert bridged["detail"]["start_week"] == 1 and bridged["detail"]["end_week"] == 3
    assert [week["week"] for week in bridged["detail"]["weeks"]] == [1, 2, 3]
    assert bridged["detail"]["weeks"][1]["bye"] is True
    resting = next(item for item in through if item["subject_name"] == "Resting")
    assert resting["value"] == 1 and resting["detail"]["active"] is True
    under = projection_streaks(streak_rows, "all_time", False)
    bye = next(item for item in under if item["subject_name"] == "Bye")
    assert bye["value"] == 1
    assert bye["detail"]["start_week"] == 3 and bye["detail"]["active"] is True
    assert all(item["subject_name"] != "Bye" or item["value"] == 1 for item in over)

    years = owner_roster_years(
        [
            _pw(player_id=1, name="Long", season=2024, week=1, owner="Noah"),
            _pw(player_id=1, name="Long", season=2024, week=2, owner="Noah"),
            _pw(player_id=1, name="Long", season=2025, week=1, owner="Noah"),
            _pw(player_id=2, name="Busy", season=2024, week=1, owner="Noah"),
            _pw(player_id=2, name="Busy", season=2024, week=2, owner="Noah"),
            _pw(player_id=2, name="Busy", season=2024, week=3, owner="Noah"),
        ],
        "2024-2025",
        "Noah",
    )
    assert [item["subject_name"] for item in years] == ["Long", "Busy"]
    assert years[0]["display"] == "2 years · 3 games"
    assert years[0]["detail"]["seasons"][0]["games"] == 2

    deals = [
        {"season": 2024, "player_id": 1, "name": "A", "kind": "trade", "owners": ["Noah", "Liam"]},
        {"season": 2024, "player_id": 1, "name": "A", "kind": "trade", "owners": ["Liam", "Sam"]},
    ]
    deal_latest = {1: {"player_id": 1, "name": "A", "pos": "WR", "nfl_team": "SF", "season": 2024, "week": 1}}
    assert movement_leaders(deals, deal_latest, "2024-2024", "trade", "trades")[0]["value"] == 2
    assert movement_leaders(deals, deal_latest, "2024-2024", "trade", "trades", "Noah")[0]["value"] == 1

    prices = [
        {"season": 2024, "player_id": 1, "name": "A", "bid": 10, "owner": "Noah"},
        {"season": 2025, "player_id": 1, "name": "A", "bid": 40, "owner": "Liam"},
    ]
    assert auction_totals(prices, "2024-2025", owner="Noah")[0]["value"] == 10
    assert auction_totals(prices, "2024-2025")[0]["value"] == 50

    crossed = [
        _pw(player_id=9, name="Cross", owner="Noah", week=1, points=10, projected_points=5),
        _pw(player_id=9, name="Cross", owner="Noah", week=2, points=10, projected_points=5),
        _pw(player_id=9, name="Cross", owner="Liam", week=3, points=10, projected_points=5),
        _pw(player_id=9, name="Cross", owner="Noah", week=4, points=10, projected_points=5),
    ]
    assert projection_streaks(crossed, "2024-2024", True, "Noah")[0]["value"] == 2
    assert projection_streaks(crossed, "2024-2024", True)[0]["value"] == 4

    start = _present_for_owner(
        "lowest_start",
        {"value": 1.2, "subject_name": "Kyler Murray", "detail": {"pos": "QB", "season": 2026, "week": 1, "owner": "Rikhav"}},
    )
    assert start["display"] == "QB · 1.2 · 2026 Wk 1"
    week = _present_for_owner(
        "highest_team_week",
        {"value": 80, "subject_name": "Noah", "detail": {"season": 2024, "week": 3, "opponent_owner": "Liam"}},
    )
    assert week["subject_name"] == "2024 Wk 3"
    assert week["display"] == "80 · vs Liam"
    hidden: list[dict] = []
    _store(
        hidden,
        "2024-2024",
        ["Noah"],
        "highest_median",
        [
            {
                "subject_type": "week",
                "subject_key": "2024:1",
                "subject_name": "2024 Wk 1",
                "value": 100,
                "display": "100",
                "detail": {},
            }
        ],
    )
    assert hidden and all("@" not in row["scope"] for row in hidden)

    print("superlative ranks ok")


if __name__ == "__main__":
    self_test()
