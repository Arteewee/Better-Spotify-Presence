import re
import time
from typing import Any
from urllib.parse import urlparse

from pypresence import Presence
from pypresence.types import ActivityType

from config import Config


CLIENT_ID = Config.DISCORD_CLIENT_ID

SPOTIFY_ASSET_KEY = "spotify"

SOURCE_CODE_URL = (
    "https://github.com/Arteewee/Better-Spotify-Presence"
)

# Batas aman agar teks tidak dipotong secara kasar oleh Discord.
MAX_SONG_LENGTH = 100
MAX_LYRIC_LENGTH = 100
MAX_TOOLTIP_LENGTH = 100
MAX_ARTIST_LENGTH = 80

LYRIC_PREFIXES = (
    "♫",
    "♪",
    "🎵",
    "🎶",
    "🎼",
)

SECTION_PATTERN = re.compile(
    r"^[\[\(<{]\s*"
    r"(verse|chorus|bridge|intro|outro|pre-chorus|"
    r"refrain|hook|instrumental|interlude)"
    r"(?:\s*\d+)?"
    r"\s*[\]\)>}]$",
    re.IGNORECASE,
)


def is_valid_url(value: Any) -> bool:
    """
    Memastikan value berupa URL HTTP/HTTPS yang valid.

    Tidak melakukan network request, sehingga tidak menambah delay.
    """

    if not isinstance(value, str):
        return False

    value = value.strip()

    if not value:
        return False

    try:
        parsed = urlparse(value)

        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.netloc)
        )

    except Exception:
        return False


def normalize_text(value: Any) -> str:
    """
    Merapikan spasi dan mengubah value menjadi teks.
    """

    if value is None:
        return ""

    return " ".join(str(value).split())


def truncate_text(
    text: str,
    max_length: int,
) -> str:
    """
    Memotong teks pada batas kata dan menambahkan ...
    hanya jika memang terjadi pemotongan.
    """

    text = normalize_text(text)

    if len(text) <= max_length:
        return text

    shortened = text[: max_length - 3]

    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0]

    return f"{shortened}..."


def format_artist(artist: Any) -> str:
    """
    Format artist seperti tampilan Spotify.

    1 artist:
        Bruno Mars

    2 artist:
        Lady Gaga & Bruno Mars

    3+ artist:
        Metro Boomin, Future & Travis Scott
    """

    artist_text = normalize_text(artist)

    if not artist_text:
        return "Unknown Artist"

    artists = [
        name.strip()
        for name in artist_text.split(",")
        if name.strip()
    ]

    if not artists:
        return "Unknown Artist"

    if len(artists) == 1:
        formatted = artists[0]

    elif len(artists) == 2:
        formatted = f"{artists[0]} & {artists[1]}"

    else:
        formatted = (
            f"{', '.join(artists[:-1])} "
            f"& {artists[-1]}"
        )

    return truncate_text(
        formatted,
        MAX_ARTIST_LENGTH,
    )


def remove_existing_prefix(text: str) -> str:
    """
    Menghapus prefix musik yang sudah ada agar tidak menjadi:
    ♫ ♫ lyric
    """

    cleaned = text.strip()

    while cleaned.startswith(LYRIC_PREFIXES):
        cleaned = cleaned[1:].lstrip()

    return cleaned


def format_section_label(text: str) -> str | None:
    """
    Mengubah label seperti [Chorus] menjadi 🎤 Chorus.
    """

    match = SECTION_PATTERN.match(text)

    if not match:
        return None

    section = match.group(1).replace("-", " ").title()

    if section.lower() in {
        "instrumental",
        "interlude",
    }:
        return "🎼 Instrumental"

    return f"🎤 {section}"


def format_lyric(
    lyric: Any,
) -> tuple[str, bool]:
    """
    Menghasilkan:
    - teks final yang ditampilkan;
    - status apakah bagian tersebut instrumental.
    """

    cleaned = normalize_text(lyric)

    if not cleaned:
        return "🎼 Instrumental", True

    section_label = format_section_label(cleaned)

    if section_label:
        is_instrumental = (
            section_label == "🎼 Instrumental"
        )

        return section_label, is_instrumental

    cleaned = remove_existing_prefix(cleaned)

    if not cleaned:
        return "🎼 Instrumental", True

    cleaned = truncate_text(
        cleaned,
        MAX_LYRIC_LENGTH - 2,
    )

    return f"♫ {cleaned}", False


