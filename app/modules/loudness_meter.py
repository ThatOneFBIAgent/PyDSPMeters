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
        self._orientation = "Auto"
        super().__init__(audio_engine, title="Loudness · LUFS", parent=parent)
        self.canvas.set_render_func(self._render)

    def build_context_menu(self, menu):
        from PySide6.QtGui import QActionGroup
        cm = menu.addMenu("Mode")
        cg = QActionGroup(self)
        for m in ["LUFS", "RMS"]:
            a = cm.addAction(m)
            a.setCheckable(True)
            a.setChecked(m == self._mode)
            a.triggered.connect(lambda checked, mode=m: self._set_mode(mode))
            cg.addAction(a)
            
        om = menu.addMenu("Orientation")
        og = QActionGroup(self)
        for o in ["Auto", "Horizontal", "Vertical"]:
            a = om.addAction(o)
            a.setCheckable(True)
            a.setChecked(o == self._orientation)
            a.triggered.connect(lambda checked, rot=o: setattr(self, "_orientation", rot))
            og.addAction(a)

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
        is_vertical = self._orientation == "Vertical"
        if self._orientation == "Auto":
            is_vertical = h > w * 1.2

        if self._mode == "LUFS":
            labels = ["Fast", "Slow"]
        else:
            labels = ["Mom", "Short"]

        raw = ([self._lufs_m, self._lufs_st] if self._mode == "LUFS" else [self._rms_m, self._rms_st])
        db_min, db_max = -60.0, 0.0

        if is_vertical:
            # Vertical columns
            m = 4
            lbl_h = 16
            val_h = 16
            bar_y = m + lbl_h
            bar_h = max(10, h - bar_y - val_h - m)
            
            col_gap = 4
            total_cols = 3
            col_w = max(12, (w - m * 2 - col_gap * (total_cols - 1)) // total_cols)

            for i in range(2):
                x = m + i * (col_w + col_gap)
                painter.setFont(Fonts.small())
                self.draw_text_badge(painter, QRectF(x, m, col_w, lbl_h), Qt.AlignCenter, labels[i], QColor(Colors.TEXT_DIM))
                
                painter.fillRect(QRectF(x + 1, bar_y, col_w - 2, bar_h), QColor(Colors.BG_INPUT))
                frac = max(0, min(1, (self._disp[i] - db_min) / (db_max - db_min)))
                fh = frac * bar_h
                if fh > 1:
                    grad = QLinearGradient(0, bar_y + bar_h, 0, bar_y)
                    grad.setColorAt(0.0, QColor(Colors.GREEN))
                    grad.setColorAt(0.6, QColor(Colors.GREEN))
                    grad.setColorAt(0.8, QColor(Colors.YELLOW))
                    grad.setColorAt(0.95, QColor(Colors.RED))
                    painter.fillRect(QRectF(x + 1, bar_y + bar_h - fh, col_w - 2, fh), QBrush(grad))

                painter.setFont(Fonts.value())
                vs = f"{raw[i]:.0f}" if raw[i] > -100 else "-∞"
                col = Colors.TEXT
                if raw[i] > -6: col = Colors.YELLOW
                if raw[i] > -1: col = Colors.RED
                self.draw_text_badge(painter, QRectF(x, bar_y + bar_h + 2, col_w, val_h), Qt.AlignCenter, vs, QColor(col))

            # Peak column
            px = m + 2 * (col_w + col_gap)
            painter.setFont(Fonts.small())
            self.draw_text_badge(painter, QRectF(px, m, col_w, lbl_h), Qt.AlignCenter, "Peak", QColor(Colors.TEXT_DIM))

            pc = Colors.GREEN
            if self._peak > -6: pc = Colors.YELLOW
            if self._peak > -1: pc = Colors.RED

            pfrac = max(0, min(1, (self._peak - db_min) / (db_max - db_min)))
            painter.fillRect(QRectF(px + 1, bar_y, col_w - 2, bar_h), QColor(Colors.BG_INPUT))
            if pfrac * bar_h > 1:
                painter.fillRect(QRectF(px + 1, bar_y + bar_h - pfrac * bar_h, col_w - 2, pfrac * bar_h), QColor(pc))

            painter.setFont(Fonts.value())
            ps = f"{self._peak:.0f}" if self._peak > -100 else "-∞"
            self.draw_text_badge(painter, QRectF(px, bar_y + bar_h + 2, col_w, val_h), Qt.AlignCenter, ps, QColor(pc))

        else:
            # Horizontal rows (Original geometry)
            m = 4
            lbl_w = 38
            val_w = 46
            bar_x = m + lbl_w + 2
            bar_w = max(10, w - bar_x - val_w - m - 2)
            
            row_gap = 3
            total_rows = 3
            row_h = max(12, (h - m * 2 - row_gap * (total_rows - 1)) // total_rows)

            for i in range(2):
                y = m + i * (row_h + row_gap)
                painter.setFont(Fonts.small())
                self.draw_text_badge(painter, QRectF(m, y, lbl_w, row_h), Qt.AlignVCenter | Qt.AlignRight, labels[i], QColor(Colors.TEXT_DIM))
                
                painter.fillRect(QRectF(bar_x, y + 1, bar_w, row_h - 2), QColor(Colors.BG_INPUT))
                frac = max(0, min(1, (self._disp[i] - db_min) / (db_max - db_min)))
                fw = frac * bar_w
                if fw > 1:
                    grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
                    grad.setColorAt(0.0, QColor(Colors.GREEN))
                    grad.setColorAt(0.6, QColor(Colors.GREEN))
                    grad.setColorAt(0.8, QColor(Colors.YELLOW))
                    grad.setColorAt(0.95, QColor(Colors.RED))
                    painter.fillRect(QRectF(bar_x, y + 1, fw, row_h - 2), QBrush(grad))

                painter.setFont(Fonts.value())
                vs = f"{raw[i]:.1f}" if raw[i] > -100 else "-∞"
                col = Colors.TEXT
                if raw[i] > -6: col = Colors.YELLOW
                if raw[i] > -1: col = Colors.RED
                self.draw_text_badge(painter, QRectF(bar_x + bar_w + 2, y, val_w, row_h), Qt.AlignVCenter | Qt.AlignRight, vs, QColor(col))

            # Peak row
            py = m + 2 * (row_h + row_gap)
            painter.setFont(Fonts.small())
            self.draw_text_badge(painter, QRectF(m, py, lbl_w, row_h), Qt.AlignVCenter | Qt.AlignRight, "Peak", QColor(Colors.TEXT_DIM))

            pc = Colors.GREEN
            if self._peak > -6: pc = Colors.YELLOW
            if self._peak > -1: pc = Colors.RED

            pfrac = max(0, min(1, (self._peak - db_min) / (db_max - db_min)))
            painter.fillRect(QRectF(bar_x, py + 1, bar_w, row_h - 2), QColor(Colors.BG_INPUT))
            if pfrac * bar_w > 1:
                painter.fillRect(QRectF(bar_x, py + 1, pfrac * bar_w, row_h - 2), QColor(pc))

            painter.setFont(Fonts.value())
            ps = f"{self._peak:.1f}" if self._peak > -100 else "-∞"
            self.draw_text_badge(painter, QRectF(bar_x + bar_w + 2, py, val_w, row_h), Qt.AlignVCenter | Qt.AlignRight, ps, QColor(pc))
