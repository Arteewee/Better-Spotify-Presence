from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCloseEvent,
    QFont,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QFrame,
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

from ui.styles import (
    apply_app_style,
    apply_responsive_geometry,
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

        apply_responsive_geometry(
            self,
            preferred_width=980,
            preferred_height=680,
            minimum_width=700,
            minimum_height=540,
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
            12
        )

        level_label = QLabel(
            "Level"
        )

        level_label.setObjectName(
            "mutedText"
        )

        level_label.setContentsMargins(
            0,
            0,
            2,
            0,
        )

        self.level_combo = QComboBox()

        self.level_combo.setObjectName(
            "logFilterCombo"
        )

        self.level_combo.setMinimumWidth(
            118
        )

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

        category_label.setContentsMargins(
            6,
            0,
            2,
            0,
        )

        self.category_combo = QComboBox()

        self.category_combo.setObjectName(
            "logFilterCombo"
        )

        self.category_combo.setMinimumWidth(
            138
        )

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

        level_frame = QFrame()
        level_frame.setObjectName(
            "logFilterFrame"
        )

        level_frame_layout = QHBoxLayout(
            level_frame
        )
        level_frame_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        level_frame_layout.setSpacing(
            0
        )
        level_frame_layout.addWidget(
            self.level_combo
        )

        filter_row.addWidget(
            level_frame
        )

        filter_row.addWidget(
            category_label
        )

        category_frame = QFrame()
        category_frame.setObjectName(
            "logFilterFrame"
        )

        category_frame_layout = QHBoxLayout(
            category_frame
        )
        category_frame_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        category_frame_layout.setSpacing(
            0
        )
        category_frame_layout.addWidget(
            self.category_combo
        )

        filter_row.addWidget(
            category_frame
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
            self._append_colored_entry(
                entry
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
        self._append_colored_entry(
            entry
        )

        if (
            self.auto_scroll_checkbox
            .isChecked()
        ):
            self._scroll_to_bottom()

    def _append_colored_entry(
        self,
        entry: dict[str, Any],
    ) -> None:
        """
        Render a log line using QTextCharFormat so severity levels
        remain easy to scan without converting the whole viewer to HTML.
        """

        cursor = self.log_text.textCursor()

        cursor.movePosition(
            QTextCursor.MoveOperation.End
        )

        # Add a newline between entries, but not before the first one.
        if not self.log_text.document().isEmpty():
            cursor.insertText(
                "\n"
            )

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
        ).upper()

        category = str(
            entry.get(
                "category",
                "APP",
            )
        ).upper()

        message = str(
            entry.get(
                "message",
                "",
            )
        )

        context = entry.get(
            "context"
        )

        default_format = QTextCharFormat()
        default_format.setForeground(
            QColor(
                "#EAEAEA"
            )
        )

        muted_format = QTextCharFormat()
        muted_format.setForeground(
            QColor(
                "#A7A7A7"
            )
        )

        level_format = QTextCharFormat()
        level_format.setFontWeight(
            QFont.Weight.DemiBold
        )

        level_colors = {
            "DEBUG": "#8AB4F8",
            "INFO": "#1ED760",
            "WARNING": "#F5C542",
            "ERROR": "#FF6B6B",
            "CRITICAL": "#FF4D9D",
        }

        level_format.setForeground(
            QColor(
                level_colors.get(
                    level,
                    "#EAEAEA",
                )
            )
        )

        category_format = QTextCharFormat()
        category_format.setForeground(
            QColor(
                "#B7C9E2"
            )
        )
        category_format.setFontWeight(
            QFont.Weight.Medium
        )

        cursor.insertText(
            f"{time_text}  ",
            muted_format,
        )

        cursor.insertText(
            f"{level:<8} ",
            level_format,
        )

        cursor.insertText(
            f"{category:<9} ",
            category_format,
        )

        cursor.insertText(
            message,
            default_format,
        )

        if context:
            context_text = ", ".join(
                f"{key}={value}"
                for key, value
                in context.items()
            )

            cursor.insertText(
                f"  |  {context_text}",
                muted_format,
            )

        self.log_text.setTextCursor(
            cursor
        )

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
        apply_app_style(
            self
        )