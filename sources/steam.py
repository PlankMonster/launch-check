"""
Pulls public, no-signup Steam store data for one app, plus a handful
of similar games for comparison. Every endpoint here is Steam's public
storefront API - the same data SteamDB and dozens of other third-party
tools have queried for over a decade. No API key, no Steamworks account,
no partner access of any kind.
"""

import re
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (LaunchCheck/1.0)"}

# Steam's appdetails "type" field for anything that isn't a full game -
# used so a DLC/soundtrack/demo page doesn't get graded as if it were one.
NON_GAME_TYPE_LABELS = {
    "dlc": "DLC",
    "music": "a soundtrack",
    "demo": "a demo",
    "video": "a video",
    "hardware": "hardware",
    "series": "a series listing",
    "episode": "an episode listing",
    "advertising": "an advertisement",
    "mod": "a mod",
    "application": "an application",
}


def describe_non_game_type(steam_type: str) -> str:
    return NON_GAME_TYPE_LABELS.get(steam_type, "not a full game listing")


def extract_appid(url: str) -> str | None:
    m = re.search(r"store\.steampowered\.com/app/(\d+)", url)
    return m.group(1) if m else None


def fetch_appdetails(appid: str, cc: str = "gb") -> dict | None:
    r = requests.get(
        "https://store.steampowered.com/api/appdetails",
        params={"appids": appid, "cc": cc},
        headers=HEADERS, timeout=10,
    )
    r.raise_for_status()
    payload = r.json().get(appid, {})
    if not payload.get("success"):
        return None
    return payload["data"]


def fetch_reviews(appid: str) -> dict:
    r = requests.get(
        f"https://store.steampowered.com/appreviews/{appid}",
        params={"json": 1, "num_per_page": 0, "language": "all"},
        headers=HEADERS, timeout=10,
    )
    r.raise_for_status()
    summary = r.json().get("query_summary", {})
    total = summary.get("total_reviews") or 0
    positive = summary.get("total_positive") or 0
    return {
        "review_count": total or None,
        "review_positive_ratio": (positive / total) if total else None,
    }


def search_similar(genre_or_term: str, cc: str = "gb", limit: int = 5, exclude_appid: str | None = None) -> list[str]:
    """Loose text search - only kept as a fallback for the rare case a
    game has no genre at all to filter by. See search_similar_by_tag()
    for the real "similar games" lookup: this one just matches the term
    against titles, so e.g. searching "Action" mostly returns games with
    the word "Action" in their name, not games that are actually tagged
    Action - not genuinely a "similar games" comparison."""
    r = requests.get(
        "https://store.steampowered.com/api/storesearch/",
        params={"term": genre_or_term, "l": "english", "cc": cc},
        headers=HEADERS, timeout=10,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    ids = [str(i["id"]) for i in items if str(i["id"]) != exclude_appid]
    return ids[:limit]


_TAG_ID_CACHE: dict[str, int] | None = None


def _tag_name_to_id(name: str) -> int | None:
    """Looks up a genre name (e.g. "Action") against Steam's public
    community-tag list to get the numeric tag id search_similar_by_tag()
    needs. This is a different id space from the small ~20-genre id Steam
    already puts on appdetails ("genres"), so it has to be looked up by
    name, not reused directly. Cached in-process since the tag list is
    the same for every request and rarely changes."""
    global _TAG_ID_CACHE
    if _TAG_ID_CACHE is None:
        r = requests.get(
            "https://store.steampowered.com/tagdata/populartags/english",
            headers=HEADERS, timeout=10,
        )
        r.raise_for_status()
        _TAG_ID_CACHE = {t["name"].lower(): t["tagid"] for t in r.json()}
    return _TAG_ID_CACHE.get(name.lower())


def search_similar_by_tag(tag_id: int, cc: str = "gb", limit: int = 5, exclude_appid: str | None = None) -> list[str]:
    """The real "similar games" lookup - uses the same tag-filtered search
    Steam's own store search page uses, so results are actually games
    that share the tag, not just games whose title contains the genre
    word. category1=998 restricts results to full games (excludes DLC/
    soundtracks/software from turning up in the comparison set)."""
    r = requests.get(
        "https://store.steampowered.com/search/results/",
        params={
            "query": "", "tags": tag_id, "category1": 998,
            "supportedlang": "english", "ndl": 1, "json": 1,
            "cc": cc, "l": "english",
        },
        headers=HEADERS, timeout=10,
    )
    r.raise_for_status()
    ids = []
    for item in r.json().get("items", []):
        m = re.search(r"/apps/(\d+)/", item.get("logo", ""))
        if m and m.group(1) != exclude_appid:
            ids.append(m.group(1))
    return ids[:limit]


def normalize(details: dict, reviews: dict) -> dict:
    return {
        "title": details.get("name", "Untitled"),
        "steam_type": details.get("type", "game"),
        "has_capsule_art": bool(details.get("header_image")),
        "screenshot_count": len(details.get("screenshots", []) or []),
        "trailer_count": len(details.get("movies", []) or []),
        "tag_count": len(details.get("genres", []) or []) + len(details.get("categories", []) or []),
        "description_length": len(details.get("detailed_description", "") or ""),
        **reviews,
    }


def fetch_and_normalize(appid: str, cc: str = "gb") -> dict | None:
    details = fetch_appdetails(appid, cc=cc)
    if details is None:
        return None
    reviews = fetch_reviews(appid)
    return normalize(details, reviews)


def fetch_similar_normalized(details: dict, appid: str, cc: str = "gb", limit: int = 5) -> list[dict]:
    tag_id = None
    for genre in details.get("genres", []):
        tag_id = _tag_name_to_id(genre.get("description", ""))
        if tag_id is not None:
            break

    if tag_id is not None:
        ids = search_similar_by_tag(tag_id, cc=cc, limit=limit, exclude_appid=appid)
    else:
        genres = details.get("genres", [])
        term = genres[0]["description"] if genres else details.get("name", "")
        ids = search_similar(term, cc=cc, limit=limit, exclude_appid=appid)

    out = []
    for sid in ids:
        d = fetch_appdetails(sid, cc=cc)
        if d is None:
            continue
        out.append(normalize(d, fetch_reviews(sid)))
    return out
