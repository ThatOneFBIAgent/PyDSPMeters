"""
PyDSPMeters: Entry Point
Modular real-time audio visualization utility.
"""

import sys
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.theme import build_stylesheet
from app.audio_engine import AudioEngine
from app.window_manager import MainWindow


def main():
    # Handle Ctrl+C (SIGINT)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("PyDSPMeters")
    app.setStyleSheet(build_stylesheet())
    app.setQuitOnLastWindowClosed(True)
    
    # Create audio engine
    engine = AudioEngine(sample_rate=44100, block_size=1024)

    # Create main window
    window = MainWindow(engine)
    window.show()

    # Start audio capture with default device
    engine.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        import os
        os._exit(0)
