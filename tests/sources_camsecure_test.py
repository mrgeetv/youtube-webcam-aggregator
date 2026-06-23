from webcam_aggregator.sources.camsecure import CamSecureSource

_BASE = "https://www.camsecure.co.uk"
_INDEX = f"{_BASE}/Camsecure_Live_Demo_Index.html"

_INDEX_HTML = """
<a href="/Camsecure3/Brixham_Harbour.html">Brixham</a>
<a href="/CoastwatchRedcarWebcam.html">Redcar</a>
<a href="/oban%20bay%20webcam.html">Oban</a>
<a href="/oban bay webcam.html">Oban dup (literal spaces)</a>
<a href="/dead_webcam.html">Dead</a>
<a href="/WebcamHosting.html">Hosting product page</a>
<a href="/Camsecure_Contact_us.html">Contact</a>
"""

_PAGES = {
    _INDEX: _INDEX_HTML,
    f"{_BASE}/Camsecure3/Brixham_Harbour.html": (
        "<title>Brixham Harbour Live Streaming Webcam</title>"
        '<iframe src="https://camsecure.co/httpswebcam/camsecure/brixham1.html"></iframe>'
    ),
    "https://camsecure.co/httpswebcam/camsecure/brixham1.html": (
        '<video><source src="/HLS/brixham.m3u8" type="application/x-mpegURL"></video>'
    ),
    # title LEADS with boilerplate -> must fall back to the "from <place>" tail
    f"{_BASE}/CoastwatchRedcarWebcam.html": (
        "<title>Live Coastal Shipping Webcam from Coastwatch Redcar</title>"
        '<iframe src="https://camsecure.co/httpswebcam/camsecure/redcar1.html"></iframe>'
    ),
    "https://camsecure.co/httpswebcam/camsecure/redcar1.html": (
        '<source src="//camsecure.uk/HLS/redcar1.m3u8">'
    ),
    f"{_BASE}/oban%20bay%20webcam.html": (
        "<title>Oban Bay Live Webcam</title>"
        '<iframe src="https://camsecure.uk/httpswebcam/camsecure/greystones.html"></iframe>'
    ),
    "https://camsecure.uk/httpswebcam/camsecure/greystones.html": (
        '<source src="//camsecure.uk/HLS/greystonesoban.m3u8">'
    ),
    # player page exists but has no stream -> dropped
    f"{_BASE}/dead_webcam.html": (
        "<title>Dead Cam Webcam</title>"
        '<iframe src="https://camsecure.co/httpswebcam/camsecure/dead.html"></iframe>'
    ),
    "https://camsecure.co/httpswebcam/camsecure/dead.html": "<p>offline</p>",
}


class _FakeFetch:
    def get(self, url: str, _timeout: float = 20.0) -> str | None:
        return _PAGES.get(url)


def test_camsecure_discover_titles_dedup_and_filtering():
    cands = list(CamSecureSource(_FakeFetch()).discover())
    by_title = {c.title: c for c in cands}

    # exactly the 3 real, live cams (dead = no stream, hosting/contact = not cams)
    assert set(by_title) == {"Brixham Harbour", "Coastwatch Redcar", "Oban Bay"}

    # trailing-boilerplate strip + the "from <place>" fallback for a lead-boilerplate title
    assert "Coastwatch Redcar" in by_title

    # direct HLS targets, protocol-relative source resolved against the player host
    assert (
        by_title["Brixham Harbour"].target_url
        == "https://camsecure.co/HLS/brixham.m3u8"
    )
    assert (
        by_title["Oban Bay"].target_url
        == "https://camsecure.uk/HLS/greystonesoban.m3u8"
    )

    # the literal-space + %20 Oban links collapse to a single cam
    assert sum(1 for c in cands if c.title == "Oban Bay") == 1

    for c in cands:
        assert c.source == "camsecure"
        assert c.category is None  # no category -> "Other"
        assert (c.predisc_key or "").startswith("hls:")  # dedups direct HLS
