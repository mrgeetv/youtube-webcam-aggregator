from webcam_aggregator.fetch import FetcherProtocol
from webcam_aggregator.sources.worldcams import WorldcamsSource


class _FakeFetcher:
    _pages: dict[str, str]

    def __init__(self, pages: dict[str, str]) -> None:
        self._pages = pages

    def get(self, url: str, _timeout: float = 20.0) -> str | None:
        return self._pages.get(url)


_LIST = (
    '<div class="cam-promo__title">'
    '<a href="/norway/finse/railroad-station">A</a></div>'
)
_CAM = (
    "<h1>Finse Railroad Station</h1>"
    'Category: &nbsp;<a href="/trains/">Trains</a>'
    'streams[0] = "<iframe src=\\"https://www.youtube.com/embed/aaaaaaaaaaa\\"></iframe>";'
)


def test_discovers_with_title_and_category() -> None:
    pages = {
        "https://worldcams.tv/list/?page=1": _LIST,
        "https://worldcams.tv/list/?page=2": "",  # empty → stop
        "https://worldcams.tv/norway/finse/railroad-station": _CAM,
    }
    fetcher: FetcherProtocol = _FakeFetcher(pages)
    cands = list(WorldcamsSource(fetch=fetcher).discover())
    assert cands
    assert all(c.source == "worldcams" for c in cands)
    # only the parts the h1 doesn't already name are appended (place is in the h1)
    assert cands[0].title == "Finse Railroad Station — Norway"
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
