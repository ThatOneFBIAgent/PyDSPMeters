import json
import os
import sys

SETTINGS_FILE = "settings.json"

class SettingsManager:
    """Manages application settings persistence using a JSON file."""
    
    @staticmethod
    def get_settings_path():
        # If running as a bundled executable, put settings next to the exe
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, SETTINGS_FILE)

    @classmethod
    def load(cls):
        path = cls.get_settings_path()
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading settings: {e}")
        return {}

    @classmethod
    def save(cls, settings):
        path = cls.get_settings_path()
        try:
            with open(path, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")
