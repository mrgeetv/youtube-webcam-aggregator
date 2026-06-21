from webcam_aggregator.sources.base import (
    extract_candidates,
    location_from_url,
    with_location,
)


def test_location_from_url():
    base = "https://worldcams.tv"
    # full path, most-specific first
    assert (
        location_from_url(f"{base}/italy/venice/rialto-bridge")
        == "Rialto Bridge, Venice, Italy"
    )
    assert (
        location_from_url(f"{base}/barbados/barbados-beaches")
        == "Barbados Beaches, Barbados"
    )
    assert (
        location_from_url("https://www.cxtvlive.com/live-camera/yosemite-falls")
        == "Yosemite Falls"
    )
    assert location_from_url("https://worldcams.tv/") == ""


def test_with_location_appends_only_new_parts():
    wc = "https://worldcams.tv"
    # generic title gains the distinguishing place (redundant country/word dropped)
    assert (
        with_location("Italy Beaches Webcam", f"{wc}/italy/cinque-terre/beach")
        == "Italy Beaches Webcam — Cinque Terre"
    )
    # h1 already names the place -> only the country is added (no double-up)
    assert (
        with_location("Dusseldorf Airport Webcam", f"{wc}/germany/dusseldorf/airport")
        == "Dusseldorf Airport Webcam — Germany"
    )
    # apostrophes/parens normalised so the place still dedupes
    assert (
        with_location(
            "Hog's Breath Saloon (Key West) Webcam",
            f"{wc}/united-states/key-west/hogs-breath-saloon",
        )
        == "Hog's Breath Saloon (Key West) Webcam — United States"
    )
    # title already names everything -> no suffix
    assert (
        with_location("Cinque Terre Beach Italy", f"{wc}/italy/cinque-terre/beach")
        == "Cinque Terre Beach Italy"
    )
    # empty title -> full location, most-specific first
    assert (
        with_location("", f"{wc}/italy/cinque-terre/beach")
        == "Beach, Cinque Terre, Italy"
    )


def test_with_location_drops_category_from_suffix():
    wc = "https://worldcams.tv"
    url = f"{wc}/spain/gran-canaria/beaches"
    # the category is shown as the group, so keep it out of the suffix
    assert (
        with_location("Playa del Inglés", url, drop="Beaches")
        == "Playa del Inglés — Gran Canaria, Spain"
    )
    # a drop value not present in the path leaves the suffix unchanged
    assert (
        with_location("Maspalomas Beach", url, drop="Webcams")
        == "Maspalomas Beach — Beaches, Gran Canaria, Spain"
    )


def test_ignores_source_attribution_link():
    html = '<div class="player"></div> Source: <a href="https://www.youtube.com/@SlowTVLive">x</a>'
    cands = list(
        extract_candidates(html, page_url="https://worldcams.tv/x", source="worldcams")
    )
    assert cands == []


def test_youtube_playlist_embed():
    html = '<iframe src="https://www.youtube.com/embed?list=UUabc&playnext=1"></iframe>'
    cands = list(
        extract_candidates(
            html, page_url="https://www.cxtvlive.com/live-camera/x", source="cxtvlive"
        )
    )
    assert any("list=UUabc" in c.target_url for c in cands)


def test_youtube_video_predisc_key():
    html = '<iframe src="https://www.youtube.com/embed/aaaaaaaaaaa"></iframe>'
    cands = list(extract_candidates(html, page_url="https://s/x", source="cxtvlive"))
    assert cands[0].predisc_key == "yt:aaaaaaaaaaa"


def test_multiangle_distinct_keys():
    html = (
        'streams[0] = "<iframe src=\\"https://www.youtube.com/embed/aaaaaaaaaaa\\"></iframe>";'
        'streams[1] = "<iframe src=\\"https://www.youtube.com/embed/bbbbbbbbbbb\\"></iframe>";'
    )
    cands = list(
        extract_candidates(html, page_url="https://worldcams.tv/x", source="worldcams")
    )
    assert len({c.angle_key for c in cands}) == 2


def test_single_quote_streams_keyed_by_stream_id():
    # worldcams multi-cam pages use streams[<id>] = '<iframe …>' (SINGLE quotes),
    # keyed by the site's stream-id (not a 0..n index). Each candidate's angle_key
    # IS that stream-id, so it survives the page reordering its cams.
    html = (
        "streams[0] = '<iframe src=\\\"https://www.youtube.com/embed/aaaaaaaaaaa\\\"></iframe>';"
        "streams[1378] = '<iframe src=\\\"https://en.example.es/cam\\\"></iframe>';"
    )
    cands = list(
        extract_candidates(html, page_url="https://worldcams.tv/x", source="worldcams")
    )
    by_key = {c.angle_key: c.target_url for c in cands}
    assert by_key["0"].endswith("/embed/aaaaaaaaaaa")
    assert by_key["1378"] == "https://en.example.es/cam"


def test_channel_has_no_predisc_key():
    html = '<a href="https://www.youtube.com/@SomeCam/live">live</a>'
    # NOTE: a bare channel link with no attribution prefix is a stream candidate
    cands = list(extract_candidates(html, page_url="https://s/x", source="cxtvlive"))
    assert cands and cands[0].predisc_key is None
