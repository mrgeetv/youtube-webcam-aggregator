from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from webcam_aggregator.fetch import Fetcher, is_safe_url

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


# ---------------------------------------------------------------------------
# Fetcher — redirects are followed manually, each hop re-validated
# ---------------------------------------------------------------------------


def test_fetcher_does_not_follow_redirect_to_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def addrinfo(host: str, *_a: object, **_k: object) -> list[tuple[object, ...]]:
        ip = "127.0.0.1" if host == "127.0.0.1" else "93.184.216.34"
        return [(None, None, None, None, (ip, 0))]

    fetched: list[str] = []

    class _Resp:
        is_redirect: bool = True
        is_permanent_redirect: bool = False
        headers: dict[str, str] = {"Location": "http://127.0.0.1/secret"}

        def raise_for_status(self) -> None: ...

        def iter_content(self, _n: int) -> object:
            return iter(())

        def close(self) -> None: ...

    def fake_get(_self: object, url: str, **_k: object) -> _Resp:
        fetched.append(url)
        return _Resp()

    monkeypatch.setattr("webcam_aggregator.fetch.socket.getaddrinfo", addrinfo)
    monkeypatch.setattr("requests.Session.get", fake_get)

    f = Fetcher(delay=0.0, retries=1)
    # public start → 302 to a private host → must NOT be fetched, returns None
    assert f.get("https://public.example/p.m3u8") is None
    assert fetched == ["https://public.example/p.m3u8"]


# ---------------------------------------------------------------------------
# Fetcher.get_segment
# ---------------------------------------------------------------------------


def test_get_segment_blocks_unsafe_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_segment must return None for private/unsafe URLs without making a request."""
    monkeypatch.setattr(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        lambda *_a, **_k: _mock_getaddrinfo("127.0.0.1"),
    )
    f = Fetcher(delay=0.0, retries=1)
    assert f.get_segment("http://127.0.0.1/seg.ts") is None


def test_get_segment_happy_relay(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_segment relays status_code, Content-Type, Content-Range and body."""
    monkeypatch.setattr(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        lambda *_a, **_k: _mock_getaddrinfo("93.184.216.34"),
    )

    class _FakeResp:
        is_redirect: bool = False
        is_permanent_redirect: bool = False
        status_code: int = 206
        headers: dict[str, str] = {
            "Content-Type": "video/mp2t",
            "Content-Range": "bytes 0-65535/1000000",
        }

        def iter_content(self, _chunk_size: int) -> object:
            return iter([b"hello", b"world"])

        def close(self) -> None: ...

    def fake_get(_self: object, _url: str, **_k: object) -> _FakeResp:
        return _FakeResp()

    monkeypatch.setattr("requests.Session.get", fake_get)

    f = Fetcher(delay=0.0, retries=1)
    result = f.get_segment(
        "https://cdn.balticlivecam.com/seg.ts", range_header="bytes=0-65535"
    )
    assert result is not None
    status, ct, cr, body = result
    assert status == 206
    assert ct == "video/mp2t"
    assert cr == "bytes 0-65535/1000000"
    assert body == b"helloworld"


def test_get_segment_refuses_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_segment must return None when the segment URL redirects."""
    monkeypatch.setattr(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        lambda *_a, **_k: _mock_getaddrinfo("93.184.216.34"),
    )

    class _RedirectResp:
        is_redirect: bool = True
        is_permanent_redirect: bool = False
        headers: dict[str, str] = {"Location": "https://other.example/seg.ts"}

        def close(self) -> None: ...

    monkeypatch.setattr(
        "requests.Session.get", lambda _self, _url, **_k: _RedirectResp()
    )

    f = Fetcher(delay=0.0, retries=1)
    assert f.get_segment("https://cdn.balticlivecam.com/seg.ts") is None


# ---------------------------------------------------------------------------
# Fetcher.get — RequestException paths
# ---------------------------------------------------------------------------


def test_get_returns_none_after_request_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All retry attempts raise RequestException → Fetcher.get returns None."""
    import requests

    monkeypatch.setattr(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        lambda *_a, **_k: _mock_getaddrinfo("93.184.216.34"),
    )
    monkeypatch.setattr(
        "requests.Session.get",
        lambda _self, _url, **_k: (_ for _ in ()).throw(
            requests.RequestException("connection failed")
        ),
    )
    f = Fetcher(delay=0.0, retries=1)
    assert f.get("https://cdn.example/playlist.m3u8") is None


