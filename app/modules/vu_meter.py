"""
Classic VU Meter Module: Analog-style needle meter with ballistics.
"""

import math
import numpy as np
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath
from PySide6.QtCore import Qt, QPointF, QRectF

from app.base_module import BaseModule
from app.modules import register_module
from app.theme import Colors, Fonts


@register_module("vu_meter", "VU Meter")
class VUMeterModule(BaseModule):

    def __init__(self, audio_engine, parent=None):
        self._needle_val = -40.0
        self._target_val = -40.0
        self._peak_lit = False
        self._clip_lit = False
        self._peak_threshold = -6.0
        self._clip_threshold = -0.5
        self._cal_offset = 0.0
        self._channel = "Left"
        self._style = 0
        self._show_peak = True
        self._show_clip = True
        self._rise_coeff = 0.30
        self._fall_coeff = 0.08
        super().__init__(audio_engine, title="VU Meter", parent=parent)
        self.canvas.set_render_func(self._render)

    def setup_settings(self):
        c = self.settings.add_combo("Style", ["Style 1", "Style 2"], 0)
        c.currentIndexChanged.connect(lambda i: setattr(self, "_style", i))
        c = self.settings.add_combo("Channel", ["Left", "Right", "Mid", "Side"], 0)
        c.currentTextChanged.connect(lambda t: setattr(self, "_channel", t))
        s = self.settings.add_slider("Cal (dB)", -20, 20, 0)
        s.valueChanged.connect(lambda v: setattr(self, "_cal_offset", float(v)))
        self.settings.add_checkbox("Peak LED", True).toggled.connect(
            lambda v: setattr(self, "_show_peak", v))
        self.settings.add_checkbox("Clip LED", True).toggled.connect(
            lambda v: setattr(self, "_show_clip", v))

    def on_audio_data(self, data: np.ndarray):
        l, r = data[:, 0], data[:, 1] if data.shape[1] > 1 else data[:, 0]
        sig = {"Left": l, "Right": r, "Mid": (l+r)*0.5, "Side": (l-r)*0.5
               }.get(self._channel, l)

        rms = np.sqrt(np.mean(sig ** 2))
        db = 20.0 * np.log10(max(rms, 1e-10)) + self._cal_offset
        self._target_val = max(-40.0, min(3.0, db))

        if self._target_val > self._needle_val:
            self._needle_val += (self._target_val - self._needle_val) * self._rise_coeff
        else:
            self._needle_val += (self._target_val - self._needle_val) * self._fall_coeff

        peak_db = 20.0 * np.log10(max(np.max(np.abs(sig)), 1e-10)) + self._cal_offset
        self._peak_lit = peak_db > self._peak_threshold
        self._clip_lit = peak_db > self._clip_threshold

    def _render(self, painter, w, h):
        is_dark = self._style == 1
        cx, cy = w / 2, h * 0.72
        radius = min(w * 0.42, h * 0.65)
        if radius < 10:
            return

        angle_start, angle_end = 150, 30
        vu_marks = [(-20, "-20"), (-10, "-10"), (-7, "-7"), (-5, "-5"),
                    (-3, "-3"), (-2, ""), (-1, "-1"),
                    (0, "0"), (1, "+1"), (2, "+2"), (3, "+3")]

        for db, label in vu_marks:
            frac = (db + 20) / 23.0
            angle = math.radians(angle_start - frac * (angle_start - angle_end))
            inner_r, outer_r = radius * 0.75, radius * 0.88
            x1 = cx + inner_r * math.cos(angle)
            y1 = cy - inner_r * math.sin(angle)
            x2 = cx + outer_r * math.cos(angle)
            y2 = cy - outer_r * math.sin(angle)
            tc = QColor(Colors.RED) if db >= 0 else (
                QColor(Colors.TEXT_BRIGHT) if is_dark else QColor("#444444"))
            painter.setPen(QPen(tc, 1.5 if abs(db) % 5 == 0 else 0.8))
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            if label:
                lr = radius * 0.63
                lx = cx + lr * math.cos(angle) - 12
                ly = cy - lr * math.sin(angle) - 7
                painter.setFont(Fonts.vu_scale())
                painter.setPen(tc)
                painter.drawText(QRectF(lx, ly, 24, 14), Qt.AlignCenter, label)

        # VU label
        painter.setFont(Fonts.header())
        painter.setPen(QColor(Colors.ACCENT) if is_dark else QColor("#444444"))
        painter.drawText(QRectF(cx - 15, cy - radius * 0.35, 30, 20),
                         Qt.AlignCenter, "VU")

        # Red zone arc
        red_frac = 20.0 / 23.0
        red_a = angle_start - red_frac * (angle_start - angle_end)
        painter.setPen(QPen(QColor(Colors.RED), 3))
        arc_r = radius * 0.88
        arc_rect = QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2)
        painter.drawArc(arc_rect, int(angle_end * 16), int((red_a - angle_end) * 16))

        # Needle
        nf = max(0, min(1, (self._needle_val + 20) / 23.0))
        na = math.radians(angle_start - nf * (angle_start - angle_end))
        nl = radius * 0.9
        nx, ny = cx + nl * math.cos(na), cy - nl * math.sin(na)
        painter.setPen(QPen(QColor(0, 0, 0, 60), 3))
        painter.drawLine(QPointF(cx + 1, cy + 1), QPointF(nx + 1, ny + 1))
        nc = QColor(Colors.VU_NEEDLE) if not is_dark else QColor(Colors.ACCENT)
        painter.setPen(QPen(nc, 2))
        painter.drawLine(QPointF(cx, cy), QPointF(nx, ny))
        painter.setBrush(QBrush(nc))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), 4, 4)

        # LEDs
        led_y = h - 18
        if self._show_peak:
            lx = w * 0.3
            pc = QColor(Colors.YELLOW) if self._peak_lit else QColor(Colors.BG_INPUT)
            painter.setBrush(QBrush(pc))
            painter.setPen(QPen(QColor(Colors.BORDER), 1))
            painter.drawEllipse(QPointF(lx, led_y), 5, 5)
            painter.setFont(Fonts.small())
            painter.setPen(QColor(Colors.TEXT_DIM))
            painter.drawText(QRectF(lx + 8, led_y - 6, 30, 12), Qt.AlignLeft, "PEAK")
        if self._show_clip:
            lx = w * 0.65
            cc = QColor(Colors.RED) if self._clip_lit else QColor(Colors.BG_INPUT)
            painter.setBrush(QBrush(cc))
            painter.setPen(QPen(QColor(Colors.BORDER), 1))
            painter.drawEllipse(QPointF(lx, led_y), 5, 5)
            painter.setFont(Fonts.small())
            painter.setPen(QColor(Colors.TEXT_DIM))
            painter.drawText(QRectF(lx + 8, led_y - 6, 30, 12), Qt.AlignLeft, "CLIP")
