import os
import sys
import subprocess
import shutil

# noqa
# currently trying to get this to work, as settings.json isn't being saved for some reason
# you're welcome to help

def build():
    print("--- Starting PyDSPMeters Nuitka Build Process ---")
    
    # 1. Verification
    entry_point = "main.py"
    if not os.path.exists(entry_point):
        print(f"Error: Could not find {entry_point}")
        return

    # 2. Icon Discovery
    icon_path = None
    for root, dirs, files in os.walk("."):
        # Stay within root (don't go up)
        if ".." in root: continue
        for file in files:
            if file.endswith(".ico"):
                choice = input(f"Do you wish to add '{file}' as an icon for the executable? (y/n): ").lower()
                if choice == 'y':
                    icon_path = os.path.join(root, file)
                    break
        if icon_path: break

    # 3. Command Construction
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--enable-plugin=pyside6",
        "--windows-console-mode=disable",
        "--include-package=app",
        "--follow-imports",
        "--output-filename=PyDSPMeters",
        "--output-dir=dist",
        "--remove-output",
        entry_point
    ]
    
    if icon_path:
        cmd.append(f"--windows-icon-from-ico={icon_path}")

    print(f"Executing: {' '.join(cmd)}")
    
    try:
        # Run the build
        subprocess.check_call(cmd)
        print("\n--- Build Successful! ---")
        print(f"Your portable executable is located at: {os.path.abspath('dist/PyDSPMeters.exe')}")
        
    except subprocess.CalledProcessError as e:
        print(f"\n--- Build Failed! ---")
        print("Tip: Ensure you have 'nuitka', 'zstandard', and a C++ compiler (like MinGW or MSVC) installed.")
        print("Run: pip install nuitka zstandard")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    build()
