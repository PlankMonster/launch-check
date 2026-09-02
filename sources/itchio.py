"""
Pulls public, no-signup itch.io store page data for one game.
itch.io has no public "app details" API for arbitrary third parties the
way Steam does, so this reads the same public HTML page a browser would
load and pulls the same information a visitor sees: cover image,
screenshots, an embedded trailer, tags, description length, and the
page's own star rating if shown. Nothing here needs the developer's
account or an API key - that only comes in later for a creator's own
private stats (see the build brief).
"""

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (LaunchCheck/1.0)"}


def is_itchio_url(url: str) -> bool:
    return "itch.io" in url


def fetch_page(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def normalize(soup: BeautifulSoup, url: str) -> dict:
    title_tag = soup.find("meta", property="og:title") or soup.find("title")
    title = title_tag["content"] if title_tag and title_tag.has_attr("content") else (
        title_tag.text if title_tag else "Untitled"
    )

    cover = soup.find("meta", property="og:image")
    has_cover = bool(cover and cover.get("content"))

    # itch.io screenshot strip - each screenshot is an <a> wrapping an <img>,
    # so only count the <a> or every screenshot gets counted twice.
    screenshot_count = len(soup.select(".screenshot_list a"))

    # embedded trailer (YouTube/Vimeo iframe, or itch's own video embed block)
    video = soup.select("iframe[src*='youtube'], iframe[src*='vimeo'], .video_embed")
    trailer_count = 1 if video else 0

    # Genre and Tags are two separate labeled rows in itch's info panel
    # table. Matched by their row label rather than by URL shape (a link
    # inside an unrelated "Content" disclosure row - e.g. "No generative AI
    # was used" - also happens to point at a /games/tag-* URL, so matching
    # on href alone overcounts). Counting both genre + tag rows mirrors how
    # the Steam side combines genres + categories into one tag_count.
    tag_count = 0
    for row in soup.select(".game_info_panel_widget tr"):
        cells = row.find_all("td")
        if len(cells) == 2 and cells[0].get_text(strip=True) in ("Genre", "Tags"):
            tag_count += len(cells[1].find_all("a"))

    desc = soup.find("div", class_="formatted_description")
    description_length = len(desc.get_text(strip=True)) if desc else 0

    # itch's rating value/count live on a <div>/<span> carrying the itemprop
    # attribute, not on a <meta> tag - so search by attribute, not tag name.
    rating_el = soup.find(attrs={"itemprop": "ratingValue"})
    rating_count_el = soup.find(attrs={"itemprop": "ratingCount"})
    review_count = None
    if rating_count_el and rating_count_el.get("content"):
        try:
            review_count = int(rating_count_el["content"])
        except ValueError:
            pass
    review_positive_ratio = None
    if rating_el and rating_el.get("content"):
        try:
            # itch shows a 1-5 star average; treat >=4/5 as "positive" for
            # the same 0-1 scale the Steam side uses
            review_positive_ratio = min(float(rating_el["content"]) / 5.0, 1.0)
        except ValueError:
            pass

    return {
        "title": title,
        "has_capsule_art": has_cover,
        "screenshot_count": screenshot_count,
        "trailer_count": trailer_count,
        "tag_count": tag_count,
        "description_length": description_length,
        "review_count": review_count,
        "review_positive_ratio": review_positive_ratio,
        "source_url": url,
    }


def fetch_and_normalize(url: str) -> dict:
    soup = fetch_page(url)
    return normalize(soup, url)
