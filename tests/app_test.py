from __future__ import annotations

from typing import Any

from webcam_aggregator.app import origin_of

# ---------------------------------------------------------------------------
# origin_of helper — must return the scheme+host with trailing slash
# ---------------------------------------------------------------------------


def test_origin_of_typical_url() -> None:
    assert (
        origin_of("https://balticlivecam.com/wp-admin/admin-ajax.php")
        == "https://balticlivecam.com/"
    )


def test_origin_of_with_path_and_query() -> None:
    assert origin_of("http://example.com/some/path?foo=bar") == "http://example.com/"


def test_origin_of_preserves_scheme() -> None:
    assert origin_of("http://insecure.example.com/x").startswith("http://")
    assert origin_of("https://secure.example.com/x").startswith("https://")


def test_origin_of_no_trailing_slash_duplication() -> None:
    result = origin_of("https://balticlivecam.com/wp-admin/admin-ajax.php")
    assert result.endswith("/")
    assert not result.endswith("//")


# ---------------------------------------------------------------------------
# _baltic_post — Referer must be the SITE ORIGIN, not the ajax URL
# ---------------------------------------------------------------------------


def test_baltic_post_sends_xhr_and_site_origin_referer() -> None:
    import webcam_aggregator.app as _app

    _baltic_post = _app._baltic_post  # pyright: ignore[reportPrivateUsage]

    captured: dict[str, Any] = {}

    class _FakeFetcher:
        def post(
            self,
            _url: str,
            _data: dict[str, str],
            *,
            headers: dict[str, str] | None = None,
            timeout: float = 20.0,
        ) -> str:
            del timeout  # unused; present to satisfy FetcherPostProtocol signature
            captured["headers"] = headers
            return "ok"

    out = _baltic_post(_FakeFetcher())(
        "https://balticlivecam.com/wp-admin/admin-ajax.php", {"action": "auth_token"}
    )
    assert out == "ok"
    headers: dict[str, str] = captured["headers"]
    assert (
        headers["Referer"] == "https://balticlivecam.com/"
    )  # site origin, NOT the ajax URL
    assert headers["X-Requested-With"] == "XMLHttpRequest"


def test_is_alive_fetch_verifies_hls() -> None:
    from webcam_aggregator.app import make_is_alive
    from webcam_aggregator.extractors.base import Resolved
    from webcam_aggregator.models import Candidate

    def resolve(_id: str, _url: str) -> Resolved:
        return Resolved(url="https://cdn.x/p.m3u8", stream_type="hls", ttl_seconds=None)

    cand = Candidate(
        title="x",
        angle_key=None,
        category=None,
        source="s",
        source_page_url="https://x/p",
        target_url="https://x/p.m3u8",
        predisc_key=None,
    )
    assert make_is_alive(resolve, lambda u: "#EXTM3U\nseg.ts\n")(cand) is True
    assert make_is_alive(resolve, lambda u: None)(cand) is False  # dead/404
    assert make_is_alive(resolve, lambda u: "<?xml?><MPD/>")(cand) is False  # DASH
