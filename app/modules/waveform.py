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
        self._channel = "Left"
        self._speed = 2.0
        self._buf_len = 2048  # Pixels of history
        self._max_buf = np.zeros(self._buf_len, dtype=np.float32)
        self._min_buf = np.zeros(self._buf_len, dtype=np.float32)
        self._rms_buf = np.zeros(self._buf_len, dtype=np.float32)
        self._write_pos = 0
        super().__init__(audio_engine, title="Waveform", parent=parent)
        self.canvas.set_render_func(self._render)

    def build_context_menu(self, menu):
        from PySide6.QtGui import QActionGroup
        cm = menu.addMenu("Channel")
        cg = QActionGroup(self)
        for c in ["Left", "Right", "Mid", "Side"]:
            a = cm.addAction(c)
            a.setCheckable(True)
            a.setChecked(c == self._channel)
            a.triggered.connect(lambda checked, ch=c: setattr(self, "_channel", ch))
            cg.addAction(a)
            
        sm = menu.addMenu("Speed")
        sg = QActionGroup(self)
        for s in [1, 2, 4, 8]:
            a = sm.addAction(f"{s}x")
            a.setCheckable(True)
            a.setChecked(int(self._speed) == s)
            a.triggered.connect(lambda checked, v=s: setattr(self, "_speed", float(v)))
            sg.addAction(a)

    def on_audio_data(self, data: np.ndarray):
        l, r = data[:, 0], data[:, 1] if data.shape[1] > 1 else data[:, 0]
        sig = {"Left": l, "Right": r, "Mid": (l+r)*0.5, "Side": (l-r)*0.5}.get(self._channel, l)
        
        # Consolidate samples into speed-dependent pixel chunks
        n = len(sig)
        chunk_size = max(1, int(1024 / self._speed))
        
        for i in range(0, n, chunk_size):
            chunk = sig[i:i + chunk_size]
            if len(chunk) == 0: continue
            
            mx = np.max(chunk)
            mn = np.min(chunk)
            rms = np.sqrt(np.mean(chunk**2))
            
            self._max_buf[self._write_pos] = mx
            self._min_buf[self._write_pos] = mn
            self._rms_buf[self._write_pos] = rms
            self._write_pos = (self._write_pos + 1) % self._buf_len

    def _render(self, painter, w, h):
        mid_y = h / 2
        painter.setPen(QPen(QColor(Colors.GRID), 1))
        painter.drawLine(0, int(mid_y), w, int(mid_y))

        n_disp = int(w)
        if n_disp > self._buf_len: n_disp = self._buf_len
        
        start = (self._write_pos - n_disp) % self._buf_len
        if start + n_disp <= self._buf_len:
            maxs = self._max_buf[start:start + n_disp]
            mins = self._min_buf[start:start + n_disp]
            rmss = self._rms_buf[start:start + n_disp]
        else:
            maxs = np.concatenate([self._max_buf[start:], self._max_buf[:(start + n_disp) % self._buf_len]])
            mins = np.concatenate([self._min_buf[start:], self._min_buf[:(start + n_disp) % self._buf_len]])
            rmss = np.concatenate([self._rms_buf[start:], self._rms_buf[:(start + n_disp) % self._buf_len]])

        # Optimized draw: use vertical lines for mirrored wave
        h_factor = h * 0.45
        for x in range(len(maxs)):
            amp = rmss[x] * 2.5
            col = QColor(Colors.ACCENT)
            if amp > 0.6: col = QColor(Colors.YELLOW)
            if amp > 0.9: col = QColor(Colors.RED)
            
            # Draw peak outline (dimmer)
            pc = QColor(col); pc.setAlpha(80)
            painter.setPen(QPen(pc, 1))
            painter.drawLine(x, int(mid_y - maxs[x] * h_factor), x, int(mid_y - mins[x] * h_factor))
            
            # Draw RMS core (solid)
            h_rms = rmss[x] * h_factor
            painter.setPen(QPen(col, 1))
            painter.drawLine(x, int(mid_y - h_rms), x, int(mid_y + h_rms))
