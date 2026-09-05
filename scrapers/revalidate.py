"""Ping the Next.js revalidate route after a successful scrape."""

from __future__ import annotations

import os

import requests


def ping_revalidate() -> None:
    url = os.environ.get("VERCEL_REVALIDATE_URL")
    secret = os.environ.get("REVALIDATE_SECRET")
    if not url or not secret:
        print("Skipping revalidate (VERCEL_REVALIDATE_URL or REVALIDATE_SECRET unset)")
        return
    response = requests.post(
        url,
        headers={"x-revalidate-secret": secret},
        timeout=20,
    )
    response.raise_for_status()
    print(f"Revalidated via {url}")
