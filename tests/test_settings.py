import json
import os
import pytest
from app.settings import SettingsManager

def test_get_settings_path():
    path = SettingsManager.get_settings_path()
    assert path.endswith("settings.json")
    assert "PyDSPMeters" in path

def test_save_and_load_settings(tmp_path, monkeypatch):
    # Mock get_settings_path to use a temporary directory
    test_file = tmp_path / "test_settings.json"
    monkeypatch.setattr(SettingsManager, "get_settings_path", lambda: str(test_file))

    settings = {"theme": "Abyss", "gain": 2.0}
    SettingsManager.save(settings)
    
    assert test_file.exists()
    
    loaded = SettingsManager.load()
    assert loaded == settings

def test_load_non_existent_file(tmp_path, monkeypatch):
    test_file = tmp_path / "missing.json"
    monkeypatch.setattr(SettingsManager, "get_settings_path", lambda: str(test_file))
    
    loaded = SettingsManager.load()
    assert loaded == {}

def test_load_corrupt_json(tmp_path, monkeypatch):
    test_file = tmp_path / "corrupt.json"
    test_file.write_text("invalid json {")
    monkeypatch.setattr(SettingsManager, "get_settings_path", lambda: str(test_file))
    
    loaded = SettingsManager.load()
    assert loaded == {}

def test_save_and_load_profile_file(tmp_path):
    profile_file = tmp_path / "profiles" / "stream.json"
    settings = {
        "window": {"width": 420, "height": 900},
        "modules": [{"key": "vu_meter", "config": {"style": 2}}],
    }

    SettingsManager.save_to_file(profile_file, settings)

    assert profile_file.exists()
    assert SettingsManager.load_from_file(profile_file) == settings
