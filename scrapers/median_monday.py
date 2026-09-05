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
from supabase_client import get_service_client

SIM_N = int(os.environ.get("SIM_N") or "1000")

LINEUP_ORDERING = {
    "QB": 0,
    "RB": 1,
    "WR": 2,
    "TE": 3,
    "RB/WR/TE": 4,
}


def rand_gamma_sum(projs, n=1000, factor=2 / 3, tamper=0.97):
    projs = np.asarray(projs, dtype=float)
    if len(projs) == 0:
        return np.zeros(n)

    mean = projs
    std_dev = projs * factor
    shape = (mean / std_dev) ** 2
    scale = (std_dev**2) / mean
    samples = gamma.rvs(a=shape[:, None], scale=scale[:, None], size=(len(projs), n))
    return samples.sum(axis=0) * tamper


def get_starters(lineup, ordering=LINEUP_ORDERING):
    starters = [
        player
        for player in lineup
        if player.lineupSlot not in ("IR", "BE")
    ]
    return sorted(starters, key=lambda player: ordering.get(player.lineupSlot, 99))


def get_lineups(league, week=None):
    lineups = {}
    for box in league.box_scores(week=week):
        lineups[box.home_team.team_name] = {
            "score": box.home_score,
            "proj": box.home_projected,
            "lineup": box.home_lineup,
        }
        lineups[box.away_team.team_name] = {
            "score": box.away_score,
            "proj": box.away_projected,
            "lineup": box.away_lineup,
        }
    return lineups


def get_lineup_mass(score: float, lineup: list):
    starters = get_starters(lineup)
    masses = np.array(
        [
            player.projected_points - player.points
            for player in starters
            if player.game_played < 100 and player.projected_points - player.points > 0
        ]
    )
    return np.insert(masses, 0, score)


def get_team_sample_scores(league, n=1000, week=None):
    lineups = get_lineups(league, week=week)
    for team, obj in lineups.items():
        masses = get_lineup_mass(obj["score"], obj["lineup"])
        projs = rand_gamma_sum(masses[1:], n)
        obj["sample_scores"] = projs + obj["score"]
    return lineups


def column_ranks(arr, one_indexed=True, descending=True):
    sort_arr = -arr if descending else arr
    order = np.argsort(sort_arr, axis=0)
    ranks = np.empty_like(order, dtype=float)
    ranks[order, np.arange(sort_arr.shape[1])] = np.arange(sort_arr.shape[0])[:, None]
    if one_indexed:
        ranks += 1
    return ranks


def get_median_summary(league, n=SIM_N, week=None):
    median_cutoff = len(league.teams) // 2
    sample_scores_dict = get_team_sample_scores(league, n, week)
    owners = list(sample_scores_dict.keys())
    sample_scores_2d_arr = np.vstack(
        [team["sample_scores"] for team in sample_scores_dict.values()]
    )
    sample_ranks = column_ranks(sample_scores_2d_arr)
    current_scores = [team["score"] for team in sample_scores_dict.values()]
    current_projs = [team["proj"] for team in sample_scores_dict.values()]
    medians = np.sum(sample_ranks <= median_cutoff, axis=1) / n
    payouts = np.sum(sample_ranks == 1, axis=1) / n
    df = pd.DataFrame(
        {
            "team": owners,
            "current": current_scores,
            "projection": current_projs,
            "median": medians,
            "payout": payouts,
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
