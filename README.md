# Spotify Pulse

> Daily snapshot of the world's biggest streaming artists — refreshed automatically every 24 hours via GitHub Actions, rendered as a live dashboard on GitHub Pages.

[![Daily Update](https://github.com/YOUR_USERNAME/spotify-pulse/actions/workflows/daily-update.yml/badge.svg)](https://github.com/YOUR_USERNAME/spotify-pulse/actions/workflows/daily-update.yml)
[![CI](https://github.com/YOUR_USERNAME/spotify-pulse/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/spotify-pulse/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)

**Live dashboard →** `https://YOUR_USERNAME.github.io/spotify-pulse/`

---

## What it does

Spotify Pulse tracks the top 50 streaming artists on Spotify every single day. It combines two data sources to give a complete picture:

1. **kworb.net** — for actual daily stream counts (Spotify doesn't expose global stream numbers via its API)
2. **Spotify Web API** — for artist metadata, popularity scores, follower counts, genres, and artwork

Each morning at 06:00 UTC, a GitHub Actions workflow runs the pipeline, persists a dated JSON snapshot, regenerates the static HTML dashboard, commits the changes, and deploys the new page to GitHub Pages. Zero infrastructure to maintain.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   kworb.net     │     │  Spotify Web    │
│   (streams)     │     │  API (metadata) │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
   ┌──────────────────────────────────┐
   │   src/pipeline.py                │
   │   • Scrape charts                │
   │   • Enrich via Spotify API       │
   │   • Write data/{date}.json       │
   │   • Append to data/history.json  │
   └─────────────┬────────────────────┘
                 │
                 ▼
   ┌──────────────────────────────────┐
   │   src/dashboard.py               │
   │   • Render docs/index.html       │
   │   • Compute rank deltas & movers │
   └─────────────┬────────────────────┘
                 │
                 ▼
   ┌──────────────────────────────────┐
   │   GitHub Actions (06:00 UTC)     │
   │   • git commit + push            │
   │   • Deploy to GitHub Pages       │
   └──────────────────────────────────┘
```

## Features

- **Live dashboard** with top 10 cards, ranks 11–50 grid, biggest movers, and a streams distribution chart
- **Rank deltas** — every artist shows their position change vs. yesterday (▲ rising, ▼ falling)
- **30-day history** stored in `data/history.json` for trend analysis
- **Resilient pipeline** — retries on rate limits, gracefully degrades if Spotify API is unreachable
- **CI/CD pipeline** — linting (ruff), unit tests (pytest), automated deploys
- **Fully serverless** — no hosting costs, no servers to maintain

## Getting started

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/spotify-pulse.git
cd spotify-pulse
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 2. Get Spotify credentials

Create an app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard), then:

```bash
cp .env.example .env
# fill in SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET
export $(cat .env | xargs)
```

### 3. Run locally

```bash
python -m src.pipeline --limit 50      # fetch + persist today's snapshot
python -m src.dashboard                # regenerate docs/index.html
open docs/index.html                   # view in browser
```

To test without Spotify credentials:

```bash
python -m src.pipeline --limit 50 --dry-run
```

### 4. Enable in GitHub

1. Push to a new GitHub repo
2. **Settings → Secrets and variables → Actions** — add `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`
3. **Settings → Pages** — set source to "GitHub Actions"
4. The first run kicks off on the next 06:00 UTC, or trigger manually from the **Actions** tab

## Project structure

```
spotify-pulse/
├── src/
│   ├── spotify_client.py   # Spotify Web API client (auth, retries, batch lookup)
│   ├── charts_scraper.py   # kworb.net scraper
│   ├── pipeline.py         # Orchestrator — pulls, merges, persists
│   └── dashboard.py        # Static HTML generator
├── data/
│   ├── latest.json         # Most recent snapshot (overwritten daily)
│   ├── history.json        # 30-day rolling rank index
│   └── YYYY-MM-DD.json     # One file per day, never overwritten
├── docs/
│   └── index.html          # GitHub Pages dashboard
├── tests/                  # pytest unit tests
└── .github/workflows/
    ├── daily-update.yml    # Cron job: scrape → render → deploy
    └── ci.yml              # Lint + test on every PR
```

## Tech stack

| Layer | Choice | Why |
|-------|--------|-----|
| Language | Python 3.11 | Mature ecosystem for scraping + API work |
| HTTP | `requests` | Battle-tested, simple |
| Parsing | `beautifulsoup4` + `lxml` | Resilient HTML parsing |
| Frontend | Vanilla HTML/CSS + Chart.js | No build step, fast loads, easy to host |
| Hosting | GitHub Pages | Free, zero-config, integrates with Actions |
| Automation | GitHub Actions | Free cron, secret management, native CI |
| Tests | `pytest` + `ruff` | Standard, fast |

## Development

```bash
pip install -r requirements-dev.txt
ruff check src tests          # lint
pytest -q                     # run tests
pytest --cov=src              # with coverage
```

## Roadmap

- [ ] Track genre-level trends (e.g. "pop is up 12% this week")
- [ ] RSS feed for daily updates
- [ ] Twitter/X bot that posts the top 5 every morning
- [ ] Country-specific charts (US, UK, BR, DE)
- [ ] Per-artist deep-dive pages with track-level data

## License

[MIT](LICENSE) — feel free to fork, learn from, and adapt for your own portfolio.

## Acknowledgements

- [kworb.net](https://kworb.net) for maintaining open Spotify chart data
- [Spotify Web API](https://developer.spotify.com/documentation/web-api) for artist metadata
