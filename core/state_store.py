import json
import os
from pathlib import Path
from typing import Any


APP_FOLDER_NAME = "BetterSpotifyPresence"
STATE_FILE_NAME = "app_state.json"


def get_state_directory() -> Path:
    """
    Windows:
        %LOCALAPPDATA%/BetterSpotifyPresence

    Fallback:
        ~/.better_spotify_presence
    """

    local_app_data = os.getenv("LOCALAPPDATA")

    if local_app_data:
        directory = (
            Path(local_app_data)
            / APP_FOLDER_NAME
        )
    else:
        directory = (
            Path.home()
            / ".better_spotify_presence"
        )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return directory


def get_state_file() -> Path:
    return (
        get_state_directory()
        / STATE_FILE_NAME
    )


def load_state() -> dict[str, Any]:
    """
    Membaca state aplikasi.

    Jika file rusak atau belum ada, kembalikan dictionary kosong.
    """

    state_file = get_state_file()

    if not state_file.exists():
        return {}

    try:
        with state_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if isinstance(data, dict):
            return data

    except (
        OSError,
        json.JSONDecodeError,
    ):
        pass

    return {}


def save_state(
    state: dict[str, Any],
) -> None:
    """
    Menyimpan state secara aman menggunakan temporary file,
    lalu mengganti file lama.
    """

    state_file = get_state_file()

    temporary_file = state_file.with_suffix(
        ".tmp"
    )

    try:
        with temporary_file.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                state,
                file,
                indent=2,
                ensure_ascii=False,
            )

        temporary_file.replace(state_file)

    except OSError as error:
        print(
            f"[State] Failed to save state: "
            f"{error}"
        )


def update_state(
    **values: Any,
) -> None:
    state = load_state()

    state.update(values)

    save_state(state)


def remove_state_keys(
    *keys: str,
) -> None:
    state = load_state()

    changed = False

    for key in keys:
        if key in state:
            del state[key]
            changed = True

    if changed:
        save_state(state)