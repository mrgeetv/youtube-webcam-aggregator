from webcam_aggregator.categories import map_category, unknown_categories


def test_known_mappings():
    assert map_category("Birds") == "Animals"
    assert map_category("Pets & Animals") == "Animals"
    assert map_category("Ski Resorts") == "Mountains"
    assert map_category("Railway Stations") == "Trains & Railways"
    assert map_category("Vatican") == "Religion"


def test_native_youtube_kept():
    assert map_category("Entertainment") == "Entertainment"
    assert map_category("Travel & Events") == "Travel & Events"


def test_unknown_and_empty_fall_back_to_other():
    assert map_category(None) == "Other"
    assert map_category("") == "Other"
    assert map_category("Something Random") == "Other"


def test_all_categories_set():
    from webcam_aggregator.categories import ALL_CATEGORIES

    assert "Animals" in ALL_CATEGORIES  # unified
    assert "Trains & Railways" in ALL_CATEGORIES
    assert "Travel & Events" in ALL_CATEGORIES  # native YouTube, passes through
    assert "Other" in ALL_CATEGORIES  # fallback
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
