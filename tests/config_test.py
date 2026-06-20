import pytest

from webcam_aggregator import config


def test_requires_api_key():
    with pytest.raises(ValueError):
        config.load({})


def test_defaults_and_strip_trailing_slash():
    c = config.load(
        {"YOUTUBE_API_KEY": "k", "PUBLIC_BASE_URL": "https://cams.example/"}
    )
    assert c.public_base_url == "https://cams.example"
    assert c.catalogue_interval_hours == 6


def test_interval_floor_and_bad_value():
    floored = config.load({"YOUTUBE_API_KEY": "k", "CATALOGUE_INTERVAL_HOURS": "0"})
    assert floored.catalogue_interval_hours == 1
    bad = config.load({"YOUTUBE_API_KEY": "k", "CATALOGUE_INTERVAL_HOURS": "x"})
    assert bad.catalogue_interval_hours == 6
