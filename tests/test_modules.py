import pytest
import numpy as np
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect
from app.modules.loudness_meter import LoudnessModule
from app.modules.vu_meter import VUMeterModule
from app.modules.oscilloscope import OscilloscopeModule
from app.modules.spectrogram import SpectrogramModule
from app.modules.waveform import WaveformModule
from app.modules.stereometer import StereometerModule
from app.window_manager import MainWindow

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

def test_vu_clip_led_follows_vu_zero_not_sample_peak():
    engine = MockEngine()
    module = VUMeterModule(engine)
    module._rise_coeff = 1.0

    t = np.arange(4096) / 44100.0
    tone = np.sin(2 * np.pi * 1000 * t).astype(np.float32)
    stereo = np.column_stack([tone, tone])

    module.on_audio_data(stereo)

    assert module._needle_l < 0.0
    assert module._needle_r < 0.0
    assert module._peak_lit_l
    assert module._peak_lit_r
    assert not module._clip_lit_l
    assert not module._clip_lit_r

def test_vu_clip_led_lights_at_vu_zero():
    engine = MockEngine()
    module = VUMeterModule(engine)
    module._rise_coeff = 1.0

    stereo = np.ones((1024, 2), dtype=np.float32)

    module.on_audio_data(stereo)

    assert module._needle_l == 0.0
    assert module._needle_r == 0.0
    assert module._clip_lit_l
    assert module._clip_lit_r

def test_oscilloscope_buffer_updates_in_place():
    engine = MockEngine()
    module = OscilloscopeModule(engine)
    left_id = id(module._waveform_l)
    right_id = id(module._waveform_r)

    samples = np.column_stack([
        np.linspace(-1.0, 1.0, 128, dtype=np.float32),
        np.linspace(1.0, -1.0, 128, dtype=np.float32),
    ])

    module.on_audio_data(samples)

    assert id(module._waveform_l) == left_id
    assert id(module._waveform_r) == right_id
    np.testing.assert_allclose(module._waveform_l[-128:], samples[:, 0])
    np.testing.assert_allclose(module._waveform_r[-128:], samples[:, 1])

def test_oscilloscope_auto_gain_expands_quiet_traces():
    engine = MockEngine()
    module = OscilloscopeModule(engine)
    quiet = np.full(256, 0.1, dtype=np.float32)

    module._set_gain_mode("Auto Fit")
    auto_gain = module._get_trace_gain(quiet, trace_key=0)
    module._set_gain_mode("Fixed", 2.0)
    fixed_gain = module._get_trace_gain(quiet, trace_key=0)

    assert auto_gain > fixed_gain
    assert fixed_gain == 2.0

def test_waveform_auto_gain_expands_quiet_traces():
    engine = MockEngine()
    module = WaveformModule(engine)
    quiet_max = np.full(128, 0.1, dtype=np.float32)
    quiet_min = np.full(128, -0.1, dtype=np.float32)

    module._set_gain_mode("Auto Fit")
    auto_gain = module._get_trace_gain(quiet_max, quiet_min, trace_key=0)
    module._set_gain_mode("Fixed", 2.0)
    fixed_gain = module._get_trace_gain(quiet_max, quiet_min, trace_key=0)

    assert auto_gain > fixed_gain
    assert fixed_gain == 2.0

def test_stereometer_auto_zoom_expands_quiet_phase_cloud():
    engine = MockEngine()
    module = StereometerModule(engine)
    left = np.full(512, 0.05, dtype=np.float32)
    right = np.full(512, 0.04, dtype=np.float32)

    module._update_auto_zoom(left, right)

    assert module._effective_zoom() > 1.0

def test_appbar_fullscreen_callback_restores_with_forced_repair():
    class DummyWindow:
        def __init__(self):
            self._appbar_fullscreen_active = False
            self.topmost_calls = []
            self.repair_calls = []

        def _set_appbar_topmost(self, enabled):
            self.topmost_calls.append(enabled)

        def _schedule_appbar_repair(self, delay=250, force_register=False):
            self.repair_calls.append((delay, force_register))

    dummy = DummyWindow()

    MainWindow._handle_appbar_callback(dummy, 2, 1)
    MainWindow._handle_appbar_callback(dummy, 2, 0)

    assert dummy.topmost_calls == [False, True]
    assert dummy.repair_calls == [(1200, True)]
    assert not dummy._appbar_fullscreen_active

def test_appbar_geometry_health_detects_moved_window():
    class DummyWindow:
        def __init__(self):
            self._appbar_active = True
            self._appbar_last_rect = QRect(100, 0, 40, 600)

        def geometry(self):
            return QRect(10, 0, 40, 600)

    assert not MainWindow._appbar_geometry_matches(DummyWindow())

def test_appbar_work_area_health_detects_lost_reservation():
    class DummyWindow:
        def __init__(self, work):
            self._appbar_edge = "right"
            self._appbar_last_rect = QRect(1880, 0, 40, 1080)
            self._work = work

        def _win32_work_area(self):
            return self._work

    reserved = DummyWindow(QRect(0, 0, 1880, 1080))
    lost = DummyWindow(QRect(0, 0, 1920, 1080))

    assert MainWindow._appbar_work_area_reserved(reserved)
    assert not MainWindow._appbar_work_area_reserved(lost)

def test_spectrogram_vertical_cache_rotates_frequency_axis():
    engine = MockEngine()
    module = SpectrogramModule(engine)
    module._buffer_data.fill(0)
    module._buffer_data[module._display_h - 1, 0] = [1, 2, 3]
    module._col_idx = 0

    module._rebuild_render_images()

    assert module._ordered_img.width() == module._history_len
    assert module._ordered_img.height() == module._display_h
    assert module._vertical_img.width() == module._display_h
    assert module._vertical_img.height() == module._history_len
    assert module._vertical_data.shape == (module._history_len, module._display_h, 3)
    np.testing.assert_array_equal(module._vertical_data[0, 0], [1, 2, 3])
