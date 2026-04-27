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
    """Compact header bar with title and close button."""

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

        # Close button
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

    def set_title(self, title: str):
        self._title.setText(title)





class RenderCanvas(QWidget):
    """
    Drawing surface for visualizations.
    Modules set a render callback via set_render_func(fn).
    The callback receives (painter, w, h) with an already-active QPainter.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(30)
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
      2. Override `build_context_menu(menu)` to add QActions.
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

        # Render canvas
        self.canvas = RenderCanvas()
        layout.addWidget(self.canvas)

        # Connect to audio engine
        self.audio_engine.data_ready.connect(self.on_audio_data)

        # Refresh timer
        from PySide6.QtCore import QTimer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(16)  # ~60 fps
        self._refresh_timer.timeout.connect(self.canvas.update)
        self._refresh_timer.start()

    def build_context_menu(self, menu):
        """Override to add QActions to the module's right-click menu."""
        pass

    @staticmethod
    def draw_text_badge(painter, rect, align, text, text_pen, bg_color=None):
        """Draws text with a rounded, padded background for readability."""
        if bg_color is None:
            bg_color = QColor(0, 0, 0, 150)
            
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(painter.font())
        if hasattr(rect, 'toRect'):
            rect = rect.toRect()
            
        br = fm.boundingRect(rect, align, text)
        pad_x, pad_y = 6, 2
        br.adjust(-pad_x, -pad_y, pad_x, pad_y)
        
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(br, 4, 4)
        
        painter.setPen(text_pen)
        painter.drawText(rect, align, text)
        painter.restore()

    def contextMenuEvent(self, event):
        """Show settings via right-click."""
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        
        self.build_context_menu(menu)
        
        if not menu.isEmpty():
            menu.addSeparator()
            
        remove_action = menu.addAction("✕ Remove Module")
        remove_action.triggered.connect(lambda: self.close_requested.emit(self))
        
        menu.exec(event.globalPos())

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
