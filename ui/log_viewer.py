from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.logger import logger


class LogBridge(QObject):
    """
    Mengubah callback logging dari thread mana pun menjadi Qt Signal.
    """

    entry_received = Signal(dict)

    def __init__(self) -> None:
        super().__init__()

        logger.subscribe(
            self._on_log_entry
        )

    def _on_log_entry(
        self,
        entry: dict[str, Any],
    ) -> None:
        self.entry_received.emit(
            entry
        )

    def close(self) -> None:
        logger.unsubscribe(
            self._on_log_entry
        )


class LogViewerWindow(QWidget):
    """
    V2.10.5.1 Log Viewer GUI.

    Fitur:
    - realtime log;
    - filter level;
    - filter category;
    - auto scroll;
    - clear view;
    - copy selected;
    - open log folder.
    """

    MAX_VISIBLE_LINES = 2000

    def __init__(self) -> None:
        super().__init__()

        self.bridge = LogBridge()
        self._entries: list[
            dict[str, Any]
        ] = []

        self.setWindowTitle(
            "Spotify+ Log Viewer"
        )

        self.setMinimumSize(
            820,
            560,
        )

        self.resize(
            980,
            680,
        )

        self._build_ui()
        self._connect_signals()
        self._apply_styles()

        self.reload_entries()

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
            12
        )

        title = QLabel(
            "Log Viewer"
        )

        title.setObjectName(
            "pageTitle"
        )

        subtitle = QLabel(
            "Realtime application logs. "
            "Clearing the view does not delete log files."
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

        filter_row = QHBoxLayout()

        filter_row.setSpacing(
            10
        )

        level_label = QLabel(
            "Level"
        )

        level_label.setObjectName(
            "mutedText"
        )

        self.level_combo = QComboBox()

        self.level_combo.addItems(
            [
                "All",
                "Debug",
                "Info",
                "Warning",
                "Error",
                "Critical",
            ]
        )

        category_label = QLabel(
            "Category"
        )

        category_label.setObjectName(
            "mutedText"
        )

        self.category_combo = QComboBox()

        self.category_combo.addItems(
            [
                "All",
                "App",
                "Engine",
                "Spotify",
                "Lyrics",
                "RPC",
                "Cache",
                "Profile",
                "Settings",
                "Updater",
                "GUI",
                "System",
            ]
        )

        self.auto_scroll_checkbox = QCheckBox(
            "Auto Scroll"
        )

        self.auto_scroll_checkbox.setChecked(
            True
        )

        filter_row.addWidget(
            level_label
        )

        filter_row.addWidget(
            self.level_combo
        )

        filter_row.addWidget(
            category_label
        )

        filter_row.addWidget(
            self.category_combo
        )

        filter_row.addStretch()

        filter_row.addWidget(
            self.auto_scroll_checkbox
        )

        root.addLayout(
            filter_row
        )

        self.log_text = QTextEdit()

        self.log_text.setReadOnly(
            True
        )

        self.log_text.setLineWrapMode(
            QTextEdit.LineWrapMode.NoWrap
        )

        self.log_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )

        root.addWidget(
            self.log_text,
            1,
        )

        status_row = QHBoxLayout()

        self.status_label = QLabel(
            "0 entries"
        )

        self.status_label.setObjectName(
            "mutedText"
        )

        status_row.addWidget(
            self.status_label
        )

        status_row.addStretch()

        root.addLayout(
            status_row
        )

        button_row = QHBoxLayout()

        self.reload_button = QPushButton(
            "Reload"
        )

        self.clear_button = QPushButton(
            "Clear View"
        )

        self.copy_button = QPushButton(
            "Copy Selected"
        )

        self.folder_button = QPushButton(
            "Open Log Folder"
        )

        self.close_button = QPushButton(
            "Close"
        )

        self.folder_button.setObjectName(
            "primaryButton"
        )

        button_row.addWidget(
            self.reload_button
        )

        button_row.addWidget(
            self.clear_button
        )

        button_row.addWidget(
            self.copy_button
        )

        button_row.addStretch()

        button_row.addWidget(
            self.folder_button
        )

        button_row.addWidget(
            self.close_button
        )

        root.addLayout(
            button_row
        )

    def _connect_signals(self) -> None:
        self.level_combo.currentTextChanged.connect(
            self.apply_filters
        )

        self.category_combo.currentTextChanged.connect(
            self.apply_filters
        )

        self.reload_button.clicked.connect(
            self.reload_entries
        )

        self.clear_button.clicked.connect(
            self.clear_view
        )

        self.copy_button.clicked.connect(
            self.copy_selected
        )

        self.folder_button.clicked.connect(
            self.open_log_folder
        )

        self.close_button.clicked.connect(
            self.hide
        )

        self.bridge.entry_received.connect(
            self.on_entry_received
        )

    # ==========================================================
    # Entry Handling
    # ==========================================================

    def reload_entries(self) -> None:
        self._entries = logger.get_entries(
            limit=self.MAX_VISIBLE_LINES
        )

        self.apply_filters()

    def on_entry_received(
        self,
        entry: dict[str, Any],
    ) -> None:
        self._entries.append(
            entry
        )

        if (
            len(self._entries)
            > self.MAX_VISIBLE_LINES
        ):
            self._entries = self._entries[
                -self.MAX_VISIBLE_LINES:
            ]

        if self._matches_filters(
            entry
        ):
            self._append_entry(
                entry
            )

        self._update_status()

    def apply_filters(self) -> None:
        filtered = [
            entry
            for entry in self._entries
            if self._matches_filters(
                entry
            )
        ]

        self.log_text.clear()

        for entry in filtered:
            self.log_text.append(
                self._format_entry(
                    entry
                )
            )

        self._update_status(
            visible_count=len(
                filtered
            )
        )

        if (
            self.auto_scroll_checkbox
            .isChecked()
        ):
            self._scroll_to_bottom()

    def _matches_filters(
        self,
        entry: dict[str, Any],
    ) -> bool:
        selected_level = (
            self.level_combo
            .currentText()
            .strip()
            .upper()
        )

        selected_category = (
            self.category_combo
            .currentText()
            .strip()
            .upper()
        )

        if (
            selected_level != "ALL"
            and entry.get(
                "level"
            ) != selected_level
        ):
            return False

        if (
            selected_category != "ALL"
            and entry.get(
                "category"
            ) != selected_category
        ):
            return False

        return True

    def _append_entry(
        self,
        entry: dict[str, Any],
    ) -> None:
        self.log_text.append(
            self._format_entry(
                entry
            )
        )

        if (
            self.auto_scroll_checkbox
            .isChecked()
        ):
            self._scroll_to_bottom()

    @staticmethod
    def _format_entry(
        entry: dict[str, Any],
    ) -> str:
        time_text = str(
            entry.get(
                "time",
                "--:--:--",
            )
        )

        level = str(
            entry.get(
                "level",
                "INFO",
            )
        )

        category = str(
            entry.get(
                "category",
                "APP",
            )
        )

        message = str(
            entry.get(
                "message",
                "",
            )
        )

        context = entry.get(
            "context"
        )

        line = (
            f"{time_text}  "
            f"{level:<8} "
            f"{category:<9} "
            f"{message}"
        )

        if context:
            context_text = ", ".join(
                f"{key}={value}"
                for key, value
                in context.items()
            )

            line += (
                f"  |  {context_text}"
            )

        return line

    def _scroll_to_bottom(self) -> None:
        cursor = self.log_text.textCursor()

        cursor.movePosition(
            QTextCursor.MoveOperation.End
        )

        self.log_text.setTextCursor(
            cursor
        )

        self.log_text.ensureCursorVisible()

    def _update_status(
        self,
        *,
        visible_count: int | None = None,
    ) -> None:
        if visible_count is None:
            visible_count = sum(
                1
                for entry in self._entries
                if self._matches_filters(
                    entry
                )
            )

        self.status_label.setText(
            (
                f"{visible_count} visible / "
                f"{len(self._entries)} buffered"
            )
        )

    # ==========================================================
    # Actions
    # ==========================================================

    def clear_view(self) -> None:
        self._entries.clear()
        logger.clear_buffer()

        self.log_text.clear()
        self._update_status(
            visible_count=0
        )

    def copy_selected(self) -> None:
        selected_text = (
            self.log_text
            .textCursor()
            .selectedText()
        )

        if not selected_text:
            QMessageBox.information(
                self,
                "Copy Selected",
                "Select log text first.",
            )

            return

        clipboard = (
            QApplication.clipboard()
        )

        clipboard.setText(
            selected_text
        )

    def open_log_folder(self) -> None:
        if not logger.open_log_folder():
            QMessageBox.critical(
                self,
                "Log Folder",
                "Could not open the log folder.",
            )

    def show_window(self) -> None:
        self.reload_entries()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """
        Hide window instead of destroying the bridge.
        """

        event.ignore()
        self.hide()

    # ==========================================================
    # Theme
    # ==========================================================

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background-color: #121212;
                color: #F5F5F5;
                font-family: "Segoe UI";
                font-size: 13px;
            }

            QLabel#pageTitle {
                font-size: 24px;
                font-weight: 700;
            }

            QLabel#mutedText {
                color: #A7A7A7;
            }

            QTextEdit {
                background-color: #0D0D0D;
                color: #EAEAEA;
                border: 1px solid #303030;
                border-radius: 10px;
                padding: 10px;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 12px;
                selection-background-color: #1ED760;
                selection-color: #081C0F;
            }

            QComboBox {
                min-height: 34px;
                padding: 0 10px;
                background-color: #292929;
                border: 1px solid #404040;
                border-radius: 8px;
            }

            QCheckBox {
                spacing: 8px;
            }

            QPushButton {
                min-height: 38px;
                padding: 0 15px;
                border-radius: 9px;
                background-color: #2A2A2A;
                border: 1px solid #444444;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #353535;
            }

            QPushButton#primaryButton {
                color: #081C0F;
                background-color: #1ED760;
                border: none;
            }

            QPushButton#primaryButton:hover {
                background-color: #2BE06B;
            }
            """
        )