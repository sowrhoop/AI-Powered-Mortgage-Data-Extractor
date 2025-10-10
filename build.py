import os
import sys
import platform
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional
import PyInstaller
import PyInstaller.__main__
import argparse

EXCLUDES = [
    "tensorflow", "tf_keras", "flax", "jax", "jaxlib",
    "torchvision", "torchaudio", "torchtext",
    "datasets", "accelerate", "optuna",
    "scikit-learn", "sklearn",
    "matplotlib", "pandas", "scipy", "ipython", "notebook",
    "evaluate", "sacremoses", "sentencepiece", "protobuf",
    "onnx", "onnxruntime",
]

NAME = "Ascendant Vision AI Platform"

# Be explicit about dynamic packages PyInstaller may miss
COLLECT_SUBMODULES = [
    "openai",
    "httpx",
    "httpcore",
    "anyio",
    "sniffio",
    "pydantic",
]

def check_build_output(name: str) -> Optional[Path]:
    """Return the built executable path if it exists, else None."""
    suffix = ".exe" if os.name == "nt" else ""
    exe = Path("dist") / f"{name}{suffix}"
    if exe.exists():
        print(f"Build successful: {exe}")
        return exe
    print(f"Executable not found: {exe}")
    # Show directory listing to aid debugging
    dist_dir = Path("dist")
    if dist_dir.exists():
        for p in dist_dir.iterdir():
            print(f" - found in dist: {p}")
    return None


def _git_describe() -> str:
    try:
        out = subprocess.check_output(["git", "describe", "--tags", "--always", "--dirty"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="ignore").strip()
    except Exception:
        return "unknown"


def _platform_sep() -> str:
    # PyInstaller expects ';' on Windows, ':' elsewhere
    return ";" if os.name == "nt" else ":"

def main():
    if platform.system() != "Windows":
        print("Warning: This project targets Windows; --windowed is applied on Windows only.")
    if sys.version_info < (3, 9):
        print("Error: Python 3.9+ is required to build this project.")
        sys.exit(2)

    parser = argparse.ArgumentParser(description="Build the Ascendant Vision AI Platform executable with PyInstaller.")
    parser.add_argument("entry", nargs="?", default="src/main.py", help="Entry point script (default: src/main.py)")
    parser.add_argument("--name", default=NAME, help=f"Application name (default: {NAME})")
    parser.add_argument("--console", action="store_true", help="Build with console window (debug run)")
    parser.add_argument("--windowed", action="store_true", help="Force windowed mode (no console)")
    parser.add_argument("--icon", default=str((Path("assets")/"app.ico")), help="Path to .ico file (Windows)")
    parser.add_argument("--clean-dist", action="store_true", help="Remove existing dist/ and build/ before building")
    parser.add_argument("--no-upx", action="store_true", help="Disable UPX even if UPX_DIR is set")
    parser.add_argument("--add-data", action="append", default=[], help="Extra data to include, format src{sep}dest (repeatable)")
    parser.add_argument("--log-level", default="WARN", choices=["TRACE","DEBUG","INFO","WARN","ERROR"], help="PyInstaller log level")
    parser.add_argument("--onefile", action="store_true", help="Build onefile (default)")
    parser.add_argument("--onedir", action="store_true", help="Build onedir instead of onefile")
    parser.add_argument("--version-tag", default=os.environ.get("APP_VERSION", _git_describe()), help="Version tag to record in build_info.txt")
    args_ns = parser.parse_args()

    print(f"Using PyInstaller {PyInstaller.__version__}")

    if args_ns.clean_dist:
        for d in ("dist", "build"):
            if Path(d).exists():
                print(f"Removing {d}/ …")
                shutil.rmtree(d, ignore_errors=True)

    # Default to onefile unless onedir explicitly requested
    bundle_mode = "--onedir" if args_ns.onedir and not args_ns.onefile else "--onefile"

    base_args: List[str] = [
        args_ns.entry,
        bundle_mode,
        f"--name={args_ns.name}",
        "--noconfirm",
        "--clean",
        "--strip",
        "--optimize=2",
        f"--log-level={args_ns.log_level}",
        *[f"--exclude-module={m}" for m in EXCLUDES],
        *[f"--collect-submodules={m}" for m in COLLECT_SUBMODULES],
    ]

    # Windowing/console flags
    if platform.system() == "Windows":
        if args_ns.console and not args_ns.windowed:
            pass  # default console app
        else:
            base_args.append("--windowed")
        icon_path = Path(args_ns.icon)
        if icon_path.exists():
            base_args.append(f"--icon={icon_path}")

    # Include assets directory by default if present
    assets_dir = Path("assets")
    if assets_dir.exists():
        sep = _platform_sep()
        base_args.append(f"--add-data={assets_dir}{sep}assets")

    # Extra add-data from CLI
    for spec in args_ns.add_data:
        base_args.append(f"--add-data={spec}")

    # UPX
    if not args_ns.no_upx:
        upx_dir = os.environ.get("UPX_DIR")
        if upx_dir and os.path.isdir(upx_dir):
            base_args.append(f"--upx-dir={upx_dir}")

    # Optimize Python runtime
    os.environ.setdefault("PYTHONOPTIMIZE", "2")
    os.environ.setdefault("PYTHONHASHSEED", "0")

    print("Building executable with arguments:\n  " + "\n  ".join(base_args))
    try:
        PyInstaller.__main__.run(base_args)
    except SystemExit as e:
        # PyInstaller calls sys.exit internally; surface a clear message
        code = getattr(e, "code", 1)
        print(f"PyInstaller exited with code {code}")
        sys.exit(code if isinstance(code, int) else 1)

    exe_path = check_build_output(args_ns.name)
    if exe_path:
        # Write build info
        info = (
            f"name={args_ns.name}\n"
            f"version={args_ns.version_tag}\n"
            f"pyinstaller={PyInstaller.__version__}\n"
            f"python={platform.python_version()}\n"
            f"platform={platform.platform()}\n"
        )
        try:
            (Path("dist")/"build_info.txt").write_text(info, encoding="utf-8")
        except Exception:
            pass
        print("Build complete.")
    else:
        print("Build finished with warnings.")

if __name__ == "__main__":
    main()
