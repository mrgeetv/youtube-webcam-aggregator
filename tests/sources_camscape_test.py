from webcam_aggregator.sources.camscape import CamscapeSource

_BASE = "https://www.camscape.com"


def _cam_page(
    streams_json: str, tags: str = "beaches", locs: tuple[str, ...] = ()
) -> str:
    tag_html = "".join(f'<a href="/showing/{t}/">x</a>' for t in tags.split())
    loc_html = "".join(f'<a href="/location/{loc}/">x</a>' for loc in locs)
    return f'{tag_html}{loc_html}<script>var c={{"streams":{streams_json}}};</script>'


class _FakeFetch:
    _pages: dict[str, str]

    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get(self, url: str, _timeout: float = 20.0) -> str | None:
        return self._pages.get(url)


def test_camscape_discover_multistream_category_location_and_dedup():
    cam = f"{_BASE}/webcam/dawlish-webcams/"
    streams = (
        '[{"name":"Marine Parade Cam","url":"https://content.jwplatform.com/players/A.html"},'
        '{"name":"Salty Cottage Cam","url":"https://www.youtube.com/embed/aaaaaaaaaaa"}]'
    )
    pages = {
        f"{_BASE}/showing/": f'<a href="{_BASE}/showing/beaches/">B</a>',
        f"{_BASE}/showing/beaches/": f'<a href="{cam}">d</a>',
        cam: _cam_page(
            streams, tags="beaches trains-railways", locs=("devon", "england")
        ),
    }
    cands = list(CamscapeSource(_FakeFetch(pages)).discover())
    assert len(cands) == 2  # both angles
    titles = {c.title for c in cands}
    # names from the JSON, geo from /location tags (specific->general), category dropped
    assert "Marine Parade Cam — Devon, England" in titles
    assert "Salty Cottage Cam — Devon, England" in titles
    assert all(c.category == "Beaches" for c in cands)  # first mapped tag
    assert all(c.source == "camscape" for c in cands)
    yt = next(c for c in cands if "youtube" in c.target_url)
    assert yt.predisc_key == "yt:aaaaaaaaaaa"  # dedups with youtube-api


def test_camscape_normalises_twitch_embed_for_ytdlp():
    cam = f"{_BASE}/webcam/x/"
    streams = '[{"name":"Live","url":"https://player.twitch.tv/?channel=foo&parent=www.camscape.com"}]'
    pages = {
        f"{_BASE}/showing/": f'<a href="{_BASE}/showing/cityscapes/">C</a>',
        f"{_BASE}/showing/cityscapes/": f'<a href="{cam}">x</a>',
        cam: _cam_page(streams, tags="cityscapes"),
    }
    cands = list(CamscapeSource(_FakeFetch(pages)).discover())
    assert cands[0].target_url == "https://www.twitch.tv/foo"
