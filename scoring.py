"""
Launch Check - scoring engine.

Takes a normalized page-data dict (produced by sources/steam.py or
sources/itchio.py) and turns it into the graded report described in
the build brief: an overall score, a checklist of known factors each
marked done/weak/missing, and a list of fixes ranked by how much they
would likely move the needle.

This module knows nothing about Steam or itch.io specifically - it
only understands the normalized shape below, so the same scorer grades
either source and any future source that maps into it:

{
    "title": str,
    "has_capsule_art": bool,
    "screenshot_count": int,
    "trailer_count": int,
    "tag_count": int,
    "description_length": int,       # characters, plain text
    "review_count": int | None,      # None = no review data at all yet
    "review_positive_ratio": float | None,  # 0.0-1.0
}
"""

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    key: str
    label: str
    status: str          # "done" | "weak" | "missing"
    detail: str
    weight: int           # how much this factor counts toward the overall score
    fixable: bool = True  # False for things like review score, which reflect reception


# (weight, fixable) per factor - screenshots and trailer weighted highest
# because they're both free to fix and shown to matter most for click-through
# on a store page; reviews is included per the brief but flagged as a signal,
# not a same-day fix.
WEIGHTS = {
    "capsule_art": 10,
    "screenshots": 20,
    "trailer": 20,
    "tags": 15,
    "description": 15,
    "reviews": 20,
}


def _status_score(status: str) -> float:
    return {"done": 1.0, "weak": 0.5, "missing": 0.0}[status]


def check_capsule_art(data: dict) -> CheckResult:
    ok = bool(data.get("has_capsule_art"))
    return CheckResult(
        "capsule_art", "Capsule / cover art",
        "done" if ok else "missing",
        "Present." if ok else "No capsule or cover image found on the page.",
        WEIGHTS["capsule_art"],
    )


def check_screenshots(data: dict) -> CheckResult:
    n = data.get("screenshot_count", 0)
    if n >= 8:
        status, detail = "done", f"{n} screenshots - comfortably above the 8+ that well-performing pages tend to show."
    elif n >= 4:
        status, detail = "weak", f"{n} screenshots - readable, but pages with 8+ typically convert better."
    else:
        status, detail = "missing", f"Only {n} screenshot(s) - too few for a visitor to judge the game."
    return CheckResult("screenshots", "Screenshot count", status, detail, WEIGHTS["screenshots"])


def check_trailer(data: dict) -> CheckResult:
    n = data.get("trailer_count", 0)
    if n >= 1:
        status, detail = "done", f"{n} trailer(s)/video(s) present."
    else:
        status, detail = "missing", "No trailer or gameplay video found - this is usually the single biggest gap."
    return CheckResult("trailer", "Trailer / video", status, detail, WEIGHTS["trailer"])


def check_tags(data: dict) -> CheckResult:
    n = data.get("tag_count", 0)
    if n >= 4:
        status, detail = "done", f"{n} tags/genres set - enough for the store's discovery algorithms to place the game well."
    elif n >= 2:
        status, detail = "weak", f"Only {n} tags/genres set - worth filling out further."
    else:
        status, detail = "missing", f"{n} tags/genres set - close to invisible to genre-based discovery."
    return CheckResult("tags", "Tag / genre coverage", status, detail, WEIGHTS["tags"])


def check_description(data: dict) -> CheckResult:
    n = data.get("description_length", 0)
    if n >= 800:
        status, detail = "done", f"~{n} characters - enough room to actually sell the game."
    elif n >= 200:
        status, detail = "weak", f"~{n} characters - present but thin."
    else:
        status, detail = "missing", f"~{n} characters - barely more than a tagline."
    return CheckResult("description", "Description length", status, detail, WEIGHTS["description"])


def check_reviews(data: dict) -> CheckResult:
    count = data.get("review_count")
    ratio = data.get("review_positive_ratio")
    if count is None:
        return CheckResult(
            "reviews", "Reviews", "missing",
            "No reviews yet - normal before/just after launch, but there's nothing here yet for buyers to judge by.",
            WEIGHTS["reviews"], fixable=False,
        )
    if count >= 50 and (ratio or 0) >= 0.70:
        status, detail = "done", f"{count} reviews, {round((ratio or 0) * 100)}% positive."
    elif count >= 10:
        status, detail = "weak", f"{count} reviews, {round((ratio or 0) * 100)}% positive - a thin or mixed signal so far."
    else:
        status, detail = "missing", f"Only {count} review(s) so far - too few to read as a signal either way."
    return CheckResult("reviews", "Reviews", status, detail, WEIGHTS["reviews"], fixable=False)


CHECKS = [check_capsule_art, check_screenshots, check_trailer, check_tags, check_description, check_reviews]


def score_page(data: dict) -> dict:
    results = [check(data) for check in CHECKS]
    total_weight = sum(r.weight for r in results)
    earned = sum(r.weight * _status_score(r.status) for r in results)
    overall = round(100 * earned / total_weight) if total_weight else 0

    fixes = sorted(
        (r for r in results if r.status != "done" and r.fixable),
        key=lambda r: r.weight * (1 - _status_score(r.status)),
        reverse=True,
    )

    return {
        "title": data.get("title", "Untitled"),
        "overall_score": overall,
        "checklist": [r.__dict__ for r in results],
        "ranked_fixes": [{"label": r.label, "detail": r.detail} for r in fixes],
    }


def compare(target: dict, similar: list[dict]) -> dict:
    """Very small comparison: how the target's raw numbers sit against
    a handful of similar games pulled the same way, per the brief."""
    def avg(key):
        vals = [s.get(key, 0) for s in similar if s.get(key) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    return {
        "compared_against": [s.get("title", "Untitled") for s in similar],
        "screenshot_count": {"this_game": target.get("screenshot_count", 0), "similar_avg": avg("screenshot_count")},
        "trailer_count": {"this_game": target.get("trailer_count", 0), "similar_avg": avg("trailer_count")},
        "tag_count": {"this_game": target.get("tag_count", 0), "similar_avg": avg("tag_count")},
    }
