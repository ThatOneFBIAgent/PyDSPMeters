"""
Theme system for PyDSPMeters.
Supports multiple switchable theme presets and Qt stylesheet generation.
"""

from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt


# ── Theme Presets ────────────────────────────────────────────────────────────

THEME_PRESETS = {
    "Midnight": {
        "BG_DARKEST": "#08080f", "BG_DARK": "#0e0e1a", "BG_MODULE": "#131320",
        "BG_HEADER": "#181830", "BG_SETTINGS": "#1a1a2e", "BG_INPUT": "#10101e",
        "BORDER": "#252545", "BORDER_ACCENT": "#3a3a6a",
        "ACCENT": "#00d4ff", "ACCENT_DIM": "#0088aa",
        "ACCENT_PURPLE": "#7c4dff", "ACCENT_PINK": "#ff4da6",
        "TEXT": "#d8d8f0", "TEXT_DIM": "#7878a0", "TEXT_BRIGHT": "#f0f0ff",
        "BAND_LOW": "#0088ff", "BAND_MID": "#00e87b", "BAND_HIGH": "#ff4444",
    },
    "Abyss": {
        "BG_DARKEST": "#000000", "BG_DARK": "#0a0a0a", "BG_MODULE": "#0f0f0f",
        "BG_HEADER": "#161616", "BG_SETTINGS": "#1a1a1a", "BG_INPUT": "#0c0c0c",
        "BORDER": "#2a2a2a", "BORDER_ACCENT": "#3a3a3a",
        "ACCENT": "#e0e0e0", "ACCENT_DIM": "#808080",
        "ACCENT_PURPLE": "#9a9a9a", "ACCENT_PINK": "#c0c0c0",
        "TEXT": "#d0d0d0", "TEXT_DIM": "#666666", "TEXT_BRIGHT": "#ffffff",
        "BAND_LOW": "#666666", "BAND_MID": "#aaaaaa", "BAND_HIGH": "#ffffff",
        "HEATMAP_STOPS": [
            (0.00, "#000000"), (0.30, "#222222"), (0.60, "#666666"),
            (0.85, "#aaaaaa"), (1.00, "#ffffff")
        ]
    },
    "Neon": {
        "BG_DARKEST": "#050a05", "BG_DARK": "#0a120a", "BG_MODULE": "#0e180e",
        "BG_HEADER": "#122012", "BG_SETTINGS": "#162816", "BG_INPUT": "#0a100a",
        "BORDER": "#1a3a1a", "BORDER_ACCENT": "#2a5a2a",
        "ACCENT": "#00ff88", "ACCENT_DIM": "#009950",
        "ACCENT_PURPLE": "#00cc66", "ACCENT_PINK": "#88ff00",
        "TEXT": "#c0f0c0", "TEXT_DIM": "#4a8a4a", "TEXT_BRIGHT": "#e0ffe0",
        "BAND_LOW": "#00cc66", "BAND_MID": "#00ff88", "BAND_HIGH": "#88ff00",
        "HEATMAP_STOPS": [
            (0.00, "#000000"), (0.30, "#004422"), (0.60, "#00aa55"),
            (0.85, "#44ff88"), (1.00, "#aaffcc")
        ]
    },
    "Ember": {
        "BG_DARKEST": "#0c0806", "BG_DARK": "#140e0a", "BG_MODULE": "#1a1410",
        "BG_HEADER": "#221a14", "BG_SETTINGS": "#2a2018", "BG_INPUT": "#120e08",
        "BORDER": "#3a2a1a", "BORDER_ACCENT": "#5a4030",
        "ACCENT": "#ff8800", "ACCENT_DIM": "#aa5500",
        "ACCENT_PURPLE": "#ff6622", "ACCENT_PINK": "#ffaa44",
        "TEXT": "#f0dcc0", "TEXT_DIM": "#8a6a4a", "TEXT_BRIGHT": "#fff0dd",
        "BAND_LOW": "#ff8800", "BAND_MID": "#ff6622", "BAND_HIGH": "#ffaa44",
        "HEATMAP_STOPS": [
            (0.00, "#000000"), (0.30, "#441100"), (0.60, "#aa4400"),
            (0.85, "#ff8800"), (1.00, "#ffcc88")
        ]
    },
    "Amethyst": {
        "BG_DARKEST": "#08060f", "BG_DARK": "#100c1a", "BG_MODULE": "#161222",
        "BG_HEADER": "#1e1830", "BG_SETTINGS": "#241e38", "BG_INPUT": "#0e0a18",
        "BORDER": "#302848", "BORDER_ACCENT": "#4a3a6a",
        "ACCENT": "#b060ff", "ACCENT_DIM": "#7030aa",
        "ACCENT_PURPLE": "#9040dd", "ACCENT_PINK": "#d080ff",
        "TEXT": "#dcd0f0", "TEXT_DIM": "#7868a0", "TEXT_BRIGHT": "#f0e8ff",
        "BAND_LOW": "#7c4dff", "BAND_MID": "#b060ff", "BAND_HIGH": "#d080ff",
        "HEATMAP_STOPS": [
            (0.00, "#000000"), (0.30, "#220044"), (0.60, "#6600aa"),
            (0.85, "#aa44ff"), (1.00, "#eebbaa")
        ]
    },
    "Transparent Ghost": {
        "BG_DARKEST": "#05000000", "BG_DARK": "#05000000", "BG_MODULE": "#05000000",
        "BG_HEADER": "#05000000", "BG_SETTINGS": "#05000000", "BG_INPUT": "#05000000",
        "BORDER": "#00000000", "BORDER_ACCENT": "#00000000",
        "ACCENT": "#00d4ff", "ACCENT_DIM": "#0088aa",
        "ACCENT_PURPLE": "#7c4dff", "ACCENT_PINK": "#ff4da6",
        "TEXT": "#d8d8f0", "TEXT_DIM": "#7878a0", "TEXT_BRIGHT": "#f0f0ff",
        "BAND_LOW": "#0088ff", "BAND_MID": "#00e87b", "BAND_HIGH": "#ff4444",
        "HEATMAP_STOPS": [
            (0.00, "#05000000"), (0.15, "#0a0040"), (0.30, "#0044cc"),
            (0.45, "#00bbcc"), (0.55, "#00cc44"), (0.70, "#cccc00"),
            (0.85, "#cc4400"), (1.00, "#ff0000")
        ]
    },
}


