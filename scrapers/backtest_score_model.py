#!/usr/bin/env python3
"""Check the score model against the Dean case and recent quarterback weeks.

A quarterback projected in the mid-teens who needs 55 points should be worth
cents on the $75 top-scorer prize. The old gamma (CV 2/3) priced that outcome
near $0.44. This script also checks that a quarterback and receiver in the
same game move together, and that the opposing defense moves the other way.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibrate_score_model import load_schedules, load_weekly
from score_model import default_scoring, load_params, sanitize_breakdown, simulate_team_scores

PAYOUT = 75.0
DEAN_N = 20000
HISTORY_N = 400
HISTORY_ROWS = 250


def _line(team: str, opponent: str, spread: float, total: float, home: str) -> dict[str, dict]:
    home_implied = max(0.5, (total + spread) / 2)
    away_implied = max(0.5, (total - spread) / 2)
    key = f"{opponent}@{team}" if home == team else f"{team}@{opponent}"
    if home == team:
        away, home_team = opponent, team
    else:
        away, home_team = team, opponent
        key = f"{away}@{home_team}"
    return {
        home_team: {
            "opponent": away,
            "implied": home_implied,
            "is_home": True,
            "spread": spread,
            "total": total,
            "game_key": key,
        },
        away: {
            "opponent": home_team,
            "implied": away_implied,
            "is_home": False,
            "spread": spread,
            "total": total,
            "game_key": key,
        },
    }


def _rate(samples: np.ndarray, threshold: float) -> float:
    return float(np.mean(samples >= threshold))


def dean_case(params: dict, scoring) -> dict:
    breakdown = {
        "passingYards": 230.0,
        "passingTouchdowns": 1.35,
        "passingInterceptions": 0.7,
        "rushingYards": 18.0,
        "rushingTouchdowns": 0.15,
    }
    lines = _line("NE", "NYJ", spread=3.0, total=44.0, home="NE")
    scores = simulate_team_scores(
        current_scores={"Dean": 80.0},
        players=[
            {
                "fantasy_team": "Dean",
                "nfl_team": "NE",
                "position": "QB",
                "starter": True,
                "mode": "pregame",
                "projected": 16.0,
                "points": 0.0,
                "breakdown": breakdown,
            }
        ],
        scoring=scoring,
        params=params,
        lines=lines,
        n=DEAN_N,
        rng=np.random.default_rng(7),
    )
    added = scores["Dean"] - 80.0
    return {
        "mean": float(added.mean()),
        "p30": _rate(added, 30),
        "p40": _rate(added, 40),
        "p55": _rate(added, 55),
        "equity": _rate(added, 55) * PAYOUT,
    }


def _without_injury(params: dict) -> dict:
    quiet = dict(params)
    quiet["injury"] = {"per_10000": {}, "snaps": {}}
    return quiet


def shared_touchdowns(params: dict) -> None:
    scoring = default_scoring()
    scoring.linear = {
        "passingTouchdowns": 4.0,
        "receivingTouchdowns": 6.0,
    }
    lines = _line("NE", "NYJ", spread=0.0, total=44.0, home="NE")
    scores = simulate_team_scores(
        current_scores={"A": 0.0, "B": 0.0},
        players=[
            {
                "fantasy_team": "A",
                "nfl_team": "NE",
                "position": "QB",
                "starter": True,
                "mode": "pregame",
                "projected": 6.0,
                "points": 0.0,
                "breakdown": {"passingTouchdowns": 1.5},
            },
            {
                "fantasy_team": "B",
                "nfl_team": "NE",
                "position": "WR",
                "starter": True,
                "mode": "pregame",
                "projected": 9.0,
                "points": 0.0,
                "breakdown": {"receivingTouchdowns": 1.5},
            },
        ],
        scoring=scoring,
        params=_without_injury(params),
        lines=lines,
        n=4000,
        rng=np.random.default_rng(11),
    )
    qb = scores["A"]
    wr = scores["B"]
    qb_td = (qb - qb.mean()) / 4.0
    wr_td = (wr - wr.mean()) / 6.0
    gap = float(np.max(np.abs(qb_td - wr_td)))
    if gap > 1e-6:
        raise SystemExit(f"Shared touchdowns diverged by {gap}")


def absurd_yards(params: dict, scoring) -> dict:
    """A 7,000-yard breakdown is scaled back to one game before it is simulated."""
    raw = {
        "rushingAttempts": 16.49,
        "rushingYards": 7188.46,
        "rushingYardsPerAttempt": 4.36,
        "rushingTouchdowns": 0.57,
        "receivingYards": 2273.23,
        "receivingReceptions": 2.82,
        "receivingYardsPerReception": 8.06,
        "receivingTouchdowns": 0.11,
        "210": 0.01,
    }
    fixed = sanitize_breakdown(raw)
    if sanitize_breakdown({"receivingYards": 81.0, "210": 1})["receivingYards"] != 81.0:
        raise SystemExit("A normal yardage line was rewritten")
    if "rushingYards" in sanitize_breakdown({"rushingYards": 9000.0}):
        raise SystemExit("Unrepairable thousand-yard line was kept")
    lines = _line("CLE", "NYJ", spread=2.5, total=39.5, home="NYJ")
    scores = simulate_team_scores(
        current_scores={"RB": 0.0},
        players=[
            {
                "fantasy_team": "RB",
                "nfl_team": "NYJ",
                "position": "RB",
                "starter": True,
                "mode": "pregame",
                "projected": 16.4,
                "points": 0.0,
                "breakdown": raw,
            }
        ],
        scoring=scoring,
        params=params,
        lines=lines,
        n=4000,
        rng=np.random.default_rng(5),
    )
    draws = scores["RB"]
    return {
        "rush_yards": float(fixed["rushingYards"]),
        "rec_yards": float(fixed["receivingYards"]),
        "mean": float(draws.mean()),
        "p99": float(np.quantile(draws, 0.99)),
    }


def injury_exit(params: dict, scoring) -> dict:
    """A full-time receiver keeps most of his projection, with a thin early-exit tail."""
    lines = _line("ATL", "NO", spread=1.5, total=47.5, home="NO")
    scores = simulate_team_scores(
        current_scores={"WR": 0.0},
        players=[
            {
                "fantasy_team": "WR",
                "nfl_team": "ATL",
                "position": "WR",
                "starter": True,
                "mode": "pregame",
                "projected": 16.7,
                "points": 0.0,
                "breakdown": {
                    "receivingReceptions": 6.0,
                    "receivingYards": 81.0,
                    "receivingTouchdowns": 0.4,
                },
            }
        ],
        scoring=scoring,
        params=params,
        lines=lines,
        n=20000,
        rng=np.random.default_rng(23),
    )
    draws = scores["WR"]
    return {
        "mean": float(draws.mean()),
        "p_near_zero": float(np.mean(draws <= 1.0)),
    }


def game_correlation(params: dict, scoring) -> dict[str, float]:
    lines = _line("NE", "NYJ", spread=3.0, total=45.0, home="NE")
    scores = simulate_team_scores(
        current_scores={"QB": 0.0, "WR": 0.0, "DST": 0.0},
        players=[
            {
                "fantasy_team": "QB",
                "nfl_team": "NE",
                "position": "QB",
                "starter": True,
                "mode": "pregame",
                "projected": 18.0,
                "points": 0.0,
                "breakdown": {
                    "passingYards": 250.0,
                    "passingTouchdowns": 1.6,
                    "passingInterceptions": 0.7,
                    "rushingYards": 20.0,
                    "rushingTouchdowns": 0.2,
                },
            },
            {
                "fantasy_team": "WR",
                "nfl_team": "NE",
                "position": "WR",
                "starter": True,
                "mode": "pregame",
                "projected": 14.0,
                "points": 0.0,
                "breakdown": {
                    "receivingReceptions": 6.0,
                    "receivingYards": 75.0,
                    "receivingTouchdowns": 0.5,
                },
            },
            {
                "fantasy_team": "DST",
                "nfl_team": "NYJ",
                "position": "D/ST",
                "starter": True,
                "mode": "pregame",
                "projected": 7.0,
                "points": 0.0,
                "breakdown": {"defensiveSacks": 2.4, "defensiveInterceptions": 0.6},
            },
        ],
        scoring=scoring,
        params=params,
        lines=lines,
        n=4000,
        rng=np.random.default_rng(19),
    )
    return {
        "qb_wr": float(np.corrcoef(scores["QB"], scores["WR"])[0, 1]),
        "qb_dst": float(np.corrcoef(scores["QB"], scores["DST"])[0, 1]),
    }


def _fantasy_frame(weekly: pd.DataFrame, schedules: pd.DataFrame) -> pd.DataFrame:
    qb = weekly[(weekly["position"] == "QB") & (weekly["attempts"] >= 10)].copy()
    qb = qb.sort_values(["player_id", "season", "week"])
    group = qb.groupby(["player_id", "season"], sort=False)
    for col in (
        "passing_yards",
        "passing_tds",
        "passing_interceptions",
        "rushing_yards",
        "rushing_tds",
    ):
        qb[f"proj_{col}"] = group[col].transform(lambda series: series.shift(1).expanding().mean())
    qb["prior_games"] = group.cumcount()
    home = schedules[["season", "week", "home_team", "spread_line", "total_line"]].rename(
        columns={"home_team": "team"}
    )
    home["is_home"] = True
    away = schedules[["season", "week", "away_team", "spread_line", "total_line"]].rename(
        columns={"away_team": "team"}
    )
    away["is_home"] = False
    slate = pd.concat([home, away], ignore_index=True)
    qb = qb.merge(slate, on=["season", "week", "team"], how="inner")
    qb = qb.dropna(subset=["proj_passing_yards", "spread_line", "total_line"])
    qb = qb[qb["prior_games"] >= 3]
    return qb


def _actual_points(row: pd.Series) -> float:
    return (
        float(row["passing_yards"]) * 0.04
        + float(row["passing_tds"]) * 4
        + float(row["passing_interceptions"]) * -2
        + float(row["rushing_yards"]) * 0.1
        + float(row["rushing_tds"]) * 6
    )


def _proj_points(row: pd.Series) -> float:
    return (
        float(row["proj_passing_yards"]) * 0.04
        + float(row["proj_passing_tds"]) * 4
        + float(row["proj_passing_interceptions"]) * -2
        + float(row["proj_rushing_yards"]) * 0.1
        + float(row["proj_rushing_tds"]) * 6
    )


def historical_qbs(params: dict, scoring) -> dict:
    weekly = load_weekly()
    schedules = load_schedules()
    frame = _fantasy_frame(weekly, schedules)
    frame["actual"] = frame.apply(_actual_points, axis=1)
    frame["proj"] = frame.apply(_proj_points, axis=1)
    mid = frame[(frame["proj"] >= 14) & (frame["proj"] <= 18)].copy()
    if mid.empty:
        raise SystemExit("No mid-teen quarterback weeks in the nflverse sample.")
    actual_p55 = float((mid["actual"] >= 55).mean())
    actual_p40 = float((mid["actual"] >= 40).mean())
    actual_p20 = float((mid["actual"] >= mid["proj"] + 20).mean())

    sample = mid.sample(n=min(HISTORY_ROWS, len(mid)), random_state=3)
    model_p55 = []
    model_p40 = []
    model_p20 = []
    for index, row in enumerate(sample.itertuples(index=False)):
        team = str(row.team)
        spread = float(row.spread_line)
        total = float(row.total_line)
        opponent = f"OPP{index}"
        if bool(row.is_home):
            lines = _line(team, opponent, spread=spread, total=total, home=team)
        else:
            lines = _line(opponent, team, spread=spread, total=total, home=opponent)
        proj = float(row.proj)
        scores = simulate_team_scores(
            current_scores={"T": 0.0},
            players=[
                {
                    "fantasy_team": "T",
                    "nfl_team": team,
                    "position": "QB",
                    "starter": True,
                    "mode": "pregame",
                    "projected": proj,
                    "points": 0.0,
                    "breakdown": {
                        "passingYards": float(row.proj_passing_yards),
                        "passingTouchdowns": float(row.proj_passing_tds),
                        "passingInterceptions": max(0.0, float(row.proj_passing_interceptions)),
                        "rushingYards": max(0.0, float(row.proj_rushing_yards)),
                        "rushingTouchdowns": max(0.0, float(row.proj_rushing_tds)),
                    },
                }
            ],
            scoring=scoring,
            params=params,
            lines=lines,
            n=HISTORY_N,
            rng=np.random.default_rng(1000 + index),
        )
        draws = scores["T"]
        model_p55.append(_rate(draws, 55))
        model_p40.append(_rate(draws, 40))
        model_p20.append(_rate(draws, proj + 20))
    return {
        "n": int(len(mid)),
        "sampled": int(len(sample)),
        "actual_p55": actual_p55,
        "actual_p40": actual_p40,
        "actual_p20": actual_p20,
        "model_p55": float(np.mean(model_p55)),
        "model_p40": float(np.mean(model_p40)),
        "model_p20": float(np.mean(model_p20)),
    }


def main() -> None:
    params = load_params()
    scoring = default_scoring()
    dean = dean_case(params, scoring)
    print(
        "Dean QB projected 16, needs 55: "
        f"mean={dean['mean']:.2f} P(>30)={dean['p30']:.4f} "
        f"P(>40)={dean['p40']:.4f} P(>=55)={dean['p55']:.5f} "
        f"equity=${dean['equity']:.3f}"
    )
    shared_touchdowns(params)
    print("Shared touchdown pool: quarterback and receiver receive the same count.")
    yards = absurd_yards(params, scoring)
    print(
        "Absurd yardage repaired: "
        f"rush={yards['rush_yards']:.1f} rec={yards['rec_yards']:.1f} "
        f"mean={yards['mean']:.2f} p99={yards['p99']:.1f}"
    )
    injury = injury_exit(params, scoring)
    print(
        "WR injury exit, projected 16.7: "
        f"mean={injury['mean']:.2f} P(<=1)={injury['p_near_zero']:.4f}"
    )
    corr = game_correlation(params, scoring)
    print(
        f"Same-game correlation: QB-WR={corr['qb_wr']:.3f} QB-opposing DST={corr['qb_dst']:.3f}"
    )
    history = historical_qbs(params, scoring)
    print(
        "Mid-teen QB weeks "
        f"(n={history['n']}, sim sample={history['sampled']}): "
        f"actual P(>=55)={history['actual_p55']:.5f} model={history['model_p55']:.5f}; "
        f"actual P(>=40)={history['actual_p40']:.4f} model={history['model_p40']:.4f}; "
        f"actual P(>proj+20)={history['actual_p20']:.4f} model={history['model_p20']:.4f}"
    )

    failures = []
    if not 14.5 <= dean["mean"] <= 17.5:
        failures.append(f"Dean mean {dean['mean']:.2f} is off the projection")
    if dean["p55"] >= 0.002:
        failures.append(f"Dean P(>=55)={dean['p55']:.5f} is still too fat")
    if dean["equity"] >= 0.15:
        failures.append(f"Dean equity ${dean['equity']:.3f} is not cents")
    if not 70 <= yards["rush_yards"] <= 75 or not 22 <= yards["rec_yards"] <= 24:
        failures.append(
            f"Yard repair rush={yards['rush_yards']:.1f} rec={yards['rec_yards']:.1f}"
        )
    if yards["p99"] > 80:
        failures.append(f"Repaired RB p99={yards['p99']:.1f} is still a thousand-yard tail")
    if not 15.2 <= injury["mean"] <= 16.5:
        failures.append(f"Injury mean {injury['mean']:.2f} is off the 3% discount")
    if not 0.0005 <= injury["p_near_zero"] <= 0.02:
        failures.append(f"Injury P(<=1)={injury['p_near_zero']:.4f} is not a thin early exit")
    if corr["qb_wr"] < 0.15:
        failures.append(f"QB-WR correlation {corr['qb_wr']:.3f} is too weak")
    if corr["qb_dst"] > -0.15:
        failures.append(f"QB-DST correlation {corr['qb_dst']:.3f} is not negative enough")
    ceiling = max(0.003, history["actual_p55"] * 8)
    if history["model_p55"] > ceiling:
        failures.append(
            f"Model P(>=55)={history['model_p55']:.5f} vs actual {history['actual_p55']:.5f}"
        )
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        raise SystemExit(1)
    print("Score model checks passed.")


if __name__ == "__main__":
    main()
