from __future__ import annotations

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
# SafeRedirectHandler — a redirect to an internal host must be refused
# ---------------------------------------------------------------------------


def test_safe_redirect_handler_blocks_private_hosts() -> None:
    import urllib.request

    from webcam_aggregator.app import SafeRedirectHandler

    h = SafeRedirectHandler()
    req = urllib.request.Request("https://example.com/")
    # loopback and link-local (cloud metadata) redirect targets → refused (None)
    assert h.redirect_request(req, None, 302, "msg", {}, "http://127.0.0.1/x") is None
    assert (
        h.redirect_request(req, None, 302, "msg", {}, "http://169.254.169.254/") is None
    )


def test_is_alive_fetch_verifies_hls() -> None:
    from webcam_aggregator.app import make_is_alive
    from webcam_aggregator.extractors.base import Resolved
    from webcam_aggregator.models import Candidate

    def resolve(_id: str, _url: str) -> Resolved:
        return Resolved(url="https://cdn.x/p.m3u8", stream_type="hls", ttl_seconds=None)

    cand = Candidate(
        title="x",
        angle_label=None,
        angle_key=None,
        category=None,
        source="s",
        source_page_url="https://x/p",
        target_url="https://x/p.m3u8",
        hint=None,
        predisc_key=None,
    )
    assert make_is_alive(resolve, lambda u: "#EXTM3U\nseg.ts\n")(cand) is True
    assert make_is_alive(resolve, lambda u: None)(cand) is False  # dead/404
    assert make_is_alive(resolve, lambda u: "<?xml?><MPD/>")(cand) is False  # DASH
