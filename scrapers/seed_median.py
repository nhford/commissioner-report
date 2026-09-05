#!/usr/bin/env python3
"""Insert the committed Median Monday JSON as the first dated pull if none exist."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from supabase_client import ROOT, get_service_client

STANDINGS = ROOT / "data" / "median-monday" / "latest.json"
META = ROOT / "data" / "median-monday" / "metadata.json"
# Week 17 2025, last update Friday Jan 30 10:21pm ET
SEED_PULLED_AT = "2026-01-30T22:21:00-05:00"


def main() -> None:
    client = get_service_client()
    existing = client.table("median_pulls").select("id").limit(1).execute().data
    if existing:
        print("median_pulls already has rows; skipping seed")
        return
    standings = json.loads(STANDINGS.read_text(encoding="utf-8"))
    meta = json.loads(META.read_text(encoding="utf-8"))
    pull = (
        client.table("median_pulls")
        .insert(
            {
                "pulled_at": SEED_PULLED_AT,
                "season": meta["season"],
                "week": meta["current_week"],
            }
        )
        .execute()
        .data[0]
    )
    rows = [
        {
            "pull_id": pull["id"],
            "team": row["team"],
            "rank": row["rank"],
            "current": row["current"],
            "projection": row["projection"],
            "median": row["median"],
            "payout": row["payout"],
            "logo_path": None,
        }
        for row in standings
    ]
    client.table("median_standings").insert(rows).execute()
    client.table("reports").upsert(
        {
            "id": "median-monday",
            "last_updated": SEED_PULLED_AT,
            "season": meta["season"],
            "current_week": meta["current_week"],
        }
    ).execute()
    print(f"Seeded pull {pull['id']} with {len(rows)} teams")


if __name__ == "__main__":
    main()
