import json
import os
import sys
import threading

SETTINGS_FILE = "settings.json"
APP_NAME = "PyDSPMeters"


# Module-level compilation checks to ensure Nuitka catches it
IS_NUITKA = "__compiled__" in globals()
IS_PYINSTALLER = getattr(sys, 'frozen', False)
IS_COMPILED = IS_NUITKA or IS_PYINSTALLER

class SettingsManager:
    """Manages application settings persistence using a JSON file."""

    @staticmethod
    def get_system_app_data_dir():
        """Helper to get the standard OS-specific config directory."""
        if sys.platform == "win32":
            base = os.environ.get("APPDATA")
            if not base or not os.path.isabs(base):
                base = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
        elif sys.platform == "darwin":
            base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
        else:
            base = os.environ.get("XDG_CONFIG_HOME")
            if not base or not os.path.isabs(base):
                base = os.path.join(os.path.expanduser("~"), ".config")
                
        return os.path.join(base, APP_NAME)

    @staticmethod
    def get_app_data_dir():
        """
        Returns the appropriate config directory.
        Defaults to AppData/Roaming, but if the app is run from a USB drive
        or if a settings.json already exists next to the .exe, it uses portable mode.
        """
        app_dir = None
        
        if IS_COMPILED:
            if IS_PYINSTALLER:
                exe_dir = os.path.dirname(os.path.realpath(sys.executable))
            else:
                exe_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
                
            # Check if we should use portable mode
            is_portable = False
            
            # 1. Does settings.json already exist here? (User preference)
            if os.path.exists(os.path.join(exe_dir, SETTINGS_FILE)):
                is_portable = True
            else:
                # 2. Is it on a USB/Removable drive?
                if sys.platform == "win32":
                    import ctypes
                    drive = os.path.splitdrive(exe_dir)[0] + "\\"
                    # 2 = DRIVE_REMOVABLE
                    if ctypes.windll.kernel32.GetDriveTypeW(drive) == 2:
                        is_portable = True
                elif sys.platform == "darwin" and exe_dir.startswith("/Volumes/"):
                    is_portable = True
                elif sys.platform.startswith("linux") and (exe_dir.startswith("/media/") or exe_dir.startswith("/run/media/")):
                    is_portable = True
                    
            if is_portable:
                app_dir = exe_dir
            
        if app_dir is not None:
            try:
                os.makedirs(app_dir, exist_ok=True)
                # Ensure the directory is actually writable (e.g. read-only USB)
                if not os.access(app_dir, os.W_OK):
                    raise OSError("Directory is read-only")
            except OSError:
                import logging
                logging.warning(f"Portable directory {app_dir} is not writable. Falling back to system path.")
                app_dir = None

        if app_dir is None:
            app_dir = SettingsManager.get_system_app_data_dir()
            try:
                os.makedirs(app_dir, exist_ok=True)
                if not os.access(app_dir, os.W_OK):
                    raise OSError("System directory is read-only")
            except OSError:
                import tempfile
                app_dir = os.path.join(tempfile.gettempdir(), APP_NAME)
                try:
                    os.makedirs(app_dir, exist_ok=True)
                except OSError:
                    pass  # Absolute worst-case scenario, but we tried, go fix your shit my guy jesus.

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

    _save_lock = threading.Lock()

    @classmethod
    def save(cls, settings):
        """
        Saves settings to disk using a thread-safe, atomic write strategy.
        """
        path = cls.get_settings_path()
        with cls._save_lock:
            try:
                # Save to a temporary file first to prevent corruption if the app crashes during write
                temp_path = path + ".tmp"
                with open(temp_path, "w") as f:
                    json.dump(settings, f, indent=4)
                
                # Atomic replace
                if os.path.exists(path):
                    os.replace(temp_path, path)
                else:
                    os.rename(temp_path, path)
            except Exception as e:
                import logging
                logging.error(f"Settings: Failed to save to {path}: {e}")