"""
Classic VU Meter Module: Analog-style needle meter with ballistics.
"""

import math
import numpy as np
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QFont
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
        # Peak hold for LED Bar style
        self._peak_hold_l = -40.0
        self._peak_hold_r = -40.0
        self._peak_hold_decay = 0.02
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
        for i, s in enumerate(["Modern", "Classic Dark", "LED Bar", "Compaq Modern", "Compaq Vintage"]):
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

        calm = menu.addMenu("Calibration (dB)")
        calg = QActionGroup(self)
        for c in [-20, -15, -10, -5, -3, -2, -1, 0, 1, 2, 3, 5, 10, 15, 20]:
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
            
            # Peak hold (for LED Bar style)
            if self._needle_l > self._peak_hold_l:
                self._peak_hold_l = self._needle_l
            else:
                self._peak_hold_l -= self._peak_hold_decay
            if self._needle_r > self._peak_hold_r:
                self._peak_hold_r = self._needle_r
            else:
                self._peak_hold_r -= self._peak_hold_decay
            
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
            
            # Peak hold
            if self._needle_l > self._peak_hold_l:
                self._peak_hold_l = self._needle_l
            else:
                self._peak_hold_l -= self._peak_hold_decay
            self._peak_hold_r = self._peak_hold_l
            
            peak = 20.0 * np.log10(max(np.max(np.abs(sig)), 1e-10)) + self._cal_offset
            self._peak_lit_l = self._peak_lit_r = peak > self._peak_threshold
            self._clip_lit_l = self._clip_lit_r = peak > self._clip_threshold

    def _render(self, painter, w, h):
        if self._style == 2:
            self._render_led_bar(painter, w, h)
            return
        if self._style in (3, 4):
            self._render_compaq(painter, w, h, vintage=self._style == 4)
            return
            
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
                
                if label:
                    # Adaptive decluttering: Hide minor labels if radius is small
                    if radius < 60 and db not in [-20, 0, 3]: continue
                    if radius < 90 and db not in [-20, -10, 0, 3]: continue
                    if radius < 120 and db in [-7, -3, -1, 1, 2]: continue
                    
                    lr = radius * 0.76
                    lx, ly = cx + lr * math.cos(angle) - 12, cy - lr * math.sin(angle) - 7
                    painter.setFont(self.get_responsive_font(Fonts.vu_scale, 24, 14, label))
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
                
                if label:
                    # Adaptive decluttering: Hide minor labels if radius is small
                    if radius < 60 and db not in [-20, 0, 3]: continue
                    if radius < 90 and db not in [-20, -10, 0, 3]: continue
                    if radius < 120 and db in [-7, -3, -1, 1, 2]: continue
                    
                    lr = radius * 0.82
                    lx, ly = cx + lr * math.cos(angle) - 12, cy - lr * math.sin(angle) - 7
                    painter.setFont(self.get_responsive_font(Fonts.vu_scale, 24, 14, label))
                    painter.setPen(col)
                    painter.drawText(QRectF(lx, ly, 24, 14), Qt.AlignCenter, label)

        # Labels
        painter.setFont(self.get_responsive_font(Fonts.small, 80, 20, self._channel))
        painter.setPen(QColor(Colors.TEXT_DIM))
        painter.drawText(QRectF(cx - 40, cy - radius * 0.45, 80, 20), Qt.AlignCenter, self._channel)

        # Needles
        needle_vals = [self._needle_l, self._needle_r] if is_stereo else [self._needle_l]
        
        if is_dark:
            # Thick "Physical" Needles
            needle_cols = [QColor("#ff4422"), QColor("#ff8844")] if is_stereo else [QColor("#ff4422")]
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
            needle_cols = [QColor(Colors.ACCENT), QColor(Colors.ACCENT_PINK)] if is_stereo else [QColor(Colors.ACCENT)]
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
                painter.setFont(self.get_responsive_font(Fonts.small, 40, 12, "PEAK"))
                painter.drawText(QRectF(18, 6, 40, 12), Qt.AlignLeft, "PEAK")
                
        if self._show_clip:
            lit = self._clip_lit_l or self._clip_lit_r
            cc = QColor(Colors.CLIP_LED) if lit else QColor(Colors.BG_INPUT)
            painter.setBrush(QBrush(cc))
            painter.setPen(QPen(QColor(Colors.BORDER), 1))
            painter.drawEllipse(QPointF(w - 12, 12), 4, 4)
            if w > 85:
                painter.setPen(QColor(Colors.TEXT_DIM))
                painter.setFont(self.get_responsive_font(Fonts.small, 40, 12, "CLIP"))
                painter.drawText(QRectF(w - 58, 6, 40, 12), Qt.AlignRight, "CLIP")

    def _render_compaq(self, painter, w, h, vintage=False):
        is_stereo = (self._channel == "L+R")
        if w < 36 or h < 36:
            return

        side = min(w, h)
        ox = (w - side) * 0.5
        oy = (h - side) * 0.5
        outer = QRectF(ox + 2, oy + 2, side - 4, side - 4)
        inset = max(5.0, side * 0.075)
        face = outer.adjusted(inset, inset, -inset, -inset)

        if vintage:
            bezel = QColor("#151515")
            bezel_hi = QColor("#303030")
            face_col = QColor("#efefe7")
            face_shadow = QColor("#d8d8cf")
            tick_col = QColor("#151515")
            text_col = QColor("#202020")
            dim_col = QColor("#6d6d60")
            red_col = QColor("#b03024")
            needle_cols = [QColor("#101010"), QColor("#555555")]
            block_col = QColor("#e4e4dc")
            knob_col = QColor("#161616")
        else:
            bezel = QColor(Colors.BG_DARKEST)
            bezel_hi = QColor(Colors.BORDER)
            face_col = QColor(Colors.BG_MODULE)
            face_shadow = QColor(Colors.BG_INPUT)
            tick_col = QColor(Colors.TEXT_DIM)
            text_col = QColor(Colors.TEXT)
            dim_col = QColor(Colors.TEXT_DIM)
            red_col = QColor(Colors.METER_HIGH)
            needle_cols = [QColor(Colors.ACCENT), QColor(Colors.ACCENT_PINK)]
            block_col = QColor(Colors.BG_HEADER)
            knob_col = QColor(Colors.ACCENT)

        painter.save()
        painter.setPen(QPen(bezel_hi, 1))
        painter.setBrush(QBrush(bezel))
        painter.drawRoundedRect(outer, 4, 4)

        painter.setPen(QPen(face_shadow, 1))
        painter.setBrush(QBrush(face_col))
        painter.drawRoundedRect(face, 5, 5)

        def compaq_font(size, bold=False):
            f = QFont("Arial", max(5, int(size * Fonts.TEXT_SCALE)))
            f.setBold(bold)
            return f

        block_w = face.width() * 0.36
        block_h = face.height() * 0.30
        block = QRectF(face.right() - block_w - 2, face.bottom() - block_h - 2, block_w, block_h)
        knob = QPointF(block.center().x() + block_w * 0.22, block.center().y() + block_h * 0.12)

        cx = knob.x()
        cy = knob.y()
        radius = max(10.0, min((cx - face.left()) * 0.92, (cy - face.top()) * 0.88))
        angle_start, angle_end = 176.0, 96.0

        def point_at(frac, r):
            angle = math.radians(angle_start - frac * (angle_start - angle_end))
            return QPointF(cx + r * math.cos(angle), cy - r * math.sin(angle))

        tick_count = 26 if side >= 120 else 18
        for i in range(tick_count + 1):
            frac = i / tick_count
            is_major = i % max(1, tick_count // 4) == 0
            is_mid = i % max(1, tick_count // 8) == 0
            inner = radius * (0.76 if is_major else 0.84 if is_mid else 0.89)
            outer_r = radius * 0.96
            col = red_col if frac >= 0.82 else tick_col
            painter.setPen(QPen(col, 1.4 if is_major else 0.9))
            painter.drawLine(point_at(frac, inner), point_at(frac, outer_r))

        if side < 82:
            label_items = []
        elif side < 115:
            label_items = [(0.60, "100")]
        elif side < 145:
            label_items = [(0.30, "50"), (0.60, "100")]
        else:
            label_items = [(0.30, "50"), (0.60, "100"), (0.90, "150")]
        label_w = max(16, min(30, face.width() * 0.19))
        label_h = max(9, min(15, face.height() * 0.11))
        label_r = radius * (0.68 if side >= 120 else 0.60)
        for frac, label in label_items:
            pos = point_at(frac, label_r)
            painter.setFont(compaq_font(label_h * 0.75, True))
            painter.setPen(text_col)
            painter.drawText(QRectF(pos.x() - label_w / 2, pos.y() - label_h / 2, label_w, label_h), Qt.AlignCenter, label)

        painter.setFont(compaq_font(min(18, max(8, face.height() * 0.17)), False))
        painter.setPen(text_col)
        painter.drawText(QRectF(face.left() + 8, face.top() + 8, face.width() * 0.22, 20), Qt.AlignLeft, "A")

        if side >= 105:
            brand = "PYDSP"
            painter.setFont(compaq_font(min(7, max(5, face.height() * 0.055)), True))
            painter.setPen(dim_col)
            painter.drawText(QRectF(face.center().x() - face.width() * 0.08, face.center().y() - 4, face.width() * 0.26, 10), Qt.AlignCenter, brand)

        vals = [self._needle_l, self._needle_r] if is_stereo else [self._needle_l]
        for idx, val in enumerate(vals):
            frac = max(0.0, min(1.0, (val + 20.0) / 23.0))
            end = point_at(frac, radius * 0.74)
            col = QColor(needle_cols[idx % len(needle_cols)])
            if is_stereo and idx == 1:
                col.setAlpha(180)
            painter.setPen(QPen(col, 2.2 if idx == 0 else 1.5))
            y_off = idx * max(1.0, side * 0.009) if is_stereo else 0.0
            painter.drawLine(QPointF(cx, cy + y_off), QPointF(end.x(), end.y() + y_off))

        painter.setPen(QPen(face_shadow, 1))
        painter.setBrush(QBrush(block_col))
        painter.drawRoundedRect(block, 5, 5)
        painter.setBrush(QBrush(knob_col))
        painter.setPen(QPen(bezel_hi, 1))
        painter.drawEllipse(knob, max(4, side * 0.034), max(4, side * 0.034))

        if self._show_peak or self._show_clip:
            led_r = max(2.0, min(4.0, side * 0.022))
            led_x = block.left() + max(5, block.width() * 0.18)
            led_y = block.bottom() - max(6, block.height() * 0.24)
            label_x = led_x + led_r * 2 + 3
            show_led_labels = side >= 115 and block.width() > 42
            painter.setFont(compaq_font(6, False))
            if self._show_peak:
                lit = self._peak_lit_l or self._peak_lit_r
                painter.setBrush(QColor(Colors.PEAK_LED) if lit else QColor(Colors.BG_INPUT))
                painter.setPen(QPen(face_shadow, 1))
                painter.drawEllipse(QPointF(led_x, led_y), led_r, led_r)
                if show_led_labels:
                    painter.setPen(dim_col)
                    painter.drawText(QRectF(label_x, led_y - 5, 20, 10), Qt.AlignLeft | Qt.AlignVCenter, "PK")
                led_y -= led_r * 2 + 4
            if self._show_clip:
                lit = self._clip_lit_l or self._clip_lit_r
                painter.setBrush(QColor(Colors.CLIP_LED) if lit else QColor(Colors.BG_INPUT))
                painter.setPen(QPen(face_shadow, 1))
                painter.drawEllipse(QPointF(led_x, led_y), led_r, led_r)
                if show_led_labels:
                    painter.setPen(dim_col)
                    painter.drawText(QRectF(label_x, led_y - 5, 24, 10), Qt.AlignLeft | Qt.AlignVCenter, "CLP")

        painter.restore()

    def _render_led_bar(self, painter, w, h):
        """LED Bar style: Segmented horizontal/vertical bar meter with peak hold."""
        is_stereo = (self._channel == "L+R")
        
        pad = 6
        bar_area_x = pad
        bar_area_w = w - pad * 2
        show_status = h > 34 and (self._show_peak or self._show_clip)
        scale_h = 12
        status_h = 12 if show_status else 0
        status_gap = 2 if show_status else 0
        bottom_reserved = scale_h + status_gap + status_h
        
        # dB range: -40 to +3
        db_min, db_max = -40.0, 3.0
        db_range = db_max - db_min
        
        # VU scale marks
        vu_ticks = [-40, -30, -20, -10, -7, -5, -3, 0, 3]
        
        # Segment count adapts to width
        n_segments = max(12, min(60, int(bar_area_w / 4)))
        seg_gap = max(1, int(bar_area_w / n_segments * 0.15))
        seg_w = (bar_area_w - (n_segments - 1) * seg_gap) / n_segments
        if seg_w < 2:
            seg_w = 2
            seg_gap = 1
        
        if is_stereo:
            # Two bars stacked
            bar_h = max(4, (h - pad * 3 - bottom_reserved) / 2)
            bar_y_l = pad
            bar_y_r = pad + bar_h + pad
            scale_y = bar_y_r + bar_h + 2
            
            self._draw_led_bar_single(painter, bar_area_x, bar_y_l, bar_area_w, bar_h,
                                       self._needle_l, self._peak_hold_l, n_segments, seg_w, seg_gap,
                                       db_min, db_max)
            self._draw_led_bar_single(painter, bar_area_x, bar_y_r, bar_area_w, bar_h,
                                       self._needle_r, self._peak_hold_r, n_segments, seg_w, seg_gap,
                                       db_min, db_max)
            
            # Channel labels
            painter.setFont(self.get_responsive_font(Fonts.small, 14, bar_h, "L"))
            painter.setPen(QColor(Colors.TEXT_DIM))
            painter.drawText(QRectF(bar_area_x - 2, bar_y_l, 14, bar_h), Qt.AlignVCenter | Qt.AlignLeft, "L")
            painter.drawText(QRectF(bar_area_x - 2, bar_y_r, 14, bar_h), Qt.AlignVCenter | Qt.AlignLeft, "R")
        else:
            # Single centered bar
            bar_h = max(6, h - pad * 2 - bottom_reserved)
            bar_y = pad
            scale_y = bar_y + bar_h + 2
            
            self._draw_led_bar_single(painter, bar_area_x, bar_y, bar_area_w, bar_h,
                                       self._needle_l, self._peak_hold_l, n_segments, seg_w, seg_gap,
                                       db_min, db_max)

        # Scale labels
        painter.setFont(Fonts.small())
        for db in vu_ticks:
            frac = (db - db_min) / db_range
            tx = bar_area_x + frac * bar_area_w
            lbl = f"{db}" if db <= 0 else f"+{db}"
            
            # Adaptive decluttering
            if bar_area_w < 200 and db not in [-40, -20, 0, 3]:
                continue
            if bar_area_w < 350 and db in [-30, -7, -5]:
                continue
            
            painter.setPen(QColor(Colors.RED) if db >= 0 else QColor(Colors.TEXT_DIM))
            painter.setFont(self.get_responsive_font(Fonts.small, 28, 12, lbl))
            if scale_y + scale_h <= h - status_h - status_gap:
                painter.drawText(QRectF(tx - 14, scale_y, 28, scale_h), Qt.AlignCenter, lbl)
        
        # PEAK / CLIP LEDs
        if show_status:
            led_y = h - pad - 6
            painter.setFont(Fonts.small())
            if self._show_peak:
                lit = self._peak_lit_l or self._peak_lit_r
                pc = QColor(Colors.PEAK_LED) if lit else QColor(Colors.BG_INPUT)
                painter.setBrush(QBrush(pc))
                painter.setPen(QPen(QColor(Colors.BORDER), 1))
                painter.drawRoundedRect(QRectF(bar_area_x, led_y, 6, 6), 1, 1)
                if w > 85:
                    painter.setPen(QColor(Colors.TEXT_DIM))
                    painter.setFont(self.get_responsive_font(Fonts.small, 30, 10, "PK"))
                    painter.drawText(QRectF(bar_area_x + 9, led_y - 2, 30, 10), Qt.AlignLeft, "PK")
                    
            if self._show_clip:
                lit = self._clip_lit_l or self._clip_lit_r
                cc = QColor(Colors.CLIP_LED) if lit else QColor(Colors.BG_INPUT)
                painter.setBrush(QBrush(cc))
                painter.setPen(QPen(QColor(Colors.BORDER), 1))
                painter.drawRoundedRect(QRectF(w - pad - 6, led_y, 6, 6), 1, 1)
                if w > 85:
                    painter.setPen(QColor(Colors.TEXT_DIM))
                    painter.setFont(self.get_responsive_font(Fonts.small, 30, 10, "CLP"))
                    painter.drawText(QRectF(w - pad - 38, led_y - 2, 30, 10), Qt.AlignRight, "CLP")

    def _draw_led_bar_single(self, painter, x, y, total_w, bar_h, level, peak_hold,
                              n_segments, seg_w, seg_gap, db_min, db_max):
        """Draw a single LED bar with gradient segments and peak hold indicator."""
        db_range = db_max - db_min
        level_frac = max(0, min(1, (level - db_min) / db_range))
        peak_frac = max(0, min(1, (peak_hold - db_min) / db_range))
        lit_segments = int(level_frac * n_segments)
        peak_seg = int(peak_frac * n_segments)
        
        # 0dB threshold segment
        zero_seg = int(((0.0 - db_min) / db_range) * n_segments)
        
        for i in range(n_segments):
            sx = x + i * (seg_w + seg_gap)
            frac = i / n_segments
            
            # Determine segment color by position
            if i >= zero_seg:
                # Red zone (≥ 0 dB)
                seg_color = QColor(Colors.METER_HIGH)
            elif frac > 0.65:
                # Yellow/warning zone
                seg_color = QColor(Colors.METER_MID)
            else:
                # Green/normal zone
                seg_color = QColor(Colors.METER_LOW)
            
            if i < lit_segments:
                # Lit segment
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(seg_color))
                painter.drawRoundedRect(QRectF(sx, y, seg_w, bar_h), 1, 1)
                
                # Subtle inner glow highlight at top
                glow = QColor(255, 255, 255, 40)
                painter.fillRect(QRectF(sx + 1, y + 1, seg_w - 2, max(1, bar_h * 0.25)), glow)
            elif i == peak_seg and peak_hold > db_min + 2:
                # Peak hold marker
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(seg_color))
                painter.drawRoundedRect(QRectF(sx, y, seg_w, bar_h), 1, 1)
            else:
                # Unlit segment — dim outline
                dim = QColor(seg_color)
                dim.setAlpha(25)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(dim))
                painter.drawRoundedRect(QRectF(sx, y, seg_w, bar_h), 1, 1)
