"""
Loudness Meter Module: Selectable LUFS or RMS with compact layout and mode badge.
Supports stereo monitoring, configurable meters, and vertical/horizontal modes.
"""

import numpy as np
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient
from PySide6.QtCore import Qt, QRectF

from app.base_module import BaseModule
from app.modules import register_module
from app.theme import Colors, Fonts
from app.dsp.loudness import LoudnessMeter

# Reactivity presets: display_alpha
REACTIVITY_PRESETS = {
    "Instant":  1.0,
    "Fast":     0.7,
    "Medium":   0.4,
    "Slow":     0.15,
    "Very Slow": 0.05,
}

def _short_unit(mode, avail_w):
    """Return an adaptively shortened unit string based on available pixel width."""
    # Full → Medium → Short
    if mode == "LUFS":
        candidates = ["LUFS", "LF", "L"]
    elif mode == "RMS":
        candidates = ["RMS", "RM", "R"]
    elif mode == "dBTP":
        candidates = ["dBTP", "TP", "T"]
    elif mode == "Int":
        candidates = ["Int", "IN", "I"]
    else:
        candidates = [mode, mode[:2], mode[0]]
        
    if avail_w >= 45:
        return candidates[0]
    elif avail_w >= 25:
        return candidates[1]
    return candidates[2]


