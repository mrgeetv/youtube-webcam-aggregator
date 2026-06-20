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


def test_new_field_defaults():
    c = config.load({"YOUTUBE_API_KEY": "k"})
    assert c.search_query  # non-empty built-in default
    assert c.log_level == "INFO"
    assert c.port == 8000


def test_new_fields_from_env():
    c = config.load(
        {
            "YOUTUBE_API_KEY": "k",
            "SEARCH_QUERY": "trains|railway",
            "LOG_LEVEL": "debug",
            "PORT": "9000",
        }
    )
    assert c.search_query == "trains|railway"
    assert c.log_level == "DEBUG"  # normalised to upper-case
    assert c.port == 9000


def test_exclude_categories_parsed_casefolded():
    c = config.load(
        {"YOUTUBE_API_KEY": "k", "EXCLUDE_CATEGORIES": "Religion, Sports ,music"}
    )
    assert c.exclude_categories == frozenset({"religion", "sports", "music"})


def test_exclude_categories_default_empty():
    assert config.load({"YOUTUBE_API_KEY": "k"}).exclude_categories == frozenset()
