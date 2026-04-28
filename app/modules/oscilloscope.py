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
        self.module_key = "oscilloscope"
        super().__init__(audio_engine, title="Oscilloscope", parent=parent)
        self.canvas.set_render_func(self._render)

    def get_settings(self):
        return {
            "display_samples": self._display_samples,
            "channel": self._channel
        }

    def apply_settings(self, settings):
        self._display_samples = settings.get("display_samples", self._display_samples)
        self._channel = settings.get("channel", self._channel)

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

    def _render(self, painter, w, h):
        mid_y = h // 2
        # Grid
        painter.setPen(QPen(QColor(Colors.GRID), 1))
        painter.drawLine(0, mid_y, w, mid_y)
        for i in range(1, 4):
            y1 = int(mid_y - h * 0.4 * i / 4)
            y2 = int(mid_y + h * 0.4 * i / 4)
            painter.drawLine(0, y1, w, y1)
            painter.drawLine(0, y2, w, y2)
        for i in range(1, 8):
            painter.drawLine(int(w * i / 8), 0, int(w * i / 8), h)

        colors = [Colors.ACCENT, Colors.ACCENT_PINK]
        for idx, ch in enumerate(self._get_channels()):
            trig = self._find_trigger(ch)
            seg = ch[trig:trig + self._display_samples]
            if len(seg) < 2:
                continue
            
            # Ultra-Performance Optimization: 
            # Downsample exactly to pixel width using NumPy
            num_points = min(len(seg), int(w))
            if num_points < 2: continue
            
            indices = np.linspace(0, len(seg) - 1, num_points).astype(np.int32)
            downsampled = seg[indices]
            
            # Map to screen coordinates
            x_coords = np.linspace(0, w, num_points)
            y_coords = mid_y - downsampled * h * 0.4
            
            from PySide6.QtCore import QPointF
            points = [QPointF(x_coords[i], y_coords[i]) for i in range(num_points)]
            
            # Glow
            gc = QColor(colors[idx % 2]); gc.setAlpha(40)
            painter.setPen(QPen(gc, 3.0))
            painter.drawPolyline(points)
            
            # Main Line
            painter.setPen(QPen(QColor(colors[idx % 2]), 1.5))
            painter.drawPolyline(points)
