import re
import requests
from cache import lyrics_cache
from config import Config

BASE_URL = "https://lrclib.net/api/get"


class LyricsManager:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SpotifyDiscordLyrics/1.0"
        })

    def get_lyrics(self, track: str, artist: str):


        cache_key = f"{track}|{artist}"
        cached = lyrics_cache.get(cache_key)

        # Sudah pernah diambil
        if cached is not None:
            return cached
        
        try:

            response = self.session.get(
                BASE_URL,
                params={
                    "track_name": track,
                    "artist_name": artist
                },
                timeout=Config.REQUEST_TIMEOUT
            )

            if response.status_code != 200:
                print("[Lyrics] Lyrics not found.")
                return []

            data = response.json()

            synced = data.get("syncedLyrics")

            if not synced:
                print("[Lyrics] Song has no synced lyrics.")
                return []

            lyrics = self.parse_lrc(synced)

            lyrics_cache.set(
                cache_key,
                lyrics
            )

            print(f"[Lyrics] Loaded {len(lyrics)} lines.")

            return lyrics

        except requests.exceptions.RequestException as e:

            print(f"[Lyrics] Network Error : {e}")
            return []

        except Exception as e:

            print(f"[Lyrics] {e}")
            return []

    def parse_lrc(self, lrc_text):

        lyrics = []

        pattern = re.compile(
            r"\[(\d+):(\d+\.\d+)\](.*)"
        )

        for line in lrc_text.splitlines():

            match = pattern.match(line)

            if not match:
                continue

            minute = int(match.group(1))
            second = float(match.group(2))

            timestamp = minute * 60 + second

            text = match.group(3).strip()

            lyrics.append({
                "time": timestamp,
                "text": text
            })

        lyrics.sort(key=lambda x: x["time"])

        return lyrics


lyrics_manager = LyricsManager()


def get_lyrics(track, artist):
    return lyrics_manager.get_lyrics(track, artist)