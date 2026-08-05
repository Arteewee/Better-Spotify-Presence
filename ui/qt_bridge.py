from typing import Any

from PySide6.QtCore import QObject, Signal

from app.engine import engine


class EngineBridge(QObject):
    """
    Jembatan antara SpotifyEngine dan Qt UI.

    Event SpotifyEngine berasal dari background thread.
    Bridge meneruskannya menjadi Qt Signal agar UI dapat
    diperbarui dengan aman dari main GUI thread.
    """

    running_changed = Signal(object)
    paused_changed = Signal(object)
    status_changed = Signal(object)
    song_changed = Signal(object)
    lyrics_changed = Signal(object)
    rate_limit_changed = Signal(object)
    profile_changed = Signal(object)
    restart_required = Signal(object)
    engine_error = Signal(object)

    def __init__(self) -> None:
        super().__init__()

        self._registered_callbacks: list[
            tuple[str, Any]
        ] = []

        self._register(
            "running_changed",
            self._on_running_changed,
        )

        self._register(
            "paused_changed",
            self._on_paused_changed,
        )

        self._register(
            "status_changed",
            self._on_status_changed,
        )

        self._register(
            "song_changed",
            self._on_song_changed,
        )

        self._register(
            "lyrics_changed",
            self._on_lyrics_changed,
        )

        self._register(
            "rate_limit_changed",
            self._on_rate_limit_changed,
        )

        self._register(
            "profile_changed",
            self._on_profile_changed,
        )

        self._register(
            "restart_required",
            self._on_restart_required,
        )

        self._register(
            "error",
            self._on_engine_error,
        )

    def _register(
        self,
        event_name: str,
        callback: Any,
    ) -> None:
        engine.on(
            event_name,
            callback,
        )

        self._registered_callbacks.append(
            (
                event_name,
                callback,
            )
        )

    def close(self) -> None:
        """
        Melepas seluruh callback saat window ditutup.
        """

        for (
            event_name,
            callback,
        ) in self._registered_callbacks:

            engine.off(
                event_name,
                callback,
            )

        self._registered_callbacks.clear()

    def request_status(self) -> dict[str, Any]:
        """
        Mengambil snapshot status terbaru.
        """

        return engine.get_status()

    def _on_running_changed(
        self,
        data: dict[str, Any],
    ) -> None:
        self.running_changed.emit(
            data
        )

    def _on_paused_changed(
        self,
        data: dict[str, Any],
    ) -> None:
        self.paused_changed.emit(
            data
        )

    def _on_status_changed(
        self,
        data: dict[str, Any],
    ) -> None:
        self.status_changed.emit(
            data
        )

    def _on_song_changed(
        self,
        data: dict[str, Any],
    ) -> None:
        self.song_changed.emit(
            data
        )

    def _on_lyrics_changed(
        self,
        data: dict[str, Any],
    ) -> None:
        self.lyrics_changed.emit(
            data
        )

    def _on_rate_limit_changed(
        self,
        data: dict[str, Any],
    ) -> None:
        self.rate_limit_changed.emit(
            data
        )

    def _on_profile_changed(
        self,
        data: dict[str, Any],
    ) -> None:
        self.profile_changed.emit(
            data
        )

    def _on_restart_required(
        self,
        data: dict[str, Any],
    ) -> None:
        self.restart_required.emit(
            data
        )

    def _on_engine_error(
        self,
        data: dict[str, Any],
    ) -> None:
        self.engine_error.emit(
            data
        )