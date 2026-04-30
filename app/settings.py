import json
import os
import sys

SETTINGS_FILE = "settings.json"

class SettingsManager:
    """Manages application settings persistence using a JSON file."""
    
    @staticmethod
    def get_settings_path():
        """
        Determines the correct path for settings.json in both dev and compiled modes.
        
        - Dev mode:   <project_root>/settings.json  (next to main.py)
        - Compiled:   <exe_directory>/settings.json  (next to the .exe)
        """
        # Check for Nuitka compiled environment
        # __compiled__ is injected by Nuitka at build time
        is_compiled = "__compiled__" in dir(__builtins__) or hasattr(__builtins__, "__compiled__")
        
        if is_compiled:
            # sys.argv[0] is the most reliable way to get the .exe's location,
            # regardless of CWD or how the process was launched
            base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        else:
            # Dev mode: walk up from this file (app/settings.py) to project root
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        settings_path = os.path.join(base_path, SETTINGS_FILE)
        return settings_path

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
