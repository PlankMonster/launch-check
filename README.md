# Launch Check — the first slice

Paste a Steam or itch.io store page, get back a scored report: what's
missing, what's weak, ranked by how much it's likely to matter. That's
the whole product at this stage — see the build brief artifact for the
full plan and what comes after this.

## What's actually in this folder

- `scoring.py` — the grading logic. Takes a game's page data and
  produces the checklist, the overall score, and the ranked fix list.
  Doesn't know or care whether the data came from Steam or itch.io.
- `sources/steam.py` — pulls a game's public Steam store data (no
  account or API key needed — this is the same public data SteamDB and
  many other tools have used for years) plus a handful of similar
  games for comparison.
- `sources/itchio.py` — reads the public itch.io store page the same
  way a browser would, since itch.io doesn't offer a public "app
  details" API the way Steam does. This is the one part of the app
  most likely to need small adjustments over time if itch.io changes
  their page layout — it's reading the page itself, not a stable API.
- `app.py` — the web app: one page, one input box, one report.
- `templates/index.html` — that one page.
- `demo_real_data.py` — proof the scoring logic works correctly on
  real data (see below — this is not a normal part of the app, it's
  how this was tested).

## Why there's a `demo_real_data.py` at all

The environment this was built in isn't allowed to make outbound calls
to Steam or itch.io directly, so `app.py` couldn't be run end-to-end
in that sandbox. To prove the actual grading logic works — not just
that the code doesn't crash — real, live data for three current pages
(Stardew Valley on Steam, a small upcoming Steam indie release, and a
game on itch.io) was pulled by hand and fed straight into `scoring.py`.
It correctly gave Stardew Valley 100/100, and correctly flagged the
same "too few screenshots" weakness on both of the smaller pages. Run
`python demo_real_data.py` to see that output yourself.

This isn't a limitation of the idea or the code — Steam's public data
is queried by thousands of tools every day with no restriction. It's
specific to the sandbox it was built in not having general internet
access. Once this runs somewhere with normal internet access (see
below), `app.py` itself works the same way, live, in a browser.

## Running it yourself

```
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5000` in a browser, on whichever machine
you run that command on.

## Getting it onto a real web address anyone can open

Running it on one machine only reaches that machine. To get an actual
link you could send someone, this needs to be *hosted* — that's a
separate, well-worn step, not a coding problem:

1. Put this folder in a GitHub repository (Claude Code can do this for
   you).
2. Connect that repository to a host with a free tier built for exactly
   this kind of small Flask app — Render.com is a common,
   straightforward choice; Railway.app is another.
3. The host builds and runs it automatically from `requirements.txt`
   and `app.py`, and gives you a public `https://…` link.

None of this needs to happen before you've decided the tool itself is
worth pursuing further — this step is only for when you want a real
link to hand to actual indie developers to try.
