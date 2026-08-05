from typing import Any

from PySide6.QtCore import (
    QObject,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QCloseEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.engine import engine
from app.settings_manager import settings
from app.logger import logger
from app.event_bus import event_bus
from app.status_manager import status_manager
from ui.notification_center import notification_center
from app.restart_manager import restart_application
from ui.qt_bridge import EngineBridge
from version import (
    APP_VERSION,
    ENGINE_VERSION,
)




class StatusBridge(QObject):
    status_changed = Signal(dict)
    fatal_error = Signal(dict)

    def __init__(self) -> None:
        super().__init__()

        event_bus.subscribe(
            "status.changed",
            self._on_status_changed,
        )

        event_bus.subscribe(
            "app.fatal_error",
            self._on_fatal_error,
        )

    def _on_status_changed(
        self,
        event: dict[str, Any],
    ) -> None:
        self.status_changed.emit(
            event
        )

    def _on_fatal_error(
        self,
        event: dict[str, Any],
    ) -> None:
        self.fatal_error.emit(
            event
        )

    def close(self) -> None:
        event_bus.unsubscribe(
            "status.changed",
            self._on_status_changed,
        )

        event_bus.unsubscribe(
            "app.fatal_error",
            self._on_fatal_error,
        )


class MainWindow(QMainWindow):
    """
    GUI Foundation Spotify+.

    Pada tahap ini:
    - menampilkan status engine;
    - menampilkan lagu dan lirik;
    - menyediakan Start, Pause, Resume, Stop;
    - belum menggunakan system tray.
    """

    def __init__(self) -> None:
        super().__init__()

        self.bridge = EngineBridge()
        self.status_bridge = StatusBridge()

        notification_center.attach(
            self
        )

        self.settings_window = None
        self.dashboard_window = None
        self.log_viewer_window = None
        self.fatal_error_dialog = None
        self.update_dialog = None

        from ui.update_dialog import (
            UpdateChecker,
        )

        self.update_checker = (
            UpdateChecker()
        )
        self._manual_update_check = False

        # Diaktifkan oleh desktop.py ketika system tray tersedia.
        self.tray_available = False
        self.force_close = False
        self._hide_notification_shown = False

        self.setWindowTitle(
            "Spotify+"
        )

        self.setMinimumSize(
            760,
            700,
        )

        self.resize(
            860,
            760,
        )

        self._build_ui()
        self._connect_signals()
        self._apply_styles()

        # Status progress diperbarui setiap 500 ms.
        # Tidak menyebabkan request Spotify baru.
        self.status_timer = QTimer(
            self
        )

        self.status_timer.setInterval(
            500
        )

        self.status_timer.timeout.connect(
            self.refresh_status
        )

        self.status_timer.start()

        self.refresh_status()
        self.refresh_global_status()

    # ==========================================================
    # UI Construction
    # ==========================================================

    def _build_ui(self) -> None:
        central_widget = QWidget()

        self.setCentralWidget(
            central_widget
        )

        root_layout = QVBoxLayout(
            central_widget
        )

        root_layout.setContentsMargins(
            28,
            24,
            28,
            24,
        )

        root_layout.setSpacing(
            18
        )

        # Header
        header_layout = QHBoxLayout()

        title_container = QVBoxLayout()

        self.title_label = QLabel(
            "Spotify+"
        )

        self.subtitle_label = QLabel(
            "Better Spotify Presence"
        )

        title_container.addWidget(
            self.title_label
        )

        title_container.addWidget(
            self.subtitle_label
        )

        header_layout.addLayout(
            title_container
        )

        header_layout.addStretch()

        self.engine_status_badge = QLabel(
            "Stopped"
        )

        self.engine_status_badge.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        header_layout.addWidget(
            self.engine_status_badge
        )

        root_layout.addLayout(
            header_layout
        )

        # Now Playing Card
        now_playing_card = QFrame()

        now_playing_card.setObjectName(
            "card"
        )

        # Cegah isi Now Playing tertekan setelah Status Bar,
        # Dashboard, dan Logs ditambahkan.
        now_playing_card.setMinimumHeight(
            250
        )

        card_layout = QVBoxLayout(
            now_playing_card
        )

        card_layout.setContentsMargins(
            22,
            20,
            22,
            20,
        )

        card_layout.setSpacing(
            8
        )

        section_title = QLabel(
            "NOW PLAYING"
        )

        section_title.setObjectName(
            "sectionTitle"
        )

        self.song_label = QLabel(
            "Nothing playing"
        )

        self.song_label.setObjectName(
            "songTitle"
        )

        self.song_label.setWordWrap(
            True
        )

        self.song_label.setMinimumHeight(
            34
        )

        self.artist_label = QLabel(
            "—"
        )

        self.artist_label.setObjectName(
            "secondaryText"
        )

        self.album_label = QLabel(
            "—"
        )

        self.album_label.setObjectName(
            "mutedText"
        )

        self.lyric_label = QLabel(
            "Waiting for lyrics..."
        )

        self.lyric_label.setObjectName(
            "lyricText"
        )

        self.lyric_label.setWordWrap(
            True
        )

        self.lyric_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        # Pastikan area lirik tidak collapse menjadi 0 px ketika
        # window kekurangan ruang vertikal.
        self.lyric_label.setMinimumHeight(
            56
        )

        self.progress_bar = QProgressBar()

        self.progress_bar.setRange(
            0,
            1000,
        )

        self.progress_bar.setValue(
            0
        )

        self.progress_bar.setTextVisible(
            False
        )

        timer_layout = QHBoxLayout()

        self.current_time_label = QLabel(
            "00:00"
        )

        self.duration_label = QLabel(
            "00:00"
        )

        timer_layout.addWidget(
            self.current_time_label
        )

        timer_layout.addStretch()

        timer_layout.addWidget(
            self.duration_label
        )

        card_layout.addWidget(
            section_title
        )

        card_layout.addWidget(
            self.song_label
        )

        card_layout.addWidget(
            self.artist_label
        )

        card_layout.addWidget(
            self.album_label
        )

        card_layout.addSpacing(
            10
        )

        card_layout.addWidget(
            self.lyric_label
        )

        card_layout.addSpacing(
            10
        )

        card_layout.addWidget(
            self.progress_bar
        )

        card_layout.addLayout(
            timer_layout
        )

        root_layout.addWidget(
            now_playing_card
        )

        # Status Card
        status_card = QFrame()

        status_card.setObjectName(
            "card"
        )

        status_layout = QGridLayout(
            status_card
        )

        status_layout.setContentsMargins(
            22,
            18,
            22,
            18,
        )

        status_layout.setHorizontalSpacing(
            28
        )

        status_layout.setVerticalSpacing(
            12
        )

        self.profile_value = QLabel(
            "—"
        )

        self.discord_value = QLabel(
            "Disconnected"
        )

        self.provider_value = QLabel(
            "—"
        )

        self.confidence_value = QLabel(
            "—"
        )

        self.cache_value = QLabel(
            "—"
        )

        self.rate_limit_value = QLabel(
            "Normal"
        )

        status_items = [
            (
                "Spotify Profile",
                self.profile_value,
            ),
            (
                "Discord RPC",
                self.discord_value,
            ),
            (
                "Lyrics Provider",
                self.provider_value,
            ),
            (
                "Confidence",
                self.confidence_value,
            ),
            (
                "Cache",
                self.cache_value,
            ),
            (
                "Spotify API",
                self.rate_limit_value,
            ),
        ]

        for index, (
            label_text,
            value_widget,
        ) in enumerate(status_items):

            row = index // 2
            column = (
                index % 2
            ) * 2

            label = QLabel(
                label_text
            )

            label.setObjectName(
                "mutedText"
            )

            value_widget.setObjectName(
                "statusValue"
            )

            status_layout.addWidget(
                label,
                row,
                column,
            )

            status_layout.addWidget(
                value_widget,
                row,
                column + 1,
            )

        root_layout.addWidget(
            status_card
        )

        # Control buttons
        controls_layout = QHBoxLayout()

        controls_layout.setSpacing(
            10
        )

        self.start_button = QPushButton(
            "Start"
        )

        self.pause_button = QPushButton(
            "Pause"
        )

        self.resume_button = QPushButton(
            "Resume"
        )

        self.stop_button = QPushButton(
            "Stop"
        )

        self.settings_button = QPushButton(
            "Settings"
        )

        self.dashboard_button = QPushButton(
            "Dashboard"
        )

        self.logs_button = QPushButton(
            "Logs"
        )

        self.start_button.setObjectName(
            "primaryButton"
        )

        self.pause_button.setObjectName(
            "secondaryButton"
        )

        self.resume_button.setObjectName(
            "secondaryButton"
        )

        self.stop_button.setObjectName(
            "dangerButton"
        )

        self.settings_button.setObjectName(
            "secondaryButton"
        )

        self.dashboard_button.setObjectName(
            "secondaryButton"
        )

        self.logs_button.setObjectName(
            "secondaryButton"
        )

        controls_layout.addWidget(
            self.start_button
        )

        controls_layout.addWidget(
            self.pause_button
        )

        controls_layout.addWidget(
            self.resume_button
        )

        controls_layout.addWidget(
            self.stop_button
        )

        controls_layout.addWidget(
            self.settings_button
        )

        controls_layout.addWidget(
            self.dashboard_button
        )

        controls_layout.addWidget(
            self.logs_button
        )

        root_layout.addLayout(
            controls_layout
        )

        # Live application status bar.
        self.live_status_frame = QFrame()

        self.live_status_frame.setObjectName(
            "liveStatusBar"
        )

        live_status_layout = QHBoxLayout(
            self.live_status_frame
        )

        live_status_layout.setContentsMargins(
            14,
            10,
            14,
            10,
        )

        live_status_layout.setSpacing(
            12
        )

        self.live_status_dot = QLabel(
            "●"
        )

        self.live_status_dot.setObjectName(
            "liveStatusDot"
        )

        self.live_status_title = QLabel(
            "Starting"
        )

        self.live_status_title.setObjectName(
            "liveStatusTitle"
        )

        self.live_status_message = QLabel(
            "Initializing Spotify+"
        )

        self.live_status_message.setObjectName(
            "liveStatusMessage"
        )

        live_status_layout.addWidget(
            self.live_status_dot
        )

        live_status_layout.addWidget(
            self.live_status_title
        )

        live_status_layout.addWidget(
            self.live_status_message,
            1,
        )

        root_layout.addWidget(
            self.live_status_frame
        )

        self.version_label = QLabel(
            f"App {APP_VERSION}  •  "
            f"Engine {ENGINE_VERSION}"
        )

        self.version_label.setObjectName(
            "footerText"
        )

        self.version_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        root_layout.addWidget(
            self.version_label
        )

    # ==========================================================
    # Signal Connections
    # ==========================================================

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(
            self.start_engine
        )

        self.pause_button.clicked.connect(
            self.pause_engine
        )

        self.resume_button.clicked.connect(
            self.resume_engine
        )

        self.stop_button.clicked.connect(
            self.stop_engine
        )

        self.settings_button.clicked.connect(
            self.open_settings
        )

        self.dashboard_button.clicked.connect(
            self.open_dashboard
        )

        self.logs_button.clicked.connect(
            self.open_logs
        )

        self.bridge.status_changed.connect(
            self.update_from_status
        )

        self.bridge.song_changed.connect(
            self.on_song_changed
        )

        self.bridge.lyrics_changed.connect(
            self.on_lyrics_changed
        )

        self.bridge.rate_limit_changed.connect(
            self.on_rate_limit_changed
        )

        self.bridge.engine_error.connect(
            self.on_engine_error
        )

        self.bridge.restart_required.connect(
            self.on_restart_required
        )

        self.status_bridge.status_changed.connect(
            self.on_global_status_changed
        )

        self.status_bridge.fatal_error.connect(
            self.on_fatal_error
        )

        self.update_checker.checking_changed.connect(
            self.on_update_checking_changed
        )

        self.update_checker.update_available.connect(
            self.on_update_available
        )

        self.update_checker.up_to_date.connect(
            self.on_up_to_date
        )

        self.update_checker.check_failed.connect(
            self.on_update_check_failed
        )

    # ==========================================================
    # Engine Controls
    # ==========================================================

    def start_engine(self) -> None:
        engine.start()

        self.refresh_status()

    def pause_engine(self) -> None:
        engine.pause()

        self.refresh_status()

    def resume_engine(self) -> None:
        engine.resume()

        self.refresh_status()

    def stop_engine(self) -> None:
        engine.stop()

        self.refresh_status()

    # ==========================================================
    # Status Updates
    # ==========================================================

    def refresh_status(self) -> None:
        try:
            status = (
                self.bridge
                .request_status()
            )

            self.update_from_status(
                status
            )

        except Exception as error:
            self.engine_status_badge.setText(
                "Error"
            )

            self.engine_status_badge.setProperty(
                "status",
                "error",
            )

            self._refresh_widget_style(
                self.engine_status_badge
            )

            logger.error(
                "GUI status refresh failed",
                category="GUI",
                context={
                    "error": str(error),
                },
            )

    def update_from_status(
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

        if running and paused:
            status_text = "Paused"
            status_property = "paused"

        elif running:
            status_text = "Running"
            status_property = "running"

        else:
            status_text = "Stopped"
            status_property = "stopped"

        self.engine_status_badge.setText(
            status_text
        )

        self.engine_status_badge.setProperty(
            "status",
            status_property,
        )

        self._refresh_widget_style(
            self.engine_status_badge
        )

        song = status.get(
            "song"
        )

        artist = status.get(
            "artist"
        )

        album = status.get(
            "album"
        )

        lyric = status.get(
            "lyric"
        )

        self.song_label.setText(
            song or "Nothing playing"
        )

        self.artist_label.setText(
            artist or "—"
        )

        self.album_label.setText(
            album or "—"
        )

        self.lyric_label.setText(
            lyric or "Instrumental"
        )

        progress = float(
            status.get(
                "progress",
                0.0,
            )
            or 0.0
        )

        duration = float(
            status.get(
                "duration",
                0.0,
            )
            or 0.0
        )

        if duration > 0:
            percentage = int(
                min(
                    max(
                        progress / duration,
                        0.0,
                    ),
                    1.0,
                )
                * 1000
            )
        else:
            percentage = 0

        self.progress_bar.setValue(
            percentage
        )

        self.current_time_label.setText(
            self.format_duration(
                progress
            )
        )

        self.duration_label.setText(
            self.format_duration(
                duration
            )
        )

        profile = status.get(
            "profile"
        )

        provider = status.get(
            "lyrics_provider"
        )

        confidence = float(
            status.get(
                "lyrics_confidence",
                0.0,
            )
            or 0.0
        )

        cache_source = status.get(
            "cache_source"
        )

        rpc_connected = bool(
            status.get(
                "rpc_connected",
                False,
            )
        )

        rate_limited = bool(
            status.get(
                "rate_limited",
                False,
            )
        )

        retry_after = int(
            status.get(
                "retry_after",
                0,
            )
            or 0
        )

        # Sinkronkan Status Manager dengan snapshot aktual engine.
        # publish=False mencegah event berulang setiap refresh 500 ms.
        engine_state = (
            "paused"
            if running and paused
            else (
                "running"
                if running
                else "stopped"
            )
        )

        status_manager.update(
            "engine",
            publish=False,
            state=engine_state,
            message=(
                "Engine paused"
                if engine_state == "paused"
                else (
                    "Engine running"
                    if engine_state == "running"
                    else "Engine stopped"
                )
            ),
        )

        status_manager.update(
            "rpc",
            publish=False,
            state=(
                "connected"
                if rpc_connected
                else "disconnected"
            ),
            message=(
                "Discord connected"
                if rpc_connected
                else "Discord disconnected"
            ),
        )

        status_manager.update(
            "spotify",
            publish=False,
            state=(
                "rate_limited"
                if rate_limited
                else "connected"
            ),
            message=(
                "Spotify cooldown active"
                if rate_limited
                else "Spotify connected"
            ),
            retry_after=retry_after,
            profile=str(
                profile or ""
            ),
        )

        status_manager.update(
            "lyrics",
            publish=False,
            state=(
                "ready"
                if provider
                else "idle"
            ),
            message=(
                "Lyrics ready"
                if provider
                else "Lyrics idle"
            ),
            provider=str(
                provider or ""
            ),
        )

        # Refresh live status bar dari snapshot yang baru disinkronkan.
        self.refresh_global_status()

        self.profile_value.setText(
            str(profile or "—")
        )

        self.provider_value.setText(
            str(provider or "—")
        )

        self.confidence_value.setText(
            (
                f"{confidence:.0%}"
                if confidence > 0
                else "—"
            )
        )

        self.cache_value.setText(
            str(
                cache_source
                or "Network"
            ).title()
        )

        self.discord_value.setText(
            (
                "Connected"
                if rpc_connected
                else "Disconnected"
            )
        )

        if rate_limited:
            self.rate_limit_value.setText(
                "Cooldown "
                + self.format_duration(
                    retry_after
                )
            )
        else:
            self.rate_limit_value.setText(
                "Normal"
            )

        self.start_button.setEnabled(
            not running
        )

        self.pause_button.setEnabled(
            running
            and not paused
        )

        self.resume_button.setEnabled(
            running
            and paused
        )

        self.stop_button.setEnabled(
            running
        )

    def on_song_changed(
        self,
        data: dict[str, Any],
    ) -> None:
        self.song_label.setText(
            data.get(
                "song"
            )
            or "Nothing playing"
        )

        self.artist_label.setText(
            data.get(
                "artist"
            )
            or "—"
        )

        self.album_label.setText(
            data.get(
                "album"
            )
            or "—"
        )

    def on_lyrics_changed(
        self,
        data: dict[str, Any],
    ) -> None:
        self.lyric_label.setText(
            data.get(
                "lyric"
            )
            or "Instrumental"
        )

    def on_rate_limit_changed(
        self,
        data: dict[str, Any],
    ) -> None:
        if data.get(
            "rate_limited",
            False,
        ):
            retry_after = int(
                data.get(
                    "retry_after",
                    0,
                )
            )

            QMessageBox.warning(
                self,
                "Spotify Rate Limit",
                (
                    "Spotify API sedang cooldown.\n\n"
                    "Sisa waktu: "
                    f"{self.format_duration(retry_after)}"
                ),
            )

    def on_engine_error(
        self,
        data: dict[str, Any],
    ) -> None:
        message = str(
            data.get(
                "message",
                "Unknown engine error",
            )
        )

        event_bus.publish(
            "app.fatal_error",
            source="engine_bridge",
            message="Spotify+ engine error",
            details=message,
        )

    def on_fatal_error(
        self,
        event: dict[str, Any],
    ) -> None:
        payload = event.get(
            "payload",
            {},
        )

        message = str(
            payload.get(
                "message",
                "Spotify+ encountered an error",
            )
        )

        details = str(
            payload.get(
                "details",
                message,
            )
        )

        logger.flush()

        from ui.fatal_error_dialog import (
            FatalErrorDialog,
        )

        if (
            self.fatal_error_dialog is not None
            and self.fatal_error_dialog.isVisible()
        ):
            return

        self.fatal_error_dialog = (
            FatalErrorDialog(
                message=message,
                details=details,
                parent=self,
            )
        )

        self.fatal_error_dialog.finished.connect(
            self._clear_fatal_dialog
        )

        self.fatal_error_dialog.show()
        self.fatal_error_dialog.raise_()
        self.fatal_error_dialog.activateWindow()

    def _clear_fatal_dialog(
        self,
        result: int,
    ) -> None:
        del result

        self.fatal_error_dialog = None

    def on_restart_required(
        self,
        data: dict[str, Any],
    ) -> None:
        items = data.get(
            "items",
            [],
        )

        profile = data.get(
            "profile"
        )

        lines = [
            "Spotify+ must restart to apply the change."
        ]

        if items:
            lines.extend(
                [
                    "",
                    "Changed:",
                ]
            )

            for item in items:
                lines.append(
                    f"- {item}"
                )

        elif profile:
            lines.extend(
                [
                    "",
                    f"Profile: {profile}",
                ]
            )

        message_box = QMessageBox(
            self
        )

        message_box.setWindowTitle(
            "Restart Required"
        )

        message_box.setIcon(
            QMessageBox.Icon.Information
        )

        message_box.setText(
            "\n".join(
                lines
            )
        )

        restart_button = (
            message_box.addButton(
                "Restart Now",
                QMessageBox.ButtonRole.AcceptRole,
            )
        )

        message_box.addButton(
            "Later",
            QMessageBox.ButtonRole.RejectRole,
        )

        message_box.exec()

        if (
            message_box.clickedButton()
            is restart_button
        ):
            if not restart_application():
                QMessageBox.critical(
                    self,
                    "Restart Failed",
                    (
                        "Spotify+ could not start a new "
                        "application process."
                    ),
                )

    def on_global_status_changed(
        self,
        event: dict[str, Any],
    ) -> None:
        del event

        overall = (
            status_manager
            .get_overall_status()
        )

        level = str(
            overall.get(
                "level",
                "neutral",
            )
        )

        self.live_status_frame.setProperty(
            "level",
            level,
        )

        self.live_status_title.setText(
            str(
                overall.get(
                    "title",
                    "Spotify+",
                )
            )
        )

        self.live_status_message.setText(
            str(
                overall.get(
                    "message",
                    "",
                )
            )
        )

        self._refresh_widget_style(
            self.live_status_frame
        )

    def refresh_global_status(self) -> None:
        self.on_global_status_changed(
            {}
        )

    def check_for_updates(
        self,
        channel: str | None = None,
        *,
        manual: bool = True,
    ) -> None:
        selected_channel = (
            channel
            or settings.get(
                "update_channel",
                "stable",
            )
        )

        self._manual_update_check = manual

        started = self.update_checker.check(
            str(selected_channel)
        )

        if (
            not started
            and manual
        ):
            QMessageBox.information(
                self,
                "Update Check",
                "An update check is already running.",
            )

    def check_for_updates_on_startup(
        self,
    ) -> None:
        if not settings.get(
            "check_updates_on_startup",
            True,
        ):
            return

        self.check_for_updates(
            str(
                settings.get(
                    "update_channel",
                    "stable",
                )
            ),
            manual=False,
        )

    def on_update_checking_changed(
        self,
        checking: bool,
    ) -> None:
        if (
            self.settings_window is not None
        ):
            self.settings_window.check_update_button.setEnabled(
                not checking
            )

            self.settings_window.check_update_button.setText(
                (
                    "Checking..."
                    if checking
                    else "Check for Updates"
                )
            )

    def on_update_available(
        self,
        result: object,
    ) -> None:
        from app.update_models import (
            UpdateCheckResult,
        )
        from ui.update_dialog import (
            UpdateAvailableDialog,
        )

        if not isinstance(
            result,
            UpdateCheckResult,
        ):
            return

        self.update_dialog = (
            UpdateAvailableDialog(
                result,
                parent=self,
            )
        )

        self.update_dialog.finished.connect(
            self._clear_update_dialog
        )

        self.update_dialog.show()
        self.update_dialog.raise_()
        self.update_dialog.activateWindow()

    def _clear_update_dialog(
        self,
        result: int,
    ) -> None:
        del result
        self.update_dialog = None

    def on_up_to_date(
        self,
        result: object,
    ) -> None:
        if not self._manual_update_check:
            return

        latest = getattr(
            result,
            "latest_version",
            "current",
        )

        QMessageBox.information(
            self,
            "Spotify+ Updates",
            (
                "Spotify+ is up to date.\n\n"
                f"Version: {latest}"
            ),
        )

    def on_update_check_failed(
        self,
        message: str,
    ) -> None:
        if not self._manual_update_check:
            logger.warning(
                "Startup update check failed silently",
                category="UPDATER",
                context={
                    "error": message,
                },
            )
            return

        QMessageBox.warning(
            self,
            "Update Check Failed",
            message,
        )

    def open_settings(self) -> None:
        """
        Membuka Settings Window.
        """

        if self.settings_window is None:
            from ui.settings_window import (
                SettingsWindow,
            )

            self.settings_window = (
                SettingsWindow()
            )

            self.settings_window.restart_required.connect(
                self.on_restart_required
            )

            self.settings_window.check_update_requested.connect(
                self.check_for_updates
            )

        self.settings_window.show_window()

    def open_dashboard(self) -> None:
        """
        Membuka Live Runtime Dashboard.
        """

        if self.dashboard_window is None:
            from ui.dashboard_window import (
                DashboardWindow,
            )

            self.dashboard_window = (
                DashboardWindow()
            )

        self.dashboard_window.show_window()

    def open_logs(self) -> None:
        """
        Membuka Log Viewer.
        """

        if self.log_viewer_window is None:
            from ui.log_viewer import (
                LogViewerWindow,
            )

            self.log_viewer_window = (
                LogViewerWindow()
            )

        self.log_viewer_window.show_window()

    # ==========================================================
    # Helpers
    # ==========================================================

    @staticmethod
    def format_duration(
        seconds: float | int,
    ) -> str:
        total_seconds = max(
            0,
            int(seconds),
        )

        minutes, remaining_seconds = divmod(
            total_seconds,
            60,
        )

        hours, minutes = divmod(
            minutes,
            60,
        )

        if hours > 0:
            return (
                f"{hours:02d}:"
                f"{minutes:02d}:"
                f"{remaining_seconds:02d}"
            )

        return (
            f"{minutes:02d}:"
            f"{remaining_seconds:02d}"
        )

    @staticmethod
    def _refresh_widget_style(
        widget: QWidget,
    ) -> None:
        widget.style().unpolish(
            widget
        )

        widget.style().polish(
            widget
        )

        widget.update()

    def set_tray_available(
        self,
        available: bool,
    ) -> None:
        """
        Menentukan apakah tombol X boleh menyembunyikan window
        ke system tray.
        """

        self.tray_available = available

    def show_from_tray(self) -> None:
        """
        Membuka kembali window dari system tray.
        """

        self.showNormal()
        self.raise_()
        self.activateWindow()

    def request_exit(self) -> None:
        """
        Dipanggil hanya ketika user memilih Exit dari tray.
        """

        self.force_close = True
        self.close()

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """
        Klik X menyembunyikan aplikasi ke tray.

        Engine hanya dihentikan saat user memilih Exit dari menu
        system tray atau saat system tray tidak tersedia.
        """

        if (
            self.tray_available
            and not self.force_close
        ):
            event.ignore()
            self.hide()

            if not self._hide_notification_shown:
                self._hide_notification_shown = True

                logger.info(
                    "Window hidden to system tray",
                    category="GUI",
                )

            return

        self.status_timer.stop()
        self.bridge.close()
        self.status_bridge.close()

        engine.shutdown()

        event.accept()

    # ==========================================================
    # Theme
    # ==========================================================

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #121212;
            }

            QWidget {
                color: #F5F5F5;
                font-family: "Segoe UI";
                font-size: 14px;
            }

            QLabel#sectionTitle {
                color: #1ED760;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }

            QLabel#songTitle {
                color: #FFFFFF;
                font-size: 24px;
                font-weight: 700;
            }

            QLabel#secondaryText {
                color: #E5E5E5;
                font-size: 15px;
                font-weight: 600;
            }

            QLabel#mutedText {
                color: #A7A7A7;
                font-size: 12px;
            }

            QLabel#lyricText {
                color: #FFFFFF;
                font-size: 18px;
                font-weight: 600;
                padding: 12px;
            }

            QLabel#statusValue {
                color: #FFFFFF;
                font-weight: 600;
            }

            QLabel#footerText {
                color: #6F6F6F;
                font-size: 11px;
            }

            QFrame#card {
                background-color: #1E1E1E;
                border: 1px solid #2B2B2B;
                border-radius: 14px;
            }

            QLabel[status="running"] {
                color: #081C0F;
                background-color: #1ED760;
                border-radius: 12px;
                padding: 7px 16px;
                font-weight: 700;
            }

            QLabel[status="paused"] {
                color: #1F1600;
                background-color: #F5C542;
                border-radius: 12px;
                padding: 7px 16px;
                font-weight: 700;
            }

            QLabel[status="stopped"] {
                color: #D0D0D0;
                background-color: #333333;
                border-radius: 12px;
                padding: 7px 16px;
                font-weight: 700;
            }

            QLabel[status="error"] {
                color: #FFFFFF;
                background-color: #C62828;
                border-radius: 12px;
                padding: 7px 16px;
                font-weight: 700;
            }

            QFrame#liveStatusBar {
                background-color: #242424;
                border: 1px solid #3A3A3A;
                border-radius: 10px;
            }

            QFrame#liveStatusBar[level="success"] {
                border-color: #1ED760;
            }

            QFrame#liveStatusBar[level="warning"] {
                border-color: #F5C542;
            }

            QFrame#liveStatusBar[level="error"] {
                border-color: #E05252;
            }

            QLabel#liveStatusDot {
                color: #A7A7A7;
                font-size: 16px;
            }

            QFrame#liveStatusBar[level="success"] QLabel#liveStatusDot {
                color: #1ED760;
            }

            QFrame#liveStatusBar[level="warning"] QLabel#liveStatusDot {
                color: #F5C542;
            }

            QFrame#liveStatusBar[level="error"] QLabel#liveStatusDot {
                color: #E05252;
            }

            QLabel#liveStatusTitle {
                color: #FFFFFF;
                font-weight: 700;
            }

            QLabel#liveStatusMessage {
                color: #A7A7A7;
            }

            QProgressBar {
                background-color: #3A3A3A;
                border: none;
                border-radius: 4px;
                min-height: 8px;
                max-height: 8px;
            }

            QProgressBar::chunk {
                background-color: #1ED760;
                border-radius: 4px;
            }

            QPushButton {
                min-height: 42px;
                padding: 0 18px;
                border-radius: 10px;
                font-weight: 600;
            }

            QPushButton#primaryButton {
                color: #081C0F;
                background-color: #1ED760;
                border: none;
            }

            QPushButton#primaryButton:hover {
                background-color: #2BE06B;
            }

            QPushButton#secondaryButton {
                color: #FFFFFF;
                background-color: #2A2A2A;
                border: 1px solid #444444;
            }

            QPushButton#secondaryButton:hover {
                background-color: #353535;
            }

            QPushButton#dangerButton {
                color: #FFFFFF;
                background-color: #3A2020;
                border: 1px solid #6B3030;
            }

            QPushButton#dangerButton:hover {
                background-color: #512626;
            }

            QPushButton:disabled {
                color: #676767;
                background-color: #242424;
                border-color: #303030;
            }
            """
        )