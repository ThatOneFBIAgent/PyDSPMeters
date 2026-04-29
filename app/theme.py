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
        "METER_LOW": "#0088ff", "METER_MID": "#00e87b", "METER_HIGH": "#ff4444",
        "PEAK_LED": "#ffcc00", "CLIP_LED": "#ff2244",
    },
    "Abyss": {
        "BG_DARKEST": "#000000", "BG_DARK": "#0a0a0a", "BG_MODULE": "#0f0f0f",
        "BG_HEADER": "#161616", "BG_SETTINGS": "#1a1a1a", "BG_INPUT": "#0c0c0c",
        "BORDER": "#2a2a2a", "BORDER_ACCENT": "#3a3a3a",
        "ACCENT": "#e0e0e0", "ACCENT_DIM": "#808080",
        "ACCENT_PURPLE": "#9a9a9a", "ACCENT_PINK": "#c0c0c0",
        "TEXT": "#d0d0d0", "TEXT_DIM": "#666666", "TEXT_BRIGHT": "#ffffff",
        "BAND_LOW": "#666666", "BAND_MID": "#aaaaaa", "BAND_HIGH": "#ffffff",
        "METER_LOW": "#666666", "METER_MID": "#aaaaaa", "METER_HIGH": "#ffffff",
        "PEAK_LED": "#cccccc", "CLIP_LED": "#ffffff",
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
        "METER_LOW": "#00cc66", "METER_MID": "#00ff88", "METER_HIGH": "#ffff00",
        "PEAK_LED": "#ff8800", "CLIP_LED": "#ff2200",
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
        "METER_LOW": "#aa5500", "METER_MID": "#ff8800", "METER_HIGH": "#ffaa44",
        "PEAK_LED": "#ffdd00", "CLIP_LED": "#ff2200",
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
        "METER_LOW": "#7030aa", "METER_MID": "#b060ff", "METER_HIGH": "#ff44cc",
        "PEAK_LED": "#ffaa00", "CLIP_LED": "#ff2244",
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
        "METER_LOW": "#0088ff", "METER_MID": "#00e87b", "METER_HIGH": "#ff4444",
        "PEAK_LED": "#ffcc00", "CLIP_LED": "#ff2244",
        "HEATMAP_STOPS": [
            (0.00, "#05000000"), (0.15, "#0a0040"), (0.30, "#0044cc"),
            (0.45, "#00bbcc"), (0.55, "#00cc44"), (0.70, "#cccc00"),
            (0.85, "#cc4400"), (1.00, "#ff0000")
        ]
    },
    "Slate": {
        "BG_DARKEST": "#1a1b26", "BG_DARK": "#24283b", "BG_MODULE": "#2f354a",
        "BG_HEADER": "#3b4261", "BG_SETTINGS": "#414868", "BG_INPUT": "#1a1b26",
        "BORDER": "#565f89", "BORDER_ACCENT": "#7aa2f7",
        "ACCENT": "#7aa2f7", "ACCENT_DIM": "#2ac3de",
        "ACCENT_PURPLE": "#bb9af7", "ACCENT_PINK": "#f7768e",
        "TEXT": "#c0caf5", "TEXT_DIM": "#a9b1d6", "TEXT_BRIGHT": "#ffffff",
        "BAND_LOW": "#7aa2f7", "BAND_MID": "#9ece6a", "BAND_HIGH": "#f7768e",
        "METER_LOW": "#2ac3de", "METER_MID": "#9ece6a", "METER_HIGH": "#f7768e",
        "PEAK_LED": "#ffcc00", "CLIP_LED": "#ff2244",
    },
    "Modern Light": {
        "BG_DARKEST": "#f0f0f5", "BG_DARK": "#ffffff", "BG_MODULE": "#fcfcfd",
        "BG_HEADER": "#e8e8f0", "BG_SETTINGS": "#ffffff", "BG_INPUT": "#f5f5f9",
        "BORDER": "#d1d1e0", "BORDER_ACCENT": "#4a90e2",
        "ACCENT": "#4a90e2", "ACCENT_DIM": "#357abd",
        "ACCENT_PURPLE": "#9013fe", "ACCENT_PINK": "#d0021b",
        "TEXT": "#2c3e50", "TEXT_DIM": "#7f8c8d", "TEXT_BRIGHT": "#000000",
        "BAND_LOW": "#4a90e2", "BAND_MID": "#40c057", "BAND_HIGH": "#fa5252",
        "METER_LOW": "#4a90e2", "METER_MID": "#357abd", "METER_HIGH": "#d0021b",
        "PEAK_LED": "#ff8800", "CLIP_LED": "#ff2244",
        "HEATMAP_STOPS": [
            (0.00, "#ffffff"), (0.30, "#e8f4fd"), (0.60, "#a0d1f7"),
            (0.85, "#4a90e2"), (1.00, "#2c3e50")
        ]
    },
    "Glass": {
        "BG_DARKEST": "#10ffffff", "BG_DARK": "#15ffffff", "BG_MODULE": "#20ffffff",
        "BG_HEADER": "#30ffffff", "BG_SETTINGS": "#40ffffff", "BG_INPUT": "#10ffffff",
        "BORDER": "#40ffffff", "BORDER_ACCENT": "#80ffffff",
        "ACCENT": "#ffffff", "ACCENT_DIM": "#cccccc",
        "ACCENT_PURPLE": "#e0e0e0", "ACCENT_PINK": "#f0f0f0",
        "TEXT": "#ffffff", "TEXT_DIM": "#dddddd", "TEXT_BRIGHT": "#ffffff",
        "BAND_LOW": "#ffffff", "BAND_MID": "#eeeeee", "BAND_HIGH": "#dddddd",
        "METER_LOW": "#cccccc", "METER_MID": "#eeeeee", "METER_HIGH": "#ffffff",
        "PEAK_LED": "#ffdd88", "CLIP_LED": "#ff8899",
    },
    "Aurora": {
        "BG_DARKEST": "#05101a", "BG_DARK": "#0a1f30", "BG_MODULE": "#0f2a42",
        "BG_HEADER": "#163550", "BG_SETTINGS": "#1a3d5c", "BG_INPUT": "#081828",
        "BORDER": "#1a4060", "BORDER_ACCENT": "#2a6080",
        "ACCENT": "#00ffcc", "ACCENT_DIM": "#00aa88",
        "ACCENT_PURPLE": "#00ccff", "ACCENT_PINK": "#ff44aa",
        "TEXT": "#c0f5e8", "TEXT_DIM": "#4a8a78", "TEXT_BRIGHT": "#e0fff8",
        "BAND_LOW": "#00ccff", "BAND_MID": "#00ffcc", "BAND_HIGH": "#ff44aa",
        "METER_LOW": "#00ccff", "METER_MID": "#00ffcc", "METER_HIGH": "#ff44aa",
        "PEAK_LED": "#ffcc00", "CLIP_LED": "#ff2244",
        "HEATMAP_STOPS": [
            (0.00, "#000000"), (0.30, "#001a22"), (0.60, "#00667a"),
            (0.85, "#00ffcc"), (1.00, "#aaffee")
        ]
    },
    "Crimson": {
        "BG_DARKEST": "#100508", "BG_DARK": "#1a080c", "BG_MODULE": "#220a10",
        "BG_HEADER": "#2a0c14", "BG_SETTINGS": "#321018", "BG_INPUT": "#150608",
        "BORDER": "#3a1020", "BORDER_ACCENT": "#5a1830",
        "ACCENT": "#ff2255", "ACCENT_DIM": "#aa1133",
        "ACCENT_PURPLE": "#ff0044", "ACCENT_PINK": "#ff6688",
        "TEXT": "#f0c0cc", "TEXT_DIM": "#8a4050", "TEXT_BRIGHT": "#ffe0e8",
        "BAND_LOW": "#ff2255", "BAND_MID": "#ff0044", "BAND_HIGH": "#ff6688",
        "METER_LOW": "#cc2244", "METER_MID": "#ff2255", "METER_HIGH": "#ff6688",
        "PEAK_LED": "#ffaa00", "CLIP_LED": "#ffffff",
        "HEATMAP_STOPS": [
            (0.00, "#000000"), (0.30, "#440011"), (0.60, "#aa0033"),
            (0.85, "#ff2255"), (1.00, "#ffaabb")
        ]
    },
    "Solar": {
        "BG_DARKEST": "#0f0c00", "BG_DARK": "#1a1400", "BG_MODULE": "#241c00",
        "BG_HEADER": "#2e2400", "BG_SETTINGS": "#382c00", "BG_INPUT": "#120e00",
        "BORDER": "#3a3000", "BORDER_ACCENT": "#5a4c00",
        "ACCENT": "#ffd700", "ACCENT_DIM": "#aa9000",
        "ACCENT_PURPLE": "#ffaa00", "ACCENT_PINK": "#ffe066",
        "TEXT": "#fff0b0", "TEXT_DIM": "#8a7a30", "TEXT_BRIGHT": "#fffde0",
        "BAND_LOW": "#ffaa00", "BAND_MID": "#ffd700", "BAND_HIGH": "#ffe066",
        "METER_LOW": "#ffaa00", "METER_MID": "#ffd700", "METER_HIGH": "#ffffff",
        "PEAK_LED": "#ff6600", "CLIP_LED": "#ff2200",
        "HEATMAP_STOPS": [
            (0.00, "#000000"), (0.30, "#1a1000"), (0.60, "#665500"),
            (0.85, "#ffd700"), (1.00, "#fffacc")
        ]
    },
    "Arctic": {
        "BG_DARKEST": "#060e18", "BG_DARK": "#0c1828", "BG_MODULE": "#122035",
        "BG_HEADER": "#182840", "BG_SETTINGS": "#1e304c", "BG_INPUT": "#090e18",
        "BORDER": "#1e3a55", "BORDER_ACCENT": "#2e5070",
        "ACCENT": "#88ddff", "ACCENT_DIM": "#3399cc",
        "ACCENT_PURPLE": "#aaddff", "ACCENT_PINK": "#66aadd",
        "TEXT": "#d0eeff", "TEXT_DIM": "#5080a0", "TEXT_BRIGHT": "#f0faff",
        "BAND_LOW": "#6699cc", "BAND_MID": "#88ddff", "BAND_HIGH": "#aaddff",
        "METER_LOW": "#3399cc", "METER_MID": "#88ddff", "METER_HIGH": "#ff4466",
        "PEAK_LED": "#ffcc44", "CLIP_LED": "#ff3322",
        "HEATMAP_STOPS": [
            (0.00, "#000000"), (0.30, "#031422"), (0.60, "#105080"),
            (0.85, "#88ddff"), (1.00, "#ddf4ff")
        ]
    },
    "Absinthe": {
        "BG_DARKEST": "#060f08", "BG_DARK": "#0c1a10", "BG_MODULE": "#122018",
        "BG_HEADER": "#182a20", "BG_SETTINGS": "#1e3228", "BG_INPUT": "#090e0a",
        "BORDER": "#203820", "BORDER_ACCENT": "#304e30",
        "ACCENT": "#88ff44", "ACCENT_DIM": "#55aa22",
        "ACCENT_PURPLE": "#66dd33", "ACCENT_PINK": "#ccff88",
        "TEXT": "#d0f0b8", "TEXT_DIM": "#507840", "TEXT_BRIGHT": "#eeffcc",
        "BAND_LOW": "#66dd33", "BAND_MID": "#88ff44", "BAND_HIGH": "#ccff88",
        "METER_LOW": "#55aa22", "METER_MID": "#88ff44", "METER_HIGH": "#ffff00",
        "PEAK_LED": "#ff8800", "CLIP_LED": "#ff2200",
        "HEATMAP_STOPS": [
            (0.00, "#000000"), (0.30, "#091a04"), (0.60, "#2a6010"),
            (0.85, "#88ff44"), (1.00, "#d4ffaa")
        ]
    },
    "Rose Quartz": {
        "BG_DARKEST": "#0f080c", "BG_DARK": "#1a1018", "BG_MODULE": "#221520",
        "BG_HEADER": "#2a1a28", "BG_SETTINGS": "#321e30", "BG_INPUT": "#120a10",
        "BORDER": "#3a2030", "BORDER_ACCENT": "#5a3050",
        "ACCENT": "#ff80b0", "ACCENT_DIM": "#cc4488",
        "ACCENT_PURPLE": "#dd60a0", "ACCENT_PINK": "#ffaacf",
        "TEXT": "#f0d0dc", "TEXT_DIM": "#8a5068", "TEXT_BRIGHT": "#ffecf2",
        "BAND_LOW": "#dd60a0", "BAND_MID": "#ff80b0", "BAND_HIGH": "#ffaacf",
        "METER_LOW": "#cc4488", "METER_MID": "#ff80b0", "METER_HIGH": "#ffaacf",
        "PEAK_LED": "#ffaa00", "CLIP_LED": "#ff2244",
        "HEATMAP_STOPS": [
            (0.00, "#000000"), (0.30, "#330018"), (0.60, "#991055"),
            (0.85, "#ff80b0"), (1.00, "#ffcce0")
        ]
    },
    "Transparent Crimson": {
        "BG_DARKEST": "#05000000", "BG_DARK": "#05000000", "BG_MODULE": "#05000000",
        "BG_HEADER": "#05000000", "BG_SETTINGS": "#05000000", "BG_INPUT": "#05000000",
        "BORDER": "#00000000", "BORDER_ACCENT": "#00000000",
        "ACCENT": "#ff2255", "ACCENT_DIM": "#aa1133",
        "ACCENT_PURPLE": "#ff0044", "ACCENT_PINK": "#ff6688",
        "TEXT": "#f0c0cc", "TEXT_DIM": "#8a4050", "TEXT_BRIGHT": "#ffe0e8",
        "BAND_LOW": "#ff2255", "BAND_MID": "#ff0044", "BAND_HIGH": "#ff6688",
        "METER_LOW": "#cc2244", "METER_MID": "#ff2255", "METER_HIGH": "#ff6688",
        "PEAK_LED": "#ffaa00", "CLIP_LED": "#ffffff",
        "HEATMAP_STOPS": [
            (0.00, "#05000000"), (0.15, "#4a001122"), (0.30, "#aa003355"),
            (0.55, "#ff2255bb"), (1.00, "#ff6688ff")
        ]
    },
    "Transparent Aurora": {
        "BG_DARKEST": "#05000000", "BG_DARK": "#05000000", "BG_MODULE": "#05000000",
        "BG_HEADER": "#05000000", "BG_SETTINGS": "#05000000", "BG_INPUT": "#05000000",
        "BORDER": "#00000000", "BORDER_ACCENT": "#00000000",
        "ACCENT": "#00ffcc", "ACCENT_DIM": "#00aa88",
        "ACCENT_PURPLE": "#00ccff", "ACCENT_PINK": "#ff44aa",
        "TEXT": "#c0f5e8", "TEXT_DIM": "#4a8a78", "TEXT_BRIGHT": "#e0fff8",
        "BAND_LOW": "#00ccff", "BAND_MID": "#00ffcc", "BAND_HIGH": "#ff44aa",
        "METER_LOW": "#00ccff", "METER_MID": "#00ffcc", "METER_HIGH": "#ff44aa",
        "PEAK_LED": "#ffcc00", "CLIP_LED": "#ff2244",
        "HEATMAP_STOPS": [
            (0.00, "#05000000"), (0.15, "#0a2a3a44"), (0.30, "#00667a88"),
            (0.55, "#00ffcccc"), (1.00, "#aaffeeff")
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

    # Meter colors (overridable by themes)
    METER_LOW = "#00e87b"
    METER_MID = "#f0c800"
    METER_HIGH = "#ff2244"
    PEAK_LED = "#ff2244"
    CLIP_LED = "#ff2244"
    
    # Internal aliases for backward compatibility
    GREEN = "#00e87b"
    YELLOW = "#f0c800"
    RED = "#ff2244"

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


def apply_theme(name: str, overrides: dict = None):
    """Switch the active color palette to the named preset and apply optional overrides."""
    global _current_theme
    if name not in THEME_PRESETS:
        return
    _current_theme = name
    
    # Baseline defaults (Midnight) to ensure we don't leak specialized colors from previous themes
    defaults = THEME_PRESETS["Midnight"]
    # Keys that are often missing in simpler themes but should reset
    reset_keys = ["BAND_LOW", "BAND_MID", "BAND_HIGH", "HEATMAP_STOPS", "METER_LOW", "METER_MID", "METER_HIGH", "PEAK_LED", "CLIP_LED"]
    
    # 1. Reset baseline for specific keys
    for key in reset_keys:
        if key in defaults:
            setattr(Colors, key, defaults[key])
        elif key.startswith("METER_") or key.endswith("_LED"):
            if "LOW" in key: setattr(Colors, key, "#00e87b")
            elif "MID" in key: setattr(Colors, key, "#f0c800")
            else: setattr(Colors, key, "#ff2244")

    # Sync back-compat aliases
    Colors.GREEN = Colors.METER_LOW
    Colors.YELLOW = Colors.METER_MID
    Colors.RED = Colors.METER_HIGH
            
    # 2. Apply the chosen preset
    preset = THEME_PRESETS[name]
    for attr, value in preset.items():
        if hasattr(Colors, attr):
            setattr(Colors, attr, value)
    
    # Sync back-compat aliases after preset
    Colors.GREEN = Colors.METER_LOW
    Colors.YELLOW = Colors.METER_MID
    Colors.RED = Colors.METER_HIGH

    # 3. Apply optional overrides
    if overrides:
        for attr, value in overrides.items():
            if hasattr(Colors, attr):
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
    """Generate global Qt stylesheet."""
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
    QLineEdit {{
        background: {Colors.BG_INPUT};
        border: 1px solid {Colors.BORDER};
        border-radius: 3px;
        color: {Colors.TEXT};
        padding: 2px 4px;
    }}
    QComboBox:hover {{
        border-color: {Colors.ACCENT_DIM};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 16px;
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
    QComboBox QAbstractItemView {{
        background: #1a1a2e;
        border: 1px solid #3a3a6a;
        selection-background-color: #0088aa;
        color: #d8d8f0;
    }}
    QMenu {{
        background: #1a1a2e;
        border: 1px solid #3a3a6a;
        padding: 4px;
        color: #d8d8f0;
    }}
    QMenu::item {{
        padding: 5px 20px;
        border-radius: 3px;
        color: #d8d8f0;
    }}
    QMenu::item:selected {{
        background: #0088aa;
        color: #ffffff;
    }}
    QMenu::separator {{
        height: 1px;
        background: #252545;
        margin: 4px 8px;
    }}
    QToolTip {{
        background: #1a1a2e;
        border: 1px solid #3a3a6a;
        color: #d8d8f0;
        padding: 4px;
    }}
    """
