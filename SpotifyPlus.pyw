"""
Spotify+ console-less launcher.

Development:
    pythonw SpotifyPlus.pyw

PyInstaller:
    pyinstaller --windowed --name Spotify+ SpotifyPlus.pyw
"""

from app.crash_handler import (
    install_crash_handler,
    report_exception,
)

install_crash_handler()

try:
    from desktop import main

    raise SystemExit(
        main()
    )

except SystemExit:
    raise

except Exception as error:
    report_exception(
        error,
        source="launcher",
        title="Spotify+ failed to start",
    )
