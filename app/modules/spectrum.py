"""
Spectrum Analyzer Module: FFT-based frequency display with accumulation buffer.
"""

import numpy as np
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath
from PySide6.QtCore import Qt, QRectF

from app.base_module import BaseModule
from app.modules import register_module
from app.theme import Colors, Fonts
from app.dsp.fft import (
    compute_fft, fft_frequencies, map_frequencies_to_pixels,
    detect_peak_frequency, hz_to_note_name,
)


@register_module("spectrum", "Spectrum Analyzer")
class SpectrumModule(BaseModule):

    def __init__(self, audio_engine, parent=None):
        self._fft_size = 4096
        self._scale = "logarithmic"
        self._mode = "FFT"
        self._channel = "Left"
        self._smoothing = 0.85
        self._show_note = False
        # Accumulation buffer — always holds enough samples for the largest FFT
        self._acc_buf = np.zeros(16384, dtype=np.float32)
        self._smoothed = np.full(8193, -120.0, dtype=np.float64)
        self._peak_freq = 0.0
        self._peak_db = -120.0
        super().__init__(audio_engine, title="Spectrum", parent=parent)
        self.canvas.set_render_func(self._render)

    def setup_settings(self):
        c = self.settings.add_combo("Mode", ["FFT", "Color Bars", "Both"], 0)
        c.currentTextChanged.connect(lambda t: setattr(self, "_mode", t))
        c = self.settings.add_combo("FFT Size", ["1024","2048","4096","8192","16384"], 2)
        c.currentTextChanged.connect(lambda t: self._set_fft_size(int(t)))
        c = self.settings.add_combo("Scale", ["Mel","Logarithmic","Linear"], 1)
        c.currentTextChanged.connect(lambda t: setattr(self, "_scale", t.lower()))
        c = self.settings.add_combo("Channel", ["Left","Right","Mid","Side"], 0)
        c.currentTextChanged.connect(lambda t: setattr(self, "_channel", t))
        s = self.settings.add_slider("Smoothing", 0, 98, 85)
        s.valueChanged.connect(lambda v: setattr(self, "_smoothing", v / 100.0))
        self.settings.add_checkbox("dB/Hz/Note", False).toggled.connect(
            lambda v: setattr(self, "_show_note", v))

    def _set_fft_size(self, size):
        self._fft_size = size
        n = size // 2 + 1
        self._smoothed = np.full(n, -120.0, dtype=np.float64)

    def on_audio_data(self, data: np.ndarray):
        l = data[:, 0]
        r = data[:, 1] if data.shape[1] > 1 else l
        sig = {"Left": l, "Right": r, "Mid": (l+r)*0.5, "Side": (l-r)*0.5
               }.get(self._channel, l)

        # Roll accumulation buffer and append new data
        n = len(sig)
        self._acc_buf = np.roll(self._acc_buf, -n)
        self._acc_buf[-n:] = sig

        # FFT on the last fft_size samples from the accumulation buffer
        segment = self._acc_buf[-self._fft_size:]
        mag = compute_fft(segment, self._fft_size)

        nb = min(len(mag), len(self._smoothed))
        a = 1.0 - self._smoothing
        self._smoothed[:nb] = self._smoothed[:nb] * self._smoothing + mag[:nb] * a

        freqs = fft_frequencies(self._fft_size, self.audio_engine.sample_rate)
        self._peak_freq, self._peak_db = detect_peak_frequency(
            self._smoothed[:len(freqs)], freqs)

    def _render(self, painter, w, h):
        db_min, db_max = -90.0, 0.0
        mb = 16
        dh = h - mb
        freqs = fft_frequencies(self._fft_size, self.audio_engine.sample_rate)
        # Grid
        painter.setFont(Fonts.small())
        for gf in [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]:
            px = map_frequencies_to_pixels(np.array([gf]), w, self._scale)[0]
            if 0 < px < w:
                painter.setPen(QPen(QColor(Colors.GRID), 1, Qt.DotLine))
                painter.drawLine(int(px), 0, int(px), int(dh))
                painter.setPen(QColor(Colors.TEXT_DIM))
                lb = f"{gf}" if gf < 1000 else f"{gf//1000}k"
                painter.drawText(QRectF(px - 12, dh + 1, 24, 14), Qt.AlignCenter, lb)
        for db in range(-80, 1, 10):
            y = dh * (1.0 - (db - db_min) / (db_max - db_min))
            if 0 < y < dh:
                painter.setPen(QPen(QColor(Colors.GRID), 1, Qt.DotLine))
                painter.drawLine(0, int(y), w, int(y))

        mag = self._smoothed
        nb = min(len(mag), len(freqs))
        if nb < 2:
            return
        px_x = map_frequencies_to_pixels(freqs[:nb], w, self._scale)

        if self._mode in ("Color Bars", "Both"):
            n_bars = 64
            bw = max(2, w / n_bars - 1)
            for b in range(n_bars):
                xs, xe = b / n_bars * w, (b + 1) / n_bars * w
                mask = (px_x >= xs) & (px_x < xe)
                if not np.any(mask): continue
                avg = np.mean(mag[:nb][mask])
                ff = max(0, min(1, (avg - db_min) / (db_max - db_min)))
                bh = ff * dh
                hf = b / n_bars
                col = QColor(Colors.BAND_LOW if hf < 0.33 else
                             Colors.BAND_MID if hf < 0.66 else Colors.BAND_HIGH)
                col.setAlpha(180)
                painter.fillRect(QRectF(xs + 1, dh - bh, bw, bh), QBrush(col))

        if self._mode in ("FFT", "Both"):
            path = QPainterPath()
            for i in range(nb):
                frac = max(0, min(1, (mag[i] - db_min) / (db_max - db_min)))
                y = dh * (1.0 - frac)
                if i == 0: path.moveTo(px_x[i], y)
                else: path.lineTo(px_x[i], y)
            gc = QColor(Colors.ACCENT); gc.setAlpha(30)
            painter.setPen(QPen(gc, 3.0)); painter.drawPath(path)
            painter.setPen(QPen(QColor(Colors.ACCENT), 1.2)); painter.drawPath(path)
            fp = QPainterPath(path)
            fp.lineTo(px_x[-1], dh); fp.lineTo(px_x[0], dh); fp.closeSubpath()
            fc = QColor(Colors.ACCENT); fc.setAlpha(15)
            painter.fillPath(fp, QBrush(fc))

        if self._show_note and self._peak_db > -80:
            note = hz_to_note_name(self._peak_freq)
            txt = f"{note}  {self._peak_freq:.0f}Hz  {self._peak_db:.1f}dB"
            painter.setFont(Fonts.value())
            tw = painter.fontMetrics().horizontalAdvance(txt) + 16
            bx = QRectF(w - tw - 8, 6, tw, 22)
            bg = QColor(Colors.BG_DARKEST); bg.setAlpha(200)
            painter.fillRect(bx, QBrush(bg))
            painter.setPen(QColor(Colors.ACCENT))
            painter.drawText(bx, Qt.AlignCenter, txt)
