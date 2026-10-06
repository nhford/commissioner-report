#!/usr/bin/env python3
"""Game-script fantasy simulator for Median Watch.

Each remaining NFL game is one draw of margin and total around the closing
line. Stats move with that score only as much as they have historically, and
passing touchdowns are drawn once and shared by the quarterback and a receiver.
Kickers and defenses are functions of the same score. The healthy draw is
shifted onto that player's ESPN projection. A skill player can then leave
mid-game: each snap is a small chance of a time-loss injury, and an exit on
play k of N keeps k/N of that healthy draw. Those shortened games are not
shifted back up.
"""

from __future__ import annotations

import io
import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PARAMS_PATH = ROOT / "data" / "score_model_params.json"
SCHEDULE_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
)

# Mack et al., AJSM 2020. Time-loss lower-extremity injuries per 10,000
# player-plays in NFL games, 2015-2018. Snaps are a typical starter's count,
# so the chance he is hurt sometime this week is 1 - (1 - p) ** snaps.
INJURY_PARAMS = {
    "source": (
        "Mack et al., AJSM 2020, time-loss lower-extremity injuries "
        "per 10,000 player-plays, NFL games 2015-2018"
    ),
    "per_10000": {"QB": 4.5, "RB": 16.0, "WR": 12.1, "TE": 10.3},
    "snaps": {"QB": 64, "RB": 42, "WR": 58, "TE": 48},
}

NFLVERSE_TO_ESPN = {
    "LA": "LAR",
    "WAS": "WSH",
    "JAC": "JAX",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
}

# ESPN scoring stat id -> breakdown name. Chunk stats are per-yard equivalents
# and are applied only when the league does not already score that stat per yard.
LINEAR_STAT_IDS = {
    3: "passingYards",
    4: "passingTouchdowns",
    19: "passing2PtConversions",
    20: "passingInterceptions",
    23: "rushingAttempts",
    24: "rushingYards",
    25: "rushingTouchdowns",
    26: "rushing2PtConversions",
    42: "receivingYards",
    43: "receivingTouchdowns",
    44: "receiving2PtConversions",
    58: "receivingTargets",
    72: "lostFumbles",
    74: "madeFieldGoalsFrom50Plus",
    77: "madeFieldGoalsFrom40To49",
    80: "madeFieldGoalsFromUnder40",
    86: "madeExtraPoints",
    93: "defensiveBlockedKickForTouchdowns",
    94: "defensiveTouchdowns",
    95: "defensiveInterceptions",
    96: "defensiveFumbles",
    98: "defensiveSafeties",
    99: "defensiveSacks",
    101: "kickoffReturnTouchdowns",
    102: "puntReturnTouchdowns",
    103: "interceptionReturnTouchdowns",
    104: "fumbleReturnTouchdowns",
}

CHUNK_STAT_IDS = {
    8: ("passingYards", 25),
    6: ("passingYards", 10),
    30: ("rushingYards", 25),
    28: ("rushingYards", 10),
    50: ("receivingYards", 25),
    48: ("receivingYards", 10),
}

RECEPTION_STAT_IDS = (53, 41)

PA_RANGES = (
    (89, 0, 0),
    (90, 1, 6),
    (91, 7, 13),
    (92, 14, 17),
    (121, 18, 21),
    (122, 22, 27),
    (123, 28, 34),
    (124, 35, 45),
    (125, 46, 99),
)

DST_COUNTS = (
    "defensiveSacks",
    "defensiveInterceptions",
    "defensiveFumbles",
    "defensiveTouchdowns",
    "defensiveBlockedKickForTouchdowns",
    "kickoffReturnTouchdowns",
    "puntReturnTouchdowns",
    "interceptionReturnTouchdowns",
    "fumbleReturnTouchdowns",
    "defensiveSafeties",
)

SKILL_YARDS = ("passingYards", "rushingYards", "receivingYards")
SKILL_COUNTS = ("receivingReceptions", "rushingAttempts", "receivingTargets", "lostFumbles", "passingInterceptions")

DEFAULT_CV = {
    "passingYards": 0.30,
    "rushingYards": 0.55,
    "receivingYards": 0.55,
    "receivingReceptions": 0.45,
    "rushingAttempts": 0.35,
    "receivingTargets": 0.40,
}


