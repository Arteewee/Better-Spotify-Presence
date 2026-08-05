import hashlib
import json
import re
import time
from typing import Any
from urllib.parse import urlparse

from pypresence import Presence
from pypresence.types import ActivityType

from config import Config
from app.logger import logger
from app.event_bus import event_bus


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
    "♩",
    "♬",
    "🎵",
    "🎶",
    "🎼",
    "🎤",
    "🎙",
    "🎙️",
    "🎧",
    "🎸",
    "🎹",
    "🌉",
)

# Alias section. Key harus sudah dalam bentuk normalized.
SECTION_ALIASES = {
    "verse": ("🎙️", "Verse", False),
    "rap verse": ("🎙️", "Rap Verse", False),
    "spoken verse": ("🎙️", "Spoken Verse", False),
    "chorus": ("🎤", "Chorus", False),
    "pre chorus": ("🎶", "Pre-Chorus", False),
    "post chorus": ("🎶", "Post-Chorus", False),
    "hook": ("🎤", "Hook", False),
    "refrain": ("🎤", "Refrain", False),
    "bridge": ("🌉", "Bridge", False),
    "intro": ("🎧", "Intro", False),
    "outro": ("🎧", "Outro", False),
    "opening": ("🎧", "Opening", False),
    "ending": ("🎧", "Ending", False),
    "break": ("🎸", "Break", True),
    "dance break": ("🎵", "Dance Break", True),
    "instrumental break": ("🎼", "Instrumental Break", True),
    "drop": ("🎵", "Drop", True),
    "build up": ("🎶", "Build-Up", True),
    "breakdown": ("🎸", "Breakdown", True),
    "beat switch": ("🎵", "Beat Switch", True),
    "solo": ("🎸", "Solo", True),
    "guitar solo": ("🎸", "Guitar Solo", True),
    "piano solo": ("🎹", "Piano Solo", True),
    "drum solo": ("🥁", "Drum Solo", True),
    "sax solo": ("🎷", "Sax Solo", True),
    "instrumental": ("🎼", "Instrumental", True),
    "interlude": ("🎼", "Interlude", True),
    "music": ("🎼", "Instrumental", True),
    "music break": ("🎼", "Music Break", True),
    "ad lib": ("🎤", "Ad-Lib", False),
    "ad libs": ("🎤", "Ad-Libs", False),
    "choir": ("🎤", "Choir", False),
    "all": ("🎤", "All", False),
}

# Normalisasi variasi section yang umum.
SECTION_NORMALIZATION_ALIASES = {
    "prechorus": "pre chorus",
    "postchorus": "post chorus",
    "build": "build up",
    "buildup": "build up",
    "beat drop": "drop",
    "instrumental solo": "solo",
    "guitar break": "guitar solo",
    "piano break": "piano solo",
    "drum break": "drum solo",
    "saxophone solo": "sax solo",
    "saxophone break": "sax solo",
    "adlib": "ad lib",
    "adlibs": "ad libs",
}

# Wrapper section: [], (), <>, {}, dan 【】.
SECTION_WRAPPER_PATTERN = re.compile(
    r"^\s*[\[\(<{【]?\s*(.*?)\s*[\]\)>}】]?\s*$",
    re.IGNORECASE,
)

# Menangkap nomor/penanda section di akhir.
# Contoh: Verse 2, Verse II, Chorus x2, Verse Two.
SECTION_SUFFIX_PATTERN = re.compile(
    r"^(.*?)"
    r"(?:\s+("
    r"\d+|"
    r"[ivxlcdm]+|"
    r"one|two|three|four|five|six|seven|eight|nine|ten|"
    r"x\s*\d+"
    r"))?$",
    re.IGNORECASE,
)

# Prefix umum seperti "Repeat Chorus" atau "Final Chorus".
SECTION_PREFIX_PATTERN = re.compile(
    r"^(?:"
    r"repeat|final|last|first|second|third|"
    r"main|full|all"
    r")\s+",
    re.IGNORECASE,
)

# Tanda baca/nada yang berarti tidak ada kata lirik.
ONLY_NON_WORD_PATTERN = re.compile(
    r"^[\s.\-–—~_*•·…,:;!?/\\|]+$"
)

