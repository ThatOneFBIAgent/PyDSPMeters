"""
Loudness Meter Module: Selectable LUFS or RMS with compact layout and mode badge.
"""

import numpy as np
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient
from PySide6.QtCore import Qt, QRectF

from app.base_module import BaseModule
from app.modules import register_module
from app.theme import Colors, Fonts
from app.dsp.loudness import LoudnessMeter


@register_module("loudness", "Loudness Meter")
class LoudnessModule(BaseModule):

    def __init__(self, audio_engine, parent=None):
        self._meter = LoudnessMeter(sample_rate=audio_engine.sample_rate, channels=2)
        self._mode = "LUFS"
        self._lufs_m = -120.0
        self._lufs_st = -120.0
        self._rms_m = -120.0
        self._rms_st = -120.0
        self._peak = -120.0
        self._peak_hold = -120.0
        self._peak_hold_frames = 0
        self._disp = [-60.0, -60.0]
        super().__init__(audio_engine, title="Loudness · LUFS", parent=parent)
        self.canvas.set_render_func(self._render)

    def setup_settings(self):
        c = self.settings.add_combo("Mode", ["LUFS", "RMS"], 0)
        c.currentTextChanged.connect(self._set_mode)

    def _set_mode(self, mode):
        self._mode = mode
        self._disp = [-60.0, -60.0]
        self.header.set_title(f"Loudness · {mode}")

    def on_audio_data(self, data: np.ndarray):
        self._meter.process(data)
        self._lufs_m = self._meter.lufs_momentary
        self._lufs_st = self._meter.lufs_shortterm
        self._rms_m = self._meter.rms_momentary
        self._rms_st = self._meter.rms_shortterm
        self._peak = self._meter.true_peak
        if self._peak > self._peak_hold:
            self._peak_hold = self._peak
            self._peak_hold_frames = 90
        elif self._peak_hold_frames > 0:
            self._peak_hold_frames -= 1
        else:
            self._peak_hold = max(self._peak_hold - 0.3, self._peak)

        if self._mode == "LUFS":
            targets = [self._lufs_m, self._lufs_st]
        else:
            targets = [self._rms_m, self._rms_st]
        for i in range(2):
            self._disp[i] += (targets[i] - self._disp[i]) * 0.3

    def _render(self, painter, w, h):
        m = 4  # tight margins
        lbl_w = 38
        val_w = 46
        bar_x = m + lbl_w + 2
        bar_w = max(10, w - bar_x - val_w - m - 2)
        db_min, db_max = -60.0, 0.0

        # Divide available height into 3 equal rows (bar1, bar2, peak)
        row_gap = 3
        total_rows = 3
        row_h = max(12, (h - m * 2 - row_gap * (total_rows - 1)) // total_rows)

        if self._mode == "LUFS":
            labels = ["Fast", "Slow"]
        else:
            labels = ["Mom", "Short"]

        raw = ([self._lufs_m, self._lufs_st] if self._mode == "LUFS"
               else [self._rms_m, self._rms_st])

        for i in range(2):
            y = m + i * (row_h + row_gap)
            # Label
            painter.setFont(Fonts.small())
            painter.setPen(QColor(Colors.TEXT_DIM))
            painter.drawText(m, y, lbl_w, row_h,
                             Qt.AlignVCenter | Qt.AlignRight, labels[i])
            # Bar background
            painter.fillRect(QRectF(bar_x, y + 1, bar_w, row_h - 2),
                             QColor(Colors.BG_INPUT))
            # Bar fill
            frac = max(0, min(1, (self._disp[i] - db_min) / (db_max - db_min)))
            fw = frac * bar_w
            if fw > 1:
                grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
                grad.setColorAt(0.0, QColor(Colors.GREEN))
                grad.setColorAt(0.6, QColor(Colors.GREEN))
                grad.setColorAt(0.8, QColor(Colors.YELLOW))
                grad.setColorAt(0.95, QColor(Colors.RED))
                painter.fillRect(QRectF(bar_x, y + 1, fw, row_h - 2),
                                 QBrush(grad))
            # Value
            painter.setFont(Fonts.value())
            vs = f"{raw[i]:.1f}" if raw[i] > -100 else "-∞"
            col = Colors.TEXT
            if raw[i] > -6: col = Colors.YELLOW
            if raw[i] > -1: col = Colors.RED
            painter.setPen(QColor(col))
            painter.drawText(bar_x + bar_w + 2, y, val_w, row_h,
                             Qt.AlignVCenter | Qt.AlignRight, vs)

        # Peak row
        py = m + 2 * (row_h + row_gap)
        painter.setFont(Fonts.small())
        painter.setPen(QColor(Colors.TEXT_DIM))
        painter.drawText(m, py, lbl_w, row_h,
                         Qt.AlignVCenter | Qt.AlignRight, "Peak")

        pc = Colors.GREEN
        if self._peak > -6: pc = Colors.YELLOW
        if self._peak > -1: pc = Colors.RED

        # Peak bar
        pfrac = max(0, min(1, (self._peak - db_min) / (db_max - db_min)))
        painter.fillRect(QRectF(bar_x, py + 1, bar_w, row_h - 2),
                         QColor(Colors.BG_INPUT))
        if pfrac * bar_w > 1:
            painter.fillRect(QRectF(bar_x, py + 1, pfrac * bar_w, row_h - 2),
                             QColor(pc))

        # Peak value
        painter.setFont(Fonts.value())
        painter.setPen(QColor(pc))
        ps = f"{self._peak:.1f}" if self._peak > -100 else "-∞"
        painter.drawText(bar_x + bar_w + 2, py, val_w, row_h,
                         Qt.AlignVCenter | Qt.AlignRight, ps)
