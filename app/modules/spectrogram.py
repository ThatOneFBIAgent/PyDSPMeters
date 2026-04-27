"""
Spectrogram Module: Scrolling time-frequency display (numpy-accelerated).
"""

import numpy as np
from PySide6.QtGui import QPainter, QColor, QImage, QPen
from PySide6.QtCore import Qt, QRectF

from app.base_module import BaseModule
from app.modules import register_module
from app.theme import Colors, Fonts
from app.dsp.fft import compute_fft, fft_frequencies, map_frequencies_to_pixels


def _build_colormap(stops, n=256):
    lut = np.zeros((n, 3), dtype=np.uint8)
    for i in range(n):
        t = i / (n - 1)
        for j in range(len(stops) - 1):
            t0, c0 = stops[j]
            t1, c1 = stops[j + 1]
            if t0 <= t <= t1:
                frac = (t - t0) / (t1 - t0) if t1 > t0 else 0
                qc0, qc1 = QColor(c0), QColor(c1)
                lut[i] = [
                    int(qc0.red() + (qc1.red() - qc0.red()) * frac),
                    int(qc0.green() + (qc1.green() - qc0.green()) * frac),
                    int(qc0.blue() + (qc1.blue() - qc0.blue()) * frac),
                ]
                break
    return lut


