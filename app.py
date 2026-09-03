"""
Launch Check - the first slice.

One route, one job: paste a Steam or itch.io store URL, get back a
graded report. No accounts, no database, no payments - see the build
brief for why, and for what comes after this.

Run locally:
    pip install -r requirements.txt
    python app.py
    # open http://localhost:5000

Deploying it so it's reachable by anyone (not just on your own machine)
is a separate, later step - see README.md.
"""

from flask import Flask, request, jsonify, render_template

from scoring import score_page, compare
from sources import steam, itchio

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze")
def analyze():
    url = (request.args.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Paste a Steam or itch.io store page URL."}), 400

    try:
        if "store.steampowered.com" in url:
            appid = steam.extract_appid(url)
            if not appid:
                return jsonify({"error": "That doesn't look like a Steam store page URL (expected .../app/<id>/...)."}), 400
            data = steam.fetch_and_normalize(appid)
            if data is None:
                return jsonify({"error": "Couldn't find that app on Steam - check the link."}), 404
            details = steam.fetch_appdetails(appid)
            similar = steam.fetch_similar_normalized(details, appid, limit=5)

        elif itchio.is_itchio_url(url):
            data = itchio.fetch_and_normalize(url)
            similar = []  # itch.io has no genre-search API to pull comparables from yet

        else:
            return jsonify({"error": "That's not a Steam or itch.io store page URL."}), 400

    except Exception as exc:  # keep the first slice's error handling simple and visible
        return jsonify({"error": f"Couldn't read that page right now ({exc})."}), 502

    comparison = compare(data, similar) if similar else None
    report = score_page(data, comparison)
    report["comparison"] = comparison
    return jsonify(report)


if __name__ == "__main__":
    app.run(debug=True)