@register_module("loudness", "Loudness Meter")
class LoudnessModule(BaseModule):

    def __init__(self, audio_engine, parent=None):
        self._meter = LoudnessMeter(sample_rate=audio_engine.sample_rate, channels=2)
        self._mode = "LUFS"
        self._orientation = "Auto"
        self.module_key = "loudness"
        
        self._show_momentary = True
        self._show_shortterm = True
        self._show_peak = True
        self._show_all_channels = False
        self._show_labels = True
        self._show_mode_indicator = True
        self._show_follow_badge = True
        self._show_scale = True
        self._show_value_badges = True
        self._reactivity = "Fast"
        
        # Values
        ch = audio_engine.channels
        self._lufs_m = np.zeros(ch) - 120.0
        self._lufs_st = np.zeros(ch) - 120.0
        self._lufs_int = -120.0
        self._rms_m = np.zeros(ch) - 120.0
        self._rms_st = np.zeros(ch) - 120.0
        self._peak = np.zeros(ch) - 120.0
        
        self._disp_m = np.zeros(ch) - 60.0
        self._disp_st = np.zeros(ch) - 60.0
        self._disp_int = -60.0
        self._disp_peak = np.zeros(ch) - 60.0
        
        # Peak follower for floating badge
        self._peak_follow = -60.0
        self._show_integrated = True
        
        super().__init__(audio_engine, title="Loudness · LUFS", parent=parent)
        self.canvas.set_render_func(self._render)

    def build_context_menu(self, menu):
        from PySide6.QtGui import QActionGroup
        
        # Mode
        cm = menu.addMenu("Mode")
        cg = QActionGroup(self)
        for m in ["LUFS", "RMS", "dBTP"]:
            a = cm.addAction(m)
            a.setCheckable(True)
            a.setChecked(m == self._mode)
            a.triggered.connect(lambda checked, mode=m: self._set_mode(mode))
            cg.addAction(a)
            
        # Orientation
        om = menu.addMenu("Orientation")
        og = QActionGroup(self)
        for o in ["Auto", "Horizontal", "Vertical"]:
            a = om.addAction(o)
            a.setCheckable(True)
            a.setChecked(o == self._orientation)
            a.triggered.connect(lambda checked, rot=o: setattr(self, "_orientation", rot))
            og.addAction(a)

        # Reactivity
        rm = menu.addMenu("Reactivity")
        rg = QActionGroup(self)
        for name in REACTIVITY_PRESETS:
            a = rm.addAction(name)
            a.setCheckable(True)
            a.setChecked(name == self._reactivity)
            a.triggered.connect(lambda checked, n=name: setattr(self, "_reactivity", n))
            rg.addAction(a)
            
        menu.addSeparator()
        
        # Visibility Toggles
        vm = menu.addMenu("Show / Hide")
        
        m_act = vm.addAction("Show Fast/Mom")
        m_act.setCheckable(True)
        m_act.setChecked(self._show_momentary)
        m_act.triggered.connect(lambda checked: setattr(self, "_show_momentary", checked))
        
        s_act = vm.addAction("Show Slow/Short")
        s_act.setCheckable(True)
        s_act.setChecked(self._show_shortterm)
        s_act.triggered.connect(lambda checked: setattr(self, "_show_shortterm", checked))
        
        p_act = vm.addAction("Show Peak")
        p_act.setCheckable(True)
        p_act.setChecked(self._show_peak)
        p_act.triggered.connect(lambda checked: setattr(self, "_show_peak", checked))
        
        vm.addSeparator()
        
        int_act = vm.addAction("Show Integrated")
        int_act.setCheckable(True)
        int_act.setChecked(self._show_integrated)
        int_act.triggered.connect(lambda checked: setattr(self, "_show_integrated", checked))
        int_act.setEnabled(self._mode == "LUFS")

        vm.addSeparator()
        
        lbl_act = vm.addAction("Show Top Labels")
        lbl_act.setCheckable(True)
        lbl_act.setChecked(self._show_labels)
        lbl_act.triggered.connect(lambda checked: setattr(self, "_show_labels", checked))
        
        ind_act = vm.addAction("Show Mode Badge")
        ind_act.setCheckable(True)
        ind_act.setChecked(self._show_mode_indicator)
        ind_act.triggered.connect(lambda checked: setattr(self, "_show_mode_indicator", checked))

        fb_act = vm.addAction("Show Follow Badge")
        fb_act.setCheckable(True)
        fb_act.setChecked(self._show_follow_badge)
        fb_act.triggered.connect(lambda checked: setattr(self, "_show_follow_badge", checked))
        
        sc_act = vm.addAction("Show Scale")
        sc_act.setCheckable(True)
        sc_act.setChecked(getattr(self, "_show_scale", True))
        sc_act.triggered.connect(lambda checked: setattr(self, "_show_scale", checked))
        
        vb_act = vm.addAction("Show Value Badges")
        vb_act.setCheckable(True)
        vb_act.setChecked(getattr(self, "_show_value_badges", True))
        vb_act.triggered.connect(lambda checked: setattr(self, "_show_value_badges", checked))
        
        menu.addSeparator()
        
        # Multi-Channel
        chan_act = menu.addAction("Show All Channels")
        chan_act.setCheckable(True)
        chan_act.setChecked(self._show_all_channels)
        chan_act.triggered.connect(lambda checked: setattr(self, "_show_all_channels", checked))

        menu.addSeparator()
        a = menu.addAction("Reset Integrated")
        a.triggered.connect(self._reset_integrated)
        a.setEnabled(self._mode == "LUFS")

    def _reset_integrated(self):
        self._meter.reset_integrated()
        self._lufs_int = -120.0
        self._disp_int = -60.0

    def _set_mode(self, mode):
        self._mode = mode
        self.header.set_title(f"Loudness · {mode}")

    def on_audio_data(self, data: np.ndarray):
        self._meter.process(data)
        
        # Get stereo values
        self._lufs_m = self._meter.lufs_momentary_channels
        self._lufs_st = self._meter.lufs_shortterm_channels
        self._lufs_int = self._meter.lufs_integrated
        self._rms_m = self._meter.rms_momentary_channels
        self._rms_st = self._meter.rms_shortterm_channels
        self._peak = self._meter.true_peak_channels
        
        # Get alpha from reactivity preset
        alpha = REACTIVITY_PRESETS.get(self._reactivity, 0.4)
        
        if self._mode == "LUFS":
            m_target, st_target = self._lufs_m, self._lufs_st
            int_target = self._lufs_int
        elif self._mode == "RMS":
            m_target, st_target = self._rms_m, self._rms_st
            int_target = -120.0
        else:  # dBTP
            m_target, st_target = self._peak, self._peak
            int_target = -120.0
            
        # Apply smoothing directly - no rubber banding
        self._disp_m = self._disp_m * (1.0 - alpha) + m_target * alpha
        self._disp_st = self._disp_st * (1.0 - alpha) + st_target * alpha
        self._disp_int = self._disp_int * (1.0 - 0.1) + int_target * 0.1 # Slow smooth for Integrated
        self._disp_peak = self._disp_peak * (1.0 - 0.3) + self._peak * 0.3
        
        # Inverse-log peak follower (mono average)
        db_floor = self._mode_scale()[0]
        current_val = float(np.mean(m_target))
        if current_val > self._peak_follow:
            self._peak_follow = current_val
        else:
            db_range = abs(db_floor)
            level_norm = max(0.01, (self._peak_follow - db_floor) / db_range)
            decay_rate = 0.03 + (1.0 - level_norm) * 0.25
            self._peak_follow -= decay_rate
            self._peak_follow = max(db_floor, self._peak_follow)

    def on_channels_changed(self):
        """Reset buffers and meter when channel count changes."""
        ch = self.audio_engine.channels
        self._meter = LoudnessMeter(sample_rate=self.audio_engine.sample_rate, channels=ch)
        self._lufs_m = np.zeros(ch) - 120.0
        self._lufs_st = np.zeros(ch) - 120.0
        self._rms_m = np.zeros(ch) - 120.0
        self._rms_st = np.zeros(ch) - 120.0
        self._peak = np.zeros(ch) - 120.0
        self._disp_m = np.zeros(ch) - 60.0
        self._disp_st = np.zeros(ch) - 60.0
        self._disp_peak = np.zeros(ch) - 60.0

    def get_settings(self):
        return {
            "mode": self._mode,
            "orientation": self._orientation,
            "reactivity": self._reactivity,
            "show_momentary": self._show_momentary,
            "show_shortterm": self._show_shortterm,
            "show_peak": self._show_peak,
            "show_all_channels": self._show_all_channels,
            "show_labels": self._show_labels,
            "show_mode_indicator": self._show_mode_indicator,
            "show_follow_badge": self._show_follow_badge,
            "show_scale": getattr(self, "_show_scale", True),
            "show_value_badges": getattr(self, "_show_value_badges", True),
        }

    def apply_settings(self, settings):
        self._mode = settings.get("mode", self._mode)
        self.header.set_title(f"Loudness · {self._mode}")
        self._orientation = settings.get("orientation", getattr(self, "_orientation", "Auto"))
        self._reactivity = settings.get("reactivity", self._reactivity)
        self._show_momentary = settings.get("show_momentary", self._show_momentary)
        self._show_shortterm = settings.get("show_shortterm", self._show_shortterm)
        self._show_peak = settings.get("show_peak", self._show_peak)
        self._show_all_channels = settings.get("show_all_channels", self._show_all_channels)
        self._show_labels = settings.get("show_labels", True)
        self._show_mode_indicator = settings.get("show_mode_indicator", True)
        self._show_follow_badge = settings.get("show_follow_badge", True)
        self._show_scale = settings.get("show_scale", True)
        self._show_value_badges = settings.get("show_value_badges", True)

    def _mode_scale(self):
        """Return (db_min, db_max) appropriate for the current mode."""
        if self._mode == "LUFS":
            return -70.0, 0.0
        elif self._mode == "RMS":
            return -60.0, 0.0
        else:  # dBTP
            return -48.0, 0.0

    def _mode_labels(self):
        """Return bar labels appropriate for the current mode."""
        if self._mode == "LUFS":
            return ["Mom", "Short", "Peak", "Int"]
        elif self._mode == "RMS":
            return ["Fast", "Slow", "Peak"]
        else:
            return ["Peak", "Avg", "Hold"]

    def _get_smooth_color(self, val, db_max=0.0):
        """Color ramp relative to the mode's ceiling."""
        c_low, c_mid, c_high = QColor(Colors.METER_LOW), QColor(Colors.METER_MID), QColor(Colors.METER_HIGH)
        dist = val - db_max  # distance below ceiling
        if dist <= -6:
            return c_low
        elif dist <= -1:
            f = (dist + 6) / 5.0
            return QColor(
                int(c_low.red() + (c_mid.red() - c_low.red()) * f),
                int(c_low.green() + (c_mid.green() - c_low.green()) * f),
                int(c_low.blue() + (c_mid.blue() - c_low.blue()) * f)
            )
        else:
            f = min(1.0, (dist + 1) / 1.0)
            return QColor(
                int(c_mid.red() + (c_high.red() - c_mid.red()) * f),
                int(c_mid.green() + (c_high.green() - c_mid.green()) * f),
                int(c_mid.blue() + (c_high.blue() - c_mid.blue()) * f)
            )

    def _render(self, painter, w, h):
        is_vertical = self._orientation == "Vertical"
        if self._orientation == "Auto":
            is_vertical = h > w * 1.1

        db_min, db_max = self._mode_scale()
        m = 4

        active_indices = []
        if self._show_momentary: active_indices.append(0)
        if self._show_shortterm: active_indices.append(1)
        if self._show_peak and not self._show_follow_badge:
            active_indices.append(2)
        if self._show_integrated and self._mode == "LUFS":
            active_indices.append(3)

        if not active_indices and not self._show_follow_badge:
            return

        labels = self._mode_labels()

        if is_vertical:
            self._render_vertical(painter, w, h, active_indices, labels, db_min, db_max, m)
        else:
            self._render_horizontal(painter, w, h, active_indices, labels, db_min, db_max, m)

    def _render_vertical(self, painter, w, h, active_indices, labels, db_min, db_max, m):
        n_groups = max(1, len(active_indices))
        group_gap = 4
        lbl_h = 14 if self._show_labels else 0
        val_h = 14 if getattr(self, "_show_value_badges", True) else 0
        mode_h = 12 if self._show_mode_indicator else 0

        bar_y = m + lbl_h
        bar_h = max(10, h - bar_y - val_h - m - mode_h)

        avail_w = w - m * 2
        scale_w = 0
        badge_w = 0
        pk_bar_w = 0

        if getattr(self, "_show_scale", True) and avail_w >= 40:
            scale_w = 22

        if self._show_follow_badge:
            if avail_w >= 60:
                badge_w = min(50, int(avail_w * 0.35))

        # Space remaining for bars (main + follow peak)
        total_gaps = (n_groups - 1) * group_gap
        if self._show_follow_badge or scale_w > 0:
            total_gaps += 4  # gap before right zone
            if scale_w > 0 and self._show_follow_badge:
                total_gaps += 2 # gap after scale
            if badge_w > 0:
                total_gaps += 2 # gap after peak

        bars_avail = avail_w - scale_w - badge_w - total_gaps
        total_units = n_groups + (0.5 if self._show_follow_badge else 0)
        
        ideal_bar_w = max(4, bars_avail / total_units) if total_units > 0 else bars_avail
        bar_w = min(ideal_bar_w, 36) if (self._show_follow_badge or scale_w > 0) else ideal_bar_w
        
        single_bar_w = bar_w
        if self._show_all_channels:
            ch_count = self.audio_engine.channels
            single_bar_w = (bar_w - (ch_count-1)*2) / ch_count
            
        if self._show_follow_badge:
            pk_bar_w = max(3, int(single_bar_w * 0.5))

        # Calculate actual content width to center it (add 12px padding budget so the badge pill doesn't clip)
        actual_content_w = (bar_w * n_groups) + pk_bar_w + scale_w + badge_w + total_gaps + (12 if badge_w > 0 else 0)
        start_x = m + max(0, (avail_w - actual_content_w) / 2)

        # Draw meter bars
        for idx, meter_idx in enumerate(active_indices):
            gx = start_x + idx * (bar_w + group_gap)

            if self._show_labels:
                painter.setFont(self.get_responsive_font(Fonts.small, bar_w, lbl_h, labels[meter_idx]))
                self.draw_text_badge(painter, QRectF(gx, m, bar_w, lbl_h), Qt.AlignCenter, labels[meter_idx], QColor(Colors.TEXT_DIM))

            if meter_idx == 0:   vals, raw = self._disp_m, (self._lufs_m if self._mode == "LUFS" else (self._rms_m if self._mode == "RMS" else self._peak))
            elif meter_idx == 1: vals, raw = self._disp_st, (self._lufs_st if self._mode == "LUFS" else (self._rms_st if self._mode == "RMS" else self._peak))
            elif meter_idx == 3: vals, raw = np.array([self._disp_int]), np.array([self._lufs_int])
            else:                vals, raw = self._disp_peak, self._peak

            grad = QLinearGradient(0, bar_y + bar_h, 0, bar_y)
            grad.setColorAt(0.0, QColor(Colors.METER_LOW))
            grad.setColorAt(0.7, QColor(Colors.METER_LOW))
            grad.setColorAt(0.85, QColor(Colors.METER_MID))
            grad.setColorAt(1.0, QColor(Colors.METER_HIGH))

            # Integrated bar is always mono (averaged)
            force_mono = (meter_idx == 3)

            if self._show_all_channels and not force_mono:
                ch_count = self.audio_engine.channels
                bw = (bar_w - (ch_count-1)*2) / ch_count
                for ch in range(ch_count):
                    bx = gx + ch * (bw + 2)
                    painter.fillRect(QRectF(bx, bar_y, bw, bar_h), QColor(Colors.BG_INPUT))
                    f = np.clip((vals[ch] - db_min) / (db_max - db_min), 0, 1)
                    if f > 0:
                        painter.fillRect(QRectF(bx, bar_y + bar_h - f * bar_h, bw, f * bar_h), QBrush(grad))
                v_max = float(np.max(raw))
            else:
                v_avg = float(np.mean(vals))
                painter.fillRect(QRectF(gx, bar_y, bar_w, bar_h), QColor(Colors.BG_INPUT))
                f = np.clip((v_avg - db_min) / (db_max - db_min), 0, 1)
                if f > 0:
                    painter.fillRect(QRectF(gx, bar_y + bar_h - f * bar_h, bar_w, f * bar_h), QBrush(grad))
                v_max = float(np.max(raw))

            if getattr(self, "_show_value_badges", True):
                ps_col = self._get_smooth_color(v_max, db_max)
                ps = f"{v_max:.0f}" if v_max > -100 else "-∞"
                painter.setFont(self.get_responsive_font(Fonts.value, bar_w, val_h, ps))
                self.draw_text_badge(painter, QRectF(gx, bar_y + bar_h + 2, bar_w, val_h), Qt.AlignCenter, ps, ps_col)

        # ── Right zone: [scale | peak_bar | badge] ──
        if self._show_follow_badge or getattr(self, "_show_scale", True):
            cur_x = start_x + n_groups * bar_w + (n_groups - 1) * group_gap + 4

            if scale_w > 0:
                painter.save()
                painter.setPen(QPen(QColor(Colors.TEXT_DIM), 1))
                painter.setFont(self.get_responsive_font(Fonts.small, scale_w, 10, "-60"))
                for db in range(0, int(db_min) - 1, -6):
                    if bar_h < 80 and db not in [0, -12, -24, -48, -60, -72]: continue
                    if bar_h < 150 and db not in [0, -6, -12, -24, -36, -48, -60, -72]: continue
                    frac = (db - db_min) / (db_max - db_min)
                    ty = bar_y + bar_h - frac * bar_h
                    painter.drawLine(int(cur_x), int(ty), int(cur_x + 3), int(ty))
                    if scale_w > 12:
                        painter.drawText(QRectF(cur_x + 4, ty - 5, scale_w - 4, 10), Qt.AlignVCenter | Qt.AlignLeft, str(db))
                painter.restore()
                cur_x += scale_w + 2

            if self._show_follow_badge:
                # Peak bar
                painter.fillRect(QRectF(cur_x, bar_y, pk_bar_w, bar_h), QColor(Colors.BG_INPUT))
                pf_norm = float(np.clip((self._peak_follow - db_min) / (db_max - db_min), 0, 1))
                if pf_norm > 0:
                    pk_grad = QLinearGradient(0, bar_y + bar_h, 0, bar_y)
                    pk_grad.setColorAt(0.0, QColor(Colors.METER_LOW))
                    pk_grad.setColorAt(0.7, QColor(Colors.METER_LOW))
                    pk_grad.setColorAt(0.85, QColor(Colors.METER_MID))
                    pk_grad.setColorAt(1.0, QColor(Colors.METER_HIGH))
                    fill_h = pf_norm * bar_h
                    painter.fillRect(QRectF(cur_x, bar_y + bar_h - fill_h, pk_bar_w, fill_h), QBrush(pk_grad))
                
                pk_right = cur_x + pk_bar_w
                cur_x = pk_right + 2
    
                # Floating badge label
                if badge_w > 0:
                    pf_y = bar_y + bar_h - pf_norm * bar_h
                    
                    unit = _short_unit(self._mode, badge_w)
                    pf_val = f"{self._peak_follow:.1f}" if badge_w > 30 else f"{self._peak_follow:.0f}"
                    pf_text = f"{pf_val}{unit}"
                    label_h = min(14, max(8, int(bar_h * 0.06)))
                    
                    ly = pf_y - label_h / 2.0
                    ly = max(bar_y, min(bar_y + bar_h - label_h, ly))
    
                    painter.setFont(self.get_responsive_font(Fonts.small, badge_w, label_h, pf_text))
                    
                    # Offset text start so pill's left padding doesn't overlap tick
                    pad_x = int(4 * getattr(Fonts, 'TEXT_SCALE', 1.0))
                    badge_x = cur_x + pad_x
    
                    self.draw_text_badge(
                        painter, QRectF(badge_x, ly, badge_w, label_h),
                        Qt.AlignVCenter | Qt.AlignLeft, pf_text,
                        QColor(Colors.BG_DARK), QColor(Colors.ACCENT)
                    )
                    
                    painter.setPen(QPen(QColor(Colors.ACCENT), 1))
                    tick_y = int(ly + label_h / 2)
                    painter.drawLine(int(pk_right), tick_y, int(badge_x - pad_x), tick_y)

        # Mode Indicator
        if self._show_mode_indicator:
            chars = list(self._mode)
            if len(chars) > 0 and avail_w > 0:
                painter.save()
                painter.setOpacity(0.6)
                painter.setFont(Fonts.small())
                ch_w = avail_w / len(chars)
                for idx, char in enumerate(chars):
                    char_rect = QRectF(m + idx * ch_w, h - 14, ch_w, 10)
                    painter.drawText(char_rect, Qt.AlignCenter, char)
                painter.restore()

    def _render_horizontal(self, painter, w, h, active_indices, labels, db_min, db_max, m):
        mode_w = 14 if self._show_mode_indicator else 0
        lbl_w = 38 if self._show_labels else 0
        val_w = 46 if getattr(self, "_show_value_badges", True) else 0
        bar_x = m + mode_w + lbl_w + (6 if (mode_w + lbl_w) > 0 else 0)
        bar_w = max(10, w - bar_x - val_w - m - (2 if val_w > 0 else 0))
        
        # Reserve bottom row for follow badge if enabled — scales with height
        badge_h = 0
        pk_bar_h = 3
        if self._show_follow_badge:
            badge_h = max(12, min(28, int(h * 0.18)))
            pk_bar_h = max(2, min(5, int(h * 0.02)))
        
        n_rows = max(1, len(active_indices))
        row_gap = 3
        avail_h = h - m * 2 - badge_h - (2 if badge_h > 0 else 0)
        
        ideal_row_h = max(6, (avail_h - row_gap * (n_rows - 1)) // n_rows)
        # Cap row height only if follow badge is present to maintain proportions
        row_h = min(ideal_row_h, 24) if self._show_follow_badge else ideal_row_h
        
        actual_content_h = (row_h * n_rows) + (row_gap * (n_rows - 1))
        start_y = m + max(0, (avail_h - actual_content_h) / 2)
        
        # Draw Vertical Mode Strip
        if self._show_mode_indicator:
            chars = list(self._mode)
            if len(chars) > 0 and h > m*2:
                painter.save()
                painter.setOpacity(0.6)
                painter.setFont(Fonts.small())
                ch_h = (h - m*2) / len(chars)
                for idx, char in enumerate(chars):
                    char_rect = QRectF(m, m + idx * ch_h, mode_w, ch_h)
                    painter.drawText(char_rect, Qt.AlignCenter, char)
                painter.restore()

        for idx, meter_idx in enumerate(active_indices):
            ry = start_y + idx * (row_h + row_gap)
            
            # Label
            if self._show_labels:
                painter.setFont(self.get_responsive_font(Fonts.small, lbl_w, row_h, labels[meter_idx]))
                self.draw_text_badge(painter, QRectF(m + mode_w, ry, lbl_w, row_h), Qt.AlignVCenter | Qt.AlignRight, labels[meter_idx], QColor(Colors.TEXT_DIM))
            
            # Get values
            if meter_idx == 0:   vals, raw = self._disp_m, (self._lufs_m if self._mode == "LUFS" else (self._rms_m if self._mode == "RMS" else self._peak))
            elif meter_idx == 1: vals, raw = self._disp_st, (self._lufs_st if self._mode == "LUFS" else (self._rms_st if self._mode == "RMS" else self._peak))
            elif meter_idx == 3: vals, raw = np.array([self._disp_int]), np.array([self._lufs_int])
            else:                vals, raw = self._disp_peak, self._peak
            
            force_mono = (meter_idx == 3)
            
            # Create Horizontal Gradient
            grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
            grad.setColorAt(0.0, QColor(Colors.METER_LOW))
            grad.setColorAt(0.7, QColor(Colors.METER_LOW))
            grad.setColorAt(0.85, QColor(Colors.METER_MID))
            grad.setColorAt(1.0, QColor(Colors.METER_HIGH))

            # Bars
            if self._show_all_channels and not force_mono:
                ch_count = self.audio_engine.channels
                bh = (row_h - (ch_count-1)*2) / ch_count
                for ch in range(ch_count):
                    by = ry + ch * (bh + 2)
                    painter.fillRect(QRectF(bar_x, by, bar_w, bh), QColor(Colors.BG_INPUT))
                    f = np.clip((vals[ch] - db_min) / (db_max - db_min), 0, 1)
                    if f > 0:
                        painter.fillRect(QRectF(bar_x, by, f * bar_w, bh), QBrush(grad))
                v_max = float(np.max(raw))
            else:
                v_avg = float(np.mean(vals))
                painter.fillRect(QRectF(bar_x, ry + 1, bar_w, row_h - 2), QColor(Colors.BG_INPUT))
                f = np.clip((v_avg - db_min) / (db_max - db_min), 0, 1)
                if f > 0:
                    painter.fillRect(QRectF(bar_x, ry + 1, f * bar_w, row_h - 2), QBrush(grad))
                v_max = float(np.max(raw))
                
            # Value Badge
            if getattr(self, "_show_value_badges", True):
                ps = f"{v_max:.1f}" if v_max > -100 else "-∞"
                painter.setFont(self.get_responsive_font(Fonts.value, val_w, row_h, ps))
                ps_col = self._get_smooth_color(v_max, db_max)
                self.draw_text_badge(painter, QRectF(bar_x + bar_w + 2, ry, val_w, row_h), Qt.AlignVCenter | Qt.AlignRight, ps, ps_col)

        # Horizontal follow badge row at the bottom
        if self._show_follow_badge:
            badge_y = h - m - badge_h
            
            # Mono peak bar (horizontal, thin)
            painter.fillRect(QRectF(bar_x, badge_y, bar_w, pk_bar_h), QColor(Colors.BG_INPUT))
            pf_norm = float(np.clip((self._peak_follow - db_min) / (db_max - db_min), 0, 1))
            if pf_norm > 0:
                pk_grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
                pk_grad.setColorAt(0.0, QColor(Colors.METER_LOW))
                pk_grad.setColorAt(0.7, QColor(Colors.METER_LOW))
                pk_grad.setColorAt(0.85, QColor(Colors.METER_MID))
                pk_grad.setColorAt(1.0, QColor(Colors.METER_HIGH))
                painter.fillRect(QRectF(bar_x, badge_y, pf_norm * bar_w, pk_bar_h), QBrush(pk_grad))
            
            # Floating label
            pf_x = bar_x + pf_norm * bar_w
            
            label_w = max(30, min(70, int(bar_w * 0.25)))
            unit = _short_unit(self._mode, label_w)
            
            pf_val = f"{self._peak_follow:.1f}" if bar_w > 60 else f"{self._peak_follow:.0f}"
            pf_text = f"{pf_val}{unit}"
            label_h = max(8, badge_h - pk_bar_h - 4)
            
            lx = pf_x - label_w / 2.0
            lx = max(bar_x, min(bar_x + bar_w - label_w, lx))
            ly = badge_y + pk_bar_h + 2
            
            painter.setFont(self.get_responsive_font(Fonts.small, label_w, label_h, pf_text))
            self.draw_text_badge(
                painter, QRectF(lx, ly, label_w, label_h),
                Qt.AlignCenter, pf_text,
                QColor(Colors.BG_DARK), QColor(Colors.ACCENT)
            )
            
            # Vertical tick line from bar to label
            painter.setPen(QPen(QColor(Colors.ACCENT), 1))
            painter.drawLine(int(pf_x), int(badge_y + pk_bar_h), int(pf_x), int(ly))
