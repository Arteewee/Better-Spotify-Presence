from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from ui.theme import Theme


APPLICATION_STYLE = f"""
QMainWindow,
QDialog {{
    background-color: {Theme.BACKGROUND};
}}

QWidget {{
    color: {Theme.TEXT};
    font-family: {Theme.FONT_FAMILY};
    font-size: {Theme.BASE_FONT_SIZE}px;
    background-color: transparent;
}}

QWidget#spotifyRoot {{
    background-color: {Theme.BACKGROUND};
}}

QToolTip {{
    color: {Theme.TEXT_STRONG};
    background-color: {Theme.SURFACE_ALT};
    border: 1px solid {Theme.BORDER_STRONG};
    padding: 5px 8px;
}}

QLabel#pageTitle,
QLabel#errorTitle {{
    color: {Theme.TEXT_STRONG};
    font-size: 24px;
    font-weight: 700;
}}

QLabel#songTitle {{
    color: {Theme.TEXT_STRONG};
    font-size: 24px;
    font-weight: 700;
}}

QLabel#secondaryText {{
    color: {Theme.TEXT_SECONDARY};
    font-size: 15px;
    font-weight: 600;
}}

QLabel#mutedText {{
    color: {Theme.TEXT_MUTED};
    font-size: 12px;
}}

QLabel#footerText {{
    color: {Theme.FOOTER};
    font-size: 11px;
}}

QLabel#sectionTitle {{
    color: {Theme.PRIMARY};
    font-size: 11px;
    font-weight: 700;
}}

QLabel#warningText {{
    color: {Theme.WARNING};
}}

QLabel#errorMessage {{
    color: #E6A6A6;
    font-size: 14px;
}}

QLabel#statusValue,
QLabel#metricValue,
QLabel#versionText,
QLabel#profileName {{
    color: {Theme.TEXT_STRONG};
    font-weight: 700;
}}

QLabel#lyricText {{
    color: {Theme.TEXT_STRONG};
    font-size: 18px;
    font-weight: 600;
    padding: 10px;
}}

QFrame#card,
QFrame#dashboardCard {{
    background-color: {Theme.SURFACE};
    border: 1px solid {Theme.BORDER};
    border-radius: {Theme.CARD_RADIUS}px;
}}

QGroupBox {{
    background-color: {Theme.SURFACE};
    border: 1px solid {Theme.BORDER};
    border-radius: 12px;
    margin-top: 14px;
    padding: 16px;
    font-weight: 700;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: {Theme.PRIMARY};
}}

QLineEdit,
QDoubleSpinBox,
QSpinBox,
QComboBox {{
    min-height: 34px;
    padding: 0 10px;
    background-color: {Theme.INPUT};
    color: {Theme.TEXT_STRONG};
    border: 1px solid {Theme.BORDER_STRONG};
    border-radius: 8px;
}}

QLineEdit:focus,
QDoubleSpinBox:focus,
QSpinBox:focus,
QComboBox:focus {{
    border-color: {Theme.PRIMARY};
}}

QComboBox QAbstractItemView {{
    background-color: {Theme.SURFACE_ALT};
    color: {Theme.TEXT};
    border: 1px solid {Theme.BORDER_STRONG};
    selection-background-color: {Theme.PRIMARY};
    selection-color: #081C0F;
}}


/* Log Viewer filter controls
   The green outline lives on the wrapper frame.
   The QComboBox keeps the native Windows/Qt arrow without
   being able to cut through the outer border. */
QFrame#logFilterFrame {{
    background-color: #252525;
    border: 1px solid {Theme.PRIMARY};
    border-radius: 10px;
}}

QFrame#logFilterFrame:hover {{
    background-color: #2B2B2B;
    border-color: {Theme.PRIMARY_HOVER};
}}

QComboBox#logFilterCombo {{
    min-height: 38px;
    padding: 0 10px 0 13px;
    color: {Theme.TEXT_STRONG};
    background-color: transparent;
    border: none;
    font-weight: 500;
}}

QComboBox#logFilterCombo:hover,
QComboBox#logFilterCombo:focus {{
    background-color: transparent;
    border: none;
}}

QComboBox#logFilterCombo::drop-down {{
    border: none;
    background-color: transparent;
    width: 30px;
}}

QComboBox#logFilterCombo QAbstractItemView {{
    background-color: {Theme.SURFACE_ALT};
    color: {Theme.TEXT};
    border: 1px solid {Theme.PRIMARY};
    border-radius: 8px;
    padding: 4px;
    outline: 0;
    selection-background-color: {Theme.PRIMARY};
    selection-color: #081C0F;
}}

QCheckBox {{
    spacing: 8px;
    min-height: 26px;
}}

QListWidget {{
    background-color: {Theme.SURFACE};
    color: {Theme.TEXT};
    border: 1px solid {Theme.BORDER};
    border-radius: 10px;
    padding: 6px;
    outline: none;
}}

QListWidget::item {{
    padding: 10px;
    border-radius: 8px;
}}

QListWidget::item:selected {{
    color: #081C0F;
    background-color: {Theme.PRIMARY};
}}

QTextEdit {{
    background-color: {Theme.INPUT_DARK};
    color: #EAEAEA;
    border: 1px solid {Theme.BORDER};
    border-radius: 10px;
    padding: 10px;
    selection-background-color: {Theme.PRIMARY};
    selection-color: #081C0F;
}}

QProgressBar {{
    background-color: #3A3A3A;
    border: none;
    border-radius: 5px;
    min-height: 9px;
    max-height: 9px;
}}

QProgressBar::chunk {{
    background-color: {Theme.PRIMARY};
    border-radius: 5px;
}}

QPushButton {{
    min-height: 38px;
    padding: 0 16px;
    border-radius: {Theme.CONTROL_RADIUS}px;
    color: {Theme.TEXT_STRONG};
    background-color: #2A2A2A;
    border: 1px solid {Theme.BORDER_STRONG};
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: #353535;
}}

QPushButton:pressed {{
    background-color: #404040;
}}

QPushButton#primaryButton {{
    color: #081C0F;
    background-color: {Theme.PRIMARY};
    border: none;
}}

QPushButton#primaryButton:hover {{
    background-color: {Theme.PRIMARY_HOVER};
}}

QPushButton#secondaryButton {{
    color: {Theme.TEXT_STRONG};
    background-color: #2A2A2A;
    border: 1px solid {Theme.BORDER_STRONG};
}}

QPushButton#dangerButton {{
    color: {Theme.TEXT_STRONG};
    background-color: {Theme.ERROR_DARK};
    border: 1px solid {Theme.ERROR_BORDER};
}}

QPushButton#dangerButton:hover {{
    background-color: #512626;
}}

QPushButton:disabled {{
    color: {Theme.TEXT_DISABLED};
    background-color: {Theme.SURFACE_ALT};
    border-color: #303030;
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollBar:vertical {{
    background: {Theme.BACKGROUND};
    width: 10px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: #555555;
    min-height: 30px;
    border-radius: 5px;
}}

QScrollBar::handle:vertical:hover {{
    background: #686868;
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    height: 0px;
    background: transparent;
}}

QScrollBar:horizontal {{
    background: {Theme.BACKGROUND};
    height: 10px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: #555555;
    min-width: 30px;
    border-radius: 5px;
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    width: 0px;
    background: transparent;
}}

QLabel[status="running"] {{
    color: #081C0F;
    background-color: {Theme.SUCCESS};
    border-radius: 12px;
    padding: 7px 16px;
    font-weight: 700;
}}

QLabel[status="paused"] {{
    color: #1F1600;
    background-color: {Theme.WARNING};
    border-radius: 12px;
    padding: 7px 16px;
    font-weight: 700;
}}

QLabel[status="stopped"] {{
    color: #D0D0D0;
    background-color: #333333;
    border-radius: 12px;
    padding: 7px 16px;
    font-weight: 700;
}}

QLabel[status="error"] {{
    color: {Theme.TEXT_STRONG};
    background-color: #C62828;
    border-radius: 12px;
    padding: 7px 16px;
    font-weight: 700;
}}

QFrame#liveStatusBar {{
    background-color: {Theme.SURFACE_ALT};
    border: 1px solid #3A3A3A;
    border-radius: {Theme.STATUS_RADIUS}px;
}}

QFrame#liveStatusBar[level="success"] {{
    border-color: {Theme.SUCCESS};
}}

QFrame#liveStatusBar[level="warning"] {{
    border-color: {Theme.WARNING};
}}

QFrame#liveStatusBar[level="error"] {{
    border-color: {Theme.ERROR};
}}

QLabel#liveStatusDot {{
    color: {Theme.TEXT_MUTED};
    font-size: 16px;
}}

QLabel#liveStatusDot[level="success"] {{
    color: {Theme.SUCCESS};
}}

QLabel#liveStatusDot[level="warning"] {{
    color: {Theme.WARNING};
}}

QLabel#liveStatusDot[level="error"] {{
    color: {Theme.ERROR};
}}

QLabel#liveStatusTitle {{
    color: {Theme.TEXT_STRONG};
    font-weight: 700;
}}

QLabel#liveStatusMessage {{
    color: {Theme.TEXT_MUTED};
}}
"""


