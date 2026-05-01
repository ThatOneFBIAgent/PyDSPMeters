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
        self._show_note = True
        self._show_floating_note = False
        # Accumulation buffer — always holds enough samples for the largest FFT
        self._acc_buf = np.zeros(max(16384, self._fft_size * 2), dtype=np.float32)
        self._smoothed = np.full(self._fft_size // 2 + 1, -120.0, dtype=np.float64)
        self._peak_freq = 0.0
        self._peak_db = -120.0
        self._smooth_peak_freq = 0.0
        self._smooth_peak_db = -120.0
        self._peak_history = []
        self._speed = 1.0
        self.module_key = "spectrum"
        super().__init__(audio_engine, title="Spectrum", parent=parent)
        self.canvas.set_render_func(self._render)

    def get_settings(self):
        return {
            "fft_size": self._fft_size,
            "scale": self._scale,
            "mode": self._mode,
            "channel": self._channel,
            "smoothing": self._smoothing,
            "show_note": self._show_note,
            "show_floating_note": self._show_floating_note,
            "speed": self._speed
        }

    def apply_settings(self, settings):
        self._set_fft_size(settings.get("fft_size", self._fft_size))
        self._scale = settings.get("scale", self._scale)
        self._mode = settings.get("mode", self._mode)
        self._channel = settings.get("channel", self._channel)
        self._smoothing = float(settings.get("smoothing", self._smoothing))
        self._show_note = settings.get("show_note", self._show_note)
        self._show_floating_note = settings.get("show_floating_note", self._show_floating_note)
        self._speed = float(settings.get("speed", self._speed))

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
        for f in [1024, 2048, 4096, 8192, 16384, 32768]:
            a = fm.addAction(str(f))
            a.setCheckable(True)
            a.setChecked(f == self._fft_size)
            a.triggered.connect(lambda checked, t=f: self._set_fft_size(int(t)))
            fg.addAction(a)
            
        sm_speed = menu.addMenu("Speed")
        sg_speed = QActionGroup(self)
        for s in [1, 2, 4]:
            a = sm_speed.addAction(f"{s}x")
            a.setCheckable(True)
            a.setChecked(int(self._speed) == s)
            a.triggered.connect(lambda checked, v=s: setattr(self, "_speed", float(v)))
            sg_speed.addAction(a)
            
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
        for sm_val in [0, 50, 75, 85, 95, 98, 99]:
            a = sm.addAction(f"{sm_val}%")
            a.setCheckable(True)
            a.setChecked(abs(sm_val/100.0 - self._smoothing) < 0.01)
            a.triggered.connect(lambda checked, v=sm_val: setattr(self, "_smoothing", v / 100.0))
            sg.addAction(a)

        a = menu.addAction("dB/Hz/Note Info")
        a.setCheckable(True)
        a.setChecked(self._show_note)
        a.triggered.connect(lambda checked: setattr(self, "_show_note", checked))

        a = menu.addAction("Floating Note Peak")
        a.setCheckable(True)
        a.setChecked(self._show_floating_note)
        a.setEnabled(self._show_note)
        a.triggered.connect(lambda checked: setattr(self, "_show_floating_note", checked))

    def _set_fft_size(self, size):
        self._fft_size = size
        n = size // 2 + 1
        self._smoothed = np.full(n, -120.0, dtype=np.float64)
        # Ensure accumulation buffer is always large enough for the FFT
        min_buf = max(16384, size * 2)
        if len(self._acc_buf) < min_buf:
            old = self._acc_buf
            self._acc_buf = np.zeros(min_buf, dtype=np.float32)
            # Preserve existing data
            copy_n = min(len(old), min_buf)
            self._acc_buf[-copy_n:] = old[-copy_n:]

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

        # Process multiple sub-steps for speed
        n_steps = int(self._speed)
        step_size = n // n_steps if n_steps > 1 else n
        
        for s in range(n_steps):
            # FFT on the last fft_size samples from the accumulation buffer, 
            # sliding backwards for sub-steps
            offset = (n_steps - 1 - s) * step_size
            start_idx = len(self._acc_buf) - self._fft_size - offset
            end_idx = len(self._acc_buf) - offset
            
            # Guard against negative indices
            if start_idx < 0:
                start_idx = 0
            if end_idx <= start_idx:
                continue
                
            segment = self._acc_buf[start_idx:end_idx]
            if len(segment) < self._fft_size:
                # Pad with zeros if not enough data yet (startup)
                padded = np.zeros(self._fft_size, dtype=np.float32)
                padded[-len(segment):] = segment
                segment = padded
            
            mag = compute_fft(segment, self._fft_size)

            nb = min(len(mag), len(self._smoothed))
            a = 1.0 - self._smoothing
            self._smoothed[:nb] = self._smoothed[:nb] * self._smoothing + mag[:nb] * a

        freqs = fft_frequencies(self._fft_size, self.audio_engine.sample_rate)
        self._peak_freq, self._peak_db = detect_peak_frequency(
            self._smoothed[:len(freqs)], freqs)
            
        # Smoothing for peak detection
        if self._peak_db > -90:
            self._peak_history.append(self._peak_freq)
            if len(self._peak_history) > 30:
                self._peak_history.pop(0)
                
            target_freq = float(np.median(self._peak_history))
            alpha = 0.05
            self._smooth_peak_freq += (target_freq - self._smooth_peak_freq) * alpha
            self._smooth_peak_db += (self._peak_db - self._smooth_peak_db) * 0.15
        else:
            self._peak_history.clear()
            self._smooth_peak_db = -120.0

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
                if w > 100:
                    lb = f"{gf}" if gf < 1000 else f"{gf//1000}k"
                    from PySide6.QtGui import QFontMetrics
                    fm = QFontMetrics(Fonts.small())
                    tw = fm.horizontalAdvance(lb) + 12
                    
                    # Draw labels in the margin area underneath the grid
                    painter.setFont(self.get_responsive_font(Fonts.small, tw, 14, lb))
                    self.draw_text_badge(painter, QRectF(px - tw/2, dh + 2, tw, 14), Qt.AlignCenter, lb, QColor(Colors.TEXT_DIM))
        for db in range(-80, 1, 10):
            y = dh * (1.0 - (db - db_min) / (db_max - db_min))
            if 0 < y < dh:
                painter.setPen(QPen(QColor(Colors.GRID), 1, Qt.DotLine))
                painter.drawLine(0, int(y), w, int(y))

        mag = self._smoothed
        # Spatial smoothing across frequency bins to reduce jaggedness/spikiness
        mag = np.convolve(mag, np.ones(5)/5.0, mode='same')
        
        # Ignore the DC bin (0 Hz) and bins above Nyquist to fix edge artifacts
        mask = (freqs >= 20.0) & (freqs <= 20000.0)
        px_x = map_frequencies_to_pixels(freqs[mask], w, self._scale)
        mag_filtered = mag[mask]
        nb = len(px_x)

        if nb < 2:
            return

        if self._mode in ("Color Bars", "Both"):
            n_bars = 64
            bw = max(2, w / n_bars - 1)
            # Pre-calculate bar values with interpolation for low-end gaps
            bar_vals = np.zeros(n_bars)
            for b in range(n_bars):
                xs, xe = b / n_bars * w, (b + 1) / n_bars * w
                bar_mask = (px_x >= xs) & (px_x < xe)
                if np.any(bar_mask):
                    bar_vals[b] = np.mean(mag_filtered[bar_mask])
                else:
                    # Interpolate from nearest bin if no bin falls exactly in this bar
                    idx = np.searchsorted(px_x, xs)
                    if idx > 0 and idx < nb:
                        # Linear interpolation between nearest bins
                        x0, x1 = px_x[idx-1], px_x[idx]
                        v0, v1 = mag_filtered[idx-1], mag_filtered[idx]
                        t = (xs - x0) / (x1 - x0) if x1 > x0 else 0
                        bar_vals[b] = v0 + t * (v1 - v0)
                    elif idx == 0:
                        bar_vals[b] = mag_filtered[0]
                    else:
                        bar_vals[b] = mag_filtered[nb-1]

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
                frac = max(0, min(1, (mag_filtered[i] - db_min) / (db_max - db_min)))
                points.append(QPointF(px_x[i], dh * (1.0 - frac)))
            
            if len(points) >= 2:
                path = QPainterPath()
                path.moveTo(points[0])
                
                # Catmull-Rom spline for smooth curves between points
                if len(points) >= 4:
                    # First segment: straight
                    path.lineTo(points[1])
                    
                    for i in range(1, len(points) - 2):
                        p0 = points[i - 1]
                        p1 = points[i]
                        p2 = points[i + 1]
                        p3 = points[i + 2]
                        
                        # Catmull-Rom to cubic Bezier control points
                        cp1x = p1.x() + (p2.x() - p0.x()) / 6.0
                        cp1y = p1.y() + (p2.y() - p0.y()) / 6.0
                        cp2x = p2.x() - (p3.x() - p1.x()) / 6.0
                        cp2y = p2.y() - (p3.y() - p1.y()) / 6.0
                        
                        path.cubicTo(cp1x, cp1y, cp2x, cp2y, p2.x(), p2.y())
                    
                    # Last segment: straight to final point
                    path.lineTo(points[-1])
                else:
                    # Too few points for spline, use lines
                    for p in points[1:]:
                        path.lineTo(p)
                
                gc = QColor(Colors.ACCENT); gc.setAlpha(30)
                painter.setPen(QPen(gc, 3.0)); painter.drawPath(path)
                painter.setPen(QPen(QColor(Colors.ACCENT), 1.2)); painter.drawPath(path)
                
                fp = QPainterPath(path)
                fp.lineTo(points[-1].x(), dh); fp.lineTo(points[0].x(), dh); fp.closeSubpath()
                fc = QColor(Colors.ACCENT); fc.setAlpha(15)
                painter.fillPath(fp, QBrush(fc))

        if self._show_note and self._smooth_peak_db > -80:
            note = hz_to_note_name(self._smooth_peak_freq)
            txt = f"{note}  {self._smooth_peak_freq:.0f}Hz  {self._smooth_peak_db:.1f}dB"
            painter.setFont(Fonts.value())
            from PySide6.QtGui import QFontMetrics
            fm = QFontMetrics(painter.font())
            tw = fm.horizontalAdvance(txt) + 20
            
            if w > 80:
                if self._show_floating_note:
                    # Calculate peak screen position
                    px = map_frequencies_to_pixels(np.array([self._smooth_peak_freq]), w, self._scale)[0]
                    frac = max(0, min(1, (self._smooth_peak_db - db_min) / (db_max - db_min)))
                    py = dh * (1.0 - frac)
                    
                    # Readability: Keep badge inside view boundaries
                    bx = max(10, min(w - tw - 10, px - tw/2))
                    by = max(10, min(dh - 30, py - 25))

                    # Draw floating badge
                    painter.setFont(self.get_responsive_font(Fonts.value, tw, 22, txt))
                    self.draw_text_badge(painter, QRectF(bx, by, tw, 22), Qt.AlignCenter, txt, QColor(Colors.ACCENT))
                    
                    # Draw small circle at peak (don't constrain this, it marks the actual bin)
                    painter.setPen(Qt.NoPen); painter.setBrush(QColor(Colors.ACCENT))
                    painter.drawEllipse(QPointF(px, py), 3, 3)
                else:
                    self.draw_text_badge(painter, QRectF(w - tw - 10, 10, tw, 22), Qt.AlignRight, txt, QColor(Colors.ACCENT))
