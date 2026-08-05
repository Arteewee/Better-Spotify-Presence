import sys
import threading
import traceback
from typing import Any, Optional

from app.event_bus import event_bus
from app.logger import logger


_installed = False
_handling = threading.Lock()


def _format_traceback(
    exception_type: type[BaseException],
    exception_value: BaseException,
    exception_traceback: Any,
) -> str:
    return "".join(
        traceback.format_exception(
            exception_type,
            exception_value,
            exception_traceback,
        )
    ).strip()


def report_exception(
    error: BaseException,
    *,
    source: str = "application",
    title: str = "Unexpected application error",
    details: Optional[str] = None,
) -> None:
    """
    Catat dan publish error tanpa membutuhkan terminal.
    """

    if details is None:
        details = "".join(
            traceback.format_exception(
                type(error),
                error,
                error.__traceback__,
            )
        ).strip()

    logger.critical(
        title,
        category="SYSTEM",
        context={
            "source": source,
            "error_type": type(error).__name__,
            "error": str(error),
        },
    )

    logger.error(
        details,
        category="SYSTEM",
    )

    logger.flush()

    event_bus.publish(
        "app.fatal_error",
        source=source,
        message=title,
        details=details,
        error_type=type(error).__name__,
    )


def _system_exception_hook(
    exception_type: type[BaseException],
    exception_value: BaseException,
    exception_traceback: Any,
) -> None:
    if issubclass(
        exception_type,
        KeyboardInterrupt,
    ):
        original = getattr(
            sys,
            "__excepthook__",
            None,
        )

        if callable(original):
            original(
                exception_type,
                exception_value,
                exception_traceback,
            )

        return

    if not _handling.acquire(
        blocking=False
    ):
        return

    try:
        details = _format_traceback(
            exception_type,
            exception_value,
            exception_traceback,
        )

        report_exception(
            exception_value,
            source="sys.excepthook",
            title="Spotify+ encountered an unexpected error",
            details=details,
        )

    finally:
        _handling.release()


def _thread_exception_hook(
    args: threading.ExceptHookArgs,
) -> None:
    if not _handling.acquire(
        blocking=False
    ):
        return

    try:
        details = _format_traceback(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
        )

        thread_name = (
            args.thread.name
            if args.thread is not None
            else "unknown"
        )

        report_exception(
            args.exc_value,
            source=f"thread:{thread_name}",
            title="A Spotify+ background process crashed",
            details=details,
        )

    finally:
        _handling.release()


def install_crash_handler() -> None:
    global _installed

    if _installed:
        return

    sys.excepthook = (
        _system_exception_hook
    )

    if hasattr(
        threading,
        "excepthook",
    ):
        threading.excepthook = (
            _thread_exception_hook
        )

    _installed = True

    logger.debug(
        "Global crash handler installed",
        category="SYSTEM",
    )