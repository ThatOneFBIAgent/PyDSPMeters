"""
Window Manager: Main application window with compact title bar,
module management, snapping logic, and theme switching.
"""

import math
import time
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
from app.settings import SettingsManager

# Ensure all modules register themselves
from app.modules import oscilloscope, loudness_meter, vu_meter  # noqa
from app.modules import stereometer, spectrum, spectrogram, waveform  # noqa


class LoadingOverlay(QWidget):
    """Professional splash overlay with animation."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._opacity = 1.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)
        self._start_time = QTimer.singleShot(0, lambda: None) # Placeholder
        import time
        self._birth = time.time()

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter
        with QPainter(self) as p:
            p.setRenderHint(QPainter.Antialiasing)
            
            # Background
            bg = QColor(Colors.BG_DARKEST)
            bg.setAlpha(int(255 * self._opacity))
            p.fillRect(self.rect(), bg)
            
            # Pulsing Logo
            pulse = (math.sin((time.time() - self._birth) * 5) + 1) * 0.5
            text_col = QColor(Colors.ACCENT)
            text_col.setAlpha(int((150 + 105 * pulse) * self._opacity))
            
            p.setPen(text_col)
            f = Fonts.header()
            f.setPointSize(24)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, "PYDSPMETERS")
            
            f.setPointSize(10)
            p.setFont(f)
            p.setPen(QColor(Colors.TEXT_DIM))
            p.drawText(self.rect().adjusted(0, 50, 0, 50), Qt.AlignCenter, "INITIALIZING ENGINE...")

    def fade_out(self):
        self._fade_timer = QTimer(self)
        def step():
            self._opacity -= 0.05
            if self._opacity <= 0:
                self._fade_timer.stop()
                self.hide()
                if self.parent() and hasattr(self.parent(), "_on_overlay_finished"):
                    self.parent()._on_overlay_finished()
                self.deleteLater()
            self.update()
        self._fade_timer.timeout.connect(step)
        self._fade_timer.start(20)


def _icon_btn(text, tooltip, size=22):
    btn = QPushButton(text)
    btn.setFixedSize(size, size)
    btn.setToolTip(tooltip)
    btn.setObjectName("titleBarButton")
    return btn


class TitleBar(QFrame):
    def __init__(self, parent_window, parent=None):
        super().__init__(parent)
        self._window = parent_window
        self._drag_pos = None
        self.setFixedHeight(28)
        self.setObjectName("titleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 4, 0)
        layout.setSpacing(2)

        self.logo = QLabel("DSP")
        self.logo.setFont(Fonts.header())
        layout.addWidget(self.logo)

        layout.addStretch()

        self.add_btn = _icon_btn("+", "Add module")
        layout.addWidget(self.add_btn)

        self.layout_btn = _icon_btn("▥", "Layout toggle")
        layout.addWidget(self.layout_btn)

        self.gear_btn = _icon_btn("⚙", "Settings")
        layout.addWidget(self.gear_btn)

        self.min_btn = _icon_btn("─", "Minimize")
        self.min_btn.clicked.connect(self._window.showMinimized)
        layout.addWidget(self.min_btn)

        self.close_btn = _icon_btn("×", "Close")
        self.close_btn.clicked.connect(self._window.close)
        layout.addWidget(self.close_btn)
        
        self.update_theme()

    def update_theme(self):
        self.setStyleSheet(f"#titleBar {{ background: {Colors.BG_DARKEST}; border-bottom: 1px solid {Colors.BORDER}; }}")
        self.logo.setStyleSheet(f"color: {Colors.ACCENT}; background: transparent; font-size: 10pt; font-weight: bold;")
        
        btn_style = f"QPushButton#titleBarButton {{ background: transparent; border: none; color: {Colors.TEXT_DIM}; " \
                    f"font-size: 10pt; padding: 0; margin: 0; min-height: 0px; min-width: 0px; }} " \
                    f"QPushButton#titleBarButton:hover {{ color: {Colors.ACCENT}; }}"
        
        for b in [self.add_btn, self.layout_btn, self.gear_btn, self.min_btn]:
            b.setStyleSheet(btn_style)
            
        self.close_btn.setStyleSheet(f"QPushButton#titleBarButton {{ background: transparent; border: none; color: {Colors.TEXT_DIM}; "
                                    f"font-size: 10pt; padding: 0; margin: 0; min-height: 0px; min-width: 0px; }} "
                                    f"QPushButton#titleBarButton:hover {{ color: {Colors.RED}; }}")

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
                max(60, self._window.width() + delta.x()),
                max(40, self._window.height() + delta.y()),
            )
            self._window.snap_to_edge()


class MainWindow(QMainWindow):
    """
    Main application window. Frameless, always-on-top,
    with module management, themes, and edge snapping.
    """

    SNAP_THRESHOLD = 20

    def __init__(self, audio_engine: AudioEngine, splash=None):
        super().__init__()
        self.audio_engine = audio_engine
        self._splash = splash
        self._settings = SettingsManager.load()

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(40, 40)
        self.resize(300, 650)
        self._loading_settings = True
        self._is_ready = False # Track if fully initialized
        
        # Loading Overlay (Internal window fade-in)
        self._loading_overlay = LoadingOverlay(self)
        self._loading_overlay.resize(self.size())
        self._loading_overlay.raise_()
        self._loading_overlay.show()

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
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setVisible(False)
        self.splitter.setHandleWidth(4)
        self.splitter.setChildrenCollapsible(False)
        main_layout.addWidget(self.splitter)
        
        self._layout_vertical = True
        self._update_ui_styles()

        # Resize grip
        self._grip = ResizeGrip(self)

        # Module list
        self._modules: list[BaseModule] = []

        # Connect title bar buttons
        self.title_bar.add_btn.clicked.connect(self._show_add_menu)
        self.title_bar.layout_btn.clicked.connect(self._toggle_layout)
        self.title_bar.gear_btn.clicked.connect(self._show_gear_menu)

        # Apply window settings
        
        # Apply window settings
        win_s = self._settings.get("window", {})
        if "width" in win_s and "height" in win_s:
            self.resize(win_s["width"], win_s["height"])
        if "x" in win_s and "y" in win_s:
            self.move(win_s["x"], win_s["y"])
        
        self._layout_vertical = win_s.get("vertical_layout", True)
        if not self._layout_vertical:
            self.splitter.setOrientation(Qt.Horizontal)
            self.title_bar.layout_btn.setText("▤")
        
        # Apply UI settings
        ui_s = self._settings.get("ui", {})
        Fonts.TEXT_SCALE = ui_s.get("text_scale", 1.0)
        initial_theme = ui_s.get("theme", "Midnight")
        apply_theme(initial_theme, ui_s.get("color_overrides", {}))
        self.setStyleSheet(build_stylesheet())
        
        self._show_headers = win_s.get("show_headers", True)
        self._auto_hide_ui = win_s.get("auto_hide_ui", False)
        
        # Divider settings (must be after apply_theme to use correct BORDER color)
        self.splitter.setHandleWidth(win_s.get("divider_width", 4))
        self._set_divider_opacity(win_s.get("divider_opacity", 100))

        # Audio settings
        audio_s = self._settings.get("audio", {})
        self.audio_engine.gain_multiplier = audio_s.get("gain", 1.0)
        self.audio_engine.channels = audio_s.get("channels", 2)
        self._target_device_id = audio_s.get("device_full_id") # Persistent identifier
        self._current_device = audio_s.get("device_index") # Fallback index
        
        # Modules
        module_items = self._settings.get("modules")
        if module_items is None:
            module_items = ["oscilloscope", "loudness", "spectrum"]
            
        for i, item in enumerate(module_items):
            m_key = item if isinstance(item, str) else item.get("key")
            m_config = {} if isinstance(item, str) else item.get("config", {})
            
            if self._splash:
                self._splash.set_progress(60 + int(30 * (i / len(module_items))), f"Loading {m_key}...")
                QApplication.processEvents()
            
            self.add_module(m_key, m_config)
            
        def finalize_load():
            self._loading_settings = False
            self.splitter.setVisible(True)
            
            saved_sizes = self._settings.get("splitter_sizes", [])
            if saved_sizes and len(saved_sizes) == self.splitter.count():
                self.splitter.setSizes(saved_sizes)
            else:
                # Fair distribution if no saved sizes or mismatch
                total = self.splitter.width() if not self._layout_vertical else self.splitter.height()
                count = self.splitter.count()
                if count > 0:
                    self.splitter.setSizes([total // count] * count)
            
            if hasattr(self, "_loading_overlay") and self._loading_overlay:
                self._loading_overlay.fade_out()
                    
        QTimer.singleShot(250, finalize_load)

        def start_audio():
            self._refresh_devices()
            best_index = None
            
            # Try to match by full_id first
            if self._target_device_id:
                for d in self._devices:
                    if d["full_id"] == self._target_device_id:
                        best_index = d["index"]
                        break
            
            # Fallback to index if valid
            if best_index is None and self._current_device is not None:
                if any(d["index"] == self._current_device for d in self._devices):
                    best_index = self._current_device
            
            self._current_device = best_index
            self.audio_engine.start(best_index)
            self._is_ready = True

        QTimer.singleShot(100, start_audio)

    # ── Device Management ───────────────────────────────────────────────────

    def _refresh_devices(self):
        self._devices = AudioEngine.list_devices()

    def _select_device(self, device_index, full_id=None):
        self._current_device = device_index
        self._target_device_id = full_id
        self.audio_engine.start(device_index)

    def _select_channels(self, count):
        self.audio_engine.channels = count
        self.audio_engine.start(self._current_device, count)
        # Refresh all modules to adapt to new channel count
        for m in self._modules:
            if hasattr(m, "on_channels_changed"):
                m.on_channels_changed()
            m.update()

    # ── Gear Menu (Device + Theme) ──────────────────────────────────────────

    def _show_gear_menu(self):
        from PySide6.QtWidgets import QWidgetAction, QSlider, QHBoxLayout
        menu = QMenu(self)
        
        # Force Midnight colors for settings for readability
        menu.setStyleSheet(f"""
            QMenu {{ background: #1a1a2e; border: 1px solid #3a3a6a; color: #d8d8f0; padding: 4px; }}
            QMenu::item {{ padding: 5px 20px; border-radius: 3px; color: #d8d8f0; }}
            QMenu::item:selected {{ background: #0088aa; color: #ffffff; }}
            QMenu::separator {{ height: 1px; background: #252545; margin: 4px 8px; }}
            QLabel {{ color: #a9b1d6; }}
            QSlider::groove:horizontal {{ background: #10101a; height: 4px; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: #00bbcc; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
        """)

        # Audio device submenu grouped by API
        dev_menu = menu.addMenu("🎤  Audio Device")
        default_action = QAction("Default Input", self)
        default_action.setCheckable(True)
        default_action.setChecked(self._current_device is None)
        default_action.triggered.connect(lambda: self._select_device(None))
        dev_menu.addAction(default_action)
        dev_menu.addSeparator()

        self._refresh_devices()
        
        # Channel count selection
        chan_menu = menu.addMenu("🔢  Channels")
        for c in [1, 2, 4, 6, 8]:
            action = QAction(f"{c} Channel{'s' if c > 1 else ''}", self)
            action.setCheckable(True)
            action.setChecked(self.audio_engine.channels == c)
            action.triggered.connect(lambda checked, count=c: self._select_channels(count))
            chan_menu.addAction(action)
            
        menu.addSeparator()

        apis = {}
        for d in self._devices:
            apis.setdefault(d["hostapi"], []).append(d)

        for api, devs in apis.items():
            api_menu = dev_menu.addMenu(api)
            for d in devs:
                label = d["name"]
                action = QAction(label, self)
                action.setCheckable(True)
                action.setChecked(self._current_device == d["index"])
                idx = d["index"]
                full_id = d["full_id"]
                action.triggered.connect(lambda checked, i=idx, fid=full_id: self._select_device(i, fid))
                api_menu.addAction(action)

        menu.addSeparator()

        # Overdrive (Gain) slider via QWidgetAction
        gain_act = QWidgetAction(self)
        gain_widget = QWidget()
        gain_layout = QHBoxLayout(gain_widget)
        gain_layout.setContentsMargins(10, 4, 10, 4)
        gain_label = QLabel("Input Overdrive:")
        gain_label.setFixedWidth(90)
        
        gain_slider = QSlider(Qt.Horizontal)
        gain_slider.setRange(0, 150)
        gain_slider.setValue(int(self.audio_engine.gain_multiplier * 100))
        gain_slider.setFixedWidth(110)
        
        from PySide6.QtWidgets import QLineEdit
        from PySide6.QtGui import QIntValidator
        gain_input = QLineEdit(str(gain_slider.value()))
        gain_input.setFixedWidth(40)
        gain_input.setAlignment(Qt.AlignCenter)
        gain_input.setValidator(QIntValidator(0, 150))
        gain_input.setStyleSheet(f"background: {Colors.BG_INPUT}; border: 1px solid {Colors.BORDER}; padding: 1px;")

        def on_gain_slider(v):
            self.audio_engine.gain_multiplier = v / 100.0
            gain_input.setText(str(v))

        def on_gain_text():
            try:
                v = int(gain_input.text())
                v = max(0, min(150, v))
                gain_slider.setValue(v)
                self.audio_engine.gain_multiplier = v / 100.0
            except: pass

        gain_slider.valueChanged.connect(on_gain_slider)
        gain_input.editingFinished.connect(on_gain_text)
        
        gain_layout.addWidget(gain_label)
        gain_layout.addWidget(gain_slider)
        gain_layout.addWidget(gain_input)
        gain_act.setDefaultWidget(gain_widget)
        menu.addAction(gain_act)

        # Text Scale Slider
        text_act = QWidgetAction(self)
        text_widget = QWidget()
        text_layout = QHBoxLayout(text_widget)
        text_layout.setContentsMargins(10, 4, 10, 4)
        text_label = QLabel("Label Scale:")
        text_label.setFixedWidth(90)
        
        text_slider = QSlider(Qt.Horizontal)
        text_slider.setRange(50, 150) # 50% to 150%
        text_slider.setValue(int(Fonts.TEXT_SCALE * 100))
        text_slider.setFixedWidth(110)
        
        text_val = QLabel(f"{text_slider.value()}%")
        text_val.setFixedWidth(40)
        text_val.setAlignment(Qt.AlignCenter)

        def on_text_scale(v):
            Fonts.TEXT_SCALE = v / 100.0
            text_val.setText(f"{v}%")
            # Trigger a refresh of the entire UI to update font sizes
            self.setStyleSheet(build_stylesheet())
            for m in self._modules:
                m.setStyleSheet(f"#baseModule {{ background: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; border-radius: 4px; }}")
                m.header.update() # Refresh header fonts if needed
        
        text_slider.valueChanged.connect(on_text_scale)
        
        text_layout.addWidget(text_label)
        text_layout.addWidget(text_slider)
        text_layout.addWidget(text_val)
        text_act.setDefaultWidget(text_widget)
        menu.addAction(text_act)

        menu.addSeparator()

        # UI Settings
        hdr_action = QAction("Show Module Headers", self)
        hdr_action.setCheckable(True)
        hdr_action.setChecked(self._show_headers)
        hdr_action.triggered.connect(self._toggle_headers)
        menu.addAction(hdr_action)
        
        ghost_action = QAction("Auto-Hide Title Bar", self)
        ghost_action.setCheckable(True)
        ghost_action.setChecked(self._auto_hide_ui)
        ghost_action.triggered.connect(self._toggle_ghost_mode)
        menu.addAction(ghost_action)
        
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

        menu.addSeparator()
        
        # Divider Settings
        div_menu = menu.addMenu("📏  Divider Settings")
        
        # Width
        w_act = QWidgetAction(self)
        w_widget = QWidget()
        w_layout = QHBoxLayout(w_widget)
        w_label = QLabel("Width:")
        w_label.setFixedWidth(60)
        w_slider = QSlider(Qt.Horizontal)
        w_slider.setRange(0, 12)
        w_slider.setValue(self.splitter.handleWidth())
        w_slider.valueChanged.connect(self._set_divider_width)
        w_layout.addWidget(w_label)
        w_layout.addWidget(w_slider)
        w_act.setDefaultWidget(w_widget)
        div_menu.addAction(w_act)
        
        # Visibility (Opacity)
        o_act = QWidgetAction(self)
        o_widget = QWidget()
        o_layout = QHBoxLayout(o_widget)
        o_label = QLabel("Opacity:")
        o_label.setFixedWidth(60)
        o_slider = QSlider(Qt.Horizontal)
        o_slider.setRange(0, 100)
        # We'll simulate this by setting stylesheet handle color
        o_slider.setValue(self._settings.get("window", {}).get("divider_opacity", 100))
        o_slider.valueChanged.connect(self._set_divider_opacity)
        o_layout.addWidget(o_label)
        o_layout.addWidget(o_slider)
        o_act.setDefaultWidget(o_widget)
        div_menu.addAction(o_act)

        menu.exec(QCursor.pos())

    def _toggle_headers(self, show: bool):
        self._show_headers = show
        for m in self._modules:
            m.header.setVisible(show)

    def _toggle_ghost_mode(self, enabled: bool):
        self._auto_hide_ui = enabled
        self._update_ghost_mode()

    def _apply_theme(self, name: str):
        apply_theme(name, self._settings.get("ui", {}).get("color_overrides", {}))
        app = QApplication.instance()
        if app:
            app.setStyleSheet(build_stylesheet())
        self._update_ui_styles()
        for m in self._modules:
            if hasattr(m, "on_theme_changed"):
                m.on_theme_changed()
            m.update_theme() # New helper or manual update
        self._update_ghost_mode()

    def _update_ui_styles(self):
        # Title Bar & Buttons
        if hasattr(self, "title_bar"):
            self.title_bar.update_theme()
        
        # Splitter handle
        self._set_divider_opacity(self._settings.get("window", {}).get("divider_opacity", 100))

    def _set_divider_width(self, w):
        self.splitter.setHandleWidth(w)
        
    def _set_divider_opacity(self, alpha_pct):
        win_s = self._settings.setdefault("window", {})
        win_s["divider_opacity"] = alpha_pct
        
        # 1. Parse base color from theme
        b_hex = Colors.BORDER
        if b_hex.startswith("#") and len(b_hex) == 9:
            c = QColor()
            c.setAlpha(int(b_hex[1:3], 16))
            c.setRed(int(b_hex[3:5], 16))
            c.setGreen(int(b_hex[5:7], 16))
            c.setBlue(int(b_hex[7:9], 16))
        else:
            c = QColor(b_hex)
            
        c.setAlpha(int(c.alpha() * alpha_pct / 100))
        color_str = f"rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha()})"
        
        h_c = QColor(Colors.ACCENT)
        h_c.setAlpha(int(h_c.alpha() * alpha_pct / 100))
        hover_str = f"rgba({h_c.red()}, {h_c.green()}, {h_c.blue()}, {h_c.alpha()})"

        # 2. Apply local stylesheet to the splitter
        # We use different margins based on orientation to keep it clean
        if self.splitter.orientation() == Qt.Vertical:
            margin = "1px 40px" # Horizontal bar
        else:
            margin = "40px 1px" # Vertical bar
            
        theme = current_theme_name()
        is_transparent = "Transparent" in theme or "Glass" in theme
        
        if is_transparent:
            bg_rgba = "transparent"
        else:
            bg_c = QColor(Colors.BG_DARKEST)
            bg_rgba = f"rgba({bg_c.red()}, {bg_c.green()}, {bg_c.blue()}, {bg_c.alpha()})"

        self.splitter.setStyleSheet(f"""
            QSplitter {{
                background: {bg_rgba};
            }}
            QSplitter::handle {{
                background-color: {color_str if c.alpha() > 0 else "transparent"};
                margin: {margin};
                border-radius: 2px;
            }}
            QSplitter::handle:hover {{
                background-color: {hover_str};
            }}
        """)

    def _update_ghost_mode(self):
        # Ghost mode active if manually toggled OR if it's a 'Ghost/Glass/Transparent' theme
        theme = current_theme_name()
        is_transparent = "Transparent" in theme or "Glass" in theme
        ghost_active = self._auto_hide_ui or is_transparent
        
        show = not ghost_active or self.underMouse()
        self.title_bar.setVisible(show)
        self._grip.setVisible(show)

    def enterEvent(self, event):
        self._update_ghost_mode()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._update_ghost_mode()
        super().leaveEvent(event)

    # ── Module Management ───────────────────────────────────────────────────

    def _show_add_menu(self):
        menu = QMenu(self)
        for key, info in MODULE_REGISTRY.items():
            action = QAction(info["display_name"], self)
            action.triggered.connect(lambda checked, k=key: self.add_module(k))
            menu.addAction(action)
        menu.exec(QCursor.pos())

    def add_module(self, module_key: str, config: dict = None):
        if module_key not in MODULE_REGISTRY:
            return
        cls = MODULE_REGISTRY[module_key]["class"]
        module = cls(self.audio_engine)
        module.module_key = module_key # Store for saving
        module.close_requested.connect(self.remove_module)
        module.move_requested.connect(self._move_module)
        
        if config:
            module.apply_settings(config)
            
        # Apply header visibility
        module.header.setVisible(self._show_headers)
        
        self.splitter.addWidget(module)
        self._modules.append(module)
        
        # Ensure new module is visible
        if self._loading_settings:
            return # Don't redistribute while loading, we'll set sizes once at the end
            
        sizes = self.splitter.sizes()
        if len(sizes) > 1:
            total = sum(sizes)
            if total > 0:
                # Manual add: Try to give new module a fair share without flattening everyone
                # We give the new module 1/Nth of the space, and reduce others proportionally
                new_share = total // len(sizes)
                remaining = total - new_share
                old_total = sum(sizes[:-1])
                if old_total > 0:
                    new_sizes = [int(s * remaining / old_total) for s in sizes[:-1]]
                    new_sizes.append(new_share)
                    # Adjust for rounding errors
                    diff = total - sum(new_sizes)
                    new_sizes[0] += diff
                    self.splitter.setSizes(new_sizes)
                else:
                    self.splitter.setSizes([total // len(sizes)] * len(sizes))
            else:
                self.splitter.setSizes([100] * len(sizes))

    def remove_module(self, module: BaseModule):
        if module in self._modules:
            self._modules.remove(module)
            module.cleanup()
            module.setParent(None)
            module.deleteLater()

    def _move_module(self, module, direction):
        idx = self.splitter.indexOf(module)
        new_idx = idx + direction
        if 0 <= new_idx < self.splitter.count():
            # In QSplitter, insertWidget moves the widget if it's already there
            self.splitter.insertWidget(new_idx, module)

    # ── Layout Toggle ───────────────────────────────────────────────────────

    def _toggle_layout(self):
        self._layout_vertical = not self._layout_vertical
        if self._layout_vertical:
            self.splitter.setOrientation(Qt.Vertical)
            self.title_bar.layout_btn.setText("▥")
            self.title_bar.layout_btn.setToolTip("Switch to Horizontal layout")
        else:
            self.splitter.setOrientation(Qt.Horizontal)
            self.title_bar.layout_btn.setText("▤")
            self.title_bar.layout_btn.setToolTip("Switch to Vertical layout")
            
        # Refresh divider style to update margins and respect opacity
        self._set_divider_opacity(self._settings.get("window", {}).get("divider_opacity", 100))

    # ── Snapping ────────────────────────────────────────────────────────────
    
    def snap_to_edge(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        
        avail = screen.availableGeometry()
        full = screen.geometry()
        x, y = self.pos().x(), self.pos().y()
        w, h = self.width(), self.height()
        t = self.SNAP_THRESHOLD

        # ── Horizontal Snapping (Position & Size) ───────────────────────────
        
        # Snap width to full/avail width
        if abs(w - avail.width()) < t:
            w = avail.width()
        elif abs(w - full.width()) < t:
            w = full.width()

        # Snap X position
        # Prioritize 'avail' (above taskbar) but allow 'full' (behind taskbar)
        for rect in [avail, full]:
            if abs(x - rect.left()) < t:
                x = rect.left()
                break
            if abs(x + w - rect.right()) < t:
                x = rect.right() - w
                break

        # Center horizontal
        cx = full.left() + full.width() // 2
        if abs(x + w // 2 - cx) < t:
            x = cx - w // 2

        # ── Vertical Snapping (Position & Size) ─────────────────────────────
        
        # Snap height to full/avail height
        if abs(h - avail.height()) < t:
            h = avail.height()
        elif abs(h - full.height()) < t:
            h = full.height()

        # Snap Y position
        for rect in [avail, full]:
            if abs(y - rect.top()) < t:
                y = rect.top()
                break
            if abs(y + h - rect.bottom()) < t:
                y = rect.bottom() - h
                break

        # Apply changes
        if (w, h) != (self.width(), self.height()):
            self.resize(w, h)
        self.move(x, y)

    # ── Events ──────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._grip.move(
            self.width() - self._grip.width() - 2,
            self.height() - self._grip.height() - 2,
        )
        if hasattr(self, "_loading_overlay") and self._loading_overlay and self._loading_overlay.isVisible():
            try:
                self._loading_overlay.resize(self.size())
            except:
                self._loading_overlay = None

    def _on_overlay_finished(self):
        self._loading_overlay = None

    def contextMenuEvent(self, event):
        self._show_gear_menu()

    def closeEvent(self, event):
        """Handle application exit: Save settings and try clean quit."""
        # Prepare settings for saving
        settings = {
            "window": {
                "x": self.pos().x(),
                "y": self.pos().y(),
                "width": self.width(),
                "height": self.height(),
                "vertical_layout": self._layout_vertical,
                "show_headers": self._show_headers,
                "auto_hide_ui": self._auto_hide_ui,
                "divider_width": self.splitter.handleWidth(),
                "divider_opacity": self._settings.get("window", {}).get("divider_opacity", 100)
            },
            "audio": {
                "device_index": self._current_device,
                "device_full_id": getattr(self, "_target_device_id", None),
                "gain": self.audio_engine.gain_multiplier,
                "channels": self.audio_engine.channels
            },
            "ui": {
                "theme": current_theme_name(),
                "text_scale": Fonts.TEXT_SCALE,
                "color_overrides": self._settings.get("ui", {}).get("color_overrides", {})
            },
            "modules": [{"key": m.module_key, "config": m.get_settings()} for m in self._modules],
            "splitter_sizes": self.splitter.sizes()
        }
        SettingsManager.save(settings)

        self.audio_engine.stop()
        event.accept()
        QApplication.instance().quit()
        
        # Safety fallback: if the process is still alive in 500ms, force it out.
        import os
        QTimer.singleShot(500, lambda: os._exit(0))
