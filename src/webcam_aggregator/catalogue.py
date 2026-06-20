from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace

from .categories import map_category
from .dedup import dedupe
from .fetch import thread_map
from .models import Candidate, CatalogueEntry, stable_id
from .sources.base import Source

log = logging.getLogger("webcam-aggregator.catalogue")

DROP_THRESHOLD = 0.5
AGREE_TO_ACCEPT = 2
_NO_EXCLUDE: frozenset[str] = (
    frozenset()
)  # default arg (basedpyright: no call in default)


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
    )


def _apply_yt_category(c: Candidate, live: Mapping[str, str]) -> Candidate:
    # YouTube-source cams carry no category until here; fill it from the live lookup.
    # Scoped to youtube-api so a worldcams/cxtvlive yt-embed keeps its scraped
    # category; cross-source dedup priority resolves the rest.
    if c.source == "youtube-api" and c.predisc_key:
        cat = live.get(c.predisc_key[3:])
        if cat:
            return replace(c, category=cat)
    return c


def build_catalogue(
    sources: list[Source],
    *,
    is_alive: Callable[[Candidate], bool],
    youtube_live: Callable[[Iterable[str]], Mapping[str, str]],
    history: dict[str, Hist],
    exclude_categories: frozenset[str] = _NO_EXCLUDE,
) -> list[CatalogueEntry]:
    # Per source: liveness-filter + per-source empty guard -> kept candidates.
    # Cross-source dedup runs ONCE at the end so the same cam from two sources collapses.
    kept_all: list[Candidate] = []
    for src in sources:
        crashed = False
        try:
            cands = list(src.discover())
        except Exception:
            log.exception("source %s discover() failed", src.name)
            cands = []
            crashed = True
        yt_ids = [
            c.predisc_key[3:]
            for c in cands
            if c.predisc_key and c.predisc_key.startswith("yt:")
        ]
        live: Mapping[str, str] = youtube_live(yt_ids) if yt_ids else {}

        def alive(c: Candidate, _live: Mapping[str, str] = live) -> bool:
            if c.predisc_key and c.predisc_key.startswith("yt:"):
                return c.predisc_key[3:] in _live
            return is_alive(c)

        kept = [
            _apply_yt_category(c, live)
            for c, ok in zip(cands, thread_map(alive, cands))
            if ok
        ]
        log.info("%s: %d kept / %d discovered", src.name, len(kept), len(cands))

        h = history.setdefault(src.name, Hist())
        if crashed and h.last_kept:
            # A crash is not a genuine "0 cams" result — reuse the last good set and
            # leave history untouched, so two consecutive crashes can't get accepted
            # as an empty set (which would wipe last_kept and disable the guard).
            log.warning(
                "%s discover crashed; reusing previous %d", src.name, len(h.last_kept)
            )
            kept_all.extend(h.last_kept)
            continue
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

    entries = [_to_entry(c) for c in dedupe(kept_all)]
    if exclude_categories:
        # exclude_categories is casefolded (config._csv_set) for case-insensitive match
        entries = [
            e for e in entries if e.category.casefold() not in exclude_categories
        ]
    return entries
