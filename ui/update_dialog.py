import webbrowser
from typing import Any

from PySide6.QtCore import (
    QObject,
    QThread,
    Signal,
)
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.styles import (
    apply_app_style,
    apply_responsive_geometry,
)
from app.update_manager import (
    UpdateCheckError,
    UpdateDownloadError,
    update_manager,
)
from app.update_models import (
    UpdateCheckResult,
)


class UpdateCheckWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        channel: str,
    ) -> None:
        super().__init__()
        self.channel = channel

    def run(self) -> None:
        try:
            result = (
                update_manager
                .check_for_updates(
                    channel=self.channel
                )
            )
            self.finished.emit(
                result
            )

        except UpdateCheckError as error:
            self.failed.emit(
                str(error)
            )

        except Exception as error:
            self.failed.emit(
                str(error)
            )


class UpdateDownloadWorker(QObject):
    progress = Signal(dict)
    completed = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        result: UpdateCheckResult,
    ) -> None:
        super().__init__()

        import threading

        self.result = result
        self.cancel_event = (
            threading.Event()
        )

    def run(self) -> None:
        try:
            path = (
                update_manager
                .download_update(
                    self.result,
                    progress_callback=(
                        self.progress.emit
                    ),
                    cancel_event=(
                        self.cancel_event
                    ),
                )
            )

            self.completed.emit(
                str(path)
            )

        except UpdateDownloadError as error:
            if (
                self.cancel_event.is_set()
                or "cancelled"
                in str(error).lower()
            ):
                self.cancelled.emit()
            else:
                self.failed.emit(
                    str(error)
                )

        except Exception as error:
            self.failed.emit(
                str(error)
            )

    def cancel(self) -> None:
        self.cancel_event.set()


