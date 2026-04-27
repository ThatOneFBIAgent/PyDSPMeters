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
        self._waveform_l = np.zeros(4096, dtype=np.float32)
        self._waveform_r = np.zeros(4096, dtype=np.float32)
        self._display_samples = 1024
        self._channel = "L+R"
        super().__init__(audio_engine, title="Oscilloscope", parent=parent)
        self.canvas.set_render_func(self._render)

    def setup_settings(self):
        c = self.settings.add_combo("Channel", ["L+R", "Left", "Right", "Mid", "Side"], 0)
        c.currentTextChanged.connect(lambda t: setattr(self, "_channel", t))
        s = self.settings.add_slider("Zoom", 256, 4096, 1024)
        s.valueChanged.connect(lambda v: setattr(self, "_display_samples", v))

    def on_audio_data(self, data: np.ndarray):
        n = len(data)
        self._waveform_l = np.roll(self._waveform_l, -n)
        self._waveform_l[-n:] = data[:, 0]
        r = data[:, 1] if data.shape[1] > 1 else data[:, 0]
        self._waveform_r = np.roll(self._waveform_r, -n)
        self._waveform_r[-n:] = r

    def _find_trigger(self, data):
        for i in range(1, len(data) - self._display_samples):
            if data[i - 1] <= 0 < data[i]:
                return i
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
            path = QPainterPath()
            for i, s in enumerate(seg):
                x = i / len(seg) * w
                y = mid_y - s * h * 0.4
                if i == 0: path.moveTo(x, y)
                else: path.lineTo(x, y)
            # Glow
            gc = QColor(colors[idx % 2]); gc.setAlpha(40)
            painter.setPen(QPen(gc, 3.0))
            painter.drawPath(path)
            # Line
            painter.setPen(QPen(QColor(colors[idx % 2]), 1.5))
            painter.drawPath(path)
