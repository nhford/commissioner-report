"""Lineup efficiency and projection-beater math.

Fallback copy of coding-projects/lineup-efficiency/efficiency.py for the
Tuesday job, which cannot read that private repo. Local scrapes prefer the
original file when it sits next to this project. Keep the two copies in sync.

Both ratios use actual points on each side. Projections only choose who would
have started. Season rates must sum the two totals, then divide — never average
the weekly percentages.

Call configure(slot_counts) before the two-argument starters_optimize form.
The notebook and the commissioner-report scraper share this file.
"""

from __future__ import annotations

NATURAL_ORDERING = {
    "QB": 0,
    "RB": 1,
    "WR": 2,
    "TE": 3,
    "RB/WR/TE": 4,
    "D/ST": 5,
}

DEFAULT_SLOTS: dict[str, int] | None = None


def configure(slot_counts: dict) -> None:
    global DEFAULT_SLOTS
    DEFAULT_SLOTS = {str(key): int(value) for key, value in slot_counts.items()}


def _slots(slots: dict | None = None) -> dict[str, int]:
    source = slots if slots is not None else DEFAULT_SLOTS
    if source is None:
        raise RuntimeError("Call configure(slot_counts) or pass slots.")
    return {str(key): int(value) for key, value in source.items()}


def starters_actual(lineup):
    starters = [
        [player, player.lineupSlot]
        for player in lineup
        if player.lineupSlot not in ("IR", "BE")
    ]
    return sorted(
        starters,
        key=lambda row: NATURAL_ORDERING.get(row[0].lineupSlot, 99),
    )


def starters_optimize(lineup, property, slots=None):
    slot_counts = _slots(slots)
    ordered = sorted(
        lineup,
        key=lambda player: float(getattr(player, property) or 0),
        reverse=True,
    )
    best = []
    for player in ordered:
        pos = player.position
        if slot_counts.get(pos, 0) > 0:
            best.append([player, pos])
            slot_counts[pos] -= 1
        elif pos in ("RB", "WR", "TE") and slot_counts.get("RB/WR/TE", 0) > 0:
            best.append([player, "RB/WR/TE"])
            slot_counts["RB/WR/TE"] -= 1
    return sorted(best, key=lambda row: NATURAL_ORDERING.get(row[1], 99))


def sum_lineup(lineup) -> float:
    total = 0.0
    for player, _slot in lineup:
        total += float(getattr(player, "points", 0) or 0)
    return total


def calc_efficiency(actual, optimized):
    actual_total = sum_lineup(actual)
    optimal_total = sum_lineup(optimized)
    if not optimal_total:
        return 0, round(actual_total, 2), round(optimal_total, 2)
    return (
        round(actual_total / optimal_total, 3),
        round(actual_total, 2),
        round(optimal_total, 2),
    )


def lineup_totals(lineup, slots=None) -> dict:
    """Actual starter points, hindsight-optimal points, and projection-lineup points.

    projection_lineup_points is the actual score of the lineup chosen by
    projected_points. anti_projection_starts counts starters who are outside
    that lineup.
    """
    actual = starters_actual(lineup)
    optimal = starters_optimize(lineup, "points", slots)
    projected = starters_optimize(lineup, "projected_points", slots)
    projected_ids = {row[0].playerId for row in projected}
    anti = sum(1 for row in actual if row[0].playerId not in projected_ids)
    projected_mass = 0.0
    for player in lineup:
        projected_mass += float(getattr(player, "projected_points", 0) or 0)
    return {
        "starter_points": round(sum_lineup(actual), 2),
        "optimal_points": round(sum_lineup(optimal), 2),
        "projection_lineup_points": round(sum_lineup(projected), 2),
        "anti_projection_starts": anti,
        "projected_mass": projected_mass,
    }
