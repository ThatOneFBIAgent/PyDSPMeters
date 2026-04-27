"""
Waveform Module: Scrolling waveform display with multi-band coloring and peak history.
"""

import numpy as np
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath
from PySide6.QtCore import Qt, QRectF

from app.base_module import BaseModule
from app.modules import register_module
from app.theme import Colors, Fonts
from app.dsp.filters import MultiBandFilter


@register_module("waveform", "Waveform")
class WaveformModule(BaseModule):

    def __init__(self, audio_engine, parent=None):
        self._channel_l = "Left"
        self._channel_r = "Right"
        self._color_mode = "Static"
        self._show_peak_history = False
        self._speed = 1.0
        self._dual = True
        self._buf_len = 4096
        self._buffer_l = np.zeros(self._buf_len, dtype=np.float32)
        self._buffer_r = np.zeros(self._buf_len, dtype=np.float32)
        self._peak_history = np.zeros((self._buf_len, 3), dtype=np.float32)
        self._peak_idx = 0
        self._multiband = MultiBandFilter(sample_rate=audio_engine.sample_rate)
        super().__init__(audio_engine, title="Waveform", parent=parent)
        self.canvas.set_render_func(self._render)

    def setup_settings(self):
        c = self.settings.add_combo("Channel 1", ["Left","Right","Mid","Side"], 0)
        c.currentTextChanged.connect(lambda t: setattr(self, "_channel_l", t))
        c = self.settings.add_combo("Channel 2", ["Right","Left","Mid","Side","None"], 0)
        c.currentTextChanged.connect(self._set_ch2)
        c = self.settings.add_combo("Color", ["Static","Multi-Band","Color Map"], 0)
        c.currentTextChanged.connect(lambda t: setattr(self, "_color_mode", t))
        self.settings.add_checkbox("Peak History", False).toggled.connect(
            lambda v: setattr(self, "_show_peak_history", v))
        s = self.settings.add_slider("Speed", 1, 8, 1)
        s.valueChanged.connect(lambda v: setattr(self, "_speed", float(v)))

    def _set_ch2(self, t):
        self._channel_r = t
        self._dual = t != "None"

    def _get_sig(self, data, name):
        l, r = data[:, 0], data[:, 1] if data.shape[1] > 1 else data[:, 0]
        return {"Left": l, "Right": r, "Mid": (l+r)*0.5, "Side": (l-r)*0.5}.get(name, l)

    def on_audio_data(self, data: np.ndarray):
        sl = self._get_sig(data, self._channel_l)
        n = len(sl)
        step = max(1, int(self._speed))
        self._buffer_l = np.roll(self._buffer_l, -n * step)
        self._buffer_l[-n:] = sl
        if self._dual:
            sr = self._get_sig(data, self._channel_r)
            self._buffer_r = np.roll(self._buffer_r, -n * step)
            self._buffer_r[-n:] = sr
        if self._show_peak_history:
            low, mid, high = self._multiband.split(sl)
            idx = self._peak_idx % self._buf_len
            self._peak_history[idx] = [np.sqrt(np.mean(low**2)),
                                       np.sqrt(np.mean(mid**2)),
                                       np.sqrt(np.mean(high**2))]
            self._peak_idx += 1

    def _render(self, painter, w, h):
        n_ch = 2 if self._dual else 1
        ch_h = h // n_ch

        bufs = [(self._buffer_l, self._channel_l)]
        if self._dual:
            bufs.append((self._buffer_r, self._channel_r))

        for ci, (buf, _) in enumerate(bufs):
            y_off = ci * ch_h
            mid_y = y_off + ch_h // 2
            painter.setPen(QPen(QColor(Colors.GRID_BRIGHT), 1))
            painter.drawLine(0, mid_y, w, mid_y)
            if ci > 0:
                painter.setPen(QPen(QColor(Colors.BORDER), 1))
                painter.drawLine(0, y_off, w, y_off)

            step = max(1, len(buf) // w)
            if self._color_mode == "Multi-Band":
                low, mid_b, high = self._multiband.split(buf)
                for bd, col in [(low, Colors.BAND_LOW), (mid_b, Colors.BAND_MID),
                                (high, Colors.BAND_HIGH)]:
                    path = QPainterPath()
                    for i in range(min(len(bd) // step, w)):
                        s = bd[i * step] if i * step < len(bd) else 0
                        y = mid_y - s * ch_h * 0.45
                        if i == 0: path.moveTo(i, y)
                        else: path.lineTo(i, y)
                    c = QColor(col); c.setAlpha(150)
                    painter.setPen(QPen(c, 1)); painter.drawPath(path)
            else:
                path = QPainterPath()
                for i in range(min(len(buf) // step, w)):
                    s = buf[i * step] if i * step < len(buf) else 0
                    y = mid_y - s * ch_h * 0.45
                    if i == 0: path.moveTo(i, y)
                    else: path.lineTo(i, y)
                painter.setPen(QPen(QColor(Colors.ACCENT), 1.2))
                painter.drawPath(path)
                if self._color_mode == "Color Map":
                    fp = QPainterPath(path)
                    fp.lineTo(w, mid_y); fp.lineTo(0, mid_y); fp.closeSubpath()
                    fc = QColor(Colors.ACCENT); fc.setAlpha(20)
                    painter.fillPath(fp, QBrush(fc))

        if self._show_peak_history and self._peak_idx > 0:
            pi = self._peak_idx
            n = min(pi, self._buf_len)
            cols = [Colors.BAND_LOW, Colors.BAND_MID, Colors.BAND_HIGH]
            for band in range(3):
                path = QPainterPath()
                for i in range(n):
                    idx = (pi - n + i) % self._buf_len
                    x = i / n * w
                    y = h - self._peak_history[idx, band] * h * 4
                    if i == 0: path.moveTo(x, y)
                    else: path.lineTo(x, y)
                c = QColor(cols[band]); c.setAlpha(80)
                painter.setPen(QPen(c, 1.5)); painter.drawPath(path)
