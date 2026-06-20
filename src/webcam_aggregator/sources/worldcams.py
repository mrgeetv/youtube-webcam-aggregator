from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import replace

from ..fetch import FetcherProtocol
from ..models import Candidate
from .base import extract_candidates

_LINKS = re.compile(r'class="cam-promo__title"[^>]*>\s*<a href="([^"]+)"')
_TITLE = re.compile(r"<h1[^>]*>([^<]{1,120})</h1>")
_CATEGORY = re.compile(r'Category:\s*(?:&nbsp;)?<a href="/([^/]+)/">([^<]+)</a>')


class WorldcamsSource:
    name: str = "worldcams"
    _fetch: FetcherProtocol

    def __init__(self, fetch: FetcherProtocol) -> None:
        self._fetch = fetch

    def _camera_urls(self) -> Iterator[str]:
        page = 1
        while page <= 80:
            html = self._fetch.get(f"https://worldcams.tv/list/?page={page}")
            if not html:
                break
            links = list(dict.fromkeys(_LINKS.findall(html)))
            if not links:
                break
            for link in links:
                yield "https://worldcams.tv" + link
            page += 1

    def discover(self) -> Iterator[Candidate]:
        for url in self._camera_urls():
            html = self._fetch.get(url)
            if not html:
                continue
            tm = _TITLE.search(html)
            cm = _CATEGORY.search(html)
            title = tm.group(1).strip() if tm else ""
            category = cm.group(2).strip() if cm else None
            for c in extract_candidates(html, page_url=url, source="worldcams"):
                yield replace(c, title=title, category=category)
