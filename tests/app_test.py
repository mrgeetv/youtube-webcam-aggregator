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
