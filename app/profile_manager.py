import json
import os
import re
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from dotenv import dotenv_values


PROFILE_FILE_VERSION = 1

PROFILE_NAME_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,49}$"
)


class ProfileManager:
    """
    Unlimited Spotify developer profile storage.

    Profiles disimpan di:
    %LOCALAPPDATA%/BetterSpotifyPresence/profiles.json

    Saat profiles.json belum ada, credential legacy dari .env:
    - primary
    - secondary

    akan dimigrasikan otomatis tanpa menghapus isi .env.
    """

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

        self.app_data_dir = (
            Path(
                os.getenv(
                    "LOCALAPPDATA",
                    str(Path.home()),
                )
            )
            / "BetterSpotifyPresence"
        )

        self.app_data_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.path = (
            self.app_data_dir
            / "profiles.json"
        )

        self._data: dict[str, Any] = (
            self._empty_data()
        )

        self.reload()

    @staticmethod
    def _empty_data() -> dict[str, Any]:
        return {
            "version": PROFILE_FILE_VERSION,
            "active_profile": "",
            "profiles": {},
            "created_at": time.time(),
            "updated_at": time.time(),
        }

    # ========================================================
    # Load / Save / Migration
    # ========================================================

    def reload(self) -> None:
        with self._lock:
            if self.path.exists():
                self._data = self._load_file()
            else:
                self._data = (
                    self._migrate_legacy_env()
                )

                self._save()

            self._repair_data()

    def _load_file(self) -> dict[str, Any]:
        try:
            with self.path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            if not isinstance(data, dict):
                raise ValueError(
                    "profiles.json root must be an object."
                )

            return data

        except (
            OSError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            backup_path = self.path.with_suffix(
                ".broken.json"
            )

            try:
                self.path.replace(
                    backup_path
                )

            except OSError:
                pass

            print(
                "[Profiles] Invalid profiles.json. "
                f"Creating a new file: {error}"
            )

            return self._migrate_legacy_env()

    def _migrate_legacy_env(
        self,
    ) -> dict[str, Any]:
        values = dotenv_values(
            self.env_path
        )

        profiles: dict[
            str,
            dict[str, Any],
        ] = {}

        for legacy_name in (
            "primary",
            "secondary",
        ):
            prefix = (
                f"SPOTIFY_{legacy_name.upper()}"
            )

            client_id = (
                values.get(
                    f"{prefix}_CLIENT_ID"
                )
                or ""
            ).strip()

            client_secret = (
                values.get(
                    f"{prefix}_CLIENT_SECRET"
                )
                or ""
            ).strip()

            redirect_uri = (
                values.get(
                    f"{prefix}_REDIRECT_URI"
                )
                or ""
            ).strip()

            if not any(
                (
                    client_id,
                    client_secret,
                    redirect_uri,
                )
            ):
                continue

            profiles[
                legacy_name
            ] = {
                "name": legacy_name,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "created_at": time.time(),
                "updated_at": time.time(),
                "legacy_source": True,
            }

        requested_active = (
            values.get(
                "ACTIVE_SPOTIFY_PROFILE"
            )
            or ""
        ).strip()

        if (
            requested_active
            not in profiles
        ):
            requested_active = (
                next(
                    iter(profiles),
                    "",
                )
            )

        print(
            "[Profiles] Legacy .env profiles "
            f"migrated: {len(profiles)}"
        )

        return {
            "version": PROFILE_FILE_VERSION,
            "active_profile": requested_active,
            "profiles": profiles,
            "created_at": time.time(),
            "updated_at": time.time(),
        }

    def _repair_data(self) -> None:
        changed = False

        if not isinstance(
            self._data.get(
                "profiles"
            ),
            dict,
        ):
            self._data[
                "profiles"
            ] = {}

            changed = True

        profiles = self._data[
            "profiles"
        ]

        invalid_keys = []

        for profile_name, profile in (
            profiles.items()
        ):
            if not isinstance(
                profile,
                dict,
            ):
                invalid_keys.append(
                    profile_name
                )

                continue

            profile.setdefault(
                "name",
                profile_name,
            )

            profile.setdefault(
                "client_id",
                "",
            )

            profile.setdefault(
                "client_secret",
                "",
            )

            profile.setdefault(
                "redirect_uri",
                "",
            )

            profile.setdefault(
                "created_at",
                time.time(),
            )

            profile.setdefault(
                "updated_at",
                time.time(),
            )

        for profile_name in invalid_keys:
            profiles.pop(
                profile_name,
                None,
            )

            changed = True

        active = str(
            self._data.get(
                "active_profile",
                "",
            )
            or ""
        )

        if active not in profiles:
            self._data[
                "active_profile"
            ] = next(
                iter(profiles),
                "",
            )

            changed = True

        self._data[
            "version"
        ] = PROFILE_FILE_VERSION

        if changed:
            self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._data[
            "updated_at"
        ] = time.time()

        temporary = self.path.with_suffix(
            ".tmp"
        )

        with temporary.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                self._data,
                file,
                indent=2,
                ensure_ascii=False,
            )

        temporary.replace(
            self.path
        )

    # ========================================================
    # Validation
    # ========================================================

    @staticmethod
    def validate_profile_name(
        profile_name: str,
    ) -> str:
        name = " ".join(
            profile_name.split()
        )

        if not name:
            raise ValueError(
                "Profile name is required."
            )

        if not PROFILE_NAME_PATTERN.fullmatch(
            name
        ):
            raise ValueError(
                "Profile name may contain letters, numbers, "
                "spaces, dots, underscores, and hyphens "
                "(maximum 50 characters)."
            )

        return name

    @staticmethod
    def validate_credentials(
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> tuple[str, str, str]:
        client_id = client_id.strip()
        client_secret = client_secret.strip()
        redirect_uri = redirect_uri.strip()

        if not client_id:
            raise ValueError(
                "Spotify Client ID is required."
            )

        if not client_secret:
            raise ValueError(
                "Spotify Client Secret is required."
            )

        if not (
            redirect_uri.startswith(
                "http://"
            )
            or redirect_uri.startswith(
                "https://"
            )
        ):
            raise ValueError(
                "Spotify Redirect URI must use "
                "http:// or https://."
            )

        return (
            client_id,
            client_secret,
            redirect_uri,
        )

    # ========================================================
    # Public API
    # ========================================================

    def list_profiles(
        self,
    ) -> list[str]:
        with self._lock:
            return list(
                self._data[
                    "profiles"
                ].keys()
            )

    def count(self) -> int:
        return len(
            self.list_profiles()
        )

    def exists(
        self,
        profile_name: str,
    ) -> bool:
        with self._lock:
            return (
                profile_name
                in self._data[
                    "profiles"
                ]
            )

    def get_active_profile_name(
        self,
    ) -> str:
        with self._lock:
            return str(
                self._data.get(
                    "active_profile",
                    "",
                )
                or ""
            )

    def get_active_profile(
        self,
    ) -> dict[str, Any]:
        name = (
            self.get_active_profile_name()
        )

        if not name:
            return {
                "name": "",
                "client_id": "",
                "client_secret": "",
                "redirect_uri": "",
            }

        return self.get_profile(
            name
        )

    def set_active_profile(
        self,
        profile_name: str,
    ) -> bool:
        name = self.validate_profile_name(
            profile_name
        )

        with self._lock:
            if (
                name
                not in self._data[
                    "profiles"
                ]
            ):
                raise ValueError(
                    f"Unknown Spotify profile: {name}"
                )

            if (
                name
                == self._data.get(
                    "active_profile"
                )
            ):
                return False

            self._data[
                "active_profile"
            ] = name

            self._save()

            return True

    def get_profile(
        self,
        profile_name: str,
    ) -> dict[str, Any]:
        name = self.validate_profile_name(
            profile_name
        )

        with self._lock:
            profile = self._data[
                "profiles"
            ].get(name)

            if profile is None:
                raise ValueError(
                    f"Unknown Spotify profile: {name}"
                )

            return deepcopy(
                profile
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
        name = self.validate_profile_name(
            profile_name
        )

        (
            client_id,
            client_secret,
            redirect_uri,
        ) = self.validate_credentials(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

        with self._lock:
            if (
                name
                in self._data[
                    "profiles"
                ]
            ):
                raise ValueError(
                    f"Profile already exists: {name}"
                )

            now = time.time()

            profile = {
                "name": name,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "created_at": now,
                "updated_at": now,
                "legacy_source": False,
            }

            self._data[
                "profiles"
            ][name] = profile

            if (
                make_active
                or not self._data.get(
                    "active_profile"
                )
            ):
                self._data[
                    "active_profile"
                ] = name

            self._save()

            return deepcopy(
                profile
            )

    def update_profile(
        self,
        profile_name: str,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        name = self.validate_profile_name(
            profile_name
        )

        (
            client_id,
            client_secret,
            redirect_uri,
        ) = self.validate_credentials(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

        with self._lock:
            profile = self._data[
                "profiles"
            ].get(name)

            if profile is None:
                raise ValueError(
                    f"Unknown Spotify profile: {name}"
                )

            profile[
                "client_id"
            ] = client_id

            profile[
                "client_secret"
            ] = client_secret

            profile[
                "redirect_uri"
            ] = redirect_uri

            profile[
                "updated_at"
            ] = time.time()

            self._save()

            return deepcopy(
                profile
            )

    def rename_profile(
        self,
        old_name: str,
        new_name: str,
    ) -> bool:
        old_name = self.validate_profile_name(
            old_name
        )

        new_name = self.validate_profile_name(
            new_name
        )

        if old_name == new_name:
            return False

        with self._lock:
            profiles = self._data[
                "profiles"
            ]

            if old_name not in profiles:
                raise ValueError(
                    f"Unknown Spotify profile: {old_name}"
                )

            if new_name in profiles:
                raise ValueError(
                    f"Profile already exists: {new_name}"
                )

            profile = profiles.pop(
                old_name
            )

            profile[
                "name"
            ] = new_name

            profile[
                "updated_at"
            ] = time.time()

            profiles[
                new_name
            ] = profile

            if (
                self._data.get(
                    "active_profile"
                )
                == old_name
            ):
                self._data[
                    "active_profile"
                ] = new_name

            self._save()

            return True

    def duplicate_profile(
        self,
        source_name: str,
        new_name: str,
    ) -> dict[str, Any]:
        source = self.get_profile(
            source_name
        )

        return self.add_profile(
            new_name,
            client_id=source[
                "client_id"
            ],
            client_secret=source[
                "client_secret"
            ],
            redirect_uri=source[
                "redirect_uri"
            ],
            make_active=False,
        )

    def delete_profile(
        self,
        profile_name: str,
    ) -> bool:
        name = self.validate_profile_name(
            profile_name
        )

        with self._lock:
            profiles = self._data[
                "profiles"
            ]

            if name not in profiles:
                return False

            if len(profiles) <= 1:
                raise ValueError(
                    "The last Spotify profile cannot be deleted."
                )

            profiles.pop(
                name
            )

            if (
                self._data.get(
                    "active_profile"
                )
                == name
            ):
                self._data[
                    "active_profile"
                ] = next(
                    iter(profiles)
                )

            self._save()

            return True

    def get_token_cache_path(
        self,
        profile_name: Optional[str] = None,
    ) -> str:
        name = (
            profile_name
            or self.get_active_profile_name()
            or "default"
        )

        safe_name = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "_",
            name,
        ).strip("_")

        return str(
            self.app_data_dir
            / (
                "spotify_oauth_"
                f"{safe_name}.cache"
            )
        )

    def export_safe_snapshot(
        self,
    ) -> dict[str, Any]:
        """
        Snapshot tanpa client secret untuk diagnostics/UI.
        """

        with self._lock:
            return {
                "active_profile":
                    self.get_active_profile_name(),

                "profiles": [
                    {
                        "name": name,
                        "has_client_id": bool(
                            profile.get(
                                "client_id"
                            )
                        ),
                        "has_client_secret": bool(
                            profile.get(
                                "client_secret"
                            )
                        ),
                        "redirect_uri":
                            profile.get(
                                "redirect_uri",
                                "",
                            ),
                    }
                    for name, profile
                    in self._data[
                        "profiles"
                    ].items()
                ],

                "count":
                    len(
                        self._data[
                            "profiles"
                        ]
                    ),

                "path":
                    str(self.path),
            }


profiles = ProfileManager()