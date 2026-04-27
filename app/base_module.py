"""
Base class for all visualization modules.
Provides a collapsible settings panel, header bar, and audio data hookup.
"""

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QComboBox, QSlider, QCheckBox,
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QIcon

from app.theme import Colors, Fonts


class ModuleHeader(QFrame):
    """Compact header bar with title, settings toggle, and close button."""

    settings_toggled = Signal(bool)
    close_requested = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self.setObjectName("moduleHeader")
        self.setStyleSheet(f"""
            #moduleHeader {{
                background: {Colors.BG_HEADER};
                border-bottom: 1px solid {Colors.BORDER};
                border-radius: 0px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(4)

        self._title = QLabel(title)
        self._title.setFont(Fonts.header())
        self._title.setStyleSheet(f"color: {Colors.ACCENT}; background: transparent; font-size: 8pt; font-weight: normal;")
        layout.addWidget(self._title)

        layout.addStretch()

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setFixedSize(22, 22)
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Colors.TEXT_DIM};
                font-size: 12pt;
                padding: 0;
            }}
            QPushButton:hover {{ color: {Colors.ACCENT}; }}
        """)
        self._settings_btn.clicked.connect(self._toggle_settings)
        layout.addWidget(self._settings_btn)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.setToolTip("Remove module")
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {Colors.TEXT_DIM};
                font-size: 10pt;
                padding: 0;
            }}
            QPushButton:hover {{ color: {Colors.RED}; }}
        """)
        self._close_btn.clicked.connect(self.close_requested.emit)
        layout.addWidget(self._close_btn)

        self._settings_open = False

    def _toggle_settings(self):
        self._settings_open = not self._settings_open
        self.settings_toggled.emit(self._settings_open)

    def set_title(self, title: str):
        self._title.setText(title)


class SettingsPanel(QFrame):
    """Collapsible settings panel that slides open below the header."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPanel")
        self.setStyleSheet(f"""
            #settingsPanel {{
                background: {Colors.BG_SETTINGS};
                border-bottom: 1px solid {Colors.BORDER};
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 6, 8, 6)
        self._layout.setSpacing(4)

        self.setMaximumHeight(0)
        self._expanded = False

    def add_row(self, label_text: str, widget: QWidget) -> QWidget:
        """Add a labeled setting row."""
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(70)
        lbl.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 8pt; background: transparent;")
        row.addWidget(lbl)
        row.addWidget(widget)
        self._layout.addLayout(row)
        return widget

    def add_combo(self, label: str, items: list[str],
                  default: int = 0) -> QComboBox:
        """Convenience: add a combo box setting."""
        combo = QComboBox()
        combo.addItems(items)
        combo.setCurrentIndex(default)
        self.add_row(label, combo)
        return combo

    def add_slider(self, label: str, min_val: int = 0, max_val: int = 100,
                   default: int = 50) -> QSlider:
        """Convenience: add a horizontal slider setting."""
        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        self.add_row(label, slider)
        return slider

    def add_checkbox(self, label: str, checked: bool = False) -> QCheckBox:
        """Convenience: add a checkbox setting."""
        cb = QCheckBox()
        cb.setChecked(checked)
        self.add_row(label, cb)
        return cb

    def toggle(self, show: bool):
        """Animate expand/collapse."""
        self._expanded = show
        target_h = self.sizeHint().height() if show else 0
        anim = QPropertyAnimation(self, b"maximumHeight", self)
        anim.setDuration(200)
        anim.setStartValue(self.maximumHeight())
        anim.setEndValue(target_h)
        anim.setEasingCurve(QEasingCurve.InOutCubic)
        anim.start(QPropertyAnimation.DeleteWhenStopped)


class RenderCanvas(QWidget):
    """
    Drawing surface for visualizations.
    Modules set a render callback via set_render_func(fn).
    The callback receives (painter, w, h) with an already-active QPainter.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self._render_func = None

    def set_render_func(self, func):
        """Set external render callback: func(painter, width, height)."""
        self._render_func = func

    def paintEvent(self, event):
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(Colors.BG_MODULE))
        w, h = self.width(), self.height()
        if self._render_func and w > 0 and h > 0:
            try:
                self._render_func(painter, w, h)
            except Exception:
                pass  # Silently handle render errors
        painter.end()


class BaseModule(QWidget):
    """
    Base class for all visualization modules.

    Subclasses must:
      1. Call super().__init__() with a title.
      2. Override `setup_settings()` to add controls to self.settings.
      3. Override `on_audio_data(data)` to process incoming audio.
      4. Override `canvas.render(painter, w, h)` via self.canvas for drawing.
    """

    close_requested = Signal(object)  # emits self

    def __init__(self, audio_engine, title: str = "Module", parent=None):
        super().__init__(parent)
        self.audio_engine = audio_engine
        self._title = title

        self.setObjectName("baseModule")
        self.setStyleSheet(f"""
            #baseModule {{
                background: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
            }}
        """)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self.header = ModuleHeader(title)
        self.header.close_requested.connect(lambda: self.close_requested.emit(self))
        layout.addWidget(self.header)

        # Settings panel
        self.settings = SettingsPanel()
        self.header.settings_toggled.connect(self.settings.toggle)
        layout.addWidget(self.settings)

        # Render canvas
        self.canvas = RenderCanvas()
        layout.addWidget(self.canvas)

        # Setup settings (subclass hook)
        self.setup_settings()

        # Connect to audio engine
        self.audio_engine.data_ready.connect(self.on_audio_data)

        # Refresh timer
        from PySide6.QtCore import QTimer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(16)  # ~60 fps
        self._refresh_timer.timeout.connect(self.canvas.update)
        self._refresh_timer.start()

    def setup_settings(self):
        """Override to add settings widgets to self.settings."""
        pass

    def on_audio_data(self, data: np.ndarray):
        """
        Override to process incoming audio data.
        Called on the main thread with shape (block_size, 2).
        """
        pass

    def cleanup(self):
        """Called when the module is being removed."""
        self._refresh_timer.stop()
        try:
            self.audio_engine.data_ready.disconnect(self.on_audio_data)
        except RuntimeError:
            pass
