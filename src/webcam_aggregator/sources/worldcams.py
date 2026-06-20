from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import replace

from ..fetch import FetcherProtocol, thread_map
from ..models import Candidate
from .base import extract_candidates, with_location

_MAX_LIST_PAGES = 80
_LINKS = re.compile(r'class="cam-promo__title"[^>]*>\s*<a href="([^"]+)"')
_TITLE = re.compile(r"<h1[^>]*>([^<]{1,120})</h1>")
_CATEGORY = re.compile(r'Category:\s*(?:&nbsp;)?<a href="/([^/]+)/">([^<]+)</a>')


class WorldcamsSource:
    name: str = "worldcams"
    _fetch: FetcherProtocol

    def __init__(self, fetch: FetcherProtocol) -> None:
        self._fetch = fetch

    def _camera_urls(self) -> list[str]:
        # List pages stay sequential with early-stop (politest, only ~tens of them);
        # the bulk — the per-camera detail pages — is fetched concurrently in discover.
        urls: list[str] = []
        for page in range(1, _MAX_LIST_PAGES + 1):
            html = self._fetch.get(f"https://worldcams.tv/list/?page={page}")
            links = list(dict.fromkeys(_LINKS.findall(html))) if html else []
            if not links:
                break
            urls.extend("https://worldcams.tv" + link for link in links)
        return list(dict.fromkeys(urls))

    def discover(self) -> Iterator[Candidate]:
        urls = self._camera_urls()
        for url, html in zip(urls, thread_map(self._fetch.get, urls)):
            if not html:
                continue
            tm = _TITLE.search(html)
            cm = _CATEGORY.search(html)
            title = with_location(tm.group(1).strip() if tm else "", url)
            category = cm.group(2).strip() if cm else None
            for c in extract_candidates(html, page_url=url, source="worldcams"):
                yield replace(c, title=title, category=category)
