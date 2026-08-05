import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
)

from app.engine import engine
from config import Config
from app.settings_manager import settings
from app.logger import logger
from app.event_bus import event_bus
from app.status_manager import status_manager
from app.crash_handler import (
    install_crash_handler,
    report_exception,
)
from ui.main_window import MainWindow
from ui.tray import TrayIcon


def main() -> int:
    install_crash_handler()

    logger.info(
        "Spotify+ application starting",
        category="APP",
    )

    # Force singleton initialization before UI creation.
    status_manager.get()

    event_bus.publish(
        "app.started",
        source="desktop",
    )

    application = QApplication(
        sys.argv
    )

    application.setApplicationName(
        "Spotify+"
    )

    application.setApplicationDisplayName(
        "Spotify+"
    )

    application.setOrganizationName(
        "RJH"
    )

    application.aboutToQuit.connect(
        logger.flush
    )

    # Window boleh ditutup tanpa menghentikan aplikasi karena
    # engine tetap berjalan melalui system tray.
    application.setQuitOnLastWindowClosed(
        False
    )

    window = MainWindow()

    tray: TrayIcon | None = None

    if TrayIcon.is_available():
        tray = TrayIcon(
            window
        )

        window.set_tray_available(
            True
        )

        tray.show()

    else:
        # Fallback: jika OS tidak menyediakan tray, tombol X
        # tetap menutup aplikasi secara normal.
        application.setQuitOnLastWindowClosed(
            True
        )

        QMessageBox.warning(
            window,
            "System Tray Unavailable",
            (
                "System tray tidak tersedia. "
                "Menutup window akan menghentikan Spotify+."
            ),
        )

    window.show()

    update_success_file = (
        Path(
            Config.APP_DATA_DIR
        )
        / "updates"
        / "last-update-success.json"
    )

    if update_success_file.exists():
        try:
            import json

            update_success = json.loads(
                update_success_file.read_text(
                    encoding="utf-8"
                )
            )

            update_success_file.unlink(
                missing_ok=True
            )

            installed_version = str(
                update_success.get(
                    "version",
                    "",
                )
            )

            QMessageBox.information(
                window,
                "Update Installed",
                (
                    "Spotify+ was updated successfully."
                    + (
                        f"\n\nVersion: {installed_version}"
                        if installed_version
                        else ""
                    )
                ),
            )

        except (
            OSError,
            ValueError,
        ):
            pass

    update_error_file = (
        Path(
            Config.APP_DATA_DIR
        )
        / "updates"
        / "last-update-error.txt"
    )

    if update_error_file.exists():
        try:
            update_error_message = (
                update_error_file.read_text(
                    encoding="utf-8"
                )
            )

            update_error_file.unlink(
                missing_ok=True
            )

            QMessageBox.warning(
                window,
                "Update Rolled Back",
                (
                    "The previous update could not be applied. "
                    "Spotify+ restored the previous version.\n\n"
                    f"{update_error_message}"
                ),
            )

        except OSError:
            pass

    # Update check berjalan di background dan tidak memblokir
    # engine, live lyrics, atau GUI startup.
    QTimer.singleShot(
        3000,
        window.check_for_updates_on_startup,
    )

    # Jalankan engine otomatis hanya jika preference aktif.
    if settings.get(
        "start_engine_on_launch",
        True,
    ):
        QTimer.singleShot(
            0,
            engine.start,
        )

    # Simpan reference agar object tray tidak dihapus GC.
    application.tray_icon = tray
    application.main_window = window

    exit_code = application.exec()

    event_bus.publish(
        "app.stopping",
        source="desktop",
        exit_code=exit_code,
    )

    logger.info(
        "Spotify+ application stopped",
        category="APP",
        context={
            "exit_code": exit_code,
        },
    )

    logger.shutdown()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(
        main()
    )