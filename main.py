import time
from typing import Any, Optional

from config import Config
from lyrics import get_lyrics
from rpc import clear, update
from spotify import get_current_song
from sync_engine import (
    get_current_line,
    reset,
    set_lyrics,
)


current_song: Optional[dict[str, Any]] = None

last_song_id: Optional[str] = None
last_line: Optional[str] = None

# Playback clock lokal.
base_progress_seconds = 0.0
base_clock_time = 0.0

# Timestamp untuk timer Discord.
song_start_timestamp: Optional[int] = None
song_end_timestamp: Optional[int] = None

# Waktu polling Spotify terakhir.
last_spotify_poll_time = 0.0

# Mencegah clear() dikirim terus-menerus ketika Spotify idle.
discord_has_been_cleared = False

# Mencegah satu respons None sementara langsung menghapus activity.
empty_poll_count = 0
EMPTY_POLLS_BEFORE_CLEAR = 2


def get_local_progress() -> float:
    """
    Menghasilkan progress lagu berdasarkan clock lokal Python.

    Setelah progress didapat dari Spotify, Python melanjutkan clock
    secara mandiri tanpa menunggu Spotify API.
    """

    if current_song is None:
        return 0.0

    elapsed = time.perf_counter() - base_clock_time

    progress = base_progress_seconds + elapsed
    duration = current_song["duration"] / 1000.0

    return max(
        0.0,
        min(progress, duration),
    )


def initialize_playback_clock(
    song: dict[str, Any],
) -> None:
    """
    Membuat clock baru ketika lagu berubah.
    """

    global base_progress_seconds
    global base_clock_time
    global song_start_timestamp
    global song_end_timestamp

    base_progress_seconds = (
        song["progress"] / 1000.0
    )

    base_clock_time = time.perf_counter()

    now_unix = time.time()

    song_start_timestamp = int(
        now_unix - base_progress_seconds
    )

    song_end_timestamp = int(
        song_start_timestamp
        + (song["duration"] / 1000.0)
    )


def hard_sync_playback_clock(
    api_progress_seconds: float,
) -> None:
    """
    Menyamakan local clock secara langsung.

    Dipakai ketika user melakukan seek atau perbedaan clock terlalu
    jauh dari progress Spotify.
    """

    global base_progress_seconds
    global base_clock_time
    global song_start_timestamp
    global song_end_timestamp
    global last_line

    if current_song is None:
        return

    base_progress_seconds = api_progress_seconds
    base_clock_time = time.perf_counter()

    now_unix = time.time()

    song_start_timestamp = int(
        now_unix - api_progress_seconds
    )

    song_end_timestamp = int(
        song_start_timestamp
        + (current_song["duration"] / 1000.0)
    )

    # Paksa lirik diperiksa kembali setelah seek.
    last_line = None


def smoothly_correct_clock(
    song: dict[str, Any],
) -> None:
    """
    Mengoreksi drift clock lokal terhadap Spotify.

    Koreksi kecil dilakukan secara halus agar lirik tidak maju-mundur.
    Seek besar akan menggunakan hard sync.
    """

    global base_progress_seconds
    global base_clock_time
    global last_line

    api_progress = song["progress"] / 1000.0
    local_progress = get_local_progress()

    drift = api_progress - local_progress
    absolute_drift = abs(drift)

    # User kemungkinan melakukan seek maju/mundur.
    if absolute_drift >= 1.25:
        if Config.DEBUG:
            print(
                f"[Clock] Hard sync: "
                f"{drift:+.3f}s"
            )

        hard_sync_playback_clock(api_progress)
        return

    # Untuk drift menengah, lakukan koreksi sebagian agar tidak
    # menghasilkan perpindahan lirik yang kasar.
    if absolute_drift >= 0.20:
        correction = drift * 0.35

        corrected_progress = (
            local_progress + correction
        )

        base_progress_seconds = corrected_progress
        base_clock_time = time.perf_counter()

        if Config.DEBUG:
            print(
                f"[Clock] Smooth correction: "
                f"{correction:+.3f}s"
            )


