import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

from config import Config


CACHE_VERSION = 1


class PersistentLyricsCache:
    """
    Offline persistent cache untuk synced lyrics.

    Data disimpan di Local App Data, bukan di repository.
    """

    def __init__(self) -> None:
        self.path = (
            Path(Config.APP_DATA_DIR)
            / "lyrics_cache.json"
        )

        self._data: dict[str, Any] = {
            "version": CACHE_VERSION,
            "entries": {},
        }

        self.hits = 0
        self.misses = 0
        self.writes = 0
        self.evictions = 0

        self._load()

    @staticmethod
    def make_key(
        track: str,
        artist: str,
        duration_ms: Optional[int],
    ) -> str:
        normalized = (
            f"{track.strip().lower()}|"
            f"{artist.strip().lower()}|"
            f"{int(duration_ms or 0)}"
        )

        return hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

    def _load(self) -> None:
        if not self.path.exists():
            return

        try:
            with self.path.open(
                "r",
                encoding="utf-8",
            ) as file:
                loaded = json.load(file)

            if (
                isinstance(loaded, dict)
                and isinstance(
                    loaded.get("entries"),
                    dict,
                )
            ):
                self._data = loaded

        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            print(
                "[Lyrics Cache] Failed to load: "
                f"{error}"
            )

    def _save(self) -> None:
        temporary = self.path.with_suffix(
            ".tmp"
        )

        try:
            self.path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with temporary.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    self._data,
                    file,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

            temporary.replace(
                self.path
            )

        except OSError as error:
            print(
                "[Lyrics Cache] Failed to save: "
                f"{error}"
            )

    def get(
        self,
        track: str,
        artist: str,
        duration_ms: Optional[int],
    ) -> Optional[list[dict]]:
        key = self.make_key(
            track,
            artist,
            duration_ms,
        )

        entry = self._data[
            "entries"
        ].get(key)

        if not isinstance(entry, dict):
            self.misses += 1
            return None

        lyrics = entry.get(
            "lyrics"
        )

        if not isinstance(
            lyrics,
            list,
        ):
            self.misses += 1
            return None

        self.hits += 1

        entry["last_accessed"] = (
            time.time()
        )

        entry["hits"] = int(
            entry.get(
                "hits",
                0,
            )
        ) + 1

        return lyrics

    def set(
        self,
        track: str,
        artist: str,
        duration_ms: Optional[int],
        lyrics: list[dict],
        provider: str,
        confidence: float,
    ) -> None:
        if not lyrics:
            return

        key = self.make_key(
            track,
            artist,
            duration_ms,
        )

        now = time.time()

        self._data[
            "entries"
        ][key] = {
            "track": track,
            "artist": artist,
            "duration_ms": int(
                duration_ms or 0
            ),
            "provider": provider,
            "confidence": confidence,
            "lyrics": lyrics,
            "created_at": now,
            "last_accessed": now,
            "hits": 0,
        }

        self.writes += 1

        self._prune()
        self._save()

    def _prune(self) -> None:
        entries = self._data[
            "entries"
        ]

        max_entries = (
            Config
            .PERSISTENT_LYRICS_CACHE_SIZE
        )

        if len(entries) <= max_entries:
            return

        ordered = sorted(
            entries.items(),
            key=lambda item: float(
                item[1].get(
                    "last_accessed",
                    0.0,
                )
            ),
        )

        remove_count = (
            len(entries)
            - max_entries
        )

        for key, _ in ordered[
            :remove_count
        ]:
            entries.pop(
                key,
                None,
            )

            self.evictions += 1

    def get_stats(self) -> dict[str, Any]:
        entries = self._data[
            "entries"
        ]

        requests = (
            self.hits
            + self.misses
        )

        hit_rate = (
            self.hits / requests
            if requests
            else 0.0
        )

        return {
            "entries": len(entries),
            "max_entries":
                Config.PERSISTENT_LYRICS_CACHE_SIZE,
            "path": str(self.path),
            "hits": self.hits,
            "misses": self.misses,
            "writes": self.writes,
            "evictions": self.evictions,
            "hit_rate": hit_rate,
        }



persistent_lyrics_cache = (
    PersistentLyricsCache()
)