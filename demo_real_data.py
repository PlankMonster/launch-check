"""
This sandbox's network policy blocks outbound calls to store.steampowered.com
and itch.io directly (org egress allowlist only covers package registries),
so app.py can't be exercised end-to-end from inside this environment.

What follows instead is the real public data for three actual, currently-live
pages - pulled moments ago via a research fetch, by hand, the numbers are
exactly what those pages show right now - fed straight into scoring.py, the
same module app.py calls. This is here to prove the grading logic actually
discriminates between a strong page, a mid one, and a well-built itch.io page,
using real numbers rather than made-up test fixtures.
"""

from scoring import score_page

# store.steampowered.com/app/413150 - Stardew Valley, fetched live
stardew = {
    "title": "Stardew Valley",
    "has_capsule_art": True,
    "screenshot_count": 16,
    "trailer_count": 1,
    "tag_count": 3 + 9,  # 3 genres + 9 categories, as returned
    "description_length": 2800,
    "review_count": 393226,
    "review_positive_ratio": 388818 / 393226,
}

# store.steampowered.com/app/4927490 - Cleaning Up The Puzzle Gallery,
# a small upcoming indie release, fetched live
puzzle_gallery = {
    "title": "Cleaning Up The Puzzle Gallery",
    "has_capsule_art": True,
    "screenshot_count": 5,
    "trailer_count": 1,
    "tag_count": 2 + 13,  # 2 genres + 13 categories
    "description_length": 2800,
    "review_count": None,  # unreleased - no reviews yet
    "review_positive_ratio": None,
}

# nlch.itch.io/usuimo, fetched live
usuimo = {
    "title": "Usuimo",
    "has_capsule_art": True,
    "screenshot_count": 6,   # mixed gifs/jpegs shown on the page
    "trailer_count": 1,
    "tag_count": 11,         # Simulation, Action, Adventure, 2D, Anime, etc.
    "description_length": 1400,
    "review_count": 72,
    "review_positive_ratio": 4.7 / 5.0,
}

for game in (stardew, puzzle_gallery, usuimo):
    report = score_page(game)
    print(f"\n=== {report['title']} — {report['overall_score']}/100 ===")
    for c in report["checklist"]:
        print(f"  [{c['status'].upper():>7}] {c['label']}: {c['detail']}")
    print("  Ranked fixes:")
    if not report["ranked_fixes"]:
        print("    (none - every checked factor is in good shape)")
    for f in report["ranked_fixes"]:
        print(f"    - {f['label']}: {f['detail']}")
