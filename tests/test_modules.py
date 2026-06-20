import pytest
import numpy as np
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
from app.modules.loudness_meter import LoudnessModule

# Create a global QApplication for tests that need it
app = QApplication.instance() or QApplication([])

class MockEngine:
    def __init__(self):
        self.sample_rate = 44100
        self.channels = 2
        self.data_ready = MagicMock()

def test_loudness_module_mode_switch():
    engine = MockEngine()
    module = LoudnessModule(engine)
    
    assert module._mode == "LUFS"
    assert "LUFS" in module.header._title.text()
    
    module._set_mode("RMS")
    assert module._mode == "RMS"
    assert "RMS" in module.header._title.text()

def test_loudness_module_processing():
    engine = MockEngine()
    module = LoudnessModule(engine)
    
    # Simulate loud stereo sine wave
    t = np.arange(1024) / 44100.0
    tone = np.sin(2 * np.pi * 1000 * t).astype(np.float32)
    stereo = np.column_stack([tone, tone])
    
    module.on_audio_data(stereo)
    
    # Peak should be near 0 dBFS
    assert np.all(module._peak > -1.0)
    # LUFS should be around -3.0 dB for a full scale sine
    assert np.all(module._lufs_m > -5.0)

def test_loudness_module_uses_combined_lufs_for_stereo_display():
    engine = MockEngine()
    module = LoudnessModule(engine)
    module._reactivity = "Instant"
    
    t = np.arange(44100) / 44100.0
    tone = np.sin(2 * np.pi * 1000 * t).astype(np.float32)
    stereo = np.column_stack([tone, tone])
    
    module.on_audio_data(stereo)
    
    assert module._lufs_m_combined > module._lufs_m[0] + 2.5
    vals, raw = module._meter_values(0, per_channel=False)
    assert raw[0] == module._lufs_m_combined
    assert vals[0] == module._disp_m_combined

def test_loudness_module_settings_persistence():
    engine = MockEngine()
    module = LoudnessModule(engine)
    
    # Mock settings
    settings = {
        "mode": "RMS",
        "orientation": "Vertical",
        "show_peak": False
    }
    
    module.apply_settings(settings)
    assert module._mode == "RMS"
    assert module._orientation == "Vertical"
    assert module._show_peak == False
    
    # Save settings
    saved = module.get_settings()
    assert saved["mode"] == "RMS"
    assert saved["orientation"] == "Vertical"
    assert saved["show_peak"] == False
