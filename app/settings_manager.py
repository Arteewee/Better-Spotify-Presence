import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from dotenv import dotenv_values, set_key

from config import Config
from app.profile_manager import profiles


class SettingsManager:
    """
    Central settings manager untuk Spotify+.

    Settings dibagi menjadi dua kelompok:

    1. Environment settings
       - Spotify profile
       - Client ID / Client Secret
       - Redirect URI
       - Discord Client ID

       Disimpan di file .env.

    2. Application preferences
       - Start engine saat aplikasi dibuka
       - Minimize to tray
       - Now playing notification
       - Diagnostics
       - Polling interval
       - Lyrics provider timeout

       Disimpan di:
       %LOCALAPPDATA%/BetterSpotifyPresence/settings.json
    """

    DEFAULT_PREFERENCES: dict[str, Any] = {
        "start_engine_on_launch": True,
        "minimize_to_tray": True,
        "show_now_playing_notification": True,
        "diagnostics_enabled": True,
        "diagnostics_interval": 60.0,
        "spotify_refresh_rate": 4.0,
        "spotify_fast_refresh_rate": 1.0,
        "spotify_ending_window": 12.0,
        "lyrics_provider_timeout": 4.0,
        "lyrics_min_confidence": 0.72,
        "check_updates_on_startup": True,
        "update_channel": "stable",
    }


    def __init__(self) -> None:
        self._lock = threading.RLock()

        self.project_root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        self.env_path = (
            self.project_root
            / ".env"
        )

        self.settings_path = (
            Path(Config.APP_DATA_DIR)
            / "settings.json"
        )

        self._preferences: dict[str, Any] = {}

        self.reload()

    # ==========================================================
    # Loading / Saving
    # ==========================================================

    def reload(self) -> None:
        """
        Reload preferences dari disk.
        """

        with self._lock:
            loaded = self._load_preferences()

            merged = (
                self.DEFAULT_PREFERENCES.copy()
            )

            merged.update(
                loaded
            )

            self._preferences = (
                self._validate_preferences(
                    merged
                )
            )

    def _load_preferences(
        self,
    ) -> dict[str, Any]:
        if not self.settings_path.exists():
            return {}

        try:
            with self.settings_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(
                    file
                )

            if isinstance(data, dict):
                return data

        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            print(
                "[Settings] Failed to load "
                f"settings: {error}"
            )

        return {}

    def save(self) -> None:
        """
        Save application preferences secara atomic.
        """

        with self._lock:
            self.settings_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            temporary_path = (
                self.settings_path
                .with_suffix(".tmp")
            )

            try:
                with temporary_path.open(
                    "w",
                    encoding="utf-8",
                ) as file:
                    json.dump(
                        self._preferences,
                        file,
                        indent=2,
                        ensure_ascii=False,
                    )

                temporary_path.replace(
                    self.settings_path
                )

            except OSError as error:
                print(
                    "[Settings] Failed to save "
                    f"settings: {error}"
                )

                raise

    # ==========================================================
    # Generic Preferences API
    # ==========================================================

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        with self._lock:
            return self._preferences.get(
                key,
                default,
            )

    def set(
        self,
        key: str,
        value: Any,
        *,
        save: bool = True,
    ) -> None:
        if key not in self.DEFAULT_PREFERENCES:
            raise KeyError(
                f"Unknown setting: {key}"
            )

        validated = (
            self._validate_single(
                key,
                value,
            )
        )

        with self._lock:
            self._preferences[
                key
            ] = validated

            if save:
                self.save()

    def update(
        self,
        values: dict[str, Any],
        *,
        save: bool = True,
    ) -> None:
        validated_values: dict[
            str,
            Any,
        ] = {}

        for key, value in values.items():
            if (
                key
                not in self.DEFAULT_PREFERENCES
            ):
                raise KeyError(
                    f"Unknown setting: {key}"
                )

            validated_values[key] = (
                self._validate_single(
                    key,
                    value,
                )
            )

        with self._lock:
            self._preferences.update(
                validated_values
            )

            if save:
                self.save()

    def reset_preferences(
        self,
    ) -> None:
        with self._lock:
            self._preferences = (
                self.DEFAULT_PREFERENCES.copy()
            )

            self.save()

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            return self._preferences.copy()

    # ==========================================================
    # Validation
    # ==========================================================

    def _validate_preferences(
        self,
        preferences: dict[str, Any],
    ) -> dict[str, Any]:
        validated: dict[str, Any] = {}

        for key, default in (
            self.DEFAULT_PREFERENCES.items()
        ):
            value = preferences.get(
                key,
                default,
            )

            try:
                validated[key] = (
                    self._validate_single(
                        key,
                        value,
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                validated[key] = default

        return validated

    @staticmethod
    def _validate_single(
        key: str,
        value: Any,
    ) -> Any:
        boolean_keys = {
            "start_engine_on_launch",
            "minimize_to_tray",
            "show_now_playing_notification",
            "diagnostics_enabled",
            "check_updates_on_startup",
        }

        if key in boolean_keys:
            if isinstance(value, bool):
                return value

            if isinstance(value, str):
                normalized = (
                    value.strip().lower()
                )

                if normalized in {
                    "1",
                    "true",
                    "yes",
                    "on",
                }:
                    return True

                if normalized in {
                    "0",
                    "false",
                    "no",
                    "off",
                }:
                    return False

            raise TypeError(
                f"{key} must be boolean."
            )

        if key == "update_channel":
            channel = str(
                value
            ).strip().lower()

            if channel not in {
                "stable",
                "beta",
                "nightly",
            }:
                raise ValueError(
                    "update_channel must be stable, "
                    "beta, or nightly."
                )

            return channel

        numeric_ranges = {
            "diagnostics_interval":
                (5.0, 3600.0),

            "spotify_refresh_rate":
                (1.0, 30.0),

            "spotify_fast_refresh_rate":
                (0.5, 10.0),

            "spotify_ending_window":
                (1.0, 60.0),

            "lyrics_provider_timeout":
                (1.0, 30.0),

            "lyrics_min_confidence":
                (0.0, 1.0),
        }

        if key in numeric_ranges:
            number = float(
                value
            )

            minimum, maximum = (
                numeric_ranges[key]
            )

            if not (
                minimum
                <= number
                <= maximum
            ):
                raise ValueError(
                    f"{key} must be between "
                    f"{minimum} and {maximum}."
                )

            return number

        return value

    # ==========================================================
    # Environment / Spotify Profiles
    # ==========================================================

    def get_env_values(
        self,
    ) -> dict[str, Optional[str]]:
        values = dotenv_values(
            self.env_path
        )

        return {
            key: (
                str(value)
                if value is not None
                else None
            )
            for key, value
            in values.items()
        }

    def list_profiles(
        self,
    ) -> list[str]:
        return profiles.list_profiles()

    def get_active_profile(self) -> str:
        return (
            profiles
            .get_active_profile_name()
        )

    def set_active_profile(
        self,
        profile_name: str,
    ) -> bool:
        return profiles.set_active_profile(
            profile_name
        )

    def get_profile(
        self,
        profile_name: str,
    ) -> dict[str, str]:
        profile = profiles.get_profile(
            profile_name
        )

        return {
            "name": str(
                profile.get(
                    "name",
                    profile_name,
                )
            ),

            "client_id": str(
                profile.get(
                    "client_id",
                    "",
                )
            ),

            "client_secret": str(
                profile.get(
                    "client_secret",
                    "",
                )
            ),

            "redirect_uri": str(
                profile.get(
                    "redirect_uri",
                    "",
                )
            ),
        }

    def save_profile(
        self,
        profile_name: str,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        profiles.update_profile(
            profile_name,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

    def add_profile(
        self,
        profile_name: str,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        make_active: bool = False,
    ) -> dict[str, Any]:
        return profiles.add_profile(
            profile_name,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            make_active=make_active,
        )

    def rename_profile(
        self,
        old_name: str,
        new_name: str,
    ) -> bool:
        return profiles.rename_profile(
            old_name,
            new_name,
        )

    def duplicate_profile(
        self,
        source_name: str,
        new_name: str,
    ) -> dict[str, Any]:
        return profiles.duplicate_profile(
            source_name,
            new_name,
        )

    def delete_profile(
        self,
        profile_name: str,
    ) -> bool:
        return profiles.delete_profile(
            profile_name
        )

    def get_profile_snapshot(
        self,
    ) -> dict[str, Any]:
        return profiles.export_safe_snapshot()

    def get_discord_client_id(
        self,
    ) -> str:
        values = self.get_env_values()

        return (
            values.get(
                "DISCORD_CLIENT_ID"
            )
            or ""
        )

    def set_discord_client_id(
        self,
        client_id: str,
    ) -> None:
        client_id = (
            client_id.strip()
        )

        if not client_id:
            raise ValueError(
                "Discord Client ID is required."
            )

        self._ensure_env_file()

        set_key(
            str(self.env_path),
            "DISCORD_CLIENT_ID",
            client_id,
        )

    def _ensure_env_file(self) -> None:
        if self.env_path.exists():
            return

        self.env_path.touch(
            exist_ok=True
        )

    # ==========================================================
    # Runtime Config Snapshot
    # ==========================================================

    def get_runtime_preferences(
        self,
    ) -> dict[str, Any]:
        """
        Snapshot yang nanti dipakai desktop.py, tray.py,
        settings window, dan updater.
        """

        return {
            "start_engine_on_launch":
                self.get(
                    "start_engine_on_launch"
                ),

            "minimize_to_tray":
                self.get(
                    "minimize_to_tray"
                ),

            "show_now_playing_notification":
                self.get(
                    "show_now_playing_notification"
                ),

            "diagnostics_enabled":
                self.get(
                    "diagnostics_enabled"
                ),

            "diagnostics_interval":
                self.get(
                    "diagnostics_interval"
                ),

            "spotify_refresh_rate":
                self.get(
                    "spotify_refresh_rate"
                ),

            "spotify_fast_refresh_rate":
                self.get(
                    "spotify_fast_refresh_rate"
                ),

            "spotify_ending_window":
                self.get(
                    "spotify_ending_window"
                ),

            "lyrics_provider_timeout":
                self.get(
                    "lyrics_provider_timeout"
                ),

            "lyrics_min_confidence":
                self.get(
                    "lyrics_min_confidence"
                ),

            "check_updates_on_startup":
                self.get(
                    "check_updates_on_startup"
                ),

            "update_channel":
                self.get(
                    "update_channel"
                ),
        }


settings = SettingsManager()