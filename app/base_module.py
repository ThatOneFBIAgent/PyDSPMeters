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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(4)

        self._title = QLabel(title)
        self._title.setFont(Fonts.header())
        layout.addWidget(self._title)

        layout.addStretch()

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.setToolTip("Remove module")
        self._close_btn.clicked.connect(self.close_requested.emit)
        layout.addWidget(self._close_btn)

        self.update_theme()

    def update_theme(self):
        self.setStyleSheet(f"#moduleHeader {{ background: {Colors.BG_HEADER}; border-bottom: 1px solid {Colors.BORDER}; }}")
        self._title.setStyleSheet(f"color: {Colors.ACCENT}; background: transparent; font-size: 8pt; font-weight: normal;")
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
                import traceback
                traceback.print_exc()
        painter.end()


class BaseModule(QWidget):
    """
    Base class for all visualization modules.
    """

    close_requested = Signal(object)  # emits self
    move_requested = Signal(object, int)  # emits self, direction (-1 or 1)

    def __init__(self, audio_engine, title: str = "Module", parent=None):
        super().__init__(parent)
        self.audio_engine = audio_engine
        self._title = title
        self.setObjectName("baseModule")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = ModuleHeader(title)
        self.header.close_requested.connect(lambda: self.close_requested.emit(self))
        layout.addWidget(self.header)

        self.canvas = RenderCanvas()
        layout.addWidget(self.canvas)

        self.update_theme()
        self.audio_engine.data_ready.connect(self.on_audio_data)

        from PySide6.QtCore import QTimer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(16)
        self._refresh_timer.timeout.connect(self.canvas.update)
        self._refresh_timer.start()

    def update_theme(self):
        self.setStyleSheet(f"#baseModule {{ background: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; border-radius: 4px; }}")
        if hasattr(self, "header"):
            self.header.update_theme()

    @staticmethod
    def get_responsive_font(font_func, w=None, h=None, text=None, min_size=5):
        """
        Returns a font scaled by the global TEXT_SCALE, but further reduced
        if it doesn't fit within the given width/height constraints.
        """
        try:
            if not callable(font_func):
                return QFont()
                
            font = font_func() # Gets the global scaled font
            size = font.pointSize()
            if size <= 0: size = 8 # Safety fallback
            
            # If dimensions are too small to calculate, just return the base font
            if (w is not None and w <= 0) or (h is not None and h <= 0):
                return font

            # Vertical constraint check
            if h is not None and h < size * 1.6:
                size = max(min_size, int(h * 0.6))
                font.setPointSize(size)
                
            # Horizontal constraint check (if text is provided)
            if text and w is not None:
                from PySide6.QtGui import QFontMetrics
                fm = QFontMetrics(font)
                # Avoid infinite loops if horizontalAdvance is broken
                limit = 20
                txt_str = str(text)
                while fm.horizontalAdvance(txt_str) > w * 0.95 and size > min_size and limit > 0:
                    size -= 1
                    font.setPointSize(size)
                    fm = QFontMetrics(font)
                    limit -= 1
                    
            return font
        except Exception as e:
            import traceback
            print(f"Responsive Font Error for '{text}': {e}")
            traceback.print_exc()
            return font_func() if callable(font_func) else QFont()

    def self_test(self):
        """Perform a basic health check on the module."""
        issues = []
        if not hasattr(self, 'canvas') or self.canvas is None:
            issues.append("Canvas not initialized")
        if not hasattr(self, 'audio_engine') or self.audio_engine is None:
            issues.append("Audio engine not connected")
        
        if issues:
            print(f"[{self._title}] Self-Test Failed: {', '.join(issues)}")
            return False
        return True

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
        from app.theme import Fonts
        pad_x = int(6 * Fonts.TEXT_SCALE)
        pad_y = int(2 * Fonts.TEXT_SCALE)
        br.adjust(-pad_x, -pad_y, pad_x, pad_y)
        
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(br, int(4 * Fonts.TEXT_SCALE), int(4 * Fonts.TEXT_SCALE))
        
        painter.setPen(text_pen)
        painter.drawText(rect, align, text)
        painter.restore()

    def contextMenuEvent(self, event):
        """Show settings via right-click."""
        from PySide6.QtWidgets import QMenu, QSplitter
        menu = QMenu(self)
        
        self.build_context_menu(menu)
        
        if not menu.isEmpty():
            menu.addSeparator()
            
        # Determine orientation for better labels
        parent = self.parentWidget()
        is_vert = False
        if isinstance(parent, QSplitter):
            is_vert = parent.orientation() == Qt.Vertical

        # Movement
        move_menu = menu.addMenu("⇅ Move Module")
        if is_vert:
            up_act = move_menu.addAction("↑ Move Up")
            up_act.triggered.connect(lambda: self.move_requested.emit(self, -1))
            down_act = move_menu.addAction("↓ Move Down")
            down_act.triggered.connect(lambda: self.move_requested.emit(self, 1))
        else:
            left_act = move_menu.addAction("← Move Left")
            left_act.triggered.connect(lambda: self.move_requested.emit(self, -1))
            right_act = move_menu.addAction("→ Move Right")
            right_act.triggered.connect(lambda: self.move_requested.emit(self, 1))

        menu.addSeparator()
        remove_action = menu.addAction("✕ Remove Module")
        remove_action.triggered.connect(lambda: self.close_requested.emit(self))
        
        menu.exec(event.globalPos())

    def on_audio_data(self, data: np.ndarray):
        """
        Override to process incoming audio data.
        Called on the main thread with shape (block_size, channels).
        """
        pass

    def get_settings(self) -> dict:
        """Override to return a dict of settings to persist."""
        return {}

    def apply_settings(self, settings: dict):
        """Override to apply persisted settings."""
        pass

    def cleanup(self):
        """Called when the module is being removed."""
        self._refresh_timer.stop()
        try:
            self.audio_engine.data_ready.disconnect(self.on_audio_data)
        except RuntimeError:
            pass
        except Exception:
            pass
