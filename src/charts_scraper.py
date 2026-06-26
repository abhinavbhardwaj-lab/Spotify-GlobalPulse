"""Scraper for kworb.net global daily tracks chart."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

KWORB_TRACKS_URL = "https://kworb.net/spotify/country/global_daily.html"
USER_AGENT = "Mozilla/5.0 (compatible; SpotifyPulse/1.0)"


@dataclass
class TrackChartRow:
    rank: int
    track_id: Optional[str]
    title: str
    artist: str
    daily_streams: int
    total_streams: int

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "track_id": self.track_id,
            "title": self.title,
            "artist": self.artist,
            "daily_streams": self.daily_streams,
            "total_streams": self.total_streams,
        }


def _to_int(value: str) -> int:
    if not value:
        return 0
    s = value.strip().replace(",", "").replace("+", "")
    if not s or s == "-":
        return 0
    try:
        if "." in s:
            return int(float(s) * 1_000_000)
        return int(s)
    except ValueError:
        return 0


def _pick_tracks_table(soup: BeautifulSoup):
    """Pick the table whose links point at /track/ pages."""
    for t in soup.find_all("table"):
        if any("track/" in a.get("href", "") for a in t.find_all("a", href=True)):
            return t
    return None


def _extract_id(href: str) -> Optional[str]:
    # "../track/49j6SvuvWfbEKZKzsHCdLJ.html" → "49j6SvuvWfbEKZKzsHCdLJ"
    last = href.rstrip("/").split("/")[-1]
    return last.rsplit(".", 1)[0] if last else None


def fetch_top_tracks(limit: int = 50, timeout: int = 20) -> list[TrackChartRow]:
    r = requests.get(KWORB_TRACKS_URL, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    table = _pick_tracks_table(soup)
    if not table:
        raise RuntimeError("Could not find tracks table on kworb page")

    rows: list[TrackChartRow] = []
    for tr in table.find_all("tr"):
        track_link = None
        artist_link = None
        for a in tr.find_all("a", href=True):
            href = a["href"]
            if "track/" in href and track_link is None:
                track_link = a
            elif "artist/" in href and artist_link is None:
                artist_link = a
        if not track_link:
            continue

        title = track_link.get_text(strip=True)
        artist = artist_link.get_text(strip=True) if artist_link else ""
        track_id = _extract_id(track_link["href"])

        # kworb global_daily layout:
        # [0]=rank [1]=movement [2]=artist-title [3]=days [4]=peak
        # [5]=peak-run [6]=daily streams [7]=daily change [8]=total streams
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        try:
            rank = int(cells[0].replace(",", "")) if cells else len(rows) + 1
        except ValueError:
            rank = len(rows) + 1
        daily_streams = _to_int(cells[6]) if len(cells) > 6 else 0
        total_streams = _to_int(cells[8]) if len(cells) > 8 else 0

        rows.append(
            TrackChartRow(
                rank=rank,
                track_id=track_id,
                title=title,
                artist=artist,
                daily_streams=daily_streams,
                total_streams=total_streams,
            )
        )
        if len(rows) >= limit:
            break

    logger.info("Scraped %d tracks from kworb", len(rows))
    return rows
