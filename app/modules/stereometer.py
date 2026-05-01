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
        self._display_mode = "Vectorscope"
        self._color_mode = "Static"
        self._corr_mode = "Single-Band"
        self._guide_mode = "Rhombus"
        self._zoom = 1.0
        self._show_labels = True
        self._minimal_mode = False
        self._halved_view = False
        self._left = np.zeros(1024, dtype=np.float32)
        self._right = np.zeros(1024, dtype=np.float32)
        self._corr = 0.0
        self._mb_corr = {"low": 0.0, "mid": 0.0, "high": 0.0, "overall": 0.0}
        self._multiband = MultiBandFilter(sample_rate=audio_engine.sample_rate)
        self.module_key = "stereometer"
        super().__init__(audio_engine, title="Stereometer", parent=parent)
        self.canvas.set_render_func(self._render)

    def get_settings(self):
        return {
            "display_mode": self._display_mode,
            "color_mode": self._color_mode,
            "corr_mode": self._corr_mode,
            "guide_mode": self._guide_mode,
            "zoom": self._zoom,
            "show_labels": self._show_labels,
            "minimal_mode": self._minimal_mode,
            "halved_view": self._halved_view
        }

    _VALID_DISPLAY_MODES = {"Vectorscope", "Lissajous"}
    _VALID_COLOR_MODES = {"Static", "Multi-Band", "Multi-Band (RGB)"}
    _VALID_CORR_MODES = {"Single-Band", "Multi-Band"}
    _VALID_GUIDE_MODES = {"None", "Rhombus", "Circle"}

    def apply_settings(self, settings):
        dm = settings.get("display_mode", self._display_mode)
        self._display_mode = dm if dm in self._VALID_DISPLAY_MODES else "Vectorscope"
        cm = settings.get("color_mode", self._color_mode)
        self._color_mode = cm if cm in self._VALID_COLOR_MODES else "Static"
        crm = settings.get("corr_mode", self._corr_mode)
        self._corr_mode = crm if crm in self._VALID_CORR_MODES else "Single-Band"
        gm = settings.get("guide_mode", self._guide_mode)
        self._guide_mode = gm if gm in self._VALID_GUIDE_MODES else "Rhombus"
        self._zoom = settings.get("zoom", self._zoom)
        self._show_labels = settings.get("show_labels", self._show_labels)
        self._minimal_mode = settings.get("minimal_mode", self._minimal_mode)
        self._halved_view = settings.get("halved_view", self._halved_view)

    def build_context_menu(self, menu):
        from PySide6.QtGui import QActionGroup
        
        dm = menu.addMenu("Display Mode")
        dg = QActionGroup(self)
        for d in ["Vectorscope", "Lissajous"]:
            a = dm.addAction(d)
            a.setCheckable(True)
            a.setChecked(d == self._display_mode)
            a.triggered.connect(lambda checked, t=d: setattr(self, "_display_mode", t))
            dg.addAction(a)

        gm = menu.addMenu("Guide Map")
        gg = QActionGroup(self)
        for g in ["None", "Rhombus", "Circle"]:
            a = gm.addAction(g)
            a.setCheckable(True)
            a.setChecked(g == self._guide_mode)
            a.triggered.connect(lambda checked, t=g: setattr(self, "_guide_mode", t))
            gg.addAction(a)

        zm = menu.addMenu("Zoom")
        zg = QActionGroup(self)
        # "it looks ugly" look this has a tendency to jump a lot even at 2x zoom, i'm giving user granularity.
        for z in [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0]:
            a = zm.addAction(f"{z}x")
            a.setCheckable(True)
            a.setChecked(z == self._zoom)
            a.triggered.connect(lambda checked, v=z: setattr(self, "_zoom", v))
            zg.addAction(a)

        cm = menu.addMenu("Color")
        cg = QActionGroup(self)
        for c in ["Static", "Multi-Band", "Multi-Band (RGB)"]:
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
            
        crm.setEnabled(not self._minimal_mode)
            
        a = menu.addAction("Minimal Mode")
        a.setCheckable(True)
        a.setChecked(self._minimal_mode)
        a.triggered.connect(lambda checked: setattr(self, "_minimal_mode", checked))

        a = menu.addAction("Show Labels")
        a.setCheckable(True)
        a.setChecked(self._show_labels)
        a.triggered.connect(lambda checked: setattr(self, "_show_labels", checked))

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

        # Reserve space for labels if they are showing
        margin = 18 if self._show_labels else 4
        
        if self._halved_view:
            cy = scope_h
            # In halved view, we only need margin at top and sides, not bottom
            radius = min(cx - margin, scope_h - margin)
        else:
            cy = scope_h / 2
            # Leave room for labels on all 4 sides
            radius = min(cx - margin, cy - margin)

        # 1. Base Grid / Crosshair (Always visible)
        painter.setPen(QPen(QColor(Colors.GRID), 0.5))
        painter.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))
        painter.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))

        # 2. Guide Maps
        painter.setPen(QPen(QColor(Colors.GRID), 1))
        if self._guide_mode == "Rhombus":
            if self._halved_view:
                painter.drawPolygon([QPointF(cx-radius, cy), QPointF(cx, cy-radius), QPointF(cx+radius, cy)])
            else:
                painter.drawPolygon([QPointF(cx, cy-radius), QPointF(cx+radius, cy), QPointF(cx, cy+radius), QPointF(cx-radius, cy)])
        elif self._guide_mode == "Circle":
            if self._halved_view:
                painter.drawArc(int(cx-radius), int(cy-radius), int(radius*2), int(radius*2), 0, 180 * 16)
                painter.drawLine(int(cx-radius), int(cy), int(cx+radius), int(cy))
            else:
                painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Labels (only if enabled)
        if self._show_labels:
            painter.setFont(Fonts.small())
            painter.setPen(QColor(Colors.TEXT_DIM))
            if self._halved_view:
                if self._display_mode == "Vectorscope":
                    painter.setFont(self.get_responsive_font(Fonts.small, 12, 12, "M"))
                    painter.drawText(QRectF(cx - 6, 2, 12, 12), Qt.AlignCenter, "M")
                    painter.setFont(self.get_responsive_font(Fonts.small, 12, 12, "S"))
                    painter.drawText(QRectF(cx - radius - 14, cy - 14, 12, 12), Qt.AlignCenter, "S")
                    painter.drawText(QRectF(cx + radius + 2, cy - 14, 12, 12), Qt.AlignCenter, "S")
                else:
                    painter.setFont(self.get_responsive_font(Fonts.small, 12, 12, "L"))
                    painter.drawText(QRectF(cx - radius - 14, cy - 14, 12, 12), Qt.AlignCenter, "L")
                    painter.setFont(self.get_responsive_font(Fonts.small, 12, 12, "R"))
                    painter.drawText(QRectF(cx + radius + 2, cy - 14, 12, 12), Qt.AlignCenter, "R")
            else:
                if self._display_mode == "Vectorscope":
                    painter.setFont(self.get_responsive_font(Fonts.small, 20, 14, "M"))
                    painter.drawText(QRectF(cx - 10, cy - radius - 16, 20, 14), Qt.AlignCenter, "M")
                    painter.drawText(QRectF(cx - 10, cy + radius + 2, 20, 14), Qt.AlignCenter, "M")
                    painter.setFont(self.get_responsive_font(Fonts.small, 16, 14, "S"))
                    painter.drawText(QRectF(cx - radius - 18, cy - 7, 16, 14), Qt.AlignCenter, "S")
                    painter.drawText(QRectF(cx + radius + 2, cy - 7, 16, 14), Qt.AlignCenter, "S")
                else:
                    painter.setFont(self.get_responsive_font(Fonts.small, 20, 14, "L"))
                    painter.drawText(QRectF(cx - 10, cy - radius - 16, 20, 14), Qt.AlignCenter, "L")
                    painter.drawText(QRectF(cx - 10, cy + radius + 2, 20, 14), Qt.AlignCenter, "L")
                    painter.setFont(self.get_responsive_font(Fonts.small, 16, 14, "R"))
                    painter.drawText(QRectF(cx - radius - 18, cy - 7, 16, 14), Qt.AlignCenter, "R")
                    painter.drawText(QRectF(cx + radius + 2, cy - 7, 16, 14), Qt.AlignCenter, "R")

        left, right = self._left, self._right

        if self._color_mode.startswith("Multi-Band"):
            low_l, mid_l, high_l = self._multiband.split(left)
            low_r, mid_r, high_r = self._multiband.split(right)
            
            if self._color_mode == "Multi-Band (RGB)":
                cols = ["#FF3333", "#33FF33", "#3388FF"]
            else:
                cols = [Colors.BAND_LOW, Colors.BAND_MID, Colors.BAND_HIGH]
                
            for bl, br, col in zip([low_l, mid_l, high_l], [low_r, mid_r, high_r], cols):
                self._draw_dots(painter, bl, br, cx, cy, radius, QColor(col), 100)
        else:
            col = QColor(Colors.ACCENT)
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

            painter.setPen(QColor(Colors.TEXT_DIM))
            painter.setFont(self.get_responsive_font(Fonts.small, 20, inner_h, "-1"))
            painter.drawText(QRectF(margin, bar_y - 1, 20, inner_h), Qt.AlignVCenter, "-1")
            painter.setFont(self.get_responsive_font(Fonts.small, 20, inner_h, "+1"))
            painter.drawText(QRectF(margin + bar_w - 16, bar_y - 1, 20, inner_h), Qt.AlignVCenter, "+1")

    def _draw_dots(self, painter, left, right, cx, cy, radius, color, alpha):
        n = len(left)
        step = max(1, n // 1000)
        
        # Vectorized coordinate calculation
        l_seg = left[::step]
        r_seg = right[::step]
        
        # Apply zoom to segments
        l_seg = l_seg * self._zoom
        r_seg = r_seg * self._zoom

        if self._display_mode == "Vectorscope":
            # Rotated M/S view (Standard Vectorscope)
            xs = cx + (l_seg - r_seg) * 0.5 * radius
            ys = cy - (l_seg + r_seg) * 0.5 * radius
        else:
            # Raw L/R view (True Lissajous math curve)
            xs = cx + r_seg * radius
            ys = cy - l_seg * radius
        
        points = [QPointF(xs[i], ys[i]) for i in range(len(xs))]

        if not points:
            return

        if color is None:
            painter.setPen(QPen(QColor(Colors.ACCENT), 1.5))
        else:
            dc = QColor(color); dc.setAlpha(alpha)
            painter.setPen(QPen(dc, 1.5))
        
        painter.drawPoints(points)
