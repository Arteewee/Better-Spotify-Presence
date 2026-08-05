from collections import deque
from typing import Any, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.event_bus import event_bus


class NotificationBridge(QObject):
    notification_received = Signal(dict)

    def __init__(self) -> None:
        super().__init__()

        event_bus.subscribe(
            "notification.show",
            self._on_notification,
        )

        event_bus.subscribe(
            "spotify.rate_limit",
            self._on_rate_limit,
        )

        event_bus.subscribe(
            "app.fatal_error",
            self._on_fatal_error,
        )

        event_bus.subscribe(
            "log.created",
            self._on_log_created,
        )

    def _on_notification(
        self,
        event: dict[str, Any],
    ) -> None:
        self.notification_received.emit(
            dict(
                event.get(
                    "payload",
                    {},
                )
            )
        )

    def _on_rate_limit(
        self,
        event: dict[str, Any],
    ) -> None:
        payload = event.get(
            "payload",
            {},
        )

        self.notification_received.emit(
            {
                "level": "warning",
                "title": "Spotify Cooldown",
                "message": (
                    "Spotify is rate limited. "
                    f"Retry in {payload.get('retry_after', 0)} seconds."
                ),
                "duration": 5000,
            }
        )

    def _on_fatal_error(
        self,
        event: dict[str, Any],
    ) -> None:
        payload = event.get(
            "payload",
            {},
        )

        self.notification_received.emit(
            {
                "level": "error",
                "title": "Application Error",
                "message": payload.get(
                    "message",
                    "Unexpected application error",
                ),
                "duration": 7000,
            }
        )


    def _on_log_created(
        self,
        event: dict[str, Any],
    ) -> None:
        entry = (
            event.get(
                "payload",
                {},
            ).get(
                "entry",
                {},
            )
        )

        level = str(
            entry.get(
                "level",
                "",
            )
        ).upper()

        category = str(
            entry.get(
                "category",
                "APP",
            )
        ).upper()

        # Hindari spam dari provider lyrics yang sedang fallback.
        if category == "LYRICS":
            return

        if level not in {
            "ERROR",
            "CRITICAL",
        }:
            return

        self.notification_received.emit(
            {
                "level": "error",
                "title": f"{category} Error",
                "message": str(
                    entry.get(
                        "message",
                        "Unexpected error",
                    )
                ),
                "duration": 6000,
            }
        )


class ToastWidget(QFrame):

    def __init__(
        self,
        *,
        title: str,
        message: str,
        level: str,
        parent: QWidget,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "toast"
        )

        self.setProperty(
            "level",
            level,
        )

        self.setFixedWidth(
            340
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            14,
            12,
            14,
            12,
        )

        layout.setSpacing(
            4
        )

        title_label = QLabel(
            title
        )

        title_label.setObjectName(
            "toastTitle"
        )

        message_label = QLabel(
            message
        )

        message_label.setObjectName(
            "toastMessage"
        )

        message_label.setWordWrap(
            True
        )

        layout.addWidget(
            title_label
        )

        layout.addWidget(
            message_label
        )

        self.setStyleSheet(
            """
            QFrame#toast {
                background-color: #202020;
                border: 1px solid #444444;
                border-radius: 12px;
            }

            QFrame#toast[level="success"] {
                border-color: #1ED760;
            }

            QFrame#toast[level="warning"] {
                border-color: #F5C542;
            }

            QFrame#toast[level="error"] {
                border-color: #E05252;
            }

            QLabel#toastTitle {
                color: #FFFFFF;
                font-weight: 700;
                font-size: 13px;
            }

            QLabel#toastMessage {
                color: #CFCFCF;
                font-size: 12px;
            }
            """
        )


class NotificationCenter(QObject):
    """
    Internal toast notification queue.

    Attach ke MainWindow:
        notification_center.attach(window)
    """

    def __init__(self) -> None:
        super().__init__()

        self.bridge = NotificationBridge()

        self.bridge.notification_received.connect(
            self.enqueue
        )

        self._parent_window: Optional[
            QWidget
        ] = None

        self._queue: deque[
            dict[str, Any]
        ] = deque()

        self._active_toast: Optional[
            ToastWidget
        ] = None

        self._animation: Optional[
            QPropertyAnimation
        ] = None

    def attach(
        self,
        parent_window: QWidget,
    ) -> None:
        self._parent_window = (
            parent_window
        )

    def enqueue(
        self,
        notification: dict[str, Any],
    ) -> None:
        self._queue.append(
            {
                "level":
                    str(
                        notification.get(
                            "level",
                            "info",
                        )
                    ).lower(),

                "title":
                    str(
                        notification.get(
                            "title",
                            "Spotify+",
                        )
                    ),

                "message":
                    str(
                        notification.get(
                            "message",
                            "",
                        )
                    ),

                "duration":
                    int(
                        notification.get(
                            "duration",
                            4000,
                        )
                    ),
            }
        )

        if self._active_toast is None:
            self._show_next()

    def _show_next(self) -> None:
        if (
            not self._queue
            or self._parent_window is None
        ):
            return

        data = self._queue.popleft()

        toast = ToastWidget(
            title=data[
                "title"
            ],
            message=data[
                "message"
            ],
            level=data[
                "level"
            ],
            parent=self._parent_window,
        )

        toast.adjustSize()

        margin = 20

        end_x = (
            self._parent_window.width()
            - toast.width()
            - margin
        )

        y = margin

        start_x = (
            self._parent_window.width()
            + toast.width()
        )

        toast.move(
            start_x,
            y,
        )

        toast.show()
        toast.raise_()

        self._active_toast = toast

        animation = QPropertyAnimation(
            toast,
            b"pos",
            self,
        )

        animation.setDuration(
            250
        )

        animation.setStartValue(
            toast.pos()
        )

        animation.setEndValue(
            toast.pos().__class__(
                end_x,
                y,
            )
        )

        animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        animation.start()

        self._animation = animation

        QTimer.singleShot(
            max(
                1000,
                data[
                    "duration"
                ],
            ),
            self._hide_active,
        )

    def _hide_active(self) -> None:
        toast = self._active_toast

        if toast is None:
            return

        toast.hide()
        toast.deleteLater()

        self._active_toast = None
        self._animation = None

        QTimer.singleShot(
            100,
            self._show_next,
        )

    # Convenience API

    @staticmethod
    def info(
        title: str,
        message: str,
        *,
        duration: int = 4000,
    ) -> None:
        event_bus.publish(
            "notification.show",
            source="notification_center",
            level="info",
            title=title,
            message=message,
            duration=duration,
        )

    @staticmethod
    def success(
        title: str,
        message: str,
        *,
        duration: int = 4000,
    ) -> None:
        event_bus.publish(
            "notification.show",
            source="notification_center",
            level="success",
            title=title,
            message=message,
            duration=duration,
        )

    @staticmethod
    def warning(
        title: str,
        message: str,
        *,
        duration: int = 5000,
    ) -> None:
        event_bus.publish(
            "notification.show",
            source="notification_center",
            level="warning",
            title=title,
            message=message,
            duration=duration,
        )

    @staticmethod
    def error(
        title: str,
        message: str,
        *,
        duration: int = 6000,
    ) -> None:
        event_bus.publish(
            "notification.show",
            source="notification_center",
            level="error",
            title=title,
            message=message,
            duration=duration,
        )


notification_center = NotificationCenter()