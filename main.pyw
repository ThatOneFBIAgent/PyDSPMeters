"""
PyDSPMeters: Entry Point
Modular real-time audio visualization utility.
"""

from PySide6.QtWidgets import QApplication, QSplashScreen, QLabel
from PySide6.QtCore import Qt, QTimer, QRectF, QPoint
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QFont, QPen, QIcon
import sys
import os
import ctypes
import glob

from app.theme import build_stylesheet, Colors, Fonts, apply_theme

# --- Application Configuration ---
# Set this to the name of your icon file. It will survive Nuitka packaging.
# If left empty, the app will automatically try to find a .ico in its directory.
APP_ICON_NAME = "icon.ico" 
# ---------------------------------

class CustomSplashScreen(QSplashScreen):
    """Splash screen with branding and progress."""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setFixedSize(450, 280)
        self._progress = 0
        self._status = "Initializing core components..."
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center() - self.rect().center())
        
    def set_progress(self, val, status=None):
        self._progress = val
        if status:
            self._status = status
        self.update()

    def paintEvent(self, event):
        with QPainter(self) as p:
            p.setRenderHint(QPainter.Antialiasing)
            
            # Draw background gradient
            rect = self.rect()
            bg_grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            bg_grad.setColorAt(0, QColor(Colors.BG_DARKEST))
            bg_grad.setColorAt(1, QColor("#0c0c1a")) # Slightly lighter corner
            p.fillRect(rect, bg_grad)
            
            # Subtle accent glow / border
            p.setPen(QPen(QColor(Colors.BORDER), 1))
            p.drawRect(rect.adjusted(0, 0, -1, -1))
            
            # Glow behind logo
            glow = QLinearGradient(rect.center() - QPoint(180, 0), rect.center() + QPoint(180, 0))
            glow_col = QColor(Colors.ACCENT)
            glow_col.setAlpha(35)
            glow.setColorAt(0, Qt.transparent)
            glow.setColorAt(0.5, glow_col)
            glow.setColorAt(1, Qt.transparent)
            p.fillRect(rect.adjusted(0, 105, 0, -115), glow)

            # Logo Text
            p.setPen(QColor(Colors.ACCENT))
            f = Fonts.header()
            f.setPointSize(32)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 4)
            f.setWeight(QFont.Black)
            p.setFont(f)
            p.drawText(rect.adjusted(0, -25, 0, 0), Qt.AlignCenter, "PYDSPMETERS")
            
            # Subtitle
            p.setPen(QColor(Colors.TEXT_DIM))
            f.setPointSize(10)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 1)
            f.setBold(False)
            f.setWeight(QFont.Normal)
            p.setFont(f)
            p.drawText(rect.adjusted(0, 30, 0, 0), Qt.AlignCenter, "MODULAR AUDIO ANALYZER")
            
            # Version
            f.setPointSize(8)
            p.setFont(f)
            p.setPen(QColor(Colors.BORDER_ACCENT))
            p.drawText(rect.adjusted(0, 0, -15, -15), Qt.AlignBottom | Qt.AlignRight, "v1.0.3")

            # Status (placed ABOVE progress bar)
            p.setPen(QColor(Colors.TEXT_DIM))
            f.setPointSize(9)
            p.setFont(f)
            p.drawText(rect.adjusted(50, 0, -50, -65), Qt.AlignBottom | Qt.AlignLeft, self._status)
            
            # Progress bar container
            bar_rect = QRectF(50, 230, 350, 6)
            p.setBrush(QColor(Colors.BG_DARK))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(bar_rect, 3, 3)
            
            # Progress bar fill
            if self._progress > 0:
                progress_rect = QRectF(50, 230, 350 * (self._progress / 100), 6)
                grad = QLinearGradient(progress_rect.topLeft(), progress_rect.topRight())
                grad.setColorAt(0, QColor(Colors.ACCENT_DIM))
                grad.setColorAt(1, QColor(Colors.ACCENT))
                p.setBrush(grad)
                p.drawRoundedRect(progress_rect, 3, 3)


def main():
    # Handle Ctrl+C (SIGINT)
    import signal, sys
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("PyDSPMeters")
    
    # Override default Python taskbar icon if a .ico is found or in settings
    if sys.platform == "win32":
        try:
            myappid = 'pydspmeters.app.1.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
            
    # Try to load icon robustly (survives Nuitka packaging)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = ""
    
    if APP_ICON_NAME:
        target_path = os.path.join(base_dir, APP_ICON_NAME)
        if os.path.exists(target_path):
            icon_path = target_path
            
    if not icon_path:
        icos = glob.glob(os.path.join(base_dir, "*.ico"))
        if icos:
            icon_path = icos[0]
            
    if icon_path and os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Initialize theme
    apply_theme("Midnight")
    
    # Show Splash immediately
    splash = CustomSplashScreen()
    splash.show()
    app.processEvents()
    
    # Now do heavier imports
    splash.set_progress(20, "Loading UI modules...")
    app.processEvents()
    from app.window_manager import MainWindow
    
    splash.set_progress(40, "Initializing Audio Engine...")
    app.processEvents()
    from app.audio_engine import AudioEngine
    engine = AudioEngine(sample_rate=44100, block_size=1024)

    splash.set_progress(60, "Restoring workspace...")
    app.processEvents()
    
    app.setStyleSheet(build_stylesheet())
    window = MainWindow(engine, splash=splash)
    
    splash.set_progress(90, "Starting real-time streams...")
    app.processEvents()

    # Wait for window to be ready
    def finalize():
        splash.set_progress(100, "Ready")
        splash.finish(window)
        window.show()

    QTimer.singleShot(500, finalize)

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        import os
        os._exit(0)
