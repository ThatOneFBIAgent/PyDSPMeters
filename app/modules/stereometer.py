"""
Stereometer Module: Lissajous / Linear / Scaled stereo display with correlation meter.
"""

import numpy as np
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtCore import Qt, QPointF, QRectF

from app.base_module import BaseModule
from app.modules import register_module
from app.theme import Colors, Fonts
from app.dsp.correlation import correlation, multiband_correlation
from app.dsp.filters import MultiBandFilter


@register_module("stereometer", "Stereometer")
class StereometerModule(BaseModule):

    def __init__(self, audio_engine, parent=None):
        self._display_mode = "Lissajous"
        self._color_mode = "Static"
        self._corr_mode = "Single-Band"
        self._minimal_mode = False
        self._halved_view = False
        self._left = np.zeros(1024, dtype=np.float32)
        self._right = np.zeros(1024, dtype=np.float32)
        self._corr = 0.0
        self._mb_corr = {"low": 0.0, "mid": 0.0, "high": 0.0, "overall": 0.0}
        self._multiband = MultiBandFilter(sample_rate=audio_engine.sample_rate)
        super().__init__(audio_engine, title="Stereometer", parent=parent)
        self.canvas.set_render_func(self._render)

    def build_context_menu(self, menu):
        from PySide6.QtGui import QActionGroup
        
        dm = menu.addMenu("Display")
        dg = QActionGroup(self)
        for d in ["Lissajous", "Linear", "Scaled"]:
            a = dm.addAction(d)
            a.setCheckable(True)
            a.setChecked(d == self._display_mode)
            a.triggered.connect(lambda checked, t=d: setattr(self, "_display_mode", t))
            dg.addAction(a)

        cm = menu.addMenu("Color")
        cg = QActionGroup(self)
        for c in ["Static", "RGB", "Multi-Band"]:
            a = cm.addAction(c)
            a.setCheckable(True)
            a.setChecked(c == self._color_mode)
            a.triggered.connect(lambda checked, t=c: setattr(self, "_color_mode", t))
            cg.addAction(a)

        crm = menu.addMenu("Correlation")
        crg = QActionGroup(self)
        for c in ["Single-Band", "Multi-Band"]:
            a = crm.addAction(c)
            a.setCheckable(True)
            a.setChecked(c == self._corr_mode)
            a.triggered.connect(lambda checked, t=c: setattr(self, "_corr_mode", t))
            crg.addAction(a)
            
        a = menu.addAction("Minimal Mode")
        a.setCheckable(True)
        a.setChecked(self._minimal_mode)
        a.triggered.connect(lambda checked: setattr(self, "_minimal_mode", checked))

        a = menu.addAction("Halved View")
        a.setCheckable(True)
        a.setChecked(self._halved_view)
        a.triggered.connect(lambda checked: setattr(self, "_halved_view", checked))

    def on_audio_data(self, data: np.ndarray):
        self._left = data[:, 0].copy()
        self._right = data[:, 1].copy() if data.shape[1] > 1 else data[:, 0].copy()
        self._corr = correlation(self._left, self._right)
        if self._corr_mode == "Multi-Band":
            self._mb_corr = multiband_correlation(
                self._left, self._right, self.audio_engine.sample_rate)

    def _render(self, painter, w, h):
        corr_h = 28 if not self._minimal_mode else 0
        scope_h = h - corr_h
        cx = w / 2

        if self._halved_view:
            cy = scope_h
            radius = min(cx, scope_h) * 0.95
        else:
            cy = scope_h / 2
            radius = min(cx, cy) * 0.85

        # Crosshairs
        painter.setPen(QPen(QColor(Colors.GRID), 1))
        if self._halved_view:
            painter.drawLine(int(cx), 4, int(cx), int(cy))
            painter.drawLine(4, int(cy), int(w - 4), int(cy))
            painter.setFont(Fonts.small())
            painter.setPen(QColor(Colors.TEXT_DIM))
            painter.drawText(QRectF(cx - 6, 2, 12, 12), Qt.AlignCenter, "M")
            painter.drawText(QRectF(2, cy - 14, 12, 12), Qt.AlignCenter, "S")
            painter.drawText(QRectF(w - 14, cy - 14, 12, 12), Qt.AlignCenter, "S")
        else:
            painter.drawLine(int(cx), 4, int(cx), int(scope_h - 4))
            painter.drawLine(4, int(cy), int(w - 4), int(cy))
            painter.setFont(Fonts.small())
            painter.setPen(QColor(Colors.TEXT_DIM))
            painter.drawText(QRectF(cx - 6, 2, 12, 12), Qt.AlignCenter, "M")
            painter.drawText(QRectF(2, cy - 6, 12, 12), Qt.AlignCenter, "S")
            painter.drawText(QRectF(w - 14, cy - 6, 12, 12), Qt.AlignCenter, "S")

        left, right = self._left, self._right

        if self._color_mode == "Multi-Band":
            low_l, mid_l, high_l = self._multiband.split(left)
            low_r, mid_r, high_r = self._multiband.split(right)
            for bl, br, col in [(low_l, low_r, Colors.BAND_LOW),
                                (mid_l, mid_r, Colors.BAND_MID),
                                (high_l, high_r, Colors.BAND_HIGH)]:
                self._draw_dots(painter, bl, br, cx, cy, radius, QColor(col), 100)
        else:
            col = QColor(Colors.ACCENT) if self._color_mode == "Static" else None
            self._draw_dots(painter, left, right, cx, cy, radius, col, 160)

        # Correlation bar
        if not self._minimal_mode:
            margin = 12
            bar_w = w - margin * 2
            bar_y = scope_h + 4
            inner_h = corr_h - 8
            painter.fillRect(QRectF(margin, bar_y, bar_w, inner_h), QColor(Colors.BG_INPUT))
            center_x = margin + bar_w / 2
            painter.setPen(QPen(QColor(Colors.GRID_BRIGHT), 1))
            painter.drawLine(int(center_x), int(bar_y), int(center_x), int(bar_y + inner_h))

            if self._corr_mode == "Single-Band":
                cx2 = margin + (self._corr + 1) / 2 * bar_w
                col = QColor(Colors.GREEN) if self._corr > 0 else QColor(Colors.RED)
                painter.setBrush(QBrush(col)); painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(QRectF(cx2 - 3, bar_y + 1, 6, inner_h - 2), 2, 2)
            else:
                bh = inner_h / 4
                for j, (name, col) in enumerate([("low", Colors.BAND_LOW),
                                                  ("mid", Colors.BAND_MID),
                                                  ("high", Colors.BAND_HIGH),
                                                  ("overall", Colors.ACCENT)]):
                    val = self._mb_corr.get(name, 0.0)
                    bx = margin + (val + 1) / 2 * bar_w
                    painter.setBrush(QBrush(QColor(col))); painter.setPen(Qt.NoPen)
                    painter.drawRoundedRect(QRectF(bx - 2, bar_y + j * bh + 1, 4, bh - 2), 1, 1)

            painter.setFont(Fonts.small())
            painter.setPen(QColor(Colors.TEXT_DIM))
            painter.drawText(QRectF(margin, bar_y - 1, 20, inner_h), Qt.AlignVCenter, "-1")
            painter.drawText(QRectF(margin + bar_w - 16, bar_y - 1, 20, inner_h), Qt.AlignVCenter, "+1")

    def _draw_dots(self, painter, left, right, cx, cy, radius, color, alpha):
        n = len(left)
        # Limit to ~1000 points for performance, but at least every other sample
        step = max(1, n // 1000)
        
        points = []
        for i in range(0, n, step):
            lv, rv = float(left[i]), float(right[i])
            if self._display_mode == "Lissajous":
                x = cx + (lv + rv) * 0.5 * radius
                y = cy - (lv - rv) * 0.5 * radius
            elif self._display_mode == "Linear":
                x, y = cx + rv * radius, cy - lv * radius
            else:
                s = 3.0
                x = cx + (np.tanh(lv * s) + np.tanh(rv * s)) * 0.5 * radius
                y = cy - (np.tanh(lv * s) - np.tanh(rv * s)) * 0.5 * radius
            points.append(QPointF(x, y))

        if not points:
            return

        if color is None:
            # If color mode is RGB, we still need to draw individually or group by color
            # For performance, we'll just use a single color for now if RGB is active but too slow
            painter.setPen(QPen(QColor(Colors.ACCENT), 1.5))
            painter.drawPoints(points)
        else:
            dc = QColor(color); dc.setAlpha(alpha)
            painter.setPen(QPen(dc, 1.5))
            painter.drawPoints(points)
