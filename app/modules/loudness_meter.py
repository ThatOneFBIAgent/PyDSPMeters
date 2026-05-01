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
        
        # Values
        ch = audio_engine.channels
        self._lufs_m = np.zeros(ch) - 120.0
        self._lufs_st = np.zeros(ch) - 120.0
        self._rms_m = np.zeros(ch) - 120.0
        self._rms_st = np.zeros(ch) - 120.0
        self._peak = np.zeros(ch) - 120.0
        
        self._disp_m = np.zeros(ch) - 60.0
        self._disp_st = np.zeros(ch) - 60.0
        self._disp_peak = np.zeros(ch) - 60.0
        
        super().__init__(audio_engine, title="Loudness · LUFS", parent=parent)
        self.canvas.set_render_func(self._render)

    def build_context_menu(self, menu):
        from PySide6.QtGui import QActionGroup
        
        # Mode
        cm = menu.addMenu("Mode")
        cg = QActionGroup(self)
        for m in ["LUFS", "RMS"]:
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
        
        menu.addSeparator()
        
        # Multi-Channel
        chan_act = menu.addAction("Show All Channels")
        chan_act.setCheckable(True)
        chan_act.setChecked(self._show_all_channels)
        chan_act.triggered.connect(lambda checked: setattr(self, "_show_all_channels", checked))

    def _set_mode(self, mode):
        self._mode = mode
        self.header.set_title(f"Loudness · {mode}")

    def on_audio_data(self, data: np.ndarray):
        self._meter.process(data)
        
        # Get stereo values
        self._lufs_m = self._meter.lufs_momentary_channels
        self._lufs_st = self._meter.lufs_shortterm_channels
        self._rms_m = self._meter.rms_momentary_channels
        self._rms_st = self._meter.rms_shortterm_channels
        self._peak = self._meter.true_peak_channels
        
        # Smoothing for display
        alpha = 0.3
        if self._mode == "LUFS":
            m_target, st_target = self._lufs_m, self._lufs_st
        else:
            m_target, st_target = self._rms_m, self._rms_st
            
        self._disp_m += (m_target - self._disp_m) * alpha
        self._disp_st += (st_target - self._disp_st) * alpha
        self._disp_peak += (self._peak - self._disp_peak) * alpha

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
            "show_momentary": self._show_momentary,
            "show_shortterm": self._show_shortterm,
            "show_peak": self._show_peak,
            "show_all_channels": self._show_all_channels
        }

    def apply_settings(self, settings):
        self._mode = settings.get("mode", self._mode)
        self.header.set_title(f"Loudness · {self._mode}")
        self._orientation = settings.get("orientation", self._orientation)
        self._show_momentary = settings.get("show_momentary", self._show_momentary)
        self._show_shortterm = settings.get("show_shortterm", self._show_shortterm)
        self._show_peak = settings.get("show_peak", self._show_peak)
        self._show_all_channels = settings.get("show_all_channels", self._show_all_channels)

    def _get_smooth_color(self, val):
        c_low, c_mid, c_high = QColor(Colors.METER_LOW), QColor(Colors.METER_MID), QColor(Colors.METER_HIGH)
        if val <= -6:
            return c_low
        elif val <= -1:
            f = (val + 6) / 5.0
            return QColor(
                int(c_low.red() + (c_mid.red() - c_low.red()) * f),
                int(c_low.green() + (c_mid.green() - c_low.green()) * f),
                int(c_low.blue() + (c_mid.blue() - c_low.blue()) * f)
            )
        else:
            f = min(1.0, (val + 1) / 1.0)
            return QColor(
                int(c_mid.red() + (c_high.red() - c_mid.red()) * f),
                int(c_mid.green() + (c_high.green() - c_mid.green()) * f),
                int(c_mid.blue() + (c_high.blue() - c_mid.blue()) * f)
            )

    def _render(self, painter, w, h):
        is_vertical = self._orientation == "Vertical"
        if self._orientation == "Auto":
            is_vertical = h > w * 1.1

        db_min, db_max = -60.0, 0.0
        m = 4
        
        # Identify active meters
        active_indices = []
        if self._show_momentary: active_indices.append(0)
        if self._show_shortterm: active_indices.append(1)
        if self._show_peak:      active_indices.append(2)
        
        if not active_indices:
            return

        labels = ["Fast", "Slow", "Peak"] if self._mode == "LUFS" else ["Mom", "Short", "Peak"]
        
        if is_vertical:
            self._render_vertical(painter, w, h, active_indices, labels, db_min, db_max, m)
        else:
            self._render_horizontal(painter, w, h, active_indices, labels, db_min, db_max, m)

    def _render_vertical(self, painter, w, h, active_indices, labels, db_min, db_max, m):
        n_groups = len(active_indices)
        group_gap = 6
        lbl_h = 16
        val_h = 16
        bar_y = m + lbl_h
        bar_h = max(10, h - bar_y - val_h - m - 12) # Reserved space for mode at bottom
        
        # Total available width for bars
        avail_w = w - m*2 - group_gap * (n_groups - 1)
        group_w = avail_w / n_groups
        
        for idx, meter_idx in enumerate(active_indices):
            gx = m + idx * (group_w + group_gap)
            
            # Label
            painter.setFont(self.get_responsive_font(Fonts.small, group_w, lbl_h, labels[meter_idx]))
            self.draw_text_badge(painter, QRectF(gx, m, group_w, lbl_h), Qt.AlignCenter, labels[meter_idx], QColor(Colors.TEXT_DIM))
            
            # Get values
            if meter_idx == 0:   vals, raw = self._disp_m, (self._lufs_m if self._mode == "LUFS" else self._rms_m)
            elif meter_idx == 1: vals, raw = self._disp_st, (self._lufs_st if self._mode == "LUFS" else self._rms_st)
            else:                vals, raw = self._disp_peak, self._peak
            
            # Create Vertical Gradient
            grad = QLinearGradient(0, bar_y + bar_h, 0, bar_y)
            grad.setColorAt(0.0, QColor(Colors.METER_LOW))
            grad.setColorAt(0.7, QColor(Colors.METER_LOW))
            grad.setColorAt(0.85, QColor(Colors.METER_MID))
            grad.setColorAt(1.0, QColor(Colors.METER_HIGH))

            # Draw Bars
            if self._show_all_channels:
                ch_count = self.audio_engine.channels
                bw = (group_w - (ch_count-1)*2) / ch_count
                for ch in range(ch_count):
                    bx = gx + ch * (bw + 2)
                    painter.fillRect(QRectF(bx, bar_y, bw, bar_h), QColor(Colors.BG_INPUT))
                    f = np.clip((vals[ch] - db_min) / (db_max - db_min), 0, 1)
                    if f > 0:
                        painter.fillRect(QRectF(bx, bar_y + bar_h - f * bar_h, bw, f * bar_h), QBrush(grad))
                v_max = np.max(raw)
            else:
                v_avg = np.mean(vals)
                painter.fillRect(QRectF(gx, bar_y, group_w, bar_h), QColor(Colors.BG_INPUT))
                f = np.clip((v_avg - db_min) / (db_max - db_min), 0, 1)
                if f > 0:
                    painter.fillRect(QRectF(gx, bar_y + bar_h - f * bar_h, group_w, f * bar_h), QBrush(grad))
                v_max = np.max(raw)
            
            # Value Badge
            ps_col = self._get_smooth_color(v_max)
            ps = f"{v_max:.0f}" if v_max > -100 else "-∞"
            painter.setFont(self.get_responsive_font(Fonts.value, group_w, val_h, ps))
            self.draw_text_badge(painter, QRectF(gx, bar_y + bar_h + 2, group_w, val_h), Qt.AlignCenter, ps, ps_col)

        # Vertical Mode Indicator (Horizontal strip at bottom)
        mode_rect = QRectF(m, h - 14, w - m*2, 10)
        painter.setFont(self.get_responsive_font(Fonts.small, mode_rect.width(), mode_rect.height(), self._mode))
        self.draw_text_badge(painter, mode_rect, Qt.AlignCenter, self._mode, QColor(Colors.ACCENT), QColor(0, 0, 0, 100))

    def _render_horizontal(self, painter, w, h, active_indices, labels, db_min, db_max, m):
        mode_w = 14
        lbl_w = 38
        val_w = 46
        bar_x = m + mode_w + lbl_w + 6
        bar_w = max(10, w - bar_x - val_w - m - 2)
        
        n_rows = len(active_indices)
        row_gap = 3
        row_h = (h - m*2 - row_gap * (n_rows - 1)) // n_rows
        
        # Draw Vertical Mode Strip
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
            ry = m + idx * (row_h + row_gap)
            
            # Label
            painter.setFont(self.get_responsive_font(Fonts.small, lbl_w, row_h, labels[meter_idx]))
            self.draw_text_badge(painter, QRectF(m + mode_w, ry, lbl_w, row_h), Qt.AlignVCenter | Qt.AlignRight, labels[meter_idx], QColor(Colors.TEXT_DIM))
            
            # Get values
            if meter_idx == 0:   vals, raw = self._disp_m, (self._lufs_m if self._mode == "LUFS" else self._rms_m)
            elif meter_idx == 1: vals, raw = self._disp_st, (self._lufs_st if self._mode == "LUFS" else self._rms_st)
            else:                vals, raw = self._disp_peak, self._peak
            
            # Create Horizontal Gradient
            grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
            grad.setColorAt(0.0, QColor(Colors.METER_LOW))
            grad.setColorAt(0.7, QColor(Colors.METER_LOW))
            grad.setColorAt(0.85, QColor(Colors.METER_MID))
            grad.setColorAt(1.0, QColor(Colors.METER_HIGH))

            # Bars
            if self._show_all_channels:
                ch_count = self.audio_engine.channels
                bh = (row_h - (ch_count-1)*2) / ch_count
                for ch in range(ch_count):
                    by = ry + ch * (bh + 2)
                    painter.fillRect(QRectF(bar_x, by, bar_w, bh), QColor(Colors.BG_INPUT))
                    f = np.clip((vals[ch] - db_min) / (db_max - db_min), 0, 1)
                    if f > 0:
                        painter.fillRect(QRectF(bar_x, by, f * bar_w, bh), QBrush(grad))
                v_max = np.max(raw)
            else:
                v_avg = np.mean(vals)
                painter.fillRect(QRectF(bar_x, ry + 1, bar_w, row_h - 2), QColor(Colors.BG_INPUT))
                f = np.clip((v_avg - db_min) / (db_max - db_min), 0, 1)
                if f > 0:
                    painter.fillRect(QRectF(bar_x, ry + 1, f * bar_w, row_h - 2), QBrush(grad))
                v_max = np.max(raw)
                
            # Value Badge
            ps = f"{v_max:.1f}" if v_max > -100 else "-∞"
            painter.setFont(self.get_responsive_font(Fonts.value, val_w, row_h, ps))
            ps_col = self._get_smooth_color(v_max)
            self.draw_text_badge(painter, QRectF(bar_x + bar_w + 2, ry, val_w, row_h), Qt.AlignVCenter | Qt.AlignRight, ps, ps_col)