@dataclass
class Scoring:
    linear: dict[str, float]
    pa_buckets: list[tuple[int, int, float]] = field(default_factory=list)

    def score(self, arrays: dict[str, np.ndarray], n: int) -> np.ndarray:
        total = np.zeros(n, dtype=float)
        for name, values in arrays.items():
            weight = self.linear.get(name, 0.0)
            if not weight:
                continue
            total = total + np.asarray(values, dtype=float) * weight
        return total

    def uses_ppr(self) -> bool:
        return self.linear.get("receivingReceptions", 0.0) >= 0.4


def default_scoring() -> Scoring:
    """ESPN default PPR: 4-point passing touchdowns, 1 point per reception."""
    return Scoring(
        linear={
            "passingYards": 0.04,
            "passingTouchdowns": 4.0,
            "passingInterceptions": -2.0,
            "rushingYards": 0.1,
            "rushingTouchdowns": 6.0,
            "receivingYards": 0.1,
            "receivingTouchdowns": 6.0,
            "receivingReceptions": 1.0,
            "lostFumbles": -2.0,
            "madeExtraPoints": 1.0,
            "madeFieldGoalsFromUnder40": 3.0,
            "madeFieldGoalsFrom40To49": 4.0,
            "madeFieldGoalsFrom50Plus": 5.0,
            "defensiveSacks": 1.0,
            "defensiveInterceptions": 2.0,
            "defensiveFumbles": 2.0,
            "defensiveTouchdowns": 6.0,
            "kickoffReturnTouchdowns": 6.0,
            "puntReturnTouchdowns": 6.0,
            "interceptionReturnTouchdowns": 6.0,
            "fumbleReturnTouchdowns": 6.0,
            "defensiveSafeties": 2.0,
        },
        pa_buckets=[
            (0, 0, 10.0),
            (1, 6, 7.0),
            (7, 13, 4.0),
            (14, 17, 1.0),
            (18, 21, 0.0),
            (22, 27, -1.0),
            (28, 34, -4.0),
            (35, 45, -7.0),
            (46, 99, -10.0),
        ],
    )


def scoring_from_league(league) -> Scoring:
    items = getattr(getattr(league, "settings", None), "scoring_format", None) or []
    by_id: dict[int, float] = {}
    for item in items:
        try:
            by_id[int(item["id"])] = float(item.get("points") or 0)
        except (KeyError, TypeError, ValueError):
            continue
    if not by_id:
        return default_scoring()
    return scoring_from_ids(by_id)


def scoring_from_ids(by_id: dict[int, float]) -> Scoring:
    linear: dict[str, float] = {}
    for stat_id, name in LINEAR_STAT_IDS.items():
        points = by_id.get(stat_id, 0.0)
        if points:
            linear[name] = linear.get(name, 0.0) + points
    reception = 0.0
    for stat_id in RECEPTION_STAT_IDS:
        if by_id.get(stat_id):
            reception = by_id[stat_id]
            break
    if reception:
        linear["receivingReceptions"] = reception
    for stat_id, (name, chunk) in CHUNK_STAT_IDS.items():
        points = by_id.get(stat_id, 0.0)
        if points and not linear.get(name):
            linear[name] = points / chunk
    buckets = []
    for stat_id, lo, hi in PA_RANGES:
        if stat_id in by_id:
            buckets.append((lo, hi, by_id[stat_id]))
    if not buckets:
        buckets = list(default_scoring().pa_buckets)
    if "passingTouchdowns" not in linear and "passingYards" not in linear:
        return default_scoring()
    return Scoring(linear=linear, pa_buckets=buckets)


def load_params(path: Path | None = None) -> dict:
    params_path = path or PARAMS_PATH
    if not params_path.exists():
        raise FileNotFoundError(
            f"Missing {params_path}. Run scrapers/calibrate_score_model.py."
        )
    return json.loads(params_path.read_text())


def espn_abbr(team: str) -> str:
    team = str(team or "").upper()
    return NFLVERSE_TO_ESPN.get(team, team)


def norm_pos(pos: str | None) -> str:
    raw = (pos or "").upper().replace(" ", "")
    if raw in {"DST", "D/ST", "DEF", "D"}:
        return "D/ST"
    if raw in {"QB", "RB", "WR", "TE", "K"}:
        return raw
    return "FLEX"


