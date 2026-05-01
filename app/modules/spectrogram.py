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
        self._display_h = 256
        self._history_len = 512
        self._db_floor = -90.0
        self._history = np.zeros((self._history_len, self._display_h), dtype=np.float32)
        self._col_idx = 0
        self._lut = _build_colormap(Colors.HEATMAP_STOPS)
        self._speed = 1.0
        self._last_rendered_idx = 0
        self.module_key = "spectrogram"
        super().__init__(audio_engine, title="Spectrogram", parent=parent)
        self.canvas.set_render_func(self._render)

    def on_theme_changed(self):
        self._lut = _build_colormap(Colors.HEATMAP_STOPS)
        # Force re-color existing buffer to prevent bleeding from old theme
        if hasattr(self, "_buffer_data"):
            # Map history values (0-1) to indices (0-255)
            indices = np.clip((self._history * 255).astype(np.int32), 0, 255)
            # Apply LUT to entire history and update buffer_data
            # Note: buffer_data is (H, W, 3), history is (W, H)
            for x in range(self._history_len):
                rgb_col = self._lut[indices[x]]
                if self._buffer_data.shape[1] > x:
                    self._buffer_data[:, x] = rgb_col[::-1]

    def get_settings(self):
        return {
            "fft_size": self._fft_size,
            "scale": self._scale,
            "orientation": self._orientation,
            "tilt": self._tilt,
            "mode": self._mode,
            "show_piano": self._show_piano,
            "show_freq": self._show_freq,
            "speed": self._speed,
            "db_floor": self._db_floor
        }

    def apply_settings(self, settings):
        self._fft_size = settings.get("fft_size", self._fft_size)
        self._scale = settings.get("scale", self._scale)
        self._orientation = settings.get("orientation", self._orientation)
        self._tilt = float(settings.get("tilt", self._tilt))
        self._mode = settings.get("mode", self._mode)
        self._show_piano = settings.get("show_piano", self._show_piano)
        self._show_freq = settings.get("show_freq", self._show_freq)
        self._speed = float(settings.get("speed", self._speed))
        self._db_floor = float(settings.get("db_floor", self._db_floor))
        # Re-initialize history if FFT size changed
        self._set_fft(self._fft_size)

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
        
        sm = menu.addMenu("Speed")
        sg = QActionGroup(self)
        for s in [1, 2, 4, 8]:
            a = sm.addAction(f"{s}x")
            a.setCheckable(True)
            a.setChecked(int(self._speed) == s)
            a.triggered.connect(lambda checked, v=s: setattr(self, "_speed", float(v)))
            sg.addAction(a)
            
        menu.addSeparator()
        flm = menu.addMenu("Floor (Sensitivity)")
        flg = QActionGroup(self)
        for f in [-120, -90, -70, -50]:
            a = flm.addAction(f"{f} dB")
            a.setCheckable(True)
            a.setChecked(int(self._db_floor) == f)
            a.triggered.connect(lambda checked, v=f: setattr(self, "_db_floor", float(v)))
            flg.addAction(a)

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
        
        n_steps = int(self._speed)
        step_size = len(sig) // n_steps
        
        freqs = fft_frequencies(self._fft_size, self.audio_engine.sample_rate)
        n_bins = min(self._fft_size // 2, len(freqs))
        px = map_frequencies_to_pixels(freqs[:n_bins], self._display_h, self._scale)
        px_int = np.clip(px.astype(np.int32), 0, self._display_h - 1)
        
        for s in range(n_steps):
            start = s * step_size
            end = start + self._fft_size
            
            if start + self._fft_size > len(sig):
                chunk = sig[-self._fft_size:]
            else:
                chunk = sig[start:end]
                
            mag = compute_fft(chunk, self._fft_size, window=self._get_window())

            if abs(self._tilt) > 0.1:
                mag = mag + np.linspace(-self._tilt, self._tilt, len(mag))

            db_min, db_max = self._db_floor, 0.0
            norm = np.clip((mag - db_min) / (db_max - db_min), 0, 1)

            column = np.zeros(self._display_h, dtype=np.float32)
            np.maximum.at(column, px_int[:n_bins], norm[:n_bins])
            
            # Interpolation to fill gaps
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
        if self._col_idx < 1: return

        if not hasattr(self, "_buffer_img") or self._buffer_img.height() != self._display_h:
            self._buffer_data = np.zeros((self._display_h, self._history_len, 3), dtype=np.uint8)
            self._buffer_img = QImage(self._buffer_data.data, self._history_len, self._display_h, 
                                     self._history_len * 3, QImage.Format_RGB888)

        # Colormap all new columns since last render
        if self._last_rendered_idx < self._col_idx:
            # For efficiency, only color the range we missed
            for idx in range(self._last_rendered_idx, self._col_idx):
                write_head = idx % self._history_len
                column_data = self._history[write_head]
                indices = np.clip((column_data * 255).astype(np.int32), 0, 255)
                rgb_col = self._lut[indices]
                self._buffer_data[:, write_head] = rgb_col[::-1]
            
            self._last_rendered_idx = self._col_idx
        
        # Draw circular segments
        head = self._col_idx % self._history_len
        from PySide6.QtCore import QRect
        
        len_1 = self._history_len - head
        w_1 = int(w * (len_1 / self._history_len))
        
        if self._orientation == "Horizontal":
            painter.drawImage(QRect(0, 0, w_1, h), self._buffer_img, QRect(head, 0, len_1, self._display_h))
            painter.drawImage(QRect(w_1, 0, w - w_1, h), self._buffer_img, QRect(0, 0, head, self._display_h))
        else:
            from PySide6.QtGui import QTransform
            painter.drawImage(QRect(0, 0, w, h), self._buffer_img.transformed(QTransform().rotate(90)))

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
                        from PySide6.QtGui import QFontMetrics
                        fm = QFontMetrics(Fonts.small())
                        tw = fm.horizontalAdvance(lb) + 12
                        painter.setFont(self.get_responsive_font(Fonts.small, tw, 12, lb))
                        self.draw_text_badge(painter, QRectF(6, fy - 10, tw, 12), Qt.AlignLeft, lb, QColor(255, 255, 255, 150))

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
