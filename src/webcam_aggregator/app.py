from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, override

import psutil

from . import config
from .cache import ResolveCache
from .catalogue import Hist, build_catalogue
from .extractors.base import Resolved
from .extractors.baltic import BalticResolver
from .extractors.direct_hls import DirectHls
from .extractors.ipcamlive import IpcamliveResolver
from .extractors.metatag import MetaTagExtractor
from .extractors.ytdlp import YtDlpExtractor
from .fetch import Fetcher
from .models import Candidate, CatalogueEntry
from .registry import Registry
from .serving import render_playlist, serve_child_manifest, serve_stream

log = logging.getLogger("webcam-aggregator")
_HLS_CT = "application/vnd.apple.mpegurl"
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def _http_post(url: str, data: dict[str, str]) -> str:
    body = urllib.parse.urlencode(data).encode()
    headers = {"User-Agent": _UA, "X-Requested-With": "XMLHttpRequest", "Referer": url}
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def _is_ytdlp(u: str) -> bool:
    return any(
        h in u
        for h in ("youtube.com", "youtu.be", "twitch.tv", "dailymotion.com", "earthcam")
    )


def build_registry(_extractors: dict[str, Any]) -> Registry:
    rules: list[tuple[Callable[[str], bool], str]] = [
        (lambda u: "balticlivecam.com" in u, "baltic"),
        (lambda u: "ipcamlive.com/player/player.php" in u, "ipcamlive"),
        (lambda u: "webtv.feratel.com" in u, "metatag"),
        (lambda u: _is_ytdlp(u), "ytdlp"),
        (lambda u: ".m3u8" in u or "worldcams.tv/player?url=" in u, "direct"),
    ]
    return Registry(rules)


def make_resolve(
    registry: Registry, extractors: dict[str, Any]
) -> Callable[[str, str], Resolved]:
    def resolve(_entry_id: str, target_url: str) -> Resolved:
        name = registry.match(target_url, resolve_redirect=lambda u: u)
        if name is None:
            raise ValueError(f"no extractor for {target_url}")
        result: Resolved = extractors[name].resolve(target_url)
        return result

    return resolve


class CatalogueStore:
    _snapshot: dict[str, CatalogueEntry]
    ready: bool

    def __init__(self) -> None:
        self._snapshot = {}
        self.ready = False

    def swap(self, entries: list[CatalogueEntry]) -> None:
        self._snapshot = {e.id: e for e in entries}  # atomic rebind
        self.ready = True

    def snapshot(self) -> dict[str, CatalogueEntry]:
        return self._snapshot


def make_is_alive(
    resolve: Callable[[str, str], Resolved],
) -> Callable[[Candidate], bool]:
    def is_alive(c: Candidate) -> bool:
        try:
            resolve("probe", c.target_url)
            return True
        except Exception:
            return False

    return is_alive


def make_handler(
    store: CatalogueStore,
    cache: ResolveCache,
    base_url: str,
    manifest_fetch: Callable[[str], str | None],
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            if path == "/playlist.m3u8":
                if not store.ready:
                    self._respond(503, "text/plain", b"not ready yet")
                    return
                body = render_playlist(
                    list(store.snapshot().values()), base_url=base_url
                )
                self._respond(200, _HLS_CT, body.encode())
                return

            if path.endswith("/m") and path.startswith("/stream/"):
                # /stream/<id>/m?u=<url>
                entry_id = path[len("/stream/") : -len("/m")]
                u_list = qs.get("u", [])
                if not u_list:
                    self._respond(400, "text/plain", b"missing u= param")
                    return
                upstream_url = u_list[0]
                status, ct, body = serve_child_manifest(
                    entry_id, upstream_url, fetch=manifest_fetch, base_url=base_url
                )
                self._respond(status, ct, body)
                return

            if path.startswith("/stream/"):
                entry_id = path[len("/stream/") :]
                status, ct_or_loc, body = serve_stream(
                    entry_id,
                    catalogue=store.snapshot(),
                    cache=cache,
                    fetch=manifest_fetch,
                    base_url=base_url,
                )
                if status == 302:
                    self.send_response(302)
                    self.send_header("Location", ct_or_loc)
                    self.end_headers()
                    return
                self._respond(status, ct_or_loc, body)
                return

            if path == "/health":
                snapshot = store.snapshot()
                payload = {
                    "status": "ok",
                    "ready": store.ready,
                    "streams": len(snapshot),
                    "rss_mb": round(psutil.Process().memory_info().rss / 1048576, 1),
                }
                self._respond(200, "application/json", json.dumps(payload).encode())
                return

            self._respond(404, "text/plain", b"not found")

        def _respond(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        @override
        def log_message(self, format: str, *args: Any) -> None:
            log.debug(format, *args)

    return Handler


def run_http_server(
    handler_cls: type[BaseHTTPRequestHandler], port: int = 8000
) -> None:
    server = ThreadingHTTPServer(("", port), handler_cls)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    log.info("HTTP server listening on port %d", port)


def build_app(
    cfg: config.Config,
) -> tuple[CatalogueStore, ResolveCache, Callable[[], None]]:
    fetcher = Fetcher()

    extractors: dict[str, Any] = {
        "ytdlp": YtDlpExtractor(),
        "direct": DirectHls(),
        "metatag": MetaTagExtractor(_http_get),
        "baltic": BalticResolver(_http_get, _http_post),
        "ipcamlive": IpcamliveResolver(_http_get),
    }
    registry = build_registry(extractors)
    resolve = make_resolve(registry, extractors)
    cache: ResolveCache = ResolveCache(resolve, clock=time.monotonic)

    try:
        import googleapiclient.discovery

        yt_client = googleapiclient.discovery.build(
            "youtube", "v3", developerKey=cfg.youtube_api_key
        )
    except Exception:
        yt_client = None

    from .sources.youtube_api import YoutubeApiSource
    from .sources.worldcams import WorldcamsSource
    from .sources.cxtvlive import CxtvliveSource

    search_query = "webcam live outdoor scenic"
    sources = [
        YoutubeApiSource(yt_client, search_query) if yt_client is not None else None,
        WorldcamsSource(fetcher),
        CxtvliveSource(fetcher),
    ]
    active_sources: list[Any] = [s for s in sources if s is not None]

    store = CatalogueStore()
    history: dict[str, Hist] = {}
    is_alive = make_is_alive(resolve)

    def youtube_live(ids: Any) -> set[str]:
        if yt_client is None:
            return set()
        yt_src = YoutubeApiSource(yt_client, search_query)
        return yt_src.live_ids(ids)

    def rebuild_once() -> None:
        log.info("starting catalogue rebuild")
        entries = build_catalogue(
            active_sources,
            is_alive=is_alive,
            youtube_live=youtube_live,
            history=history,
        )
        store.swap(entries)
        log.info("catalogue rebuilt: %d entries", len(entries))

    return store, cache, rebuild_once


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    cfg = config.load()
    store, cache, rebuild_once = build_app(cfg)

    handler_cls = make_handler(
        store,
        cache,
        cfg.public_base_url,
        manifest_fetch=lambda url: Fetcher(delay=0.0, retries=1).get(url),
    )
    run_http_server(handler_cls, port=8000)

    while True:
        try:
            rebuild_once()
        except Exception:
            log.exception("catalogue rebuild failed; will retry next cycle")
        time.sleep(cfg.catalogue_interval_hours * 3600)
