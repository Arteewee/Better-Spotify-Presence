from datetime import datetime
from typing import Any

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.engine import engine


class DashboardWindow(QWidget):
    """
    Live Runtime Dashboard Spotify+.

    Seluruh data berasal dari state lokal engine dan tidak menambah
    request Spotify, lyrics provider, maupun Discord RPC.
    """

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(
            "Spotify+ Runtime Dashboard"
        )

        self.setMinimumSize(
            760,
            680,
        )

        self.resize(
            880,
            760,
        )

        self.value_labels: dict[
            str,
            QLabel,
        ] = {}

        self._build_ui()
        self._apply_styles()

        self.timer = QTimer(
            self
        )

        self.timer.setInterval(
            500
        )

        self.timer.timeout.connect(
            self.refresh
        )

        self.timer.start()

        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        root.setSpacing(
            14
        )

        title = QLabel(
            "Live Runtime Dashboard"
        )

        title.setObjectName(
            "pageTitle"
        )

        subtitle = QLabel(
            "Local runtime metrics — no additional API requests"
        )

        subtitle.setObjectName(
            "mutedText"
        )

        root.addWidget(
            title
        )

        root.addWidget(
            subtitle
        )

        scroll = QScrollArea()

        scroll.setWidgetResizable(
            True
        )

        scroll.setFrameShape(
            QScrollArea.Shape.NoFrame
        )

        content = QWidget()
        layout = QVBoxLayout(
            content
        )

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setSpacing(
            14
        )

        layout.addWidget(
            self._create_card(
                "SPOTIFY API",
                [
                    ("Profile", "profile"),
                    ("Status", "spotify_status"),
                    ("Normal polling", "spotify_polling"),
                    ("Fast polling", "spotify_fast_polling"),
                    ("Request attempts", "spotify_request_attempts"),
                    ("Successful", "spotify_successful_requests"),
                    ("Failed", "spotify_failed_requests"),
                    ("Rate limits", "spotify_rate_limit_count"),
                    ("Cached returns", "spotify_cached_returns"),
                    ("Last success", "spotify_last_success"),
                ],
            )
        )

        layout.addWidget(
            self._create_card(
                "LYRICS",
                [
                    ("Provider", "lyrics_provider"),
                    ("Confidence", "lyrics_confidence"),
                    ("Latency", "lyrics_latency"),
                    ("Cache source", "cache_source"),
                    ("Provider success", "provider_successes"),
                    ("Provider failure", "provider_failures"),
                    ("Provider timeout", "provider_timeouts"),
                    ("Memory entries", "memory_cache_entries"),
                    ("Memory hit rate", "memory_cache_hit_rate"),
                    ("Offline entries", "offline_cache_entries"),
                    ("Offline hit rate", "persistent_cache_hit_rate"),
                ],
            )
        )

        layout.addWidget(
            self._create_rpc_card()
        )

        layout.addWidget(
            self._create_card(
                "ENGINE",
                [
                    ("State", "engine_state"),
                    ("Uptime", "uptime"),
                    ("Target loop", "target_loop_hz"),
                    ("Loop count", "loop_count"),
                    ("Last loop", "loop_last_ms"),
                    ("Average loop", "loop_average_ms"),
                    ("Maximum loop", "loop_max_ms"),
                    ("Current song", "song"),
                ],
            )
        )

        layout.addStretch()

        scroll.setWidget(
            content
        )

        root.addWidget(
            scroll,
            1,
        )

    def _create_card(
        self,
        title_text: str,
        items: list[tuple[str, str]],
    ) -> QFrame:
        card = QFrame()

        card.setObjectName(
            "dashboardCard"
        )

        card_layout = QVBoxLayout(
            card
        )

        heading = QLabel(
            title_text
        )

        heading.setObjectName(
            "sectionTitle"
        )

        card_layout.addWidget(
            heading
        )

        grid = QGridLayout()

        grid.setHorizontalSpacing(
            26
        )

        grid.setVerticalSpacing(
            10
        )

        for index, (
            label_text,
            key,
        ) in enumerate(items):
            row = index // 2
            column = (
                index % 2
            ) * 2

            label = QLabel(
                label_text
            )

            label.setObjectName(
                "mutedText"
            )

            value = QLabel(
                "—"
            )

            value.setObjectName(
                "metricValue"
            )

            value.setTextInteractionFlags(
                Qt.TextInteractionFlag
                .TextSelectableByMouse
            )

            self.value_labels[
                key
            ] = value

            grid.addWidget(
                label,
                row,
                column,
            )

            grid.addWidget(
                value,
                row,
                column + 1,
            )

        card_layout.addLayout(
            grid
        )

        return card

    def _create_rpc_card(
        self,
    ) -> QFrame:
        card = self._create_card(
            "DISCORD RPC",
            [
                ("Connection", "rpc_connection"),
                ("Updates sent", "rpc_updates_sent"),
                ("Updates skipped", "rpc_updates_skipped"),
                ("Optimization", "rpc_optimization_rate"),
            ],
        )

        self.optimization_bar = QProgressBar()

        self.optimization_bar.setRange(
            0,
            1000,
        )

        self.optimization_bar.setTextVisible(
            False
        )

        card.layout().addWidget(
            self.optimization_bar
        )

        return card

    def refresh(self) -> None:
        try:
            status = engine.get_status()

            rate_limited = bool(
                status.get(
                    "rate_limited",
                    False,
                )
            )

            retry_after = int(
                status.get(
                    "retry_after",
                    0,
                )
                or 0
            )

            spotify_status = (
                f"Cooldown {self.format_duration(retry_after)}"
                if rate_limited
                else "Connected"
            )

            running = bool(
                status.get(
                    "running",
                    False,
                )
            )

            paused = bool(
                status.get(
                    "paused",
                    False,
                )
            )

            engine_state = (
                "Paused"
                if running and paused
                else (
                    "Running"
                    if running
                    else "Stopped"
                )
            )

            last_success = float(
                status.get(
                    "spotify_last_successful_request",
                    0.0,
                )
                or 0.0
            )

            values: dict[
                str,
                Any,
            ] = {
                "profile":
                    status.get(
                        "profile",
                        "—",
                    ),

                "spotify_status":
                    spotify_status,

                "spotify_polling":
                    f"{status.get('spotify_polling', 0):.1f}s",

                "spotify_fast_polling":
                    f"{status.get('spotify_fast_polling', 0):.1f}s",

                "spotify_request_attempts":
                    status.get(
                        "spotify_request_attempts",
                        0,
                    ),

                "spotify_successful_requests":
                    status.get(
                        "spotify_successful_requests",
                        0,
                    ),

                "spotify_failed_requests":
                    status.get(
                        "spotify_failed_requests",
                        0,
                    ),

                "spotify_rate_limit_count":
                    status.get(
                        "spotify_rate_limit_count",
                        0,
                    ),

                "spotify_cached_returns":
                    status.get(
                        "spotify_cached_returns",
                        0,
                    ),

                "spotify_last_success":
                    (
                        datetime.fromtimestamp(
                            last_success
                        ).strftime(
                            "%H:%M:%S"
                        )
                        if last_success
                        else "—"
                    ),

                "lyrics_provider":
                    status.get(
                        "lyrics_provider"
                    )
                    or "—",

                "lyrics_confidence":
                    f"{float(status.get('lyrics_confidence', 0) or 0):.0%}",

                "lyrics_latency":
                    f"{float(status.get('lyrics_latency', 0) or 0):.2f}s",

                "cache_source":
                    (
                        str(
                            status.get(
                                "cache_source"
                            )
                            or "network"
                        ).title()
                    ),

                "provider_successes":
                    status.get(
                        "provider_successes",
                        0,
                    ),

                "provider_failures":
                    status.get(
                        "provider_failures",
                        0,
                    ),

                "provider_timeouts":
                    status.get(
                        "provider_timeouts",
                        0,
                    ),

                "memory_cache_entries":
                    status.get(
                        "memory_cache_entries",
                        0,
                    ),

                "memory_cache_hit_rate":
                    f"{float(status.get('memory_cache_hit_rate', 0) or 0):.0%}",

                "offline_cache_entries":
                    status.get(
                        "offline_cache_entries",
                        0,
                    ),

                "persistent_cache_hit_rate":
                    f"{float(status.get('persistent_cache_hit_rate', 0) or 0):.0%}",

                "rpc_connection":
                    (
                        "Connected"
                        if status.get(
                            "rpc_connected",
                            False,
                        )
                        else "Disconnected"
                    ),

                "rpc_updates_sent":
                    status.get(
                        "rpc_updates_sent",
                        0,
                    ),

                "rpc_updates_skipped":
                    status.get(
                        "rpc_updates_skipped",
                        0,
                    ),

                "rpc_optimization_rate":
                    f"{float(status.get('rpc_optimization_rate', 0) or 0):.0%}",

                "engine_state":
                    engine_state,

                "uptime":
                    self.format_duration(
                        status.get(
                            "uptime",
                            0,
                        )
                    ),

                "target_loop_hz":
                    f"{float(status.get('target_loop_hz', 0) or 0):.0f} Hz",

                "loop_count":
                    status.get(
                        "loop_count",
                        0,
                    ),

                "loop_last_ms":
                    f"{float(status.get('loop_last_ms', 0) or 0):.3f} ms",

                "loop_average_ms":
                    f"{float(status.get('loop_average_ms', 0) or 0):.3f} ms",

                "loop_max_ms":
                    f"{float(status.get('loop_max_ms', 0) or 0):.3f} ms",

                "song":
                    status.get(
                        "song"
                    )
                    or "Nothing playing",
            }

            for key, value in values.items():
                label = self.value_labels.get(
                    key
                )

                if label is not None:
                    label.setText(
                        str(value)
                    )

            optimization = float(
                status.get(
                    "rpc_optimization_rate",
                    0.0,
                )
                or 0.0
            )

            self.optimization_bar.setValue(
                int(
                    max(
                        0.0,
                        min(
                            optimization,
                            1.0,
                        ),
                    )
                    * 1000
                )
            )

        except Exception as error:
            print(
                "[Dashboard] Refresh error: "
                f"{error}"
            )

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    @staticmethod
    def format_duration(
        seconds: float | int,
    ) -> str:
        total = max(
            0,
            int(seconds),
        )

        hours, remainder = divmod(
            total,
            3600,
        )

        minutes, seconds = divmod(
            remainder,
            60,
        )

        if hours:
            return (
                f"{hours:02d}:"
                f"{minutes:02d}:"
                f"{seconds:02d}"
            )

        return (
            f"{minutes:02d}:"
            f"{seconds:02d}"
        )

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background-color: #121212;
                color: #F5F5F5;
                font-family: "Segoe UI";
                font-size: 13px;
            }

            QLabel#pageTitle {
                font-size: 24px;
                font-weight: 700;
            }

            QLabel#sectionTitle {
                color: #1ED760;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }

            QLabel#mutedText {
                color: #A7A7A7;
                font-size: 12px;
            }

            QLabel#metricValue {
                color: #FFFFFF;
                font-weight: 600;
            }

            QFrame#dashboardCard {
                background-color: #1E1E1E;
                border: 1px solid #2B2B2B;
                border-radius: 13px;
                padding: 10px;
            }

            QProgressBar {
                background-color: #3A3A3A;
                border: none;
                border-radius: 4px;
                min-height: 8px;
                max-height: 8px;
            }

            QProgressBar::chunk {
                background-color: #1ED760;
                border-radius: 4px;
            }
            """
        )