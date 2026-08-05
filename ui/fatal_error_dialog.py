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

        self.setMinimumSize(
            680,
            460,
        )

        self.resize(
            760,
            540,
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

            QLabel#errorTitle {
                color: #FFFFFF;
                font-size: 23px;
                font-weight: 700;
            }

            QLabel#errorMessage {
                color: #E6A6A6;
                font-size: 14px;
            }

            QLabel#sectionTitle {
                color: #E05252;
                font-size: 11px;
                font-weight: 700;
            }

            QTextEdit {
                background-color: #0D0D0D;
                color: #EAEAEA;
                border: 1px solid #5A3030;
                border-radius: 10px;
                padding: 10px;
                font-family: "Cascadia Mono", "Consolas";
                font-size: 12px;
            }

            QPushButton {
                min-height: 38px;
                padding: 0 16px;
                border-radius: 9px;
                background-color: #2A2A2A;
                border: 1px solid #444444;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #353535;
            }

            QPushButton#primaryButton {
                color: #FFFFFF;
                background-color: #B73535;
                border: none;
            }

            QPushButton#primaryButton:hover {
                background-color: #C74343;
            }
            """
        )