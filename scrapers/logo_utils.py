"""Shared ESPN fantasy-logo download, normalize, and storage helpers."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

from espn_client import ROOT, require_cookies
from supabase_client import upload_logo

OWNERS_BY_YEAR = json.loads(
    (ROOT / "data" / "league.json").read_text(encoding="utf-8")
).get("owners_by_year") or {}

LOCAL_FALLBACK_DIR = ROOT / "data" / "logo-fallbacks"
DESKTOP_LOGO_HISTORY = Path(
    "/Users/noahford/Desktop/fantasy-football/logo-history"
)
DESKTOP_FALLBACKS = {
    (2024, 1): DESKTOP_LOGO_HISTORY / "2024-v2-josh-allen-enthusiasts.png",
    (2025, 1): DESKTOP_LOGO_HISTORY / "2025-turnover-on-downs.jpg",
    (2026, 1): DESKTOP_LOGO_HISTORY / "2026-joshing-around.png",
}

MAX_EDGE = 512
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://fantasy.espn.com/",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}


def owner_for(year: int, team_id: int) -> str | None:
    name = OWNERS_BY_YEAR.get(str(year), {}).get(str(team_id))
    if not name or name == "N/A":
        return None
    return name


def logo_dest(season: int, team_id: int, ext: str) -> str:
    return f"fantasy/{season}/{team_id}.{ext}"


def local_fallback(season: int, team_id: int) -> Path | None:
    matches = sorted(LOCAL_FALLBACK_DIR.glob(f"{season}-{team_id}.*"))
    if matches:
        return matches[0]
    desktop = DESKTOP_FALLBACKS.get((season, team_id))
    if desktop and desktop.is_file():
        return desktop
    return None


def cookies() -> dict[str, str]:
    espn_s2, swid = require_cookies()
    return {"swid": swid, "espn_s2": espn_s2}


def fetch_remote(url: str) -> tuple[bytes, str] | None:
    if not url:
        return None
    try:
        response = requests.get(
            url, cookies=cookies(), headers=REQUEST_HEADERS, timeout=20
        )
        if response.status_code != 200:
            return None
        content_type = (response.headers.get("content-type") or "").split(";")[0]
        content_type = content_type.strip().lower()
        if "json" in content_type or "html" in content_type:
            return None
        if "svg" in content_type or url.lower().split("?")[0].endswith(".svg"):
            return response.content, "svg"
        return response.content, "raster"
    except Exception as exc:
        print(f"  download failed: {exc}")
        return None


def normalize_raster(data: bytes) -> bytes:
    img = Image.open(BytesIO(data))
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    else:
        img = img.convert("RGB")
    if max(img.size) > MAX_EDGE:
        img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def bytes_from_path(path: Path) -> tuple[bytes, str]:
    data = path.read_bytes()
    if path.suffix.lower() == ".svg":
        return data, "svg"
    return normalize_raster(data), "jpg"


def load_team_logo(team, season: int) -> tuple[bytes, str, str | None] | None:
    """Return (bytes, ext, source_url) or None."""
    url = getattr(team, "logo_url", "") or None
    if url:
        fetched = fetch_remote(url)
        if fetched:
            data, kind = fetched
            if kind == "svg":
                return data, "svg", url
            try:
                return normalize_raster(data), "jpg", url
            except Exception as exc:
                print(f"  cannot decode {team.team_name}: {exc}")
    fallback = local_fallback(season, team.team_id)
    if fallback:
        data, ext = bytes_from_path(fallback)
        return data, ext, url
    return None


def upsert_catalog(client, rows: list[dict]) -> bool:
    if not rows:
        return True
    try:
        client.table("fantasy_logos").upsert(rows).execute()
        return True
    except Exception as exc:
        print(f"  fantasy_logos upsert failed ({exc}). Apply the SQL migration.")
        return False


def write_catalog_json(client, rows: list[dict]) -> None:
    payload = json.dumps(rows, indent=2).encode("utf-8")
    upload_logo(client, "fantasy/catalog.json", payload, "application/json")


def scrape_league_logos(client, league) -> tuple[dict[str, str], list[dict]]:
    """Upload every team logo for a season. Returns (name -> path, catalog rows)."""
    paths: dict[str, str] = {}
    rows: list[dict] = []
    for team in league.teams:
        loaded = load_team_logo(team, league.year)
        dest = None
        source_url = getattr(team, "logo_url", "") or None
        if loaded:
            data, ext, source_url = loaded
            dest = logo_dest(league.year, team.team_id, ext)
            content_type = "image/svg+xml" if ext == "svg" else "image/jpeg"
            upload_logo(client, dest, data, content_type)
            paths[team.team_name] = dest
        rows.append(
            {
                "season": league.year,
                "team_id": team.team_id,
                "owner": owner_for(league.year, team.team_id),
                "team_name": team.team_name,
                "logo_path": dest,
                "source_url": source_url,
            }
        )
        status = dest or "missing"
        print(f"  {team.team_id:2d} {team.team_name}: {status}")
    upsert_catalog(client, rows)
    return paths, rows
