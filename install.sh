#!/usr/bin/env bash
# =============================================================================
# Noclip Desktop — installer for Linux and macOS
# =============================================================================
#
# Usage:
#   chmod +x install.sh
#   ./install.sh                 # Install all runtime dependencies
#   ./install.sh --electron      # Also set up Electron / Node.js dependencies
#   ./install.sh --ollama        # Also install Ollama (for local LLM models)
#   ./install.sh --electron --ollama  # Install everything
#
# The script must be run from the root of the Noclip Desktop repository.
# =============================================================================

set -euo pipefail

INSTALL_ELECTRON=false
INSTALL_OLLAMA=false

for arg in "$@"; do
    case "$arg" in
        --electron) INSTALL_ELECTRON=true ;;
        --ollama)   INSTALL_OLLAMA=true   ;;
        --help|-h)
            sed -n '2,14p' "$0"   # print the Usage block at the top
            exit 0
            ;;
        *) echo "Unknown argument: $arg  (use --electron, --ollama, or --help)"; exit 1 ;;
    esac
done

OS="$(uname -s)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Colour helpers ─────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
banner()  { echo -e "\n${CYAN}══════════════════════════════════════════════════${NC}"; \
            echo -e "${CYAN}  $1${NC}"; \
            echo -e "${CYAN}══════════════════════════════════════════════════${NC}"; }
ok()      { echo -e "${GREEN}  ✔  $1${NC}"; }
warn()    { echo -e "${YELLOW}  ⚠  $1${NC}"; }
fail()    { echo -e "${RED}  ✖  $1${NC}"; exit 1; }

# ── Python version check ────────────────────────────────────────────────────
banner "Checking Python"

PYTHON=""
for candidate in python3.12 python3 python; do
    if command -v "$candidate" &>/dev/null; then
        ver="$("$candidate" -c 'import sys; print(sys.version_info[:2])')"
        maj="$("$candidate" -c 'import sys; print(sys.version_info[0])')"
        min="$("$candidate" -c 'import sys; print(sys.version_info[1])')"
        if [ "$maj" -ge 3 ] && [ "$min" -ge 12 ]; then
            PYTHON="$candidate"
            ok "Found $candidate ($(${candidate} --version 2>&1))"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    warn "Python 3.12+ not found."
    if [ "$OS" = "Darwin" ]; then
        echo "  Install it with: brew install python@3.12"
        echo "  Or download from: https://www.python.org/downloads/"
    else
        echo "  Install it with: sudo apt-get install -y python3.12 python3.12-venv python3.12-dev"
        echo "  Or download from: https://www.python.org/downloads/"
    fi
    fail "Please install Python 3.12+ and re-run this script."
fi

# ── OS-specific system packages ─────────────────────────────────────────────
banner "Installing system packages"

if [ "$OS" = "Linux" ]; then
    if ! command -v apt-get &>/dev/null; then
        warn "apt-get not found — skipping system package install."
        warn "Make sure the following are installed for your distro:"
        warn "  python3-tk  python3-dev  portaudio19-dev  xdg-utils  libxcb-xinerama0"
    else
        echo "  Running sudo apt-get update …"
        sudo apt-get update -qq
        sudo apt-get install -y \
            python3-tk \
            python3-dev \
            portaudio19-dev \
            xdg-utils \
            libxcb-xinerama0
        ok "System packages installed."
    fi

elif [ "$OS" = "Darwin" ]; then
    if ! command -v brew &>/dev/null; then
        warn "Homebrew not found. Attempting to install …"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install portaudio || true
    ok "macOS system packages installed."

else
    warn "Unrecognised OS '$OS'. Skipping system package step."
fi

# ── Python (pip) dependencies ───────────────────────────────────────────────
banner "Installing Python dependencies"

REQ="$SCRIPT_DIR/requirements.txt"
if [ ! -f "$REQ" ]; then
    fail "requirements.txt not found at $REQ"
fi

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r "$REQ"
ok "Python packages installed."

# ── Ollama (optional) ────────────────────────────────────────────────────────
if [ "$INSTALL_OLLAMA" = true ]; then
    banner "Installing Ollama"

    if command -v ollama &>/dev/null; then
        ok "Ollama is already installed: $(ollama --version 2>&1 || true)"
    elif [ "$OS" = "Linux" ] || [ "$OS" = "Darwin" ]; then
        curl -fsSL https://ollama.com/install.sh | sh
        ok "Ollama installed."
    else
        warn "Automatic Ollama install is supported on Linux and macOS only."
        warn "Download from https://ollama.com and follow the installer."
    fi

    echo ""
    echo "  Recommended CPU-optimised models (pull whichever you want):"
    echo "    ollama pull qwen3-vl:30b"
    echo "    ollama pull deepseek-coder-v2:16b"
    echo "    ollama pull llama3.1:8b-instruct-q4_K_M"
fi

# ── Node.js / Electron dependencies (optional) ──────────────────────────────
if [ "$INSTALL_ELECTRON" = true ]; then
    banner "Installing Node.js / Electron dependencies"

    if ! command -v node &>/dev/null; then
        warn "Node.js not found."
        if [ "$OS" = "Darwin" ]; then
            echo "  Install with: brew install node"
        else
            echo "  Install with: sudo apt-get install -y nodejs npm"
            echo "  Or use nvm:   https://github.com/nvm-sh/nvm"
        fi
        fail "Please install Node.js 20+ and re-run with --electron."
    fi

    NODE_VER="$(node -e 'process.stdout.write(String(process.versions.node.split(".")[0]))')"
    if [ "$NODE_VER" -lt 20 ]; then
        fail "Node.js 20+ is required (found $(node --version)). Please upgrade."
    fi
    ok "Node.js $(node --version) found."

    ELECTRON_DIR="$SCRIPT_DIR/electron"
    if [ ! -d "$ELECTRON_DIR" ]; then
        fail "electron/ directory not found at $ELECTRON_DIR"
    fi

    (cd "$ELECTRON_DIR" && npm install)
    ok "Electron npm dependencies installed."
fi

# ── Done ─────────────────────────────────────────────────────────────────────
banner "Installation complete"

echo ""
echo "  To run the local server:"
echo "    python app/app.py"
echo ""
echo "  To build the server executable:"
echo "    python build.py"
echo ""
if [ "$INSTALL_ELECTRON" = true ]; then
    echo "  To build the Electron desktop app:"
    echo "    python build.py --app-type electron"
    echo ""
fi
if [ "$INSTALL_OLLAMA" = true ]; then
    echo "  To start Ollama and use a local model:"
    echo "    ollama serve   # (in a separate terminal)"
    echo "    ollama pull llama3.1:8b-instruct-q4_K_M"
    echo ""
fi
echo "  The Gradio web UI will open at http://127.0.0.1:7860"
echo ""
