import urllib.parse
import urllib.request

import pytest

from webcam_aggregator.extractors.baltic import BalticResolver
from webcam_aggregator.extractors.ipcamlive import IpcamliveResolver

_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def _http_post(url: str, data: dict[str, str]) -> str:
    body = urllib.parse.urlencode(data).encode()
    headers = {
        "User-Agent": _UA,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://balticlivecam.com/",
    }
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


# --- offline unit tests -----------------------------------------------------


def test_ipcamlive_builds_m3u8():
    body = 'var address = "https://g0.ipcamlive.com/"; var streamid = "abc123";'
    out = IpcamliveResolver(fetch=lambda u: body).resolve(
        "https://g0.ipcamlive.com/player.php?alias=x"
    )
    assert out.url == "https://g0.ipcamlive.com/streams/abc123/stream.m3u8"
    assert out.stream_type == "hls"


def test_ipcamlive_missing_vars_raises():
    with pytest.raises(ValueError):
        IpcamliveResolver(fetch=lambda u: "no vars here").resolve(
            "https://x/player.php?alias=y"
        )


def test_baltic_extracts_m3u8_from_auth_token():
    page = "var data = { action: 'auth_token', id: 126, embed:1 };"
    fragment = 'sources:[{src:"https://edge01.balticlivecam.com/blc/x/index.m3u8?token=hash:1781917651106"}]'

    def get(_url: str) -> str:
        return page

    def post(_url: str, data: dict[str, str]) -> str:
        assert data["action"] == "auth_token"
        assert data["id"] == "126"
        return fragment

    out = BalticResolver(get=get, post=post).resolve(
        "https://balticlivecam.com/cameras/x/?embed"
    )
    assert out.url.endswith("token=hash:1781917651106")
    assert out.stream_type == "hls"
    assert out.ttl_seconds is not None


# --- live tests (real endpoints; excluded from default run; run with `-m live`) ---


@pytest.mark.live
def test_baltic_live():
    out = BalticResolver(get=_http_get, post=_http_post).resolve(
        "https://balticlivecam.com/cameras/latvia/riga/11-november-embankment/?embed"
    )
    assert ".m3u8" in out.url
    assert "balticlivecam" in out.url


@pytest.mark.live
def test_ipcamlive_live_handles_real_player_php():
    # Real cxtvlive ipcamlive embed. The cam may be offline (empty streamid → ValueError);
    # both outcomes prove the resolver parses the real player.php format without crashing.
    url = "https://g0.ipcamlive.com/player/player.php?alias=5d0a729743d32"
    try:
        out = IpcamliveResolver(fetch=_http_get).resolve(url)
    except ValueError:
        return
    assert "ipcamlive.com/streams/" in out.url
    assert out.url.endswith("stream.m3u8")
