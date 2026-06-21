from __future__ import annotations

import json
import re
from typing import override

from ..fetch import thread_map
from ..models import Candidate
from .base import HtmlScraperSource, predisc_key, with_location_parts

_BASE = "https://www.camscape.com"

# camscape category slug -> a categories._MAP key (mapped to the unified taxonomy at
# build). The granular animal sub-cats all collapse to Animals; None -> "Other".
_CATEGORY: dict[str, str | None] = {
    "alpacas": "Animals",
    "bats": "Animals",
    "beaches": "Beaches",
    "bears": "Animals",
    "bees": "Animals",
    "big-cats": "Animals",
    "big-dogs": "Animals",
    "birds": "Birds",
    "boats": "Ships",
    "bovines": "Animals",
    "buildings": "Buildings",
    "business-miscellaneous": None,
    "christmas": "Christmas",
    "cityscapes": "Cities",
    "critters": "Animals",
    "culture": None,
    "deer": "Animals",
    "domestic-animals": "Animals",
    "elephants": "Animals",
    "entertainment": "Entertainment",
    "giraffes": "Animals",
    "goats": "Animals",
    "horses": "Animals",
    "landscapes": "Parks",
    "monsters": None,
    "nature": "Parks",
    "nightlife": "Bars",
    "pigs": "Animals",
    "planes-airports": "Airports",
    "primates": "Animals",
    "religion": "Religion",
    "rivers-seas-lakes": "Rivers Lakes",
    "roads": "Traffic",
    "sealife": "Animals",
    "shopping-district": None,
    "ski-resorts": "Ski Resorts",
    "space-astronomy": "Space",
    "squirrels": "Animals",
    "tortoises": "Animals",
    "tourist-attractions": "Sights",
    "trains-railways": "Trains",
    "urban-spaces": "Cities",
    "zebras": "Animals",
}

_CAT_PAGE = re.compile(r'href="(https://www\.camscape\.com/showing/[a-z0-9-]+/)"')
_PAGE = re.compile(r'href="(https://www\.camscape\.com/showing/[a-z0-9-]+/page/\d+/)"')
_CAM = re.compile(r'href="(https://www\.camscape\.com/webcam/[a-z0-9-]+/)"')
_TAG = re.compile(r'/showing/([a-z0-9-]+)/"')  # only the cam's own tags on a cam page
_LOC = re.compile(r'/location/([a-z0-9-]+)/"')
_CHANNEL = re.compile(r"[?&]channel=([A-Za-z0-9_]+)")

# ctx = (location parts general->specific, {stream index: name})
_Ctx = tuple[list[str], dict[str, str]]


def _streams(html: str) -> list[dict[str, object]]:
    # The cam's streams (every angle's embed url + name) live in a "streams":[{...}] JSON
    # blob; the rendered iframe only shows the active one, so parse the JSON.
    i = html.find('"streams":')
    if i < 0:
        return []
    try:
        arr, _ = json.JSONDecoder().raw_decode(html, html.index("[", i))
    except ValueError:
        return []
    return [s for s in arr if isinstance(s, dict)] if isinstance(arr, list) else []


class CamscapeSource(HtmlScraperSource[_Ctx]):
    name: str = "camscape"

    @override
    def _page_urls(self) -> list[str]:
        cats = sorted(
            set(_CAT_PAGE.findall(self._fetch.get(f"{_BASE}/showing/") or ""))
        )

        def crawl(cat: str) -> set[str]:
            out: set[str] = set()
            seen: set[str] = set()
            queue = [cat]
            while queue:
                p = queue.pop()
                if p in seen:
                    continue
                seen.add(p)
                h = self._fetch.get(p) or ""
                out.update(_CAM.findall(h))
                queue += [u for u in set(_PAGE.findall(h)) if u not in seen]
            return out

        cams: set[str] = set()
        for found in thread_map(crawl, cats):
            cams |= found
        return sorted(cams)

    @override
    def _page_meta(self, html: str, url: str) -> tuple[str | None, _Ctx]:
        category = next(
            (_CATEGORY.get(t) for t in _TAG.findall(html) if _CATEGORY.get(t)), None
        )
        # location tags are specific->general in the doc; with_location_parts wants
        # general->specific, so reverse + prettify.
        locs = list(dict.fromkeys(_LOC.findall(html)))
        location = [loc.replace("-", " ").title() for loc in reversed(locs)]
        names = {str(i): str(s.get("name") or "") for i, s in enumerate(_streams(html))}
        return category, (location, names)

    @override
    def _title_for(
        self, cand: Candidate, url: str, category: str | None, ctx: _Ctx
    ) -> str:
        location, names = ctx
        return with_location_parts(
            names.get(cand.angle_key or "", ""), location, drop=category or ""
        )

    @override
    def _candidates(self, html: str, url: str) -> list[Candidate]:
        out: list[Candidate] = []
        for i, s in enumerate(_streams(html)):
            embed = str(s.get("url") or "")
            if not embed:
                continue
            # Twitch player embeds need normalising to twitch.tv/<channel> for yt-dlp.
            m = _CHANNEL.search(embed) if "player.twitch.tv" in embed else None
            target = f"https://www.twitch.tv/{m.group(1)}" if m else embed
            out.append(
                Candidate(
                    title="",
                    angle_key=str(i),
                    category=None,
                    source=self.name,
                    source_page_url=url,
                    target_url=target,
                    predisc_key=predisc_key(target),
                )
            )
        return out
