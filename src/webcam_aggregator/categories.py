from __future__ import annotations

_MAP: dict[str, str] = {
    "Animals": "Animals",
    "Birds": "Animals",
    "Pets & Animals": "Animals",
    "Aquariums": "Aquariums",
    "Beaches": "Beaches",
    "Water": "Water & Waterways",
    "Rivers Lakes": "Water & Waterways",
    "Pools": "Water & Waterways",
    "Ships": "Ports & Ships",
    "Ports": "Ports & Ships",
    "Mountains": "Mountains",
    "Ski Resorts": "Mountains",
    "Volcanoes": "Mountains",
    "Parks": "Nature & Parks",
    "Cities": "Cities",
    "Sights": "Landmarks",
    "Bridges": "Landmarks",
    "Buildings": "Landmarks",
    "Castles": "Landmarks",
    "Monuments": "Landmarks",
    "Religion": "Religion",
    "Churches": "Religion",
    "Vatican": "Religion",
    "Airports": "Airports",
    "Traffic": "Traffic",
    "Autos & Vehicles": "Traffic",
    "Trains": "Trains & Railways",
    "Railway Stations": "Trains & Railways",
    "Bars": "Bars & Nightlife",
    "Bars Clubs Restaurants": "Bars & Nightlife",
    "Sports": "Sports",
    "Stadiums": "Sports",
    "Hotels": "Hotels",
    "Schools Universities": "Education",
    "Education": "Education",
    "Music": "Music",
    "Space": "Space",
    "Christmas": "Seasonal",
    "Radio Studios": "Studios",
}
_NATIVE_YT: set[str] = {
    "Entertainment",
    "Travel & Events",
    "People & Blogs",
    "News & Politics",
    "Science & Technology",
    "Nonprofits & Activism",
}


def map_category(raw: str | None) -> str:
    if not raw:
        return "Other"
    if raw in _MAP:
        return _MAP[raw]
    if raw in _NATIVE_YT:
        return raw
    return "Other"


# Every category that can appear as a playlist group-title — i.e. the full set a user
# may name in EXCLUDE_CATEGORIES. Source of truth; the README list is drift-guarded by
# a test (tests/categories_test.py).
ALL_CATEGORIES: tuple[str, ...] = tuple(
    sorted(set(_MAP.values()) | _NATIVE_YT | {"Other"})
)

_ALL_CASEFOLDED: frozenset[str] = frozenset(c.casefold() for c in ALL_CATEGORIES)


def unknown_categories(names: frozenset[str]) -> frozenset[str]:
    """Casefolded names that aren't real categories — likely typos in EXCLUDE_CATEGORIES."""
    return frozenset(n for n in names if n.casefold() not in _ALL_CASEFOLDED)
