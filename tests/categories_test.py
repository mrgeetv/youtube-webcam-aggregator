from webcam_aggregator.categories import map_category


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
