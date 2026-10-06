#!/usr/bin/env python3
"""Fit Median Watch score-model parameters from nflverse and write them to disk.

The nightly sim reads data/score_model_params.json. It does not download
history. Re-run this script when you want to refresh the fit.

Game-script noise (margin and total residuals) is unconditional, because the
sim draws the final score first. Each stat then moves with that score only as
much as history says it does, and the leftover noise is what remains after
that relationship.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from score_model import INJURY_PARAMS

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "score_model_params.json"
CACHE = ROOT / "data" / ".cache"

SCHEDULE_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
)
WEEKLY_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_week_{year}.csv"
)

SEASONS = range(2018, 2026)
MIN_GAMES = 5

WEEKLY_COLS = [
    "player_id",
    "position",
    "season",
    "week",
    "season_type",
    "team",
    "attempts",
    "passing_yards",
    "passing_tds",
    "passing_interceptions",
    "carries",
    "rushing_yards",
    "rushing_tds",
    "receptions",
    "targets",
    "receiving_yards",
    "receiving_tds",
    "def_sacks",
    "def_interceptions",
    "def_fumbles",
    "fg_made",
    "fg_made_0_19",
    "fg_made_20_29",
    "fg_made_30_39",
    "fg_made_40_49",
    "fg_made_50_59",
    "fg_made_60_",
    "pat_made",
    "pat_att",
    "fantasy_points",
    "fantasy_points_ppr",
]


def download(url: str, name: str) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "commissioner-report"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = resp.read()
    path.write_bytes(data)
    return data


def load_schedules() -> pd.DataFrame:
    raw = download(SCHEDULE_URL, "games.csv")
    df = pd.read_csv(io.BytesIO(raw))
    df = df[df["game_type"] == "REG"].copy()
    df = df[df["season"].between(SEASONS.start, SEASONS.stop - 1)]
    return df


def load_weekly() -> pd.DataFrame:
    frames = []
    for year in SEASONS:
        try:
            raw = download(WEEKLY_URL.format(year=year), f"stats_player_week_{year}.csv")
        except urllib.error.HTTPError as exc:
            print(f"skip {year}: {exc}")
            continue
        header = pd.read_csv(io.BytesIO(raw), nrows=0).columns
        cols = [col for col in WEEKLY_COLS if col in header]
        frame = pd.read_csv(io.BytesIO(raw), usecols=cols)
        frames.append(frame)
        print(f"weekly {year}: {len(frame)} rows")
    if not frames:
        raise SystemExit("No weekly nflverse files downloaded.")
    df = pd.concat(frames, ignore_index=True)
    if "season_type" in df.columns:
        df = df[df["season_type"] == "REG"]
    df = df.dropna(subset=["team", "player_id"])
    numeric = [col for col in df.columns if col not in ("player_id", "position", "team", "season_type")]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["position"] = df["position"].fillna("").astype(str).str.upper()
    return df


def team_points(schedules: pd.DataFrame) -> pd.DataFrame:
    home = schedules[["season", "week", "home_team", "home_score"]].rename(
        columns={"home_team": "team", "home_score": "points"}
    )
    away = schedules[["season", "week", "away_team", "away_score"]].rename(
        columns={"away_team": "team", "away_score": "points"}
    )
    points = pd.concat([home, away], ignore_index=True)
    points["points"] = pd.to_numeric(points["points"], errors="coerce")
    return points.dropna(subset=["points"])


def game_residuals(schedules: pd.DataFrame) -> dict:
    done = schedules.dropna(subset=["spread_line", "total_line", "home_score", "away_score"])
    margin = (done["home_score"] - done["away_score"]) - done["spread_line"]
    total = (done["home_score"] + done["away_score"]) - done["total_line"]
    sd_m = float(margin.std(ddof=1))
    sd_t = float(total.std(ddof=1))
    corr = float(np.corrcoef(margin, total)[0, 1]) if len(done) > 2 else 0.0
    return {
        "n_games": int(len(done)),
        "sd_margin": round(sd_m, 4),
        "sd_total": round(sd_t, 4),
        "corr_margin_total": round(corr, 4),
    }


def _within_cv(frame: pd.DataFrame, col: str) -> float | None:
    if frame.empty or col not in frame.columns:
        return None
    grp = frame.groupby(["player_id", "season"])[col]
    mu = grp.transform("mean")
    n = grp.transform("size")
    mask = n >= MIN_GAMES
    if int(mask.sum()) < 50:
        return None
    values = frame.loc[mask, col].to_numpy(dtype=float)
    center = float(values.mean())
    if center <= 1e-6:
        return None
    resid = values - mu[mask].to_numpy(dtype=float)
    sd = float(np.sqrt(np.mean(resid**2)))
    return sd / center


def _elasticity_and_resid_cv(frame: pd.DataFrame, col: str) -> tuple[float | None, float | None]:
    """How many percent a stat moves per percent of team points, and the leftover CV.

    A one-for-one scale overstates receiving and passing yards: within a season
    they move about a quarter as much as the final score.
    """
    if frame.empty or col not in frame.columns or "points" not in frame.columns:
        return None, None
    elasticities = []
    resid_sq = []
    centers = []
    for (_, _), group in frame.groupby(["player_id", "season"]):
        if len(group) < MIN_GAMES:
            continue
        points = group["points"].to_numpy(dtype=float)
        values = group[col].to_numpy(dtype=float)
        if np.var(points, ddof=1) < 1 or float(values.mean()) <= 0.5:
            continue
        slope = np.cov(values, points, ddof=1)[0, 1] / np.var(points, ddof=1)
        elasticity = slope * float(points.mean()) / float(values.mean())
        pred = float(values.mean()) + slope * (points - float(points.mean()))
        elasticities.append(float(elasticity))
        resid_sq.append(float(np.mean(np.square(values - pred))))
        centers.append(float(values.mean()))
    if len(elasticities) < 30:
        return None, None
    center = float(np.mean(centers))
    if center <= 1e-6:
        return None, None
    cv = float(np.sqrt(np.mean(resid_sq)) / center)
    elasticity = float(np.median(elasticities))
    return elasticity, cv


def _team_td_fit(team_games: pd.DataFrame, col: str) -> tuple[float | None, float | None]:
    elasticities = []
    resid_sq = []
    for (_, _), group in team_games.groupby(["team", "season"]):
        if len(group) < MIN_GAMES:
            continue
        points = group["points"].to_numpy(dtype=float)
        values = group[col].to_numpy(dtype=float)
        if np.var(points, ddof=1) < 1 or float(values.mean()) <= 0.05:
            continue
        slope = np.cov(values, points, ddof=1)[0, 1] / np.var(points, ddof=1)
        elasticity = slope * float(points.mean()) / float(values.mean())
        pred = float(values.mean()) + slope * (points - float(points.mean()))
        elasticities.append(float(elasticity))
        resid_sq.append(float(np.mean(np.square(values - pred))))
    if len(elasticities) < 20:
        return None, None
    return float(np.median(elasticities)), float(np.mean(resid_sq))


def _var_ratio(frame: pd.DataFrame, col: str) -> float | None:
    cv = _within_cv(frame, col)
    if cv is None:
        return None
    # var/mean = (cv * mean)^2 / mean = cv^2 * mean. Recompute directly.
    grp = frame.groupby(["player_id", "season"])[col]
    mu = grp.transform("mean")
    n = grp.transform("size")
    mask = n >= MIN_GAMES
    values = frame.loc[mask, col].to_numpy(dtype=float)
    center = float(values.mean())
    if center <= 1e-6:
        return None
    resid = values - mu[mask].to_numpy(dtype=float)
    return float(np.mean(np.square(resid)) / center)


def fit(weekly: pd.DataFrame, schedules: pd.DataFrame) -> dict:
    points = team_points(schedules)
    merged = weekly.merge(points, on=["season", "week", "team"], how="inner")

    offense = (
        merged.groupby(["season", "week", "team"], as_index=False)
        .agg(
            passing_yards=("passing_yards", "sum"),
            rushing_yards=("rushing_yards", "sum"),
            passing_tds=("passing_tds", "sum"),
            rushing_tds=("rushing_tds", "sum"),
            points=("points", "first"),
        )
    )
    offense = offense[offense["points"] > 0]
    rates = {
        "passing_yards": float(offense["passing_yards"].sum() / offense["points"].sum()),
        "rushing_yards": float(offense["rushing_yards"].sum() / offense["points"].sum()),
        "passing_tds": float(offense["passing_tds"].sum() / offense["points"].sum()),
        "rushing_tds": float(offense["rushing_tds"].sum() / offense["points"].sum()),
    }
    td_sum = offense["passing_tds"].sum() + offense["rushing_tds"].sum()
    pass_td_share = float(offense["passing_tds"].sum() / td_sum) if td_sum else 0.62

    filters = {
        "QB": merged["attempts"] >= 10,
        "RB": (merged["position"] == "RB") & ((merged["carries"] + merged["targets"]) >= 3),
        "WR": (merged["position"] == "WR") & (merged["targets"] >= 2),
        "TE": (merged["position"] == "TE") & (merged["targets"] >= 2),
        "K": merged["position"].isin(["K", "PK"])
        & ((merged["fg_made"] + merged["pat_att"]) >= 1),
    }
    stat_cols = {
        "QB": ["passing_yards", "rushing_yards"],
        "RB": ["rushing_yards", "receiving_yards", "receptions"],
        "WR": ["receiving_yards", "receptions"],
        "TE": ["receiving_yards", "receptions"],
    }
    name_map = {
        "passing_yards": "passingYards",
        "rushing_yards": "rushingYards",
        "receiving_yards": "receivingYards",
        "receptions": "receivingReceptions",
    }
    stat_cv: dict[str, dict[str, float]] = {}
    stat_elasticity: dict[str, dict[str, float]] = {}
    for pos, cols in stat_cols.items():
        frame = merged.loc[filters[pos]]
        stat_cv[pos] = {}
        stat_elasticity[pos] = {}
        for col in cols:
            elasticity, cv = _elasticity_and_resid_cv(frame, col)
            mapped = name_map[col]
            if cv is not None and np.isfinite(cv):
                stat_cv[pos][mapped] = round(float(np.clip(cv, 0.05, 1.25)), 4)
            if elasticity is not None and np.isfinite(elasticity):
                stat_elasticity[pos][mapped] = round(float(np.clip(elasticity, 0.0, 1.5)), 4)

    points_cv = {}
    points_cv_ppr = {}
    for pos, mask in filters.items():
        frame = merged.loc[mask]
        cv = _within_cv(frame, "fantasy_points")
        cv_ppr = _within_cv(frame, "fantasy_points_ppr")
        if cv is not None:
            points_cv[pos] = round(float(np.clip(cv, 0.15, 1.1)), 4)
        if cv_ppr is not None:
            points_cv_ppr[pos] = round(float(np.clip(cv_ppr, 0.15, 1.1)), 4)
    points_cv.setdefault("D/ST", 0.55)
    points_cv.setdefault("FLEX", points_cv.get("WR", 0.65))
    points_cv_ppr.setdefault("D/ST", 0.55)
    points_cv_ppr.setdefault("FLEX", points_cv_ppr.get("WR", 0.6))

    ints = merged.loc[filters["QB"]]
    count_var_ratio = {}
    int_ratio = _var_ratio(ints, "passing_interceptions")
    if int_ratio is not None:
        count_var_ratio["passingInterceptions"] = round(max(1.0, float(int_ratio)), 4)

    if "def_sacks" in merged.columns:
        team_def = (
            merged.groupby(["season", "week", "team"], as_index=False)
            .agg(
                def_sacks=("def_sacks", "sum"),
                def_interceptions=("def_interceptions", "sum"),
                def_fumbles=("def_fumbles", "sum"),
            )
        )
        labeled = team_def.copy()
        labeled["player_id"] = labeled["team"]
        for src, dest in (
            ("def_sacks", "defensiveSacks"),
            ("def_interceptions", "defensiveInterceptions"),
            ("def_fumbles", "defensiveFumbles"),
        ):
            ratio = _var_ratio(labeled, src)
            if ratio is not None:
                count_var_ratio[dest] = round(max(1.0, float(ratio)), 4)

    fg_under = fg_mid = fg_long = 0.0
    for col in ("fg_made_0_19", "fg_made_20_29", "fg_made_30_39"):
        if col in merged.columns:
            fg_under += float(merged[col].sum())
    if "fg_made_40_49" in merged.columns:
        fg_mid = float(merged["fg_made_40_49"].sum())
    for col in ("fg_made_50_59", "fg_made_60_"):
        if col in merged.columns:
            fg_long += float(merged[col].sum())
    fg_total = fg_under + fg_mid + fg_long
    if fg_total <= 0:
        fg_share = {"under40": 0.55, "from40To49": 0.30, "from50Plus": 0.15}
    else:
        fg_share = {
            "under40": round(fg_under / fg_total, 4),
            "from40To49": round(fg_mid / fg_total, 4),
            "from50Plus": round(fg_long / fg_total, 4),
        }

    xp_rate = 0.94
    if "pat_att" in merged.columns and merged["pat_att"].sum() > 0:
        xp_rate = float(merged["pat_made"].sum() / merged["pat_att"].sum())

    pass_elas, pass_var = _team_td_fit(offense, "passing_tds")
    rush_elas, rush_var = _team_td_fit(offense, "rushing_tds")

    residuals = game_residuals(schedules)
    params = {
        "seasons": [SEASONS.start, SEASONS.stop - 1],
        "n_team_games": int(len(offense)),
        **residuals,
        "xp_rate": round(float(np.clip(xp_rate, 0.8, 0.99)), 4),
        "rates_per_point": {key: round(val, 4) for key, val in rates.items()},
        "pass_td_share": round(pass_td_share, 4),
        "td_elasticity": {
            "passing": round(float(np.clip(pass_elas or 1.0, 0.0, 1.5)), 4),
            "rushing": round(float(np.clip(rush_elas or 1.0, 0.0, 1.5)), 4),
        },
        "td_resid_var": {
            "passing": round(float(pass_var or 0.9), 4),
            "rushing": round(float(rush_var or 0.6), 4),
        },
        "stat_cv": stat_cv,
        "stat_elasticity": stat_elasticity,
        "position_points_cv": points_cv,
        "position_points_cv_ppr": points_cv_ppr,
        "count_var_ratio": count_var_ratio,
        "fg_distance_share": fg_share,
        "injury": INJURY_PARAMS,
    }
    return params


def main() -> None:
    print("Downloading nflverse schedules and weekly stats...")
    schedules = load_schedules()
    weekly = load_weekly()
    params = fit(weekly, schedules)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(params, indent=2) + "\n")
    print(f"Wrote {OUT_PATH}")
    print(json.dumps(params, indent=2))


if __name__ == "__main__":
    main()
