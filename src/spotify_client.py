"""
Spotify Web API client.

Uses Client Credentials flow to fetch track and artist metadata.
Authentication via SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET env vars.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


class SpotifyClient:
    """Thin wrapper around the Spotify Web API with retry-aware requests."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.client_id = client_id or os.environ.get("SPOTIFY_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("SPOTIFY_CLIENT_SECRET")
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "Spotify credentials missing. Set SPOTIFY_CLIENT_ID and "
                "SPOTIFY_CLIENT_SECRET environment variables."
            )
        self._session = session or requests.Session()
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    # -- auth ----------------------------------------------------------------

    def _authenticate(self) -> None:
        creds = f"{self.client_id}:{self.client_secret}".encode()
        headers = {
            "Authorization": f"Basic {base64.b64encode(creds).decode()}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = self._session.post(
            SPOTIFY_AUTH_URL,
            headers=headers,
            data={"grant_type": "client_credentials"},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expiry = time.time() + payload.get("expires_in", 3600) - 60
        logger.info("Spotify token refreshed")

    def _auth_headers(self) -> dict[str, str]:
        if not self._token or time.time() >= self._token_expiry:
            self._authenticate()
        return {"Authorization": f"Bearer {self._token}"}

    # -- requests ------------------------------------------------------------

    def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        url = f"{SPOTIFY_API_BASE}{path}"
        for _ in range(3):
            response = self._session.get(
                url, headers=self._auth_headers(), params=params, timeout=15
            )
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 2))
                logger.warning("Rate limited, sleeping %ds", retry_after)
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError(f"Spotify API failed after retries: {url}")

    # -- tracks --------------------------------------------------------------

    def get_tracks(self, track_ids: list[str]) -> list[dict[str, Any]]:
        """Per-track lookup (the batch /tracks endpoint is restricted for some apps)."""
        results: list[dict[str, Any]] = []
        for tid in track_ids:
            try:
                payload = self._get(f"/tracks/{tid}")
            except Exception as exc:
                logger.warning("Track %s lookup failed: %s", tid, exc)
                continue
            results.append(self._parse_track(payload))
        return results

    @staticmethod
    def _parse_track(data: dict[str, Any]) -> dict[str, Any]:
        album = data.get("album") or {}
        images = album.get("images") or []
        return {
            "id": data["id"],
            "name": data["name"],
            "artists": [a["name"] for a in data.get("artists", [])],
            "album": album.get("name"),
            "album_image": images[0]["url"] if images else None,
            "popularity": data.get("popularity", 0),
            "duration_ms": data.get("duration_ms"),
            "preview_url": data.get("preview_url"),
            "spotify_url": data.get("external_urls", {}).get("spotify"),
            "explicit": data.get("explicit", False),
            "release_date": album.get("release_date"),
        }

    # -- search fallback for tracks without IDs ------------------------------

    def search_track(self, title: str, artist: str = "") -> Optional[dict[str, Any]]:
        query = f"track:{title}"
        if artist:
            query += f" artist:{artist}"
        payload = self._get("/search", params={"q": query, "type": "track", "limit": 1})
        items = payload.get("tracks", {}).get("items", [])
        return self._parse_track(items[0]) if items else None
