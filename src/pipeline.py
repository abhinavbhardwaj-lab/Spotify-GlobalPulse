"""Daily pipeline: scrape global tracks chart, enrich via Spotify, persist."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from .charts_scraper import TrackChartRow, fetch_top_tracks
from .spotify_client import SpotifyClient

logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


def enrich_with_spotify(
    chart_rows: list[TrackChartRow], client: SpotifyClient
) -> dict[str, dict[str, Any]]:
    ids_with_tracks = [r for r in chart_rows if r.track_id]
    track_ids = [r.track_id for r in ids_with_tracks]
    try:
        fetched = client.get_tracks(track_ids) if track_ids else []
    except Exception as exc:
        logger.warning("Spotify enrichment failed (%s) - continuing without it", exc)
        return {}
    by_id = {t["id"]: t for t in fetched}
    enriched: dict[str, dict[str, Any]] = {}
    for row in chart_rows:
        key = row.track_id or f"{row.title}|{row.artist}"
        if row.track_id and row.track_id in by_id:
            enriched[key] = by_id[row.track_id]
    logger.info("Enriched %d/%d tracks", len(enriched), len(chart_rows))
    return enriched


def merge(
    chart_rows: list[TrackChartRow], enriched: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    out = []
    for row in chart_rows:
        key = row.track_id or f"{row.title}|{row.artist}"
        sp = enriched.get(key)
        out.append({
            **row.to_dict(),
            "spotify": sp,
            "display_title": (sp or {}).get("name") or row.title,
            "display_artist": ", ".join((sp or {}).get("artists") or []) or row.artist,
        })
    return out


def update_history(snapshot: list[dict[str, Any]], date: str) -> dict[str, Any]:
    history_path = DATA_DIR / "history.json"
    history = (
        json.loads(history_path.read_text())
        if history_path.exists()
        else {"days": [], "tracks": {}}
    )
    history.setdefault("tracks", {})
    if date not in history["days"]:
        history["days"].append(date)
        history["days"] = sorted(set(history["days"]))[-30:]
    for entry in snapshot:
        key = entry["track_id"] or entry["display_title"]
        per = history["tracks"].setdefault(key, {"label": entry["display_title"], "days": {}})
        per["days"][date] = {"rank": entry["rank"], "daily_streams": entry["daily_streams"]}
    return history


def run(limit: int = 50, dry_run: bool = False) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    logger.info("Fetching top %d tracks from kworb global daily chart", limit)
    chart_rows = fetch_top_tracks(limit=limit)

    enriched: dict[str, dict[str, Any]] = {}
    if not dry_run and os.environ.get("SPOTIFY_CLIENT_ID"):
        client = SpotifyClient()
        enriched = enrich_with_spotify(chart_rows, client)

    snapshot = merge(chart_rows, enriched)
    payload = {
        "date": today,
        "source": "kworb.net global_daily + spotify-web-api",
        "track_count": len(snapshot),
        "tracks": snapshot,
    }
    (DATA_DIR / f"{today}.json").write_text(json.dumps(payload, indent=2))
    (DATA_DIR / "latest.json").write_text(json.dumps(payload, indent=2))
    history = update_history(snapshot, today)
    (DATA_DIR / "history.json").write_text(json.dumps(history, indent=2))
    logger.info("Wrote snapshot for %s", today)
    return DATA_DIR / f"{today}.json"


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        run(limit=args.limit, dry_run=args.dry_run)
    except Exception as exc:
        logger.exception("Pipeline failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
