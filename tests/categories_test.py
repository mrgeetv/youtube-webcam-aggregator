import pytest

from webcam_aggregator.categories import map_category, unknown_categories


def test_known_mappings():
    assert map_category("Birds") == "Animals"
    assert map_category("Pets & Animals") == "Animals"
    assert map_category("Ski Resorts") == "Mountains"
    assert map_category("Railway Stations") == "Trains & Railways"
    assert map_category("Vatican") == "Religion"
    assert map_category("Weather") == "Weather"
    assert map_category("Sports Live") == "Sports"
    assert map_category("Watch Soccer Live") == "Sports"


def test_source_other_and_quality_tags_map_to_other_not_unmapped():
    # a source's literal "Other" (and non-content tags) -> our "Other", NOT "Unmapped"
    assert map_category("Other") == "Other"
    assert map_category("High Definition Hd") == "Other"


def test_native_youtube_kept():
    assert map_category("Entertainment") == "Entertainment"
    assert map_category("Travel & Events") == "Travel & Events"


def test_empty_falls_back_to_other():
    assert map_category(None) == "Other"
    assert map_category("") == "Other"


def test_unknown_category_is_flagged_not_buried_in_other():
    # a source that DID give a category we don't recognise -> distinct "Unmapped
    # Category" (visible + logged), NOT silently "Other"
    assert map_category("Something Random") == "Unmapped Category"


def test_unmapped_category_logged_once(caplog: pytest.LogCaptureFixture):
    import logging

    with caplog.at_level(logging.WARNING, logger="webcam-aggregator.categories"):
        assert map_category("Zqx Unmapped Probe") == "Unmapped Category"
        assert map_category("Zqx Unmapped Probe") == "Unmapped Category"  # 2nd: no log
    hits = [r for r in caplog.records if "Zqx Unmapped Probe" in r.getMessage()]
    assert len(hits) == 1


def test_all_categories_set():
    from webcam_aggregator.categories import ALL_CATEGORIES

    assert "Animals" in ALL_CATEGORIES  # unified
    assert "Trains & Railways" in ALL_CATEGORIES
    assert "Travel & Events" in ALL_CATEGORIES  # native YouTube, passes through
    assert "Other" in ALL_CATEGORIES  # fallback (source gave no category)
    assert "Unmapped Category" in ALL_CATEGORIES  # source gave one we don't map
    assert list(ALL_CATEGORIES) == sorted(ALL_CATEGORIES)  # stable, sorted order


def test_unknown_categories_returns_empty_for_valid():
    assert unknown_categories(frozenset({"animals", "religion"})) == frozenset()


def test_unknown_categories_returns_typos():
    assert unknown_categories(frozenset({"relgion", "animals"})) == frozenset(
        {"relgion"}
    )


def test_readme_documents_every_category():
    """Drift guard: every excludable category must be listed in the README, so users
    always know what they can pass to EXCLUDE_CATEGORIES."""
    from pathlib import Path

    from webcam_aggregator.categories import ALL_CATEGORIES

    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text("utf-8")
    missing = [c for c in ALL_CATEGORIES if c not in readme]
    assert not missing, f"categories missing from README: {missing}"
