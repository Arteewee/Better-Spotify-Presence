import time
from typing import Any, Optional

from config import Config
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
    - hampir selesai: lebih cepat mendeteksi lagu berikutnya;
    - cooldown: pemanggilan fungsi tetap boleh terjadi,
      tetapi spotify.py tidak melakukan network request.
    """

    status = get_spotify_status()

    if status["rate_limited"]:

        # Nilainya tidak memengaruhi API karena spotify.py
        # langsung mengembalikan cache.
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

    # Paksa lirik dihitung ulang setelah seek.
    last_line = None


def smoothly_correct_clock(
    song: dict[str, Any],
) -> None:
    """
    Koreksi drift hanya menggunakan respons API asli.

    Data cache/rate-limit tidak boleh menarik local clock mundur.
    """

    global base_progress_seconds
    global base_clock_time

    if song.get("_from_cache", False):
        return

    api_progress = (
        song["progress"] / 1000.0
    )

    local_progress = (
        get_local_progress()
    )

    drift = (
        api_progress
        - local_progress
    )

    absolute_drift = abs(drift)

    # Kemungkinan user melakukan seek.
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

    # Koreksi bertahap untuk drift sedang.
    if absolute_drift >= 0.20:

        correction = drift * 0.35

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


def load_song(
    song: dict[str, Any],
) -> None:
    """
    Memuat metadata, clock, dan synced lyrics.
    """

    global current_song
    global last_song_id
    global last_line
    global discord_has_been_cleared

    current_song = song.copy()
    last_song_id = song["id"]
    last_line = None

    reset()

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

    loaded_lyrics = get_lyrics(
        song["name"],
        song["artist"],
    )

    set_lyrics(
        loaded_lyrics
    )

    if not loaded_lyrics:

        print(
            "[Lyrics] No synced lyrics found."
        )

    discord_has_been_cleared = False


def update_discord_lyrics() -> None:
    """
    Live lyrics tetap memakai local clock setiap 50 ms.
    """

    global last_line

    if current_song is None:
        return

    current_time = get_local_progress()

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
    Jika Spotify sedang rate limited, kita tidak tahu lagu berikutnya.

    Setelah lagu cache selesai dan melewati grace period,
    activity lama dibersihkan agar tidak nyangkut.
    """

    if current_song is None:
        return

    status = get_spotify_status()

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

    status = get_spotify_status()

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
    song: Optional[dict[str, Any]],
) -> None:
    """
    Memproses hasil Spotify poll.
    """

    global current_song
    global last_song_id
    global discord_has_been_cleared
    global empty_poll_count

    status = get_spotify_status()

    # Saat rate limited, None bukan berarti Spotify idle.
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

    # Lagu berubah.
    if song["id"] != last_song_id:

        print(
            f"\n🎵 Song Changed -> "
            f"{song['name']}"
        )

        clear()
        load_song(song)

        return

    # Metadata cache tetap boleh disimpan, tetapi jangan
    # memperbarui progress dari data cache.
    if current_song is not None:

        preserved_progress = (
            current_song.get(
                "progress",
                0,
            )
        )

        current_song.update(song)

        if song.get(
            "_from_cache",
            False,
        ):

            current_song["progress"] = (
                preserved_progress
            )

    smoothly_correct_clock(song)


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

        update_discord_lyrics()

        handle_cached_song_end()

        print_rate_limit_status()

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