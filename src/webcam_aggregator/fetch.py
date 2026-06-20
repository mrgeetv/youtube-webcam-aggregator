from __future__ import annotations

import ipaddress
import logging
import os
import socket
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol, TypeVar, cast, override
from urllib.parse import urlencode, urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter

log = logging.getLogger("webcam-aggregator.fetch")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

MAX_BYTES = 8 * 1024 * 1024  # 8 MB ceiling for any fetched document
SEGMENT_MAX_BYTES = 16 * 1024 * 1024  # 16 MB ceiling for a proxied media segment
_MAX_REDIRECTS = 5


def resolve_scrape_workers() -> int:
    """Concurrency for scraping/liveness. The work is I/O-bound (network waits), so
    the ceiling is politeness to the target host, not local cores. Override with the
    SCRAPE_WORKERS env var (e.g. raise it on a small box where the build is slow)."""
    default = min(16, (os.cpu_count() or 2) * 4)
    raw = os.environ.get("SCRAPE_WORKERS")
    if raw is None:
        return default
    try:
        v = int(raw)
    except ValueError:
        log.warning("invalid SCRAPE_WORKERS=%r — using default %d", raw, default)
        return default
    if v <= 0:
        log.warning("SCRAPE_WORKERS=%d is not positive — using default %d", v, default)
        return default
    return v


SCRAPE_WORKERS = resolve_scrape_workers()

_T = TypeVar("_T")
_R = TypeVar("_R")


def thread_map(
    fn: Callable[[_T], _R], items: list[_T], *, workers: int = SCRAPE_WORKERS
) -> list[_R]:
    """Map fn over items concurrently, preserving order. Empty in → empty out."""
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(items)))) as ex:
        return list(ex.map(fn, items))


