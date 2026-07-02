import os
import sys
import subprocess
import shutil
import argparse

# --- ANSI Colors for Polished CMD Output ---
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_step(msg):
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}>>> {msg}{Colors.ENDC}")

def print_success(msg):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")

def print_warning(msg):
    print(f"{Colors.WARNING}! {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")

def find_icon(preferred_path=None, assume_yes=False):
    if preferred_path:
        if os.path.exists(preferred_path):
            return os.path.abspath(preferred_path)
        print_warning(f"Requested icon was not found: {preferred_path}")

    # Only search known safe directories rather than entire tree
    search_dirs = [".", "app", "assets"]
    for d in search_dirs:
        if not os.path.exists(d): continue
        for file in os.listdir(d):
            if file.endswith(".ico"):
                icon_path = os.path.join(d, file)
                if assume_yes:
                    return os.path.abspath(icon_path)
                choice = input(f"{Colors.OKCYAN}? Found icon '{icon_path}'. Use this for the executable? (y/n): {Colors.ENDC}").strip().lower()
                if choice == 'y':
                    return os.path.abspath(icon_path)
    return None

def check_tool(tool_name):
    try:
        subprocess.run(
            [sys.executable, "-m", tool_name, "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def verify_build():
    exe_name = "PyDSPMeters.exe" if sys.platform == "win32" else "PyDSPMeters"
    exe_path = os.path.join("dist", exe_name)
    if os.path.exists(exe_path):
        print_success(f"Verified: {exe_path} exists!")
        return True
    return False

def build_nuitka(entry_point, icon_path):
    print_step("Compiling with Nuitka (Max Performance & Compression)...")
    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",  # Squeeze space into a single executable
        "--enable-plugin=pyside6",
        "--nofollow-import-to=PySide6.QtCharts",
        "--nofollow-import-to=PySide6.QtNetwork",
        "--nofollow-import-to=PySide6.QtMultimedia",
        "--nofollow-import-to=PySide6.QtWebEngineCore",
        "--nofollow-import-to=PySide6.QtWebEngineWidgets",
        "--nofollow-import-to=PySide6.QtSql",
        "--nofollow-import-to=PySide6.QtXml",
        "--nofollow-import-to=PySide6.QtTest",
        "--nofollow-import-to=PySide6.QtQml",
        "--nofollow-import-to=PySide6.QtQuick",
        "--nofollow-import-to=PySide6.QtShaderTools",
        "--nofollow-import-to=PySide6.Qt3D",
        "--nofollow-import-to=PySide6.QtPrintSupport",
        "--nofollow-import-to=PySide6.QtDesigner",
        "--nofollow-import-to=PySide6.QtHelp",
        "--nofollow-import-to=PySide6.QtSvg",
        "--nofollow-import-to=PySide6.QtSvgWidgets",
        "--windows-console-mode=disable",
        "--include-package=app",
        "--include-package=dsp_accel",
        "--follow-imports",
        "--output-filename=PyDSPMeters.exe" if sys.platform == "win32" else "--output-filename=PyDSPMeters",
        "--output-dir=dist",
        "--remove-output", # Note: This removes intermediate C cache, increasing recompilation time.
        entry_point
    ]
    if icon_path:
        if sys.platform == "win32":
            cmd.append(f"--windows-icon-from-ico={icon_path}")
        elif sys.platform == "darwin":
            cmd.append(f"--macos-app-icon={icon_path}")

    try:
        subprocess.check_call(cmd)
        if verify_build():
            print_success("Nuitka build completed successfully!")
            return True
        else:
            print_error("Nuitka command succeeded but executable was not found.")
            return False
    except subprocess.CalledProcessError:
        print_error("Nuitka build failed. (Ensure you have a C++ compiler and zstandard installed).")
        return False

def build_pyinstaller(entry_point, icon_path):
    print_step("Compiling with PyInstaller (Fallback mode)...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name=PyDSPMeters",
        "--distpath=dist",
        "--workpath=build",
        "--clean",
        "--hidden-import=app",
        "--hidden-import=dsp_accel",
        "--hidden-import=dsp_accel.dsp_accel",
        "--collect-submodules=dsp_accel",
    ]
    if icon_path:
        cmd.append(f"--icon={icon_path}")
        
    cmd.append(entry_point)
    
    try:
        subprocess.check_call(cmd)
        if verify_build():
            print_success("PyInstaller build completed successfully!")
            return True
        else:
            print_error("PyInstaller command succeeded but executable was not found.")
            return False
    except subprocess.CalledProcessError:
        print_error("PyInstaller build failed.")
        return False
    finally:
        # Clean up pyinstaller artifacts regardless of success/failure
        if os.path.exists("PyDSPMeters.spec"):
            os.remove("PyDSPMeters.spec")
        if os.path.exists("build"):
            shutil.rmtree("build", ignore_errors=True)

def parse_args():
    parser = argparse.ArgumentParser(description="Build PyDSPMeters distribution artifacts.")
    parser.add_argument(
        "--icon",
        default=APP_ICON_NAME if "APP_ICON_NAME" in globals() else "icon.ico",
        help="Icon file to use for the executable. Use an empty value to auto-detect.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Use the first discovered icon without prompting.",
    )
    return parser.parse_args()


def build():
    # Enable ANSI colors on Windows CMD
    if sys.platform == "win32":
        os.system("")
        
    print(f"\n{Colors.HEADER}{Colors.BOLD}======================================{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}   PyDSPMeters Distribution Builder   {Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}======================================{Colors.ENDC}\n")
    
    entry_point = "main.pyw"
    if not os.path.exists(entry_point):
        print_error(f"Could not find entry point: {entry_point}")
        sys.exit(1)

    args = parse_args()
    icon_path = find_icon(args.icon or None, assume_yes=args.yes)
    if icon_path:
        print_success(f"Using icon: {icon_path}")
    else:
        print_warning("No icon selected or found.")

    # Try Nuitka first
    if check_tool("nuitka"):
        success = build_nuitka(entry_point, icon_path)
        if success:
            sys.exit(0)
        else:
            print_warning("Nuitka failed. Attempting fallback to PyInstaller...")
    else:
        print_warning("Nuitka not found. Falling back to PyInstaller...")

    # Fallback to PyInstaller
    if check_tool("PyInstaller"):
        success = build_pyinstaller(entry_point, icon_path)
        if success:
            sys.exit(0)
        else:
            print_error("Both Nuitka and PyInstaller failed.")
            sys.exit(1)
    else:
        print_error("PyInstaller not found either! Please install Nuitka or PyInstaller.")
        print(f"Run: {Colors.OKCYAN}pip install nuitka zstandard{Colors.ENDC} OR {Colors.OKCYAN}pip install pyinstaller{Colors.ENDC}")
        sys.exit(1)

if __name__ == "__main__":
    build()