@register_module("spectrogram", "Spectrogram")
class SpectrogramModule(BaseModule):

    def __init__(self, audio_engine, parent=None):
        self._fft_size = 2048
        self._scale = "logarithmic"
        self._orientation = "Horizontal"
        self._tilt = 0.0
        self._mode = "Classic"
        self._show_piano = False
        self._show_freq = True
        self._loop = False
        self._display_h = 128  # Reduced for performance
        self._history_len = 400
        self._history = np.zeros((self._history_len, self._display_h), dtype=np.float32)
        self._col_idx = 0
        self._lut = _build_colormap(Colors.HEATMAP_STOPS)
        self._img_cache = None  # Keep reference for QImage data
        self._frame_skip = 0
        super().__init__(audio_engine, title="Spectrogram", parent=parent)
        self.canvas.set_render_func(self._render)

    def on_theme_changed(self):
        self._lut = _build_colormap(Colors.HEATMAP_STOPS)

    def build_context_menu(self, menu):
        from PySide6.QtGui import QActionGroup
        
        fm = menu.addMenu("FFT Size")
        fg = QActionGroup(self)
        for f in [1024, 2048, 4096, 8192]:
            a = fm.addAction(str(f))
            a.setCheckable(True)
            a.setChecked(f == self._fft_size)
            a.triggered.connect(lambda checked, t=f: self._set_fft(int(t)))
            fg.addAction(a)

        scm = menu.addMenu("Scale")
        scg = QActionGroup(self)
        for s in ["Mel", "Logarithmic", "Linear"]:
            a = scm.addAction(s)
            a.setCheckable(True)
            a.setChecked(s.lower() == self._scale)
            a.triggered.connect(lambda checked, t=s: setattr(self, "_scale", t.lower()))
            scg.addAction(a)
            
        om = menu.addMenu("Orientation")
        og = QActionGroup(self)
        for o in ["Horizontal", "Vertical"]:
            a = om.addAction(o)
            a.setCheckable(True)
            a.setChecked(o == self._orientation)
            a.triggered.connect(lambda checked, t=o: setattr(self, "_orientation", t))
            og.addAction(a)
            
        mm = menu.addMenu("Mode")
        mg = QActionGroup(self)
        for m in ["Sharper", "Sharp", "Classic"]:
            a = mm.addAction(m)
            a.setCheckable(True)
            a.setChecked(m == self._mode)
            a.triggered.connect(lambda checked, t=m: setattr(self, "_mode", t))
            mg.addAction(a)

        tm = menu.addMenu("Tilt")
        tg = QActionGroup(self)
        for t in [-20, -10, 0, 10, 20]:
            a = tm.addAction(str(t))
            a.setCheckable(True)
            a.setChecked(abs(t - self._tilt) < 0.1)
            a.triggered.connect(lambda checked, v=t: setattr(self, "_tilt", float(v)))
            tg.addAction(a)

        a = menu.addAction("Piano Overlay")
        a.setCheckable(True)
        a.setChecked(self._show_piano)
        a.triggered.connect(lambda checked: setattr(self, "_show_piano", checked))

        a = menu.addAction("Frequency Lines")
        a.setCheckable(True)
        a.setChecked(self._show_freq)
        a.triggered.connect(lambda checked: setattr(self, "_show_freq", checked))

    def _set_fft(self, size):
        self._fft_size = size
        self._history = np.zeros((self._history_len, self._display_h), dtype=np.float32)
        self._col_idx = 0

    def _get_window(self):
        if self._mode == "Sharper": return "blackmanharris"
        if self._mode == "Sharp": return "blackman"
        return "hann"

    def on_audio_data(self, data: np.ndarray):
        sig = (data[:, 0] + data[:, 1]) * 0.5 if data.shape[1] > 1 else data[:, 0]
        mag = compute_fft(sig, self._fft_size, window=self._get_window())

        if abs(self._tilt) > 0.1:
            n = len(mag)
            mag = mag + np.linspace(-self._tilt, self._tilt, n)

        db_min, db_max = -90.0, 0.0
        norm = np.clip((mag - db_min) / (db_max - db_min), 0, 1)

        # Map FFT bins to display bins using frequency scale
        freqs = fft_frequencies(self._fft_size, self.audio_engine.sample_rate)
        n_bins = min(len(norm), len(freqs))
        px = map_frequencies_to_pixels(freqs[:n_bins], self._display_h, self._scale)

        column = np.zeros(self._display_h, dtype=np.float32)
        px_int = np.clip(px.astype(np.int32), 0, self._display_h - 1)
        # Use numpy advanced indexing for speed
        np.maximum.at(column, px_int[:n_bins], norm[:n_bins])
        
        # Fill gaps in the column (especially at the low end where bins are sparse)
        nonzero = np.where(column > 0)[0]
        if len(nonzero) > 1:
            from scipy.interpolate import interp1d
            f = interp1d(nonzero, column[nonzero], kind='linear', fill_value="nearest")
            full_idx = np.arange(nonzero[0], nonzero[-1] + 1)
            column[full_idx] = np.maximum(column[full_idx], f(full_idx))

        idx = self._col_idx % self._history_len
        self._history[idx] = column
        self._col_idx += 1

    def _render(self, painter, w, h):
        if self._col_idx < 1:
            return

        # Always render the full history buffer for a stable-width display.
        # np.roll reorders the circular buffer so the newest column is on
        # the right edge and the oldest (or empty/black) is on the left.
        write_head = self._col_idx % self._history_len
        ordered = np.roll(self._history, -write_head, axis=0)

        # Transpose: rows = freq bins (low freq at bottom), cols = time
        display = ordered.T[::-1]

        # Numpy LUT colormap lookup (fast)
        indices = np.clip((display * 255).astype(np.int32), 0, 255)
        rgb = self._lut[indices]
        rgb = np.ascontiguousarray(rgb)
        self._img_cache = rgb  # prevent GC while QImage references this memory

        qimg = QImage(rgb.data, rgb.shape[1], rgb.shape[0],
                      rgb.shape[1] * 3, QImage.Format_RGB888)

        if self._orientation == "Vertical":
            from PySide6.QtGui import QTransform
            qimg = qimg.transformed(QTransform().rotate(90))

        scaled = qimg.scaled(w, h, Qt.IgnoreAspectRatio, Qt.FastTransformation)
        painter.drawImage(0, 0, scaled)

        # Frequency overlay lines
        if self._show_freq:
            painter.setFont(Fonts.small())
            for gf in [100, 500, 1000, 5000, 10000]:
                if self._orientation == "Horizontal":
                    fy = h - map_frequencies_to_pixels(
                        np.array([gf]), h, self._scale)[0]
                    if 0 < fy < h:
                        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
                        painter.drawLine(0, int(fy), w, int(fy))
                        lb = f"{gf}" if gf < 1000 else f"{gf // 1000}k"
                        self.draw_text_badge(painter, QRectF(6, fy - 10, 30, 12), Qt.AlignLeft, lb, QColor(255, 255, 255, 150))

        if self._show_piano:
            self._draw_piano(painter, w, h)

    def _draw_piano(self, painter, w, h):
        notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        black = {1, 3, 6, 8, 10}
        for octave in range(1, 9):
            for ni, note in enumerate(notes):
                freq = 440.0 * 2 ** ((octave - 4) + (ni - 9) / 12.0)
                if freq < 20 or freq > 20000:
                    continue
                fy = h - map_frequencies_to_pixels(
                    np.array([freq]), h, self._scale)[0]
                if 0 < fy < h:
                    col = QColor(0, 0, 0, 100) if ni in black else QColor(255, 255, 255, 60)
                    painter.setPen(QPen(col, 1))
                    painter.drawLine(w - 20, int(fy), w, int(fy))
