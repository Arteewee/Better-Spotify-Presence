from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtGui import (
    QAction,
    QIcon,
)
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QStyle,
    QSystemTrayIcon,
)

from app.engine import engine
from app.logger import logger
from app.event_bus import event_bus
from app.status_manager import status_manager
from ui.main_window import MainWindow
from ui.qt_bridge import EngineBridge


class TrayIcon(QObject):
    """
    System tray controller Spotify+.

    Menu tray:
    - Open Spotify+
    - Start / Pause / Resume / Stop
    - Exit
    """

    def __init__(
        self,
        window: MainWindow,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self.window = window
        self.bridge = EngineBridge()
        self._is_exiting = False

        event_bus.subscribe(
            "status.changed",
            self._on_global_status_changed,
        )

        icon = self._build_icon()

        self.tray = QSystemTrayIcon(
            icon,
            self,
        )

        self.tray.setToolTip(
            "Spotify+"
        )

        self.menu = QMenu()

        self.open_action = QAction(
            "Open Spotify+",
            self,
        )

        self.start_action = QAction(
            "Start",
            self,
        )

        self.pause_action = QAction(
            "Pause",
            self,
        )

        self.resume_action = QAction(
            "Resume",
            self,
        )

        self.stop_action = QAction(
            "Stop",
            self,
        )

        self.settings_action = QAction(
            "Settings",
            self,
        )

        self.logs_action = QAction(
            "Logs",
            self,
        )

        self.exit_action = QAction(
            "Exit",
            self,
        )

        self.menu.addAction(
            self.open_action
        )

        self.menu.addSeparator()

        self.menu.addAction(
            self.start_action
        )

        self.menu.addAction(
            self.pause_action
        )

        self.menu.addAction(
            self.resume_action
        )

        self.menu.addAction(
            self.stop_action
        )

        self.menu.addSeparator()

        self.menu.addAction(
            self.settings_action
        )

        self.menu.addAction(
            self.logs_action
        )

        self.menu.addSeparator()

        self.menu.addAction(
            self.exit_action
        )

        self.tray.setContextMenu(
            self.menu
        )

        self._connect_signals()
        self.refresh_actions(
            engine.get_status()
        )

    @staticmethod
    def is_available() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def _build_icon(self) -> QIcon:
        """
        Gunakan icon window/app bila tersedia.
        Fallback ke icon bawaan Qt supaya tray tetap berfungsi.
        """

        application = QApplication.instance()

        if application is not None:
            app_icon = application.windowIcon()

            if not app_icon.isNull():
                return app_icon

        style = QApplication.style()

        return style.standardIcon(
            QStyle.StandardPixmap.SP_MediaPlay
        )

    def _connect_signals(self) -> None:
        self.open_action.triggered.connect(
            self.show_window
        )

        self.start_action.triggered.connect(
            engine.start
        )

        self.pause_action.triggered.connect(
            engine.pause
        )

        self.resume_action.triggered.connect(
            engine.resume
        )

        self.stop_action.triggered.connect(
            engine.stop
        )

        self.settings_action.triggered.connect(
            self.window.open_settings
        )

        self.logs_action.triggered.connect(
            self.window.open_logs
        )

        self.exit_action.triggered.connect(
            self.exit_application
        )

        self.tray.activated.connect(
            self.on_tray_activated
        )

        self.bridge.status_changed.connect(
            self.refresh_actions
        )

        self.bridge.song_changed.connect(
            self.on_song_changed
        )

    def show(self) -> None:
        self.tray.show()

    def show_window(self) -> None:
        self.window.show_from_tray()

    def on_tray_activated(
        self,
        reason: QSystemTrayIcon.ActivationReason,
    ) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        }:
            self.show_window()

    def refresh_actions(
        self,
        status: dict[str, Any],
    ) -> None:
        running = bool(
            status.get(
                "running",
                False,
            )
        )

        paused = bool(
            status.get(
                "paused",
                False,
            )
        )

        self.start_action.setEnabled(
            not running
        )

        self.pause_action.setEnabled(
            running
            and not paused
        )

        self.resume_action.setEnabled(
            running
            and paused
        )

        self.stop_action.setEnabled(
            running
        )

        if running and paused:
            self.tray.setToolTip(
                "Spotify+ — Paused"
            )

        elif running:
            song = status.get(
                "song"
            )

            if song:
                self.tray.setToolTip(
                    f"Spotify+ — {song}"
                )
            else:
                self.tray.setToolTip(
                    "Spotify+ — Running"
                )

        else:
            self.tray.setToolTip(
                "Spotify+ — Stopped"
            )

    def on_song_changed(
        self,
        data: dict[str, Any],
    ) -> None:
        song = data.get(
            "song"
        )

        artist = data.get(
            "artist"
        )

        if song:
            message = song

            if artist:
                message += (
                    f"\n{artist}"
                )

            self.tray.showMessage(
                "Now Playing",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )

    def notify_hidden(self) -> None:
        self.tray.showMessage(
            "Spotify+ is still running",
            (
                "The window was hidden. "
                "Open it again from the system tray."
            ),
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def _on_global_status_changed(
        self,
        event: dict[str, Any],
    ) -> None:
        del event

        overall = (
            status_manager
            .get_overall_status()
        )

        self.tray.setToolTip(
            (
                "Spotify+ — "
                f"{overall.get('title', 'Running')}"
            )
        )

    def exit_application(self) -> None:
        if self._is_exiting:
            return

        self._is_exiting = True

        self.bridge.close()

        logger.info(
            "Application exit requested from system tray",
            category="GUI",
        )

        logger.flush()

        event_bus.unsubscribe(
            "status.changed",
            self._on_global_status_changed,
        )

        self.tray.hide()

        self.window.request_exit()

        application = QApplication.instance()

        if application is not None:
            application.quit()