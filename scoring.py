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
    weight: int            # how much this factor counts toward the overall score
    advice: str = ""       # longer, actionable guidance - only set when status isn't "done"
    fixable: bool = True   # False for things like review score, which reflect reception


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

# Longer, actionable guidance shown alongside a weak/missing checklist item.
# Kept separate from the short `detail` diagnosis above so the score-driving
# logic never has to change to update this wording.
ADVICE = {
    "capsule_art": (
        "This is the very first thing people see, in search results and store "
        "listings, before they even reach your page. Without one, your game "
        "looks unfinished or abandoned at a glance. Use a high-contrast image "
        "showing your most recognizable character, scene, or color palette — "
        "avoid dense text, it goes illegible at thumbnail size."
    ),
    "screenshots_weak": (
        "Add 3-5 more so the set together shows: (1) actual gameplay, not "
        "menus, (2) variety — different areas, enemies, or moments, since "
        "near-identical shots read as 'short or repetitive game,' (3) your "
        "single most striking visual as shot #1 or #2, since most browsers "
        "judge from the first couple before scrolling."
    ),
    "screenshots_missing": (
        "A visitor deciding whether to look further needs at least 5-8 images "
        "to judge the game at all. Lead with your best or most unusual moment, "
        "then spread the rest across different parts of the game."
    ),
    "trailer": (
        "This is usually the single biggest gap, because both stores give "
        "trailers better placement in their discovery feeds, and most buyers "
        "will watch 15 seconds of gameplay before reading a paragraph. It "
        "doesn't need polish — a raw 30-60 second gameplay clip with real "
        "audio, showing 2-3 different moments, beats having none."
    ),
    "tags": (
        "Tags control who ever sees your page, before a human judges it — "
        "under-tagging costs you visibility regardless of how good the page "
        "itself is. Fill in every genuinely accurate tag, including specific "
        "ones (art style, a defining mechanic, platform) not just broad genre "
        "labels."
    ),
    "description": (
        "A thin description leaves visitors guessing what makes the game "
        "worth their time. Cover: what you actually do minute-to-minute, what "
        "makes it different from similar games, and 2-3 concrete specifics (a "
        "number, a mechanic, a setting detail) rather than only mood words "
        "like 'immersive' or 'epic.'"
    ),
    "reviews": (
        "This isn't something to fix directly on the page — it reflects what "
        "people who've already played think. If it's early or thin, the "
        "highest-leverage move is usually strengthening the page itself "
        "(screenshots, trailer, description) so the players who do arrive are "
        "the right audience for the game — that's what tends to produce good "
        "reviews, not the other way around."
    ),
}


def _status_score(status: str) -> float:
    return {"done": 1.0, "weak": 0.5, "missing": 0.0}[status]


def _count_word(n: int, singular: str, plural: str) -> str:
    """"1 screenshot" not "1 screenshot(s)" - the literal "(s)" read as
    broken/unfinished copy at n == 1, which is a common case (most
    checklist items that aren't "done" sit right at 0 or 1)."""
    return f"{n} {singular}" if n == 1 else f"{n} {plural}"


def check_capsule_art(data: dict) -> CheckResult:
    ok = bool(data.get("has_capsule_art"))
    return CheckResult(
        "capsule_art", "Capsule / cover art",
        "done" if ok else "missing",
        "Present." if ok else "No capsule or cover image found on the page.",
        WEIGHTS["capsule_art"],
        advice="" if ok else ADVICE["capsule_art"],
    )


def _with_similar_avg_prefix(base_advice: str, noun: str, n: int, similar_avg: float | None) -> str:
    """Lead with the real similar-games number when it actually makes the
    point (the average is higher than this game's own count) - falls back
    to the fixed wording untouched when there's nothing to compare against
    (e.g. itch.io, which has no similar-games search yet) or when the
    average wouldn't reinforce the point anyway."""
    if similar_avg is not None and similar_avg > n:
        return f"Similar games in this comparison average {similar_avg} {noun} - you have {n}. " + base_advice
    return base_advice


