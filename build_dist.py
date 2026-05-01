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
    entry_point = "main.pyw"
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
        
        # 4. Post-build Cleanup
        # Nuitka in standalone mode creates a folder: dist/PyDSPMeters.dist
        dist_folder = os.path.join("dist", "PyDSPMeters.dist")
        
        # If the folder doesn't exist (maybe Nuitka behaved differently), find it
        if not os.path.exists(dist_folder):
            for item in os.listdir("dist"):
                if item.endswith(".dist"):
                    dist_folder = os.path.join("dist", item)
                    break
        
        print(f"Dist folder identified: {dist_folder}")
        
        # 5. Create ZIP for Installer/Distribution
        zip_name = "PyDSPMeters_Standalone"
        zip_dest = os.path.abspath(os.path.join("dist_zip", zip_name))
        
        # Ensure we don't zip into the source folder to avoid recursion
        if os.path.exists("dist_zip"):
            shutil.rmtree("dist_zip")
        os.makedirs("dist_zip")
        
        print(f"Creating {zip_name}.zip in 'dist_zip'...")
        # root_dir is the folder to zip, base_dir is the folder name inside the zip
        shutil.make_archive(zip_dest, 'zip', root_dir=dist_folder)
        
        final_zip = zip_dest + ".zip"
        print(f"ZIP created: {final_zip}")
        print(f"\nYour standalone folder is located at: {dist_folder}")
        print(f"Your distribution ZIP is located at: {final_zip}")
        
    except subprocess.CalledProcessError as e:
        print(f"\n--- Build Failed! ---")
        print("Tip: Ensure you have 'nuitka', 'zstandard', and a C++ compiler (like MinGW or MSVC) installed.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    build()
