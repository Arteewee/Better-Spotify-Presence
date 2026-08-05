import time
from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
)
from typing import Any, Optional

from config import Config
from diagnostics import print_diagnostics
from lyrics import get_lyrics
from rpc import clear, update
from spotify import (
    get_current_song,
    get_spotify_status,
)
from sync_engine import (
    get_current_line,
    reset,
    set_lyrics,
)


current_song: Optional[
    dict[str, Any]
] = None

last_song_id: Optional[str] = None
last_line: Optional[str] = None

# Playback clock lokal.
base_progress_seconds = 0.0
base_clock_time = 0.0

# Timestamp timer Discord.
song_start_timestamp: Optional[int] = None
song_end_timestamp: Optional[int] = None

# Waktu polling Spotify terakhir.
last_spotify_poll_time = 0.0

# Hindari clear berulang saat idle.
discord_has_been_cleared = False

# Hindari satu respons None sementara langsung clear.
empty_poll_count = 0

# Hindari log rate-limit berulang-ulang.
last_rate_limit_log = 0.0

# ===========================
# Background Lyrics Loader
# ===========================

lyrics_executor = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="lyrics-loader",
)

lyrics_future: Optional[
    Future
] = None

lyrics_future_song_id: Optional[str] = None

# Token generasi mencegah hasil lagu lama dipasang ke lagu baru.
lyrics_generation = 0

lyrics_loading = False


def get_local_progress() -> float:
    """
    Progress lokal tidak bergantung pada frekuensi Spotify API.
    """

    if current_song is None:
        return 0.0

    elapsed = (
        time.perf_counter()
        - base_clock_time
    )

    progress = (
        base_progress_seconds
        + elapsed
    )

    duration = (
        current_song["duration"]
        / 1000.0
    )

    return max(
        0.0,
        min(
            progress,
            duration,
        ),
    )


def get_remaining_duration() -> float:
    """
    Menghitung sisa durasi lagu berdasarkan local clock.
    """

    if current_song is None:
        return float("inf")

    duration = (
        current_song["duration"]
        / 1000.0
    )

    return max(
        0.0,
        duration - get_local_progress(),
    )


def get_spotify_poll_interval() -> float:
    """
    Poll adaptif:
    - normal: hemat request;
    - hampir selesai: lebih cepat;
    - cooldown: spotify.py mengembalikan cache.
    """

    status = get_spotify_status()

    if status["rate_limited"]:
        return Config.SPOTIFY_REFRESH_RATE

    if (
        current_song is not None
        and get_remaining_duration()
        <= Config.SPOTIFY_ENDING_WINDOW
    ):
        return (
            Config.SPOTIFY_FAST_REFRESH_RATE
        )

    return Config.SPOTIFY_REFRESH_RATE


def initialize_playback_clock(
    song: dict[str, Any],
) -> None:
    """
    Membuat local playback clock baru.
    """

    global base_progress_seconds
    global base_clock_time
    global song_start_timestamp
    global song_end_timestamp

    base_progress_seconds = (
        song["progress"] / 1000.0
    )

    base_clock_time = (
        time.perf_counter()
    )

    now_unix = time.time()

    song_start_timestamp = int(
        now_unix
        - base_progress_seconds
    )

    song_end_timestamp = int(
        song_start_timestamp
        + (
            song["duration"]
            / 1000.0
        )
    )


def hard_sync_playback_clock(
    api_progress_seconds: float,
) -> None:
    """
    Hard sync saat user seek atau drift sangat besar.
    """

    global base_progress_seconds
    global base_clock_time
    global song_start_timestamp
    global song_end_timestamp
    global last_line

    if current_song is None:
        return

    base_progress_seconds = (
        api_progress_seconds
    )

    base_clock_time = (
        time.perf_counter()
    )

    now_unix = time.time()

    song_start_timestamp = int(
        now_unix
        - api_progress_seconds
    )

    song_end_timestamp = int(
        song_start_timestamp
        + (
            current_song["duration"]
            / 1000.0
        )
    )

    last_line = None


def smoothly_correct_clock(
    song: dict[str, Any],
) -> None:
    """
    Koreksi drift hanya menggunakan respons API asli.
    """

    global base_progress_seconds
    global base_clock_time

    if song.get(
        "_from_cache",
        False,
    ):
        return

    api_progress = (
        song["progress"]
        / 1000.0
    )

    local_progress = (
        get_local_progress()
    )

    drift = (
        api_progress
        - local_progress
    )

    absolute_drift = abs(
        drift
    )

    if absolute_drift >= 1.25:
        if Config.DEBUG:
            print(
                f"[Clock] Hard sync: "
                f"{drift:+.3f}s"
            )

        hard_sync_playback_clock(
            api_progress
        )

        return

    if absolute_drift >= 0.20:
        correction = (
            drift * 0.35
        )

        base_progress_seconds = (
            local_progress
            + correction
        )

        base_clock_time = (
            time.perf_counter()
        )

        if Config.DEBUG:
            print(
                f"[Clock] Smooth correction: "
                f"{correction:+.3f}s"
            )