TOAST_STYLE = f"""
QFrame#toast {{
    background-color: {Theme.SURFACE_ALT};
    border: 1px solid {Theme.BORDER_STRONG};
    border-radius: 12px;
}}

QFrame#toast[level="success"] {{
    border-color: {Theme.SUCCESS};
}}

QFrame#toast[level="warning"] {{
    border-color: {Theme.WARNING};
}}

QFrame#toast[level="error"] {{
    border-color: {Theme.ERROR};
}}

QLabel#toastTitle {{
    color: {Theme.TEXT_STRONG};
    font-weight: 700;
    font-size: 13px;
}}

QLabel#toastMessage {{
    color: #CFCFCF;
    font-size: 12px;
}}
"""


def apply_app_style(widget: QWidget) -> None:
    # Give only the top-level window a solid background.
    # Child widgets (especially QLabel) stay transparent so text no longer
    # appears inside dark rectangular tiles.
    widget.setObjectName(
        widget.objectName()
        or "spotifyRoot"
    )

    widget.setStyleSheet(
        APPLICATION_STYLE
    )


def apply_responsive_geometry(
    widget: QWidget,
    *,
    preferred_width: int,
    preferred_height: int,
    minimum_width: int = 620,
    minimum_height: int = 520,
) -> None:
    screen = widget.screen() or QGuiApplication.primaryScreen()

    if screen is None:
        widget.setMinimumSize(minimum_width, minimum_height)
        widget.resize(preferred_width, preferred_height)
        return

    available = screen.availableGeometry()
    max_width = max(520, int(available.width() * 0.92))
    max_height = max(440, int(available.height() * 0.90))

    widget.setMinimumSize(
        min(minimum_width, max_width),
        min(minimum_height, max_height),
    )

    widget.resize(
        min(preferred_width, max_width),
        min(preferred_height, max_height),
    )