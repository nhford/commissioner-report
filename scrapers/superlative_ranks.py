"""Pure Superlatives rankings. Category ids match lib/superlatives.ts."""

from __future__ import annotations

from itertools import combinations

PAYOUT_START = 2024
MEDIAN_CUT = 6


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


def week_text(season: int, week: int) -> str:
    return f"{season} Wk {week}"


def span_text(start_season: int, start_week: int, end_season: int, end_week: int) -> str:
    if start_season == end_season:
        if start_week == end_week:
            return week_text(start_season, start_week)
        return f"{start_season} Wk {start_week}–{end_week}"
    return f"{week_text(start_season, start_week)}–{week_text(end_season, end_week)}"


def in_scope(season: int, scope: str) -> bool:
    if scope == "all_time":
        return True
    return int(season) == int(scope)


def prize_amount(places: dict | None, place: int):
    if not places:
        return None
    if str(place) in places:
        return places[str(place)]
    if place in places:
        return places[place]
    return None


def prizes_missing(payouts: dict, scope: str) -> bool:
    finishes = payouts.get("season_finish") or {}
    for year, places in finishes.items():
        if scope != "all_time" and str(year) != str(scope):
            continue
        for place in (1, 2):
            if prize_amount(places, place) is None:
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
    ordered = sorted(scores, reverse=True)
    if not ordered:
        return 0.0
    return ordered[min(MEDIAN_CUT - 1, len(ordered) - 1)]


def owner_logo(logos: dict, season: int, owner: str, fallback_season: int) -> str | None:
    return logos.get((season, owner)) or logos.get((fallback_season, owner))


PODIUM = 3
ALTERNATES = 17


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
    chosen = items[: PODIUM + ALTERNATES]
    rows = []
    for rank, item in enumerate(chosen[:PODIUM], start=1):
        detail = dict(item.get("detail") or {})
        if rank == 1:
            extras = [_candidate(extra) for extra in chosen[PODIUM:]]
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
        for pid, tid in curr.items():
            old = prev.get(pid)
            kind = None
            if old is None:
                kind = "add"
            elif old != tid:
                kind = "trade"
            if kind:
                events.append(
                    {
                        "season": season,
                        "player_id": pid,
                        "name": names.get(pid, str(pid)),
                        "kind": kind,
                    }
                )
        for pid, old_tid in prev.items():
            if pid not in curr and old_tid in played:
                events.append(
                    {
                        "season": season,
                        "player_id": pid,
                        "name": names.get(pid, str(pid)),
                        "kind": "drop",
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
                },
            }
        )
    items.sort(key=lambda item: (-item["value"], item["subject_name"]))
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
    return items


def lowest_starts(rows: list[dict], scope: str) -> list[dict]:
    chosen = []
    for row in rows:
        if not in_scope(int(row["season"]), scope) or not row.get("started"):
            continue
        if row.get("pos") in {"D/ST", "DST"}:
            continue
        chosen.append(row)
    chosen.sort(key=lambda row: (r2(row["points"]), int(row["season"]), int(row["week"]), row["name"]))
    items = []
    for row in chosen[:3]:
        pid = int(row["player_id"])
        season = int(row["season"])
        week = int(row["week"])
        points = r2(row["points"])
        pos = row.get("pos")
        bits = [bit for bit in (pos, points_text(points), week_text(season, week)) if bit]
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
                    "season": season,
                    "week": week,
                },
            }
        )
    return items


def auction_totals(picks: list[dict], scope: str) -> list[dict]:
    totals: dict[int, float] = {}
    latest: dict[int, dict] = {}
    for pick in picks:
        season = int(pick["season"])
        if not in_scope(season, scope):
            continue
        pid = int(pick["player_id"])
        totals[pid] = totals.get(pid, 0) + float(pick.get("bid") or 0)
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
                    "pos": info.get("pos"),
                },
            }
        )
    items.sort(key=lambda item: (-item["value"], item["subject_name"]))
    return items


def movement_leaders(events: list[dict], latest: dict[int, dict], scope: str, kind: str, suffix: str) -> list[dict]:
    counts: dict[int, float] = {}
    for event in events:
        if event["kind"] != kind or not in_scope(int(event["season"]), scope):
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


