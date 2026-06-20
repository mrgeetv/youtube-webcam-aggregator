from __future__ import annotations

import time

import requests

_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


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
        for attempt in range(self._retries):
            try:
                resp = self._session.get(url, timeout=timeout)
                resp.raise_for_status()
                time.sleep(self._delay)
                return resp.text
            except requests.RequestException:
                if attempt == self._retries - 1:
                    return None
                time.sleep(2**attempt)
        return None
