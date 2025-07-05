import os
import sys
import subprocess
import importlib.util
from pathlib import Path
from shutil import which

REQUIRED_MODULES = {
    "PIL": "Pillow",
    "qrcode": "qrcode",
    "nuitka": "nuitka",
}

ENTRY_SCRIPT = "mizban.py"
OUTPUT_NAME = "Mizban.exe" if os.name == "nt" else "Mizban"
ICON_PATH = "clients/frontend/favicon.ico"
DATA_DIR = "clients/frontend"
BUILD_DIR = "builds/nuitka"
DIST_DIR = "dists/nuitka"

# ────────────────────────────────────────────────────────────────
def is_venv_active():
    return sys.prefix != sys.base_prefix or hasattr(sys, "real_prefix")

def check_dependencies():
    missing = []
    for module, pkg in REQUIRED_MODULES.items():
        if importlib.util.find_spec(module) is None:
            missing.append(pkg)
    if missing:
        print("\n❌ Missing required packages in your virtual environment:")
        for pkg in missing:
            print(f"   - {pkg}")
        print("\n💡 Install them using:")
        print("   pip install " + " ".join(missing))
        sys.exit(1)

def build_with_nuitka():
    if not which("python"):
        print("❌ Could not find Python executable.")
        sys.exit(1)

    cmd = [
        sys.executable,
        "-m", "nuitka",
        ENTRY_SCRIPT,
        "--standalone",
        "--onefile",
        "--follow-imports",
        f"--include-data-dir={DATA_DIR}={DATA_DIR}",
        "--output-dir=" + BUILD_DIR,
        "--remove-output",
        "--lto=yes",
        "--assume-yes-for-downloads",
        "--nofollow-import-to=tkinter,asyncio,unittest,distutils,setuptools,numpy,PIL.ImageFont,PIL.ImageDraw,PIL.ImageTk",
        f"--output-filename={OUTPUT_NAME}",
    ]

    if os.name == "nt" and ICON_PATH.endswith(".ico") and Path(ICON_PATH).exists():
        cmd.append(f"--windows-icon-from-ico={ICON_PATH}")
    elif ICON_PATH.endswith(".ico") and Path(ICON_PATH).exists():
        cmd.append(f"--macos-app-icon={ICON_PATH}")

    print("\n🚀 Building with Nuitka...\n")
    print(" ".join(cmd), "\n")
    subprocess.run(cmd, check=True)
    print(f"\n✅ Build complete! Executable at: {BUILD_DIR}/{OUTPUT_NAME}")

# ────────────────────────────────────────────────────────────────
def main():
    if not is_venv_active():
        print("❌ You must activate your virtual environment first!")
        print("💡 On Windows:\n    .\\.venv\\Scripts\\activate")
        print("💡 On Unix:\n    source .venv/bin/activate")
        sys.exit(1)

    check_dependencies()
    build_with_nuitka()

if __name__ == "__main__":
    main()
