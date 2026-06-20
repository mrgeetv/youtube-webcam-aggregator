from __future__ import annotations

from urllib.parse import quote

from webcam_aggregator.cache import ResolveCache
from webcam_aggregator.extractors.base import Resolved
from webcam_aggregator.models import CatalogueEntry
from webcam_aggregator.serving import (
    rewrite_manifest,
    render_playlist,
    serve_stream,
    serve_child_manifest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE = "https://cams.example"
ENTRY_ID = "ab12"


def _entry(
    entry_id: str = ENTRY_ID,
    title: str = "Miami",
    category: str = "Beaches",
    target_url: str = "https://origin.example/cam/playlist.m3u8",
) -> CatalogueEntry:
    return CatalogueEntry(
        id=entry_id,
        title=title,
        category=category,
        source="test",
        source_page_url="https://origin.example/cam",
        target_url=target_url,
        resolver_hint=None,
    )


def _make_cache(resolved: Resolved | None) -> ResolveCache:
    """Real ResolveCache with an injected resolver returning a fixed Resolved."""

    def _resolve(_entry_id: str, _target_url: str) -> Resolved:
        if resolved is None:
            raise RuntimeError("resolve failed")
        return resolved

    return ResolveCache(_resolve, clock=lambda: 0.0)


# ---------------------------------------------------------------------------
# 1. render_playlist
# ---------------------------------------------------------------------------


def test_render_playlist_extinf_line() -> None:
    entries = [_entry()]
    out = render_playlist(entries, base_url=BASE)
    assert '#EXTINF:-1 group-title="Beaches",Miami' in out


def test_render_playlist_stream_url() -> None:
    entries = [_entry()]
    out = render_playlist(entries, base_url=BASE)
    assert f"{BASE}/stream/{ENTRY_ID}" in out


# ---------------------------------------------------------------------------
# 2. rewrite_manifest — YouTube master (absolute variant URLs → .m3u8)
# ---------------------------------------------------------------------------

YT_UPSTREAM = "https://manifest.googlevideo.com/api/manifest/hls_playlist/master.m3u8"

YT_MASTER = """\
#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=500000
https://manifest.googlevideo.com/api/manifest/hls_variant/itag/234/hls_variant/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2000000
https://manifest.googlevideo.com/api/manifest/hls_variant/itag/299/hls_variant/index.m3u8
"""

YT_VARIANT_1 = "https://manifest.googlevideo.com/api/manifest/hls_variant/itag/234/hls_variant/index.m3u8"
YT_VARIANT_2 = "https://manifest.googlevideo.com/api/manifest/hls_variant/itag/299/hls_variant/index.m3u8"


def test_rewrite_manifest_yt_master_variant_lines_become_proxy_urls() -> None:
    out = rewrite_manifest(
        YT_MASTER, upstream_url=YT_UPSTREAM, entry_id=ENTRY_ID, base_url=BASE
    )
    expected_1 = f"{BASE}/stream/{ENTRY_ID}/m?u={quote(YT_VARIANT_1, safe='')}"
    expected_2 = f"{BASE}/stream/{ENTRY_ID}/m?u={quote(YT_VARIANT_2, safe='')}"
    assert expected_1 in out
    assert expected_2 in out


def test_rewrite_manifest_yt_master_comment_lines_unchanged() -> None:
    out = rewrite_manifest(
        YT_MASTER, upstream_url=YT_UPSTREAM, entry_id=ENTRY_ID, base_url=BASE
    )
    assert "#EXTM3U" in out
    assert "#EXT-X-VERSION:3" in out
    assert "#EXT-X-STREAM-INF:BANDWIDTH=500000" in out


def test_rewrite_manifest_yt_master_raw_upstream_urls_absent() -> None:
    """Original absolute URLs must no longer appear as bare non-comment lines."""
    out = rewrite_manifest(
        YT_MASTER, upstream_url=YT_UPSTREAM, entry_id=ENTRY_ID, base_url=BASE
    )
    lines = [ln for ln in out.splitlines() if ln and not ln.startswith("#")]
    for line in lines:
        assert line.startswith(f"{BASE}/stream/"), f"unexpected line: {line!r}"


# ---------------------------------------------------------------------------
# 3. rewrite_manifest — Wowza media (relative refs)
# ---------------------------------------------------------------------------

WOWZA_UPSTREAM = "https://cdn.x/cam/playlist.m3u8"

WOWZA_MEDIA = """\
#EXTM3U
chunklist_w1.m3u8
media_1.ts
"""


def test_rewrite_manifest_wowza_child_m3u8_becomes_proxy_url() -> None:
    absolute_child = "https://cdn.x/cam/chunklist_w1.m3u8"
    expected = f"{BASE}/stream/{ENTRY_ID}/m?u={quote(absolute_child, safe='')}"
    out = rewrite_manifest(
        WOWZA_MEDIA, upstream_url=WOWZA_UPSTREAM, entry_id=ENTRY_ID, base_url=BASE
    )
    assert expected in out


def test_rewrite_manifest_wowza_segment_becomes_absolute_direct() -> None:
    absolute_seg = "https://cdn.x/cam/media_1.ts"
    out = rewrite_manifest(
        WOWZA_MEDIA, upstream_url=WOWZA_UPSTREAM, entry_id=ENTRY_ID, base_url=BASE
    )
    assert absolute_seg in out
    # Must NOT be routed through us
    assert f"{BASE}/stream/" not in out.replace(
        f"{BASE}/stream/{ENTRY_ID}/m?u=", ""
    ).replace(absolute_seg, "")


def test_rewrite_manifest_wowza_segment_not_proxied() -> None:
    """Segment URL must appear verbatim (absolute), not wrapped in our /stream/ proxy path."""
    out = rewrite_manifest(
        WOWZA_MEDIA, upstream_url=WOWZA_UPSTREAM, entry_id=ENTRY_ID, base_url=BASE
    )
    lines = [ln for ln in out.splitlines() if ln and not ln.startswith("#")]
    segments = [ln for ln in lines if not ln.startswith(f"{BASE}/stream/")]
    assert any("media_1.ts" in seg for seg in segments)


# ---------------------------------------------------------------------------
# 4. serve_stream
# ---------------------------------------------------------------------------


def test_serve_stream_unknown_id_returns_404() -> None:
    cache = _make_cache(Resolved(url="u", stream_type="hls", ttl_seconds=60))
    status, _, _ = serve_stream(
        "unknown",
        catalogue={},
        cache=cache,
        fetch=lambda u: None,
        base_url=BASE,
    )
    assert status == 404


def test_serve_stream_cache_miss_returns_502() -> None:
    entry = _entry()
    cache = _make_cache(None)  # resolver raises → negative cache → returns None
    status, _, _ = serve_stream(
        ENTRY_ID,
        catalogue={ENTRY_ID: entry},
        cache=cache,
        fetch=lambda u: None,
        base_url=BASE,
    )
    assert status == 502


def test_serve_stream_hls_returns_200_rewritten_body() -> None:
    manifest = "#EXTM3U\nrelative_chunk.m3u8\n"
    resolved = Resolved(
        url="https://cdn.x/cam/playlist.m3u8",
        stream_type="hls",
        ttl_seconds=60,
    )
    cache = _make_cache(resolved)
    entry = _entry(target_url="https://origin.example/cam/playlist.m3u8")
    status, ct, body = serve_stream(
        ENTRY_ID,
        catalogue={ENTRY_ID: entry},
        cache=cache,
        fetch=lambda u: manifest,
        base_url=BASE,
    )
    assert status == 200
    assert "mpegurl" in ct
    text = body.decode()
    expected_proxied = f"{BASE}/stream/{ENTRY_ID}/m?u={quote('https://cdn.x/cam/relative_chunk.m3u8', safe='')}"
    assert expected_proxied in text


def test_serve_stream_mp4_returns_302_with_location() -> None:
    mp4_url = "https://cdn.x/video.mp4"
    resolved = Resolved(url=mp4_url, stream_type="mp4", ttl_seconds=60)
    cache = _make_cache(resolved)
    entry = _entry()
    status, location, body = serve_stream(
        ENTRY_ID,
        catalogue={ENTRY_ID: entry},
        cache=cache,
        fetch=lambda u: None,
        base_url=BASE,
    )
    assert status == 302
    assert location == mp4_url
    assert body == b""


# ---------------------------------------------------------------------------
# 5. serve_child_manifest
# ---------------------------------------------------------------------------


def test_serve_child_manifest_fetch_failure_returns_502() -> None:
    status, _, _ = serve_child_manifest(
        ENTRY_ID,
        "https://cdn.x/cam/chunklist.m3u8",
        fetch=lambda u: None,
        base_url=BASE,
    )
    assert status == 502


def test_serve_child_manifest_returns_200_rewritten_body() -> None:
    media_manifest = "#EXTM3U\nseg_001.ts\n"
    upstream_url = "https://cdn.x/cam/chunklist.m3u8"
    status, ct, body = serve_child_manifest(
        ENTRY_ID,
        upstream_url,
        fetch=lambda u: media_manifest,
        base_url=BASE,
    )
    assert status == 200
    assert "mpegurl" in ct
    text = body.decode()
    # Segment must be absolute direct (not proxied)
    assert "https://cdn.x/cam/seg_001.ts" in text
    assert f"{BASE}/stream/" not in text
