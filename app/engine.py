import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Optional

from dotenv import set_key

from config import Config
from app.settings_manager import settings
from app.logger import logger
from app.event_bus import event_bus
from core.lyrics import get_lyrics_status
from core.rpc import get_rpc_status
from core.spotify import get_spotify_status

# main.py sekarang masih menyimpan playback loop dan state runtime.
# Engine memakai fungsi-fungsi stabil tersebut tanpa mengubah core.
import main as runtime


EventCallback = Callable[[dict[str, Any]], None]


class SpotifyEngine:
    """
    Facade utama Better Spotify Presence.

    UI, system tray, dan updater hanya berkomunikasi dengan class ini.
    Mereka tidak perlu mengakses spotify.py, lyrics.py, atau rpc.py
    secara langsung.
    """

    VALID_EVENTS = {
        "running_changed",
        "paused_changed",
        "status_changed",
        "song_changed",
        "lyrics_changed",
        "rate_limit_changed",
        "profile_changed",
        "runtime_settings_changed",
        "restart_required",
        "error",
    }

    def __init__(self) -> None:
        self._thread: Optional[
            threading.Thread
        ] = None

        self._stop_event = (
            threading.Event()
        )

        self._pause_event = (
            threading.Event()
        )

        self._state_lock = (
            threading.RLock()
        )

        self._callbacks: dict[
            str,
            list[EventCallback],
        ] = defaultdict(list)

        self._running = False
        self._last_error: Optional[str] = None

        # Runtime performance metrics.
        self._started_at_monotonic = 0.0
        self._loop_count = 0
        self._loop_total_seconds = 0.0
        self._loop_last_seconds = 0.0
        self._loop_max_seconds = 0.0

        # Snapshot event agar event yang sama tidak dikirim berulang.
        self._last_song_id: Optional[str] = None
        self._last_lyric: Optional[str] = None
        self._last_rate_limit_state = False
        self._last_status_snapshot: Optional[
            dict[str, Any]
        ] = None

        self.reload_runtime_settings(
            emit_event=False
        )

    # ==========================================================
    # Event System
    # ==========================================================

    def on(
        self,
        event_name: str,
        callback: EventCallback,
    ) -> None:
        """
        Mendaftarkan callback.

        Contoh:
            engine.on(
                "song_changed",
                handle_song_changed,
            )
        """

        if event_name not in self.VALID_EVENTS:
            raise ValueError(
                f"Unknown engine event: "
                f"{event_name}"
            )

        if not callable(callback):
            raise TypeError(
                "Event callback must be callable."
            )

        with self._state_lock:
            if (
                callback
                not in self._callbacks[event_name]
            ):
                self._callbacks[
                    event_name
                ].append(callback)

    def off(
        self,
        event_name: str,
        callback: EventCallback,
    ) -> None:
        """
        Menghapus callback yang sebelumnya didaftarkan.
        """

        with self._state_lock:
            callbacks = self._callbacks.get(
                event_name,
                [],
            )

            if callback in callbacks:
                callbacks.remove(callback)

    def _emit(
        self,
        event_name: str,
        data: Optional[
            dict[str, Any]
        ] = None,
    ) -> None:
        """
        Menjalankan semua callback event.

        Catatan:
        callback berjalan dari engine thread. Saat masuk PySide6,
        callback akan diteruskan melalui Qt Signal agar aman untuk UI.
        """

        payload = data or {}

        with self._state_lock:
            callbacks = list(
                self._callbacks.get(
                    event_name,
                    [],
                )
            )

        for callback in callbacks:
            try:
                callback(payload)

            except Exception as error:
                logger.error(
                    "Engine event callback failed",
                    category="ENGINE",
                    context={
                        "event": event_name,
                        "error": str(error),
                    },
                )

    # ==========================================================
    # Engine Lifecycle
    # ==========================================================

    @property
    def is_running(self) -> bool:
        with self._state_lock:
            return self._running

    @property
    def is_paused(self) -> bool:
        return self._pause_event.is_set()

    def start(self) -> bool:
        """
        Menjalankan playback engine pada background thread.

        Return:
            True  -> engine berhasil dimulai
            False -> engine sudah berjalan
        """

        with self._state_lock:
            if (
                self._thread is not None
                and self._thread.is_alive()
            ):
                return False

            self._stop_event.clear()
            self._pause_event.clear()

            self._last_error = None
            self._last_status_snapshot = None
            self._last_song_id = None
            self._last_lyric = None

            self._started_at_monotonic = (
                time.monotonic()
            )

            self._loop_count = 0
            self._loop_total_seconds = 0.0
            self._loop_last_seconds = 0.0
            self._loop_max_seconds = 0.0

            # Paksa Spotify poll langsung saat startup.
            runtime.last_spotify_poll_time = 0.0

            self._thread = threading.Thread(
                target=self._run_loop,
                name="spotify-engine",
                daemon=True,
            )

            self._running = True
            self._thread.start()

        self._emit(
            "running_changed",
            {
                "running": True,
            },
        )

        logger.info(
            "Engine started",
            category="ENGINE",
        )

        event_bus.publish(
            "engine.started",
            source="engine",
        )

        return True

    def stop(
        self,
        timeout: float = 5.0,
    ) -> bool:
        """
        Menghentikan engine dan membersihkan Discord Presence.

        Engine masih dapat dijalankan lagi menggunakan start().
        """

        with self._state_lock:
            thread = self._thread

            if (
                thread is None
                or not thread.is_alive()
            ):
                self._running = False
                return False

            self._stop_event.set()
            self._pause_event.clear()

        if (
            thread is not threading.current_thread()
        ):
            thread.join(
                timeout=timeout
            )

        try:
            runtime.clear_current_activity()

        except Exception as error:
            logger.error(
                "Failed to clear Discord activity",
                category="ENGINE",
                context={
                    "error": str(error),
                },
            )

        with self._state_lock:
            self._running = False
            self._thread = None

        self._emit(
            "running_changed",
            {
                "running": False,
            },
        )

        logger.info(
            "Engine stopped",
            category="ENGINE",
        )

        event_bus.publish(
            "engine.stopped",
            source="engine",
        )

        return True

    def shutdown(self) -> None:
        """
        Final shutdown saat aplikasi benar-benar keluar.

        Berbeda dari stop(), method ini juga menutup thread pool
        background lyrics sehingga engine tidak boleh di-start lagi.
        """

        self.stop()

        try:
            runtime.invalidate_lyrics_loader()

            runtime.lyrics_executor.shutdown(
                wait=False,
                cancel_futures=True,
            )

        except Exception as error:
            logger.error(
                "Lyrics executor shutdown failed",
                category="ENGINE",
                context={
                    "error": str(error),
                },
            )

    def pause(self) -> bool:
        """
        Pause Discord Presence tanpa menghentikan aplikasi.
        """

        if not self.is_running:
            return False

        if self.is_paused:
            return False

        self._pause_event.set()

        try:
            runtime.clear()
        except Exception as error:
            logger.error(
                "Failed to clear presence while pausing",
                category="ENGINE",
                context={
                    "error": str(error),
                },
            )

        self._emit(
            "paused_changed",
            {
                "paused": True,
            },
        )

        logger.info(
            "Engine paused",
            category="ENGINE",
        )

        event_bus.publish(
            "engine.paused",
            source="engine",
        )

        return True

    def resume(self) -> bool:
        """
        Melanjutkan playback engine setelah pause.
        """

        if not self.is_running:
            return False

        if not self.is_paused:
            return False

        # Paksa polling dan RPC refresh.
        runtime.last_spotify_poll_time = 0.0
        runtime.last_line = None

        self._pause_event.clear()

        self._emit(
            "paused_changed",
            {
                "paused": False,
            },
        )

        logger.info(
            "Engine resumed",
            category="ENGINE",
        )

        event_bus.publish(
            "engine.resumed",
            source="engine",
        )

        return True

    # ==========================================================
    # Playback Loop
    # ==========================================================

    def _run_loop(self) -> None:
        """
        Non-blocking playback loop yang sebelumnya dijalankan
        langsung oleh main.py.
        """

        try:
            while not self._stop_event.is_set():

                loop_start = (
                    time.perf_counter()
                )

                if self._pause_event.is_set():
                    self._publish_events()

                    self._stop_event.wait(
                        0.10
                    )

                    continue

                current_clock = (
                    time.perf_counter()
                )

                spotify_poll_interval = (
                    runtime
                    .get_spotify_poll_interval()
                )

                if (
                    current_clock
                    - runtime.last_spotify_poll_time
                    >= spotify_poll_interval
                ):
                    spotify_song = (
                        runtime.get_current_song()
                    )

                    runtime.handle_spotify_result(
                        spotify_song
                    )

                    runtime.last_spotify_poll_time = (
                        current_clock
                    )

                # Ambil hasil background loader tanpa blocking.
                runtime.process_lyrics_result()

                runtime.update_discord_lyrics()

                runtime.handle_cached_song_end()

                runtime.print_rate_limit_status()

                self._publish_events()

                loop_duration = (
                    time.perf_counter()
                    - loop_start
                )

                self._loop_count += 1
                self._loop_last_seconds = (
                    loop_duration
                )

                self._loop_total_seconds += (
                    loop_duration
                )

                self._loop_max_seconds = max(
                    self._loop_max_seconds,
                    loop_duration,
                )

                remaining_sleep = max(
                    0.0,
                    Config.LYRIC_REFRESH_RATE
                    - loop_duration,
                )

                self._stop_event.wait(
                    remaining_sleep
                )

        except Exception as error:
            self._last_error = str(error)

            logger.error(
                "Fatal engine error",
                category="ENGINE",
                context={
                    "error": str(error),
                },
            )

            event_bus.publish(
                "app.fatal_error",
                source="engine",
                message="Fatal engine error",
                details=str(error),
            )

            self._emit(
                "error",
                {
                    "message": str(error),
                    "exception": error,
                },
            )

        finally:
            with self._state_lock:
                self._running = False

            self._emit(
                "running_changed",
                {
                    "running": False,
                },
            )

    # ==========================================================
    # Status and Events
    # ==========================================================

    def get_status(self) -> dict[str, Any]:
        """
        Menggabungkan status Spotify, lyrics, RPC, dan playback.
        """

        spotify_status = (
            get_spotify_status()
        )

        lyrics_status = (
            get_lyrics_status()
        )

        rpc_status = (
            get_rpc_status()
        )

        song = (
            runtime.current_song.copy()
            if runtime.current_song
            else {}
        )

        try:
            progress = (
                runtime.get_local_progress()
                if song
                else 0.0
            )

        except Exception:
            progress = 0.0

        duration = (
            float(
                song.get(
                    "duration",
                    0,
                )
            )
            / 1000.0
        )

        uptime = (
            time.monotonic()
            - self._started_at_monotonic
            if (
                self.is_running
                and self._started_at_monotonic
                > 0
            )
            else 0.0
        )

        average_loop = (
            self._loop_total_seconds
            / self._loop_count
            if self._loop_count
            else 0.0
        )

        rpc_sent = int(
            rpc_status.get(
                "updates_sent",
                0,
            )
        )

        rpc_skipped = int(
            rpc_status.get(
                "updates_skipped",
                0,
            )
        )

        rpc_total = (
            rpc_sent
            + rpc_skipped
        )

        rpc_optimization_rate = (
            rpc_skipped / rpc_total
            if rpc_total
            else 0.0
        )

        memory_cache_stats = (
            lyrics_status.get(
                "memory_cache_stats",
                {},
            )
        )

        persistent_cache_stats = (
            lyrics_status.get(
                "persistent_cache_stats",
                {},
            )
        )

        return {
            # Engine
            "running": self.is_running,
            "paused": self.is_paused,
            "error": self._last_error,
            "uptime": uptime,
            "loop_count": self._loop_count,
            "loop_last_ms":
                self._loop_last_seconds
                * 1000.0,
            "loop_average_ms":
                average_loop
                * 1000.0,
            "loop_max_ms":
                self._loop_max_seconds
                * 1000.0,
            "target_loop_hz": (
                1.0
                / Config.LYRIC_REFRESH_RATE
                if Config.LYRIC_REFRESH_RATE
                else 0.0
            ),
            "spotify_polling":
                Config.SPOTIFY_REFRESH_RATE,
            "spotify_fast_polling":
                Config.SPOTIFY_FAST_REFRESH_RATE,

            # Spotify
            "profile": spotify_status.get(
                "active_profile",
                Config.ACTIVE_SPOTIFY_PROFILE,
            ),
            "rate_limited": (
                spotify_status.get(
                    "rate_limited",
                    False,
                )
            ),
            "retry_after": (
                spotify_status.get(
                    "retry_after",
                    0,
                )
            ),
            "spotify_error": (
                spotify_status.get(
                    "last_error"
                )
            ),
            "spotify_request_attempts":
                spotify_status.get(
                    "request_attempts",
                    0,
                ),
            "spotify_successful_requests":
                spotify_status.get(
                    "successful_requests",
                    0,
                ),
            "spotify_failed_requests":
                spotify_status.get(
                    "failed_requests",
                    0,
                ),
            "spotify_rate_limit_count":
                spotify_status.get(
                    "rate_limit_count",
                    0,
                ),
            "spotify_cached_returns":
                spotify_status.get(
                    "cached_returns",
                    0,
                ),
            "spotify_last_successful_request":
                spotify_status.get(
                    "last_successful_request",
                    0.0,
                ),

            # Playback
            "song_id": song.get("id"),
            "song": song.get("name"),
            "artist": song.get("artist"),
            "album": song.get("album"),
            "album_cover": song.get(
                "album_cover"
            ),
            "spotify_url": song.get(
                "spotify_url"
            ),
            "progress": progress,
            "duration": duration,
            "lyric": runtime.last_line,

            # Lyrics
            "lyrics_provider": (
                lyrics_status.get(
                    "last_provider"
                )
            ),
            "lyrics_latency": (
                lyrics_status.get(
                    "last_latency",
                    0.0,
                )
            ),
            "lyrics_confidence": (
                lyrics_status.get(
                    "last_confidence",
                    0.0,
                )
            ),
            "cache_source": (
                lyrics_status.get(
                    "last_cache_source"
                )
            ),
            "offline_cache_entries": (
                lyrics_status.get(
                    "persistent_cache_entries",
                    0,
                )
            ),
            "memory_cache_entries":
                memory_cache_stats.get(
                    "entries",
                    0,
                ),
            "memory_cache_hits":
                memory_cache_stats.get(
                    "hits",
                    0,
                ),
            "memory_cache_misses":
                memory_cache_stats.get(
                    "misses",
                    0,
                ),
            "memory_cache_hit_rate":
                memory_cache_stats.get(
                    "hit_rate",
                    0.0,
                ),
            "persistent_cache_hits":
                persistent_cache_stats.get(
                    "hits",
                    0,
                ),
            "persistent_cache_misses":
                persistent_cache_stats.get(
                    "misses",
                    0,
                ),
            "persistent_cache_hit_rate":
                persistent_cache_stats.get(
                    "hit_rate",
                    0.0,
                ),
            "provider_successes":
                lyrics_status.get(
                    "provider_successes",
                    0,
                ),
            "provider_failures":
                lyrics_status.get(
                    "provider_failures",
                    0,
                ),
            "provider_timeouts":
                lyrics_status.get(
                    "provider_timeouts",
                    0,
                ),

            # Discord RPC
            "rpc_connected": (
                rpc_status.get(
                    "connected",
                    False,
                )
            ),
            "rpc_updates_sent": (
                rpc_status.get(
                    "updates_sent",
                    0,
                )
            ),
            "rpc_updates_skipped": (
                rpc_status.get(
                    "updates_skipped",
                    0,
                )
            ),
            "rpc_optimization_rate":
                rpc_optimization_rate,

            "start_engine_on_launch":
                settings.get(
                    "start_engine_on_launch"
                ),

            "minimize_to_tray":
                settings.get(
                    "minimize_to_tray"
                ),

            "show_now_playing_notification":
                settings.get(
                    "show_now_playing_notification"
                ),

            "diagnostics_enabled":
                Config.DIAGNOSTICS_ENABLED,
        }

    def _publish_events(self) -> None:
        """
        Mengirim event hanya ketika state penting berubah.
        """

        status = self.get_status()

        song_id = status.get(
            "song_id"
        )

        lyric = status.get(
            "lyric"
        )

        rate_limited = bool(
            status.get(
                "rate_limited",
                False,
            )
        )

        if song_id != self._last_song_id:
            self._last_song_id = song_id

            self._emit(
                "song_changed",
                {
                    "song_id": song_id,
                    "song": status.get(
                        "song"
                    ),
                    "artist": status.get(
                        "artist"
                    ),
                    "album": status.get(
                        "album"
                    ),
                    "album_cover": status.get(
                        "album_cover"
                    ),
                    "spotify_url": status.get(
                        "spotify_url"
                    ),
                    "duration": status.get(
                        "duration",
                        0.0,
                    ),
                },
            )

        if lyric != self._last_lyric:
            self._last_lyric = lyric

            self._emit(
                "lyrics_changed",
                {
                    "lyric": lyric,
                    "progress": status.get(
                        "progress",
                        0.0,
                    ),
                    "provider": status.get(
                        "lyrics_provider"
                    ),
                    "confidence": status.get(
                        "lyrics_confidence",
                        0.0,
                    ),
                },
            )

        if (
            rate_limited
            != self._last_rate_limit_state
        ):
            self._last_rate_limit_state = (
                rate_limited
            )

            self._emit(
                "rate_limit_changed",
                {
                    "rate_limited":
                        rate_limited,

                    "retry_after":
                        status.get(
                            "retry_after",
                            0,
                        ),
                },
            )

        # Status event tidak membawa progress agar tidak dikirim
        # setiap 50 ms hanya karena timer berubah.
        comparable_status = {
            key: value
            for key, value in status.items()
            if key not in {
                "progress",
            }
        }

        if (
            comparable_status
            != self._last_status_snapshot
        ):
            self._last_status_snapshot = (
                comparable_status.copy()
            )

            self._emit(
                "status_changed",
                status,
            )

    # ==========================================================
    # Runtime Settings
    # ==========================================================

    def reload_runtime_settings(
        self,
        *,
        emit_event: bool = True,
    ) -> dict[str, Any]:
        """
        Reload settings.json dan terapkan setting live.
        """

        settings.reload()

        preferences = (
            settings.get_runtime_preferences()
        )

        changed = (
            Config.apply_runtime_settings(
                preferences
            )
        )

        if any(
            key in changed
            for key in {
                "spotify_refresh_rate",
                "spotify_fast_refresh_rate",
                "spotify_ending_window",
            }
        ):
            runtime.last_spotify_poll_time = 0.0

        if changed:
            logger.info(
                "Runtime settings applied",
                category="SETTINGS",
                context={
                    "changed": ", ".join(
                        changed.keys()
                    ),
                },
            )

            for key, values in changed.items():
                logger.debug(
                    "Runtime setting changed",
                    category="SETTINGS",
                    context={
                        "setting": key,
                        "old": values["old"],
                        "new": values["new"],
                    },
                )

        result = {
            "changed": changed,
            "preferences": preferences,
        }

        if emit_event:
            self._emit(
                "runtime_settings_changed",
                result,
            )

            self._last_status_snapshot = None

        return result

    # ==========================================================
    # Spotify Profile
    # ==========================================================

    def switch_profile(
        self,
        profile_name: str,
    ) -> bool:
        """
        Mengubah profile aktif di .env.

        Karena Config dan OAuth client dibuat saat aplikasi startup,
        perubahan profile baru berlaku setelah process restart.
        GUI nanti akan menampilkan dialog restart.
        """

        profile = (
            profile_name
            .strip()
            .lower()
        )

        if (
            profile
            not in Config.SPOTIFY_PROFILES
        ):
            raise ValueError(
                f"Spotify profile tidak dikenal: "
                f"{profile}"
            )

        if (
            profile
            == Config.ACTIVE_SPOTIFY_PROFILE
        ):
            return False

        project_root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        env_file = (
            project_root
            / ".env"
        )

        set_key(
            str(env_file),
            "ACTIVE_SPOTIFY_PROFILE",
            profile,
        )

        self._emit(
            "profile_changed",
            {
                "profile": profile,
                "requires_restart": True,
            },
        )

        self._emit(
            "restart_required",
            {
                "reason": (
                    "spotify_profile_changed"
                ),
                "profile": profile,
            },
        )

        logger.info(
            "Spotify profile changed; restart required",
            category="PROFILE",
            context={
                "profile": profile,
            },
        )

        event_bus.publish(
            "notification.show",
            source="engine",
            level="warning",
            title="Restart Required",
            message=(
                f"Profile '{profile}' will be used "
                "after restarting Spotify+."
            ),
            duration=5000,
        )

        return True


# Singleton.
# GUI, tray, dan updater harus memakai object yang sama.
engine = SpotifyEngine()