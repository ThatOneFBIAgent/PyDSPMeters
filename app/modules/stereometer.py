"""
Stereometer Module: Lissajous / Linear / Scaled stereo display with correlation meter.
"""

import numpy as np
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap
from PySide6.QtCore import Qt, QPointF, QRectF
from scipy.signal import get_window

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
        self._halved_view = False
        self._minimal_mode = False
        self._corr_pos = "Bottom"
        
        self._width_gain = 1.0 
        self._persistence = 0.5 
        self._max_dots = 1024
        self._window_alpha = 0.1 
        self._window_cache = {}
        self._buffer = None
        
        self._left = np.zeros(1024, dtype=np.float32)
        self._right = np.zeros(1024, dtype=np.float32)
        self._corr = 0.0
        self._mb_corr = {"low": 0.0, "mid": 0.0, "high": 0.0, "overall": 0.0}
        self._multiband = MultiBandFilter(sample_rate=audio_engine.sample_rate)
        self._corr_peak = 0.0
        self._mb_corr_peak = {}
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
            "width_gain": self._width_gain,
            "persistence": self._persistence,
            "max_dots": self._max_dots,
            "show_labels": self._show_labels,
            "minimal_mode": self._minimal_mode,
            "halved_view": self._halved_view,
            "corr_pos": self._corr_pos
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
        self._zoom = float(settings.get("zoom", self._zoom))
        self._width_gain = float(settings.get("width_gain", self._width_gain))
        self._persistence = float(settings.get("persistence", self._persistence))
        self._max_dots = int(settings.get("max_dots", self._max_dots))
        self._show_labels = bool(settings.get("show_labels", self._show_labels))
        self._minimal_mode = bool(settings.get("minimal_mode", self._minimal_mode))
        self._halved_view = bool(settings.get("halved_view", self._halved_view))
        self._corr_pos = str(settings.get("corr_pos", self._corr_pos))

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
        for z in [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0]:
            a = zm.addAction(f"{z}x")
            a.setCheckable(True)
            a.setChecked(abs(z - self._zoom) < 0.01)
            a.triggered.connect(lambda checked, v=z: (setattr(self, "_zoom", v), self.canvas.update()))
            zg.addAction(a)

        wm = menu.addMenu("Width Gain")
        wg = QActionGroup(self)
        for w in [1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0]:
            a = wm.addAction(f"{w}x")
            a.setCheckable(True)
            a.setChecked(abs(w - self._width_gain) < 0.01)
            a.triggered.connect(lambda checked, v=w: (setattr(self, "_width_gain", v), self.canvas.update()))
            wg.addAction(a)

        pm = menu.addMenu("Correlation Smoothing")
        pg = QActionGroup(self)
        for p, label in [(0.0, "None (Fast)"), (0.5, "Natural"), (0.8, "Smooth"), (0.95, "Slow")]:
            a = pm.addAction(label)
            a.setCheckable(True)
            a.setChecked(abs(p - self._persistence) < 0.01)
            a.triggered.connect(lambda checked, v=p: (setattr(self, "_persistence", v), self.canvas.update()))
            pg.addAction(a)
            
        sm = menu.addMenu("Max Dots (Density)")
        sg = QActionGroup(self)
        for d in [256, 512, 1024, 2048, 4096, 8192]:
            a = sm.addAction(str(d))
            a.setCheckable(True)
            a.setChecked(d == self._max_dots)
            a.triggered.connect(lambda checked, v=d: (setattr(self, "_max_dots", v), self.canvas.update()))
            sg.addAction(a)

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
            
        cpm = menu.addMenu("Correlation Position")
        cpg = QActionGroup(self)
        for p in ["Top", "Bottom", "Left", "Right"]:
            a = cpm.addAction(p)
            a.setCheckable(True)
            a.setChecked(p == self._corr_pos)
            a.triggered.connect(lambda checked, t=p: setattr(self, "_corr_pos", t))
            cpg.addAction(a)
            
        cpm.setEnabled(not self._minimal_mode)
        crm.setEnabled(not self._minimal_mode)
            
        a = menu.addAction("Minimal Mode")
        a.setCheckable(True)
        a.setChecked(self._minimal_mode)
        a.triggered.connect(lambda checked: (setattr(self, "_minimal_mode", checked), self.canvas.update()))

        a = menu.addAction("Show Labels")
        a.setCheckable(True)
        a.setChecked(self._show_labels)
        a.triggered.connect(lambda checked: (setattr(self, "_show_labels", checked), self.canvas.update()))

        a = menu.addAction("Halved View")
        a.setCheckable(True)
        a.setChecked(self._halved_view)
        a.triggered.connect(lambda checked: (setattr(self, "_halved_view", checked), self.canvas.update()))

    def on_audio_data(self, data: np.ndarray):
        n = len(data)
        l_raw = data[:, 0].copy()
        r_raw = data[:, 1].copy() if data.shape[1] > 1 else data[:, 0].copy()
        
        # 1. Apply Width Gain (Mid/Side processing)
        if self._width_gain != 1.0:
            mid = (l_raw + r_raw) * 0.5
            side = (l_raw - r_raw) * 0.5 * self._width_gain
            l_proc = mid + side
            r_proc = mid - side
        else:
            l_proc, r_proc = l_raw, r_raw

        # 2. Apply Custom Tukey Window (Very thin margin FFT window style)
        # This prevents sharp jumps at the edges of the buffer
        cache_key = (n, self._window_alpha)
        if cache_key in self._window_cache:
            win = self._window_cache[cache_key]
        else:
            win = get_window(('tukey', self._window_alpha), n, fftbins=False).astype(np.float32)
            self._window_cache[cache_key] = win
            
        self._left = (l_proc * win)
        self._right = (r_proc * win)
        
        # 3. Smoothed Correlation
        new_corr = correlation(l_raw, r_raw)
        alpha = 1.0 - self._persistence
        if self._persistence == 0: alpha = 1.0
        
        self._corr = self._corr * (1.0 - alpha) + new_corr * alpha
        # Peak/Ghost decay
        self._corr_peak = max(abs(self._corr_peak) * 0.95, abs(self._corr)) * np.sign(self._corr if abs(self._corr) > abs(self._corr_peak) * 0.95 else self._corr_peak)
        # Simplify peak logic: just a slow-following "shadow"
        if not hasattr(self, "_corr_ghost"): self._corr_ghost = self._corr
        self._corr_ghost = self._corr_ghost * 0.9 + self._corr * 0.1
        
        if self._corr_mode == "Multi-Band":
            new_mb = multiband_correlation(
                l_raw, r_raw, self.audio_engine.sample_rate)
            if not hasattr(self, "_mb_corr_ghost"): self._mb_corr_ghost = {}
            for k in new_mb:
                old = self._mb_corr.get(k, 0.0)
                self._mb_corr[k] = old * (1.0 - alpha) + new_mb[k] * alpha
                old_g = self._mb_corr_ghost.get(k, self._mb_corr[k])
                self._mb_corr_ghost[k] = old_g * 0.92 + self._mb_corr[k] * 0.08

    def _render(self, painter, w, h):
        corr_size = 28 if not self._minimal_mode else 0
        pos = self._corr_pos
        
        if self._minimal_mode:
            scope_rect = QRectF(0, 0, w, h)
            corr_rect = QRectF(0, 0, 0, 0)
        elif pos == "Bottom":
            scope_rect = QRectF(0, 0, w, h - corr_size)
            corr_rect = QRectF(0, h - corr_size, w, corr_size)
        elif pos == "Top":
            scope_rect = QRectF(0, corr_size, w, h - corr_size)
            corr_rect = QRectF(0, 0, w, corr_size)
        elif pos == "Left":
            scope_rect = QRectF(corr_size, 0, w - corr_size, h)
            corr_rect = QRectF(0, 0, corr_size, h)
        else: # Right
            scope_rect = QRectF(0, 0, w - corr_size, h)
            corr_rect = QRectF(w - corr_size, 0, corr_size, h)

        sw, sh = scope_rect.width(), scope_rect.height()
        sx, sy_off = scope_rect.x(), scope_rect.y()
        
        cx = sx + sw / 2
        
        # Reserve space for labels if they are showing
        margin = 18 if self._show_labels else 4
        
        if self._halved_view:
            cy = sy_off + sh
            radius = min(sw / 2 - margin, sh - margin)
        else:
            cy = sy_off + sh / 2
            radius = min(sw / 2 - margin, sh / 2 - margin)

        # 1. Base Grid / Crosshair
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

        # 3. Trace (Drawn directly, no persistence)
        left, right = self._left, self._right
        if self._color_mode.startswith("Multi-Band"):
            low_l, mid_l, high_l = self._multiband.split(left)
            low_r, mid_r, high_r = self._multiband.split(right)
            cols = ["#FF3333", "#33FF33", "#3388FF"] if self._color_mode == "Multi-Band (RGB)" else [Colors.BAND_LOW, Colors.BAND_MID, Colors.BAND_HIGH]
            for bl, br, col in zip([low_l, mid_l, high_l], [low_r, mid_r, high_r], cols):
                self._draw_trace(painter, bl, br, cx, cy, radius, QColor(col), 160)
        else:
            col = QColor(Colors.ACCENT)
            self._draw_trace(painter, left, right, cx, cy, radius, col, 200)

        # Labels
        if self._show_labels:
            painter.setFont(Fonts.small())
            painter.setPen(QColor(Colors.TEXT_DIM))
            if self._halved_view:
                if self._display_mode == "Vectorscope":
                    painter.setFont(self.get_responsive_font(Fonts.small, 12, 12, "M"))
                    painter.drawText(QRectF(cx - 6, sy_off + 2, 12, 12), Qt.AlignCenter, "M")
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
                    painter.drawText(QRectF(cx - 10, cy + radius + 2, 20, 14), Qt.AlignCenter, "R")
                    painter.setFont(self.get_responsive_font(Fonts.small, 16, 14, "L"))
                    painter.drawText(QRectF(cx - radius - 18, cy - 7, 16, 14), Qt.AlignCenter, "L")
                    painter.setFont(self.get_responsive_font(Fonts.small, 16, 14, "R"))
                    painter.drawText(QRectF(cx + radius + 2, cy - 7, 16, 14), Qt.AlignCenter, "R")

        # Correlation bar
        if not self._minimal_mode:
            is_vert_corr = pos in ["Left", "Right"]
            margin = 16 if is_vert_corr else 12
            inner_m = 6
            
            bx, by, bw, bh = corr_rect.x(), corr_rect.y(), corr_rect.width(), corr_rect.height()
            
            if is_vert_corr:
                bar_rect = QRectF(bx + inner_m, by + margin, bw - inner_m * 2, bh - margin * 2)
            else:
                bar_rect = QRectF(bx + margin, by + inner_m, bw - margin * 2, bh - inner_m * 2)
                
            painter.fillRect(bar_rect, QColor(Colors.BG_INPUT))
            
            if is_vert_corr:
                mid = bar_rect.y() + bar_rect.height() / 2
                painter.setPen(QPen(QColor(Colors.GRID_BRIGHT), 1))
                painter.drawLine(int(bar_rect.x()), int(mid), int(bar_rect.x() + bar_rect.width()), int(mid))
            else:
                mid = bar_rect.x() + bar_rect.width() / 2
                painter.setPen(QPen(QColor(Colors.GRID_BRIGHT), 1))
                painter.drawLine(int(mid), int(bar_rect.y()), int(mid), int(bar_rect.y() + bar_rect.height()))

            if self._corr_mode == "Single-Band":
                val = self._corr
                ghost = getattr(self, "_corr_ghost", val)
                
                # Ghost
                col_g = QColor(Colors.ACCENT_DIM); col_g.setAlpha(100)
                painter.setBrush(QBrush(col_g)); painter.setPen(Qt.NoPen)
                if is_vert_corr:
                    py = bar_rect.y() + bar_rect.height() * (1.0 - (ghost + 1) / 2.0)
                    painter.drawRoundedRect(QRectF(bar_rect.x() + 2, py - 2, bar_rect.width() - 4, 4), 1, 1)
                else:
                    px = bar_rect.x() + (ghost + 1) / 2 * bar_rect.width()
                    painter.drawRoundedRect(QRectF(px - 2, bar_rect.y() + 2, 4, bar_rect.height() - 4), 1, 1)

                # Active
                col = QColor(Colors.GREEN) if val > 0 else QColor(Colors.RED)
                painter.setBrush(QBrush(col)); painter.setPen(Qt.NoPen)
                if is_vert_corr:
                    py = bar_rect.y() + bar_rect.height() * (1.0 - (val + 1) / 2.0)
                    painter.drawRoundedRect(QRectF(bar_rect.x() + 1, py - 3, bar_rect.width() - 2, 6), 2, 2)
                else:
                    px = bar_rect.x() + (val + 1) / 2 * bar_rect.width()
                    painter.drawRoundedRect(QRectF(px - 3, bar_rect.y() + 1, 6, bar_rect.height() - 2), 2, 2)
            else:
                n_bands = 4
                bands = [("low", Colors.BAND_LOW), ("mid", Colors.BAND_MID), ("high", Colors.BAND_HIGH), ("overall", Colors.ACCENT)]
                
                sub_bw = bar_rect.width() / n_bands
                for j, (name, col_hex) in enumerate(bands):
                    val = self._mb_corr.get(name, 0.0)
                    ghost = getattr(self, "_mb_corr_ghost", {}).get(name, val)
                    sub_x = bar_rect.x() + j * sub_bw
                    
                    painter.fillRect(QRectF(sub_x + 1, bar_rect.y(), sub_bw - 2, bar_rect.height()), QColor(Colors.BG_DARKEST))
                    
                    mid_y = bar_rect.y() + bar_rect.height() / 2
                    painter.setPen(QPen(QColor(Colors.GRID), 0.5))
                    painter.drawLine(int(sub_x + 1), int(mid_y), int(sub_x + sub_bw - 1), int(mid_y))
                    
                    # Ghost
                    col_g = QColor(col_hex); col_g.setAlpha(80)
                    painter.setBrush(QBrush(col_g)); painter.setPen(Qt.NoPen)
                    py_g = bar_rect.y() + bar_rect.height() * (1.0 - (ghost + 1) / 2.0)
                    painter.drawRect(QRectF(sub_x + 2, py_g - 1, sub_bw - 4, 2))

                    # Active
                    painter.setBrush(QBrush(QColor(col_hex)))
                    py = bar_rect.y() + bar_rect.height() * (1.0 - (val + 1) / 2.0)
                    ind_w = max(2.0, sub_bw - 4)
                    ind_x = sub_x + (sub_bw - ind_w) / 2
                    painter.drawRoundedRect(QRectF(ind_x, py - 2, ind_w, 4), 1, 1)

            painter.setPen(QColor(Colors.TEXT_DIM))
            # Consistent Labels for Vertical Scale (+1 top, -1 bottom)
            painter.setFont(self.get_responsive_font(Fonts.small, bw if is_vert_corr else 20, 14, "+1"))
            if is_vert_corr:
                painter.drawText(QRectF(bx, bar_rect.y() - 14, bw, 14), Qt.AlignCenter, "+1")
                painter.drawText(QRectF(bx, bar_rect.y() + bar_rect.height(), bw, 14), Qt.AlignCenter, "-1")
            else:
                # Labels at the ends of the horizontal stretch (but still referring to the vertical scale of the segments)
                painter.drawText(QRectF(bx, bar_rect.y() - 14, 20, 14), Qt.AlignLeft, "+1")
                painter.drawText(QRectF(bx + bw - 20, bar_rect.y() - 14, 20, 14), Qt.AlignRight, "+1")
                painter.drawText(QRectF(bx, bar_rect.y() + bh, 20, 14), Qt.AlignLeft, "-1")
                painter.drawText(QRectF(bx + bw - 20, bar_rect.y() + bh, 20, 14), Qt.AlignRight, "-1")

    def _draw_trace(self, painter, left, right, cx, cy, radius, color, alpha):
        n = len(left)
        step = max(1, n // self._max_dots)
        
        l_seg = left[::step] * self._zoom
        r_seg = right[::step] * self._zoom

        painter.save()
        painter.setOpacity(alpha / 255.0)

        if self._display_mode == "Vectorscope":
            # 1. Vectorscope (Point Cloud) - Shows Stereo Density
            dx = (l_seg - r_seg) * 0.5
            dy = (l_seg + r_seg) * 0.5
            
            # Limiting to Guide Map (Default to Rhombus even if None)
            if self._guide_mode == "Circle":
                mag = np.sqrt(dx**2 + dy**2)
                mask = mag > 1.0
                dx[mask] /= mag[mask]
                dy[mask] /= mag[mask]
            else:
                # Rhombus is the standard M/S boundary
                mag = np.abs(dx) + np.abs(dy)
                mask = mag > 1.0
                dx[mask] /= mag[mask]
                dy[mask] /= mag[mask]
            
            xs = cx + dx * radius
            ys = cy - dy * radius
            
            points = [QPointF(xs[i], ys[i]) for i in range(len(xs))]
            if not points: 
                painter.restore()
                return
            
            # Draw a slight glow/blur by drawing multiple times
            painter.setPen(QPen(QColor(color), 2.5))
            painter.setOpacity(alpha / 255.0 * 0.3)
            painter.drawPoints(points)
            
            painter.setPen(QPen(QColor(color), 1.0))
            painter.setOpacity(alpha / 255.0)
            painter.drawPoints(points)
            
        else:
            # 2. Lissajous (Polyline) - Shows Phase Curves
            dx = right[::step] * self._zoom
            dy = left[::step] * self._zoom
            
            # Limiting to Guide Map (Default to Rhombus even if None)
            if self._guide_mode == "Circle":
                mag = np.sqrt(dx**2 + dy**2)
                mask = mag > 1.0
                dx[mask] /= mag[mask]
                dy[mask] /= mag[mask]
            else:
                # Square/Rhombus boundary
                mag = np.abs(dx) + np.abs(dy)
                mask = mag > 1.0
                dx[mask] /= mag[mask]
                dy[mask] /= mag[mask]
            
            xs = cx + dx * radius
            ys = cy - dy * radius
            
            points = [QPointF(xs[i], ys[i]) for i in range(len(xs))]
            if len(points) < 2: 
                painter.restore()
                return
            
            # Glow
            pen = QPen(QColor(color), 2.0)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.setOpacity(alpha / 255.0 * 0.4)
            painter.drawPolyline(points)
            
            painter.setPen(QPen(QColor(color), 1.0))
            painter.setOpacity(alpha / 255.0)
            painter.drawPolyline(points)
            
        painter.restore()
