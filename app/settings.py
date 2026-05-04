import json
import os
import sys

SETTINGS_FILE = "settings.json"
APP_NAME = "PyDSPMeters"


class SettingsManager:
    """Manages application settings persistence using a JSON file."""

    @staticmethod
    def get_app_data_dir():
        """
        Returns the platform-appropriate config directory for the application.
        """
        if sys.platform == "win32":
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
        elif sys.platform == "darwin":
            base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
        else:
            base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")

        app_dir = os.path.join(base, APP_NAME)
        os.makedirs(app_dir, exist_ok=True)
        return app_dir

    @classmethod
    def get_settings_path(cls):
        return os.path.join(cls.get_app_data_dir(), SETTINGS_FILE)

    @classmethod
    def load(cls):
        path = cls.get_settings_path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading settings: {e}")
        return {}

    @classmethod
    def save(cls, settings):
        path = cls.get_settings_path()
        try:
            with open(path, "w") as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")