def load_song(
    song: dict[str, Any],
) -> None:
    """
    Memproses lagu baru.

    Clock diaktifkan sebelum request lirik, sehingga waktu yang
    digunakan untuk mengunduh lirik tidak menyebabkan sinkronisasi
    tertinggal.
    """

    global current_song
    global last_song_id
    global last_line
    global discord_has_been_cleared

    current_song = song
    last_song_id = song["id"]
    last_line = None

    reset()
    initialize_playback_clock(song)

    print("\n==============================")
    print(f"🎵 {song['name']}")
    print(f"👤 {song['artist']}")
    print("==============================")

    loaded_lyrics = get_lyrics(
        song["name"],
        song["artist"],
    )

    set_lyrics(loaded_lyrics)

    if not loaded_lyrics:
        print("[Lyrics] No synced lyrics found.")

    discord_has_been_cleared = False


def update_discord_lyrics() -> None:
    """
    Mengecek lirik menggunakan local playback clock.

    Discord hanya menerima update ketika baris tampilan berubah.
    Jika belum ada baris lirik aktif, tampilkan Instrumental.
    """

    global last_line

    if current_song is None:
        return

    current_time = get_local_progress()

    line = get_current_line(current_time)

    display_line = (
        line.strip()
        if isinstance(line, str)
        else ""
    )

    if not display_line:

        display_line = "Instrumental"

    if display_line == last_line:
        return

    last_line = display_line

    print(
        f"[{current_time:07.2f}] "
        f"{display_line}"
    )

    update(
        song=current_song["name"],
        artist=current_song["artist"],
        lyric=display_line,
        start=song_start_timestamp,
        end=song_end_timestamp,
        album_cover=current_song.get("album_cover"),
        album_name=current_song.get("album"),
        spotify_url=current_song.get("spotify_url"),
    )


def handle_spotify_result(
    song: Optional[dict[str, Any]],
) -> None:
    """
    Memproses hasil polling Spotify.
    """

    global current_song
    global last_song_id
    global last_line
    global discord_has_been_cleared
    global empty_poll_count

    if song is None:
        empty_poll_count += 1

        if (
            empty_poll_count
            < EMPTY_POLLS_BEFORE_CLEAR
        ):
            return

        if not discord_has_been_cleared:
            clear()
            discord_has_been_cleared = True

        current_song = None
        last_song_id = None
        last_line = None

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

    # Masih lagu yang sama.
    current_song = song

    smoothly_correct_clock(song)


def main() -> None:
    global last_spotify_poll_time

    print("===================================")
    print(" Spotify Discord Lyrics")
    print("===================================\n")

    spotify_poll_interval = (
        Config.SPOTIFY_REFRESH_RATE
    )

    lyric_refresh_interval = (
        Config.LYRIC_REFRESH_RATE
    )

    while True:
        loop_start = time.perf_counter()
        current_clock = time.perf_counter()

        # Spotify API hanya digunakan untuk:
        # - mendeteksi pergantian lagu;
        # - mendeteksi pause;
        # - memperbaiki drift;
        # - mendeteksi seek.
        if (
            current_clock
            - last_spotify_poll_time
            >= spotify_poll_interval
        ):
            spotify_song = get_current_song()

            handle_spotify_result(
                spotify_song
            )

            last_spotify_poll_time = (
                current_clock
            )

        # Lirik menggunakan local clock dan dapat diperiksa jauh lebih
        # sering daripada Spotify API.
        update_discord_lyrics()

        loop_duration = (
            time.perf_counter() - loop_start
        )

        remaining_sleep = max(
            0.0,
            lyric_refresh_interval
            - loop_duration,
        )

        time.sleep(remaining_sleep)


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print("\n[App] Program stopped.")
        clear()

    except Exception as error:
        print(f"\n[App Error] {error}")
        clear()
        raise