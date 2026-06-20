from __future__ import annotations

import json
import logging
import sys
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
from .extractors.base import Extractor, Resolved
from .extractors.baltic import BalticResolver
from .extractors.direct_hls import DirectHls
from .extractors.ipcamlive import IpcamliveResolver
from .extractors.metatag import MetaTagExtractor
from .extractors.ytdlp import YtDlpExtractor
from .fetch import MAX_BYTES, UA, Fetcher, is_safe_url
from .models import Candidate, CatalogueEntry
from .registry import Registry
from .serving import render_playlist, serve_child_manifest, serve_stream
from .sources.cxtvlive import CxtvliveSource
from .sources.worldcams import WorldcamsSource
from .sources.youtube_api import YoutubeApiSource

log = logging.getLogger("webcam-aggregator")
_HLS_CT = "application/vnd.apple.mpegurl"


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-check every redirect hop with is_safe_url (block internal-host SSRF)."""

    @override
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: Any,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        if not is_safe_url(newurl):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(SafeRedirectHandler())


def origin_of(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    return f"{p.scheme}://{p.hostname}/"


def _http_get(url: str) -> str:
    if not is_safe_url(url):
        raise ValueError(f"unsafe url: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with _OPENER.open(req, timeout=20) as r:
        data = r.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError(f"response too large from {url}")
        return data.decode("utf-8", "replace")


def _http_post(url: str, data: dict[str, str]) -> str:
    if not is_safe_url(url):
        raise ValueError(f"unsafe url: {url}")
    body = urllib.parse.urlencode(data).encode()
    headers = {
        "User-Agent": UA,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": origin_of(url),
    }
    req = urllib.request.Request(url, data=body, headers=headers)
    with _OPENER.open(req, timeout=20) as r:
        resp_data = r.read(MAX_BYTES + 1)
        if len(resp_data) > MAX_BYTES:
            raise ValueError(f"response too large from {url}")
        return resp_data.decode("utf-8", "replace")


def _is_ytdlp(u: str) -> bool:
    return any(
        h in u
        for h in ("youtube.com", "youtu.be", "twitch.tv", "dailymotion.com", "earthcam")
    )


def build_registry(extractors: dict[str, Extractor]) -> Registry:
    rules: list[tuple[Callable[[str], bool], str]] = [
        (lambda u: "balticlivecam.com" in u, "baltic"),
        (lambda u: "ipcamlive.com/player/player.php" in u, "ipcamlive"),
        (lambda u: "webtv.feratel.com" in u, "metatag"),
        (lambda u: _is_ytdlp(u), "ytdlp"),
        (lambda u: ".m3u8" in u or "worldcams.tv/player?url=" in u, "direct"),
    ]
    for _predicate, name in rules:
        if name not in extractors:
            raise ValueError(f"registry rule references unknown extractor {name!r}")
    return Registry(rules)


def make_resolve(
    registry: Registry, extractors: dict[str, Extractor]
) -> Callable[[str, str], Resolved]:
    def resolve(_entry_id: str, target_url: str) -> Resolved:
        name = registry.match(target_url, resolve_redirect=lambda u: u)
        if name is None:
            log.debug("no extractor matched target %s", target_url)
            raise ValueError(f"no extractor for {target_url}")
        return extractors[name].resolve(target_url)

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
        except Exception as exc:
            log.debug("liveness probe failed for %s: %s", c.target_url, exc)
            return False

    return is_alive


def make_handler(
    store: CatalogueStore,
    cache: ResolveCache,
    base_url: str,
    manifest_fetch: Callable[[str], str | None],
    source_counts: Callable[[], dict[str, int]],
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
                # /stream/<id>/m?u=<url>&sig=<hmac>
                entry_id = path[len("/stream/") : -len("/m")]
                u_list = qs.get("u", [])
                if not u_list:
                    self._respond(400, "text/plain", b"missing u= param")
                    return
                sig_list = qs.get("sig", [])
                if not sig_list:
                    self._respond(403, "text/plain", b"bad signature")
                    return
                status, ct, body = serve_child_manifest(
                    entry_id,
                    u_list[0],
                    sig_list[0],
                    fetch=manifest_fetch,
                    base_url=base_url,
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
                    "sources": source_counts(),
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


class _QuietHTTPServer(ThreadingHTTPServer):
    @override
    def handle_error(self, request: Any, client_address: Any) -> None:
        # A player closing a stream mid-write is normal, not an error to dump.
        if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


def run_http_server(
    handler_cls: type[BaseHTTPRequestHandler], port: int = 8000
) -> None:
    server = _QuietHTTPServer(("", port), handler_cls)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    log.info("HTTP server listening on port %d", port)


def build_app(
    cfg: config.Config,
) -> tuple[
    CatalogueStore,
    ResolveCache,
    Callable[[], None],
    Callable[[], dict[str, int]],
]:
    fetcher = Fetcher()

    extractors: dict[str, Extractor] = {
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
        log.exception("YouTube client init failed; youtube-api source disabled")
        yt_client = None

    yt_source = (
        YoutubeApiSource(yt_client, cfg.search_query) if yt_client is not None else None
    )
    active_sources: list[Any] = [
        s
        for s in (yt_source, WorldcamsSource(fetcher), CxtvliveSource(fetcher))
        if s is not None
    ]

    store = CatalogueStore()
    history: dict[str, Hist] = {}
    is_alive = make_is_alive(resolve)

    def youtube_live(ids: Any) -> set[str]:
        if yt_source is None:
            return set()
        return yt_source.live_ids(ids)

    def source_counts() -> dict[str, int]:
        return {name: (h.last_count or 0) for name, h in history.items()}

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

    return store, cache, rebuild_once, source_counts


def main() -> None:
    cfg = config.load()
    # Root stays at WARNING so third-party libs (googleapiclient, urllib3) never
    # log request URLs at DEBUG — those carry the API key as a query param. Only
    # our own loggers honour LOG_LEVEL.
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("webcam-aggregator").setLevel(
        getattr(logging, cfg.log_level, logging.INFO)
    )
    store, cache, rebuild_once, source_counts = build_app(cfg)

    manifest_fetcher = Fetcher(delay=0.0, retries=1)
    handler_cls = make_handler(
        store,
        cache,
        cfg.public_base_url,
        manifest_fetch=manifest_fetcher.get,
        source_counts=source_counts,
    )
    run_http_server(handler_cls, port=cfg.port)

    while True:
        try:
            rebuild_once()
        except Exception:
            log.exception("catalogue rebuild failed; will retry next cycle")
        time.sleep(cfg.catalogue_interval_hours * 3600)
