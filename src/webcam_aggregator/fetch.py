from __future__ import annotations

import ipaddress
import socket
import time
from typing import Protocol
from urllib.parse import urlsplit

import requests

_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

MAX_BYTES = 8 * 1024 * 1024  # 8 MB ceiling for any fetched document


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


class Fetcher:
    _session: requests.Session
    _delay: float
    _retries: int

    def __init__(self, delay: float = 1.0, retries: int = 3) -> None:
        self._delay = delay
        self._retries = retries
        self._session = requests.Session()
        self._session.headers["User-Agent"] = _UA

    def get(self, url: str, timeout: float = 20.0) -> str | None:
        if not is_safe_url(url):
            return None
        for attempt in range(self._retries):
            try:
                resp = self._session.get(url, timeout=timeout, stream=True)
                resp.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                for chunk in resp.iter_content(8192):
                    total += len(chunk)
                    if total > MAX_BYTES:
                        return None  # oversized → refuse
                    chunks.append(chunk)
                time.sleep(self._delay)
                return b"".join(chunks).decode("utf-8", "replace")
            except requests.RequestException:
                if attempt == self._retries - 1:
                    return None
                time.sleep(2**attempt)
        return None
