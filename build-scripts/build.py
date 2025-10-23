import os
import sys
import subprocess
import importlib.util
from pathlib import Path
from shutil import which

# Required modules mapped to their pip names
REQUIRED_MODULES = {
    "PIL": "Pillow",
    "qrcode": "qrcode",
    "nuitka": "nuitka",
    "pystray": "pystray",
}


DATA_DIR = "clients/frontend"
ICON_PATH = "clients/frontend/favicon.ico"  # Must be .ico for Windows
BUILD_DIR = "builds/nuitka"

TARGETS = {
    "cli": {
        "entry": f"{Path(__file__).parent.parent.resolve()}/src/cli_main.py",
        "output": "Mizban_CLI.exe" if os.name == "nt" else "mizban_cli"
    },
    "gui": {
        "entry": f"{Path(__file__).parent.parent.resolve()}/src/gui_main.py",
        "output": "Mizban.exe" if os.name == "nt" else "mizban_gui"
    },
}

# ───────────────────────────────────────────────────────────────────

def is_venv_active():
    return sys.prefix != sys.base_prefix or hasattr(sys, "real_prefix")

def check_dependencies():
    missing = []
    for module, pip_name in REQUIRED_MODULES.items():
        if importlib.util.find_spec(module) is None:
            missing.append(pip_name)
    if missing:
        print("\n❌ Missing required packages in your virtual environment:")
        for pkg in missing:
            print(f"   - {pkg}")
        print("\n💡 Fix it with:")
        print("   pip install " + " ".join(missing))
        sys.exit(1)

def build_target(name, entry_script, output_name):
    print(f"\n🚧 Building target: {name.upper()}")
    cmd = [
        sys.executable, "-m", "nuitka",
        entry_script,
        "--standalone",
        "--follow-imports",
        "--enable-plugin=tk-inter",
        f"--include-data-dir={DATA_DIR}={DATA_DIR}",
        f"--output-dir={BUILD_DIR}",
        "--remove-output",
        "--lto=yes",
        "--assume-yes-for-downloads",
        "--noinclude-unittest-mode=error",
        "--windows-console-mode=disable" if name == "gui" else "--windows-console-mode=force",
        "--nofollow-import-to=hashlib,ssl,asyncio,unittest,distutils,setuptools,numpy,PIL.ImageFont,PIL.ImageDraw,PIL.ImageTk,PIL.WebPImagePlugin,PIL.Pdf*,PIL.Gif*",
        f"--output-filename={output_name}",
    ]
    
    if os.name == "nt" and ICON_PATH.endswith(".ico") and Path(ICON_PATH).exists():
        cmd.append(f"--windows-icon-from-ico={ICON_PATH}")
    elif ICON_PATH.endswith(".icns") and Path(ICON_PATH).exists():
        cmd.append(f"--macos-app-icon={ICON_PATH}")

    print(" ".join(cmd), "\n")

    try:
        subprocess.run(cmd, check=True)
        print(f"\n✅ {name.upper()} build complete! ➜ {BUILD_DIR}/{output_name}")
    except subprocess.CalledProcessError:
        print(f"\n❌ Failed to build {name.upper()}")
        sys.exit(1)

# ───────────────────────────────────────────────────────────────────

def main():
    if not is_venv_active():
        print("❌ Virtual environment not detected.")
        print("💡 Activate it first:")
        print("   On Windows: .\\.venv\\Scripts\\activate")
        print("   On Unix/Mac: source .venv/bin/activate")
        sys.exit(1)

    check_dependencies()

    target = None
    if len(sys.argv) > 1:
        target = sys.argv[1].lower()

    if target not in ("cli", "gui", "all", None):
        print("❌ Invalid target. Use: cli, gui, or all")
        sys.exit(1)

    if target in ("cli", None, "all"):
        t = TARGETS["cli"]
        build_target("cli", t["entry"], t["output"])

    if target in ("gui", None, "all"):
        t = TARGETS["gui"]
        build_target("gui", t["entry"], t["output"])

# ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
