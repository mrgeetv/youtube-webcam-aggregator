from webcam_aggregator.sources.base import extract_candidates


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


def test_channel_has_no_predisc_key():
    html = '<a href="https://www.youtube.com/@SomeCam/live">live</a>'
    # NOTE: a bare channel link with no attribution prefix is a stream candidate
    cands = list(extract_candidates(html, page_url="https://s/x", source="cxtvlive"))
    assert cands and cands[0].predisc_key is None
