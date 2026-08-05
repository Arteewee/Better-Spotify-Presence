import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:

    # ===========================
    # Spotify Profile Switch
    # ===========================

    ACTIVE_SPOTIFY_PROFILE = os.getenv(
        "ACTIVE_SPOTIFY_PROFILE",
        "primary",
    ).strip().lower()

    SPOTIFY_PROFILES = {
        "primary": {
            "client_id": os.getenv(
                "SPOTIFY_PRIMARY_CLIENT_ID"
            ),
            "client_secret": os.getenv(
                "SPOTIFY_PRIMARY_CLIENT_SECRET"
            ),
            "redirect_uri": os.getenv(
                "SPOTIFY_PRIMARY_REDIRECT_URI"
            ),
        },
        "secondary": {
            "client_id": os.getenv(
                "SPOTIFY_SECONDARY_CLIENT_ID"
            ),
            "client_secret": os.getenv(
                "SPOTIFY_SECONDARY_CLIENT_SECRET"
            ),
            "redirect_uri": os.getenv(
                "SPOTIFY_SECONDARY_REDIRECT_URI"
            ),
        },
    }

    if ACTIVE_SPOTIFY_PROFILE not in SPOTIFY_PROFILES:
        raise ValueError(
            "ACTIVE_SPOTIFY_PROFILE harus "
            "'primary' atau 'secondary'."
        )

    ACTIVE_SPOTIFY_CONFIG = SPOTIFY_PROFILES[
        ACTIVE_SPOTIFY_PROFILE
    ]

    SPOTIFY_CLIENT_ID = (
        ACTIVE_SPOTIFY_CONFIG["client_id"]
    )

    SPOTIFY_CLIENT_SECRET = (
        ACTIVE_SPOTIFY_CONFIG["client_secret"]
    )

    SPOTIFY_REDIRECT_URI = (
        ACTIVE_SPOTIFY_CONFIG["redirect_uri"]
    )

    if not all(
        [
            SPOTIFY_CLIENT_ID,
            SPOTIFY_CLIENT_SECRET,
            SPOTIFY_REDIRECT_URI,
        ]
    ):
        raise ValueError(
            "Credential Spotify untuk profile "
            f"'{ACTIVE_SPOTIFY_PROFILE}' belum lengkap."
        )

    # ===========================
    # Local App Data
    # ===========================

    APP_DATA_DIR = (
        Path(
            os.getenv(
                "LOCALAPPDATA",
                str(Path.home()),
            )
        )
        / "BetterSpotifyPresence"
    )

    APP_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # OAuth token cache dipisahkan per profile.
    SPOTIFY_TOKEN_CACHE_PATH = str(
        APP_DATA_DIR
        / (
            f"spotify_oauth_"
            f"{ACTIVE_SPOTIFY_PROFILE}.cache"
        )
    )

    # ===========================
    # Discord
    # ===========================

    DISCORD_CLIENT_ID = os.getenv(
        "DISCORD_CLIENT_ID"
    )

    if not DISCORD_CLIENT_ID:
        raise ValueError(
            "DISCORD_CLIENT_ID belum diisi."
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

    # Timeout Spotify API.
    REQUEST_TIMEOUT = 10

    # ===========================
    # Lyrics Providers
    # ===========================

    # Timeout per provider. Jika satu provider lambat,
    # loader langsung mencoba provider berikutnya.
    LYRICS_PROVIDER_TIMEOUT = 4

    # Confidence minimal untuk hasil pencarian fuzzy.
    LYRICS_MIN_CONFIDENCE = 0.72

    # Maksimum jumlah lagu pada cache offline.
    PERSISTENT_LYRICS_CACHE_SIZE = 500

    # Diagnostics terminal.
    DIAGNOSTICS_ENABLED = True
    DIAGNOSTICS_INTERVAL = 60.0

    # Endpoint resmi LRCLIB.
    LRCLIB_GET_URL = (
        "https://lrclib.net/api/get"
    )

    LRCLIB_SEARCH_URL = (
        "https://lrclib.net/api/search"
    )

    # Opsional: URL instance NeteaseCloudMusicApi milik sendiri,
    # contoh http://127.0.0.1:3000
    # Kosongkan jika tidak digunakan.
    NETEASE_API_BASE_URL = os.getenv(
        "NETEASE_API_BASE_URL",
        "",
    ).strip()

    # Fallback cooldown jika Spotify mengirim 429 tetapi tidak
    # menyertakan Retry-After yang valid.
    DEFAULT_RATE_LIMIT_SECONDS = 60

    # Maksimum nilai Retry-After yang diterima.
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