from bisect import bisect_right
from typing import Any


class SyncEngine:
    """
    Menyimpan timestamp lirik sekali saja.

    Pencarian lirik menggunakan binary search, sehingga tidak perlu
    melakukan looping dari baris pertama setiap 50 ms.
    """

    def __init__(self) -> None:
        self.timestamps: list[float] = []
        self.lines: list[str] = []
        self.current_index = -1

    def set_lyrics(
        self,
        lyrics: list[dict[str, Any]],
    ) -> None:
        self.timestamps = []
        self.lines = []
        self.current_index = -1

        for lyric in lyrics:
            timestamp = lyric.get("time")
            text = lyric.get("text", "")

            if timestamp is None:
                continue

            self.timestamps.append(float(timestamp))
            self.lines.append(str(text))

    def reset(self) -> None:
        self.current_index = -1

    def get_current_line(
        self,
        current_time: float,
    ) -> str:
        if not self.timestamps:
            return ""

        index = (
            bisect_right(
                self.timestamps,
                current_time,
            )
            - 1
        )

        if index < 0:
            self.current_index = -1
            return ""

        if index >= len(self.lines):
            index = len(self.lines) - 1

        self.current_index = index

        return self.lines[index]


sync_engine = SyncEngine()


def set_lyrics(
    lyrics: list[dict[str, Any]],
) -> None:
    sync_engine.set_lyrics(lyrics)


def get_current_line(
    current_time: float,
) -> str:
    return sync_engine.get_current_line(
        current_time
    )


def reset() -> None:
    sync_engine.reset()