def lyrics_worker(
    song_id: str,
    generation: int,
    track: str,
    artist: str,
    duration_ms: int,
) -> tuple[
    str,
    int,
    list[dict],
]:
    """
    Worker thread. Tidak menyentuh state playback global.
    """

    loaded_lyrics = get_lyrics(
        track,
        artist,
        duration_ms,
    )

    return (
        song_id,
        generation,
        loaded_lyrics,
    )


def start_lyrics_loader(
    song: dict[str, Any],
) -> None:
    """
    Mulai request lirik di background.

    Playback clock, polling Spotify, dan Discord RPC tidak menunggu
    request provider lirik.
    """

    global lyrics_future
    global lyrics_future_song_id
    global lyrics_generation
    global lyrics_loading

    lyrics_generation += 1

    generation = (
        lyrics_generation
    )

    lyrics_future_song_id = (
        song["id"]
    )

    lyrics_loading = True

    print(
        "[Lyrics] Loading in background..."
    )

    lyrics_future = (
        lyrics_executor.submit(
            lyrics_worker,
            song["id"],
            generation,
            song["name"],
            song["artist"],
            song["duration"],
        )
    )


def process_lyrics_result() -> None:
    """
    Pasang hasil worker hanya bila masih cocok dengan lagu aktif.

    Ini mencegah:
    - lirik lagu lama masuk setelah user cepat menekan Next;
    - hasil timeout lama merusak lagu baru;
    - main loop terblokir.
    """

    global lyrics_future
    global lyrics_future_song_id
    global lyrics_loading
    global last_line

    future = lyrics_future

    if (
        future is None
        or not future.done()
    ):
        return

    lyrics_future = None
    lyrics_future_song_id = None
    lyrics_loading = False

    try:
        (
            result_song_id,
            result_generation,
            loaded_lyrics,
        ) = future.result()

    except Exception as error:
        print(
            "[Lyrics] Background loader error: "
            f"{error}"
        )

        return

    if current_song is None:
        print(
            "[Lyrics] Ignored result: "
            "no active song."
        )
        return

    if (
        result_song_id
        != current_song["id"]
    ):
        print(
            "[Lyrics] Ignored stale result "
            "from previous song."
        )
        return

    if (
        result_generation
        != lyrics_generation
    ):
        print(
            "[Lyrics] Ignored stale "
            "loader generation."
        )
        return

    set_lyrics(
        loaded_lyrics
    )

    # Paksa evaluasi lirik menggunakan progress lokal terbaru.
    last_line = None

    if loaded_lyrics:
        print(
            "[Lyrics] Background lyrics ready."
        )
    else:
        print(
            "[Lyrics] No synced lyrics found."
        )


def invalidate_lyrics_loader() -> None:
    """
    Membatalkan/menandai hasil worker lama sebagai stale.
    """

    global lyrics_future
    global lyrics_future_song_id
    global lyrics_generation
    global lyrics_loading

    lyrics_generation += 1
    lyrics_loading = False
    lyrics_future_song_id = None

    if (
        lyrics_future is not None
        and not lyrics_future.done()
    ):
        # cancel() hanya berhasil jika worker belum mulai.
        lyrics_future.cancel()

    lyrics_future = None


def load_song(
    song: dict[str, Any],
) -> None:
    """
    Memuat metadata dan clock seketika.
    Lirik dimuat non-blocking di background.
    """

    global current_song
    global last_song_id
    global last_line
    global discord_has_been_cleared

    invalidate_lyrics_loader()

    current_song = song.copy()
    last_song_id = song["id"]
    last_line = None

    reset()
    set_lyrics([])

    initialize_playback_clock(
        song
    )

    print(
        "\n=============================="
    )

    print(
        f"🎵 {song['name']}"
    )

    print(
        f"👤 {song['artist']}"
    )

    print(
        "=============================="
    )

    start_lyrics_loader(
        song
    )

    discord_has_been_cleared = False


def update_discord_lyrics() -> None:
    """
    Live lyrics menggunakan local clock setiap 50 ms.
    """

    global last_line

    if current_song is None:
        return

    current_time = (
        get_local_progress()
    )

    line = get_current_line(
        current_time
    )

    raw_line = (
        line.strip()
        if isinstance(line, str)
        else ""
    )

    if raw_line == last_line:
        return

    last_line = raw_line

    printable_line = (
        raw_line
        if raw_line
        else "Instrumental"
    )

    print(
        f"[{current_time:07.2f}] "
        f"{printable_line}"
    )

    update(
        song=current_song["name"],
        artist=current_song["artist"],
        lyric=raw_line,
        start=song_start_timestamp,
        end=song_end_timestamp,
        album_cover=current_song.get(
            "album_cover"
        ),
        album_name=current_song.get(
            "album"
        ),
        spotify_url=current_song.get(
            "spotify_url"
        ),
    )


