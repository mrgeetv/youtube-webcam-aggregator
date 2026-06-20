from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import replace

from ..fetch import FetcherProtocol, thread_map
from ..models import Candidate
from .base import extract_candidates, with_location

_SLUG = re.compile(r"live-camera/([^<\s]+)")
_TITLE = re.compile(r"<h1[^>]*>([^<]{1,120})</h1>")
_CATEGORY = re.compile(r"cameras/category/([a-z0-9-]+)")


class CxtvliveSource:
    name: str = "cxtvlive"
    _fetch: FetcherProtocol

    def __init__(self, fetch: FetcherProtocol) -> None:
        self._fetch = fetch

    def _slugs(self) -> list[str]:
        sm = self._fetch.get("https://www.cxtvlive.com/sitemap.xml") or ""
        return list(dict.fromkeys(_SLUG.findall(sm)))

    def discover(self) -> Iterator[Candidate]:
        slugs = self._slugs()
        urls = ["https://www.cxtvlive.com/live-camera/" + s for s in slugs]
        for slug, url, html in zip(slugs, urls, thread_map(self._fetch.get, urls)):
            if not html:
                continue
            tm = _TITLE.search(html)
            cm = _CATEGORY.search(html)
            title = with_location(
                tm.group(1).strip() if tm else slug.replace("-", " ").title(), url
            )
            category = cm.group(1).replace("-", " ").title() if cm else None
            for c in extract_candidates(html, page_url=url, source="cxtvlive"):
                yield replace(c, title=title, category=category)
