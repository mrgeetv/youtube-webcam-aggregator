from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_SEARCH_QUERY = (
    "cam|webcam|live|beach|wildlife|aquarium|space|harbor|park|mountain|coast|city"
    "|traffic|nature|zoo -gameplay -playing -subscriber -donation -follower -facecam"
    " -reaction -chatting -gaming -fortnite -troll -asmr -twitch"
)


@dataclass(frozen=True)
class Config:
    youtube_api_key: str
    public_base_url: str
    catalogue_interval_hours: int
    search_query: str
    log_level: str
    port: int


def _int_env(env: dict[str, str], key: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(env.get(key, str(default))))
    except ValueError:
        return default


def load(env: dict[str, str] | None = None) -> Config:
    e = env if env is not None else dict(os.environ)
    key = e.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise ValueError("YOUTUBE_API_KEY is required")
    return Config(
        youtube_api_key=key,
        public_base_url=e.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        catalogue_interval_hours=_int_env(e, "CATALOGUE_INTERVAL_HOURS", 6, 1),
        search_query=e.get("SEARCH_QUERY", "").strip() or _DEFAULT_SEARCH_QUERY,
        log_level=e.get("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        port=_int_env(e, "PORT", 8000, 1),
    )
