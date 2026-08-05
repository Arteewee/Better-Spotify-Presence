import re
import time
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Optional

import requests

from config import Config


@dataclass
class ProviderResult:
    provider: str
    lyrics: list[dict]
    latency: float
    confidence: float = 0.0
    matched_track: str = ""
    matched_artist: str = ""
    matched_duration: float = 0.0


class LyricsProvider(ABC):
    name = "base"

    def __init__(
        self,
        session: requests.Session,
    ) -> None:
        self.session = session

    @abstractmethod
    def fetch(
        self,
        track: str,
        artist: str,
        duration_seconds: Optional[float],
    ) -> ProviderResult:
        raise NotImplementedError


def normalize_match_text(
    value: Any,
) -> str:
    """
    Metadata Matching Engine.

    Menghapus noise umum tanpa menghapus identitas inti lagu.
    """

    text = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(
            character
        )
    ).lower()

    text = re.sub(
        r"\([^)]*\)|\[[^\]]*\]",
        " ",
        text,
    )

    text = re.sub(
        r"\b(?:"
        r"official|audio|video|lyrics?|"
        r"visualizer|remaster(?:ed)?|"
        r"deluxe|explicit|clean|"
        r"radio edit|single version|"
        r"album version|live"
        r")\b",
        " ",
        text,
    )

    text = re.sub(
        r"\b(?:feat|ft|featuring)\.?\b",
        " ",
        text,
    )

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    return " ".join(
        text.split()
    )


def token_set(
    value: Any,
) -> set[str]:
    return set(
        normalize_match_text(
            value
        ).split()
    )


def sequence_similarity(
    left: Any,
    right: Any,
) -> float:
    left_text = normalize_match_text(
        left
    )

    right_text = normalize_match_text(
        right
    )

    if not left_text or not right_text:
        return 0.0

    return SequenceMatcher(
        None,
        left_text,
        right_text,
    ).ratio()


def token_similarity(
    left: Any,
    right: Any,
) -> float:
    left_tokens = token_set(left)
    right_tokens = token_set(right)

    if not left_tokens or not right_tokens:
        return 0.0

    intersection = len(
        left_tokens & right_tokens
    )

    union = len(
        left_tokens | right_tokens
    )

    return (
        intersection / union
        if union
        else 0.0
    )


def field_similarity(
    left: Any,
    right: Any,
) -> float:
    """
    Menggabungkan sequence ratio dan token overlap.
    """

    return (
        sequence_similarity(
            left,
            right,
        ) * 0.65
        + token_similarity(
            left,
            right,
        ) * 0.35
    )


def duration_similarity(
    expected: Optional[float],
    actual: Optional[float],
) -> float:
    if not expected or not actual:
        return 0.75

    difference = abs(
        float(expected)
        - float(actual)
    )

    if difference <= 1.5:
        return 1.0

    if difference <= 3.0:
        return 0.95

    if difference <= 6.0:
        return 0.85

    if difference <= 10.0:
        return 0.65

    if difference <= 15.0:
        return 0.35

    return 0.0


def calculate_confidence(
    requested_track: str,
    requested_artist: str,
    requested_duration: Optional[float],
    candidate_track: Any,
    candidate_artist: Any,
    candidate_duration: Any,
) -> float:
    title_score = field_similarity(
        requested_track,
        candidate_track,
    )

    artist_score = field_similarity(
        requested_artist,
        candidate_artist,
    )

    duration_score = duration_similarity(
        requested_duration,
        (
            float(candidate_duration)
            if candidate_duration
            else None
        ),
    )

    # Judul harus memiliki bobot terbesar.
    score = (
        title_score * 0.58
        + artist_score * 0.27
        + duration_score * 0.15
    )

    # Guard agar kandidat dengan title sangat rendah tidak lolos
    # hanya karena durasi kebetulan sama.
    if title_score < 0.45:
        score *= 0.55

    if artist_score < 0.25:
        score *= 0.75

    return max(
        0.0,
        min(
            score,
            1.0,
        ),
    )


def parse_lrc(
    lrc_text: str,
) -> list[dict]:
    lyrics: list[dict] = []

    pattern = re.compile(
        r"\[(\d+):"
        r"(\d+(?:\.\d+)?)\]"
        r"(.*)"
    )

    for line in lrc_text.splitlines():
        match = pattern.match(
            line
        )

        if not match:
            continue

        lyrics.append(
            {
                "time": (
                    int(match.group(1))
                    * 60
                    + float(
                        match.group(2)
                    )
                ),
                "text": (
                    match.group(3)
                    .strip()
                ),
            }
        )

    lyrics.sort(
        key=lambda item: item["time"]
    )

    return lyrics


class LRCLIBExactProvider(
    LyricsProvider
):
    name = "lrclib_exact"

    def fetch(
        self,
        track: str,
        artist: str,
        duration_seconds: Optional[float],
    ) -> ProviderResult:
        started = time.perf_counter()

        params: dict[str, Any] = {
            "track_name": track,
            "artist_name": artist,
        }

        if duration_seconds:
            params["duration"] = round(
                duration_seconds
            )

        response = self.session.get(
            Config.LRCLIB_GET_URL,
            params=params,
            timeout=(
                Config.LYRICS_PROVIDER_TIMEOUT
            ),
        )

        latency = (
            time.perf_counter()
            - started
        )

        if response.status_code == 404:
            return ProviderResult(
                self.name,
                [],
                latency,
            )

        response.raise_for_status()

        data = response.json()
        synced = data.get(
            "syncedLyrics"
        )

        lyrics = (
            parse_lrc(synced)
            if synced
            else []
        )

        confidence = calculate_confidence(
            track,
            artist,
            duration_seconds,
            data.get("trackName", track),
            data.get("artistName", artist),
            data.get(
                "duration",
                duration_seconds,
            ),
        )

        return ProviderResult(
            provider=self.name,
            lyrics=lyrics,
            latency=latency,
            confidence=(
                confidence
                if lyrics
                else 0.0
            ),
            matched_track=str(
                data.get(
                    "trackName",
                    "",
                )
            ),
            matched_artist=str(
                data.get(
                    "artistName",
                    "",
                )
            ),
            matched_duration=float(
                data.get(
                    "duration",
                    0.0,
                )
                or 0.0
            ),
        )


