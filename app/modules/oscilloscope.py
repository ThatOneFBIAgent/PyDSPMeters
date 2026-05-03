"""
Oscilloscope Module: Real-time waveform display with zero-crossing trigger.
"""

import numpy as np
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath
from PySide6.QtCore import Qt

from app.base_module import BaseModule
from app.modules import register_module
from app.theme import Colors


@register_module("oscilloscope", "Oscilloscope")
class OscilloscopeModule(BaseModule):

    def __init__(self, audio_engine, parent=None):
        self._waveform_l = np.zeros(8192, dtype=np.float32)
        self._waveform_r = np.zeros(8192, dtype=np.float32)
        self._display_samples = 1024
        self._channel = "L+R"
        self._display_mode = "Dual" if audio_engine.channels >= 2 else "Overlay"
        self._orientation = "Horizontal"
        self._grid_pixmap = None
        self._last_size = (0, 0)
        self.module_key = "oscilloscope"
        super().__init__(audio_engine, title="Oscilloscope", parent=parent)
        self.canvas.set_render_func(self._render)

    def get_settings(self):
        return {
            "display_samples": self._display_samples,
            "channel": self._channel,
            "display_mode": getattr(self, "_display_mode", "Overlay"),
            "orientation": getattr(self, "_orientation", "Horizontal")
        }

    def apply_settings(self, settings):
        self._display_samples = settings.get("display_samples", self._display_samples)
        self._channel = settings.get("channel", self._channel)
        self._display_mode = settings.get("display_mode", getattr(self, "_display_mode", "Overlay"))
        self._orientation = settings.get("orientation", getattr(self, "_orientation", "Horizontal"))

    def build_context_menu(self, menu):
        from PySide6.QtGui import QActionGroup
        cm = menu.addMenu("Channel")
        cg = QActionGroup(self)
        for c in ["L+R", "Left", "Right", "Mid", "Side"]:
            a = cm.addAction(c)
            a.setCheckable(True)
            a.setChecked(c == self._channel)
            a.triggered.connect(lambda checked, ch=c: setattr(self, "_channel", ch))
            cg.addAction(a)
            
        om = menu.addMenu("Orientation")
        og = QActionGroup(self)
        for o in ["Auto", "Horizontal", "Vertical"]:
            a = om.addAction(o)
            a.setCheckable(True)
            a.setChecked(o == getattr(self, "_orientation", "Horizontal"))
            a.triggered.connect(lambda checked, v=o: setattr(self, "_orientation", v))
            og.addAction(a)

        dm = menu.addMenu("Display Mode")
        dm.setEnabled(self._channel == "L+R")
        dg = QActionGroup(self)
        for d in ["Overlay", "Dual"]:
            a = dm.addAction(d)
            a.setCheckable(True)
            a.setChecked(d == getattr(self, "_display_mode", "Overlay"))
            a.triggered.connect(lambda checked, v=d: setattr(self, "_display_mode", v))
            dg.addAction(a)

        zm = menu.addMenu("Zoom Samples")
        zg = QActionGroup(self)
        for z in [256, 512, 1024, 2048, 4096, 8192]:
            a = zm.addAction(str(z))
            a.setCheckable(True)
            a.setChecked(z == self._display_samples)
            a.triggered.connect(lambda checked, zv=z: setattr(self, "_display_samples", zv))
            zg.addAction(a)

    def on_audio_data(self, data: np.ndarray):
        n = len(data)
        buf_len = len(self._waveform_l)
        
        if n >= buf_len:
            self._waveform_l[:] = data[-buf_len:, 0]
            if data.shape[1] > 1:
                self._waveform_r[:] = data[-buf_len:, 1]
            else:
                self._waveform_r[:] = data[-buf_len:, 0]
        else:
            self._waveform_l = np.roll(self._waveform_l, -n)
            self._waveform_l[-n:] = data[:, 0]
            r = data[:, 1] if data.shape[1] > 1 else data[:, 0]
            self._waveform_r = np.roll(self._waveform_r, -n)
            self._waveform_r[-n:] = r

    def _find_trigger(self, data):
        # Use NumPy for faster zero-crossing detection
        search_limit = len(data) - self._display_samples
        if search_limit <= 0: return 0
        
        # Look for zero crossing in the first half of the buffer
        subset = data[:search_limit]
        crossings = np.where((subset[:-1] <= 0) & (subset[1:] > 0))[0]
        if len(crossings) > 0:
            return crossings[0]
        return 0

    def _get_channels(self):
        l, r = self._waveform_l, self._waveform_r
        if self._channel == "Left": return [l]
        if self._channel == "Right": return [r]
        if self._channel == "Mid": return [(l + r) * 0.5]
        if self._channel == "Side": return [(l - r) * 0.5]
        return [l, r]

    def _update_grid(self, w, h):
        from PySide6.QtGui import QPixmap, QPen
        self._grid_pixmap = QPixmap(w, h)
        self._grid_pixmap.fill(Qt.transparent)
        
        painter = QPainter(self._grid_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Grid Colors
        grid_col = QColor(Colors.GRID)
        grid_col.setAlpha(60)
        strong_col = QColor(Colors.GRID)
        strong_col.setAlpha(120)
        
        is_vert = self._orientation == "Vertical"
        if self._orientation == "Auto":
            is_vert = h > w * 1.2
            
        # 1. Main Axes
        painter.setPen(QPen(strong_col, 1, Qt.DashLine))
        if is_vert:
            mid_x = w / 2
            painter.drawLine(int(mid_x), 0, int(mid_x), h)
            # Time divisions
            painter.setPen(QPen(grid_col, 1))
            for i in range(1, 8):
                y = int(h * i / 8)
                painter.drawLine(0, y, w, y)
        else:
            mid_y = h / 2
            painter.drawLine(0, int(mid_y), w, int(mid_y))
            # Time divisions
            painter.setPen(QPen(grid_col, 1))
            for i in range(1, 8):
                x = int(w * i / 8)
                painter.drawLine(x, 0, x, h)
                
        # 2. 'Funky' Sub-ticks (Non-linear diagnostic look)
        painter.setPen(QPen(grid_col, 0.5))
        if is_vert:
            for i in range(1, 16):
                # logarithmic or sine-spaced ticks for 'funky' look
                f = np.sin(i / 16 * np.pi / 2)
                x1 = int(w/2 + w/2 * f)
                x2 = int(w/2 - w/2 * f)
                painter.drawLine(x1, 0, x1, 4)
                painter.drawLine(x1, h-4, x1, h)
                painter.drawLine(x2, 0, x2, 4)
                painter.drawLine(x2, h-4, x2, h)
        else:
            for i in range(1, 16):
                f = np.sin(i / 16 * np.pi / 2)
                y1 = int(h/2 + h/2 * f)
                y2 = int(h/2 - h/2 * f)
                painter.drawLine(0, y1, 4, y1)
                painter.drawLine(w-4, y1, w, y1)
                painter.drawLine(0, y2, 4, y2)
                painter.drawLine(w-4, y2, w, y2)

        # 3. Corner Markers
        cs = 8
        painter.setPen(QPen(strong_col, 1.5))
        painter.drawLine(0, 0, cs, 0); painter.drawLine(0, 0, 0, cs) # TL
        painter.drawLine(w, 0, w-cs, 0); painter.drawLine(w, 0, w, cs) # TR
        painter.drawLine(0, h, cs, h); painter.drawLine(0, h, 0, h-cs) # BL
        painter.drawLine(w, h, w-cs, h); painter.drawLine(w, h, w, h-cs) # BR
        
        painter.end()
        self._last_size = (w, h)

    def _render(self, painter, w, h):
        if (w, h) != self._last_size or self._grid_pixmap is None:
            self._update_grid(w, h)
            
        if self._grid_pixmap:
            painter.drawPixmap(0, 0, self._grid_pixmap)
            
        is_vert = self._orientation == "Vertical"
        if self._orientation == "Auto":
            is_vert = h > w * 1.2
            
        display_chans = self._get_channels()
        colors = [Colors.ACCENT, Colors.ACCENT_PINK]
        mode = getattr(self, "_display_mode", "Overlay")
        
        if is_vert:
            if mode == "Dual" and len(display_chans) > 1:
                n_ch = len(display_chans)
                ch_w = w / n_ch
                for idx, ch in enumerate(display_chans):
                    cx = ch_w * (idx + 0.5)
                    self._draw_trace(painter, ch, w, h, cx, ch_w * 0.45, colors[idx % 2], vertical=True)
            else:
                mid_x = w / 2
                for idx, ch in enumerate(display_chans):
                    self._draw_trace(painter, ch, w, h, mid_x, w * 0.45, colors[idx % 2], vertical=True)
        else:
            if mode == "Dual" and len(display_chans) > 1:
                n_ch = len(display_chans)
                ch_h = h / n_ch
                for idx, ch in enumerate(display_chans):
                    cy = ch_h * (idx + 0.5)
                    self._draw_trace(painter, ch, w, h, cy, ch_h * 0.45, colors[idx % 2], vertical=False)
            else:
                mid_y = h / 2
                for idx, ch in enumerate(display_chans):
                    self._draw_trace(painter, ch, w, h, mid_y, h * 0.45, colors[idx % 2], vertical=False)

    def _draw_trace(self, painter, ch, w, h, center, factor, color, vertical=False):
        trig = self._find_trigger(ch)
        seg = ch[trig:trig + self._display_samples]
        if len(seg) < 2: return
        
        # Determine number of points based on the long axis
        long_axis = h if vertical else w
        num_points = min(len(seg), int(long_axis))
        if num_points < 2: return
        
        indices = np.linspace(0, len(seg) - 1, num_points).astype(np.int32)
        downsampled = seg[indices]
        
        # Waveform values with clipping ("maxing" at bounds)
        # We clip at 1.0/-1.0 relative to the center and factor
        # If user wants "maxing" specifically when hitting the top/bottom:
        vals = np.clip(downsampled, -1.0, 1.0)
        
        t_coords = np.linspace(0, long_axis, num_points)
        v_coords = center - vals * factor
        
        from PySide6.QtCore import QPointF
        if vertical:
            points = [QPointF(v_coords[i], t_coords[i]) for i in range(num_points)]
        else:
            points = [QPointF(t_coords[i], v_coords[i]) for i in range(num_points)]
        
        gc = QColor(color); gc.setAlpha(40)
        painter.setPen(QPen(gc, 3.0))
        painter.drawPolyline(points)
        
        painter.setPen(QPen(QColor(color), 1.5))
        painter.drawPolyline(points)