def test_get_retries_on_request_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First attempt raises RequestException, second succeeds → returns content."""
    import requests

    monkeypatch.setattr(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        lambda *_a, **_k: _mock_getaddrinfo("93.184.216.34"),
    )
    call_count = [0]

    class _GoodResp:
        is_redirect: bool = False
        is_permanent_redirect: bool = False

        def raise_for_status(self) -> None: ...

        def iter_content(self, _n: int) -> object:
            return iter([b"hello"])

        def close(self) -> None: ...

    def fake_get(_self: object, _url: str, **_k: object) -> _GoodResp:
        call_count[0] += 1
        if call_count[0] == 1:
            raise requests.RequestException("transient failure")
        return _GoodResp()

    monkeypatch.setattr("requests.Session.get", fake_get)
    f = Fetcher(delay=0.0, retries=2)
    result = f.get("https://cdn.example/playlist.m3u8")
    assert result == "hello"
    assert call_count[0] == 2


def test_get_redirect_no_location_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redirect response with no Location header → returns None."""
    monkeypatch.setattr(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        lambda *_a, **_k: _mock_getaddrinfo("93.184.216.34"),
    )

    class _NoLocResp:
        is_redirect: bool = True
        is_permanent_redirect: bool = False
        headers: dict[str, str] = {}  # no Location

        def close(self) -> None: ...

    monkeypatch.setattr("requests.Session.get", lambda _self, _url, **_k: _NoLocResp())
    f = Fetcher(delay=0.0, retries=1)
    assert f.get("https://cdn.example/playlist.m3u8") is None


def test_get_segment_request_exception_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RequestException in get_segment → None."""
    import requests

    monkeypatch.setattr(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        lambda *_a, **_k: _mock_getaddrinfo("93.184.216.34"),
    )
    monkeypatch.setattr(
        "requests.Session.get",
        lambda _self, _url, **_k: (_ for _ in ()).throw(
            requests.RequestException("timeout")
        ),
    )
    f = Fetcher(delay=0.0, retries=1)
    assert f.get_segment("https://cdn.example/seg.ts") is None


def test_get_oversized_body_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Body exceeding MAX_BYTES ceiling → _fetch_following returns None."""
    from webcam_aggregator.fetch import MAX_BYTES

    monkeypatch.setattr(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        lambda *_a, **_k: _mock_getaddrinfo("93.184.216.34"),
    )

    class _BigResp:
        is_redirect: bool = False
        is_permanent_redirect: bool = False

        def raise_for_status(self) -> None: ...

        def iter_content(self, _n: int) -> object:
            # Return one chunk larger than MAX_BYTES
            return iter([b"x" * (MAX_BYTES + 1)])

        def close(self) -> None: ...

    monkeypatch.setattr("requests.Session.get", lambda _self, _url, **_k: _BigResp())
    f = Fetcher(delay=0.0, retries=1)
    assert f.get("https://cdn.example/big.m3u8") is None


def test_get_segment_oversized_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Segment exceeding SEGMENT_MAX_BYTES ceiling → get_segment returns None."""
    from webcam_aggregator.fetch import SEGMENT_MAX_BYTES

    monkeypatch.setattr(
        "webcam_aggregator.fetch.socket.getaddrinfo",
        lambda *_a, **_k: _mock_getaddrinfo("93.184.216.34"),
    )

    class _BigSegResp:
        is_redirect: bool = False
        is_permanent_redirect: bool = False
        status_code: int = 200
        headers: dict[str, str] = {"Content-Type": "video/mp2t"}

        def iter_content(self, _n: int) -> object:
            return iter([b"x" * (SEGMENT_MAX_BYTES + 1)])

        def close(self) -> None: ...

    monkeypatch.setattr("requests.Session.get", lambda _self, _url, **_k: _BigSegResp())
    f = Fetcher(delay=0.0, retries=1)
    assert f.get_segment("https://cdn.example/seg.ts") is None
