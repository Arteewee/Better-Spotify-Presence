import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    # ===========================
    # Spotify
    # ===========================

    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")

    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

    SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

    # ===========================
    # Discord
    # ===========================

    DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")

    # ===========================
    # Update Interval
    # ===========================

    # Cek Spotify setiap 1 detik
    SPOTIFY_REFRESH_RATE = 0.5

    # Sinkronisasi lyric
    LYRIC_REFRESH_RATE = 0.05

    # ===========================
    # Request
    # ===========================

    REQUEST_TIMEOUT = 10

    # ===========================
    # Cache
    # ===========================

    ENABLE_CACHE = True

    MAX_CACHE_SIZE = 100

    # ===========================
    # Debug
    # ===========================

    DEBUG = True