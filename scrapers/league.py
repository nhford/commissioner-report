"""League facts shared by the scrapers. data/league.json is the source."""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@cache
def load_league() -> dict:
    return json.loads((ROOT / "data" / "league.json").read_text(encoding="utf-8"))


def owners_by_year() -> dict:
    return load_league().get("owners_by_year") or {}


def first_season() -> int:
    years = [int(year) for year in owners_by_year()]
    return min(years) if years else 2022


def current_season() -> int:
    return int(load_league().get("current_season") or first_season())


def team_owner(season: int, team_id: int | None) -> str | None:
    """Raw owners_by_year value. None when the team id is absent."""
    if team_id is None:
        return None
    block = owners_by_year().get(str(int(season))) or {}
    name = block.get(str(int(team_id)))
    if not name:
        return None
    return str(name)


def owner_name(season: int, team_id: int | None) -> str:
    """Owner label stored on a roster row. Missing teams are Unknown. N/A stays N/A."""
    return team_owner(season, team_id) or "Unknown"


def owner_for(season: int, team_id: int | None) -> str | None:
    """Owner used for logos and catalogs. Vacant teams are skipped."""
    name = team_owner(season, team_id)
    if not name or name == "N/A":
        return None
    return name


def owner_for_team(season: int, team_id: int | None) -> str | None:
    name = owner_for(season, team_id)
    if not name or name == "Unknown":
        return None
    return name


def league_owner_names() -> list[str]:
    names: set[str] = set()
    for block in owners_by_year().values():
        for name in block.values():
            if name and name != "N/A":
                names.add(str(name))
    return sorted(names)


def owners_between(start: int, end: int) -> list[str]:
    names: set[str] = set()
    for year, block in owners_by_year().items():
        season = int(year)
        if season < start or season > end:
            continue
        for name in (block or {}).values():
            if name and name != "N/A":
                names.add(str(name))
    return sorted(names)


def week1_thursday(season: int) -> date | None:
    raw = (load_league().get("week1_thursday") or {}).get(str(int(season)))
    if not raw:
        return None
    return date.fromisoformat(str(raw))


def opening_thursday(season: int) -> date:
    """Thursday of NFL week 1. Stored dates win. Later seasons use the Labor Day rule."""
    stored = week1_thursday(season)
    if stored:
        return stored
    september_first = date(int(season), 9, 1)
    labor_day = september_first + timedelta(days=(0 - september_first.weekday()) % 7)
    return labor_day + timedelta(days=3)
