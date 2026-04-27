"""
Window Manager: Main application window with compact title bar,
module management, snapping logic, and theme switching.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMenu, QComboBox, QPushButton, QLabel, QFrame, QApplication,
    QSizePolicy, QWidgetAction,
)
from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal, QTimer
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QActionGroup

from app.theme import (
    Colors, Fonts, build_stylesheet, THEME_PRESETS,
    apply_theme, current_theme_name,
)
from app.audio_engine import AudioEngine
from app.base_module import BaseModule
from app.modules import MODULE_REGISTRY

# Ensure all modules register themselves
from app.modules import oscilloscope, loudness_meter, vu_meter  # noqa
from app.modules import stereometer, spectrum, spectrogram, waveform  # noqa


# ── Compact icon-style button ───────────────────────────────────────────────
def _icon_btn(text, tooltip, size=22):
    btn = QPushButton(text)
    btn.setFixedSize(size, size)
    btn.setToolTip(tooltip)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent; border: none;
            color: {Colors.TEXT_DIM}; font-size: 10pt; padding: 0;
        }}
        QPushButton:hover {{ color: {Colors.ACCENT}; }}
    """)
    return btn


class TitleBar(QFrame):
    """Ultra-compact title bar: [DSP] — stretch — [+][⫞][⚙][─][×]"""

    def __init__(self, parent_window, parent=None):
        super().__init__(parent)
        self._window = parent_window
        self._drag_pos = None
        self.setFixedHeight(28)
        self.setObjectName("titleBar")
        self.setStyleSheet(f"""
            #titleBar {{
                background: {Colors.BG_DARKEST};
                border-bottom: 1px solid {Colors.BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 4, 0)
        layout.setSpacing(2)

        # Logo / title — compact
        title = QLabel("DSP")
        title.setFont(Fonts.header())
        title.setStyleSheet(f"""
            color: {Colors.ACCENT}; font-size: 10pt;
            background: transparent; font-weight: bold;
        """)
        title.setFixedWidth(24)
        layout.addWidget(title)

        layout.addStretch()

        # Add module
        self.add_btn = _icon_btn("+", "Add module")
        layout.addWidget(self.add_btn)

        # Layout toggle
        self.layout_btn = _icon_btn("▥", "Vertical / Horizontal layout")
        layout.addWidget(self.layout_btn)

        # Settings gear (device + theme)
        self.gear_btn = _icon_btn("⚙", "Settings")
        layout.addWidget(self.gear_btn)

        # Minimize
        min_btn = _icon_btn("─", "Minimize")
        min_btn.clicked.connect(self._window.showMinimized)
        layout.addWidget(min_btn)

        # Close
        close_btn = _icon_btn("×", "Close")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {Colors.TEXT_DIM}; font-size: 10pt; padding: 0;
            }}
            QPushButton:hover {{ color: {Colors.RED}; }}
        """)
        close_btn.clicked.connect(self._window.close)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self._window.pos()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self._window.move(
                event.globalPosition().toPoint() - self._drag_pos
            )
            self._window.snap_to_edge()

    def mouseReleaseEvent(self, event):
        if self._drag_pos:
            self._window.snap_to_edge()
            self._drag_pos = None


class ResizeGrip(QWidget):
    """Bottom-right resize grip."""

    def __init__(self, parent_window):
        super().__init__(parent_window)
        self._window = parent_window
        self.setFixedSize(14, 14)
        self.setCursor(Qt.SizeFDiagCursor)
        self._drag_pos = None

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QPen
        p = QPainter(self)
        if not p.isActive():
            return
        p.setPen(QPen(QColor(Colors.TEXT_DIM), 1))
        for i in range(3):
            p.drawPoint(12 - i * 4, 12)
            p.drawPoint(12, 12 - i * 4)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self._drag_pos = event.globalPosition().toPoint()
            self._window.resize(
                max(160, self._window.width() + delta.x()),
                max(120, self._window.height() + delta.y()),
            )
            self._window.snap_to_edge()


