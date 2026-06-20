from __future__ import annotations

import socket
from unittest.mock import patch

from webcam_aggregator.fetch import is_safe_url


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_getaddrinfo(ip: str):
    """Return a monkeypatch for socket.getaddrinfo that resolves to a single IP."""
    return [(None, None, None, None, (ip, 0))]


# ---------------------------------------------------------------------------
# is_safe_url — private/reserved addresses must be blocked
# ---------------------------------------------------------------------------


def test_is_safe_url_blocks_link_local() -> None:
    with patch(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        return_value=_mock_getaddrinfo("169.254.169.254"),
    ):
        assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False


def test_is_safe_url_blocks_loopback() -> None:
    with patch(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        return_value=_mock_getaddrinfo("127.0.0.1"),
    ):
        assert is_safe_url("http://127.0.0.1/") is False


def test_is_safe_url_blocks_private_10() -> None:
    with patch(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        return_value=_mock_getaddrinfo("10.0.0.1"),
    ):
        assert is_safe_url("http://10.0.0.1/") is False


def test_is_safe_url_blocks_private_192_168() -> None:
    with patch(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        return_value=_mock_getaddrinfo("192.168.1.1"),
    ):
        assert is_safe_url("http://192.168.1.1/") is False


def test_is_safe_url_blocks_file_scheme() -> None:
    # file:// must be rejected regardless of DNS
    assert is_safe_url("file:///etc/passwd") is False


def test_is_safe_url_blocks_ftp_scheme() -> None:
    assert is_safe_url("ftp://example.com/x") is False


def test_is_safe_url_allows_public_host() -> None:
    # Monkeypatch so the test is offline and deterministic
    with patch(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        return_value=_mock_getaddrinfo("93.184.216.34"),  # example.com's public IP
    ):
        assert is_safe_url("https://example.com/x") is True


def test_is_safe_url_dns_failure_returns_false() -> None:
    with patch(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        side_effect=socket.gaierror("nxdomain"),
    ):
        assert is_safe_url("https://this.does.not.exist.example/") is False


def test_is_safe_url_no_host_returns_false() -> None:
    assert is_safe_url("https:///path") is False


def test_is_safe_url_blocks_ipv6_loopback() -> None:
    with patch(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        return_value=_mock_getaddrinfo("::1"),
    ):
        assert is_safe_url("http://[::1]/") is False


def test_is_safe_url_blocks_multicast() -> None:
    with patch(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        return_value=_mock_getaddrinfo("224.0.0.1"),
    ):
        assert is_safe_url("http://multicast.example/") is False