# ── Mutable Color Palette ───────────────────────────────────────────────────
class Colors:
    """Active color palette. Values are updated by apply_theme()."""
    BG_DARKEST = "#08080f"
    BG_DARK = "#0e0e1a"
    BG_MODULE = "#131320"
    BG_HEADER = "#181830"
    BG_SETTINGS = "#1a1a2e"
    BG_INPUT = "#10101e"
    BORDER = "#252545"
    BORDER_ACCENT = "#3a3a6a"

    ACCENT = "#00d4ff"
    ACCENT_DIM = "#0088aa"
    ACCENT_PURPLE = "#7c4dff"
    ACCENT_PINK = "#ff4da6"

    TEXT = "#d8d8f0"
    TEXT_DIM = "#7878a0"
    TEXT_BRIGHT = "#f0f0ff"

    # Meter colors (shared across all themes)
    GREEN = "#00e87b"
    GREEN_DIM = "#00783e"
    YELLOW = "#f0c800"
    ORANGE = "#ff8800"
    RED = "#ff2244"
    RED_DIM = "#881122"

    # Multi-band
    BAND_LOW = "#0088ff"
    BAND_MID = "#00e87b"
    BAND_HIGH = "#ff4444"

    HEATMAP_STOPS = [
        (0.00, "#000000"), (0.15, "#0a0040"), (0.30, "#0044cc"),
        (0.45, "#00bbcc"), (0.55, "#00cc44"), (0.70, "#cccc00"),
        (0.85, "#cc4400"), (1.00, "#ff0000")
    ]

    # Grid / subtle
    GRID = "#1a1a32"
    GRID_BRIGHT = "#252548"

    # VU meter
    VU_CREAM = "#f5f0e0"
    VU_DARK_FACE = "#1a1a28"
    VU_NEEDLE = "#cc2200"
    VU_RED_ZONE = "#ff3333"

    @staticmethod
    def q(hex_color: str) -> QColor:
        return QColor(hex_color)

    @staticmethod
    def with_alpha(hex_color: str, alpha: int) -> QColor:
        c = QColor(hex_color)
        c.setAlpha(alpha)
        return c


