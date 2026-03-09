"""
Standalone build script — runs on Windows, macOS, and Linux without GitHub Actions.

Usage
-----
    # Build the server (PyInstaller) executable for the current platform:
    python3 build.py

    # Build the Electron desktop app (requires Node.js ≥ 20):
    python3 build.py --app-type electron

    # Build and code-sign on macOS:
    python3 build.py --sign "Developer ID Application: Your Name (TEAMID)"

    # Install Python and Node dependencies, then build:
    python3 build.py --setup

Prerequisites
-------------
All platforms:
    python3 -m pip install -r requirements.txt
    python3 -m pip install pyinstaller

Linux (install once with apt):
    sudo apt-get update
    sudo apt-get install -y python3-tk python3-dev portaudio19-dev xdg-utils libxcb-xinerama0

macOS:
    brew install portaudio
    # If using pyenv, install Tkinter manually:
    # https://dev.to/xshapira/using-tkinter-with-pyenv-a-simple-two-step-guide-hh5

Electron builds additionally require Node.js ≥ 20 with npm.

Notes
-----
1. PyInstaller prints many warnings; the first real error is near the bottom of the log,
   just before the cleanup section.
2. Code signing for macOS:
   https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

from app.version import version

# Path separator used by PyInstaller --add-data: ";" on Windows, ":" everywhere else.
_SEP = ";" if platform.system() == "Windows" else ":"

# Human-readable name and the on-disk executable name
_APP_NAME = "Noclip Desktop"
_EXE_NAME = f"{_APP_NAME}.exe" if platform.system() == "Windows" else _APP_NAME


def setup(include_node: bool = False) -> None:
    """Install Python (and optionally Node) dependencies."""
    print("==> Installing Python dependencies …")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    if platform.system() == "Linux":
        print(
            "\n[Linux] If the build fails, make sure the following system packages are installed:\n"
            "  sudo apt-get update\n"
            "  sudo apt-get install -y python3-tk python3-dev portaudio19-dev "
            "xdg-utils libxcb-xinerama0\n"
        )

    if include_node:
        print("==> Installing Node.js (Electron) dependencies …")
        subprocess.check_call(["npm", "install"], cwd="electron")


def compile_server(signing_key: str | None = None) -> None:
    """Run PyInstaller to produce the server executable."""
    import PyInstaller.__main__  # pylint: disable=import-outside-toplevel

    app_script = os.path.join("app", "app.py")

    pyinstaller_options = [
        "--clean",
        "--noconfirm",
        f"--name={_APP_NAME}",
        "--icon=app/resources/icon.png",
        "--onefile",
        # Hidden imports required for successful packaging
        "--hidden-import=pyautogui",
        "--hidden-import=appdirs",
        "--hidden-import=pyparsing",
        "--hidden-import=openai",
        # google-genai doesn't play nice with PyInstaller without these
        "--hidden-import=google_genai",
        "--hidden-import=google",
        "--hidden-import=google.genai",
        # Gradio web UI
        "--hidden-import=gradio",
        "--hidden-import=uvicorn",
        "--collect-all=gradio",
        "--collect-all=gradio_client",
        # Additional LLM providers
        "--hidden-import=anthropic",
        # Multi-monitor detection
        "--hidden-import=screeninfo",
        # Static files and source modules bundled into the executable
        # https://pyinstaller.org/en/stable/runtime-information.html
        f"--add-data=app/resources/*{_SEP}resources",
        f"--add-data=app/*.py{_SEP}.",
        f"--add-data=app/utils/*.py{_SEP}utils",
        f"--add-data=app/models/*.py{_SEP}models",
        app_script,
    ]

    if platform.system() == "Darwin" and signing_key:
        pyinstaller_options.append(f"--codesign-identity={signing_key}")
        # Note: Apple Notarization may fail for binaries signed with an old SDK.
        # See: https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing
    elif platform.system() == "Linux":
        pyinstaller_options.append("--hidden-import=PIL._tkinter_finder")

    PyInstaller.__main__.run(pyinstaller_options)
    print(f"==> Server executable written to dist/{_EXE_NAME}")


def build_electron() -> None:
    """
    Build the Electron desktop app wrapper around the server executable.

    Requires:
    - The server executable already built in dist/
    - Node.js ≥ 20 with npm available on PATH
    """
    server_bundle_dir = os.path.join("dist", "noclip-desktop-server")
    os.makedirs(server_bundle_dir, exist_ok=True)
    shutil.copy(os.path.join("dist", _EXE_NAME), server_bundle_dir)
    print(f"==> Copied server binary to {server_bundle_dir}/")

    print("==> Installing Electron npm dependencies …")
    subprocess.check_call(["npm", "install"], cwd="electron")

    system = platform.system()
    if system == "Windows":
        builder_flag = "--win"
    elif system == "Darwin":
        builder_flag = "--mac"
    else:
        builder_flag = "--linux"

    print(f"==> Building Electron app ({system}) …")
    subprocess.check_call(["npx", "electron-builder", builder_flag], cwd="electron")
    print("==> Electron app written to electron/dist/")


def codesign_macos(signing_key: str) -> None:
    """Deep-sign the macOS .app bundle."""
    app_path = f"dist/{_APP_NAME}.app"
    subprocess.check_call([
        "codesign", "--deep", "--force", "--verbose",
        "--sign", signing_key, app_path, "--options", "runtime",
    ])


def notarize_macos(signing_key: str, zip_path: str) -> None:
    """Submit the zip to Apple notarization and staple on success."""
    keychain_profile = signing_key.split("(")[0].strip()
    subprocess.check_call([
        "xcrun", "notarytool", "submit", "--wait",
        "--keychain-profile", keychain_profile, "--verbose", zip_path,
    ])
    input(
        f"Check notarization status with:\n"
        f"  xcrun notarytool history --keychain-profile {keychain_profile}\n"
        f"Then press Enter to staple …"
    )
    subprocess.check_call(["xcrun", "stapler", "staple", f"dist/{_APP_NAME}.app"])


def create_zip() -> str:
    """Zip the built artifact and return the zip filename."""
    print("==> Creating release zip …")
    base = f"Noclip-Desktop-v{version}"

    system = platform.system()
    if system == "Darwin":
        suffix = "MacOS-M-Series" if platform.processor() == "arm" else "MacOS-Intel"
        zip_name = f"{base}-{suffix}.zip"
        subprocess.check_call([
            "ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
            f"{_APP_NAME}.app", zip_name,
        ], cwd="dist")
    elif system == "Linux":
        zip_name = f"{base}-Linux.zip"
        subprocess.check_call(["zip", "-r9", zip_name, _APP_NAME], cwd="dist")
    elif system == "Windows":
        zip_name = f"{base}-Windows.zip"
        subprocess.check_call([
            "powershell", "Compress-Archive",
            "-Path", f"{_APP_NAME}.exe",
            "-DestinationPath", zip_name,
        ], cwd="dist")
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    print(f"==> Release archive: dist/{zip_name}")
    return zip_name


def build(app_type: str = "server", signing_key: str | None = None, release: bool = False) -> None:
    """
    Full build pipeline.

    Parameters
    ----------
    app_type:   "server"   — PyInstaller executable only (default)
                "electron" — PyInstaller executable + Electron wrapper
    signing_key: macOS Developer ID for code-signing (optional)
    release:    When True, also produce a zip archive suitable for distribution
    """
    compile_server(signing_key)

    macos = platform.system() == "Darwin"
    if macos and signing_key:
        codesign_macos(signing_key)

    if app_type == "electron":
        build_electron()

    if release:
        zip_path = create_zip()

        if macos and signing_key:
            notarize_macos(signing_key, os.path.join("dist", zip_path))
            # Re-zip after stapling
            create_zip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build Noclip Desktop for the current platform.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 build.py\n"
            "  python3 build.py --app-type electron\n"
            '  python3 build.py --sign "Developer ID Application: My Name (TEAM)"\n'
            "  python3 build.py --release\n"
            "  python3 build.py --setup --app-type electron\n"
        ),
    )
    parser.add_argument(
        "--app-type",
        choices=["server", "electron"],
        default="server",
        help="Build the PyInstaller server executable only (default) or add the Electron wrapper.",
    )
    parser.add_argument(
        "--sign",
        metavar="SIGNING_KEY",
        default=None,
        help="macOS Developer ID Application signing identity (e.g. 'Developer ID Application: Name (ID)').",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Also produce a zip archive for distribution (and run notarization on macOS when --sign is provided).",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Install Python and (for --app-type electron) Node.js dependencies before building.",
    )

    args = parser.parse_args()

    if args.setup:
        setup(include_node=args.app_type == "electron")

    build(app_type=args.app_type, signing_key=args.sign, release=args.release)
