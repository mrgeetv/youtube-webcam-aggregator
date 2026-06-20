from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from .categories import map_category
from .dedup import dedupe
from .models import Candidate, CatalogueEntry, stable_id
from .sources.base import Source

log = logging.getLogger("webcam-aggregator.catalogue")

DROP_THRESHOLD = 0.5
AGREE_TO_ACCEPT = 2


@dataclass
class Hist:
    last_count: int | None = None
    shrink_streak: int = 0
    last_kept: list[Candidate] = field(default_factory=list)


def _to_entry(c: Candidate) -> CatalogueEntry:
    return CatalogueEntry(
        id=stable_id(c),
        title=c.title or "(untitled)",
        category=map_category(c.category),
        source=c.source,
        source_page_url=c.source_page_url,
        target_url=c.target_url,
        resolver_hint=c.hint,
    )


def build_catalogue(
    sources: list[Source],
    *,
    is_alive: Callable[[Candidate], bool],
    youtube_live: Callable[[Iterable[str]], set[str]],
    history: dict[str, Hist],
) -> list[CatalogueEntry]:
    # Per source: liveness-filter + per-source empty guard -> kept candidates.
    # Cross-source dedup runs ONCE at the end so the same cam from two sources collapses.
    kept_all: list[Candidate] = []
    for src in sources:
        try:
            cands = list(src.discover())
        except Exception:
            log.exception("source %s discover() failed", src.name)
            cands = []
        yt_ids = [
            c.predisc_key[3:]
            for c in cands
            if c.predisc_key and c.predisc_key.startswith("yt:")
        ]
        live = youtube_live(yt_ids) if yt_ids else set()

        def alive(c: Candidate, _live: set[str] = live) -> bool:
            if c.predisc_key and c.predisc_key.startswith("yt:"):
                return c.predisc_key[3:] in _live
            return is_alive(c)

        kept = [c for c in cands if alive(c)]
        log.info("%s: %d kept / %d discovered", src.name, len(kept), len(cands))

        h = history.setdefault(src.name, Hist())
        collapsed = (
            h.last_count is not None
            and h.last_count > 0
            and len(kept) < h.last_count * (1 - DROP_THRESHOLD)
        )
        if collapsed:
            h.shrink_streak += 1
            if h.shrink_streak < AGREE_TO_ACCEPT:
                log.warning(
                    "%s collapsed to %d (< %.0f%% of last %d); keeping previous %d",
                    src.name,
                    len(kept),
                    DROP_THRESHOLD * 100,
                    h.last_count,
                    len(h.last_kept),
                )
                kept_all.extend(h.last_kept)  # guard: reuse this source's last good set
                continue
        h.shrink_streak = 0
        h.last_count = len(kept)
        h.last_kept = kept
        kept_all.extend(kept)

    return [_to_entry(c) for c in dedupe(kept_all)]
