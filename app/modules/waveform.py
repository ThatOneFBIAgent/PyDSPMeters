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
from app.dsp import accel as dsp_accel


@register_module("waveform", "Waveform")
class WaveformModule(BaseModule):

    def __init__(self, audio_engine, parent=None):
        self._channel = "All" if audio_engine.channels > 2 else "L+R"
        self._speed = 2.0
        self._buf_len = 2048  # Pixels of history
        self._max_buf = np.zeros((self._buf_len, audio_engine.channels), dtype=np.float32)
        self._min_buf = np.zeros((self._buf_len, audio_engine.channels), dtype=np.float32)
        self._rms_buf = np.zeros((self._buf_len, audio_engine.channels), dtype=np.float32)
        self._write_pos = 0
        self._display_mode = "Split" if audio_engine.channels >= 2 else "Overlay"
        self.module_key = "waveform"
        super().__init__(audio_engine, title="Waveform", parent=parent)
        self.canvas.set_render_func(self._render)

    def get_settings(self):
        return {
            "channel": self._channel,
            "speed": self._speed,
            "display_mode": self._display_mode
        }

    def apply_settings(self, settings):
        self._channel = settings.get("channel", self._channel)
        self._speed = float(settings.get("speed", self._speed))
        self._display_mode = settings.get("display_mode", self._display_mode)

    def build_context_menu(self, menu):
        from PySide6.QtGui import QActionGroup
        cm = menu.addMenu("Channel")
        cg = QActionGroup(self)
        channels = ["All"] if self.audio_engine.channels > 2 else ["L+R"]
        channels += [f"Ch {i+1}" for i in range(self.audio_engine.channels)]
        if self.audio_engine.channels == 2:
            channels = ["L+R", "Left", "Right", "Mid", "Side"]
            
        for c in channels:
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
            
        dm = menu.addMenu("Display Mode")
        dg = QActionGroup(self)
        for d in ["Overlay", "Split"]:
            a = dm.addAction(d)
            a.setCheckable(True)
            a.setChecked(self._display_mode == d)
            a.triggered.connect(lambda checked, v=d: setattr(self, "_display_mode", v))
            dg.addAction(a)

    def on_audio_data(self, data: np.ndarray):
        # Consolidate samples into speed-dependent pixel chunks
        n = len(data)
        chunk_size = max(1, int(1024 / self._speed))
        
        # Ensure buffers match engine channel count (in case it changed)
        ch_count = data.shape[1]
        if ch_count != self._max_buf.shape[1]:
            self._max_buf = np.zeros((self._buf_len, ch_count), dtype=np.float32)
            self._min_buf = np.zeros((self._buf_len, ch_count), dtype=np.float32)
            self._rms_buf = np.zeros((self._buf_len, ch_count), dtype=np.float32)
            self._write_pos = 0

        # Use accelerated chunk reduction
        max_chunks, min_chunks, rms_chunks = dsp_accel.waveform_reduce(data, chunk_size)
        n_chunks = len(max_chunks)
        
        for i in range(n_chunks):
            self._max_buf[self._write_pos] = max_chunks[i]
            self._min_buf[self._write_pos] = min_chunks[i]
            self._rms_buf[self._write_pos] = rms_chunks[i]
            self._write_pos = (self._write_pos + 1) % self._buf_len

    def _render(self, painter, w, h):
        n_disp = int(w)
        if n_disp > self._buf_len: n_disp = self._buf_len
        
        start = (self._write_pos - n_disp) % self._buf_len
        
        def get_seg(buf):
            if start + n_disp <= self._buf_len:
                return buf[start:start + n_disp]
            else:
                return np.concatenate([buf[start:], buf[:(start + n_disp) % self._buf_len]])

        max_all = get_seg(self._max_buf)
        min_all = get_seg(self._min_buf)
        rms_all = get_seg(self._rms_buf)

        # Map channel selection to indices
        if self._channel == "Left" or self._channel == "Ch 1": channels = [0]
        elif self._channel == "Right" or self._channel == "Ch 2": channels = [1]
        elif self._channel.startswith("Ch "):
            try: channels = [int(self._channel.split()[1]) - 1]
            except: channels = [0]
        elif self._channel == "Mid": 
            # Recalculate mid for display from stored L/R
            maxs = (max_all[:, 0] + max_all[:, 1]) * 0.5
            mins = (min_all[:, 0] + min_all[:, 1]) * 0.5
            rmss = (rms_all[:, 0] + rms_all[:, 1]) * 0.5
            self._draw_wave(painter, maxs, mins, rmss, Colors.ACCENT, h / 2, h)
            return
        elif self._channel == "Side":
            maxs = (max_all[:, 0] - max_all[:, 1]) * 0.5
            mins = (min_all[:, 0] - min_all[:, 1]) * 0.5
            rmss = np.abs(rms_all[:, 0] - rms_all[:, 1]) * 0.5
            self._draw_wave(painter, maxs, mins, rmss, Colors.ACCENT_PURPLE, h / 2, h)
            return
        else: # L+R or All
            channels = list(range(self.audio_engine.channels))

        colors = [Colors.ACCENT, Colors.ACCENT_PINK, Colors.ACCENT_PURPLE, Colors.BAND_LOW, Colors.BAND_MID, Colors.BAND_HIGH, Colors.METER_MID, Colors.METER_HIGH]
        
        if self._display_mode == "Split" and len(channels) > 1:
            n_ch = len(channels)
            strip_h = h / n_ch
            for i, idx in enumerate(channels):
                cy = (i + 0.5) * strip_h
                # Draw divider
                if i > 0:
                    painter.setPen(QPen(QColor(Colors.GRID), 1))
                    painter.drawLine(0, int(i * strip_h), w, int(i * strip_h))
                
                if idx < len(max_all[0]):
                    self._draw_wave(painter, max_all[:, idx], min_all[:, idx], rms_all[:, idx], colors[idx % len(colors)], cy, strip_h)
        else:
            mid_y = h / 2
            painter.setPen(QPen(QColor(Colors.GRID), 1))
            painter.drawLine(0, int(mid_y), w, int(mid_y))
            for idx in channels:
                if idx < len(max_all[0]):
                    self._draw_wave(painter, max_all[:, idx], min_all[:, idx], rms_all[:, idx], colors[idx % len(colors)], mid_y, h)

    def _draw_wave(self, painter, maxs, mins, rmss, base_color, mid_y, h):
        from PySide6.QtCore import QLineF
        h_factor = h * 0.45
        
        # Optimized drawing: Group lines by color to minimize pen changes
        base_lines = []
        yellow_lines = []
        red_lines = []
        peak_lines = []
        
        for x in range(len(maxs)):
            # RMS Core coloring based on amplitude
            rms_val = rmss[x] * 2.0 # Standardized scale
            h_rms = rmss[x] * h_factor
            
            line = QLineF(x, mid_y - h_rms, x, mid_y + h_rms)
            if rms_val > 0.7: 
                red_lines.append(line)
            elif rms_val > 0.3: 
                yellow_lines.append(line)
            else: 
                base_lines.append(line)
            
            # Peak outline (using base_color)
            peak_lines.append(QLineF(x, mid_y - maxs[x] * h_factor, x, mid_y - mins[x] * h_factor))

        # 1. Draw Peaks (translucent background)
        pc = QColor(base_color)
        pc.setAlpha(35)
        painter.setPen(QPen(pc, 1))
        painter.drawLines(peak_lines)
        
        # 2. Draw RMS Cores with theme-aware meter colors
        if base_lines:
            painter.setPen(QPen(QColor(Colors.METER_LOW), 1))
            painter.drawLines(base_lines)
        if yellow_lines:
            painter.setPen(QPen(QColor(Colors.METER_MID), 1))
            painter.drawLines(yellow_lines)
        if red_lines:
            painter.setPen(QPen(QColor(Colors.METER_HIGH), 1))
            painter.drawLines(red_lines)
