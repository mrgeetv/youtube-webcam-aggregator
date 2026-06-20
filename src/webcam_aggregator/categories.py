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