def role_for(position: str | None) -> str:
    pos = norm_pos(position)
    if pos == "D/ST":
        return "DST"
    if pos == "K":
        return "K"
    return "SKILL"


def load_week_lines(season: int, week: int) -> dict[str, dict]:
    """Closing spread and total for one week, keyed by ESPN team abbreviation."""
    req = urllib.request.Request(SCHEDULE_URL, headers={"User-Agent": "commissioner-report"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    df = pd.read_csv(io.BytesIO(raw))
    sub = df[(df["season"] == int(season)) & (df["week"] == int(week))]
    regular = sub[sub["game_type"] == "REG"]
    if not regular.empty:
        sub = regular
    lines: dict[str, dict] = {}
    for row in sub.itertuples(index=False):
        spread = getattr(row, "spread_line", None)
        total = getattr(row, "total_line", None)
        if spread is None or total is None or pd.isna(spread) or pd.isna(total):
            continue
        home = espn_abbr(row.home_team)
        away = espn_abbr(row.away_team)
        spread_f = float(spread)
        total_f = float(total)
        home_implied = max(0.5, (total_f + spread_f) / 2)
        away_implied = max(0.5, (total_f - spread_f) / 2)
        key = f"{away}@{home}"
        lines[home] = {
            "opponent": away,
            "implied": home_implied,
            "is_home": True,
            "spread": spread_f,
            "total": total_f,
            "game_key": key,
        }
        lines[away] = {
            "opponent": home,
            "implied": away_implied,
            "is_home": False,
            "spread": spread_f,
            "total": total_f,
            "game_key": key,
        }
    return lines


def _points_cv(params: dict, position: str, scoring: Scoring) -> float:
    table_name = "position_points_cv_ppr" if scoring.uses_ppr() else "position_points_cv"
    table = params.get(table_name) or params.get("position_points_cv") or {}
    pos = norm_pos(position)
    if pos not in table and pos == "D/ST":
        return 0.55
    return float(table.get(pos, table.get("FLEX", 0.6)))


def scale_mean(base: float, script: np.ndarray, elasticity: float) -> np.ndarray:
    """Move a projection partway with the simulated score.

    Elasticity is the percent change in the stat per percent change in team
    points. Passing yards move about a quarter as much as the score; team
    touchdown totals move about one for one.
    """
    factor = 1.0 + float(elasticity) * (np.asarray(script, dtype=float) - 1.0)
    return float(base) * np.clip(factor, 0.0, 4.0)


def _stat_elasticity(params: dict, position: str, stat: str, default: float = 0.3) -> float:
    table = (params.get("stat_elasticity") or {}).get(norm_pos(position), {})
    if stat in table:
        return float(table[stat])
    fallback = (params.get("stat_elasticity") or {}).get("WR", {})
    if stat in fallback:
        return float(fallback[stat])
    return default


def _stat_cv(params: dict, position: str, stat: str) -> float:
    table = (params.get("stat_cv") or {}).get(norm_pos(position), {})
    if stat in table:
        return float(table[stat])
    flex = (params.get("stat_cv") or {}).get("WR", {})
    if stat in flex:
        return float(flex[stat])
    return float(DEFAULT_CV.get(stat, 0.5))


def sample_gamma(mean: np.ndarray, cv: float, rng: np.random.Generator) -> np.ndarray:
    mean = np.asarray(mean, dtype=float)
    out = np.zeros(mean.shape, dtype=float)
    mask = mean > 1e-6
    if not np.any(mask):
        return out
    cv = float(np.clip(cv, 0.05, 1.25))
    shape = 1.0 / cv**2
    out[mask] = rng.gamma(shape, mean[mask] * cv**2)
    return out


def sample_count(mean: np.ndarray, var_ratio: float, rng: np.random.Generator) -> np.ndarray:
    mean = np.maximum(np.asarray(mean, dtype=float), 0.0)
    out = np.zeros(mean.shape, dtype=int)
    active = mean > 1e-4
    if not np.any(active):
        return out
    values = mean[active]
    ratio = max(float(var_ratio), 1.0)
    if ratio <= 1.05:
        out[active] = rng.poisson(values)
        return out
    prob = 1.0 / ratio
    n_success = np.maximum(values * prob / (1.0 - prob), 1e-3)
    out[active] = rng.negative_binomial(n_success, prob)
    return out


def sample_td_pool(mean: np.ndarray, resid_var: float, rng: np.random.Generator) -> np.ndarray:
    """Rounded normal around the script-scaled mean.

    resid_var is the variance left after team points are known, so a 5-touchdown
    day only shows up when the simulated game is already a shootout.
    """
    mean = np.maximum(np.asarray(mean, dtype=float), 0.0)
    sd = float(np.sqrt(max(resid_var, 0.16)))
    draw = rng.normal(mean, sd)
    return np.clip(np.rint(draw), 0, 12).astype(int)


def allocate(totals: np.ndarray, weights: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    weights = np.asarray(weights, dtype=float)
    weights = np.clip(weights, 0, None)
    out = np.zeros((len(totals), len(weights)), dtype=int)
    total_weight = float(weights.sum())
    if total_weight <= 0 or len(weights) == 0:
        return out
    probs = weights / total_weight
    for index, count in enumerate(totals):
        if count <= 0:
            continue
        out[index] = rng.multinomial(int(count), probs)
    return out


def _injury_rates(params: dict) -> tuple[dict, dict]:
    raw = params.get("injury")
    if not isinstance(raw, dict):
        return dict(INJURY_PARAMS["per_10000"]), dict(INJURY_PARAMS["snaps"])
    per = raw.get("per_10000", INJURY_PARAMS["per_10000"])
    snaps = raw.get("snaps", INJURY_PARAMS["snaps"])
    return dict(per or {}), dict(snaps or {})


def _snap_count(player: dict, params: dict) -> int | None:
    """Offensive snaps that still carry an injury hazard.

    Pregame, that is a starter's full game. Live, snaps shrink with the share
    of the projection still ahead of him, and points already scored stay put.
    """
    per, snaps = _injury_rates(params)
    pos = norm_pos(player.get("position"))
    if pos not in per or pos not in snaps:
        return None
    if float(per.get(pos) or 0) <= 0:
        return None
    base = int(snaps[pos])
    if base <= 0:
        return None
    if player.get("mode") == "live":
        projected = float(player.get("projected") or 0)
        already = float(player.get("points") or 0)
        remaining = max(0.0, projected - already)
        if projected > 0:
            base = max(1, int(round(base * min(1.0, remaining / projected))))
    return base


def play_fraction(
    player: dict,
    n: int,
    rng: np.random.Generator,
    params: dict,
) -> np.ndarray:
    """Share of the healthy score he gets to play.

    Each snap is an independent chance of a time-loss injury. Exit on snap k
    of N keeps k/N. Surviving every snap keeps the whole draw.
    """
    snaps = _snap_count(player, params)
    if snaps is None:
        return np.ones(n, dtype=float)
    per, _ = _injury_rates(params)
    p = float(per[norm_pos(player.get("position"))]) / 10000.0
    if p <= 0 or p >= 1:
        return np.ones(n, dtype=float)
    exit_play = rng.geometric(p, size=n)
    return np.minimum(1.0, exit_play / snaps)


def center(samples: np.ndarray, target: float) -> np.ndarray:
    samples = np.asarray(samples, dtype=float)
    if len(samples) == 0:
        return samples
    return samples + (float(target) - float(samples.mean()))


def bucket_points(allowed: np.ndarray, buckets: list[tuple[int, int, float]]) -> np.ndarray:
    allowed = np.asarray(allowed, dtype=float)
    out = np.zeros(len(allowed), dtype=float)
    for lo, hi, points in buckets:
        mask = (allowed >= lo) & (allowed <= hi)
        out[mask] = points
    return out


def _marginal(target: float, position: str, scoring: Scoring, params: dict, n: int, rng: np.random.Generator) -> np.ndarray:
    if target <= 0:
        return np.zeros(n, dtype=float)
    cv = _points_cv(params, position, scoring)
    return sample_gamma(np.full(n, target), cv, rng)


def _draw_games(lines: dict[str, dict], params: dict, n: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
    """Final scores by ESPN abbreviation. `spread` is the home margin."""
    drawn: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    sd_m = float(params["sd_margin"])
    sd_t = float(params["sd_total"])
    corr = float(np.clip(params.get("corr_margin_total") or 0.0, -0.95, 0.95))
    ordered = sorted(lines.values(), key=lambda info: not info.get("is_home"))
    for info in ordered:
        key = info.get("game_key")
        if not key or key in drawn or not info.get("implied"):
            continue
        z1 = rng.standard_normal(n)
        z2 = corr * z1 + np.sqrt(1.0 - corr**2) * rng.standard_normal(n)
        margin = float(info["spread"]) + sd_m * z1
        total = np.maximum(0.0, float(info["total"]) + sd_t * z2)
        drawn[key] = (
            np.maximum(0.0, (total + margin) / 2.0),
            np.maximum(0.0, (total - margin) / 2.0),
        )
    team_points: dict[str, np.ndarray] = {}
    for team, info in lines.items():
        pair = drawn.get(info.get("game_key") or "")
        if pair is None:
            continue
        team_points[team] = pair[0] if info.get("is_home") else pair[1]
    return team_points


def _script(team_points: np.ndarray | None, implied: float | None, n: int) -> np.ndarray:
    if team_points is None or not implied:
        return np.ones(n, dtype=float)
    return np.clip(team_points / max(float(implied), 0.5), 0.0, 4.0)


def _fg_shares(breakdown: dict, params: dict) -> tuple[float, float, float]:
    under = float(breakdown.get("madeFieldGoalsFromUnder40") or 0)
    mid = float(breakdown.get("madeFieldGoalsFrom40To49") or 0)
    long = float(breakdown.get("madeFieldGoalsFrom50Plus") or 0) + float(
        breakdown.get("madeFieldGoalsFrom60Plus") or 0
    )
    total = under + mid + long
    if total <= 1e-6:
        share = params.get("fg_distance_share") or {}
        return (
            float(share.get("under40", 0.55)),
            float(share.get("from40To49", 0.30)),
            float(share.get("from50Plus", 0.15)),
        )
    return under / total, mid / total, long / total


def _kicker_points(
    sim_points: np.ndarray,
    pass_tds: np.ndarray,
    rush_tds: np.ndarray,
    breakdown: dict,
    scoring: Scoring,
    params: dict,
    rng: np.random.Generator,
) -> np.ndarray:
    n = len(sim_points)
    off_tds = np.asarray(pass_tds, dtype=int) + np.asarray(rush_tds, dtype=int)
    xp_rate = float(params.get("xp_rate") or 0.94)
    xp = rng.binomial(np.maximum(off_tds, 0), xp_rate)
    fg_mean = np.maximum(0.0, (sim_points - 6.0 * off_tds - xp) / 3.0)
    under_s, mid_s, long_s = _fg_shares(breakdown, params)
    arrays = {
        "madeExtraPoints": xp,
        "madeFieldGoalsFromUnder40": rng.poisson(fg_mean * under_s),
        "madeFieldGoalsFrom40To49": rng.poisson(fg_mean * mid_s),
        "madeFieldGoalsFrom50Plus": rng.poisson(fg_mean * long_s),
    }
    return scoring.score(arrays, n)


def _dst_points(
    opp_points: np.ndarray,
    breakdown: dict,
    scoring: Scoring,
    params: dict,
    rng: np.random.Generator,
) -> np.ndarray:
    n = len(opp_points)
    arrays: dict[str, np.ndarray] = {}
    ratios = params.get("count_var_ratio") or {}
    for name in DST_COUNTS:
        mean = float(breakdown.get(name) or 0)
        if mean <= 0 and scoring.linear.get(name, 0) == 0:
            continue
        arrays[name] = sample_count(np.full(n, max(mean, 0.0)), ratios.get(name, 1.15), rng)
    total = scoring.score(arrays, n)
    total = total + bucket_points(opp_points, scoring.pa_buckets)
    return total


def _skill_points(
    player: dict,
    script: np.ndarray,
    pass_tds: np.ndarray,
    rush_tds: np.ndarray,
    rec_tds: np.ndarray,
    scoring: Scoring,
    params: dict,
    rng: np.random.Generator,
) -> np.ndarray:
    n = len(script)
    breakdown = player.get("breakdown") or {}
    position = player.get("position")
    arrays: dict[str, np.ndarray] = {
        "passingTouchdowns": pass_tds,
        "rushingTouchdowns": rush_tds,
        "receivingTouchdowns": rec_tds,
    }
    for stat in SKILL_YARDS:
        base = float(breakdown.get(stat) or 0)
        mean = scale_mean(base, script, _stat_elasticity(params, position, stat))
        arrays[stat] = sample_gamma(mean, _stat_cv(params, position, stat), rng)
    ratios = params.get("count_var_ratio") or {}
    for stat in SKILL_COUNTS:
        base = float(breakdown.get(stat) or 0)
        if base <= 0 and not scoring.linear.get(stat):
            continue
        if stat == "receivingReceptions":
            arrays[stat] = sample_gamma(
                scale_mean(base, script, _stat_elasticity(params, position, stat)),
                _stat_cv(params, position, stat),
                rng,
            )
            continue
        if stat == "rushingAttempts":
            elas = _stat_elasticity(params, position, "rushingYards", 0.3)
            arrays[stat] = sample_count(scale_mean(base, script, elas), ratios.get(stat, 1.1), rng)
            continue
        if stat == "receivingTargets":
            elas = _stat_elasticity(params, position, "receivingReceptions", 0.3)
            arrays[stat] = sample_count(scale_mean(base, script, elas), ratios.get(stat, 1.1), rng)
            continue
        arrays[stat] = sample_count(np.full(n, base), ratios.get(stat, 1.1), rng)
    return scoring.score(arrays, n)


def _positive_weights(players: list[dict], stat: str) -> np.ndarray:
    return np.array(
        [max(0.0, float((p.get("breakdown") or {}).get(stat) or 0)) for p in players],
        dtype=float,
    )


def _allocate_team(
    players: list[dict],
    script: np.ndarray,
    implied: float | None,
    sim_points: np.ndarray | None,
    params: dict,
    rng: np.random.Generator,
) -> dict[int, dict[str, np.ndarray]]:
    """Shared touchdown draws for one NFL team. Keys are indexes into `players`."""
    n = len(script)
    pregame = [p for p in players if p.get("mode") == "pregame"]
    assigned: dict[int, dict[str, np.ndarray]] = {
        p["index"]: {
            "pass": np.zeros(n, dtype=int),
            "rush": np.zeros(n, dtype=int),
            "rec": np.zeros(n, dtype=int),
        }
        for p in players
    }
    if not pregame:
        return assigned

    qb_w = _positive_weights(pregame, "passingTouchdowns")
    rec_w = _positive_weights(pregame, "receivingTouchdowns")
    rush_w = _positive_weights(pregame, "rushingTouchdowns")
    rates = params.get("rates_per_point") or {}
    pass_base = float(qb_w.sum())
    if pass_base <= 1e-6 and implied:
        pass_base = float(rates.get("passing_tds") or 0.066) * float(implied)
    rec_sum = float(rec_w.sum())
    other_rec = max(0.0, pass_base - rec_sum)
    rec_probs = np.concatenate([rec_w, [other_rec]]) if other_rec > 0 else rec_w

    rush_sum = float(rush_w.sum())
    rush_base = rush_sum
    if implied:
        historical_rush = float(rates.get("rushing_tds") or 0.04) * float(implied)
        rush_base = max(rush_sum, historical_rush)
    other_rush = max(0.0, rush_base - rush_sum)
    rush_probs = np.concatenate([rush_w, [other_rush]]) if other_rush > 0 else rush_w

    td_var = params.get("td_resid_var") or {}
    td_elas = params.get("td_elasticity") or {}
    pass_mean = scale_mean(pass_base, script, float(td_elas.get("passing") or 1.0))
    rush_mean = scale_mean(rush_base, script, float(td_elas.get("rushing") or 1.0))
    pass_totals = sample_td_pool(pass_mean, float(td_var.get("passing") or 0.8), rng)
    rush_totals = sample_td_pool(rush_mean, float(td_var.get("rushing") or 0.6), rng)

    if pass_base > 1e-6 and qb_w.sum() > 0:
        qb_draw = allocate(pass_totals, qb_w, rng)
        for slot, player in enumerate(pregame):
            assigned[player["index"]]["pass"] = qb_draw[:, slot]
    if len(rec_probs) and float(np.sum(rec_probs)) > 0 and rec_w.sum() > 0:
        rec_draw = allocate(pass_totals, rec_probs, rng)
        for slot, player in enumerate(pregame):
            assigned[player["index"]]["rec"] = rec_draw[:, slot]
    if len(rush_probs) and float(np.sum(rush_probs)) > 0 and rush_w.sum() > 0:
        rush_draw = allocate(rush_totals, rush_probs, rng)
        for slot, player in enumerate(pregame):
            assigned[player["index"]]["rush"] = rush_draw[:, slot]

    # Stash team totals on a side channel for the kicker via the first player.
    assigned["pass_totals"] = pass_totals  # type: ignore[index]
    assigned["rush_totals"] = rush_totals  # type: ignore[index]
    assigned["sim_points"] = sim_points  # type: ignore[index]
    return assigned


def simulate_team_scores(
    *,
    current_scores: dict[str, float],
    players: list[dict],
    scoring: Scoring,
    params: dict,
    lines: dict[str, dict] | None,
    n: int,
    rng: np.random.Generator | None = None,
) -> dict[str, np.ndarray]:
    """Return length-n samples for each fantasy team, including points already scored."""
    rng = rng or np.random.default_rng()
    lines = lines or {}
    n = int(n)
    samples = {
        team: np.full(n, float(current), dtype=float)
        for team, current in current_scores.items()
    }
    indexed = []
    for index, player in enumerate(players):
        row = dict(player)
        row["index"] = index
        row["breakdown"] = row.get("breakdown") or {}
        indexed.append(row)

    game_points = _draw_games(lines, params, n, rng)
    by_team: dict[str, list[dict]] = {}
    for player in indexed:
        by_team.setdefault(player.get("nfl_team") or "", []).append(player)

    allocations: dict[str, dict] = {}
    for nfl_team, group in by_team.items():
        info = lines.get(nfl_team) or {}
        sim_points = game_points.get(nfl_team)
        script = _script(sim_points, info.get("implied"), n)
        allocations[nfl_team] = _allocate_team(
            group, script, info.get("implied"), sim_points, params, rng
        )

    for player in indexed:
        if not player.get("starter"):
            continue
        if player.get("mode") == "done":
            continue
        fantasy_team = player.get("fantasy_team")
        if fantasy_team not in samples:
            continue
        projected = float(player.get("projected") or 0)
        already = float(player.get("points") or 0)
        target = projected if player.get("mode") == "pregame" else max(0.0, projected - already)
        if target <= 0 and player.get("mode") != "pregame":
            continue
        if player.get("mode") == "pregame" and projected <= 0:
            continue

        nfl_team = player.get("nfl_team") or ""
        info = lines.get(nfl_team) or {}
        sim_points = game_points.get(nfl_team)
        script = _script(sim_points, info.get("implied"), n)
        alloc = allocations.get(nfl_team) or {}
        kind = role_for(player.get("position"))
        use_game = player.get("mode") == "pregame" and bool(player.get("breakdown"))

        if kind == "DST" and use_game:
            opp = info.get("opponent")
            opp_points = game_points.get(opp) if opp else None
            if opp_points is None:
                raw = _marginal(target, player.get("position"), scoring, params, n, rng)
            else:
                raw = _dst_points(opp_points, player["breakdown"], scoring, params, rng)
        elif kind == "K" and use_game and alloc.get("sim_points") is not None:
            raw = _kicker_points(
                alloc["sim_points"],
                alloc.get("pass_totals", np.zeros(n, dtype=int)),
                alloc.get("rush_totals", np.zeros(n, dtype=int)),
                player["breakdown"],
                scoring,
                params,
                rng,
            )
        elif kind == "SKILL" and use_game:
            cell = alloc.get(player["index"]) or {}
            raw = _skill_points(
                player,
                script,
                cell.get("pass", np.zeros(n, dtype=int)),
                cell.get("rush", np.zeros(n, dtype=int)),
                cell.get("rec", np.zeros(n, dtype=int)),
                scoring,
                params,
                rng,
            )
            if float(raw.mean()) < 0.35 * target and target > 2:
                raw = _marginal(target, player.get("position"), scoring, params, n, rng)
        else:
            raw = _marginal(target, player.get("position"), scoring, params, n, rng)

        # Center the healthy game onto the projection, then shorten it if he
        # leaves. A second center would lift the early exits back up.
        healthy = center(raw, target)
        samples[fantasy_team] = samples[fantasy_team] + healthy * play_fraction(
            player, n, rng, params
        )
    return samples
