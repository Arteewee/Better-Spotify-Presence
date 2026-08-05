import time
from typing import Any

from core.lyrics import get_lyrics_status
from core.rpc import get_rpc_status
from core.spotify import get_spotify_status


_last_print_time = 0.0


def build_diagnostics() -> dict[str, Any]:
    spotify = get_spotify_status()
    lyrics = get_lyrics_status()
    rpc = get_rpc_status()

    return {
        "spotify_profile":
            spotify.get(
                "active_profile",
                "unknown",
            ),

        "spotify_rate_limited":
            spotify.get(
                "rate_limited",
                False,
            ),

        "spotify_retry_after":
            spotify.get(
                "retry_after",
                0,
            ),

        "lyrics_provider":
            lyrics.get(
                "last_provider",
            ),

        "lyrics_latency":
            lyrics.get(
                "last_latency",
                0.0,
            ),

        "lyrics_confidence":
            lyrics.get(
                "last_confidence",
                0.0,
            ),

        "lyrics_cache_source":
            lyrics.get(
                "last_cache_source",
            ),

        "persistent_cache_entries":
            lyrics.get(
                "persistent_cache_entries",
                0,
            ),

        "rpc_connected":
            rpc.get(
                "connected",
                False,
            ),

        "rpc_updates_sent":
            rpc.get(
                "updates_sent",
                0,
            ),

        "rpc_updates_skipped":
            rpc.get(
                "updates_skipped",
                0,
            ),

        "spotify_request_attempts":
            spotify.get(
                "request_attempts",
                0,
            ),

        "spotify_rate_limit_count":
            spotify.get(
                "rate_limit_count",
                0,
            ),

        "memory_cache_entries":
            lyrics.get(
                "memory_cache_stats",
                {},
            ).get(
                "entries",
                0,
            ),

        "memory_cache_hit_rate":
            lyrics.get(
                "memory_cache_stats",
                {},
            ).get(
                "hit_rate",
                0.0,
            ),
    }


def print_diagnostics(
    *,
    force: bool = False,
    interval: float = 60.0,
) -> None:
    global _last_print_time

    now = time.monotonic()

    if (
        not force
        and now - _last_print_time
        < interval
    ):
        return

    _last_print_time = now

    data = build_diagnostics()

    print("\n[Diagnostics]")
    print(
        "  Spotify Profile : "
        f"{data['spotify_profile']}"
    )
    print(
        "  Rate Limited    : "
        f"{data['spotify_rate_limited']}"
    )
    print(
        "  Lyrics Provider : "
        f"{data['lyrics_provider'] or '-'}"
    )
    print(
        "  Confidence      : "
        f"{data['lyrics_confidence']:.0%}"
    )
    print(
        "  Lyrics Latency  : "
        f"{data['lyrics_latency']:.2f}s"
    )
    print(
        "  Cache Source    : "
        f"{data['lyrics_cache_source'] or '-'}"
    )
    print(
        "  Offline Entries : "
        f"{data['persistent_cache_entries']}"
    )
    print(
        "  RPC Connected   : "
        f"{data['rpc_connected']}"
    )
    print(
        "  RPC Sent/Skip   : "
        f"{data['rpc_updates_sent']}/"
        f"{data['rpc_updates_skipped']}"
    )