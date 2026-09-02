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
    r = requests.get(
        "https://store.steampowered.com/api/storesearch/",
        params={"term": genre_or_term, "l": "english", "cc": cc},
        headers=HEADERS, timeout=10,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    ids = [str(i["id"]) for i in items if str(i["id"]) != exclude_appid]
    return ids[:limit]


def normalize(details: dict, reviews: dict) -> dict:
    return {
        "title": details.get("name", "Untitled"),
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
