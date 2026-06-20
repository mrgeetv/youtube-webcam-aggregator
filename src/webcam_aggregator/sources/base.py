from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from typing import Protocol
from urllib.parse import unquote

from ..models import Candidate

_YT_VIDEO = re.compile(
    r"youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=|live/)([A-Za-z0-9_-]{11})"
)
_YT_PLAYLIST = re.compile(r"youtube(?:-nocookie)?\.com/embed\?list=([A-Za-z0-9_-]+)")
_YT_CHANNEL = re.compile(
    r"youtube\.com/(channel/[A-Za-z0-9_-]+|@[A-Za-z0-9_.-]+)(?:/live)?"
)
_M3U8 = re.compile(r"https?:[\\/]+[^\"'\s\\]+\.m3u8[^\"'\s\\]*")
_WC_STREAMS = re.compile(r'streams\[\d+\]\s*=\s*"((?:[^"\\]|\\.)*)"')
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


def _angle_targets(html: str) -> list[str]:
    out: list[str] = []
    for raw in _WC_STREAMS.findall(html):
        m = _IFRAME_SRC.search(raw)
        if m:
            out.append(m.group(1))
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
        norm = re.sub(r"[?&](token|expire|hdnts|st|e)=[^&]*", "", t).rstrip("?&")
        return f"hls:{norm}"
    return None


def extract_candidates(html: str, *, page_url: str, source: str) -> Iterator[Candidate]:
    clean = _strip_attribution(html)
    raw_targets = _angle_targets(clean)
    if not raw_targets:
        for m in _YT_VIDEO.finditer(clean):
            raw_targets.append(f"https://www.youtube.com/watch?v={m.group(1)}")
        for m in _YT_PLAYLIST.finditer(clean):
            raw_targets.append(f"https://www.youtube.com/embed?list={m.group(1)}")
        for pm in _WC_PLAYER.finditer(clean):
            raw_targets.append("https://worldcams.tv/player?url=" + pm.group(1))
        for mm in _M3U8.finditer(clean):
            raw_targets.append(mm.group(0))
        cm = _YT_CHANNEL.search(clean)
        if cm:
            raw_targets.append("https://www.youtube.com/" + cm.group(1) + "/live")
        if not raw_targets:
            ifr = _IFRAME_TAG.search(clean)
            if ifr:
                raw_targets.append(ifr.group(1))
    seen: set[str] = set()
    multi = len(raw_targets) > 1
    for idx, target in enumerate(raw_targets):
        if target in seen:
            continue
        seen.add(target)
        yield Candidate(
            title="",
            angle_label=None,
            angle_key=str(idx) if multi else None,
            category=None,
            source=source,
            source_page_url=page_url,
            target_url=target,
            hint=None,
            predisc_key=_predisc_key(target),
        )
