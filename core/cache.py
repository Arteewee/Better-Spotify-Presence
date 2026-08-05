from collections import OrderedDict
from typing import Any


class Cache:

    def __init__(
        self,
        max_size: int = 100,
    ) -> None:
        self.max_size = max_size
        self.cache = OrderedDict()

        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.evictions = 0

    def get(
        self,
        key: Any,
    ) -> Any:
        if key not in self.cache:
            self.misses += 1
            return None

        self.hits += 1
        self.cache.move_to_end(
            key
        )

        return self.cache[key]

    def set(
        self,
        key: Any,
        value: Any,
    ) -> None:
        self.sets += 1
        self.cache[key] = value

        self.cache.move_to_end(
            key
        )

        if len(self.cache) > self.max_size:
            self.cache.popitem(
                last=False
            )

            self.evictions += 1

    def clear(self) -> None:
        self.cache.clear()

    def has(
        self,
        key: Any,
    ) -> bool:
        return key in self.cache

    def size(self) -> int:
        return len(self.cache)

    def get_stats(self) -> dict[str, Any]:
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
            "entries": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "evictions": self.evictions,
            "hit_rate": hit_rate,
        }


lyrics_cache = Cache(100)