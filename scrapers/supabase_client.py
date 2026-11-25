"""Service-role Supabase client for scrapers. Never import this from the Next.js app."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DEFAULT_URL = "https://jdfdpbgqiigkjatzudle.supabase.co"


def supabase_url() -> str:
    return (
        os.environ.get("SUPABASE_URL")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
        or DEFAULT_URL
    )


def get_service_client() -> Client:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise SystemExit(
            "Missing SUPABASE_SERVICE_ROLE_KEY. "
            "Set it in .env (local) or GitHub Actions secrets."
        )
    return create_client(supabase_url(), key)


def fetch_all(client: Client, table: str, columns: str, orders: list[str]) -> list[dict]:
    rows: list[dict] = []
    start = 0
    size = 1000
    while True:
        query = client.table(table).select(columns)
        for column in orders:
            query = query.order(column)
        batch = query.range(start, start + size - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < size:
            return rows
        start += size


def delete_season(client: Client, table: str, season: int) -> None:
    previous = None
    for _ in range(40):
        probe = (
            client.table(table)
            .select("season", count="exact")
            .eq("season", season)
            .limit(1)
            .execute()
        )
        left = probe.count or 0
        if left == 0:
            return
        if previous is not None and left >= previous:
            raise SystemExit(f"Could not clear {table} for {season} ({left} rows left)")
        previous = left
        client.table(table).delete().eq("season", season).execute()


def insert_chunks(client: Client, table: str, rows: list[dict]) -> None:
    for index in range(0, len(rows), 200):
        client.table(table).insert(rows[index : index + 200]).execute()


def upsert_chunks(client: Client, table: str, rows: list[dict], conflict: str) -> None:
    for index in range(0, len(rows), 200):
        client.table(table).upsert(rows[index : index + 200], on_conflict=conflict).execute()


def upload_logo(client: Client, path: str, data: bytes, content_type: str) -> None:
    bucket = client.storage.from_("logos")
    options = {
        "content-type": content_type,
        "upsert": "true",
        "cache-control": "2592000",
    }
    try:
        bucket.upload(path, data, options)
    except Exception:
        bucket.update(path, data, {"content-type": content_type})