def build_large_text(
    artist: Any,
    album_name: Any,
) -> str:
    """
    Hover saat mouse diarahkan ke album cover.
    Menampilkan album dan artist.
    """

    album = normalize_text(album_name)
    artist = format_artist(artist)

    if album and artist:
        text = f"💿 {album} • 👤 {artist}"

    elif album:
        text = f"💿 {album}"

    elif artist:
        text = f"👤 {artist}"

    else:
        text = "Spotify"

    return truncate_text(
        text,
        MAX_TOOLTIP_LENGTH,
    )

def build_small_text(
    is_instrumental: bool,
) -> str:
    """
    Hover pada logo Spotify kecil.
    """

    if is_instrumental:
        return "Spotify • Instrumental • By RJH"

    return "Spotify • Realtime Lyrics • By RJH"


class DiscordRPC:

    def __init__(self) -> None:

        self.rpc = None
        self.connected = False

        self.last_payload = None

        self.connect()

    def connect(self) -> None:

        try:

            self.rpc = Presence(CLIENT_ID)
            self.rpc.connect()

            self.connected = True

            print("[Discord] Connected")

        except Exception as error:

            print(
                f"[Discord] Connect error: {error}"
            )

            self.connected = False

    def reset_cache(self) -> None:

        self.last_payload = None

    def clear(self) -> None:

        self.reset_cache()

        if not self.connected:
            return

        try:

            self.rpc.clear()

        except Exception as error:

            print(
                f"[Discord] Clear error: {error}"
            )

            self.connected = False

    def build_payload(
        self,
        song: Any,
        artist: Any,
        lyric: Any = "",
        start: int | None = None,
        end: int | None = None,
        album_cover: Any = None,
        album_name: Any = None,
        spotify_url: Any = None,
    ) -> dict[str, Any]:

        display_lyric, is_instrumental = (
            format_lyric(lyric)
        )

        has_external_cover = is_valid_url(
            album_cover
        )

        if has_external_cover:
            large_image = album_cover.strip()
        else:
            large_image = SPOTIFY_ASSET_KEY

        payload: dict[str, Any] = {
            "activity_type": ActivityType.LISTENING,

            "details": truncate_text(
                normalize_text(song)
                or "Unknown Track",
                MAX_SONG_LENGTH,
            ),

            "state": display_lyric,

            "large_image": large_image,

            "large_text": build_large_text(
                artist,
                album_name,
            ),

            "small_image": SPOTIFY_ASSET_KEY,

            "small_text": build_small_text(
                is_instrumental,
            ),
        }

        if start is not None:
            payload["start"] = int(start)

        if end is not None:
            payload["end"] = int(end)

        if is_valid_url(spotify_url):

            clean_spotify_url = spotify_url.strip()

            payload["large_url"] = clean_spotify_url
            payload["details_url"] = clean_spotify_url

            payload["buttons"] = [
                {
                    "label": "🎵 Listen on Spotify",
                    "url": clean_spotify_url,
                },
                {
                    "label": "💻 Source Code",
                    "url": SOURCE_CODE_URL,
                },
            ]

        return payload

    def update(
        self,
        song: Any,
        artist: Any,
        lyric: Any = "",
        start: int | None = None,
        end: int | None = None,
        album_cover: Any = None,
        album_name: Any = None,
        spotify_url: Any = None,
    ) -> None:

        if not self.connected:

            self.connect()

            if not self.connected:
                return

        payload = self.build_payload(
            song=song,
            artist=artist,
            lyric=lyric,
            start=start,
            end=end,
            album_cover=album_cover,
            album_name=album_name,
            spotify_url=spotify_url,
        )

        if payload == self.last_payload:
            return

        try:

            self.rpc.update(**payload)

            self.last_payload = payload.copy()

        except Exception as error:

            print(
                f"[Discord] Update error: {error}"
            )

            self.connected = False

            time.sleep(2)

            self.connect()


rpc = DiscordRPC()


def update(
    song: Any,
    artist: Any,
    lyric: Any = "",
    start: int | None = None,
    end: int | None = None,
    album_cover: Any = None,
    album_name: Any = None,
    spotify_url: Any = None,
) -> None:

    rpc.update(
        song=song,
        artist=artist,
        lyric=lyric,
        start=start,
        end=end,
        album_cover=album_cover,
        album_name=album_name,
        spotify_url=spotify_url,
    )


def clear() -> None:

    rpc.clear()