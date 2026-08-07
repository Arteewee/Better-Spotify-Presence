import os
from pathlib import Path

from dotenv import load_dotenv
from app.profile_manager import profiles

load_dotenv()


class Config:

    # ===========================
    # Spotify Profile Manager
    # ===========================

    ACTIVE_SPOTIFY_PROFILE = (
        profiles.get_active_profile_name()
    )

    SPOTIFY_PROFILES = {
        profile_name:
            profiles.get_profile(
                profile_name
            )
        for profile_name
        in profiles.list_profiles()
    }

    if not ACTIVE_SPOTIFY_PROFILE:
        raise ValueError(
            "Belum ada Spotify profile. "
            "Tambahkan credential di profiles.json "
            "atau isi legacy primary/secondary di .env "
            "untuk migrasi otomatis."
        )

    ACTIVE_SPOTIFY_CONFIG = (
        profiles.get_active_profile()
    )

    SPOTIFY_CLIENT_ID = (
        ACTIVE_SPOTIFY_CONFIG[
            "client_id"
        ]
    )

    SPOTIFY_CLIENT_SECRET = (
        ACTIVE_SPOTIFY_CONFIG[
            "client_secret"
        ]
    )

    SPOTIFY_REDIRECT_URI = (
        ACTIVE_SPOTIFY_CONFIG[
            "redirect_uri"
        ]
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
    SPOTIFY_TOKEN_CACHE_PATH = (
        profiles.get_token_cache_path(
            ACTIVE_SPOTIFY_PROFILE
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

    # ===========================
    # Runtime Settings
    # ===========================

    @classmethod
    def apply_runtime_settings(
        cls,
        preferences: dict,
    ) -> dict:
        """
        Terapkan setting yang aman diubah tanpa restart.
        """

        mapping = {
            "spotify_refresh_rate":
                "SPOTIFY_REFRESH_RATE",

            "spotify_fast_refresh_rate":
                "SPOTIFY_FAST_REFRESH_RATE",

            "spotify_ending_window":
                "SPOTIFY_ENDING_WINDOW",

            "lyrics_provider_timeout":
                "LYRICS_PROVIDER_TIMEOUT",

            "lyrics_min_confidence":
                "LYRICS_MIN_CONFIDENCE",

            "diagnostics_enabled":
                "DIAGNOSTICS_ENABLED",

            "diagnostics_interval":
                "DIAGNOSTICS_INTERVAL",
        }

        changed = {}

        for setting_key, attribute_name in mapping.items():
            if setting_key not in preferences:
                continue

            new_value = preferences[
                setting_key
            ]

            old_value = getattr(
                cls,
                attribute_name,
            )

            if old_value == new_value:
                continue

            setattr(
                cls,
                attribute_name,
                new_value,
            )

            changed[setting_key] = {
                "old": old_value,
                "new": new_value,
            }

        return changed