ONLY_MUSIC_SYMBOL_PATTERN = re.compile(
    r"^[♪♫♩♬🎵🎶🎼🎸🎹🥁🎷\s.\-–—~_*•·…]+$"
)

# Marker instrumental yang sering dikirim provider.
INSTRUMENTAL_MARKER_PATTERN = re.compile(
    r"^[\[\(<{【]?\s*"
    r"(?:"
    r"instrumental(?:\s+(?:break|section|solo))?|"
    r"interlude|"
    r"music(?:\s+(?:break|playing|only))?|"
    r"no\s+lyrics|"
    r"without\s+lyrics|"
    r"solo|"
    r"guitar\s+solo|"
    r"piano\s+solo|"
    r"drum\s+solo|"
    r"sax(?:ophone)?\s+solo"
    r")"
    r"\s*[\]\)>}】]?$",
    re.IGNORECASE,
)


def is_valid_url(value: Any) -> bool:
    """
    Memastikan value berupa URL HTTP/HTTPS yang valid.
    Tidak melakukan network request.
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
    Merapikan whitespace dan mengubah value menjadi teks.
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
    Menghapus prefix musik yang sudah ada agar tidak menjadi
    prefix ganda.
    """

    cleaned = text.strip()

    prefix_removed = True

    while prefix_removed:
        prefix_removed = False

        for prefix in LYRIC_PREFIXES:
            if cleaned.startswith(prefix):
                cleaned = cleaned[
                    len(prefix):
                ].lstrip()
                prefix_removed = True
                break

    return cleaned


def strip_section_annotation(text: str) -> str:
    """
    Menghapus keterangan performer pada label section.

    Contoh:
        Chorus: Bruno Mars -> Chorus
        Verse - Artist A  -> Verse
    """

    # Colon paling aman sebagai pemisah performer.
    if ":" in text:
        text = text.split(":", 1)[0]

    # Dash hanya dipakai bila bagian kiri sudah terlihat seperti section.
    dash_match = re.match(
        r"^(.+?)\s+[–—]\s+.+$",
        text,
    )

    if dash_match:
        text = dash_match.group(1)

    return normalize_text(text)


def normalize_section_name(
    text: str,
) -> tuple[str, str]:
    """
    Menghasilkan:
        (nama section normalized, suffix tampilan)

    Contoh:
        PRE-CHORUS -> ("pre chorus", "")
        Verse II   -> ("verse", "II")
        Chorus x2  -> ("chorus", "x2")
    """

    normalized = strip_section_annotation(
        text
    ).lower()

    normalized = normalized.replace(
        "_",
        " ",
    )

    normalized = normalized.replace(
        "-",
        " ",
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    normalized = SECTION_PREFIX_PATTERN.sub(
        "",
        normalized,
    ).strip()

    match = SECTION_SUFFIX_PATTERN.match(
        normalized
    )

    if not match:
        return normalized, ""

    base = normalize_text(
        match.group(1)
    )

    suffix = normalize_text(
        match.group(2)
    )

    base = SECTION_NORMALIZATION_ALIASES.get(
        base,
        base,
    )

    return base, suffix


def format_section_suffix(
    suffix: str,
) -> str:
    """
    Merapikan suffix tanpa mengubah makna provider.
    """

    if not suffix:
        return ""

    if suffix.lower().startswith("x"):
        return suffix.lower().replace(
            " ",
            "",
        )

    if suffix.isdigit():
        return suffix

    # Roman numeral / number word.
    return suffix.upper()


def detect_section(
    text: str,
) -> tuple[str, str, bool] | None:
    """
    Better Section Detection.

    Mendukung:
      [Verse 1]
      VERSE II
      (Pre Chorus)
      <Guitar Solo 2>
      [Chorus: Artist]
      Final Chorus
      Chorus x2
    """

    match = SECTION_WRAPPER_PATTERN.match(
        text
    )

    if not match:
        return None

    inner_text = match.group(1)

    section_name, suffix = (
        normalize_section_name(
            inner_text
        )
    )

    section_data = SECTION_ALIASES.get(
        section_name
    )

    if section_data is None:
        return None

    emoji, label, is_instrumental = (
        section_data
    )

    formatted_suffix = (
        format_section_suffix(suffix)
    )

    if formatted_suffix:
        label = (
            f"{label} "
            f"{formatted_suffix}"
        )

    return (
        emoji,
        label,
        is_instrumental,
    )


def is_instrumental_text(
    text: str,
) -> bool:
    """
    Better Instrumental Detection.

    Hanya menandai teks yang benar-benar kosong, berupa simbol,
    atau marker instrumental. Lirik seperti "oh", "la-la-la",
    dan humming tetap dianggap lirik.
    """

    cleaned = normalize_text(text)

    if not cleaned:
        return True

    if ONLY_NON_WORD_PATTERN.fullmatch(
        cleaned
    ):
        return True

    if ONLY_MUSIC_SYMBOL_PATTERN.fullmatch(
        cleaned
    ):
        return True

    if INSTRUMENTAL_MARKER_PATTERN.fullmatch(
        cleaned
    ):
        return True

    # Setelah prefix musik dibuang, pastikan masih ada huruf/angka.
    without_prefix = remove_existing_prefix(
        cleaned
    )

    if not without_prefix:
        return True

    return not bool(
        re.search(
            r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]",
            without_prefix,
        )
    )


