#!/usr/bin/env python3
"""Scrape ESPN fantasy team logos for every season and store them on Supabase.

Files go in the public `logos` bucket at fantasy/{season}/{team_id}.jpg (or .svg).
Rows go in `fantasy_logos` so the site can look them up by season, team, or owner.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from espn_client import FIRST_SEASON, get_league, season_id
from logo_utils import (
    logo_dest,
    owner_for,
    scrape_league_logos,
    upsert_catalog,
    write_catalog_json,
)
from supabase_client import get_service_client


def stored_paths(client, season: int) -> dict[int, str]:
    items = client.storage.from_("logos").list(f"fantasy/{season}") or []
    paths: dict[int, str] = {}
    for item in items:
        name = item.get("name") or ""
        stem, _, ext = name.partition(".")
        if stem.isdigit() and ext in {"jpg", "svg", "png"}:
            paths[int(stem)] = logo_dest(season, int(stem), ext)
    return paths


def catalog_from_storage(client, years: list[int]) -> list[dict]:
    rows: list[dict] = []
    for year in years:
        print(f"Season {year}")
        league = get_league(year)
        existing = stored_paths(client, year)
        for team in league.teams:
            dest = existing.get(team.team_id)
            print(f"  {team.team_id:2d} {team.team_name}: {dest or 'missing'}")
            rows.append(
                {
                    "season": year,
                    "team_id": team.team_id,
                    "owner": owner_for(year, team.team_id),
                    "team_name": team.team_name,
                    "logo_path": dest,
                    "source_url": getattr(team, "logo_url", "") or None,
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, help="Scrape a single season")
    parser.add_argument(
        "--catalog-only",
        action="store_true",
        help="Rebuild the catalog from files already in the logos bucket",
    )
    args = parser.parse_args()

    current = season_id()
    years = [args.year] if args.year else list(range(FIRST_SEASON, current + 1))
    client = get_service_client()
    if args.catalog_only:
        catalog = catalog_from_storage(client, years)
        upsert_catalog(client, catalog)
        write_catalog_json(client, catalog)
        print(f"Wrote catalog for {len(catalog)} teams")
        return

    uploaded = 0
    catalog: list[dict] = []
    for year in years:
        print(f"Season {year}")
        league = get_league(year)
        paths, rows = scrape_league_logos(client, league)
        uploaded += len(paths)
        catalog.extend(rows)
    write_catalog_json(client, catalog)
    print(f"Uploaded {uploaded} logos across {len(years)} season(s)")


if __name__ == "__main__":
    main()
