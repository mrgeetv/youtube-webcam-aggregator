from __future__ import annotations

import re
from typing import override
from urllib.parse import urljoin

from ..models import Candidate
from .base import HtmlScraperSource, predisc_key

_BASE = "https://www.camsecure.co.uk"
_INDEX = f"{_BASE}/Camsecure_Live_Demo_Index.html"

# Each cam detail page embeds its player in an iframe on the camsecure.co/.uk
# `httpswebcam` host; that player page is a video.js with a direct `/HLS/<name>.m3u8`
# source (open CDN — segments need no token/Referer; the player PAGE does, handled by
# `_REFERER_HOSTS`). The index also lists product/info pages (hosting, FAQ, world map …)
# that carry "webcam" in their name — `_SKIP` drops them, and a couple that embed a demo
# stream are caught by the iframe/HLS checks too.
_SKIP = (
    "hosting",
    "features",
    "faq",
    "drivers",
    "ipnetwork",
    "map",
    "camsecure_webcam",
)
_CAM_HREF = re.compile(r'href="(/[^"]+\.html)"', re.I)
_PLAYER_IFRAME = re.compile(
    r'<iframe[^>]+src="(https?://camsecure\.[a-z.]+/httpswebcam/[^"]+)"', re.I
)
_HLS_SRC = re.compile(r'<source[^>]+src="([^"]+\.m3u8[^"]*)"', re.I)
_TITLE = re.compile(r"<title>([^<]+)</title>", re.I)
# "Brixham Harbour Live Streaming Webcam" -> "Brixham Harbour"; titles that LEAD with
# boilerplate ("Live Coastal Shipping Webcam from Coastwatch Redcar") fall back to the
# "from <place>" tail.
_BOILER = re.compile(r"\s*\b(?:live\s+)?(?:streaming\s+)?webcam\b.*$", re.I)
_LEADING_BOILER = re.compile(r"^(?:live|streaming|coastal)\b", re.I)
_FROM = re.compile(r"\bfrom\s+(.+?)\s*$", re.I)


def _clean_title(raw: str) -> str:
    t = _BOILER.sub("", raw).strip()
    if not t or _LEADING_BOILER.match(t):
        m = _FROM.search(raw)
        if m:
            t = m.group(1).strip()
    return t


class CamSecureSource(HtmlScraperSource[str]):
    """CamSecure's live-demo index -> per-cam pages -> the player iframe's direct HLS.
    ctx is the cleaned cam title (the page <title>, boilerplate stripped)."""

    name: str = "camsecure"

    @override
    def _page_urls(self) -> list[str]:
        idx = self._fetch.get(_INDEX) or ""
        out: set[str] = set()
        for href in _CAM_HREF.findall(idx):
            low = href.lower()
            if "webcam" not in low and not re.search(
                r"/(camsecure[23]|christmas)/", low
            ):
                continue
            if any(s in low for s in _SKIP):
                continue
            out.add(urljoin(_BASE, href.replace(" ", "%20")))  # %20 dupe -> one entry
        return sorted(out)

    @override
    def _page_meta(self, html: str, url: str) -> tuple[str | None, str]:
        m = _TITLE.search(html)
        return None, (_clean_title(m.group(1).strip()) if m else "")

    @override
    def _title_for(
        self, cand: Candidate, url: str, category: str | None, ctx: str
    ) -> str:
        return ctx

    @override
    def _candidates(self, html: str, url: str) -> list[Candidate]:
        ifr = _PLAYER_IFRAME.search(html)
        if not ifr:
            return []  # a product/info page, not a cam
        src = _HLS_SRC.search(self._fetch.get(ifr.group(1)) or "")
        if not src:
            return []  # offline / no stream on the player page
        m3u8 = urljoin(ifr.group(1), src.group(1))
        return [
            Candidate(
                title="",
                angle_key=None,
                category=None,  # no category in the feed -> "Other"
                source=self.name,
                source_page_url=url,
                target_url=m3u8,
                predisc_key=predisc_key(m3u8),
            )
        ]