def team_week_extremes(rows: list[dict], scope: str, logos: dict, current_season: int, lowest: bool) -> list[dict]:
    chosen = []
    for row in rows:
        if not in_scope(int(row["season"]), scope):
            continue
        owner = usable_owner(row.get("owner"))
        if not owner:
            continue
        chosen.append(row)
    chosen.sort(
        key=lambda row: (
            r2(row["points"]) if lowest else -r2(row["points"]),
            int(row["season"]),
            int(row["week"]),
            row.get("owner") or "",
        )
    )
    items = []
    for row in chosen[:3]:
        owner = usable_owner(row.get("owner"))
        season = int(row["season"])
        week = int(row["week"])
        points = r2(row["points"])
        items.append(
            {
                "subject_type": "team",
                "subject_key": f"{owner}:{season}:{week}",
                "subject_name": owner,
                "value": points,
                "display": f"{points_text(points)} · {week_text(season, week)}",
                "detail": {
                    "season": season,
                    "week": week,
                    "team_name": row.get("team_name"),
                    "logo_path": owner_logo(logos, season, owner, current_season),
                },
            }
        )
    return items


def weekly_winners(rows: list[dict], scope: str) -> list[tuple[tuple[int, int], list[dict]]]:
    groups: dict[tuple[int, int], list[dict]] = {}
    for row in rows:
        season = int(row["season"])
        if not row.get("is_regular") or season < PAYOUT_START or not in_scope(season, scope):
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
    items.sort(key=lambda item: (-item["value"], item["subject_name"]))
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
    finishes = payouts.get("season_finish") or {}
    for year, places in finishes.items():
        season = int(year)
        if not in_scope(season, scope):
            continue
        placed = finishers.get(season) or finishers.get(year) or {}
        for place in (1, 2):
            amount = prize_amount(places, place)
            owner = usable_owner(placed.get(place) or placed.get(str(place)))
            if amount is None or not owner:
                continue
            totals[owner] = totals.get(owner, 0) + float(amount)
    for (season, _week), winners in weekly_winners(rows, scope):
        rate = weekly_rate(payouts, season)
        if rate <= 0 or not winners:
            continue
        shares = split_cents(rate, len(winners))
        for row, share in zip(winners, shares):
            owner = usable_owner(row.get("owner"))
            if owner:
                totals[owner] = totals.get(owner, 0) + share
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
                },
            }
        )
    items.sort(key=lambda item: (-item["value"], item["subject_name"]))
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
    items.sort(key=lambda item: (-item["value"], item["subject_name"]))
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
    items.sort(key=lambda item: (-item["value"], item["subject_name"]))
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
    items.sort(key=lambda item: (-item["value"], item["subject_name"]))
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
        if not in_scope(int(row["season"]), scope):
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
    items.sort(key=lambda item: (-item["value"], item["subject_name"]))
    return items


def anti_projection(rows: list[dict], scope: str, logos: dict, current_season: int) -> list[dict]:
    totals: dict[str, int] = {}
    for row in rows:
        if not in_scope(int(row["season"]), scope) or not row.get("projections_ok"):
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
    items.sort(key=lambda item: (-item["value"], item["subject_name"]))
    return items


def player_duos(rows: list[dict], scope: str) -> list[dict]:
    groups: dict[tuple, dict[int, dict]] = {}
    for row in rows:
        if not in_scope(int(row["season"]), scope) or not row.get("started"):
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
                    "partner_id": int(second["player_id"]),
                    "partner_name": second["name"],
                    "partner_pos": second.get("pos"),
                },
            }
        )
    items.sort(key=lambda item: (-item["value"], item["subject_name"]))
    return items


