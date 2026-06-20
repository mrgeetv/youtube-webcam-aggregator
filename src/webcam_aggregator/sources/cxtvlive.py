from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import replace

from ..fetch import FetcherProtocol
from ..models import Candidate
from .base import extract_candidates

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
        for slug in self._slugs():
            url = "https://www.cxtvlive.com/live-camera/" + slug
            html = self._fetch.get(url)
            if not html:
                continue
            tm = _TITLE.search(html)
            cm = _CATEGORY.search(html)
            title = tm.group(1).strip() if tm else slug.replace("-", " ").title()
            category = cm.group(1).replace("-", " ").title() if cm else None
            for c in extract_candidates(html, page_url=url, source="cxtvlive"):
                yield replace(c, title=title, category=category)
