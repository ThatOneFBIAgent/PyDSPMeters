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
        self._needle_l = -40.0
        self._needle_r = -40.0
        self._target_l = -40.0
        self._target_r = -40.0
        self._peak_lit_l = False
        self._peak_lit_r = False
        self._clip_lit_l = False
        self._clip_lit_r = False
        self._peak_threshold = -6.0
        self._clip_threshold = -0.5
        self._cal_offset = 0.0
        self._channel = "L+R" if audio_engine.channels >= 2 else "Left"
        self._style = 0
        self._show_peak = True
        self._show_clip = True
        self._rise_coeff = 0.30
        self._fall_coeff = 0.08
        self.module_key = "vu_meter"
        super().__init__(audio_engine, title="VU Meter", parent=parent)
        self.canvas.set_render_func(self._render)

    def get_settings(self):
        return {
            "channel": self._channel,
            "cal_offset": self._cal_offset,
            "style": self._style,
            "show_peak": self._show_peak,
            "show_clip": self._show_clip
        }

    def apply_settings(self, settings):
        self._channel = settings.get("channel", self._channel)
        self._cal_offset = float(settings.get("cal_offset", self._cal_offset))
        self._style = int(settings.get("style", self._style))
        self._show_peak = settings.get("show_peak", self._show_peak)
        self._show_clip = settings.get("show_clip", self._show_clip)

    def build_context_menu(self, menu):
        from PySide6.QtGui import QActionGroup
        
        sm = menu.addMenu("Style")
        sg = QActionGroup(self)
        for i, s in enumerate(["Modern", "Classic Dark"]):
            a = sm.addAction(s)
            a.setCheckable(True)
            a.setChecked(i == self._style)
            a.triggered.connect(lambda checked, idx=i: setattr(self, "_style", idx))
            sg.addAction(a)
            
        cm = menu.addMenu("Channel")
        cg = QActionGroup(self)
        channels = ["L+R", "Left", "Right", "Mid", "Side"]
        for c in channels:
            a = cm.addAction(c)
            a.setCheckable(True)
            a.setChecked(c == self._channel)
            a.triggered.connect(lambda checked, t=c: setattr(self, "_channel", t))
            cg.addAction(a)

        calm = menu.addMenu("Cal (dB)")
        calg = QActionGroup(self)
        for c in [-20, -10, 0, 10, 20]:
            a = calm.addAction(str(c))
            a.setCheckable(True)
            a.setChecked(abs(c - self._cal_offset) < 0.1)
            a.triggered.connect(lambda checked, v=c: setattr(self, "_cal_offset", float(v)))
            calg.addAction(a)
            
        a = menu.addAction("Peak LED")
        a.setCheckable(True)
        a.setChecked(self._show_peak)
        a.triggered.connect(lambda checked: setattr(self, "_show_peak", checked))

        a = menu.addAction("Clip LED")
        a.setCheckable(True)
        a.setChecked(self._show_clip)
        a.triggered.connect(lambda checked: setattr(self, "_show_clip", checked))

    def on_audio_data(self, data: np.ndarray):
        l, r = data[:, 0], data[:, 1] if data.shape[1] > 1 else data[:, 0]
        
        # Calculate targets
        if self._channel == "L+R":
            rms_l = np.sqrt(np.mean(l ** 2))
            rms_r = np.sqrt(np.mean(r ** 2))
            target_l = 20.0 * np.log10(max(rms_l, 1e-10)) + self._cal_offset
            target_r = 20.0 * np.log10(max(rms_r, 1e-10)) + self._cal_offset
            self._target_l = max(-40.0, min(3.0, target_l))
            self._target_r = max(-40.0, min(3.0, target_r))
            
            # Ballistics
            self._needle_l += (self._target_l - self._needle_l) * (self._rise_coeff if self._target_l > self._needle_l else self._fall_coeff)
            self._needle_r += (self._target_r - self._needle_r) * (self._rise_coeff if self._target_r > self._needle_r else self._fall_coeff)
            
            # Peak/Clip
            peak_l = 20.0 * np.log10(max(np.max(np.abs(l)), 1e-10)) + self._cal_offset
            peak_r = 20.0 * np.log10(max(np.max(np.abs(r)), 1e-10)) + self._cal_offset
            self._peak_lit_l = peak_l > self._peak_threshold
            self._peak_lit_r = peak_r > self._peak_threshold
            self._clip_lit_l = peak_l > self._clip_threshold
            self._clip_lit_r = peak_r > self._clip_threshold
        else:
            sig = {"Left": l, "Right": r, "Mid": (l+r)*0.5, "Side": (l-r)*0.5}.get(self._channel, l)
            rms = np.sqrt(np.mean(sig ** 2))
            db = 20.0 * np.log10(max(rms, 1e-10)) + self._cal_offset
            target = max(-40.0, min(3.0, db))
            self._target_l = self._target_r = target
            self._needle_l += (target - self._needle_l) * (self._rise_coeff if target > self._needle_l else self._fall_coeff)
            self._needle_r = self._needle_l
            
            peak = 20.0 * np.log10(max(np.max(np.abs(sig)), 1e-10)) + self._cal_offset
            self._peak_lit_l = self._peak_lit_r = peak > self._peak_threshold
            self._clip_lit_l = self._clip_lit_r = peak > self._clip_threshold

    def _render(self, painter, w, h):
        style = self._style
        is_dark = (style == 1)
        is_stereo = (self._channel == "L+R")
        
        # Geometry: Ensure a stable pivot and a non-warped radius
        cx, cy = w / 2, h - 4
        # We cap the radius to ensure it doesn't look stretched in wide windows
        radius = min(w * 0.45, h * 0.95)
        if radius < 15: return

        angle_start, angle_end = 150, 30
        
        # Scale Definitions
        vu_marks = [(-20, "-20"), (-10, "-10"), (-7, "-7"), (-5, "-5"),
                    (-3, "-3"), (-2, ""), (-1, "-1"),
                    (0, "0"), (1, "+1"), (2, "+2"), (3, "+3")]

        if is_dark:
            # Classic Dark: "Recessed Studio" look
            # Draw a subtle background plate
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#0a0a12")))
            face_rect = QRectF(cx - radius * 1.1, cy - radius * 1.1, radius * 2.2, radius * 2.2)
            painter.drawPie(face_rect, int(angle_end * 16), int((angle_start - angle_end) * 16))
            
            # Scale Arc
            arc_r = radius * 0.96
            painter.setPen(QPen(QColor("#252535"), 2))
            painter.drawArc(QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2), 
                            int(angle_end * 16), int((angle_start - angle_end) * 16))
            
            # Vintage Marks
            for db, label in vu_marks:
                frac = (db + 20) / 23.0
                angle = math.radians(angle_start - frac * (angle_start - angle_end))
                inner_r, outer_r = radius * 0.88, radius * 0.96
                
                col = QColor("#ff3344") if db >= 0 else QColor("#d0c0a0") # Warm cream
                painter.setPen(QPen(col, 2 if abs(db) % 5 == 0 or db == 0 else 1))
                painter.drawLine(QPointF(cx + inner_r * math.cos(angle), cy - inner_r * math.sin(angle)),
                                 QPointF(cx + outer_r * math.cos(angle), cy - outer_r * math.sin(angle)))
                
                if label and w > 130:
                    lr = radius * 0.76
                    lx, ly = cx + lr * math.cos(angle) - 12, cy - lr * math.sin(angle) - 7
                    painter.setFont(Fonts.vu_scale())
                    painter.setPen(col)
                    painter.drawText(QRectF(lx, ly, 24, 14), Qt.AlignCenter, label)
        else:
            # Modern: Minimalist "Floating" look
            arc_r = radius * 0.95
            painter.setPen(QPen(QColor(Colors.GRID), 1))
            painter.drawArc(QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2), 
                            int(angle_end * 16), int((angle_start - angle_end) * 16))
            
            # Red zone highlight
            red_frac = 20.0 / 23.0
            red_a = angle_start - red_frac * (angle_start - angle_end)
            painter.setPen(QPen(QColor(Colors.RED), 2))
            painter.drawArc(QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2), 
                            int(angle_end * 16), int((red_a - angle_end) * 16))

            for db, label in vu_marks:
                frac = (db + 20) / 23.0
                angle = math.radians(angle_start - frac * (angle_start - angle_end))
                inner_r, outer_r = radius * 0.90, radius * 0.95
                
                col = QColor(Colors.RED) if db >= 0 else QColor(Colors.TEXT_DIM)
                painter.setPen(QPen(col, 1.2 if abs(db) % 5 == 0 or db == 0 else 0.6))
                painter.drawLine(QPointF(cx + inner_r * math.cos(angle), cy - inner_r * math.sin(angle)),
                                 QPointF(cx + outer_r * math.cos(angle), cy - outer_r * math.sin(angle)))
                
                if label and w > 130:
                    lr = radius * 0.82
                    lx, ly = cx + lr * math.cos(angle) - 12, cy - lr * math.sin(angle) - 7
                    painter.setFont(Fonts.vu_scale())
                    painter.setPen(col)
                    painter.drawText(QRectF(lx, ly, 24, 14), Qt.AlignCenter, label)

        # Labels
        painter.setFont(Fonts.small())
        painter.setPen(QColor(Colors.TEXT_DIM))
        painter.drawText(QRectF(cx - 40, cy - radius * 0.45, 80, 20), Qt.AlignCenter, self._channel)

        # Needles
        needle_vals = [self._needle_l, self._needle_r] if is_stereo else [self._needle_l]
        
        if is_dark:
            # Thick "Physical" Needles
            needle_cols = [QColor("#ff4422"), QColor("#ff8844")] if is_stereo else [QColor("#cc2200")]
            for val, col in zip(needle_vals, needle_cols):
                nf = max(0, min(1, (val + 20) / 23.0))
                na = math.radians(angle_start - nf * (angle_start - angle_end))
                
                # Needle body
                painter.setPen(QPen(col, 2.5))
                nx, ny = cx + radius * 1.05 * math.cos(na), cy - radius * 1.05 * math.sin(na)
                painter.drawLine(QPointF(cx, cy), QPointF(nx, ny))
            
            # Physical Pivot Cap
            painter.setBrush(QBrush(QColor("#222222")))
            painter.setPen(QPen(QColor("#444444"), 1))
            painter.drawEllipse(QPointF(cx, cy), 7, 7)
            painter.setBrush(QBrush(QColor("#111111")))
            painter.drawEllipse(QPointF(cx, cy), 3, 3)
        else:
            # Sleek Modern Needles
            needle_cols = [QColor(Colors.ACCENT), QColor(Colors.ACCENT_PINK)] if is_stereo else [QColor(Colors.VU_NEEDLE)]
            for val, col in zip(needle_vals, needle_cols):
                nf = max(0, min(1, (val + 20) / 23.0))
                na = math.radians(angle_start - nf * (angle_start - angle_end))
                
                # Subtle Glow/Shadow for visibility
                if not is_stereo:
                    painter.setPen(QPen(QColor(0, 0, 0, 60), 2.5))
                    sx, sy = cx + radius * 1.05 * math.cos(na), cy - radius * 1.05 * math.sin(na)
                    painter.drawLine(QPointF(cx + 1, cy + 1), QPointF(sx + 1, sy + 1))
                
                painter.setPen(QPen(col, 2))
                nx, ny = cx + radius * 1.05 * math.cos(na), cy - radius * 1.05 * math.sin(na)
                painter.drawLine(QPointF(cx, cy), QPointF(nx, ny))
                
            painter.setBrush(QBrush(needle_cols[0]))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(cx, cy), 5, 5)

        # PEAK / CLIP status
        painter.setFont(Fonts.small())
        if self._show_peak:
            lit = self._peak_lit_l or self._peak_lit_r
            pc = QColor(Colors.PEAK_LED) if lit else QColor(Colors.BG_INPUT)
            painter.setBrush(QBrush(pc))
            painter.setPen(QPen(QColor(Colors.BORDER), 1))
            painter.drawEllipse(QPointF(12, 12), 4, 4)
            if w > 85:
                painter.setPen(QColor(Colors.TEXT_DIM))
                painter.drawText(QRectF(18, 6, 40, 12), Qt.AlignLeft, "PEAK")
                
        if self._show_clip:
            lit = self._clip_lit_l or self._clip_lit_r
            cc = QColor(Colors.CLIP_LED) if lit else QColor(Colors.BG_INPUT)
            painter.setBrush(QBrush(cc))
            painter.setPen(QPen(QColor(Colors.BORDER), 1))
            painter.drawEllipse(QPointF(w - 12, 12), 4, 4)
            if w > 85:
                painter.setPen(QColor(Colors.TEXT_DIM))
                painter.drawText(QRectF(w - 58, 6, 40, 12), Qt.AlignRight, "CLIP")
