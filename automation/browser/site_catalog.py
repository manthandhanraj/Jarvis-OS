"""Known sites and search-engine URL templates."""
from __future__ import annotations

from urllib.parse import quote_plus

SITES: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "google calendar": "https://calendar.google.com",
    "google maps": "https://www.google.com/maps",
    "maps": "https://www.google.com/maps",
    "linkedin": "https://www.linkedin.com/feed/",
    "github": "https://github.com",
    "stack overflow": "https://stackoverflow.com",
    "stackoverflow": "https://stackoverflow.com",
    "leetcode": "https://leetcode.com",
    "kaggle": "https://www.kaggle.com",
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://x.com",
    "reddit": "https://www.reddit.com",
    "netflix": "https://www.netflix.com",
    "prime video": "https://www.primevideo.com",
    "hotstar": "https://www.hotstar.com",
    "whatsapp web": "https://web.whatsapp.com",
    "spotify web": "https://open.spotify.com",
    "wikipedia": "https://www.wikipedia.org",
    "amazon": "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
}

SEARCH_ENGINES: dict[str, str] = {
    "google": "https://www.google.com/search?q={q}",
    "youtube": "https://www.youtube.com/results?search_query={q}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={q}",
    "github": "https://github.com/search?q={q}",
    "maps": "https://www.google.com/maps/search/{q}",
    "linkedin": "https://www.linkedin.com/search/results/all/?keywords={q}",
    "stackoverflow": "https://stackoverflow.com/search?q={q}",
    "amazon": "https://www.amazon.in/s?k={q}",
    "flipkart": "https://www.flipkart.com/search?q={q}",
}

_SITE_NAMES: tuple[str, ...] = tuple(sorted(SITES, key=len, reverse=True))
_ENGINE_NAMES: tuple[str, ...] = tuple(sorted(SEARCH_ENGINES, key=len, reverse=True))


def find_site(text: str) -> tuple[str, str] | None:
    lowered = text.lower()
    for name in _SITE_NAMES:
        if name in lowered:
            return name, SITES[name]
    return None


def find_engine(text: str) -> str | None:
    lowered = text.lower()
    for name in _ENGINE_NAMES:
        if name in lowered:
            return name
    return None


def build_search_url(engine: str, query: str) -> str:
    template = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["google"])
    return template.format(q=quote_plus(query))
