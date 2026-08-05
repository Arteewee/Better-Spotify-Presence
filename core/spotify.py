import time
import requests

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Any, Optional

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

from config import Config
from app.logger import logger
from app.event_bus import event_bus
from core.state_store import (
    load_state,
    remove_state_keys,
    update_state,
)
from core.utils import clean_title


ACTIVE_PROFILE = getattr(
    Config,
    "ACTIVE_SPOTIFY_PROFILE",
    "primary",
)

RATE_LIMIT_UNTIL_KEY = (
    f"spotify_{ACTIVE_PROFILE}_rate_limit_until"
)

RATE_LIMIT_REASON_KEY = (
    f"spotify_{ACTIVE_PROFILE}_rate_limit_reason"
)

RATE_LIMIT_UPDATED_KEY = (
    f"spotify_{ACTIVE_PROFILE}_rate_limit_updated_at"
)


class SpotifyClient:
    """
    Spotify metadata poller dengan:

    - anti flick-back;
    - local song cache;
    - manual 429 handling;
    - persistent Retry-After cooldown;
    - tanpa automatic Spotify retry.

    Playback realtime tetap dihitung oleh main.py.
    """

    def __init__(self) -> None:
        # Custom HTTP session tanpa retry otomatis.
        # Tujuannya supaya HTTP 429 asli beserta header Retry-After
        # langsung diterima oleh aplikasi kita.
        self.http_session = requests.Session()

        no_retry = Retry(
            total=0,
            connect=0,
            read=0,
            redirect=0,
            status=0,
            other=0,
            backoff_factor=0,
            status_forcelist=(),
            allowed_methods=None,
            respect_retry_after_header=False,
            raise_on_status=False,
        )

        adapter = HTTPAdapter(
            max_retries=no_retry
        )

        self.http_session.mount(
            "https://",
            adapter
        )

        self.http_session.mount(
            "http://",
            adapter
        )

        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=(
                    Config.SPOTIFY_CLIENT_ID
                ),
                client_secret=(
                    Config.SPOTIFY_CLIENT_SECRET
                ),
                redirect_uri=(
                    Config.SPOTIFY_REDIRECT_URI
                ),
                scope=(
                    "user-read-currently-playing "
                    "user-read-playback-state"
                ),
                cache_path=getattr(
                    Config,
                    "SPOTIFY_TOKEN_CACHE_PATH",
                    None,
                ),
                open_browser=True,
            ),
            requests_session=self.http_session,
            requests_timeout=(
                Config.REQUEST_TIMEOUT
            ),
        )

        self.current_song: Optional[
            dict[str, Any]
        ] = None

        self.previous_song: Optional[
            dict[str, Any]
        ] = None

        self.last_change_time = 0.0
        self.debounce_time = 0.8

        # Disimpan sebagai Unix timestamp agar bertahan
        # setelah aplikasi/PC restart.
        self.rate_limit_until_unix = 0.0

        self.rate_limit_reason: Optional[
            str
        ] = None

        self.last_error: Optional[str] = None
        self.last_successful_request = 0.0

        # Runtime dashboard counters.
        self.request_attempts = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.rate_limit_count = 0
        self.cached_returns = 0

        self._cooldown_message_printed = False

        logger.info(
            "Spotify client initialized",
            category="SPOTIFY",
            context={
                "profile": ACTIVE_PROFILE,
            },
        )

        event_bus.publish(
            "spotify.connected",
            source="spotify",
            profile=ACTIVE_PROFILE,
        )

        self._restore_rate_limit_state()

    def _restore_rate_limit_state(
        self,
    ) -> None:
        """
        Memuat cooldown Spotify dari file lokal.
        """

        state = load_state()

        try:
            persisted_until = float(
                state.get(
                    RATE_LIMIT_UNTIL_KEY,
                    0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            persisted_until = 0.0

        persisted_reason = state.get(
            RATE_LIMIT_REASON_KEY
        )

        now = time.time()

        if persisted_until > now:
            self.rate_limit_until_unix = (
                persisted_until
            )

            if persisted_reason:
                self.rate_limit_reason = str(
                    persisted_reason
                )

            remaining = (
                self.get_rate_limit_remaining()
            )

            logger.warning(
                "Restored active Spotify rate-limit cooldown",
                category="SPOTIFY",
                context={
                    "retry_after": remaining,
                    "reason": (
                        self.rate_limit_reason
                        or "unknown"
                    ),
                },
            )

            self._cooldown_message_printed = (
                True
            )

        else:
            self._clear_persisted_cooldown()

    def _persist_cooldown(self) -> None:
        update_state(
            **{
                RATE_LIMIT_UNTIL_KEY:
                    self.rate_limit_until_unix,

                RATE_LIMIT_REASON_KEY:
                    self.rate_limit_reason,

                RATE_LIMIT_UPDATED_KEY:
                    time.time(),
            }
        )

    def _clear_persisted_cooldown(
        self,
    ) -> None:
        remove_state_keys(
            RATE_LIMIT_UNTIL_KEY,
            RATE_LIMIT_REASON_KEY,
            RATE_LIMIT_UPDATED_KEY,
        )

    @staticmethod
    def _build_song(
        playback: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        item = playback.get("item")

        if item is None:
            return None

        artists = ", ".join(
            artist["name"]
            for artist in item.get(
                "artists",
                [],
            )
            if artist.get("name")
        )

        album = item.get("album") or {}
        images = album.get("images") or []

        album_cover = (
            images[0].get("url")
            if images
            else None
        )

        external_urls = (
            item.get("external_urls") or {}
        )

        return {
            "id": item.get("id"),

            "name": clean_title(
                item.get("name", "")
            ),

            "original_name": item.get(
                "name",
                "",
            ),

            "artist": artists,

            "album": album.get(
                "name",
                "",
            ),

            "duration": int(
                item.get(
                    "duration_ms",
                    0,
                )
            ),

            "progress": int(
                playback.get(
                    "progress_ms",
                    0,
                )
            ),

            "spotify_url": (
                external_urls.get(
                    "spotify"
                )
            ),

            "album_cover": album_cover,

            "is_playing": bool(
                playback.get(
                    "is_playing",
                    False,
                )
            ),

            "_from_cache": False,
            "_rate_limited": False,
        }

    def _cached_song(
        self,
        *,
        rate_limited: bool = False,
    ) -> Optional[dict[str, Any]]:
        if self.current_song is None:
            return None

        cached = self.current_song.copy()

        self.cached_returns += 1

        cached["_from_cache"] = True
        cached["_rate_limited"] = (
            rate_limited
        )

        return cached

    @staticmethod
    def _header_value(
        headers: Any,
        key: str,
    ) -> Optional[str]:
        if not headers:
            return None

        try:
            for header_key, value in (
                headers.items()
            ):
                if (
                    str(header_key).lower()
                    == key.lower()
                ):
                    return str(value)

        except Exception:
            return None

        return None

    def _extract_retry_after(
        self,
        error: SpotifyException,
    ) -> int:
        retry_after_value = (
            self._header_value(
                getattr(
                    error,
                    "headers",
                    None,
                ),
                "Retry-After",
            )
        )

        try:
            retry_after = int(
                float(retry_after_value)
            )

        except (
            TypeError,
            ValueError,
        ):
            retry_after = (
                Config.DEFAULT_RATE_LIMIT_SECONDS
            )

        return max(
            1,
            min(
                retry_after,
                Config.MAX_RATE_LIMIT_SECONDS,
            ),
        )

    @staticmethod
    def _extract_reason(
        error: SpotifyException,
    ) -> Optional[str]:
        reason = getattr(
            error,
            "reason",
            None,
        )

        if reason:
            return str(reason)

        message = getattr(
            error,
            "msg",
            None,
        )

        if message:
            return str(message)

        return None

    def _activate_rate_limit(
        self,
        error: SpotifyException,
    ) -> None:
        retry_after = (
            self._extract_retry_after(error)
        )

        self.rate_limit_count += 1

        self.rate_limit_until_unix = (
            time.time()
            + retry_after
        )

        self.rate_limit_reason = (
            self._extract_reason(error)
        )

        self.last_error = (
            f"Spotify rate limited for "
            f"{retry_after} seconds"
        )

        self._persist_cooldown()

        logger.warning(
            "Spotify rate limit active",
            category="SPOTIFY",
            context={
                "retry_after": retry_after,
                "reason": (
                    self.rate_limit_reason
                    or "unknown"
                ),
                "profile": ACTIVE_PROFILE,
            },
        )

        event_bus.publish(
            "spotify.rate_limit",
            source="spotify",
            retry_after=retry_after,
            reason=(
                self.rate_limit_reason
                or "unknown"
            ),
            profile=ACTIVE_PROFILE,
        )

        self._cooldown_message_printed = True

    def is_rate_limited(self) -> bool:
        return (
            time.time()
            < self.rate_limit_until_unix
        )

    def get_rate_limit_remaining(
        self,
    ) -> int:
        remaining = (
            self.rate_limit_until_unix
            - time.time()
        )

        return max(
            0,
            int(remaining),
        )

    def _finish_cooldown(self) -> None:
        if self.rate_limit_until_unix <= 0:
            return

        self.rate_limit_until_unix = 0.0
        self.rate_limit_reason = None
        self._cooldown_message_printed = False

        self._clear_persisted_cooldown()

        logger.info(
            "Spotify rate-limit cooldown ended",
            category="SPOTIFY",
            context={
                "profile": ACTIVE_PROFILE,
            },
        )

        event_bus.publish(
            "spotify.connected",
            source="spotify",
            profile=ACTIVE_PROFILE,
        )

        event_bus.publish(
            "notification.show",
            source="spotify",
            level="success",
            title="Spotify Reconnected",
            message="Spotify API cooldown has ended.",
            duration=3500,
        )

    def get_status(self) -> dict[str, Any]:
        return {
            "active_profile":
                ACTIVE_PROFILE,

            "rate_limited":
                self.is_rate_limited(),

            "retry_after":
                self.get_rate_limit_remaining(),

            "rate_limit_reason":
                self.rate_limit_reason,

            "last_error":
                self.last_error,

            "last_successful_request":
                self.last_successful_request,

            "request_attempts":
                self.request_attempts,

            "successful_requests":
                self.successful_requests,

            "failed_requests":
                self.failed_requests,

            "rate_limit_count":
                self.rate_limit_count,

            "cached_returns":
                self.cached_returns,
        }


    def get_current_song(
        self,
    ) -> Optional[dict[str, Any]]:
        """
        Selama cooldown aktif, fungsi langsung mengembalikan
        cache tanpa melakukan network request.
        """

        if self.is_rate_limited():
            if (
                not self._cooldown_message_printed
            ):
                logger.debug(
                    "Spotify API requests paused during cooldown",
                    category="SPOTIFY",
                )

                self._cooldown_message_printed = (
                    True
                )

            return self._cached_song(
                rate_limited=True
            )

        if self.rate_limit_until_unix > 0:
            self._finish_cooldown()

        try:
            self.request_attempts += 1

            playback = (
                self.sp
                .current_user_playing_track()
            )

            self.successful_requests += 1

            self.last_successful_request = (
                time.time()
            )

            logger.debug(
                "Spotify playback request succeeded",
                category="SPOTIFY",
                context={
                    "attempt": self.request_attempts,
                    "profile": ACTIVE_PROFILE,
                },
            )

            event_bus.publish(
                "spotify.connected",
                source="spotify",
                profile=ACTIVE_PROFILE,
            )

            self.last_error = None
            self.rate_limit_reason = None

            if playback is None:
                return None

            if not playback.get(
                "is_playing",
                False,
            ):
                return None

            song = self._build_song(playback)

            if (
                song is None
                or not song.get("id")
            ):
                return None

            if self.current_song is None:
                self.current_song = song

                return song.copy()

            if (
                song["id"]
                == self.current_song["id"]
            ):
                self.current_song = song

                return song.copy()

            now = time.monotonic()

            is_previous_song = (
                self.previous_song is not None

                and song["id"]
                == self.previous_song["id"]
            )

            is_inside_debounce = (
                now - self.last_change_time
            ) < self.debounce_time

            looks_like_old_response = (
                song["progress"] > 3000
            )

            if (
                is_previous_song
                and is_inside_debounce
                and looks_like_old_response
            ):
                return self._cached_song()

            logger.info(
                "Spotify song changed",
                category="SPOTIFY",
                context={
                    "song": song["name"],
                    "artist": song.get(
                        "artist",
                        "",
                    ),
                },
            )

            self.previous_song = (
                self.current_song
            )

            self.current_song = song
            self.last_change_time = now

            return song.copy()

        except SpotifyException as error:
            self.failed_requests += 1

            http_status = getattr(
                error,
                "http_status",
                None,
            )

            if http_status == 429:
                self._activate_rate_limit(
                    error
                )

                return self._cached_song(
                    rate_limited=True
                )

            self.last_error = str(error)

            logger.error(
                "Spotify API error",
                category="SPOTIFY",
                context={
                    "error": str(error),
                    "profile": ACTIVE_PROFILE,
                },
            )

            event_bus.publish(
                "spotify.error",
                source="spotify",
                message=str(error),
                profile=ACTIVE_PROFILE,
            )

            return self._cached_song()

        except Exception as error:
            self.failed_requests += 1
            self.last_error = str(error)

            logger.error(
                "Unexpected Spotify error",
                category="SPOTIFY",
                context={
                    "error": str(error),
                    "profile": ACTIVE_PROFILE,
                },
            )

            event_bus.publish(
                "spotify.error",
                source="spotify",
                message=str(error),
                profile=ACTIVE_PROFILE,
            )

            # Error sudah dicatat dan dipublish di atas.

            return self._cached_song()


spotify = SpotifyClient()


def get_current_song() -> Optional[
    dict[str, Any]
]:
    return spotify.get_current_song()


def get_spotify_status() -> dict[str, Any]:
    return spotify.get_status()