class UpdateAvailableDialog(QDialog):
    """
    Displays update metadata and release notes.

    Download/install is intentionally added in V2.11.3+.
    """

    def __init__(
        self,
        result: UpdateCheckResult,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.result = result
        self._download_thread: QThread | None = None
        self._download_worker: UpdateDownloadWorker | None = None
        self._downloaded_path: str | None = None

        self.setWindowTitle(
            "Spotify+ Update Available"
        )
        apply_responsive_geometry(
            self,
            preferred_width=700,
            preferred_height=560,
            minimum_width=580,
            minimum_height=440,
        )

        self._build_ui()
        self._apply_styles()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            22,
            22,
            22,
            22,
        )
        root.setSpacing(14)

        title = QLabel(
            "A new Spotify+ version is available"
        )
        title.setObjectName(
            "pageTitle"
        )

        version_text = QLabel(
            f"Current: {self.result.current_version}    "
            f"Latest: {self.result.latest_version}"
        )
        version_text.setObjectName(
            "versionText"
        )

        channel_text = QLabel(
            f"Channel: {self.result.channel.title()}"
        )
        channel_text.setObjectName(
            "mutedText"
        )

        if self.result.mandatory:
            requirement = QLabel(
                "This update is required because the current "
                "version is no longer supported."
            )
            requirement.setObjectName(
                "warningText"
            )
            requirement.setWordWrap(True)
            root.addWidget(requirement)

        notes_title = QLabel(
            "RELEASE NOTES"
        )
        notes_title.setObjectName(
            "sectionTitle"
        )

        notes = QTextEdit()
        notes.setReadOnly(True)

        release_notes = (
            self.result.manifest.release_notes
        )

        if release_notes:
            notes.setPlainText(
                "\n".join(
                    f"• {note}"
                    for note in release_notes
                )
            )
        else:
            notes.setPlainText(
                "No release notes were provided."
            )

        root.addWidget(title)
        root.addWidget(version_text)
        root.addWidget(channel_text)
        root.addWidget(notes_title)
        root.addWidget(notes, 1)

        self.download_status = QLabel(
            "Ready to download"
        )
        self.download_status.setObjectName(
            "mutedText"
        )

        self.download_progress = QProgressBar()
        self.download_progress.setRange(
            0,
            1000,
        )
        self.download_progress.setValue(
            0
        )
        self.download_progress.setTextVisible(
            False
        )

        self.download_details = QLabel(
            ""
        )
        self.download_details.setObjectName(
            "mutedText"
        )

        root.addWidget(
            self.download_status
        )
        root.addWidget(
            self.download_progress
        )
        root.addWidget(
            self.download_details
        )

        buttons = QHBoxLayout()

        self.release_button = QPushButton(
            "View GitHub Release"
        )
        self.later_button = QPushButton(
            "Later"
        )
        self.download_button = QPushButton(
            "Download Update"
        )
        self.download_button.setObjectName(
            "primaryButton"
        )

        self.cancel_button = QPushButton(
            "Cancel Download"
        )
        self.cancel_button.setEnabled(
            False
        )

        self.install_button = QPushButton(
            "Install and Restart"
        )
        self.install_button.setObjectName(
            "primaryButton"
        )
        self.install_button.setEnabled(
            False
        )

        buttons.addWidget(
            self.release_button
        )
        buttons.addStretch()
        buttons.addWidget(
            self.later_button
        )
        buttons.addWidget(
            self.cancel_button
        )
        buttons.addWidget(
            self.download_button
        )
        buttons.addWidget(
            self.install_button
        )

        root.addLayout(buttons)

        self.release_button.clicked.connect(
            self.open_release
        )
        self.later_button.clicked.connect(
            self.reject
        )
        self.download_button.clicked.connect(
            self.start_download
        )
        self.cancel_button.clicked.connect(
            self.cancel_download
        )
        self.install_button.clicked.connect(
            self.install_update
        )

        self.release_button.setToolTip(
            "Open this release on GitHub."
        )
        self.download_button.setToolTip(
            "Download and verify the update package in the background."
        )
        self.cancel_button.setToolTip(
            "Cancel the current update download."
        )
        self.install_button.setToolTip(
            "Back up the current installation, apply the update, and restart."
        )

    def start_download(self) -> None:
        if (
            self._download_thread is not None
            and self._download_thread.isRunning()
        ):
            return

        thread = QThread()
        worker = UpdateDownloadWorker(
            self.result
        )
        worker.moveToThread(
            thread
        )

        thread.started.connect(
            worker.run
        )
        worker.progress.connect(
            self.on_download_progress
        )
        worker.completed.connect(
            self.on_download_completed
        )
        worker.failed.connect(
            self.on_download_failed
        )
        worker.cancelled.connect(
            self.on_download_cancelled
        )

        worker.completed.connect(
            thread.quit
        )
        worker.failed.connect(
            thread.quit
        )
        worker.cancelled.connect(
            thread.quit
        )

        thread.finished.connect(
            worker.deleteLater
        )
        thread.finished.connect(
            self._cleanup_download
        )
        thread.finished.connect(
            thread.deleteLater
        )

        self._download_thread = thread
        self._download_worker = worker

        self.download_button.setEnabled(
            False
        )
        self.cancel_button.setEnabled(
            True
        )
        self.later_button.setEnabled(
            False
        )
        self.release_button.setEnabled(
            False
        )

        self.download_status.setText(
            "Downloading update..."
        )
        self.download_details.setText(
            ""
        )
        self.download_progress.setValue(
            0
        )

        thread.start()

    def cancel_download(self) -> None:
        if self._download_worker is None:
            return

        self.cancel_button.setEnabled(
            False
        )
        self.download_status.setText(
            "Cancelling download..."
        )
        self._download_worker.cancel()

    def on_download_progress(
        self,
        progress: dict[str, Any],
    ) -> None:
        percent = float(
            progress.get(
                "percent",
                0.0,
            )
            or 0.0
        )

        downloaded = int(
            progress.get(
                "downloaded_bytes",
                0,
            )
            or 0
        )

        total = int(
            progress.get(
                "total_bytes",
                0,
            )
            or 0
        )

        speed = float(
            progress.get(
                "speed_bytes",
                0.0,
            )
            or 0.0
        )

        self.download_progress.setValue(
            int(
                max(
                    0.0,
                    min(
                        percent,
                        100.0,
                    ),
                )
                * 10
            )
        )

        total_text = (
            self.format_bytes(total)
            if total > 0
            else "Unknown"
        )

        self.download_details.setText(
            (
                f"{self.format_bytes(downloaded)} / "
                f"{total_text}    "
                f"{self.format_bytes(speed)}/s"
            )
        )

    def on_download_completed(
        self,
        path: str,
    ) -> None:
        self._downloaded_path = path

        self.download_progress.setValue(
            1000
        )
        self.download_status.setText(
            "Ready to install — SHA-256 verified"
        )
        self.download_details.setText(
            path
        )

        QMessageBox.information(
            self,
            "Update Downloaded",
            (
                "The update package was downloaded and "
                "verified successfully.\\n\\n"
                "Automatic installation will be added in "
                "the next updater stage."
            ),
        )

    def on_download_failed(
        self,
        message: str,
    ) -> None:
        self._downloaded_path = None
        self.install_button.setEnabled(
            False
        )

        self.download_status.setText(
            "Download failed"
        )

        QMessageBox.critical(
            self,
            "Update Download Failed",
            message,
        )

    def on_download_cancelled(self) -> None:
        self._downloaded_path = None
        self.install_button.setEnabled(
            False
        )

        self.download_status.setText(
            "Download cancelled"
        )
        self.download_progress.setValue(
            0
        )
        self.download_details.setText(
            ""
        )

    def install_update(self) -> None:
        if not self._downloaded_path:
            return

        answer = QMessageBox.question(
            self,
            "Install Update",
            (
                "Spotify+ will close, install the update, "
                "and restart automatically.\\n\\n"
                "Continue?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return

        self.install_button.setEnabled(
            False
        )
        self.download_button.setEnabled(
            False
        )
        self.later_button.setEnabled(
            False
        )
        self.release_button.setEnabled(
            False
        )
        self.download_status.setText(
            "Preparing installation..."
        )

        launched = (
            update_manager
            .launch_installer(
                self.result,
                self._downloaded_path,
            )
        )

        if not launched:
            self.install_button.setEnabled(
                True
            )
            self.later_button.setEnabled(
                True
            )
            self.release_button.setEnabled(
                True
            )
            self.download_status.setText(
                "Installation could not be started"
            )

            QMessageBox.critical(
                self,
                "Update Installation Failed",
                "The updater helper could not be started.",
            )
            return

        from PySide6.QtWidgets import QApplication

        application = QApplication.instance()

        if application is not None:
            application.quit()

    def _cleanup_download(self) -> None:
        self._download_thread = None
        self._download_worker = None

        self.download_button.setEnabled(
            self._downloaded_path is None
        )
        self.cancel_button.setEnabled(
            False
        )
        self.later_button.setEnabled(
            True
        )
        self.release_button.setEnabled(
            True
        )

    @staticmethod
    def format_bytes(
        value: float | int,
    ) -> str:
        size = max(
            0.0,
            float(value),
        )

        units = (
            "B",
            "KB",
            "MB",
            "GB",
        )

        unit = units[0]

        for candidate in units:
            unit = candidate

            if size < 1024.0 or candidate == units[-1]:
                break

            size /= 1024.0

        if unit == "B":
            return f"{int(size)} {unit}"

        return f"{size:.1f} {unit}"

    def reject(self) -> None:
        if (
            self._download_thread is not None
            and self._download_thread.isRunning()
        ):
            QMessageBox.information(
                self,
                "Download in Progress",
                "Cancel the update download before closing this window.",
            )
            return

        super().reject()

    def open_release(self) -> None:
        url = (
            self.result.github_release_url
            or self.result.manifest.release_url
        )

        if not url:
            QMessageBox.warning(
                self,
                "Release URL",
                "No GitHub release URL is available.",
            )
            return

        webbrowser.open(url)

    def _apply_styles(self) -> None:
        apply_app_style(
            self
        )


class UpdateChecker(QObject):
    """
    Owns the QThread lifecycle for non-blocking update checks.
    """

    checking_changed = Signal(bool)
    update_available = Signal(object)
    up_to_date = Signal(object)
    check_failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: UpdateCheckWorker | None = None

    @property
    def is_checking(self) -> bool:
        return (
            self._thread is not None
            and self._thread.isRunning()
        )

    def check(
        self,
        channel: str,
    ) -> bool:
        if self.is_checking:
            return False

        thread = QThread()
        worker = UpdateCheckWorker(
            channel
        )
        worker.moveToThread(thread)

        thread.started.connect(
            worker.run
        )
        worker.finished.connect(
            self._on_finished
        )
        worker.failed.connect(
            self._on_failed
        )

        worker.finished.connect(
            thread.quit
        )
        worker.failed.connect(
            thread.quit
        )

        thread.finished.connect(
            worker.deleteLater
        )
        thread.finished.connect(
            self._cleanup
        )
        thread.finished.connect(
            thread.deleteLater
        )

        self._thread = thread
        self._worker = worker

        self.checking_changed.emit(
            True
        )
        thread.start()

        return True

    def _on_finished(
        self,
        result: Any,
    ) -> None:
        if not isinstance(
            result,
            UpdateCheckResult,
        ):
            self.check_failed.emit(
                "Updater returned an invalid result."
            )
            return

        if result.has_update:
            self.update_available.emit(
                result
            )
        else:
            self.up_to_date.emit(
                result
            )

    def _on_failed(
        self,
        message: str,
    ) -> None:
        self.check_failed.emit(
            message
        )

    def _cleanup(self) -> None:
        self._thread = None
        self._worker = None
        self.checking_changed.emit(
            False
        )