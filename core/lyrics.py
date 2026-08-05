import time
from typing import Any, Optional

import requests

from core.cache import lyrics_cache
from config import Config
from app.logger import logger
from app.event_bus import event_bus
from core.lyrics_persistent_cache import (
    persistent_lyrics_cache,
)
from core.lyrics_providers import (
    LyricsProvider,
    ProviderResult,
    build_providers,
)
from core.state_store import (
    load_state,
    update_state,
)


PROVIDER_STATS_KEY = (
    "lyrics_provider_stats"
)


class LyricsManager:

    def __init__(self) -> None:
        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": (
                    "BetterSpotifyPresence/2.9.5"
                )
            }
        )

        self.providers = build_providers(
            self.session
        )

        self.provider_stats = (
            self._load_provider_stats()
        )

        self.last_provider: Optional[
            str
        ] = None

        self.last_latency = 0.0
        self.last_confidence = 0.0
        self.last_cache_source: Optional[
            str
        ] = None

    @staticmethod
    def _default_stats() -> dict[str, Any]:
        return {
            "successes": 0,
            "failures": 0,
            "timeouts": 0,
            "total_latency": 0.0,
            "last_success": 0.0,
        }

    def _load_provider_stats(
        self,
    ) -> dict[str, dict[str, Any]]:
        state = load_state()

        stats = state.get(
            PROVIDER_STATS_KEY,
            {},
        )

        return (
            stats
            if isinstance(stats, dict)
            else {}
        )

    def _save_provider_stats(
        self,
    ) -> None:
        update_state(
            **{
                PROVIDER_STATS_KEY:
                    self.provider_stats
            }
        )

    def _stats_for(
        self,
        provider_name: str,
    ) -> dict[str, Any]:
        stats = self.provider_stats.get(
            provider_name
        )

        if not isinstance(stats, dict):
            stats = self._default_stats()

            self.provider_stats[
                provider_name
            ] = stats

        return stats

    def _provider_score(
        self,
        provider: LyricsProvider,
    ) -> float:
        default_order = {
            "lrclib_exact": 30.0,
            "lrclib_search": 20.0,
            "netease": 10.0,
        }

        stats = self._stats_for(
            provider.name
        )

        successes = int(
            stats.get(
                "successes",
                0,
            )
        )

        failures = int(
            stats.get(
                "failures",
                0,
            )
        )

        attempts = successes + failures

        if attempts == 0:
            return default_order.get(
                provider.name,
                0.0,
            )

        success_rate = (
            successes / attempts
        )

        average_latency = (
            float(
                stats.get(
                    "total_latency",
                    0.0,
                )
            )
            / max(
                successes,
                1,
            )
        )

        return (
            default_order.get(
                provider.name,
                0.0,
            )
            + success_rate * 50.0
            - average_latency * 4.0
            - failures * 0.25
        )

    def _ranked_providers(
        self,
    ) -> list[LyricsProvider]:
        return sorted(
            self.providers,
            key=self._provider_score,
            reverse=True,
        )

    def _record_result(
        self,
        result: ProviderResult,
        *,
        success: bool,
        timed_out: bool = False,
    ) -> None:
        stats = self._stats_for(
            result.provider
        )

        key = (
            "successes"
            if success
            else "failures"
        )

        stats[key] = int(
            stats.get(
                key,
                0,
            )
        ) + 1

        if success:
            stats["total_latency"] = (
                float(
                    stats.get(
                        "total_latency",
                        0.0,
                    )
                )
                + result.latency
            )

            stats["last_success"] = (
                time.time()
            )

        if timed_out:
            stats["timeouts"] = int(
                stats.get(
                    "timeouts",
                    0,
                )
            ) + 1

        self._save_provider_stats()

    def get_lyrics(
        self,
        track: str,
        artist: str,
        duration_ms: Optional[int] = None,
    ) -> list[dict]:
        memory_key = (
            f"{track.strip()}|"
            f"{artist.strip()}|"
            f"{duration_ms or 0}"
        )

        memory_cached = (
            lyrics_cache.get(
                memory_key
            )
        )

        if memory_cached is not None:
            self.last_provider = (
                "memory_cache"
            )

            self.last_latency = 0.0
            self.last_confidence = 1.0
            self.last_cache_source = (
                "memory"
            )

            logger.info(
                "Memory lyrics cache hit",
                category="CACHE",
                context={
                    "track": track,
                    "artist": artist,
                },
            )

            event_bus.publish(
                "lyrics.cache_hit",
                source="lyrics",
                provider="memory_cache",
                track=track,
                artist=artist,
            )

            return memory_cached

        persistent_cached = (
            persistent_lyrics_cache.get(
                track,
                artist,
                duration_ms,
            )
        )

        if persistent_cached is not None:
            lyrics_cache.set(
                memory_key,
                persistent_cached,
            )

            self.last_provider = (
                "persistent_cache"
            )

            self.last_latency = 0.0
            self.last_confidence = 1.0
            self.last_cache_source = (
                "offline"
            )

            logger.info(
                "Offline lyrics cache hit",
                category="CACHE",
                context={
                    "track": track,
                    "artist": artist,
                },
            )

            event_bus.publish(
                "lyrics.cache_hit",
                source="lyrics",
                provider="persistent_cache",
                track=track,
                artist=artist,
            )

            return persistent_cached

        self.last_cache_source = None

        duration_seconds = (
            duration_ms / 1000.0
            if duration_ms
            else None
        )

        providers = (
            self._ranked_providers()
        )

        if Config.DEBUG:
            logger.debug(
                "Lyrics provider order",
                category="LYRICS",
                context={
                    "order": " -> ".join(
                        provider.name
                        for provider in providers
                    ),
                },
            )

        for provider in providers:
            logger.debug(
                "Trying lyrics provider",
                category="LYRICS",
                context={
                    "provider": provider.name,
                    "track": track,
                    "artist": artist,
                },
            )

            try:
                result = provider.fetch(
                    track,
                    artist,
                    duration_seconds,
                )

            except requests.exceptions.Timeout:
                result = ProviderResult(
                    provider.name,
                    [],
                    Config
                    .LYRICS_PROVIDER_TIMEOUT,
                )

                self._record_result(
                    result,
                    success=False,
                    timed_out=True,
                )

                logger.warning(
                    "Lyrics provider timed out",
                    category="LYRICS",
                    context={
                        "provider": provider.name,
                        "timeout": (
                            Config
                            .LYRICS_PROVIDER_TIMEOUT
                        ),
                    },
                )

                continue

            except requests.exceptions.RequestException as error:
                result = ProviderResult(
                    provider.name,
                    [],
                    0.0,
                )

                self._record_result(
                    result,
                    success=False,
                )

                logger.error(
                    "Lyrics provider network error",
                    category="LYRICS",
                    context={
                        "provider": provider.name,
                        "error": str(error),
                    },
                )

                continue

            except Exception as error:
                result = ProviderResult(
                    provider.name,
                    [],
                    0.0,
                )

                self._record_result(
                    result,
                    success=False,
                )

                logger.error(
                    "Lyrics provider failed",
                    category="LYRICS",
                    context={
                        "provider": provider.name,
                        "error": str(error),
                    },
                )

                continue

            if (
                result.lyrics
                and result.confidence
                >= Config
                .LYRICS_MIN_CONFIDENCE
            ):
                self._record_result(
                    result,
                    success=True,
                )

                lyrics_cache.set(
                    memory_key,
                    result.lyrics,
                )

                persistent_lyrics_cache.set(
                    track=track,
                    artist=artist,
                    duration_ms=duration_ms,
                    lyrics=result.lyrics,
                    provider=result.provider,
                    confidence=(
                        result.confidence
                    ),
                )

                self.last_provider = (
                    result.provider
                )

                self.last_latency = (
                    result.latency
                )

                self.last_confidence = (
                    result.confidence
                )

                logger.info(
                    "Synced lyrics loaded",
                    category="LYRICS",
                    context={
                        "provider": result.provider,
                        "lines": len(
                            result.lyrics
                        ),
                        "latency": (
                            f"{result.latency:.2f}s"
                        ),
                        "confidence": (
                            f"{result.confidence:.0%}"
                        ),
                        "track": track,
                        "artist": artist,
                    },
                )

                event_bus.publish(
                    "lyrics.loaded",
                    source="lyrics",
                    provider=result.provider,
                    lines=len(
                        result.lyrics
                    ),
                    track=track,
                    artist=artist,
                )

                return result.lyrics

            self._record_result(
                result,
                success=False,
            )

            logger.warning(
                "Lyrics result rejected",
                category="LYRICS",
                context={
                    "provider": result.provider,
                    "confidence": (
                        f"{result.confidence:.0%}"
                    ),
                    "minimum": (
                        f"{Config.LYRICS_MIN_CONFIDENCE:.0%}"
                    ),
                },
            )

        self.last_provider = None
        self.last_latency = 0.0
        self.last_confidence = 0.0

        logger.error(
            "All lyrics providers failed",
            category="LYRICS",
            context={
                "track": track,
                "artist": artist,
            },
        )

        event_bus.publish(
            "lyrics.failed",
            source="lyrics",
            track=track,
            artist=artist,
        )

        return []

    def get_status(self) -> dict[str, Any]:
        persistent_stats = (
            persistent_lyrics_cache
            .get_stats()
        )

        memory_stats = (
            lyrics_cache.get_stats()
        )

        provider_successes = sum(
            int(
                stats.get(
                    "successes",
                    0,
                )
            )
            for stats
            in self.provider_stats.values()
            if isinstance(
                stats,
                dict,
            )
        )

        provider_failures = sum(
            int(
                stats.get(
                    "failures",
                    0,
                )
            )
            for stats
            in self.provider_stats.values()
            if isinstance(
                stats,
                dict,
            )
        )

        provider_timeouts = sum(
            int(
                stats.get(
                    "timeouts",
                    0,
                )
            )
            for stats
            in self.provider_stats.values()
            if isinstance(
                stats,
                dict,
            )
        )

        return {
            "last_provider":
                self.last_provider,

            "last_latency":
                self.last_latency,

            "last_confidence":
                self.last_confidence,

            "last_cache_source":
                self.last_cache_source,

            "persistent_cache_entries":
                persistent_stats[
                    "entries"
                ],

            "persistent_cache_stats":
                persistent_stats,

            "memory_cache_stats":
                memory_stats,

            "provider_successes":
                provider_successes,

            "provider_failures":
                provider_failures,

            "provider_timeouts":
                provider_timeouts,

            "provider_stats":
                self.provider_stats,

            "provider_order": [
                provider.name
                for provider
                in self._ranked_providers()
            ],
        }



lyrics_manager = LyricsManager()


def get_lyrics(
    track: str,
    artist: str,
    duration_ms: Optional[int] = None,
) -> list[dict]:
    return lyrics_manager.get_lyrics(
        track,
        artist,
        duration_ms,
    )


def get_lyrics_status() -> dict[str, Any]:
    return lyrics_manager.get_status()