def check_screenshots(data: dict, similar_avg: float | None = None) -> CheckResult:
    n = data.get("screenshot_count", 0)
    if n >= 8:
        status, detail, advice = "done", f"{n} screenshots - comfortably above the 8+ that well-performing pages tend to show.", ""
    elif n >= 4:
        status, detail = "weak", f"{n} screenshots - readable, but pages with 8+ typically convert better."
        advice = _with_similar_avg_prefix(ADVICE["screenshots_weak"], "screenshots", n, similar_avg)
    else:
        status, detail = "missing", f"Only {_count_word(n, 'screenshot', 'screenshots')} - too few for a visitor to judge the game."
        advice = _with_similar_avg_prefix(ADVICE["screenshots_missing"], "screenshots", n, similar_avg)
    return CheckResult("screenshots", "Screenshot count", status, detail, WEIGHTS["screenshots"], advice=advice)


def check_trailer(data: dict) -> CheckResult:
    n = data.get("trailer_count", 0)
    if n >= 1:
        status, detail, advice = "done", f"{_count_word(n, 'trailer/video', 'trailers/videos')} present.", ""
    else:
        status, detail, advice = "missing", "No trailer or gameplay video found - this is usually the single biggest gap.", ADVICE["trailer"]
    return CheckResult("trailer", "Trailer / video", status, detail, WEIGHTS["trailer"], advice=advice)


def check_tags(data: dict, similar_avg: float | None = None) -> CheckResult:
    n = data.get("tag_count", 0)
    if n >= 4:
        status, detail, advice = "done", f"{n} tags/genres set - enough for the store's discovery algorithms to place the game well.", ""
    elif n >= 2:
        status, detail = "weak", f"Only {n} tags/genres set - worth filling out further."
        advice = _with_similar_avg_prefix(ADVICE["tags"], "tags", n, similar_avg)
    else:
        status, detail = "missing", f"{_count_word(n, 'tag/genre', 'tags/genres')} set - close to invisible to genre-based discovery."
        advice = _with_similar_avg_prefix(ADVICE["tags"], "tags", n, similar_avg)
    return CheckResult("tags", "Tag / genre coverage", status, detail, WEIGHTS["tags"], advice=advice)


def check_description(data: dict) -> CheckResult:
    n = data.get("description_length", 0)
    if n >= 800:
        status, detail, advice = "done", f"~{n} characters - enough room to actually sell the game.", ""
    elif n >= 200:
        status, detail, advice = "weak", f"~{n} characters - present but thin.", ADVICE["description"]
    else:
        status, detail, advice = "missing", f"~{n} characters - barely more than a tagline.", ADVICE["description"]
    return CheckResult("description", "Description length", status, detail, WEIGHTS["description"], advice=advice)


def check_reviews(data: dict) -> CheckResult:
    count = data.get("review_count")
    ratio = data.get("review_positive_ratio")
    if count is None:
        return CheckResult(
            "reviews", "Reviews", "missing",
            "No reviews yet - normal before/just after launch, but there's nothing here yet for buyers to judge by.",
            WEIGHTS["reviews"], advice=ADVICE["reviews"], fixable=False,
        )
    if count >= 50 and (ratio or 0) >= 0.70:
        status, detail, advice = "done", f"{count} reviews, {round((ratio or 0) * 100)}% positive.", ""
    elif count >= 10:
        status, detail, advice = "weak", f"{count} reviews, {round((ratio or 0) * 100)}% positive - a thin or mixed signal so far.", ADVICE["reviews"]
    else:
        status, detail, advice = "missing", f"Only {_count_word(count, 'review', 'reviews')} so far - too few to read as a signal either way.", ADVICE["reviews"]
    return CheckResult("reviews", "Reviews", status, detail, WEIGHTS["reviews"], advice=advice, fixable=False)


def score_page(data: dict, comparison: dict | None = None) -> dict:
    # Pull the similar-games averages out up front so the checks below can
    # fold a real number into their advice text instead of only fixed
    # wording - comparison is None whenever there was nothing to compare
    # against (e.g. itch.io), in which case every check falls back cleanly.
    screenshot_avg = comparison["screenshot_count"]["similar_avg"] if comparison else None
    tag_avg = comparison["tag_count"]["similar_avg"] if comparison else None

    results = [
        check_capsule_art(data),
        check_screenshots(data, screenshot_avg),
        check_trailer(data),
        check_tags(data, tag_avg),
        check_description(data),
        check_reviews(data),
    ]
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
        "ranked_fixes": [{"label": r.label, "detail": r.detail, "advice": r.advice} for r in fixes],
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
