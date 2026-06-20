from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping
from urllib.parse import quote, urljoin, urlsplit

from .cache import ResolveCache
from .models import CatalogueEntry
from .signing import sign, verify

log = logging.getLogger("webcam-aggregator.serving")

_HLS_CT = "application/vnd.apple.mpegurl"
_NONCOMMENT = re.compile(r"^(?!#)(\S+)\s*$", re.M)

# Hosts whose HLS sessions are bound to the IP that fetches the manifest. Proxying
# the manifest (our IP) while the player fetches segments direct (its IP) makes the
# upstream 403 the segments. For these we hand the player the original URL and let
# it fetch the whole chain itself, so manifest + segments share one IP/session.
_DIRECT_PLAYBACK_HOSTS = ("pixelcaster.com",)


def _is_direct_playback(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return any(host == h or host.endswith("." + h) for h in _DIRECT_PLAYBACK_HOSTS)


# Hosts whose segments are token/IP-bound to OUR fetch (e.g. baltic's auth token):
# the player can't fetch them directly, so we relay the segment bytes too.
_PROXY_SEGMENT_HOSTS = ("balticlivecam.com",)


def _proxy_segments_for(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return any(host == h or host.endswith("." + h) for h in _PROXY_SEGMENT_HOSTS)


# (status_code, content_type_or_location, body)
Response = tuple[int, str, bytes]

# (status_code, content_type, content_range_or_None, body)
SegmentResponse = tuple[int, str, str | None, bytes]


def render_playlist(entries: list[CatalogueEntry], *, base_url: str) -> str:
    lines = ["#EXTM3U"]
    for e in entries:
        lines.append(f'#EXTINF:-1 group-title="{e.category}",{e.title}')
        lines.append(f"{base_url}/stream/{e.id}")
    return "\n".join(lines) + "\n"


def rewrite_manifest(
    text: str,
    *,
    upstream_url: str,
    entry_id: str,
    base_url: str,
    proxy_segments: bool = False,
) -> str:
    def repl(m: re.Match[str]) -> str:
        ref = m.group(1)
        absolute = urljoin(upstream_url, ref)
        if absolute.split("?", 1)[0].endswith(".m3u8"):
            return f"{base_url}/stream/{entry_id}/m?u={quote(absolute, safe='')}&sig={sign(absolute)}"
        if proxy_segments:
            return f"{base_url}/stream/{entry_id}/s?u={quote(absolute, safe='')}&sig={sign(absolute)}"
        return absolute

    return _NONCOMMENT.sub(repl, text)


def serve_stream(
    entry_id: str,
    *,
    catalogue: Mapping[str, CatalogueEntry],
    cache: ResolveCache,
    fetch: Callable[[str], str | None],
    base_url: str,
) -> Response:
    entry = catalogue.get(entry_id)
    if entry is None:
        return (404, "text/plain", b"unknown stream")
    resolved = cache.get(entry_id, entry.target_url)
    if resolved is None:
        log.warning("resolve failed: %s -> %s", entry_id, entry.target_url)
        return (502, "text/plain", b"resolve failed")
    if resolved.stream_type == "mp4":
        return (302, resolved.url, b"")  # redirect; 2nd field is the Location
    if _is_direct_playback(resolved.url):
        # IP-bound session: let the player fetch the whole chain itself (no proxy)
        return (302, resolved.url, b"")
    manifest = fetch(resolved.url)
    if manifest is None:
        log.warning("manifest fetch failed: %s -> %s", entry_id, resolved.url)
        return (502, "text/plain", b"upstream manifest fetch failed")
    if "#EXTM3U" not in manifest:
        # Not HLS (e.g. a DASH .mpd or an error page) — don't serve it as HLS.
        log.warning("non-HLS manifest: %s -> %s", entry_id, resolved.url)
        return (502, "text/plain", b"not an HLS stream")
    body = rewrite_manifest(
        manifest,
        upstream_url=resolved.url,
        entry_id=entry_id,
        base_url=base_url,
        proxy_segments=_proxy_segments_for(resolved.url),
    )
    return (200, _HLS_CT, body.encode())


def serve_child_manifest(
    entry_id: str,
    upstream_url: str,
    sig: str,
    *,
    fetch: Callable[[str], str | None],
    base_url: str,
) -> Response:
    if not verify(upstream_url, sig):
        return (403, "text/plain", b"bad signature")
    manifest = fetch(upstream_url)
    if manifest is None:
        return (502, "text/plain", b"upstream manifest fetch failed")
    body = rewrite_manifest(
        manifest,
        upstream_url=upstream_url,
        entry_id=entry_id,
        base_url=base_url,
        proxy_segments=_proxy_segments_for(upstream_url),
    )
    return (200, _HLS_CT, body.encode())


def serve_segment(
    entry_id: str,
    upstream_url: str,
    sig: str,
    *,
    fetch_segment: Callable[
        [str, str | None], tuple[int, str, str | None, bytes] | None
    ],
    range_header: str | None = None,
) -> SegmentResponse:
    if not verify(upstream_url, sig):
        return (403, "text/plain", None, b"bad signature")
    result = fetch_segment(upstream_url, range_header)
    if result is None:
        log.warning("segment fetch failed: %s -> %s", entry_id, upstream_url)
        return (502, "text/plain", None, b"segment fetch failed")
    return result
