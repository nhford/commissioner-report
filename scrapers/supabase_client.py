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


def upload_logo(client: Client, path: str, data: bytes, content_type: str) -> None:
    bucket = client.storage.from_("logos")
    options = {"content-type": content_type, "upsert": "true"}
    try:
        bucket.upload(path, data, options)
    except Exception:
        bucket.update(path, data, {"content-type": content_type})
