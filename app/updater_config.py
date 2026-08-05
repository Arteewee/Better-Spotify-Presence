from pathlib import Path

from config import Config
from version import APP_VERSION


class UpdaterConfig:
    GITHUB_OWNER = "Arteewee"
    GITHUB_REPOSITORY = "Better-Spotify-Presence"

    GITHUB_API_BASE = "https://api.github.com"
    RELEASES_API_URL = (
        f"{GITHUB_API_BASE}/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPOSITORY}/releases"
    )
    LATEST_RELEASE_API_URL = f"{RELEASES_API_URL}/latest"

    CURRENT_VERSION = APP_VERSION
    DEFAULT_CHANNEL = "stable"
    VALID_CHANNELS = {"stable", "beta", "nightly"}

    REQUEST_TIMEOUT = 15.0
    USER_AGENT = f"BetterSpotifyPresence/{APP_VERSION}"
    GITHUB_API_VERSION = "2026-03-10"

    MANIFEST_ASSET_NAME = "update-manifest.json"
    DOWNLOAD_CHUNK_SIZE = 1024 * 128

    UPDATE_DIR = Path(Config.APP_DATA_DIR) / "updates"
    DOWNLOAD_DIR = UPDATE_DIR / "downloads"
    STAGING_DIR = UPDATE_DIR / "staging"
    BACKUP_DIR = UPDATE_DIR / "backup"
    STATE_FILE = UPDATE_DIR / "updater-state.json"

    @classmethod
    def ensure_directories(cls) -> None:
        for directory in (
            cls.UPDATE_DIR,
            cls.DOWNLOAD_DIR,
            cls.STAGING_DIR,
            cls.BACKUP_DIR,
        ):
            directory.mkdir(parents=True, exist_ok=True)