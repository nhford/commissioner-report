#!/usr/bin/env python3
"""Monte Carlo median standings. Inserts a dated pull into Supabase."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import gamma

sys.path.insert(0, str(Path(__file__).resolve().parent))
from espn_client import get_league
from logo_utils import scrape_league_logos
from revalidate import ping_revalidate
from score_model import (
    load_params,
    load_week_lines,
    scoring_from_league,
    simulate_team_scores,
)
from supabase_client import get_service_client

SIM_N = int(os.environ.get("SIM_N") or "1000")

# M1, the original Median Watch formula: each remaining starter is an
# independent gamma with CV 2/3, then the sum is pulled in by 3%.
M1_CV = 2 / 3
M1_TAMPER = 0.97


def rand_gamma_sum(projs, n=1000, factor=M1_CV, tamper=M1_TAMPER):
    projs = np.asarray(projs, dtype=float)
    projs = projs[projs > 0]
    if len(projs) == 0:
        return np.zeros(n)
    std_dev = projs * factor
    shape = (projs / std_dev) ** 2
    scale = (std_dev**2) / projs
    samples = gamma.rvs(a=shape[:, None], scale=scale[:, None], size=(len(projs), n))
    return samples.sum(axis=0) * tamper


def _m1_remaining(player) -> float:
    slot = getattr(player, "lineupSlot", "") or ""
    if slot in ("BE", "IR"):
        return 0.0
    try:
        game_played = float(getattr(player, "game_played", 100) or 0)
    except (TypeError, ValueError):
        game_played = 100.0
    if game_played >= 100:
        return 0.0
    remaining = float(getattr(player, "projected_points", 0) or 0) - float(
        getattr(player, "points", 0) or 0
    )
    return remaining if remaining > 0 else 0.0


def _breakdown(player) -> dict:
    raw = getattr(player, "projected_breakdown", None)
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, value in raw.items():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number:
            out[str(key)] = number
    return out


def _mode(player) -> str:
    if getattr(player, "on_bye_week", False):
        return "done"
    slot = getattr(player, "lineupSlot", "") or ""
    if slot == "IR":
        return "done"
    try:
        game_played = float(getattr(player, "game_played", 100) or 0)
    except (TypeError, ValueError):
        game_played = 100.0
    if game_played >= 100:
        return "done"
    points = float(getattr(player, "points", 0) or 0)
    game_date = getattr(player, "game_date", None)
    if points > 0 or (game_date is not None and datetime.now() >= game_date):
        return "live"
    return "pregame"


def _player_input(player, fantasy_team: str) -> dict | None:
    slot = getattr(player, "lineupSlot", "") or ""
    if slot == "IR":
        return None
    nfl_team = getattr(player, "proTeam", "") or ""
    if nfl_team in ("", "None"):
        nfl_team = ""
    return {
        "fantasy_team": fantasy_team,
        "nfl_team": nfl_team,
        "position": getattr(player, "position", None) or slot,
        "starter": slot not in ("BE", "IR"),
        "mode": _mode(player),
        "projected": float(getattr(player, "projected_points", 0) or 0),
        "points": float(getattr(player, "points", 0) or 0),
        "breakdown": _breakdown(player),
    }


def _box_team(team, score, proj, lineup) -> tuple[str, dict] | None:
    name = getattr(team, "team_name", None)
    if not name:
        return None
    return str(name), {
        "score": score,
        "proj": proj,
        "lineup": lineup,
    }


def get_lineups(league, week=None):
    lineups = {}
    for box in league.box_scores(week=week):
        for side in (
            _box_team(box.home_team, box.home_score, box.home_projected, box.home_lineup),
            _box_team(box.away_team, box.away_score, box.away_projected, box.away_lineup),
        ):
            if side is not None:
                lineups[side[0]] = side[1]
    return lineups


def get_team_sample_scores(league, n=1000, week=None):
    week = int(week or league.current_week)
    lineups = get_lineups(league, week=week)
    params = load_params()
    scoring = scoring_from_league(league)
    try:
        lines = load_week_lines(int(league.year), week)
    except Exception as exc:
        print(f"Vegas lines unavailable ({exc}); touchdown pools will not use a game script")
        lines = {}
    current = {}
    players = []
    for team, obj in lineups.items():
        current[team] = float(obj["score"] or 0)
        for player in obj["lineup"]:
            row = _player_input(player, team)
            if row is not None:
                players.append(row)
    scores = simulate_team_scores(
        current_scores=current,
        players=players,
        scoring=scoring,
        params=params,
        lines=lines,
        n=n,
    )
    for team, obj in lineups.items():
        obj["sample_m2"] = scores.get(team, np.full(n, current[team]))
        remaining = [_m1_remaining(player) for player in obj["lineup"]]
        obj["sample_m1"] = rand_gamma_sum(remaining, n) + current[team]
    print(
        f"Median models M1+M2: n={n} vegas_teams={len(lines)} "
        f"players={len(players)}"
    )
    return lineups


def column_ranks(arr, one_indexed=True, descending=True):
    sort_arr = -arr if descending else arr
    order = np.argsort(sort_arr, axis=0)
    ranks = np.empty_like(order, dtype=float)
    ranks[order, np.arange(sort_arr.shape[1])] = np.arange(sort_arr.shape[0])[:, None]
    if one_indexed:
        ranks += 1
    return ranks


def _model_rates(samples: np.ndarray, cutoff: int, n: int) -> tuple[np.ndarray, np.ndarray]:
    ranks = column_ranks(samples)
    medians = np.sum(ranks <= cutoff, axis=1) / n
    payouts = np.sum(ranks == 1, axis=1) / n
    return medians, payouts


def get_median_summary(league, n=SIM_N, week=None):
    median_cutoff = len(league.teams) // 2
    sample_scores_dict = get_team_sample_scores(league, n, week)
    owners = list(sample_scores_dict.keys())
    current_scores = [team["score"] for team in sample_scores_dict.values()]
    current_projs = [team["proj"] for team in sample_scores_dict.values()]
    m1 = np.vstack([team["sample_m1"] for team in sample_scores_dict.values()])
    m2 = np.vstack([team["sample_m2"] for team in sample_scores_dict.values()])
    median_m1, payout_m1 = _model_rates(m1, median_cutoff, n)
    median_m2, payout_m2 = _model_rates(m2, median_cutoff, n)
    df = pd.DataFrame(
        {
            "team": owners,
            "current": current_scores,
            "projection": current_projs,
            "median": median_m2,
            "payout": payout_m2,
            "median_m1": median_m1,
            "payout_m1": payout_m1,
            "median_m2": median_m2,
            "payout_m2": payout_m2,
        }
    )
    df = df.sort_values(
        by=["current", "projection"], ascending=[False, False]
    ).reset_index(drop=True)
    df.index = df.index + 1
    return df.reset_index(names=["rank"])


def write_pull(client, league, df: pd.DataFrame, logo_paths: dict[str, str]) -> None:
    pulled_at = datetime.now(timezone.utc).isoformat()
    pull = (
        client.table("median_pulls")
        .insert(
            {
                "pulled_at": pulled_at,
                "season": league.year,
                "week": league.current_week,
            }
        )
        .execute()
        .data[0]
    )
    rows = []
    for rec in df.to_dict(orient="records"):
        rows.append(
            {
                "pull_id": pull["id"],
                "team": rec["team"],
                "rank": int(rec["rank"]),
                "current": float(rec["current"]),
                "projection": float(rec["projection"]),
                "median": float(rec["median"]),
                "payout": float(rec["payout"]),
                "median_m1": float(rec["median_m1"]),
                "payout_m1": float(rec["payout_m1"]),
                "median_m2": float(rec["median_m2"]),
                "payout_m2": float(rec["payout_m2"]),
                "logo_path": logo_paths.get(rec["team"]),
            }
        )
    client.table("median_standings").insert(rows).execute()
    client.table("reports").upsert(
        {
            "id": "median-monday",
            "last_updated": pulled_at,
            "season": league.year,
            "current_week": league.current_week,
        }
    ).execute()
    print(f"Inserted median pull {pull['id']} ({len(rows)} teams)")


def main() -> None:
    league = get_league()
    df = get_median_summary(league)
    client = get_service_client()
    logo_paths, _rows = scrape_league_logos(client, league)
    write_pull(client, league, df, logo_paths)
    ping_revalidate()


if __name__ == "__main__":
    main()
