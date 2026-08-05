import time

from app.engine import engine


def on_song_changed(data):
    print(
        "[EVENT] Song changed:",
        data
    )


def on_lyrics_changed(data):
    print(
        "[EVENT] Lyrics:",
        data["lyric"]
    )


def on_error(data):
    print(
        "[EVENT] Error:",
        data["message"]
    )


engine.on(
    "song_changed",
    on_song_changed,
)

engine.on(
    "lyrics_changed",
    on_lyrics_changed,
)

engine.on(
    "error",
    on_error,
)

engine.start()

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    engine.shutdown()