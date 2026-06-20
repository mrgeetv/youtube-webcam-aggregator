from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from ..models import Candidate


class YoutubeApiSource:
    name: str = "youtube-api"
    _c: Any
    _query: str
    _max: int

    def __init__(self, client: Any, query: str, max_videos: int = 1000) -> None:
        self._c = client
        self._query = query
        self._max = max_videos

    def discover(self) -> Iterator[Candidate]:
        token: str | None = None
        n = 0
        while n < self._max:
            try:
                resp = (
                    self._c.search()
                    .list(
                        part="id,snippet",
                        type="video",
                        eventType="live",
                        maxResults=50,
                        order="date",
                        q=self._query,
                        pageToken=token,
                    )
                    .execute()
                )
            except Exception:
                return  # quota/403 or transient error → stop with what we've yielded
            for it in resp.get("items", []):
                vid = it["id"]["videoId"]
                n += 1
                yield Candidate(
                    title=it["snippet"]["title"],
                    angle_label=None,
                    angle_key=None,
                    category=None,
                    source="youtube-api",
                    source_page_url=f"https://www.youtube.com/watch?v={vid}",
                    target_url=f"https://www.youtube.com/watch?v={vid}",
                    hint="youtube",
                    predisc_key=f"yt:{vid}",
                )
            token = resp.get("nextPageToken")
            if not token:
                break

    def live_ids(self, video_ids: Iterable[str]) -> set[str]:
        ids = list(video_ids)
        live: set[str] = set()
        for i in range(0, len(ids), 50):
            chunk = ids[i : i + 50]
            resp = (
                self._c.videos()
                .list(part="snippet,liveStreamingDetails", id=",".join(chunk))
                .execute()
            )
            for it in resp.get("items", []):
                snip = it.get("snippet", {})
                details = it.get("liveStreamingDetails", {})
                if (
                    snip.get("liveBroadcastContent") == "live"
                    and "actualEndTime" not in details
                ):
                    live.add(it["id"])
        return live
