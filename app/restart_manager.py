import sys
from pathlib import Path

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication

from app.engine import engine


def restart_application() -> bool:
    """
    Menjalankan instance Spotify+ baru lalu menutup instance lama.

    Mendukung:
    - development: python desktop.py
    - packaged EXE: Spotify+.exe
    """

    application = QApplication.instance()

    try:
        engine.shutdown()

    except Exception as error:
        print(
            "[Restart] Engine shutdown error: "
            f"{error}"
        )

    if getattr(
        sys,
        "frozen",
        False,
    ):
        program = sys.executable
        arguments = list(
            sys.argv[1:]
        )

    else:
        entry_script = str(
            Path(
                sys.argv[0]
            ).resolve()
        )

        program = sys.executable
        arguments = [
            entry_script,
            *sys.argv[1:],
        ]

    working_directory = str(
        Path(
            sys.argv[0]
        ).resolve().parent
    )

    started = QProcess.startDetached(
        program,
        arguments,
        working_directory,
    )

    if not started:
        print(
            "[Restart] Failed to start "
            "the new application process."
        )

        return False

    if application is not None:
        application.quit()

    return True