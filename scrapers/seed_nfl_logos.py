#!/usr/bin/env python3
"""Upload existing Hot Seat NFL PNGs into the public logos bucket."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from supabase_client import get_service_client, upload_logo

NFL_DIR = Path(
    "/Users/noahford/Desktop/projects/websites/hot-seat/hot-seat-frontend/public/images/nfl"
)


def dest_name(filename: str) -> str:
    stem = Path(filename).stem
    if stem.endswith("-2024"):
        stem = stem[: -len("-2024")]
    return f"nfl/{stem}.png"


def main() -> None:
    if not NFL_DIR.is_dir():
        raise SystemExit(f"NFL logo directory not found: {NFL_DIR}")
    client = get_service_client()
    files = sorted(NFL_DIR.glob("*.png"))
    if not files:
        raise SystemExit(f"No PNGs in {NFL_DIR}")
    for path in files:
        dest = dest_name(path.name)
        data = path.read_bytes()
        upload_logo(client, dest, data, "image/png")
        print(f"uploaded {dest}")
    print(f"Uploaded {len(files)} NFL logos")


if __name__ == "__main__":
    main()