def _ip_is_unsafe(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def _resolve_validated_ip(url: str) -> str | None:
    """Resolve the URL's host ONCE and validate every returned IP. Returns a single
    safe IP to connect to, or None if the scheme is unsupported, the host won't
    resolve, or ANY resolved IP is private/loopback/link-local/reserved/multicast.

    This is the SSRF check AND the source of truth for the connection IP: the caller
    pins the connection to the returned IP so there is no second DNS lookup between
    validation and connect (closing the DNS-rebinding TOCTOU window). Returning the
    first IP (rather than re-resolving) is what makes validate-then-pin atomic."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return None
    host = parts.hostname
    if not host:
        return None
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return None
    chosen: str | None = None
    for info in infos:
        ip_str = str(info[4][0])  # sockaddr[0] is the IP literal
        if _ip_is_unsafe(ip_str):
            return None  # any unsafe IP poisons the whole host — refuse
        if chosen is None:
            chosen = ip_str
    return chosen


class _PinnedHostAdapter(HTTPAdapter):
    """A requests adapter that CONNECTS to a pre-validated IP while preserving the
    original hostname for the HTTP Host header, TLS SNI, AND certificate validation
    (the "curl --resolve" pattern).

    Why this closes the DNS-rebinding TOCTOU: we validate the host's IPs once
    (`_resolve_validated_ip`) and then force urllib3 to dial *that* IP instead of
    re-resolving the hostname at connect time. An attacker controlling DNS cannot
    swap in an internal IP between the check and the connect, because there is no
    second lookup.

    TLS is NOT weakened. We dial the IP but set urllib3's `server_hostname` (SNI)
    and `assert_hostname` to the ORIGINAL hostname, so the certificate is verified
    against the hostname exactly as it would be normally. `verify` stays at its
    default (True); we never touch cert_reqs/assert_hostname=False/verify=False.
    The Host header is derived by requests from the unchanged request URL, so it
    too stays the original hostname.

    Thread-safety: each adapter is bound to ONE (host, ip) pair and is mounted on a
    call-local Session (see `_pinned_session`). A Session is only unsafe to share
    across threads; a fresh per-call Session + adapter is confined to the calling
    thread, so concurrent Fetcher calls from thread_map workers and the threaded
    HTTP server never share mutable state."""

    _pin_host: str
    _pin_ip: str

    def __init__(self, host: str, ip: str) -> None:
        self._pin_host = host
        self._pin_ip = ip
        super().__init__(max_retries=0)

    @override
    def get_connection_with_tls_context(
        self,
        request: requests.PreparedRequest,
        verify: Any,
        proxies: Any = None,
        cert: Any = None,
    ) -> Any:
        del proxies  # we never proxy; param exists only to match the override
        host_params, pool_kwargs = self.build_connection_pool_key_attributes(
            request, verify, cert
        )
        # For HTTPS: bind SNI + cert hostname matching to the ORIGINAL host (not the
        # IP), then repoint the TCP target at the validated IP. urllib3 connects to
        # host_params["host"] but uses server_hostname for SNI and assert_hostname
        # for the certificate match — so the cert is still validated against the
        # hostname while the socket goes to the pinned IP. (These kwargs only exist
        # on the TLS connection class; a plain http HTTPConnection rejects them, so
        # only set them for https — http has no TLS to preserve, just the IP pin.)
        # cast: server_hostname/assert_hostname are valid urllib3 pool kwargs but
        # aren't in requests' narrow _PoolKwargs TypedDict (cast via object since
        # the TypedDict doesn't structurally overlap a plain dict).
        pk = cast(dict[str, Any], cast(object, pool_kwargs))
        if host_params.get("scheme") == "https":
            pk["server_hostname"] = self._pin_host
            pk["assert_hostname"] = self._pin_host
        host_params["host"] = self._pin_ip
        return self.poolmanager.connection_from_host(**host_params, pool_kwargs=pk)


def _pinned_session(host: str, ip: str) -> requests.Session:
    """Build a call-local Session that pins connections to `ip` while presenting
    `host` for Host/SNI/cert. Call-local (not shared) so it is thread-safe."""
    session = requests.Session()
    session.headers["User-Agent"] = UA
    adapter = _PinnedHostAdapter(host, ip)
    # Mount for both schemes; the adapter handles http (plain TCP to the IP) and
    # https (TLS to the IP, SNI/cert against the host) alike.
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class FetcherProtocol(Protocol):
    def get(self, url: str, timeout: float = ..., /) -> str | None: ...


class FetcherPostProtocol(Protocol):
    def post(
        self,
        url: str,
        data: dict[str, str],
        /,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = ...,
    ) -> str | None: ...


class Fetcher:
    _delay: float
    _retries: int

    def __init__(self, delay: float = 1.0, retries: int = 3) -> None:
        self._delay = delay
        self._retries = retries

    def get(self, url: str, timeout: float = 20.0) -> str | None:
        for attempt in range(self._retries):
            try:
                body = self._fetch_following(url, timeout)
                time.sleep(self._delay)
                return body
            except requests.RequestException:
                if attempt == self._retries - 1:
                    return None
                time.sleep(2**attempt)
        return None

    def _fetch_following(self, url: str, timeout: float) -> str | None:
        # Follow redirects manually so EVERY hop is re-resolved, re-validated, and
        # re-pinned by _resolve_validated_ip. requests' own redirect following would
        # skip the guard and let an upstream 302 us at an internal host (SSRF).
        current = url
        for _hop in range(_MAX_REDIRECTS):
            ip = _resolve_validated_ip(current)
            if ip is None:
                return None
            host = urlsplit(current).hostname or ""
            # Fresh per-call session pinned to the validated IP (thread-safe).
            with _pinned_session(host, ip) as session:
                resp = session.get(
                    current, timeout=timeout, stream=True, allow_redirects=False
                )
                if resp.is_redirect or resp.is_permanent_redirect:
                    location = resp.headers.get("Location")
                    resp.close()
                    if not location:
                        return None
                    current = urljoin(current, location)
                    continue
                resp.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_content(8192):
                    total += len(chunk)
                    if total > MAX_BYTES:
                        resp.close()
                        return None  # oversized → refuse
                    chunks.append(chunk)
                return b"".join(chunks).decode("utf-8", "replace")
        return None  # too many redirects

    def get_segment(
        self, url: str, range_header: str | None = None
    ) -> tuple[int, str, str | None, bytes] | None:
        """Fetch a media segment as bytes, relaying status + Range. None on failure."""
        ip = _resolve_validated_ip(url)
        if ip is None:
            return None
        host = urlsplit(url).hostname or ""
        headers = {"Range": range_header} if range_header else {}
        try:
            with _pinned_session(host, ip) as session:
                resp = session.get(
                    url,
                    headers=headers,
                    timeout=20,
                    stream=True,
                    allow_redirects=False,
                )
                if resp.is_redirect or resp.is_permanent_redirect:
                    resp.close()
                    return None  # signed segment URLs shouldn't redirect; refuse
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_content(65536):
                    total += len(chunk)
                    if total > SEGMENT_MAX_BYTES:
                        resp.close()
                        return None
                    chunks.append(chunk)
                return (
                    resp.status_code,
                    resp.headers.get("Content-Type", "video/mp2t"),
                    resp.headers.get("Content-Range"),
                    b"".join(chunks),
                )
        except requests.RequestException:
            return None

    def post(
        self,
        url: str,
        data: dict[str, str],
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 20.0,
    ) -> str | None:
        ip = _resolve_validated_ip(url)
        if ip is None:
            return None
        host = urlsplit(url).hostname or ""
        body = urlencode(data).encode()
        for attempt in range(self._retries):
            try:
                with _pinned_session(host, ip) as session:
                    resp = session.post(
                        url,
                        data=body,
                        headers=headers or {},
                        timeout=timeout,
                        stream=True,
                        allow_redirects=False,
                    )
                    time.sleep(self._delay)
                    if resp.is_redirect or resp.is_permanent_redirect:
                        resp.close()
                        return None  # admin-ajax POSTs shouldn't redirect; refuse
                    resp.raise_for_status()
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in resp.iter_content(8192):
                        total += len(chunk)
                        if total > MAX_BYTES:
                            resp.close()
                            return None
                        chunks.append(chunk)
                    return b"".join(chunks).decode("utf-8", "replace")
            except requests.RequestException:
                if attempt == self._retries - 1:
                    return None
                time.sleep(2**attempt)
        return None
