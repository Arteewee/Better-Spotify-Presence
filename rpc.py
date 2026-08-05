import time
from urllib.parse import urlparse

from pypresence import Presence
from pypresence.types import ActivityType

from config import Config


CLIENT_ID = Config.DISCORD_CLIENT_ID

SPOTIFY_ASSET_KEY = "spotify"

SOURCE_CODE_URL = (
    "https://github.com/Arteewee/Better-Spotify-Presence"
)


def is_valid_external_image(url):
    """
    Validasi ringan URL cover.

    Tidak mengunduh gambar, jadi tidak menambah delay.
    Jika URL kosong atau formatnya bukan HTTP/HTTPS,
    RPC akan memakai asset Spotify sebagai fallback.
    """

    if not isinstance(url, str) or not url.strip():
        return False

    try:
        parsed = urlparse(url.strip())

        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.netloc)
        )

    except Exception:
        return False


class DiscordRPC:

    def __init__(self):

        self.rpc = None
        self.connected = False

        self.last_payload = None

        self.connect()

    def connect(self):

        try:

            self.rpc = Presence(CLIENT_ID)
            self.rpc.connect()

            self.connected = True

            print("[Discord] Connected")

        except Exception as error:

            print(f"[Discord] Connect error: {error}")

            self.connected = False

    def reset_cache(self):

        self.last_payload = None

    def clear(self):

        self.reset_cache()

        if not self.connected:
            return

        try:

            self.rpc.clear()

        except Exception as error:

            print(f"[Discord] Clear error: {error}")

            self.connected = False

    def update(
        self,
        song,
        artist,
        lyric="Instrumental",
        start=None,
        end=None,
        album_cover=None,
        album_name=None,
        spotify_url=None
    ):

        if not self.connected:

            self.connect()

            if not self.connected:
                return

        if is_valid_external_image(album_cover):

            large_image = album_cover.strip()

        else:

            large_image = SPOTIFY_ASSET_KEY

        if artist and album_name:

            large_text = f"{artist} • {album_name}"

        elif artist:

            large_text = artist

        elif album_name:

            large_text = album_name

        else:

            large_text = "Spotify"

        display_lyric = (
            lyric.strip()
            if isinstance(lyric, str)
            else ""
        )

        if not display_lyric:

            display_lyric = "Instrumental"

        payload = {

            "activity_type": ActivityType.LISTENING,

            "details": song,

            "state": display_lyric,

            "large_image": large_image,

            "large_text": large_text,

            "small_image": SPOTIFY_ASSET_KEY,

            "small_text": "Spotify • Live Lyrics by RJH",

        }

        if start is not None:

            payload["start"] = int(start)

        if end is not None:

            payload["end"] = int(end)

        if spotify_url:

            payload["large_url"] = spotify_url
            payload["details_url"] = spotify_url

            payload["buttons"] = [
                {
                    "label": "🎵 Listen on Spotify",
                    "url": spotify_url
                },
                {
                    "label": "💻 Source Code",
                    "url": SOURCE_CODE_URL
                }
            ]

        if payload == self.last_payload:
            return

        try:

            self.rpc.update(**payload)

            self.last_payload = payload.copy()

        except Exception as error:

            print(f"[Discord] Update error: {error}")

            self.connected = False

            time.sleep(2)

            self.connect()


rpc = DiscordRPC()


def update(
    song,
    artist,
    lyric="Instrumental",
    start=None,
    end=None,
    album_cover=None,
    album_name=None,
    spotify_url=None
):

    rpc.update(
        song=song,
        artist=artist,
        lyric=lyric,
        start=start,
        end=end,
        album_cover=album_cover,
        album_name=album_name,
        spotify_url=spotify_url
    )


def clear():

    rpc.clear()