class MainWindow(QMainWindow):
    """
    Main application window. Frameless, always-on-top,
    with module management, themes, and edge snapping.
    """

    SNAP_THRESHOLD = 20

    def __init__(self, audio_engine: AudioEngine):
        super().__init__()
        self.audio_engine = audio_engine

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setMinimumSize(160, 120)
        self.resize(300, 650)

        # Central widget
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar
        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        # Module splitter
        self._layout_vertical = True
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setHandleWidth(6)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {Colors.BORDER};
                border-radius: 2px;
                margin: 1px 30px;
            }}
            QSplitter::handle:hover {{
                background: {Colors.ACCENT};
            }}
        """)
        main_layout.addWidget(self.splitter)

        # Resize grip
        self._grip = ResizeGrip(self)

        # Module list
        self._modules: list[BaseModule] = []

        # Connect title bar buttons
        self.title_bar.add_btn.clicked.connect(self._show_add_menu)
        self.title_bar.layout_btn.clicked.connect(self._toggle_layout)
        self.title_bar.gear_btn.clicked.connect(self._show_gear_menu)

        # Track current device
        self._current_device = None
        self._devices = []
        self._refresh_devices()

        # Default modules
        self.add_module("oscilloscope")
        self.add_module("loudness")
        self.add_module("spectrum")

    # ── Device Management ───────────────────────────────────────────────────

    def _refresh_devices(self):
        self._devices = AudioEngine.list_devices()

    def _select_device(self, device_index):
        self._current_device = device_index
        self.audio_engine.start(device_index)

    # ── Gear Menu (Device + Theme) ──────────────────────────────────────────

    def _show_gear_menu(self):
        menu = QMenu(self)

        # Audio device submenu
        dev_menu = menu.addMenu("🎤  Audio Device")
        default_action = QAction("Default Input", self)
        default_action.setCheckable(True)
        default_action.setChecked(self._current_device is None)
        default_action.triggered.connect(lambda: self._select_device(None))
        dev_menu.addAction(default_action)
        dev_menu.addSeparator()

        self._refresh_devices()
        for d in self._devices:
            label = f"{d['name']} ({d['hostapi']})"
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(self._current_device == d["index"])
            idx = d["index"]
            action.triggered.connect(lambda checked, i=idx: self._select_device(i))
            dev_menu.addAction(action)

        # Make the device menu wide enough for long Voicemeeter names
        dev_menu.setMinimumWidth(380)

        menu.addSeparator()

        # Theme submenu
        theme_menu = menu.addMenu("🎨  Theme")
        current = current_theme_name()
        for name in THEME_PRESETS:
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(name == current)
            action.triggered.connect(
                lambda checked, n=name: self._apply_theme(n)
            )
            theme_menu.addAction(action)

        menu.exec(QCursor.pos())

    def _apply_theme(self, name: str):
        apply_theme(name)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(build_stylesheet())
        # Force repaint on all modules
        self.update()
        for m in self._modules:
            m.update()
            m.canvas.update()

    # ── Module Management ───────────────────────────────────────────────────

    def _show_add_menu(self):
        menu = QMenu(self)
        for key, info in MODULE_REGISTRY.items():
            action = QAction(info["display_name"], self)
            action.triggered.connect(lambda checked, k=key: self.add_module(k))
            menu.addAction(action)
        menu.exec(QCursor.pos())

    def add_module(self, module_key: str):
        if module_key not in MODULE_REGISTRY:
            return
        cls = MODULE_REGISTRY[module_key]["class"]
        module = cls(self.audio_engine)
        module.close_requested.connect(self.remove_module)
        self.splitter.addWidget(module)
        self._modules.append(module)

    def remove_module(self, module: BaseModule):
        if module in self._modules:
            self._modules.remove(module)
            module.cleanup()
            module.setParent(None)
            module.deleteLater()

    # ── Layout Toggle ───────────────────────────────────────────────────────

    def _toggle_layout(self):
        self._layout_vertical = not self._layout_vertical
        if self._layout_vertical:
            self.splitter.setOrientation(Qt.Vertical)
            self.title_bar.layout_btn.setText("▥")
            self.title_bar.layout_btn.setToolTip("Switch to Horizontal layout")
            self.splitter.setStyleSheet(f"""
                QSplitter::handle {{
                    background: {Colors.BORDER}; border-radius: 2px;
                    margin: 1px 30px;
                }}
                QSplitter::handle:hover {{ background: {Colors.ACCENT}; }}
            """)
        else:
            self.splitter.setOrientation(Qt.Horizontal)
            self.title_bar.layout_btn.setText("▤")
            self.title_bar.layout_btn.setToolTip("Switch to Vertical layout")
            self.splitter.setStyleSheet(f"""
                QSplitter::handle {{
                    background: {Colors.BORDER}; border-radius: 2px;
                    margin: 30px 1px;
                }}
                QSplitter::handle:hover {{ background: {Colors.ACCENT}; }}
            """)

    # ── Snapping ────────────────────────────────────────────────────────────

    def snap_to_edge(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        avail = screen.availableGeometry()
        x, y = self.pos().x(), self.pos().y()
        w, h = self.width(), self.height()
        t = self.SNAP_THRESHOLD

        if abs(x - avail.left()) < t:
            x = avail.left()
        elif abs(x + w - avail.right()) < t:
            x = avail.right() - w

        if abs(y - avail.top()) < t:
            y = avail.top()
        elif abs(y + h - avail.bottom()) < t:
            y = avail.bottom() - h

        cx = avail.left() + avail.width() // 2
        if abs(x + w // 2 - cx) < t:
            x = cx - w // 2

        self.move(x, y)

    # ── Events ──────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._grip.move(
            self.width() - self._grip.width() - 2,
            self.height() - self._grip.height() - 2,
        )

    def contextMenuEvent(self, event):
        self._show_gear_menu()

    def closeEvent(self, event):
        for m in self._modules:
            m.cleanup()
        self.audio_engine.stop()
        super().closeEvent(event)