def nfl_starter_weeks(rows: list[dict], scope: str) -> list[dict]:
    counts: dict[tuple[str, int, int], int] = {}
    for row in rows:
        team = row.get("nfl_team")
        if not team or team == "None" or not row.get("started"):
            continue
        if not in_scope(int(row["season"]), scope):
            continue
        key = (str(team), int(row["season"]), int(row["week"]))
        counts[key] = counts.get(key, 0) + 1
    items = []
    for (team, season, week), count in counts.items():
        items.append(
            {
                "subject_type": "nfl",
                "subject_key": f"{team}:{season}:{week}",
                "subject_name": team,
                "value": count,
                "display": f"{count} starters · {week_text(season, week)}",
                "detail": {"nfl_team": team, "season": season, "week": week},
            }
        )
    items.sort(key=lambda item: (-item["value"], item["subject_name"], item["detail"]["season"], item["detail"]["week"]))
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
) -> list[dict]:
    seasons = {int(row["season"]) for row in player_weeks}
    seasons.update(int(row["season"]) for row in draft_picks)
    events: list[dict] = []
    for season in sorted(seasons):
        events.extend(season_movements(season, player_weeks, draft_picks))
    latest = _latest_player(player_weeks)
    scopes = ["all_time", str(current_season)]
    rows: list[dict] = []
    for scope in scopes:
        rows.extend(emit("most_fantasy_teams", scope, most_fantasy_teams(player_weeks, scope)))
        rows.extend(emit("lowest_start", scope, lowest_starts(player_weeks, scope)))
        rows.extend(emit("most_auction_dollars", scope, auction_totals(draft_picks, scope)))
        rows.extend(emit("most_added", scope, movement_leaders(events, latest, scope, "add", "adds")))
        rows.extend(emit("most_dropped", scope, movement_leaders(events, latest, scope, "drop", "drops")))
        rows.extend(
            emit("most_traded_player", scope, movement_leaders(events, latest, scope, "trade", "trades"))
        )
        rows.extend(
            emit(
                "lowest_team_week",
                scope,
                team_week_extremes(team_weeks, scope, logos, current_season, True),
            )
        )
        rows.extend(
            emit(
                "highest_team_week",
                scope,
                team_week_extremes(team_weeks, scope, logos, current_season, False),
            )
        )
        rows.extend(emit("player_duo_starts", scope, player_duos(player_weeks, scope)))
        rows.extend(emit("payout_wins", scope, payout_wins(team_weeks, scope, logos, current_season)))
        rows.extend(
            emit(
                "total_earnings",
                scope,
                total_earnings(team_weeks, payouts, finishers, scope, logos, current_season),
            )
        )
        rows.extend(emit("median_streak", scope, streaks(team_weeks, scope, logos, current_season, True)))
        rows.extend(emit("median_misses", scope, streaks(team_weeks, scope, logos, current_season, False)))
        rows.extend(emit("team_duo_trades", scope, team_duo_trades(trades, scope, logos, current_season)))
        rows.extend(emit("most_trades", scope, most_trades(trades, scope, logos, current_season)))
        rows.extend(
            emit(
                "projection_beater",
                scope,
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
        )
        rows.extend(
            emit(
                "lineup_efficiency",
                scope,
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
        )
        rows.extend(
            emit("anti_projection_starts", scope, anti_projection(team_weeks, scope, logos, current_season))
        )
        rows.extend(emit("nfl_starter_week", scope, nfl_starter_weeks(player_weeks, scope)))
    return rows


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
    sample = [
        {
            "subject_type": "player",
            "subject_key": str(index),
            "subject_name": f"P{index}",
            "value": index,
            "display": str(index),
            "detail": {},
        }
        for index in range(10)
    ]
    emitted = emit("most_added", "all_time", sample)
    assert len(emitted) == 3
    assert len(emitted[0]["detail"]["alternates"]) == 7
    assert "alternates" not in emitted[1]["detail"]

    payouts = {
        "weekly": {"2024": 50, "2025": 75, "default": 75},
        "season_finish": {"2022": {"1": 100, "2": 50}, "2023": {"1": None, "2": None}},
    }
    assert split_cents(50, 2) == [25.0, 25.0]
    assert split_cents(50, 3) == [16.67, 16.67, 16.66]
    assert abs(sum(split_cents(50, 3)) - 50) < 0.001
    assert median_cutoff([70, 60, 50, 40, 30, 20, 10]) == 20

    weeks = [
        _pw(player_id=1, name="A", owner="Noah", week=1, points=-2),
        _pw(player_id=1, name="A", owner="Noah", week=2, points=-5),
        _pw(player_id=2, name="B", owner="Liam", week=1, points=-3),
        _pw(player_id=3, name="D", pos="D/ST", owner="Noah", week=1, points=-20),
    ]
    low = lowest_starts(weeks, "all_time")
    assert [item["value"] for item in low] == [-5, -3, -2]
    assert low[0]["subject_name"] == "A" and low[2]["subject_name"] == "A"

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
    assert ("Stay", "trade") in kinds
    assert ("Stay", "add") not in kinds

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

    print("superlative ranks ok")


if __name__ == "__main__":
    self_test()
