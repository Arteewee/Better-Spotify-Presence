import os

from dotenv import load_dotenv

load_dotenv()


class Config:

    # ===========================
    # Spotify Credentials
    # ===========================

    SPOTIFY_CLIENT_ID = os.getenv(
        "SPOTIFY_CLIENT_ID"
    )

    SPOTIFY_CLIENT_SECRET = os.getenv(
        "SPOTIFY_CLIENT_SECRET"
    )

    SPOTIFY_REDIRECT_URI = os.getenv(
        "SPOTIFY_REDIRECT_URI"
    )

    # ===========================
    # Discord
    # ===========================

    DISCORD_CLIENT_ID = os.getenv(
        "DISCORD_CLIENT_ID"
    )

    # ===========================
    # Spotify Polling
    # ===========================

    # Poll normal ketika lagu masih jauh dari selesai.
    # Live lyrics tidak mengikuti interval ini.
    SPOTIFY_REFRESH_RATE = 4.0

    # Poll lebih cepat ketika lagu hampir selesai agar lagu
    # berikutnya lebih cepat terdeteksi.
    SPOTIFY_FAST_REFRESH_RATE = 1.0

    # Mulai fast polling ketika sisa lagu <= nilai ini.
    SPOTIFY_ENDING_WINDOW = 12.0

    # Jangan langsung menganggap satu respons None sebagai idle.
    EMPTY_POLLS_BEFORE_CLEAR = 2

    # Berapa lama activity cache boleh dipertahankan setelah
    # posisi lagu mencapai durasi akhirnya.
    STALE_ACTIVITY_GRACE = 3.0

    # ===========================
    # Live Lyrics
    # ===========================

    # 0.05 = pengecekan local lyric clock 20 kali/detik.
    LYRIC_REFRESH_RATE = 0.05

    # ===========================
    # HTTP Request
    # ===========================

    REQUEST_TIMEOUT = 10

    # Fallback cooldown jika Spotify mengirim 429 tetapi tidak
    # menyertakan Retry-After yang valid.
    DEFAULT_RATE_LIMIT_SECONDS = 60

    # Maksimum nilai Retry-After yang akan diterima.
    # 24 jam cukup untuk quota cooldown panjang.
    MAX_RATE_LIMIT_SECONDS = 86_400

    # ===========================
    # Cache
    # ===========================

    ENABLE_CACHE = True
    MAX_CACHE_SIZE = 100

    # ===========================
    # Debug
    # ===========================

    DEBUG = True