class LRCLIBSearchProvider(
    LyricsProvider
):
    name = "lrclib_search"

    def fetch(
        self,
        track: str,
        artist: str,
        duration_seconds: Optional[float],
    ) -> ProviderResult:
        started = time.perf_counter()

        response = self.session.get(
            Config.LRCLIB_SEARCH_URL,
            params={
                "track_name": track,
                "artist_name": artist,
            },
            timeout=(
                Config.LYRICS_PROVIDER_TIMEOUT
            ),
        )

        latency = (
            time.perf_counter()
            - started
        )

        response.raise_for_status()

        records = response.json()

        if not isinstance(records, list):
            return ProviderResult(
                self.name,
                [],
                latency,
            )

        best_record = None
        best_score = 0.0

        for record in records:
            if not record.get(
                "syncedLyrics"
            ):
                continue

            score = calculate_confidence(
                track,
                artist,
                duration_seconds,
                record.get("trackName"),
                record.get("artistName"),
                record.get("duration"),
            )

            if score > best_score:
                best_score = score
                best_record = record

        if (
            best_record is None
            or best_score
            < Config.LYRICS_MIN_CONFIDENCE
        ):
            return ProviderResult(
                self.name,
                [],
                latency,
                best_score,
            )

        lyrics = parse_lrc(
            best_record["syncedLyrics"]
        )

        return ProviderResult(
            provider=self.name,
            lyrics=lyrics,
            latency=latency,
            confidence=best_score,
            matched_track=str(
                best_record.get(
                    "trackName",
                    "",
                )
            ),
            matched_artist=str(
                best_record.get(
                    "artistName",
                    "",
                )
            ),
            matched_duration=float(
                best_record.get(
                    "duration",
                    0.0,
                )
                or 0.0
            ),
        )


class NetEaseProvider(
    LyricsProvider
):
    name = "netease"

    def fetch(
        self,
        track: str,
        artist: str,
        duration_seconds: Optional[float],
    ) -> ProviderResult:
        started = time.perf_counter()

        base_url = (
            Config.NETEASE_API_BASE_URL
            .rstrip("/")
        )

        response = self.session.get(
            f"{base_url}/cloudsearch",
            params={
                "keywords": (
                    f"{track} {artist}"
                ),
                "limit": 8,
                "type": 1,
            },
            timeout=(
                Config.LYRICS_PROVIDER_TIMEOUT
            ),
        )

        response.raise_for_status()

        payload = response.json()

        songs = (
            payload.get("result", {})
            .get("songs", [])
        )

        best_song = None
        best_score = 0.0

        for song in songs:
            song_artists = ", ".join(
                item.get("name", "")
                for item in song.get(
                    "ar",
                    song.get(
                        "artists",
                        [],
                    ),
                )
            )

            song_duration_ms = song.get(
                "dt",
                song.get("duration"),
            )

            song_duration = (
                float(song_duration_ms)
                / 1000.0
                if song_duration_ms
                else None
            )

            score = calculate_confidence(
                track,
                artist,
                duration_seconds,
                song.get("name"),
                song_artists,
                song_duration,
            )

            if score > best_score:
                best_score = score
                best_song = song

        if (
            best_song is None
            or best_score
            < Config.LYRICS_MIN_CONFIDENCE
        ):
            return ProviderResult(
                self.name,
                [],
                (
                    time.perf_counter()
                    - started
                ),
                best_score,
            )

        lyric_response = self.session.get(
            f"{base_url}/lyric",
            params={
                "id": best_song["id"]
            },
            timeout=(
                Config.LYRICS_PROVIDER_TIMEOUT
            ),
        )

        lyric_response.raise_for_status()

        lyric_payload = (
            lyric_response.json()
        )

        lrc_text = (
            lyric_payload.get("lrc", {})
            .get("lyric")
        )

        lyrics = (
            parse_lrc(lrc_text)
            if lrc_text
            else []
        )

        return ProviderResult(
            provider=self.name,
            lyrics=lyrics,
            latency=(
                time.perf_counter()
                - started
            ),
            confidence=best_score,
            matched_track=str(
                best_song.get(
                    "name",
                    "",
                )
            ),
            matched_artist=", ".join(
                item.get("name", "")
                for item in best_song.get(
                    "ar",
                    best_song.get(
                        "artists",
                        [],
                    ),
                )
            ),
            matched_duration=(
                float(
                    best_song.get(
                        "dt",
                        best_song.get(
                            "duration",
                            0,
                        ),
                    )
                    or 0
                )
                / 1000.0
            ),
        )


def build_providers(
    session: requests.Session,
) -> list[LyricsProvider]:
    providers: list[LyricsProvider] = [
        LRCLIBExactProvider(session),
        LRCLIBSearchProvider(session),
    ]

    if Config.NETEASE_API_BASE_URL:
        providers.append(
            NetEaseProvider(session)
        )

    return providers