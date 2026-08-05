import logging
import os
import sys
import threading
from collections import deque
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Optional

from config import Config
from app.event_bus import event_bus


LogCallback = Callable[[dict[str, Any]], None]


class LogManager:
    """
    Central logging backend Spotify+.

    Fitur:
    - log ke terminal;
    - log harian ke file;
    - retensi log otomatis;
    - buffer log terbaru untuk GUI;
    - callback realtime untuk Log Viewer;
    - thread-safe;
    - tidak mengubah print() lama secara paksa.

    Lokasi log:
    %LOCALAPPDATA%/BetterSpotifyPresence/logs/
    """

    LEVEL_MAP = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    VALID_CATEGORIES = {
        "APP",
        "ENGINE",
        "SPOTIFY",
        "LYRICS",
        "RPC",
        "CACHE",
        "PROFILE",
        "SETTINGS",
        "UPDATER",
        "GUI",
        "SYSTEM",
    }

    def __init__(
        self,
        *,
        max_buffer_entries: int = 2000,
        retention_days: int = 14,
    ) -> None:
        self._lock = threading.RLock()

        self._callbacks: list[
            LogCallback
        ] = []

        self._buffer: deque[
            dict[str, Any]
        ] = deque(
            maxlen=max_buffer_entries
        )

        self.retention_days = max(
            1,
            int(retention_days),
        )

        self.log_dir = (
            Path(Config.APP_DATA_DIR)
            / "logs"
        )

        self.log_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.log_file = (
            self.log_dir
            / "spotify_plus.log"
        )

        self._logger = logging.getLogger(
            "spotify_plus"
        )

        self._logger.setLevel(
            logging.DEBUG
        )

        self._logger.propagate = False

        self._configure_handlers()

    # ==========================================================
    # Setup
    # ==========================================================

    def _configure_handlers(self) -> None:
        """
        Hindari duplicate handler saat module ter-import ulang.
        """

        if self._logger.handlers:
            return

        # Dalam pythonw/PyInstaller --windowed, sys.stderr dapat None.
        # Console handler hanya dibuat saat debug dan stream tersedia.
        console_handler = None

        console_stream = (
            sys.stderr
            or sys.stdout
            or getattr(
                sys,
                "__stderr__",
                None,
            )
        )

        if (
            Config.DEBUG
            and console_stream is not None
        ):
            console_handler = (
                logging.StreamHandler(
                    console_stream
                )
            )

            console_handler.setLevel(
                logging.DEBUG
            )

            console_handler.setFormatter(
                logging.Formatter(
                    "[%(asctime)s] "
                    "%(levelname)-8s "
                    "%(message)s",
                    datefmt="%H:%M:%S",
                )
            )

        file_handler = (
            TimedRotatingFileHandler(
                filename=str(
                    self.log_file
                ),
                when="midnight",
                interval=1,
                backupCount=self.retention_days,
                encoding="utf-8",
                delay=True,
            )
        )

        file_handler.setLevel(
            logging.DEBUG
        )

        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | "
                "%(levelname)s | "
                "%(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

        if console_handler is not None:
            self._logger.addHandler(
                console_handler
            )

        self._logger.addHandler(
            file_handler
        )

    # ==========================================================
    # Public Logging API
    # ==========================================================

    def debug(
        self,
        message: str,
        *,
        category: str = "APP",
        context: Optional[
            dict[str, Any]
        ] = None,
    ) -> None:
        self.log(
            "DEBUG",
            message,
            category=category,
            context=context,
        )

    def info(
        self,
        message: str,
        *,
        category: str = "APP",
        context: Optional[
            dict[str, Any]
        ] = None,
    ) -> None:
        self.log(
            "INFO",
            message,
            category=category,
            context=context,
        )

    def warning(
        self,
        message: str,
        *,
        category: str = "APP",
        context: Optional[
            dict[str, Any]
        ] = None,
    ) -> None:
        self.log(
            "WARNING",
            message,
            category=category,
            context=context,
        )

    def error(
        self,
        message: str,
        *,
        category: str = "APP",
        context: Optional[
            dict[str, Any]
        ] = None,
    ) -> None:
        self.log(
            "ERROR",
            message,
            category=category,
            context=context,
        )

    def critical(
        self,
        message: str,
        *,
        category: str = "APP",
        context: Optional[
            dict[str, Any]
        ] = None,
    ) -> None:
        self.log(
            "CRITICAL",
            message,
            category=category,
            context=context,
        )

    def exception(
        self,
        message: str,
        *,
        category: str = "APP",
        context: Optional[
            dict[str, Any]
        ] = None,
    ) -> None:
        """
        Dipanggil dari dalam except block.
        Menyimpan traceback ke file/terminal.
        """

        entry = self._build_entry(
            level="ERROR",
            category=category,
            message=message,
            context=context,
        )

        with self._lock:
            self._buffer.append(
                entry
            )

        self._logger.exception(
            self._format_message(
                entry
            )
        )

        self._emit(
            entry
        )

        event_bus.publish(
            "log.created",
            source="logger",
            entry=entry.copy(),
        )

    def log(
        self,
        level: str,
        message: str,
        *,
        category: str = "APP",
        context: Optional[
            dict[str, Any]
        ] = None,
    ) -> None:
        normalized_level = (
            str(level)
            .strip()
            .upper()
        )

        normalized_category = (
            str(category)
            .strip()
            .upper()
        )

        if (
            normalized_level
            not in self.LEVEL_MAP
        ):
            raise ValueError(
                f"Unknown log level: "
                f"{normalized_level}"
            )

        if (
            normalized_category
            not in self.VALID_CATEGORIES
        ):
            normalized_category = (
                "APP"
            )

        entry = self._build_entry(
            level=normalized_level,
            category=normalized_category,
            message=message,
            context=context,
        )

        with self._lock:
            self._buffer.append(
                entry
            )

        self._logger.log(
            self.LEVEL_MAP[
                normalized_level
            ],
            self._format_message(
                entry
            ),
        )

        self._emit(
            entry
        )

        event_bus.publish(
            "log.created",
            source="logger",
            entry=entry.copy(),
        )

    # ==========================================================
    # Entry Creation
    # ==========================================================

    @staticmethod
    def _build_entry(
        *,
        level: str,
        category: str,
        message: str,
        context: Optional[
            dict[str, Any]
        ],
    ) -> dict[str, Any]:
        now = datetime.now()

        return {
            "timestamp":
                now.timestamp(),

            "datetime":
                now.isoformat(
                    timespec="seconds"
                ),

            "time":
                now.strftime(
                    "%H:%M:%S"
                ),

            "level":
                level,

            "category":
                category,

            "message":
                str(message),

            "context":
                dict(
                    context
                    or {}
                ),

            "thread":
                threading.current_thread()
                .name,
        }

    @staticmethod
    def _format_message(
        entry: dict[str, Any],
    ) -> str:
        base = (
            f"[{entry['category']}] "
            f"{entry['message']}"
        )

        context = entry.get(
            "context"
        )

        if context:
            context_text = ", ".join(
                f"{key}={value}"
                for key, value
                in context.items()
            )

            base += (
                f" | {context_text}"
            )

        return base

    # ==========================================================
    # GUI Listener API
    # ==========================================================

    def subscribe(
        self,
        callback: LogCallback,
    ) -> None:
        if not callable(
            callback
        ):
            raise TypeError(
                "Log callback must be callable."
            )

        with self._lock:
            if (
                callback
                not in self._callbacks
            ):
                self._callbacks.append(
                    callback
                )

    def unsubscribe(
        self,
        callback: LogCallback,
    ) -> None:
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(
                    callback
                )

    def _emit(
        self,
        entry: dict[str, Any],
    ) -> None:
        with self._lock:
            callbacks = list(
                self._callbacks
            )

        for callback in callbacks:
            try:
                callback(
                    entry.copy()
                )

            except Exception as error:
                self._logger.error(
                    "[LOGGER] Callback error: "
                    f"{error}"
                )

    # ==========================================================
    # Buffer / Query API
    # ==========================================================

    def get_entries(
        self,
        *,
        level: Optional[str] = None,
        category: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        normalized_level = (
            level.strip().upper()
            if level
            else None
        )

        normalized_category = (
            category.strip().upper()
            if category
            else None
        )

        with self._lock:
            entries = list(
                self._buffer
            )

        if normalized_level:
            entries = [
                entry
                for entry in entries
                if entry[
                    "level"
                ] == normalized_level
            ]

        if normalized_category:
            entries = [
                entry
                for entry in entries
                if entry[
                    "category"
                ] == normalized_category
            ]

        if limit is not None:
            safe_limit = max(
                0,
                int(limit),
            )

            entries = entries[
                -safe_limit:
            ]

        return [
            entry.copy()
            for entry in entries
        ]

    def clear_buffer(self) -> None:
        """
        Hanya menghapus tampilan/buffer GUI.
        File log tidak dihapus.
        """

        with self._lock:
            self._buffer.clear()

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            entries = list(
                self._buffer
            )

            callback_count = len(
                self._callbacks
            )

        by_level: dict[str, int] = {}

        by_category: dict[
            str,
            int,
        ] = {}

        for entry in entries:
            level = entry[
                "level"
            ]

            category = entry[
                "category"
            ]

            by_level[level] = (
                by_level.get(
                    level,
                    0,
                )
                + 1
            )

            by_category[
                category
            ] = (
                by_category.get(
                    category,
                    0,
                )
                + 1
            )

        return {
            "buffer_entries":
                len(entries),

            "callbacks":
                callback_count,

            "log_directory":
                str(
                    self.log_dir
                ),

            "log_file":
                str(
                    self.log_file
                ),

            "retention_days":
                self.retention_days,

            "by_level":
                by_level,

            "by_category":
                by_category,
        }

    # ==========================================================
    # Lifecycle
    # ==========================================================

    def flush(self) -> None:
        with self._lock:
            handlers = list(
                self._logger.handlers
            )

        for handler in handlers:
            try:
                handler.flush()
            except Exception:
                pass

    def shutdown(self) -> None:
        self.flush()

        with self._lock:
            handlers = list(
                self._logger.handlers
            )

        for handler in handlers:
            try:
                handler.close()
            except Exception:
                pass

            try:
                self._logger.removeHandler(
                    handler
                )
            except Exception:
                pass

    # ==========================================================
    # File / Folder Helpers
    # ==========================================================

    def open_log_folder(self) -> bool:
        """
        Membuka folder log memakai file explorer OS.
        """

        try:
            if os.name == "nt":
                os.startfile(
                    str(
                        self.log_dir
                    )
                )

            elif sys.platform == "darwin":
                import subprocess

                subprocess.Popen(
                    [
                        "open",
                        str(
                            self.log_dir
                        ),
                    ]
                )

            else:
                import subprocess

                subprocess.Popen(
                    [
                        "xdg-open",
                        str(
                            self.log_dir
                        ),
                    ]
                )

            return True

        except Exception as error:
            self.error(
                f"Could not open log folder: "
                f"{error}",
                category="SYSTEM",
            )

            return False


logger = LogManager()