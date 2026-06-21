from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from typing import Protocol
from urllib.parse import unquote, urlsplit

from ..models import Candidate

_YT_VIDEO = re.compile(
    r"youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=|live/)([A-Za-z0-9_-]{11})"
)
_YT_PLAYLIST = re.compile(r"youtube(?:-nocookie)?\.com/embed\?list=([A-Za-z0-9_-]+)")
_YT_CHANNEL = re.compile(
    r"youtube\.com/(channel/[A-Za-z0-9_-]+|@[A-Za-z0-9_.-]+)(?:/live)?"
)
_M3U8 = re.compile(r"https?:[\\/]+[^\"'\s\\]+\.m3u8[^\"'\s\\]*")
_WC_STREAMS = re.compile(r"""streams\[(\d+)\]\s*=\s*(["'])((?:\\.|(?!\2).)*)\2""")
_WC_PLAYER = re.compile(r"worldcams\.tv\\?/player\?url=([^\"'\s\\]+)")
_IFRAME_SRC = re.compile(r'src=\\?"([^"\\]+)')
_IFRAME_TAG = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.I)
# Strips entire "Source: <a ...>...</a>" attribution block (including the URL inside)
_ATTRIBUTION_BLOCK = re.compile(
    r"Source:\s*(?:&nbsp;\s*)?<a\b[^>]*>.*?</a>", re.I | re.S
)


class Source(Protocol):
    name: str

    def discover(self) -> Iterable[Candidate]: ...


def _strip_attribution(html: str) -> str:
    return _ATTRIBUTION_BLOCK.sub("", html)


def _angle_targets(html: str) -> list[tuple[str | None, str]]:
    # worldcams multi-cam pages store each embed as streams[<stream-id>] = '<iframe…>'
    # (single OR double quoted). The stream-id is the join key to the per-cam name in
    # the streams__item selector, so carry it through as the angle_key.
    out: list[tuple[str | None, str]] = []
    for sid, _quote, raw in _WC_STREAMS.findall(html):
        m = _IFRAME_SRC.search(raw)
        if m:
            out.append((sid, m.group(1)))
    return out


def _predisc_key(target: str) -> str | None:
    t = (
        unquote(re.sub(r"^https?:.*?url=", "", target))
        if "player?url=" in target
        else target
    )
    m = _YT_VIDEO.search(t)
    if m:
        return f"yt:{m.group(1)}"
    if ".m3u8" in t:
        # Strip only unambiguous token params. NOT generic single-letter names like
        # `st`/`e` — those can be legitimate stream selectors, and stripping them
        # would collapse two distinct streams to one key (dedup would drop one).
        norm = re.sub(r"[?&](token|expire|hdnts)=[^&]*", "", t).rstrip("?&")
        return f"hls:{norm}"
    return None


def _norm(s: str) -> str:
    """Lower-case, drop apostrophes, punctuation -> spaces (for substring matching)."""
    s = s.lower().replace("'", "").replace("’", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def _location_parts(page_url: str) -> list[str]:
    """Prettified URL path segments, general -> specific (country, place, name)."""
    path = urlsplit(page_url).path.strip("/")
    return [
        s.replace("-", " ").title() for s in path.split("/") if s and s != "live-camera"
    ]


def location_from_url(page_url: str) -> str:
    """Full location, most-specific first: "Skid Row, Los Angeles, United States"."""
    return ", ".join(reversed(_location_parts(page_url)))


def with_location(title: str, page_url: str) -> str:
    """Append the URL location segments the title doesn't already name.

    worldcams h1s usually already include the place, so we only add what's new
    (e.g. the country) — avoiding "Dusseldorf Airport — Dusseldorf, Germany" — while
    still distinguishing generic titles ("Italy Beaches — Cinque Terre").
    """
    parts = _location_parts(page_url)
    if not title.strip():
        return location_from_url(page_url) or title
    nt = _norm(title)
    extra = [p for p in reversed(parts) if _norm(p) and _norm(p) not in nt]
    return f"{title} — {', '.join(extra)}" if extra else title


def extract_candidates(html: str, *, page_url: str, source: str) -> Iterator[Candidate]:
    clean = _strip_attribution(html)
    # Prefer the structured streams[<id>] = '<iframe…>' embeds (keyed by stream-id);
    # fall back to a whole-page scan when a page has no such array.
    pairs: list[tuple[str | None, str]] = _angle_targets(clean)
    if not pairs:
        plain: list[str] = []
        for m in _YT_VIDEO.finditer(clean):
            plain.append(f"https://www.youtube.com/watch?v={m.group(1)}")
        for m in _YT_PLAYLIST.finditer(clean):
            plain.append(f"https://www.youtube.com/embed?list={m.group(1)}")
        for pm in _WC_PLAYER.finditer(clean):
            plain.append("https://worldcams.tv/player?url=" + pm.group(1))
        for mm in _M3U8.finditer(clean):
            plain.append(mm.group(0))
        cm = _YT_CHANNEL.search(clean)
        if cm:
            plain.append("https://www.youtube.com/" + cm.group(1) + "/live")
        if not plain:
            ifr = _IFRAME_TAG.search(clean)
            if ifr:
                plain.append(ifr.group(1))
        multi = len(plain) > 1
        pairs = [(str(i) if multi else None, t) for i, t in enumerate(plain)]
    seen: set[str] = set()
    for key, target in pairs:
        if target in seen:
            continue
        seen.add(target)
        yield Candidate(
            title="",
            angle_key=key,
            category=None,
            source=source,
            source_page_url=page_url,
            target_url=target,
            predisc_key=_predisc_key(target),
        )
