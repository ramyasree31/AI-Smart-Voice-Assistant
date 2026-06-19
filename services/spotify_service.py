import base64
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search"


class SpotifyService:
    def __init__(self):
        self.client_id = SPOTIFY_CLIENT_ID
        self.client_secret = SPOTIFY_CLIENT_SECRET
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def get_access_token(self) -> Optional[str]:
        if not self.is_configured():
            return None

        if self._access_token and time.time() < self._expires_at - 30:
            return self._access_token

        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        response = requests.post(
            SPOTIFY_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth_header}"},
            timeout=10,
        )

        if response.status_code != 200:
            return None

        data = response.json()
        self._access_token = data.get("access_token")
        self._expires_at = time.time() + int(data.get("expires_in", 0))
        return self._access_token

    def search_track(self, query: str) -> Optional[dict]:
        if not query or not self.is_configured():
            return None

        access_token = self.get_access_token()
        if not access_token:
            return None

        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "q": query,
            "type": "track",
            "market": "US",
            "limit": 3,
        }

        try:
            response = requests.get(
                SPOTIFY_SEARCH_URL,
                headers=headers,
                params=params,
                timeout=10,
            )
            if response.status_code != 200:
                return None

            data = response.json()
            items = data.get("tracks", {}).get("items", [])
            if not items:
                return None

            item = items[0]
            artists = ", ".join(
                [artist.get("name", "") for artist in item.get("artists", []) if artist.get("name")]
            )

            return {
                "source": "spotify",
                "title": item.get("name") or query,
                "artist": artists or "Unknown Artist",
                "query": query,
                "url": item.get("external_urls", {}).get("spotify"),
                "playable_url": item.get("external_urls", {}).get("spotify"),
                "spotify_uri": item.get("uri"),
                "source_id": item.get("id"),
                "metadata": {
                    "album": item.get("album", {}).get("name"),
                    "duration_ms": item.get("duration_ms"),
                    "preview_url": item.get("preview_url"),
                },
            }
        except requests.RequestException:
            return None