def choose_lyric_emoji(text: str) -> str:
    """
    Emoji stabil untuk baris lirik biasa.
    Baris yang sama selalu memakai emoji yang sama.
    """

    emojis = (
        "♫",
        "♪",
        "🎵",
        "🎶",
    )

    checksum = sum(
        ord(character)
        for character in text
    )

    return emojis[
        checksum % len(emojis)
    ]


def format_lyric(
    lyric: Any,
) -> tuple[str, bool, str]:
    """
    Menghasilkan:
    - teks final;
    - status instrumental;
    - tipe tampilan.
    """

    cleaned = normalize_text(lyric)

    # Section dicek sebelum instrumental agar label seperti
    # "Guitar Solo 2" tetap tampil spesifik.
    section = detect_section(cleaned)

    if section:
        emoji, label, is_instrumental = (
            section
        )

        return (
            f"{emoji} {label}",
            is_instrumental,
            "section",
        )

    if is_instrumental_text(cleaned):
        return (
            "🎼 Instrumental",
            True,
            "instrumental",
        )

    cleaned = remove_existing_prefix(
        cleaned
    )

    if not cleaned:
        return (
            "🎼 Instrumental",
            True,
            "instrumental",
        )

    cleaned = truncate_text(
        cleaned,
        MAX_LYRIC_LENGTH - 3,
    )

    emoji = choose_lyric_emoji(
        cleaned
    )

    return (
        f"{emoji} {cleaned}",
        False,
        "lyric",
    )


def build_large_text(
    artist: Any,
    album_name: Any,
) -> str:
    """
    Hover saat mouse diarahkan ke album cover.
    Menampilkan album dan artist.
    """

    album = normalize_text(album_name)
    formatted_artist = format_artist(
        artist
    )

    if album and formatted_artist:
        text = (
            f"💿 {album} • "
            f"👤 {formatted_artist}"
        )

    elif album:
        text = f"💿 {album}"

    elif formatted_artist:
        text = f"👤 {formatted_artist}"

    else:
        text = "Spotify"

    return truncate_text(
        text,
        MAX_TOOLTIP_LENGTH,
    )


def build_small_text(
    is_instrumental: bool,
    display_type: str,
) -> str:
    """
    Hover pada logo Spotify kecil.
    """

    if is_instrumental:
        return "Spotify • Instrumental • By RJH"

    if display_type == "section":
        return "Spotify • Song Section • By RJH"

    return "Spotify • Realtime Lyrics • By RJH"


def canonicalize_payload(
    value: Any,
) -> Any:
    """
    Membuat payload deterministik tanpa mengubah isi visual.
    """

    if isinstance(value, dict):
        return {
            key: canonicalize_payload(
                value[key]
            )
            for key in sorted(value)
        }

    if isinstance(value, (list, tuple)):
        return [
            canonicalize_payload(item)
            for item in value
        ]

    return value


