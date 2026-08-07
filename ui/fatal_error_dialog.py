from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
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
from app.restart_manager import (
    restart_application,
)


class FatalErrorDialog(QDialog):
    """
    Fatal error UX untuk mode tanpa console.
    """

    def __init__(
        self,
        *,
        message: str,
        details: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.message = message
        self.details = details

        self.setWindowTitle(
            "Spotify+ Error"
        )

        self.setModal(
            True
        )

        apply_responsive_geometry(
            self,
            preferred_width=760,
            preferred_height=540,
            minimum_width=580,
            minimum_height=420,
        )

        self._build_ui()
        self._apply_styles()

    def _build_ui(self) -> None:
        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            22,
            22,
            22,
            22,
        )

        root.setSpacing(
            14
        )

        title = QLabel(
            "Spotify+ encountered an error"
        )

        title.setObjectName(
            "errorTitle"
        )

        title.setAlignment(
            Qt.AlignmentFlag.AlignLeft
        )

        message_label = QLabel(
            self.message
        )

        message_label.setObjectName(
            "errorMessage"
        )

        message_label.setWordWrap(
            True
        )

        details_title = QLabel(
            "Technical details"
        )

        details_title.setObjectName(
            "sectionTitle"
        )

        self.details_text = QTextEdit()

        self.details_text.setReadOnly(
            True
        )

        self.details_text.setPlainText(
            self.details
            or "No traceback was provided."
        )

        root.addWidget(
            title
        )

        root.addWidget(
            message_label
        )

        root.addWidget(
            details_title
        )

        root.addWidget(
            self.details_text,
            1,
        )

        buttons = QHBoxLayout()

        self.copy_button = QPushButton(
            "Copy Error"
        )

        self.logs_button = QPushButton(
            "Open Logs"
        )

        self.close_button = QPushButton(
            "Close"
        )

        self.restart_button = QPushButton(
            "Restart Spotify+"
        )

        self.restart_button.setObjectName(
            "primaryButton"
        )

        buttons.addWidget(
            self.copy_button
        )

        buttons.addWidget(
            self.logs_button
        )

        buttons.addStretch()

        buttons.addWidget(
            self.close_button
        )

        buttons.addWidget(
            self.restart_button
        )

        root.addLayout(
            buttons
        )

        self.copy_button.clicked.connect(
            self.copy_error
        )

        self.logs_button.clicked.connect(
            self.open_logs
        )

        self.close_button.clicked.connect(
            self.reject
        )

        self.restart_button.clicked.connect(
            self.restart
        )

    def copy_error(self) -> None:
        clipboard = QApplication.clipboard()

        clipboard.setText(
            (
                f"{self.message}\n\n"
                f"{self.details}"
            )
        )

        QMessageBox.information(
            self,
            "Error Copied",
            "Error details copied to clipboard.",
        )

    def open_logs(self) -> None:
        if not logger.open_log_folder():
            QMessageBox.critical(
                self,
                "Log Folder",
                "Could not open the log folder.",
            )

    def restart(self) -> None:
        logger.info(
            "Application restart requested from fatal error dialog",
            category="GUI",
        )

        logger.flush()

        if restart_application():
            self.accept()
            return

        QMessageBox.critical(
            self,
            "Restart Failed",
            "Spotify+ could not start a new process.",
        )

    def _apply_styles(self) -> None:
        apply_app_style(
            self
        )