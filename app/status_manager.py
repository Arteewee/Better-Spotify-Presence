import threading
import time
from copy import deepcopy
from typing import Any, Optional

from app.event_bus import event_bus


class StatusManager:
    """
    Central runtime status store.

    Menyimpan status yang dibutuhkan oleh:
    - Main Window status bar
    - Tray tooltip
    - Dashboard
    - Notification Center
    - Fatal error flow
    """

    DEFAULT_STATE: dict[str, Any] = {
        "engine": {
            "state": "stopped",
            "message": "Engine stopped",
            "updated_at": 0.0,
        },
        "spotify": {
            "state": "unknown",
            "message": "Spotify status unknown",
            "profile": "",
            "retry_after": 0,
            "updated_at": 0.0,
        },
        "lyrics": {
            "state": "idle",
            "message": "Lyrics idle",
            "provider": "",
            "updated_at": 0.0,
        },
        "rpc": {
            "state": "disconnected",
            "message": "Discord disconnected",
            "updated_at": 0.0,
        },
        "application": {
            "state": "starting",
            "message": "Spotify+ starting",
            "updated_at": 0.0,
        },
        "error": {
            "active": False,
            "message": "",
            "details": "",
            "updated_at": 0.0,
        },
    }

    def __init__(self) -> None:
        self._lock = threading.RLock()

        self._state = deepcopy(
            self.DEFAULT_STATE
        )

        event_bus.subscribe(
            "*",
            self._handle_event,
        )

    # ==========================================================
    # Public State API
    # ==========================================================

    def get(
        self,
        section: Optional[str] = None,
    ) -> dict[str, Any]:
        with self._lock:
            if section is None:
                return deepcopy(
                    self._state
                )

            normalized = (
                str(section)
                .strip()
                .lower()
            )

            return deepcopy(
                self._state.get(
                    normalized,
                    {},
                )
            )

    def update(
        self,
        section: str,
        *,
        publish: bool = True,
        **values: Any,
    ) -> dict[str, Any]:
        normalized = (
            str(section)
            .strip()
            .lower()
        )

        if not normalized:
            raise ValueError(
                "Status section cannot be empty."
            )

        with self._lock:
            current = self._state.setdefault(
                normalized,
                {},
            )

            current.update(
                values
            )

            current[
                "updated_at"
            ] = time.time()

            snapshot = deepcopy(
                current
            )

        if publish:
            event_bus.publish(
                "status.changed",
                source="status_manager",
                section=normalized,
                status=snapshot,
            )

        return snapshot

    def reset(
        self,
        section: Optional[str] = None,
    ) -> None:
        with self._lock:
            if section is None:
                self._state = deepcopy(
                    self.DEFAULT_STATE
                )

                return

            normalized = (
                str(section)
                .strip()
                .lower()
            )

            default = (
                self.DEFAULT_STATE.get(
                    normalized,
                    {},
                )
            )

            self._state[
                normalized
            ] = deepcopy(
                default
            )

    # ==========================================================
    # Derived Overall Status
    # ==========================================================

    def get_overall_status(
        self,
    ) -> dict[str, Any]:
        state = self.get()

        error_state = state.get(
            "error",
            {},
        )

        if error_state.get(
            "active",
            False,
        ):
            return {
                "level": "error",
                "title": "Application Error",
                "message": (
                    error_state.get(
                        "message"
                    )
                    or "Unexpected application error"
                ),
            }

        spotify = state.get(
            "spotify",
            {},
        )

        rpc = state.get(
            "rpc",
            {},
        )

        engine = state.get(
            "engine",
            {},
        )

        lyrics = state.get(
            "lyrics",
            {},
        )

        if spotify.get(
            "state"
        ) == "rate_limited":
            retry_after = int(
                spotify.get(
                    "retry_after",
                    0,
                )
                or 0
            )

            return {
                "level": "warning",
                "title": "Spotify Cooldown",
                "message": (
                    f"Retry in {retry_after} seconds"
                ),
            }

        if rpc.get(
            "state"
        ) == "disconnected":
            return {
                "level": "error",
                "title": "Discord Disconnected",
                "message": (
                    rpc.get(
                        "message"
                    )
                    or "Discord RPC disconnected"
                ),
            }

        if engine.get(
            "state"
        ) == "paused":
            return {
                "level": "warning",
                "title": "Engine Paused",
                "message": (
                    engine.get(
                        "message"
                    )
                    or "Playback engine paused"
                ),
            }

        if engine.get(
            "state"
        ) == "running":
            lyric_message = (
                lyrics.get(
                    "message"
                )
                or "Lyrics ready"
            )

            return {
                "level": "success",
                "title": "Running",
                "message": lyric_message,
            }

        return {
            "level": "neutral",
            "title": "Stopped",
            "message": (
                engine.get(
                    "message"
                )
                or "Engine stopped"
            ),
        }

    # ==========================================================
    # Event Mapping
    # ==========================================================

    def _handle_event(
        self,
        event: dict[str, Any],
    ) -> None:
        name = str(
            event.get(
                "name",
                "",
            )
        )

        payload = event.get(
            "payload",
            {},
        )

        if name == "app.started":
            self.update(
                "application",
                state="running",
                message="Spotify+ running",
            )

        elif name == "app.stopping":
            self.update(
                "application",
                state="stopping",
                message="Spotify+ stopping",
            )

        elif name == "engine.started":
            self.update(
                "engine",
                state="running",
                message="Engine running",
            )

        elif name == "engine.stopped":
            self.update(
                "engine",
                state="stopped",
                message="Engine stopped",
            )

        elif name == "engine.paused":
            self.update(
                "engine",
                state="paused",
                message="Engine paused",
            )

        elif name == "engine.resumed":
            self.update(
                "engine",
                state="running",
                message="Engine resumed",
            )

        elif name == "spotify.connected":
            self.update(
                "spotify",
                state="connected",
                message="Spotify connected",
                profile=payload.get(
                    "profile",
                    "",
                ),
                retry_after=0,
            )

        elif name == "spotify.rate_limit":
            self.update(
                "spotify",
                state="rate_limited",
                message="Spotify cooldown active",
                retry_after=payload.get(
                    "retry_after",
                    0,
                ),
                profile=payload.get(
                    "profile",
                    "",
                ),
            )

        elif name == "spotify.error":
            self.update(
                "spotify",
                state="error",
                message=payload.get(
                    "message",
                    "Spotify error",
                ),
            )

        elif name == "lyrics.loaded":
            self.update(
                "lyrics",
                state="ready",
                message="Lyrics ready",
                provider=payload.get(
                    "provider",
                    "",
                ),
            )

        elif name == "lyrics.cache_hit":
            self.update(
                "lyrics",
                state="ready",
                message="Lyrics loaded from cache",
                provider=payload.get(
                    "provider",
                    "cache",
                ),
            )

        elif name == "lyrics.failed":
            self.update(
                "lyrics",
                state="missing",
                message="Lyrics unavailable",
                provider="",
            )

        elif name == "rpc.connected":
            self.update(
                "rpc",
                state="connected",
                message="Discord connected",
            )

        elif name == "rpc.disconnected":
            self.update(
                "rpc",
                state="disconnected",
                message="Discord disconnected",
            )

        elif name == "rpc.error":
            self.update(
                "rpc",
                state="error",
                message=payload.get(
                    "message",
                    "Discord RPC error",
                ),
            )

        elif name == "app.fatal_error":
            self.update(
                "error",
                active=True,
                message=payload.get(
                    "message",
                    "Unexpected application error",
                ),
                details=payload.get(
                    "details",
                    "",
                ),
            )

        elif name == "app.error_cleared":
            self.update(
                "error",
                active=False,
                message="",
                details="",
            )


status_manager = StatusManager()