from __future__ import annotations

import importlib.util
import os
import shlex
import subprocess
import sys
from pathlib import Path
from shutil import which

IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"

# Required modules mapped to their pip names
REQUIRED_MODULES = {
    "PIL": "Pillow",
    "qrcode": "qrcode",
    "nuitka": "nuitka",
    "pystray": "pystray",
}


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIENTS_DIR = PROJECT_ROOT / "clients"
FRONTEND_DIR = CLIENTS_DIR / "frontend"
FRONTEND_TARGET = "clients/frontend"
ICON_PATH = FRONTEND_DIR / "favicon.ico"  # Must be .ico for Windows
BUILD_DIR = PROJECT_ROOT / "builds" / "nuitka"

TARGETS = {
    "cli": {
        "entry": PROJECT_ROOT / "src" / "cli_main.py",
        "output": "Mizban_CLI.exe" if os.name == "nt" else "mizban_cli",
    },
    "gui": {
        "entry": PROJECT_ROOT / "src" / "gui_main.py",
        "output": "Mizban.exe" if os.name == "nt" else "mizban_gui",
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

    if IS_LINUX:
        missing_tools = [tool for tool in ("patchelf", "ldd") if which(tool) is None]
        if missing_tools:
            print("\n❌ Missing required system tools for Nuitka onefile builds:")
            for tool in missing_tools:
                print(f"   - {tool}")
            print("\n💡 Install them with your package manager, e.g.")
            print("   sudo apt install " + " ".join(missing_tools))
            sys.exit(1)

def _format_command(cmd):
    return " ".join(shlex.quote(str(part)) for part in cmd)


def _console_mode_flag(target_name: str) -> str | None:
    if not IS_WINDOWS:
        return None
    return (
        "--windows-console-mode=disable"
        if target_name == "gui"
        else "--windows-console-mode=force"
    )


def _icon_flags() -> list[str]:
    flags: list[str] = []
    if IS_WINDOWS and ICON_PATH.suffix.lower() == ".ico" and ICON_PATH.exists():
        flags.append(f"--windows-icon-from-ico={ICON_PATH}")
    elif IS_MAC and ICON_PATH.suffix.lower() == ".icns" and ICON_PATH.exists():
        flags.append(f"--macos-app-icon={ICON_PATH}")
    return flags


def _data_flags() -> list[str]:
    flags: list[str] = []
    if FRONTEND_DIR.exists():
        flags.append(f"--include-data-dir={FRONTEND_DIR}={FRONTEND_TARGET}")
    else:
        print(f"\n⚠️  Frontend directory not found: {FRONTEND_DIR}")
    return flags


def _base_nuitka_flags(target_name: str) -> list[str]:
    flags = [
        "--follow-imports",
        f"--output-dir={BUILD_DIR}",
        "--remove-output",
        "--lto=yes",
        "--assume-yes-for-downloads",
        "--noinclude-unittest-mode=error",
        "--nofollow-import-to=hashlib,ssl,asyncio,unittest,distutils,setuptools,numpy,PIL.ImageFont,PIL.ImageDraw,PIL.ImageTk,PIL.WebPImagePlugin,PIL.Pdf*,PIL.Gif*",
        f"--jobs={max(os.cpu_count() or 1, 1)}",
        *_data_flags(),
    ]
    if target_name == "gui":
        flags.append("--enable-plugin=tk-inter")
    console_flag = _console_mode_flag(target_name)
    if console_flag:
        flags.append(console_flag)
    if IS_LINUX:
        flags.append("--onefile")
    else:
        flags.append("--standalone")
    return flags


def build_target(name, entry_script, output_name):
    print(f"\n🚧 Building target: {name.upper()}")
    if not FRONTEND_DIR.exists():
        print(f"\n❌ Frontend directory not found: {FRONTEND_DIR}")
        sys.exit(1)

    entry_path = Path(entry_script)
    if not entry_path.exists():
        print(f"\n❌ Entry script not found: {entry_path}")
        sys.exit(1)

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        str(entry_path),
        f"--output-filename={output_name}",
        *_base_nuitka_flags(name),
        *_icon_flags(),
    ]

    print(_format_command(cmd), "\n")

    try:
        subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT))
        print(f"\n✅ {name.upper()} build complete! ➜ {BUILD_DIR / output_name}")
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
