"""
Generate realistic-looking sample data so the dashboard renders on first clone.

Run: `python scripts/seed_sample_data.py`
This writes data/latest.json, data/history.json, and a few dated snapshots
so the dashboard has movers to show out of the box.
"""

from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

SEED_ARTISTS = [
    ("Bad Bunny", ["reggaeton", "latin pop"], 98, 88_400_000),
    ("Taylor Swift", ["pop"], 100, 134_500_000),
    ("The Weeknd", ["pop", "r&b"], 95, 79_200_000),
    ("Drake", ["hip hop", "rap"], 94, 89_700_000),
    ("Billie Eilish", ["pop", "alt pop"], 93, 112_300_000),
    ("Ariana Grande", ["pop"], 92, 96_100_000),
    ("Travis Scott", ["hip hop", "rap"], 91, 38_500_000),
    ("Karol G", ["reggaeton", "latin pop"], 91, 41_800_000),
    ("Olivia Rodrigo", ["pop"], 90, 35_200_000),
    ("Sabrina Carpenter", ["pop"], 92, 22_300_000),
    ("Kendrick Lamar", ["hip hop", "rap"], 91, 33_400_000),
    ("SZA", ["r&b", "alt r&b"], 90, 24_600_000),
    ("Dua Lipa", ["pop", "dance pop"], 89, 49_500_000),
    ("Post Malone", ["pop rap"], 88, 41_300_000),
    ("Justin Bieber", ["pop"], 87, 76_800_000),
    ("Ed Sheeran", ["pop", "uk pop"], 88, 116_700_000),
    ("Bruno Mars", ["pop", "funk pop"], 88, 56_200_000),
    ("Coldplay", ["rock", "alt rock"], 87, 47_900_000),
    ("Rihanna", ["pop", "r&b"], 87, 62_100_000),
    ("Eminem", ["hip hop", "rap"], 86, 86_400_000),
    ("Beyoncé", ["pop", "r&b"], 86, 36_700_000),
    ("Tate McRae", ["pop"], 87, 14_500_000),
    ("Peso Pluma", ["regional mexican"], 88, 19_200_000),
    ("Shakira", ["pop", "latin pop"], 86, 33_800_000),
    ("Doja Cat", ["pop", "rap"], 87, 31_700_000),
    ("Linkin Park", ["rock", "nu metal"], 85, 32_100_000),
    ("BTS", ["k-pop"], 86, 79_300_000),
    ("Imagine Dragons", ["pop rock"], 84, 62_400_000),
    ("Maroon 5", ["pop", "pop rock"], 84, 54_900_000),
    ("Khalid", ["pop", "r&b"], 83, 27_300_000),
    ("Halsey", ["pop", "alt pop"], 82, 25_100_000),
    ("Shawn Mendes", ["pop"], 81, 35_600_000),
    ("Calvin Harris", ["edm", "dance pop"], 81, 32_400_000),
    ("Marshmello", ["edm"], 81, 56_200_000),
    ("Lana Del Rey", ["alt pop", "indie pop"], 84, 21_500_000),
    ("Twenty One Pilots", ["alt rock"], 80, 30_900_000),
    ("J. Cole", ["hip hop", "rap"], 84, 19_800_000),
    ("Lady Gaga", ["pop"], 84, 51_200_000),
    ("Frank Ocean", ["alt r&b"], 82, 11_800_000),
    ("Tyler, The Creator", ["hip hop", "alt hip hop"], 83, 13_400_000),
    ("Selena Gomez", ["pop"], 82, 47_300_000),
    ("Miley Cyrus", ["pop"], 81, 30_500_000),
    ("Charlie Puth", ["pop"], 80, 23_900_000),
    ("Daddy Yankee", ["reggaeton"], 80, 27_800_000),
    ("J Balvin", ["reggaeton", "latin pop"], 80, 39_400_000),
    ("Lil Wayne", ["hip hop", "rap"], 79, 25_700_000),
    ("Future", ["hip hop", "rap"], 80, 22_100_000),
    ("Camila Cabello", ["pop"], 79, 28_400_000),
    ("Sia", ["pop"], 78, 33_900_000),
    ("Adele", ["pop", "soul"], 87, 50_300_000),
]


def make_snapshot(date: str, rng: random.Random) -> dict:
    artists = []
    base_streams = 22_000_000
    for i, (name, genres, popularity, followers) in enumerate(SEED_ARTISTS):
        # randomize streams slightly for daily variation
        wobble = rng.uniform(0.85, 1.15)
        daily = int((base_streams - i * 250_000) * wobble)
        daily = max(daily, 800_000)
        artists.append(
            {
                "rank": i + 1,
                "name": name,
                "daily_streams": daily,
                "total_streams": daily * rng.randint(180, 540),
                "daily_change": rng.randint(-800_000, 800_000),
                "spotify": {
                    "id": f"sample{i:03d}",
                    "name": name,
                    "popularity": popularity + rng.randint(-1, 1),
                    "followers": followers + rng.randint(-100_000, 200_000),
                    "genres": genres,
                    "image_url": None,
                    "spotify_url": f"https://open.spotify.com/artist/sample{i:03d}",
                },
            }
        )
    # shuffle ranks a little between days for movers
    artists = sorted(artists, key=lambda a: -a["daily_streams"])
    for i, a in enumerate(artists):
        a["rank"] = i + 1
    return {
        "date": date,
        "source": "sample-data (no live calls)",
        "artist_count": len(artists),
        "artists": artists,
    }


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today()
    history = {"days": [], "artists": {}}

    for offset in range(6, -1, -1):  # 7 days, ending today
        date = (today - dt.timedelta(days=offset)).isoformat()
        rng = random.Random(hash(date) & 0xFFFFFFFF)
        snapshot = make_snapshot(date, rng)
        (DATA_DIR / f"{date}.json").write_text(json.dumps(snapshot, indent=2))
        if offset == 0:
            (DATA_DIR / "latest.json").write_text(json.dumps(snapshot, indent=2))
        history["days"].append(date)
        for entry in snapshot["artists"]:
            history["artists"].setdefault(entry["name"], {})[date] = {
                "rank": entry["rank"],
                "daily_streams": entry["daily_streams"],
            }

    history["days"] = sorted(set(history["days"]))
    (DATA_DIR / "history.json").write_text(json.dumps(history, indent=2))
    print(f"Seeded {len(history['days'])} days of sample data")


if __name__ == "__main__":
    main()
