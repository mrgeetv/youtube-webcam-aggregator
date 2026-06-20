from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from urllib.parse import quote, urljoin

from .cache import ResolveCache
from .models import CatalogueEntry

_HLS_CT = "application/vnd.apple.mpegurl"
_NONCOMMENT = re.compile(r"^(?!#)(\S+)\s*$", re.M)

# (status_code, content_type_or_location, body)
Response = tuple[int, str, bytes]


def render_playlist(entries: list[CatalogueEntry], *, base_url: str) -> str:
    lines = ["#EXTM3U"]
    for e in entries:
        lines.append(f'#EXTINF:-1 group-title="{e.category}",{e.title}')
        lines.append(f"{base_url}/stream/{e.id}")
    return "\n".join(lines) + "\n"


def rewrite_manifest(
    text: str, *, upstream_url: str, entry_id: str, base_url: str
) -> str:
    def repl(m: re.Match[str]) -> str:
        ref = m.group(1)
        absolute = urljoin(upstream_url, ref)
        if absolute.split("?", 1)[0].endswith(".m3u8"):
            return f"{base_url}/stream/{entry_id}/m?u={quote(absolute, safe='')}"
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
        return (502, "text/plain", b"resolve failed")
    if resolved.stream_type == "mp4":
        return (302, resolved.url, b"")  # redirect; 2nd field is the Location
    manifest = fetch(resolved.url)
    if manifest is None:
        return (502, "text/plain", b"upstream manifest fetch failed")
    body = rewrite_manifest(
        manifest, upstream_url=resolved.url, entry_id=entry_id, base_url=base_url
    )
    return (200, _HLS_CT, body.encode())


def serve_child_manifest(
    entry_id: str,
    upstream_url: str,
    *,
    fetch: Callable[[str], str | None],
    base_url: str,
) -> Response:
    manifest = fetch(upstream_url)
    if manifest is None:
        return (502, "text/plain", b"upstream manifest fetch failed")
    body = rewrite_manifest(
        manifest, upstream_url=upstream_url, entry_id=entry_id, base_url=base_url
    )
    return (200, _HLS_CT, body.encode())