def clear_current_activity() -> None:
    """
    Membersihkan state lokal dan Discord.
    """

    global current_song
    global last_song_id
    global last_line
    global discord_has_been_cleared

    invalidate_lyrics_loader()

    if not discord_has_been_cleared:
        clear()
        discord_has_been_cleared = True

    current_song = None
    last_song_id = None
    last_line = None

    reset()
    set_lyrics([])


def handle_cached_song_end() -> None:
    """
    Bersihkan activity cache setelah lagu selesai saat cooldown.
    """

    if current_song is None:
        return

    status = (
        get_spotify_status()
    )

    if not status["rate_limited"]:
        return

    duration = (
        current_song["duration"]
        / 1000.0
    )

    elapsed = (
        base_progress_seconds
        + (
            time.perf_counter()
            - base_clock_time
        )
    )

    if (
        elapsed
        >= duration
        + Config.STALE_ACTIVITY_GRACE
    ):
        print(
            "[Spotify] Cached track ended "
            "during API cooldown."
        )

        clear_current_activity()


def print_rate_limit_status() -> None:
    """
    Menampilkan cooldown maksimal sekali per menit.
    """

    global last_rate_limit_log

    status = (
        get_spotify_status()
    )

    if not status["rate_limited"]:
        return

    now = time.monotonic()

    if (
        now - last_rate_limit_log
        < 60
    ):
        return

    last_rate_limit_log = now

    retry_after = status[
        "retry_after"
    ]

    hours, remainder = divmod(
        retry_after,
        3600,
    )

    minutes, seconds = divmod(
        remainder,
        60,
    )

    print(
        "[Spotify] Cooldown remaining: "
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def handle_spotify_result(
    song: Optional[
        dict[str, Any]
    ],
) -> None:
    """
    Memproses hasil Spotify poll.
    """

    global current_song
    global last_song_id
    global discord_has_been_cleared
    global empty_poll_count

    status = (
        get_spotify_status()
    )

    if (
        status["rate_limited"]
        and song is None
    ):
        return

    if song is None:
        empty_poll_count += 1

        if (
            empty_poll_count
            < Config.EMPTY_POLLS_BEFORE_CLEAR
        ):
            return

        clear_current_activity()
        return

    empty_poll_count = 0
    discord_has_been_cleared = False

    if song["id"] != last_song_id:
        print(
            f"\n🎵 Song Changed -> "
            f"{song['name']}"
        )

        clear()
        load_song(song)
        return

    if current_song is not None:
        preserved_progress = (
            current_song.get(
                "progress",
                0,
            )
        )

        current_song.update(
            song
        )

        if song.get(
            "_from_cache",
            False,
        ):
            current_song["progress"] = (
                preserved_progress
            )

    smoothly_correct_clock(
        song
    )


def main() -> None:
    global last_spotify_poll_time

    print(
        "==================================="
    )

    print(
        " Spotify Discord Lyrics"
    )

    print(
        "===================================\n"
    )

    print(
        f" Spotify Profile: "
        f"{Config.ACTIVE_SPOTIFY_PROFILE}"
    )

    try:
        while True:
            loop_start = (
                time.perf_counter()
            )

            current_clock = (
                time.perf_counter()
            )

            spotify_poll_interval = (
                get_spotify_poll_interval()
            )

            if (
                current_clock
                - last_spotify_poll_time
                >= spotify_poll_interval
            ):
                spotify_song = (
                    get_current_song()
                )

                handle_spotify_result(
                    spotify_song
                )

                last_spotify_poll_time = (
                    current_clock
                )

            # Ambil hasil background tanpa memblokir.
            process_lyrics_result()

            update_discord_lyrics()

            handle_cached_song_end()

            print_rate_limit_status()

            if Config.DIAGNOSTICS_ENABLED:
                print_diagnostics(
                    interval=(
                        Config
                        .DIAGNOSTICS_INTERVAL
                    )
                )

            loop_duration = (
                time.perf_counter()
                - loop_start
            )

            remaining_sleep = max(
                0.0,
                Config.LYRIC_REFRESH_RATE
                - loop_duration,
            )

            time.sleep(
                remaining_sleep
            )

    finally:
        invalidate_lyrics_loader()

        lyrics_executor.shutdown(
            wait=False,
            cancel_futures=True,
        )


if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:
        print(
            "\n[App] Program stopped."
        )

        clear()

    except Exception as error:
        print(
            f"\n[App Error] {error}"
        )

        clear()
        raise