import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

import requests

from app.event_bus import event_bus
from app.logger import logger
from app.update_models import (
    AppVersion,
    ReleaseAsset,
    UpdateCheckResult,
    UpdateManifest,
)
from app.updater_config import UpdaterConfig


class UpdateCheckError(RuntimeError):
    pass


class UpdateDownloadError(RuntimeError):
    pass


ProgressCallback = Callable[
    [dict[str, Any]],
    None,
]


class UpdateManager:
    """
    V2.11 updater foundation.

    Mendukung:
    - GitHub Releases;
    - stable, beta, nightly;
    - update-manifest.json;
    - validasi manifest;
    - perbandingan versi;
    - event dan logging.

    Belum melakukan download atau instalasi update.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version":
                    UpdaterConfig.GITHUB_API_VERSION,
                "User-Agent":
                    UpdaterConfig.USER_AGENT,
            }
        )

        self.last_result: Optional[UpdateCheckResult] = None
        self.last_error: Optional[str] = None
        self.last_download_path: Optional[str] = None

        UpdaterConfig.ensure_directories()

    def check_for_updates(
        self,
        *,
        channel: Optional[str] = None,
    ) -> UpdateCheckResult:
        selected_channel = (
            channel
            or UpdaterConfig.DEFAULT_CHANNEL
        ).strip().lower()

        if selected_channel not in UpdaterConfig.VALID_CHANNELS:
            raise ValueError(
                "Update channel must be one of: "
                + ", ".join(
                    sorted(UpdaterConfig.VALID_CHANNELS)
                )
            )

        event_bus.publish(
            "updater.check_started",
            source="update_manager",
            channel=selected_channel,
        )

        logger.info(
            "Checking for updates",
            category="UPDATER",
            context={
                "channel": selected_channel,
                "current_version":
                    UpdaterConfig.CURRENT_VERSION,
            },
        )

        try:
            releases = self._fetch_releases(
                selected_channel
            )

            release = self._select_release(
                releases,
                selected_channel,
            )

            assets = self._parse_assets(
                release
            )

            manifest_asset = self._find_asset(
                assets,
                UpdaterConfig.MANIFEST_ASSET_NAME,
            )

            manifest_data = self._fetch_json(
                manifest_asset.download_url
            )

            manifest = UpdateManifest.from_dict(
                manifest_data
            )

            self._validate_channel(
                manifest,
                selected_channel,
            )

            update_asset = self._find_asset(
                assets,
                manifest.asset_name,
            )

            current_version = AppVersion.parse(
                UpdaterConfig.CURRENT_VERSION
            )

            latest_version = manifest.version
            has_update = current_version < latest_version
            supported = not (
                current_version
                < manifest.minimum_version
            )

            result = UpdateCheckResult(
                current_version=current_version,
                latest_version=latest_version,
                channel=selected_channel,
                has_update=has_update,
                mandatory=(
                    manifest.mandatory
                    or not supported
                ),
                supported=supported,
                manifest=manifest,
                update_asset=update_asset,
                manifest_asset=manifest_asset,
                github_tag=str(
                    release.get("tag_name", "")
                ),
                github_release_name=str(
                    release.get("name", "")
                ),
                github_release_url=str(
                    release.get("html_url", "")
                ),
                published_at=str(
                    release.get("published_at", "")
                ),
            )

            with self._lock:
                self.last_result = result
                self.last_error = None

            if result.has_update:
                logger.info(
                    "Update available",
                    category="UPDATER",
                    context={
                        "current":
                            str(result.current_version),
                        "latest":
                            str(result.latest_version),
                        "mandatory":
                            result.mandatory,
                    },
                )

                event_bus.publish(
                    "updater.update_available",
                    source="update_manager",
                    result=result,
                )

            else:
                logger.info(
                    "Application is up to date",
                    category="UPDATER",
                    context={
                        "version":
                            str(current_version),
                    },
                )

                event_bus.publish(
                    "updater.up_to_date",
                    source="update_manager",
                    result=result,
                )

            return result

        except Exception as error:
            message = str(error)

            with self._lock:
                self.last_error = message

            logger.warning(
                "Update check failed",
                category="UPDATER",
                context={
                    "error": message,
                    "channel": selected_channel,
                },
            )

            event_bus.publish(
                "updater.check_failed",
                source="update_manager",
                message=message,
                channel=selected_channel,
            )

            if isinstance(error, UpdateCheckError):
                raise

            raise UpdateCheckError(
                message
            ) from error

    def download_update(
        self,
        result: UpdateCheckResult,
        *,
        progress_callback: Optional[
            ProgressCallback
        ] = None,
        cancel_event: Optional[
            threading.Event
        ] = None,
    ) -> Path:
        """
        Download update package to the local update directory,
        verify SHA-256, and atomically rename the completed file.

        This method is blocking and should run in a worker thread.
        """

        if not isinstance(
            result,
            UpdateCheckResult,
        ):
            raise TypeError(
                "result must be UpdateCheckResult."
            )

        if not result.has_update:
            raise UpdateDownloadError(
                "No update is available."
            )

        asset = result.update_asset

        safe_name = Path(
            asset.name
        ).name

        if safe_name != asset.name:
            raise UpdateDownloadError(
                "Unsafe update asset name."
            )

        destination = (
            UpdaterConfig.DOWNLOAD_DIR
            / safe_name
        )

        temporary = destination.with_suffix(
            destination.suffix + ".part"
        )

        try:
            if temporary.exists():
                temporary.unlink()

            if destination.exists():
                destination.unlink()

        except OSError as error:
            raise UpdateDownloadError(
                f"Unable to prepare download file: {error}"
            ) from error

        event_bus.publish(
            "updater.download_started",
            source="update_manager",
            version=str(
                result.latest_version
            ),
            asset_name=asset.name,
            total_bytes=asset.size,
        )

        logger.info(
            "Update download started",
            category="UPDATER",
            context={
                "version":
                    str(
                        result.latest_version
                    ),
                "asset":
                    asset.name,
                "size":
                    asset.size,
            },
        )

        started_at = time.monotonic()
        downloaded = 0
        hasher = hashlib.sha256()

        try:
            with self.session.get(
                asset.download_url,
                stream=True,
                timeout=(
                    UpdaterConfig
                    .REQUEST_TIMEOUT
                ),
            ) as response:
                response.raise_for_status()

                total = int(
                    response.headers.get(
                        "Content-Length",
                        asset.size,
                    )
                    or 0
                )

                with temporary.open(
                    "wb"
                ) as file:
                    for chunk in response.iter_content(
                        chunk_size=(
                            UpdaterConfig
                            .DOWNLOAD_CHUNK_SIZE
                        )
                    ):
                        if (
                            cancel_event is not None
                            and cancel_event.is_set()
                        ):
                            raise UpdateDownloadError(
                                "Update download cancelled."
                            )

                        if not chunk:
                            continue

                        file.write(chunk)
                        hasher.update(chunk)
                        downloaded += len(chunk)

                        elapsed = max(
                            0.001,
                            time.monotonic()
                            - started_at,
                        )

                        speed = (
                            downloaded
                            / elapsed
                        )

                        percent = (
                            downloaded
                            / total
                            * 100.0
                            if total > 0
                            else 0.0
                        )

                        progress = {
                            "downloaded_bytes":
                                downloaded,
                            "total_bytes":
                                total,
                            "percent":
                                percent,
                            "speed_bytes":
                                speed,
                            "asset_name":
                                asset.name,
                        }

                        if progress_callback:
                            progress_callback(
                                progress
                            )

                        event_bus.publish(
                            "updater.download_progress",
                            source="update_manager",
                            **progress,
                        )

            actual_hash = (
                hasher.hexdigest()
                .lower()
            )

            expected_hash = (
                result.manifest.sha256
                .lower()
            )

            event_bus.publish(
                "updater.verifying",
                source="update_manager",
                asset_name=asset.name,
            )

            if actual_hash != expected_hash:
                raise UpdateDownloadError(
                    "SHA-256 verification failed. "
                    f"Expected {expected_hash}, "
                    f"received {actual_hash}."
                )

            os.replace(
                temporary,
                destination,
            )

            with self._lock:
                self.last_download_path = str(
                    destination
                )
                self.last_error = None

            logger.info(
                "Update package downloaded and verified",
                category="UPDATER",
                context={
                    "path":
                        str(destination),
                    "sha256":
                        actual_hash,
                },
            )

            event_bus.publish(
                "updater.download_completed",
                source="update_manager",
                path=str(
                    destination
                ),
                sha256=actual_hash,
                version=str(
                    result.latest_version
                ),
            )

            return destination

        except requests.RequestException as error:
            message = (
                "Unable to download the update: "
                f"{error}"
            )

            self._handle_download_failure(
                temporary,
                message,
            )

            raise UpdateDownloadError(
                message
            ) from error

        except Exception as error:
            message = str(error)

            self._handle_download_failure(
                temporary,
                message,
            )

            if isinstance(
                error,
                UpdateDownloadError,
            ):
                raise

            raise UpdateDownloadError(
                message
            ) from error

    def _handle_download_failure(
        self,
        temporary: Path,
        message: str,
    ) -> None:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass

        with self._lock:
            self.last_error = message

        logger.warning(
            "Update download failed",
            category="UPDATER",
            context={
                "error": message,
            },
        )

        event_bus.publish(
            "updater.download_failed",
            source="update_manager",
            message=message,
        )

    def prepare_install(
        self,
        result: UpdateCheckResult,
        package_path: str | Path,
    ) -> dict[str, str]:
        """
        Create updater instruction file and return launch metadata.

        The helper performs:
        - wait for current app to exit;
        - backup current installation;
        - extract update ZIP;
        - replace application files;
        - rollback on failure;
        - restart Spotify+.
        """

        package = Path(
            package_path
        ).resolve()

        if not package.exists():
            raise UpdateDownloadError(
                "Downloaded update package does not exist."
            )

        if package.suffix.lower() != ".zip":
            raise UpdateDownloadError(
                "Update package must be a ZIP archive."
            )

        if not result.has_update:
            raise UpdateDownloadError(
                "Refusing to install because no newer version is available."
            )

        if (
            result.latest_version
            < result.current_version
        ):
            raise UpdateDownloadError(
                "Updater refused a downgrade."
            )

        install_dir = self._get_install_directory()
        helper_path = self._get_helper_path()

        instruction_path = (
            UpdaterConfig.UPDATE_DIR
            / "pending-update.json"
        )

        backup_dir = (
            UpdaterConfig.BACKUP_DIR
            / (
                "backup-"
                f"{int(time.time())}"
            )
        )

        launch_target = (
            Path(sys.executable).resolve()
            if getattr(sys, "frozen", False)
            else Path(sys.argv[0]).resolve()
        )

        instruction = {
            "package_path":
                str(package),

            "install_dir":
                str(install_dir),

            "backup_dir":
                str(backup_dir),

            "launch_target":
                str(launch_target),

            "launch_args":
                list(sys.argv[1:]),

            "process_id":
                os.getpid(),

            "version":
                str(
                    result.latest_version
                ),

            "backup_retention":
                3,
        }

        temporary = instruction_path.with_suffix(
            ".tmp"
        )

        with temporary.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                instruction,
                file,
                indent=2,
                ensure_ascii=False,
            )

        os.replace(
            temporary,
            instruction_path,
        )

        logger.info(
            "Update installation prepared",
            category="UPDATER",
            context={
                "package":
                    str(package),

                "install_dir":
                    str(install_dir),

                "version":
                    str(
                        result.latest_version
                    ),
            },
        )

        return {
            "helper_path":
                str(helper_path),

            "instruction_path":
                str(instruction_path),
        }

    def launch_installer(
        self,
        result: UpdateCheckResult,
        package_path: str | Path,
    ) -> bool:
        metadata = self.prepare_install(
            result,
            package_path,
        )

        helper_path = Path(
            metadata[
                "helper_path"
            ]
        )

        instruction_path = Path(
            metadata[
                "instruction_path"
            ]
        )

        if getattr(
            sys,
            "frozen",
            False,
        ):
            command = [
                str(helper_path),
                str(instruction_path),
            ]

        else:
            command = [
                sys.executable,
                str(helper_path),
                str(instruction_path),
            ]

        try:
            subprocess.Popen(
                command,
                cwd=str(
                    helper_path.parent
                ),
                close_fds=True,
            )

        except OSError as error:
            logger.error(
                "Failed to launch updater helper",
                category="UPDATER",
                context={
                    "error": str(error),
                },
            )

            event_bus.publish(
                "updater.install_failed",
                source="update_manager",
                message=str(error),
            )

            return False

        event_bus.publish(
            "updater.install_started",
            source="update_manager",
            version=str(
                result.latest_version
            ),
        )

        return True

    @staticmethod
    def _get_install_directory() -> Path:
        if getattr(
            sys,
            "frozen",
            False,
        ):
            return Path(
                sys.executable
            ).resolve().parent

        return Path(
            __file__
        ).resolve().parents[1]

    @staticmethod
    def _get_helper_path() -> Path:
        install_dir = (
            UpdateManager
            ._get_install_directory()
        )

        if getattr(
            sys,
            "frozen",
            False,
        ):
            executable = (
                install_dir
                / "Spotify+Updater.exe"
            )

            if executable.exists():
                return executable

        helper = (
            install_dir
            / "updater"
            / "updater_helper.py"
        )

        if not helper.exists():
            raise UpdateDownloadError(
                "Updater helper was not found."
            )

        return helper

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            result = self.last_result
            error = self.last_error

        return {
            "current_version":
                UpdaterConfig.CURRENT_VERSION,
            "channel":
                UpdaterConfig.DEFAULT_CHANNEL,
            "last_error": error,
            "last_result": result,
            "last_download_path":
                self.last_download_path,
        }

    def _fetch_releases(
        self,
        channel: str,
    ) -> list[dict[str, Any]]:
        if channel == "stable":
            data = self._fetch_json(
                UpdaterConfig.LATEST_RELEASE_API_URL
            )

            if not isinstance(data, dict):
                raise UpdateCheckError(
                    "GitHub latest release response is invalid."
                )

            return [data]

        data = self._fetch_json(
            UpdaterConfig.RELEASES_API_URL,
            params={"per_page": 30},
        )

        if not isinstance(data, list):
            raise UpdateCheckError(
                "GitHub releases response is invalid."
            )

        return [
            release
            for release in data
            if isinstance(release, dict)
        ]

    def _fetch_json(
        self,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=UpdaterConfig.REQUEST_TIMEOUT,
            )
            response.raise_for_status()

        except requests.RequestException as error:
            raise UpdateCheckError(
                "Unable to contact the update server: "
                f"{error}"
            ) from error

        try:
            return response.json()

        except (
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise UpdateCheckError(
                "Update server returned invalid JSON."
            ) from error

    @staticmethod
    def _select_release(
        releases: list[dict[str, Any]],
        channel: str,
    ) -> dict[str, Any]:
        candidates: list[
            tuple[AppVersion, dict[str, Any]]
        ] = []

        for release in releases:
            if release.get("draft", False):
                continue

            prerelease = bool(
                release.get("prerelease", False)
            )

            tag = str(
                release.get("tag_name", "")
            ).strip()

            try:
                version = AppVersion.parse(tag)
            except ValueError:
                continue

            if channel == "stable" and prerelease:
                continue

            if (
                channel == "beta"
                and version.label == "nightly"
            ):
                continue

            candidates.append(
                (version, release)
            )

        if not candidates:
            raise UpdateCheckError(
                f"No usable {channel} release found."
            )

        candidates.sort(
            key=lambda item:
                item[0].comparison_key(),
            reverse=True,
        )

        return candidates[0][1]

    @staticmethod
    def _parse_assets(
        release: dict[str, Any],
    ) -> list[ReleaseAsset]:
        raw_assets = release.get("assets", [])

        if not isinstance(raw_assets, list):
            raise UpdateCheckError(
                "GitHub release assets are invalid."
            )

        assets: list[ReleaseAsset] = []

        for raw_asset in raw_assets:
            if not isinstance(raw_asset, dict):
                continue

            try:
                assets.append(
                    ReleaseAsset.from_github(
                        raw_asset
                    )
                )
            except ValueError:
                continue

        return assets

    @staticmethod
    def _find_asset(
        assets: list[ReleaseAsset],
        asset_name: str,
    ) -> ReleaseAsset:
        for asset in assets:
            if asset.name == asset_name:
                return asset

        raise UpdateCheckError(
            "Required release asset not found: "
            f"{asset_name}"
        )

    @staticmethod
    def _validate_channel(
        manifest: UpdateManifest,
        selected_channel: str,
    ) -> None:
        allowed = {
            "stable": {"stable"},
            "beta": {"stable", "beta"},
            "nightly": {
                "stable",
                "beta",
                "nightly",
            },
        }

        if (
            manifest.channel
            not in allowed[selected_channel]
        ):
            raise UpdateCheckError(
                "Release manifest channel does not "
                "match the selected update channel."
            )


update_manager = UpdateManager()