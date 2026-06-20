from webcam_aggregator.registry import Registry


def test_host_rule_beats_m3u8_catchall():
    r = Registry(
        [(lambda u: "feratel" in u, "feratel"), (lambda u: u.endswith(".m3u8"), "hls")]
    )
    got = r.match("https://webtv.feratel.com/x.m3u8", resolve_redirect=lambda u: u)
    assert got == "feratel"


def test_redirect_resolved_first():
    r = Registry([(lambda u: "balticlivecam.com" in u, "baltic")])
    got = r.match(
        "https://tinyurl.com/abc",
        resolve_redirect=lambda u: "https://balticlivecam.com/cam",
    )
    assert got == "baltic"


def test_no_match_returns_none():
    r = Registry([(lambda u: False, "never")])
    assert r.match("https://x", resolve_redirect=lambda u: u) is None
