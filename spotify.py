import os
import time
from typing import Any, Optional

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

from utils import clean_title

load_dotenv()


class SpotifyClient:
    """
    Spotify metadata poller.

    Tugas file ini hanya:
    - mengambil lagu yang sedang diputar;
    - mengambil progress terbaru;
    - memfilter respons lama yang menyebabkan flick back.

    Penghitungan progress realtime dilakukan di main.py.
    """

    def __init__(self) -> None:
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
                scope=(
                    "user-read-currently-playing "
                    "user-read-playback-state"
                ),
                open_browser=True,
            ),
            requests_timeout=10,
            retries=2,
        )

        self.current_song: Optional[dict[str, Any]] = None
        self.previous_song: Optional[dict[str, Any]] = None

        self.last_change_time = 0.0

        # Jika API kembali ke lagu lama dalam waktu ini,
        # respons tersebut akan dianggap stale.
        self.debounce_time = 0.8

    @staticmethod
    def _build_song(
        playback: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        item = playback.get("item")

        if item is None:
            return None

        artists = ", ".join(
            artist["name"]
            for artist in item.get("artists", [])
        )

        album = item.get("album") or {}
        images = album.get("images") or []

        album_cover = (
            images[0].get("url")
            if images
            else None
        )

        external_urls = item.get("external_urls") or {}

        return {
            "id": item.get("id"),
            "name": clean_title(item.get("name", "")),
            "original_name": item.get("name", ""),
            "artist": artists,
            "album": album.get("name", ""),
            "duration": int(item.get("duration_ms", 0)),
            "progress": int(playback.get("progress_ms", 0)),
            "spotify_url": external_urls.get("spotify"),
            "album_cover": album_cover,
            "is_playing": bool(
                playback.get("is_playing", False)
            ),
        }

    def get_current_song(
        self,
    ) -> Optional[dict[str, Any]]:
        try:
            playback = self.sp.current_user_playing_track()

            if playback is None:
                return None

            if not playback.get("is_playing", False):
                return None

            song = self._build_song(playback)

            if song is None or not song.get("id"):
                return None

            # Lagu pertama saat aplikasi dijalankan.
            if self.current_song is None:
                self.current_song = song
                return song.copy()

            # Masih lagu yang sama.
            if song["id"] == self.current_song["id"]:
                self.current_song = song
                return song.copy()

            now = time.monotonic()

            is_previous_song = (
                self.previous_song is not None
                and song["id"] == self.previous_song["id"]
            )

            is_inside_debounce = (
                now - self.last_change_time
            ) < self.debounce_time

            # Jika respons tiba-tiba kembali ke lagu sebelumnya dan
            # progress-nya sudah jauh dari awal, kemungkinan besar API
            # sedang memberikan respons lama.
            looks_like_old_response = song["progress"] > 3000

            if (
                is_previous_song
                and is_inside_debounce
                and looks_like_old_response
            ):
                return self.current_song.copy()

            print(
                f"[Spotify] Song changed -> "
                f"{song['name']}"
            )

            self.previous_song = self.current_song
            self.current_song = song
            self.last_change_time = now

            return song.copy()

        except Exception as error:
            print(f"[Spotify] {error}")

            # Kalau API gagal sesaat, pertahankan lagu aktif agar
            # Discord tidak langsung menghilang.
            if self.current_song is not None:
                return self.current_song.copy()

            return None


spotify = SpotifyClient()


def get_current_song() -> Optional[dict[str, Any]]:
    return spotify.get_current_song()