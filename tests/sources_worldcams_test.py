import pytest

from webcam_aggregator.fetch import FetcherProtocol
from webcam_aggregator.sources.worldcams import WorldcamsSource


class _FakeFetcher:
    _pages: dict[str, str]

    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get(self, url: str, _timeout: float = 20.0) -> str | None:
        return self._pages.get(url)


_LIST = '<div class="cam-promo__title"><a href="/x/cam-a">A</a></div>'
_CAM = (
    "<h1>Finse Railroad</h1>"
    'Category: &nbsp;<a href="/trains/">Trains</a>'
    'streams[0] = "<iframe src=\\"https://www.youtube.com/embed/aaaaaaaaaaa\\"></iframe>";'
)


def test_discovers_with_title_and_category() -> None:
    pages = {
        "https://worldcams.tv/list/?page=1": _LIST,
        "https://worldcams.tv/list/?page=2": "",  # empty → stop
        "https://worldcams.tv/x/cam-a": _CAM,
    }
    fetcher: FetcherProtocol = _FakeFetcher(pages)
    cands = list(WorldcamsSource(fetch=fetcher).discover())
    assert cands
    assert all(c.source == "worldcams" for c in cands)
    assert cands[0].title == "Finse Railroad"
    assert cands[0].category == "Trains"
    assert cands[0].predisc_key == "yt:aaaaaaaaaaa"


def test_stops_when_page_returns_no_links() -> None:
    pages = {
        "https://worldcams.tv/list/?page=1": "<html>no cam-promo links here</html>",
    }
    urls_fetched: list[str] = []

    class _TrackingFetcher:
        _urls: list[str]

        def __init__(self, tracked: list[str]) -> None:
            self._urls = tracked

        def get(self, url: str, _timeout: float = 20.0) -> str | None:
            self._urls.append(url)
            return pages.get(url, "")

    fetcher: FetcherProtocol = _TrackingFetcher(urls_fetched)
    cands = list(WorldcamsSource(fetch=fetcher).discover())
    assert cands == []
    # Should only have fetched the first list page (then stopped — no links)
    list_fetches = [u for u in urls_fetched if "/list/?page=" in u]
    assert list_fetches == ["https://worldcams.tv/list/?page=1"]


def test_skips_camera_page_returning_none() -> None:
    pages: dict[str, str] = {
        "https://worldcams.tv/list/?page=1": _LIST,
        "https://worldcams.tv/list/?page=2": "",
        # cam-a deliberately absent → fetcher returns None
    }
    fetcher: FetcherProtocol = _FakeFetcher(pages)
    cands = list(WorldcamsSource(fetch=fetcher).discover())
    assert cands == []


@pytest.mark.live
def test_worldcams_live_discovers_real_cams() -> None:
    from webcam_aggregator.fetch import Fetcher

    src = WorldcamsSource(fetch=Fetcher(delay=0.0))
    found = []
    for c in src.discover():
        found.append(c)
        if len(found) >= 3:  # just prove discovery works against the real site
            break
    assert len(found) >= 1
    assert any(c.title for c in found)