_current_theme = "Midnight"


def apply_theme(name: str):
    """Switch the active color palette to the named preset."""
    global _current_theme
    if name not in THEME_PRESETS:
        return
    _current_theme = name
    preset = THEME_PRESETS[name]
    for attr, value in preset.items():
        setattr(Colors, attr, value)


def current_theme_name() -> str:
    return _current_theme


# ── Spectrogram / Heatmap Color Maps ────────────────────────────────────────
# (Use Colors.HEATMAP_STOPS instead)


# ── Fonts ────────────────────────────────────────────────────────────────────
class Fonts:
    FAMILY = "Segoe UI"
    FAMILY_MONO = "Cascadia Code"
    TEXT_SCALE = 1.0

    @staticmethod
    def header() -> QFont:
        f = QFont(Fonts.FAMILY, int(9 * Fonts.TEXT_SCALE))
        f.setBold(True)
        return f

    @staticmethod
    def label() -> QFont:
        return QFont(Fonts.FAMILY, int(8 * Fonts.TEXT_SCALE))

    @staticmethod
    def value() -> QFont:
        f = QFont(Fonts.FAMILY_MONO, int(10 * Fonts.TEXT_SCALE))
        f.setBold(True)
        return f

    @staticmethod
    def small() -> QFont:
        return QFont(Fonts.FAMILY, int(7 * Fonts.TEXT_SCALE))

    @staticmethod
    def vu_scale() -> QFont:
        f = QFont(Fonts.FAMILY, int(7 * Fonts.TEXT_SCALE))
        f.setBold(True)
        return f


# ── Global Stylesheet ───────────────────────────────────────────────────────
def build_stylesheet() -> str:
    """Generate the global Qt stylesheet from the current Colors."""
    return f"""
    * {{
        color: {Colors.TEXT};
        font-family: "{Fonts.FAMILY}";
        font-size: 9pt;
    }}
    QMainWindow, QWidget#centralWidget {{
        background: {Colors.BG_DARKEST};
    }}
    QComboBox {{
        background: {Colors.BG_INPUT};
        border: 1px solid {Colors.BORDER};
        border-radius: 3px;
        padding: 3px 8px;
        min-height: 18px;
    }}
    QComboBox:hover {{
        border-color: {Colors.ACCENT_DIM};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 16px;
    }}
    QComboBox QAbstractItemView {{
        background: {Colors.BG_SETTINGS};
        border: 1px solid {Colors.BORDER_ACCENT};
        selection-background-color: {Colors.ACCENT_DIM};
    }}
    QSlider::groove:horizontal {{
        background: {Colors.BG_INPUT};
        height: 4px;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {Colors.ACCENT};
        width: 12px;
        height: 12px;
        margin: -4px 0;
        border-radius: 6px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {Colors.TEXT_BRIGHT};
    }}
    QCheckBox {{
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {Colors.BORDER};
        border-radius: 3px;
        background: {Colors.BG_INPUT};
    }}
    QCheckBox::indicator:checked {{
        background: {Colors.ACCENT};
        border-color: {Colors.ACCENT};
    }}
    QPushButton {{
        background: {Colors.BG_SETTINGS};
        border: 1px solid {Colors.BORDER};
        border-radius: 3px;
        padding: 4px 12px;
        min-height: 18px;
    }}
    QPushButton:hover {{
        background: {Colors.BG_INPUT};
        border-color: {Colors.ACCENT_DIM};
    }}
    QLabel {{
        color: {Colors.TEXT_DIM};
        font-size: 8pt;
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QMenu {{
        background: {Colors.BG_SETTINGS};
        border: 1px solid {Colors.BORDER_ACCENT};
        padding: 4px;
    }}
    QMenu::item {{
        padding: 5px 20px;
        border-radius: 3px;
    }}
    QMenu::item:selected {{
        background: {Colors.ACCENT_DIM};
    }}
    QMenu::separator {{
        height: 1px;
        background: {Colors.BORDER};
        margin: 4px 8px;
    }}
    QToolTip {{
        background: {Colors.BG_SETTINGS};
        border: 1px solid {Colors.BORDER_ACCENT};
        color: {Colors.TEXT};
        padding: 4px;
    }}
    """
