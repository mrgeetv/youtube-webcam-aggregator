from webcam_aggregator.categories import map_category


def test_known_mappings():
    assert map_category("Birds") == "Animals"
    assert map_category("Pets & Animals") == "Animals"
    assert map_category("Ski Resorts") == "Mountains"
    assert map_category("Railway Stations") == "Trains & Railways"


def test_native_youtube_kept():
    assert map_category("Entertainment") == "Entertainment"
    assert map_category("Travel & Events") == "Travel & Events"


def test_unknown_and_empty_uncategorised():
    assert map_category(None) == "Uncategorised"
    assert map_category("") == "Uncategorised"
    assert map_category("Something Random") == "Uncategorised"
