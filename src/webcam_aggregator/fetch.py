from __future__ import annotations

import ipaddress
import logging
import os
import socket
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol, TypeVar
from urllib.parse import urlencode, urljoin, urlsplit

import requests

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


def is_safe_url(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return False
    host = parts.hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            return False
    return True


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
    _session: requests.Session
    _delay: float
    _retries: int

    def __init__(self, delay: float = 1.0, retries: int = 3) -> None:
        self._delay = delay
        self._retries = retries
        self._session = requests.Session()
        self._session.headers["User-Agent"] = UA

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
        # Follow redirects manually so EVERY hop is re-checked by is_safe_url.
        # requests' own redirect following would skip the guard and let an
        # upstream 302 us at an internal host (SSRF).
        current = url
        for _hop in range(_MAX_REDIRECTS):
            if not is_safe_url(current):
                return None
            resp = self._session.get(
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
        if not is_safe_url(url):
            return None
        headers = {"Range": range_header} if range_header else {}
        try:
            resp = self._session.get(
                url, headers=headers, timeout=20, stream=True, allow_redirects=False
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
        if not is_safe_url(url):
            return None
        body = urlencode(data).encode()
        for attempt in range(self._retries):
            try:
                resp = self._session.post(
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