def build_payload_hash(
    payload: dict[str, Any],
) -> str:
    """
    Membuat fingerprint stabil untuk payload Discord.
    """

    serialized = json.dumps(
        canonicalize_payload(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


class DiscordRPC:

    def __init__(self) -> None:

        self.rpc = None
        self.connected = False

        # Fingerprint payload terakhir yang berhasil dikirim.
        self.last_payload_hash: str | None = None

        # Statistik internal untuk Diagnostics Mode.
        self.rpc_updates_sent = 0
        self.rpc_updates_skipped = 0
        self.last_update_time = 0.0

        self.connect()

    def connect(self) -> None:

        try:

            self.rpc = Presence(CLIENT_ID)
            self.rpc.connect()

            self.connected = True

            logger.info(
                "Discord RPC connected",
                category="RPC",
            )

            event_bus.publish(
                "rpc.connected",
                source="rpc",
            )

        except Exception as error:

            logger.error(
                "Discord RPC connection failed",
                category="RPC",
                context={
                    "error": str(error),
                },
            )

            event_bus.publish(
                "rpc.error",
                source="rpc",
                message=str(error),
            )

            event_bus.publish(
                "rpc.disconnected",
                source="rpc",
            )

            self.connected = False

    def reset_cache(self) -> None:

        self.last_payload_hash = None
        self.last_update_time = 0.0

    def clear(self) -> None:

        self.reset_cache()

        if not self.connected:
            return

        try:

            self.rpc.clear()

        except Exception as error:

            logger.error(
                "Discord RPC clear failed",
                category="RPC",
                context={
                    "error": str(error),
                },
            )

            self.connected = False

    def get_status(self) -> dict[str, Any]:
        """
        Statistik RPC untuk Diagnostics Mode.
        """

        return {
            "connected": self.connected,
            "updates_sent": self.rpc_updates_sent,
            "updates_skipped": self.rpc_updates_skipped,
            "last_update_time": self.last_update_time,
        }

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

        (
            display_lyric,
            is_instrumental,
            display_type,
        ) = format_lyric(lyric)

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
                display_type,
            ),
        }

        if start is not None:
            payload["start"] = int(start)

        if end is not None:
            payload["end"] = int(end)

        if is_valid_url(spotify_url):

            clean_spotify_url = (
                spotify_url.strip()
            )

            payload["large_url"] = (
                clean_spotify_url
            )

            payload["details_url"] = (
                clean_spotify_url
            )

            payload["buttons"] = [
                {
                    "label":
                        "🎵 Listen on Spotify",
                    "url":
                        clean_spotify_url,
                },
                {
                    "label":
                        "💻 Source Code",
                    "url":
                        SOURCE_CODE_URL,
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

        payload_hash = build_payload_hash(
            payload
        )

        # Skip payload identik tanpa debounce waktu.
        # Pergantian lirik tetap dikirim seketika.
        if (
            payload_hash
            == self.last_payload_hash
        ):
            self.rpc_updates_skipped += 1
            return

        try:

            self.rpc.update(**payload)

            # Cache baru disimpan setelah update berhasil.
            self.last_payload_hash = payload_hash
            self.rpc_updates_sent += 1
            self.last_update_time = time.monotonic()

            logger.debug(
                "Discord presence updated",
                category="RPC",
                context={
                    "song": str(song),
                    "sent": self.rpc_updates_sent,
                    "skipped": self.rpc_updates_skipped,
                },
            )

        except Exception as error:

            logger.error(
                "Discord RPC update failed",
                category="RPC",
                context={
                    "error": str(error),
                },
            )

            event_bus.publish(
                "rpc.error",
                source="rpc",
                message=str(error),
            )

            event_bus.publish(
                "rpc.disconnected",
                source="rpc",
            )

            self.connected = False

            # Sesudah reconnect, payload penuh harus dikirim kembali.
            self.reset_cache()

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


def get_rpc_status() -> dict[str, Any]:
    """
    Status RPC untuk Diagnostics Mode.
    """

    return rpc.get_status()