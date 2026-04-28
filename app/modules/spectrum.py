"""
Spectrum Analyzer Module: FFT-based frequency display with accumulation buffer.
"""

import numpy as np
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath
from PySide6.QtCore import Qt, QRectF, QPointF

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

    def build_context_menu(self, menu):
        from PySide6.QtGui import QActionGroup
        
        mm = menu.addMenu("Mode")
        mg = QActionGroup(self)
        for m in ["FFT", "Color Bars", "Both"]:
            a = mm.addAction(m)
            a.setCheckable(True)
            a.setChecked(m == self._mode)
            a.triggered.connect(lambda checked, t=m: setattr(self, "_mode", t))
            mg.addAction(a)
            
        fm = menu.addMenu("FFT Size")
        fg = QActionGroup(self)
        for f in [1024, 2048, 4096, 8192, 16384]:
            a = fm.addAction(str(f))
            a.setCheckable(True)
            a.setChecked(f == self._fft_size)
            a.triggered.connect(lambda checked, t=f: self._set_fft_size(int(t)))
            fg.addAction(a)
            
        scm = menu.addMenu("Scale")
        scg = QActionGroup(self)
        for s in ["Mel", "Logarithmic", "Linear"]:
            a = scm.addAction(s)
            a.setCheckable(True)
            a.setChecked(s.lower() == self._scale)
            a.triggered.connect(lambda checked, t=s: setattr(self, "_scale", t.lower()))
            scg.addAction(a)
            
        cm = menu.addMenu("Channel")
        cg = QActionGroup(self)
        for c in ["Left", "Right", "Mid", "Side"]:
            a = cm.addAction(c)
            a.setCheckable(True)
            a.setChecked(c == self._channel)
            a.triggered.connect(lambda checked, t=c: setattr(self, "_channel", t))
            cg.addAction(a)

        sm = menu.addMenu("Smoothing")
        sg = QActionGroup(self)
        for sm_val in [0, 50, 75, 85, 95]:
            a = sm.addAction(f"{sm_val}%")
            a.setCheckable(True)
            a.setChecked(abs(sm_val/100.0 - self._smoothing) < 0.01)
            a.triggered.connect(lambda checked, v=sm_val: setattr(self, "_smoothing", v / 100.0))
            sg.addAction(a)

        a = menu.addAction("dB/Hz/Note Info")
        a.setCheckable(True)
        a.setChecked(self._show_note)
        a.triggered.connect(lambda checked: setattr(self, "_show_note", checked))

    def _set_fft_size(self, size):
        self._fft_size = size
        n = size // 2 + 1
        self._smoothed = np.full(n, -120.0, dtype=np.float64)

    def on_audio_data(self, data: np.ndarray):
        l = data[:, 0]
        r = data[:, 1] if data.shape[1] > 1 else l
        sig = {"Left": l, "Right": r, "Mid": (l+r)*0.5, "Side": (l-r)*0.5
               }.get(self._channel, l)

        # Update accumulation buffer
        n = len(sig)
        buf_len = len(self._acc_buf)
        if n >= buf_len:
            self._acc_buf[:] = sig[-buf_len:]
        else:
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
                lb = f"{gf}" if gf < 1000 else f"{gf//1000}k"
                from PySide6.QtGui import QFontMetrics
                fm = QFontMetrics(Fonts.small())
                tw = fm.horizontalAdvance(lb) + 12
                # Draw labels in the margin area underneath the grid
                self.draw_text_badge(painter, QRectF(px - tw/2, dh + 2, tw, 14), Qt.AlignCenter, lb, QColor(Colors.TEXT_DIM))
        for db in range(-80, 1, 10):
            y = dh * (1.0 - (db - db_min) / (db_max - db_min))
            if 0 < y < dh:
                painter.setPen(QPen(QColor(Colors.GRID), 1, Qt.DotLine))
                painter.drawLine(0, int(y), w, int(y))

        mag = self._smoothed
        # Spatial smoothing across frequency bins to reduce jaggedness/spikiness
        mag = np.convolve(mag, np.ones(5)/5.0, mode='same')
        
        nb = min(len(mag), len(freqs))
        if nb < 2:
            return
        px_x = map_frequencies_to_pixels(freqs[:nb], w, self._scale)

        if self._mode in ("Color Bars", "Both"):
            n_bars = 64
            bw = max(2, w / n_bars - 1)
            # Pre-calculate bar values with interpolation for low-end gaps
            bar_vals = np.zeros(n_bars)
            for b in range(n_bars):
                xs, xe = b / n_bars * w, (b + 1) / n_bars * w
                mask = (px_x >= xs) & (px_x < xe)
                if np.any(mask):
                    bar_vals[b] = np.mean(mag[:nb][mask])
                else:
                    # Interpolate from nearest bin if no bin falls exactly in this bar
                    idx = np.searchsorted(px_x, xs)
                    if idx > 0 and idx < nb:
                        # Linear interpolation between nearest bins
                        x0, x1 = px_x[idx-1], px_x[idx]
                        v0, v1 = mag[idx-1], mag[idx]
                        t = (xs - x0) / (x1 - x0) if x1 > x0 else 0
                        bar_vals[b] = v0 + t * (v1 - v0)
                    elif idx == 0:
                        bar_vals[b] = mag[0]
                    else:
                        bar_vals[b] = mag[nb-1]

            for b in range(n_bars):
                xs = b / n_bars * w
                ff = max(0, min(1, (bar_vals[b] - db_min) / (db_max - db_min)))
                bh = ff * dh
                hf = b / n_bars
                col = QColor(Colors.BAND_LOW if hf < 0.33 else
                             Colors.BAND_MID if hf < 0.66 else Colors.BAND_HIGH)
                col.setAlpha(180)
                painter.fillRect(QRectF(xs + 1, dh - bh, bw, bh), QBrush(col))

        if self._mode in ("FFT", "Both"):
            # Optimization: Downsample points to window width for smoother/faster rendering
            step = max(1, nb // (int(w) * 2))
            points = []
            for i in range(0, nb, step):
                frac = max(0, min(1, (mag[i] - db_min) / (db_max - db_min)))
                points.append(QPointF(px_x[i], dh * (1.0 - frac)))
            
            if points:
                path = QPainterPath()
                path.moveTo(points[0])
                for p in points[1:]:
                    path.lineTo(p)
                
                gc = QColor(Colors.ACCENT); gc.setAlpha(30)
                painter.setPen(QPen(gc, 3.0)); painter.drawPath(path)
                painter.setPen(QPen(QColor(Colors.ACCENT), 1.2)); painter.drawPath(path)
                
                fp = QPainterPath(path)
                fp.lineTo(points[-1].x(), dh); fp.lineTo(points[0].x(), dh); fp.closeSubpath()
                fc = QColor(Colors.ACCENT); fc.setAlpha(15)
                painter.fillPath(fp, QBrush(fc))

        if self._show_note and self._peak_db > -80:
            note = hz_to_note_name(self._peak_freq)
            txt = f"{note}  {self._peak_freq:.0f}Hz  {self._peak_db:.1f}dB"
            painter.setFont(Fonts.value())
            self.draw_text_badge(painter, QRectF(w - 200, 10, 180, 22), Qt.AlignRight, txt, QColor(Colors.ACCENT))
