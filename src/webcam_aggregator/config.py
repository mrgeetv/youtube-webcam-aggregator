from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    youtube_api_key: str
    public_base_url: str
    catalogue_interval_hours: int


def load(env: dict[str, str] | None = None) -> Config:
    e = env if env is not None else dict(os.environ)
    key = e.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise ValueError("YOUTUBE_API_KEY is required")
    try:
        interval = max(1, int(e.get("CATALOGUE_INTERVAL_HOURS", "6")))
    except ValueError:
        interval = 6
    return Config(
        youtube_api_key=key,
        public_base_url=e.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        catalogue_interval_hours=interval,
    )
