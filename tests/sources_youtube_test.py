from typing import Any

from webcam_aggregator.sources.youtube_api import YoutubeApiSource


class _Req:
    _result: Any

    def __init__(self, result: Any) -> None:
        self._result = result

    def execute(self) -> Any:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _Endpoint:
    _results: list[Any]
    _i: int

    def __init__(self, results: list[Any]) -> None:
        self._results = results
        self._i = 0

    def list(self, **_kwargs: Any) -> _Req:
        r = self._results[min(self._i, len(self._results) - 1)]
        self._i += 1
        return _Req(r)


class _FakeClient:
    _search: _Endpoint
    _videos: _Endpoint

    def __init__(
        self,
        search: list[Any] | None = None,
        videos: list[Any] | None = None,
    ) -> None:
        self._search = _Endpoint(search or [])
        self._videos = _Endpoint(videos or [])

    def search(self) -> _Endpoint:
        return self._search

    def videos(self) -> _Endpoint:
        return self._videos


def _item(vid: str, title: str = "t") -> dict[str, Any]:
    return {"id": {"videoId": vid}, "snippet": {"title": title}}


def test_discover_paginates_and_stops() -> None:
    page1 = {"items": [_item("aaaaaaaaaaa")], "nextPageToken": "T"}
    page2 = {"items": [_item("bbbbbbbbbbb")]}  # no nextPageToken → stop
    src = YoutubeApiSource(_FakeClient(search=[page1, page2]), query="cam")
    cands = list(src.discover())
    assert [c.predisc_key for c in cands] == ["yt:aaaaaaaaaaa", "yt:bbbbbbbbbbb"]


def test_discover_stops_on_quota_error() -> None:
    src = YoutubeApiSource(_FakeClient(search=[RuntimeError("403 quota")]), query="cam")
    assert list(src.discover()) == []


def test_live_ids_filters_offair() -> None:
    resp = {
        "items": [
            {
                "id": "live1",
                "snippet": {"liveBroadcastContent": "live"},
                "liveStreamingDetails": {},
            },
            {
                "id": "ended",
                "snippet": {"liveBroadcastContent": "live"},
                "liveStreamingDetails": {"actualEndTime": "x"},
            },
            {
                "id": "vod",
                "snippet": {"liveBroadcastContent": "none"},
                "liveStreamingDetails": {},
            },
        ]
    }
    src = YoutubeApiSource(_FakeClient(videos=[resp]), query="cam")
    assert src.live_ids(["live1", "ended", "vod"]) == {"live1"}
