from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.styles import (
    apply_app_style,
    apply_responsive_geometry,
)
from app.engine import engine
from app.settings_manager import settings
from app.logger import logger


class SettingsWindow(QWidget):
    """
    Spotify+ application settings.

    Spotify credentials are managed only through Profile Manager.
    Runtime-safe preferences are applied immediately.
    """

    restart_required = Signal(dict)
    runtime_settings_changed = Signal(dict)
    check_update_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        self.profile_manager_window = None

        self.setWindowTitle(
            "Spotify+ Settings"
        )

        apply_responsive_geometry(
            self,
            preferred_width=720,
            preferred_height=760,
            minimum_width=600,
            minimum_height=580,
        )

        self._build_ui()
        self._apply_styles()
        self._apply_tooltips()
        self.load_settings()

    # ==========================================================
    # UI
    # ==========================================================

    def _build_ui(self) -> None:
        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            18,
            18,
            18,
            18,
        )

        root.setSpacing(
            14
        )

        title = QLabel(
            "Settings"
        )

        title.setObjectName(
            "pageTitle"
        )

        subtitle = QLabel(
            "Configure application behavior and runtime engine "
            "preferences."
        )

        subtitle.setObjectName(
            "mutedText"
        )

        subtitle.setWordWrap(
            True
        )

        root.addWidget(
            title
        )

        root.addWidget(
            subtitle
        )

        scroll = QScrollArea()

        scroll.setWidgetResizable(
            True
        )

        scroll.setFrameShape(
            QScrollArea.Shape.NoFrame
        )

        content = QWidget()

        content_layout = QVBoxLayout(
            content
        )

        content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        content_layout.setSpacing(
            14
        )

        content_layout.addWidget(
            self._build_general_group()
        )

        content_layout.addWidget(
            self._build_profile_group()
        )

        content_layout.addWidget(
            self._build_engine_group()
        )

        content_layout.addWidget(
            self._build_update_group()
        )

        content_layout.addStretch()

        scroll.setWidget(
            content
        )

        root.addWidget(
            scroll,
            1,
        )

        buttons = QHBoxLayout()

        buttons.addStretch()

        self.reload_button = QPushButton(
            "Reload"
        )

        self.save_button = QPushButton(
            "Save Settings"
        )

        self.save_button.setObjectName(
            "primaryButton"
        )

        buttons.addWidget(
            self.reload_button
        )

        buttons.addWidget(
            self.save_button
        )

        root.addLayout(
            buttons
        )

        self.reload_button.clicked.connect(
            self.load_settings
        )

        self.save_button.clicked.connect(
            self.save_settings
        )

        self.manage_profiles_button.clicked.connect(
            self.open_profile_manager
        )

        self.check_update_button.clicked.connect(
            self.request_update_check
        )

    def _build_general_group(
        self,
    ) -> QGroupBox:
        group = QGroupBox(
            "Application"
        )

        layout = QFormLayout(
            group
        )

        self.start_engine_checkbox = QCheckBox(
            "Start engine when Spotify+ opens"
        )

        self.minimize_to_tray_checkbox = QCheckBox(
            "Close window to system tray"
        )

        self.notification_checkbox = QCheckBox(
            "Show now-playing notifications"
        )

        self.diagnostics_checkbox = QCheckBox(
            "Enable terminal diagnostics"
        )

        self.diagnostics_interval_spin = QDoubleSpinBox()

        self.diagnostics_interval_spin.setRange(
            5.0,
            3600.0,
        )

        self.diagnostics_interval_spin.setSuffix(
            " seconds"
        )

        self.diagnostics_interval_spin.setDecimals(
            0
        )

        layout.addRow(
            self.start_engine_checkbox
        )

        layout.addRow(
            self.minimize_to_tray_checkbox
        )

        layout.addRow(
            self.notification_checkbox
        )

        layout.addRow(
            self.diagnostics_checkbox
        )

        layout.addRow(
            "Diagnostics interval",
            self.diagnostics_interval_spin,
        )

        return group

    def _build_profile_group(
        self,
    ) -> QGroupBox:
        group = QGroupBox(
            "Spotify Profiles"
        )

        layout = QFormLayout(
            group
        )

        self.active_profile_value = QLabel(
            "—"
        )

        self.active_profile_value.setObjectName(
            "statusValue"
        )

        self.profile_count_value = QLabel(
            "0"
        )

        self.profile_count_value.setObjectName(
            "statusValue"
        )

        self.manage_profiles_button = QPushButton(
            "Manage Profiles"
        )

        self.discord_client_id_input = QLineEdit()

        note = QLabel(
            "Spotify credentials and profile switching are managed "
            "from Profile Manager. Those changes require restart."
        )

        note.setObjectName(
            "warningText"
        )

        note.setWordWrap(
            True
        )

        layout.addRow(
            "Active profile",
            self.active_profile_value,
        )

        layout.addRow(
            "Available profiles",
            self.profile_count_value,
        )

        layout.addRow(
            "",
            self.manage_profiles_button,
        )

        layout.addRow(
            "Discord Application ID",
            self.discord_client_id_input,
        )

        layout.addRow(
            note
        )

        return group

    def _build_engine_group(
        self,
    ) -> QGroupBox:
        group = QGroupBox(
            "Playback and Lyrics Engine"
        )

        layout = QFormLayout(
            group
        )

        self.spotify_refresh_spin = QDoubleSpinBox()

        self.spotify_refresh_spin.setRange(
            1.0,
            30.0,
        )

        self.spotify_refresh_spin.setSingleStep(
            0.5
        )

        self.spotify_refresh_spin.setSuffix(
            " seconds"
        )

        self.fast_refresh_spin = QDoubleSpinBox()

        self.fast_refresh_spin.setRange(
            0.5,
            10.0,
        )

        self.fast_refresh_spin.setSingleStep(
            0.5
        )

        self.fast_refresh_spin.setSuffix(
            " seconds"
        )

        self.ending_window_spin = QDoubleSpinBox()

        self.ending_window_spin.setRange(
            1.0,
            60.0,
        )

        self.ending_window_spin.setSuffix(
            " seconds"
        )

        self.lyrics_timeout_spin = QDoubleSpinBox()

        self.lyrics_timeout_spin.setRange(
            1.0,
            30.0,
        )

        self.lyrics_timeout_spin.setSuffix(
            " seconds"
        )

        self.confidence_spin = QDoubleSpinBox()

        self.confidence_spin.setRange(
            0.0,
            1.0,
        )

        self.confidence_spin.setSingleStep(
            0.01
        )

        self.confidence_spin.setDecimals(
            2
        )

        layout.addRow(
            "Spotify polling",
            self.spotify_refresh_spin,
        )

        layout.addRow(
            "Fast polling",
            self.fast_refresh_spin,
        )

        layout.addRow(
            "Ending window",
            self.ending_window_spin,
        )

        layout.addRow(
            "Lyrics provider timeout",
            self.lyrics_timeout_spin,
        )

        layout.addRow(
            "Minimum confidence",
            self.confidence_spin,
        )

        return group

    def _build_update_group(
        self,
    ) -> QGroupBox:
        group = QGroupBox(
            "Auto Updates"
        )

        layout = QFormLayout(
            group
        )

        self.check_updates_checkbox = QCheckBox(
            "Check for updates when Spotify+ starts"
        )

        self.update_channel_combo = QComboBox()
        self.update_channel_combo.addItems(
            [
                "stable",
                "beta",
                "nightly",
            ]
        )

        self.check_update_button = QPushButton(
            "Check for Updates"
        )

        note = QLabel(
            "Stable is recommended. Beta and Nightly may "
            "contain unfinished changes."
        )
        note.setObjectName(
            "warningText"
        )
        note.setWordWrap(True)

        layout.addRow(
            self.check_updates_checkbox
        )
        layout.addRow(
            "Update channel",
            self.update_channel_combo,
        )
        layout.addRow(
            "",
            self.check_update_button,
        )
        layout.addRow(note)

        return group

    def _apply_tooltips(self) -> None:
        self.start_engine_checkbox.setToolTip(
            "Automatically start the engine when Spotify+ opens."
        )
        self.minimize_to_tray_checkbox.setToolTip(
            "Keep Spotify+ running in the system tray when the window closes."
        )
        self.notification_checkbox.setToolTip(
            "Show desktop notifications for relevant now-playing events."
        )
        self.diagnostics_checkbox.setToolTip(
            "Enable additional runtime diagnostics."
        )
        self.manage_profiles_button.setToolTip(
            "Add, edit, duplicate, delete, or activate Spotify Developer profiles."
        )
        self.check_update_button.setToolTip(
            "Check GitHub Releases for a newer Spotify+ version."
        )
        self.update_channel_combo.setToolTip(
            "Stable is recommended for normal use."
        )
        self.save_button.setToolTip(
            "Save settings and apply runtime-safe changes immediately."
        )

    # ==========================================================
    # Load / Save
    # ==========================================================

    def load_settings(self) -> None:
        settings.reload()

        preferences = settings.as_dict()

        self.start_engine_checkbox.setChecked(
            bool(
                preferences[
                    "start_engine_on_launch"
                ]
            )
        )

        self.minimize_to_tray_checkbox.setChecked(
            bool(
                preferences[
                    "minimize_to_tray"
                ]
            )
        )

        self.notification_checkbox.setChecked(
            bool(
                preferences[
                    "show_now_playing_notification"
                ]
            )
        )

        self.diagnostics_checkbox.setChecked(
            bool(
                preferences[
                    "diagnostics_enabled"
                ]
            )
        )

        self.diagnostics_interval_spin.setValue(
            float(
                preferences[
                    "diagnostics_interval"
                ]
            )
        )

        self.spotify_refresh_spin.setValue(
            float(
                preferences[
                    "spotify_refresh_rate"
                ]
            )
        )

        self.fast_refresh_spin.setValue(
            float(
                preferences[
                    "spotify_fast_refresh_rate"
                ]
            )
        )

        self.ending_window_spin.setValue(
            float(
                preferences[
                    "spotify_ending_window"
                ]
            )
        )

        self.lyrics_timeout_spin.setValue(
            float(
                preferences[
                    "lyrics_provider_timeout"
                ]
            )
        )

        self.confidence_spin.setValue(
            float(
                preferences[
                    "lyrics_min_confidence"
                ]
            )
        )

        self.active_profile_value.setText(
            settings.get_active_profile()
            or "—"
        )

        self.profile_count_value.setText(
            str(
                len(
                    settings.list_profiles()
                )
            )
        )

        self.discord_client_id_input.setText(
            settings.get_discord_client_id()
        )

        self.check_updates_checkbox.setChecked(
            bool(
                preferences[
                    "check_updates_on_startup"
                ]
            )
        )

        channel_index = (
            self.update_channel_combo.findText(
                str(
                    preferences[
                        "update_channel"
                    ]
                )
            )
        )

        if channel_index >= 0:
            self.update_channel_combo.setCurrentIndex(
                channel_index
            )

    def save_settings(self) -> None:
        try:
            previous_discord_id = (
                settings.get_discord_client_id()
            )

            new_discord_id = (
                self.discord_client_id_input
                .text()
                .strip()
            )

            preferences = {
                "start_engine_on_launch":
                    self.start_engine_checkbox
                    .isChecked(),

                "minimize_to_tray":
                    self.minimize_to_tray_checkbox
                    .isChecked(),

                "show_now_playing_notification":
                    self.notification_checkbox
                    .isChecked(),

                "diagnostics_enabled":
                    self.diagnostics_checkbox
                    .isChecked(),

                "diagnostics_interval":
                    self.diagnostics_interval_spin
                    .value(),

                "spotify_refresh_rate":
                    self.spotify_refresh_spin
                    .value(),

                "spotify_fast_refresh_rate":
                    self.fast_refresh_spin
                    .value(),

                "spotify_ending_window":
                    self.ending_window_spin
                    .value(),

                "lyrics_provider_timeout":
                    self.lyrics_timeout_spin
                    .value(),

                "lyrics_min_confidence":
                    self.confidence_spin
                    .value(),

                "check_updates_on_startup":
                    self.check_updates_checkbox
                    .isChecked(),

                "update_channel":
                    self.update_channel_combo
                    .currentText(),
            }

            settings.update(
                preferences,
                save=False,
            )

            settings.set_discord_client_id(
                new_discord_id
            )

            settings.save()

            logger.info(
                "Application settings saved",
                category="SETTINGS",
                context={
                    "discord_id_changed":
                        discord_id_changed
                        if "discord_id_changed" in locals()
                        else False,
                },
            )

            runtime_result = (
                engine.reload_runtime_settings()
            )

            self.runtime_settings_changed.emit(
                runtime_result
            )

            discord_id_changed = (
                new_discord_id
                != previous_discord_id
            )

            logger.info(
                "Settings applied",
                category="SETTINGS",
                context={
                    "runtime_changes": ", ".join(
                        runtime_result.get(
                            "changed",
                            {},
                        ).keys()
                    ),
                    "restart_required":
                        discord_id_changed,
                },
            )

            changed_runtime = (
                runtime_result.get(
                    "changed",
                    {},
                )
            )

            message_lines = [
                "Settings saved successfully."
            ]

            if changed_runtime:
                message_lines.extend(
                    [
                        "",
                        "Applied immediately:",
                    ]
                )

                for key in changed_runtime:
                    message_lines.append(
                        f"- {key}"
                    )

            if discord_id_changed:
                message_lines.extend(
                    [
                        "",
                        "Restart required for:",
                        "- Discord Application ID",
                    ]
                )

            QMessageBox.information(
                self,
                "Settings Saved",
                "\n".join(
                    message_lines
                ),
            )

            if discord_id_changed:
                self.restart_required.emit(
                    {
                        "reason":
                            "discord_application_changed",

                        "items": [
                            "Discord Application ID",
                        ],
                    }
                )

            self.load_settings()

        except Exception as error:
            QMessageBox.critical(
                self,
                "Settings Error",
                str(error),
            )

    def request_update_check(self) -> None:
        channel = (
            self.update_channel_combo
            .currentText()
            .strip()
            .lower()
        )

        self.check_update_requested.emit(
            channel
        )

    # ==========================================================
    # Profile Manager
    # ==========================================================

    def open_profile_manager(self) -> None:
        if self.profile_manager_window is None:
            from ui.profile_manager_window import (
                ProfileManagerWindow,
            )

            self.profile_manager_window = (
                ProfileManagerWindow()
            )

            self.profile_manager_window.profiles_changed.connect(
                self.on_profiles_changed
            )

            self.profile_manager_window.restart_required.connect(
                self.restart_required.emit
            )

        self.profile_manager_window.show_window()

    def on_profiles_changed(
        self,
        data: dict[str, Any],
    ) -> None:
        self.active_profile_value.setText(
            str(
                data.get(
                    "active_profile",
                    "—",
                )
                or "—"
            )
        )

        profiles = data.get(
            "profiles",
            [],
        )

        self.profile_count_value.setText(
            str(
                len(profiles)
            )
        )

    def show_window(self) -> None:
        self.load_settings()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ==========================================================
    # Theme
    # ==========================================================

    def _apply_styles(self) -> None:
        apply_app_style(
            self
        )