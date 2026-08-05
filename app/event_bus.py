import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


EventCallback = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class Event:
    """
    Immutable application event.
    """

    name: str
    payload: dict[str, Any] = field(
        default_factory=dict
    )
    timestamp: float = field(
        default_factory=time.time
    )
    source: str = "app"

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "payload": dict(
                self.payload
            ),
            "timestamp": self.timestamp,
            "source": self.source,
        }


class EventBus:
    """
    Thread-safe publish/subscribe event bus.

    Event name mendukung:
    - exact event: spotify.connected
    - wildcard global: *
    - namespace wildcard: spotify.*

    Callback menerima satu dictionary:
    {
        "name": "...",
        "payload": {...},
        "timestamp": ...,
        "source": "..."
    }
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

        self._subscribers: dict[
            str,
            list[EventCallback],
        ] = defaultdict(list)

        self._history: list[
            dict[str, Any]
        ] = []

        self._history_limit = 500

    # ==========================================================
    # Subscription
    # ==========================================================

    def subscribe(
        self,
        event_name: str,
        callback: EventCallback,
    ) -> None:
        event_name = self._normalize_name(
            event_name
        )

        if not callable(callback):
            raise TypeError(
                "Event callback must be callable."
            )

        with self._lock:
            callbacks = self._subscribers[
                event_name
            ]

            if callback not in callbacks:
                callbacks.append(
                    callback
                )

    def unsubscribe(
        self,
        event_name: str,
        callback: EventCallback,
    ) -> None:
        event_name = self._normalize_name(
            event_name
        )

        with self._lock:
            callbacks = self._subscribers.get(
                event_name,
                [],
            )

            if callback in callbacks:
                callbacks.remove(
                    callback
                )

            if not callbacks:
                self._subscribers.pop(
                    event_name,
                    None,
                )

    def clear_subscribers(
        self,
        event_name: Optional[str] = None,
    ) -> None:
        with self._lock:
            if event_name is None:
                self._subscribers.clear()
                return

            self._subscribers.pop(
                self._normalize_name(
                    event_name
                ),
                None,
            )

    # ==========================================================
    # Publishing
    # ==========================================================

    def publish(
        self,
        event_name: str,
        *,
        source: str = "app",
        **payload: Any,
    ) -> dict[str, Any]:
        event = Event(
            name=self._normalize_name(
                event_name
            ),
            payload=dict(
                payload
            ),
            source=(
                str(source).strip()
                or "app"
            ),
        )

        event_data = event.as_dict()

        with self._lock:
            self._history.append(
                event_data
            )

            if (
                len(self._history)
                > self._history_limit
            ):
                self._history = (
                    self._history[
                        -self._history_limit:
                    ]
                )

            callbacks = self._collect_callbacks(
                event.name
            )

        for callback in callbacks:
            try:
                callback(
                    event_data
                )

            except Exception:
                # Event bus tidak boleh bergantung pada terminal dan
                # tidak boleh menggagalkan callback lainnya.
                continue

        return event_data

    def _collect_callbacks(
        self,
        event_name: str,
    ) -> list[EventCallback]:
        callbacks: list[
            EventCallback
        ] = []

        exact = self._subscribers.get(
            event_name,
            [],
        )

        callbacks.extend(
            exact
        )

        namespace = event_name.split(
            ".",
            1,
        )[0]

        namespace_callbacks = (
            self._subscribers.get(
                f"{namespace}.*",
                [],
            )
        )

        callbacks.extend(
            namespace_callbacks
        )

        callbacks.extend(
            self._subscribers.get(
                "*",
                [],
            )
        )

        unique_callbacks: list[
            EventCallback
        ] = []

        for callback in callbacks:
            if callback not in unique_callbacks:
                unique_callbacks.append(
                    callback
                )

        return unique_callbacks

    # ==========================================================
    # History / Diagnostics
    # ==========================================================

    def get_history(
        self,
        *,
        event_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            history = list(
                self._history
            )

        if event_name:
            normalized = self._normalize_name(
                event_name
            )

            history = [
                event
                for event in history
                if event.get(
                    "name"
                ) == normalized
            ]

        if limit is not None:
            history = history[
                -max(
                    0,
                    int(limit),
                ):
            ]

        return [
            {
                **event,
                "payload": dict(
                    event.get(
                        "payload",
                        {},
                    )
                ),
            }
            for event in history
        ]

    def clear_history(self) -> None:
        with self._lock:
            self._history.clear()

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "subscriber_groups":
                    len(
                        self._subscribers
                    ),

                "subscriber_count":
                    sum(
                        len(callbacks)
                        for callbacks
                        in self._subscribers.values()
                    ),

                "history_entries":
                    len(
                        self._history
                    ),

                "history_limit":
                    self._history_limit,
            }

    @staticmethod
    def _normalize_name(
        event_name: str,
    ) -> str:
        normalized = (
            str(event_name)
            .strip()
            .lower()
        )

        if not normalized:
            raise ValueError(
                "Event name cannot be empty."
            )

        return normalized


event_bus = EventBus()