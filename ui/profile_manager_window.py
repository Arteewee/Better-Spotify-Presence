from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ui.styles import (
    apply_app_style,
    apply_responsive_geometry,
)
from app.settings_manager import settings


class AddProfileDialog(QDialog):

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle(
            "Add Spotify Profile"
        )

        self.setMinimumWidth(
            500
        )

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.client_id_input = QLineEdit()
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        self.redirect_uri_input = QLineEdit(
            "http://127.0.0.1:8888/callback"
        )

        self.show_secret = QCheckBox(
            "Show Client Secret"
        )

        self.make_active = QCheckBox(
            "Set as active profile"
        )

        self.show_secret.toggled.connect(
            self._toggle_secret
        )

        form.addRow(
            "Profile name",
            self.name_input,
        )

        form.addRow(
            "Client ID",
            self.client_id_input,
        )

        form.addRow(
            "Client Secret",
            self.client_secret_input,
        )

        form.addRow(
            "",
            self.show_secret,
        )

        form.addRow(
            "Redirect URI",
            self.redirect_uri_input,
        )

        form.addRow(
            "",
            self.make_active,
        )

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(
            self.accept
        )

        buttons.rejected.connect(
            self.reject
        )

        layout.addWidget(buttons)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #121212;
            }

            QWidget {
                color: #F5F5F5;
                font-family: "Segoe UI";
                font-size: 13px;
            }

            QLineEdit {
                min-height: 34px;
                padding: 0 10px;
                background-color: #292929;
                border: 1px solid #404040;
                border-radius: 8px;
            }

            QLineEdit:focus {
                border-color: #1ED760;
            }

            QPushButton {
                min-height: 36px;
                padding: 0 15px;
                border-radius: 8px;
                background-color: #2A2A2A;
                border: 1px solid #444444;
            }
            """
        )

    def _toggle_secret(
        self,
        visible: bool,
    ) -> None:
        self.client_secret_input.setEchoMode(
            (
                QLineEdit.EchoMode.Normal
                if visible
                else QLineEdit.EchoMode.Password
            )
        )

    def values(self) -> dict[str, Any]:
        return {
            "name":
                self.name_input.text().strip(),

            "client_id":
                self.client_id_input.text().strip(),

            "client_secret":
                self.client_secret_input.text().strip(),

            "redirect_uri":
                self.redirect_uri_input.text().strip(),

            "make_active":
                self.make_active.isChecked(),
        }


class ProfileManagerWindow(QWidget):
    """
    Unlimited Spotify Profile Manager GUI.
    """

    profiles_changed = Signal(dict)
    restart_required = Signal(dict)

    def __init__(self) -> None:
        super().__init__()

        self._selected_profile = ""

        self.setWindowTitle(
            "Spotify+ Profile Manager"
        )

        apply_responsive_geometry(
            self,
            preferred_width=920,
            preferred_height=700,
            minimum_width=700,
            minimum_height=560,
        )

        self._build_ui()
        self._connect_signals()
        self._apply_styles()
        self.reload_profiles()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        root.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        title = QLabel(
            "Spotify Profiles"
        )

        title.setObjectName(
            "pageTitle"
        )

        subtitle = QLabel(
            "Add, rename, duplicate, delete, and activate "
            "Spotify Developer profiles."
        )

        subtitle.setObjectName(
            "mutedText"
        )

        root.addWidget(title)
        root.addWidget(subtitle)

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        left = QWidget()
        left_layout = QVBoxLayout(left)

        left_title = QLabel(
            "AVAILABLE PROFILES"
        )

        left_title.setObjectName(
            "sectionTitle"
        )

        self.profile_list = QListWidget()

        left_layout.addWidget(left_title)
        left_layout.addWidget(
            self.profile_list,
            1,
        )

        first_row = QHBoxLayout()

        self.add_button = QPushButton(
            "Add"
        )

        self.rename_button = QPushButton(
            "Rename"
        )

        first_row.addWidget(
            self.add_button
        )

        first_row.addWidget(
            self.rename_button
        )

        second_row = QHBoxLayout()

        self.duplicate_button = QPushButton(
            "Duplicate"
        )

        self.delete_button = QPushButton(
            "Delete"
        )

        self.delete_button.setObjectName(
            "dangerButton"
        )

        second_row.addWidget(
            self.duplicate_button
        )

        second_row.addWidget(
            self.delete_button
        )

        left_layout.addLayout(first_row)
        left_layout.addLayout(second_row)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        detail_title = QLabel(
            "PROFILE DETAILS"
        )

        detail_title.setObjectName(
            "sectionTitle"
        )

        self.profile_name = QLabel(
            "—"
        )

        self.profile_name.setObjectName(
            "profileName"
        )

        self.active_badge = QLabel(
            "Not Active"
        )

        self.active_badge.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        form = QFormLayout()

        self.client_id_input = QLineEdit()
        self.client_secret_input = QLineEdit()

        self.client_secret_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        self.redirect_uri_input = QLineEdit()

        self.show_secret = QCheckBox(
            "Show Client Secret"
        )

        self.show_secret.toggled.connect(
            self._toggle_secret
        )

        form.addRow(
            "Client ID",
            self.client_id_input,
        )

        form.addRow(
            "Client Secret",
            self.client_secret_input,
        )

        form.addRow(
            "",
            self.show_secret,
        )

        form.addRow(
            "Redirect URI",
            self.redirect_uri_input,
        )

        action_row = QHBoxLayout()

        self.save_button = QPushButton(
            "Save Profile"
        )

        self.save_button.setObjectName(
            "primaryButton"
        )

        self.active_button = QPushButton(
            "Set Active"
        )

        action_row.addWidget(
            self.save_button
        )

        action_row.addWidget(
            self.active_button
        )

        note = QLabel(
            "Credential changes and active-profile changes "
            "require restarting Spotify+."
        )

        note.setObjectName(
            "warningText"
        )

        note.setWordWrap(True)

        right_layout.addWidget(
            detail_title
        )

        right_layout.addWidget(
            self.profile_name
        )

        right_layout.addWidget(
            self.active_badge
        )

        right_layout.addSpacing(10)
        right_layout.addLayout(form)
        right_layout.addLayout(action_row)
        right_layout.addWidget(note)
        right_layout.addStretch()

        splitter.addWidget(left)
        splitter.addWidget(right)

        splitter.setStretchFactor(
            0,
            2,
        )

        splitter.setStretchFactor(
            1,
            3,
        )

        root.addWidget(
            splitter,
            1,
        )

        close_row = QHBoxLayout()
        close_row.addStretch()

        self.close_button = QPushButton(
            "Close"
        )

        close_row.addWidget(
            self.close_button
        )

        root.addLayout(close_row)

    def _connect_signals(self) -> None:
        self.profile_list.currentItemChanged.connect(
            self._selection_changed
        )

        self.add_button.clicked.connect(
            self.add_profile
        )

        self.rename_button.clicked.connect(
            self.rename_profile
        )

        self.duplicate_button.clicked.connect(
            self.duplicate_profile
        )

        self.delete_button.clicked.connect(
            self.delete_profile
        )

        self.save_button.clicked.connect(
            self.save_profile
        )

        self.active_button.clicked.connect(
            self.set_active_profile
        )

        self.close_button.clicked.connect(
            self.hide
        )

    def reload_profiles(
        self,
        preferred: str = "",
    ) -> None:
        names = settings.list_profiles()
        active = settings.get_active_profile()

        selected = (
            preferred
            or self._selected_profile
            or active
        )

        self.profile_list.blockSignals(
            True
        )

        self.profile_list.clear()

        selected_item = None

        for name in names:
            display = (
                f"✓ {name}"
                if name == active
                else name
            )

            item = QListWidgetItem(
                display
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                name,
            )

            self.profile_list.addItem(
                item
            )

            if name == selected:
                selected_item = item

        self.profile_list.blockSignals(
            False
        )

        if selected_item is None:
            selected_item = (
                self.profile_list.item(0)
                if self.profile_list.count()
                else None
            )

        if selected_item is not None:
            self.profile_list.setCurrentItem(
                selected_item
            )

            self._load_profile(
                str(
                    selected_item.data(
                        Qt.ItemDataRole.UserRole
                    )
                )
            )
        else:
            self._clear_form()

        self.delete_button.setEnabled(
            len(names) > 1
        )

        self._emit_profiles_changed()

    def _selection_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        del previous

        if current is None:
            self._clear_form()
            return

        self._load_profile(
            str(
                current.data(
                    Qt.ItemDataRole.UserRole
                )
            )
        )

    def _load_profile(
        self,
        profile_name: str,
    ) -> None:
        profile = settings.get_profile(
            profile_name
        )

        self._selected_profile = profile_name

        self.profile_name.setText(
            profile_name
        )

        self.client_id_input.setText(
            profile.get(
                "client_id",
                "",
            )
        )

        self.client_secret_input.setText(
            profile.get(
                "client_secret",
                "",
            )
        )

        self.redirect_uri_input.setText(
            profile.get(
                "redirect_uri",
                "",
            )
        )

        is_active = (
            profile_name
            == settings.get_active_profile()
        )

        self.active_badge.setText(
            (
                "Active Profile"
                if is_active
                else "Not Active"
            )
        )

        self.active_badge.setProperty(
            "active",
            (
                "true"
                if is_active
                else "false"
            ),
        )

        self.active_badge.style().unpolish(
            self.active_badge
        )

        self.active_badge.style().polish(
            self.active_badge
        )

        self.active_button.setEnabled(
            not is_active
        )

        self.rename_button.setEnabled(True)
        self.duplicate_button.setEnabled(True)
        self.save_button.setEnabled(True)

    def _clear_form(self) -> None:
        self._selected_profile = ""

        self.profile_name.setText("—")
        self.client_id_input.clear()
        self.client_secret_input.clear()
        self.redirect_uri_input.clear()

        self.rename_button.setEnabled(False)
        self.duplicate_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.active_button.setEnabled(False)

    def add_profile(self) -> None:
        dialog = AddProfileDialog(self)

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        values = dialog.values()

        try:
            profile = settings.add_profile(
                values["name"],
                client_id=values["client_id"],
                client_secret=values[
                    "client_secret"
                ],
                redirect_uri=values[
                    "redirect_uri"
                ],
                make_active=values[
                    "make_active"
                ],
            )

            self.reload_profiles(
                profile["name"]
            )

            if values["make_active"]:
                self._emit_restart(
                    "active_profile_changed",
                    profile["name"],
                )

            QMessageBox.information(
                self,
                "Profile Created",
                (
                    f"Profile '{profile['name']}' created."
                    + (
                        "\n\nRestart Spotify+ to use it."
                        if values["make_active"]
                        else ""
                    )
                ),
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Profile Error",
                str(error),
            )

    def rename_profile(self) -> None:
        if not self._selected_profile:
            return

        old_name = self._selected_profile

        new_name, accepted = (
            QInputDialog.getText(
                self,
                "Rename Profile",
                "New profile name",
                text=old_name,
            )
        )

        if not accepted:
            return

        try:
            was_active = (
                old_name
                == settings.get_active_profile()
            )

            settings.rename_profile(
                old_name,
                new_name,
            )

            clean_name = new_name.strip()

            self.reload_profiles(
                clean_name
            )

            if was_active:
                self._emit_restart(
                    "active_profile_renamed",
                    clean_name,
                )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Rename Error",
                str(error),
            )

    def duplicate_profile(self) -> None:
        if not self._selected_profile:
            return

        new_name, accepted = (
            QInputDialog.getText(
                self,
                "Duplicate Profile",
                "New profile name",
                text=(
                    f"{self._selected_profile} Copy"
                ),
            )
        )

        if not accepted:
            return

        try:
            profile = settings.duplicate_profile(
                self._selected_profile,
                new_name,
            )

            self.reload_profiles(
                profile["name"]
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Duplicate Error",
                str(error),
            )

    def delete_profile(self) -> None:
        if not self._selected_profile:
            return

        selected = self._selected_profile
        was_active = (
            selected
            == settings.get_active_profile()
        )

        answer = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete profile '{selected}'?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            settings.delete_profile(
                selected
            )

            self._selected_profile = ""
            self.reload_profiles()

            if was_active:
                self._emit_restart(
                    "active_profile_deleted",
                    settings.get_active_profile(),
                )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Delete Error",
                str(error),
            )

    def save_profile(self) -> None:
        if not self._selected_profile:
            return

        try:
            settings.save_profile(
                self._selected_profile,
                client_id=(
                    self.client_id_input.text()
                ),
                client_secret=(
                    self.client_secret_input.text()
                ),
                redirect_uri=(
                    self.redirect_uri_input.text()
                ),
            )

            self._emit_profiles_changed()

            self._emit_restart(
                "profile_credentials_changed",
                self._selected_profile,
            )

            QMessageBox.information(
                self,
                "Profile Saved",
                (
                    "Profile credentials saved.\n\n"
                    "Restart Spotify+ to apply them."
                ),
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Save Error",
                str(error),
            )

    def set_active_profile(self) -> None:
        if not self._selected_profile:
            return

        try:
            changed = settings.set_active_profile(
                self._selected_profile
            )

            self.reload_profiles(
                self._selected_profile
            )

            if changed:
                self._emit_restart(
                    "active_profile_changed",
                    self._selected_profile,
                )

                QMessageBox.information(
                    self,
                    "Active Profile Changed",
                    (
                        f"'{self._selected_profile}' is active.\n\n"
                        "Restart Spotify+ to apply it."
                    ),
                )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Profile Error",
                str(error),
            )

    def _emit_profiles_changed(self) -> None:
        self.profiles_changed.emit(
            {
                "profiles":
                    settings.list_profiles(),

                "active_profile":
                    settings.get_active_profile(),
            }
        )

    def _emit_restart(
        self,
        reason: str,
        profile_name: str,
    ) -> None:
        self.restart_required.emit(
            {
                "reason": reason,
                "profile": profile_name,
            }
        )

    def _toggle_secret(
        self,
        visible: bool,
    ) -> None:
        self.client_secret_input.setEchoMode(
            (
                QLineEdit.EchoMode.Normal
                if visible
                else QLineEdit.EchoMode.Password
            )
        )

    def _apply_tooltips(self) -> None:
        self.add_button.setToolTip(
            "Create a new Spotify Developer profile."
        )
        self.rename_button.setToolTip(
            "Rename the selected profile."
        )
        self.duplicate_button.setToolTip(
            "Create a copy of the selected profile."
        )
        self.delete_button.setToolTip(
            "Delete the selected profile."
        )
        self.save_button.setToolTip(
            "Save Client ID, Client Secret, and Redirect URI."
        )
        self.set_active_button.setToolTip(
            "Use this profile after Spotify+ restarts."
        )

    def show_window(self) -> None:
        self.reload_profiles()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _apply_styles(self) -> None:
        apply_app_style(
            self
        )