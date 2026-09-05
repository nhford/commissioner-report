"""Shared ESPN league factory. Cookies come from env, never from source."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from espn_api.football import League

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DEFAULT_LEAGUE_ID = "619156725"
DEFAULT_SEASON_ID = 2026
FIRST_SEASON = 2022


def require_cookies() -> tuple[str, str]:
    espn_s2 = os.environ.get("ESPN_S2")
    swid = os.environ.get("ESPN_SWID")
    if not espn_s2 or not swid:
        raise SystemExit(
            "Missing ESPN_S2 and/or ESPN_SWID. "
            "Copy .env.example to .env (local) or set GitHub Actions secrets."
        )
    return espn_s2, swid


def league_id() -> str:
    return os.environ.get("ESPN_LEAGUE_ID") or DEFAULT_LEAGUE_ID


def season_id(override: int | None = None) -> int:
    if override is not None:
        return override
    return int(os.environ.get("ESPN_SEASON_ID") or DEFAULT_SEASON_ID)


def get_league(year: int | None = None) -> League:
    espn_s2, swid = require_cookies()
    return League(
        league_id=league_id(),
        year=season_id(year),
        espn_s2=espn_s2,
        swid=swid,
    )
