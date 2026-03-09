@echo off
:: =============================================================================
:: Noclip Desktop — installer for Windows
:: =============================================================================
::
:: Usage (run from the Noclip Desktop repository root):
::   install.bat                      — install all runtime dependencies
::   install.bat /electron            — also set up Electron / Node.js deps
::   install.bat /ollama              — also install Ollama (local LLM)
::   install.bat /electron /ollama    — install everything
::
:: Tip: right-click and "Run as Administrator" if you see permission errors.
:: =============================================================================

setlocal EnableDelayedExpansion

set "INSTALL_ELECTRON=0"
set "INSTALL_OLLAMA=0"

:: ── Parse arguments ──────────────────────────────────────────────────────────
:parse_args
if "%~1"=="" goto check_python
if /I "%~1"=="/electron" ( set "INSTALL_ELECTRON=1" & shift & goto parse_args )
if /I "%~1"=="/ollama"   ( set "INSTALL_OLLAMA=1"   & shift & goto parse_args )
if /I "%~1"=="/help"     goto show_help
echo Unknown argument: %~1  (use /electron, /ollama, or /help)
exit /b 1

:show_help
echo Usage:
echo   install.bat                   -- runtime Python dependencies
echo   install.bat /electron         -- also install Electron/Node.js deps
echo   install.bat /ollama           -- also install Ollama for local LLM
echo   install.bat /electron /ollama -- install everything
exit /b 0

:: ── Helpers ───────────────────────────────────────────────────────────────────
:check_python
echo.
echo ==================================================
echo   Checking Python
echo ==================================================

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH.
    echo.
    echo   Download Python 3.12+ from https://www.python.org/downloads/
    echo   Make sure to check "Add Python to PATH" during installation.
    exit /b 1
)

:: Check Python version >= 3.12
for /f "delims=" %%v in ('python -c "import sys; print(sys.version_info >= (3,12))"') do set "PY_OK=%%v"
if /I "!PY_OK!"=="False" (
    echo [ERROR] Python 3.12+ is required.
    for /f "delims=" %%v in ('python --version 2^>^&1') do echo Found: %%v
    echo.
    echo   Download Python 3.12+ from https://www.python.org/downloads/
    exit /b 1
)

for /f "delims=" %%v in ('python --version 2^>^&1') do echo   [OK] Found %%v

:: ── Python (pip) dependencies ─────────────────────────────────────────────
echo.
echo ==================================================
echo   Installing Python dependencies
echo ==================================================

if not exist "%~dp0requirements.txt" (
    echo [ERROR] requirements.txt not found at %~dp0
    exit /b 1
)

python -m pip install --upgrade pip
python -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo [ERROR] pip install failed.
    exit /b 1
)
echo   [OK] Python packages installed.

:: ── Ollama (optional) ─────────────────────────────────────────────────────
if "!INSTALL_OLLAMA!"=="1" (
    echo.
    echo ==================================================
    echo   Installing Ollama
    echo ==================================================

    where ollama >nul 2>&1
    if not errorlevel 1 (
        echo   [OK] Ollama is already installed.
    ) else (
        :: Try winget first (built into Windows 10/11)
        where winget >nul 2>&1
        if not errorlevel 1 (
            echo   Installing Ollama via winget ...
            winget install Ollama.Ollama --silent --accept-package-agreements --accept-source-agreements
            if errorlevel 1 (
                echo   [WARN] winget install failed. Download manually:
                echo          https://ollama.com/download/OllamaSetup.exe
            ) else (
                echo   [OK] Ollama installed via winget.
            )
        ) else (
            echo   winget not available. Downloading Ollama installer ...
            set "OLLAMA_EXE=%TEMP%\OllamaSetup.exe"
            curl -fsSL -o "!OLLAMA_EXE!" https://ollama.com/download/OllamaSetup.exe
            if errorlevel 1 (
                echo   [ERROR] Download failed. Get the installer from https://ollama.com/download/OllamaSetup.exe
                exit /b 1
            )
            start /wait "" "!OLLAMA_EXE!" /S
            echo   [OK] Ollama installed.
        )
    )

    echo.
    echo   Recommended CPU-optimised models (pull whichever you want):
    echo     ollama pull qwen3-vl:30b
    echo     ollama pull deepseek-coder-v2:16b
    echo     ollama pull llama3.1:8b-instruct-q4_K_M
)

:: ── Node.js / Electron dependencies (optional) ───────────────────────────
if "!INSTALL_ELECTRON!"=="1" (
    echo.
    echo ==================================================
    echo   Installing Node.js / Electron dependencies
    echo ==================================================

    where node >nul 2>&1
    if errorlevel 1 (
        echo   Node.js not found on PATH.
        echo   Download Node.js 20+ from https://nodejs.org/
        exit /b 1
    )

    for /f "delims=" %%v in ('node -e "process.stdout.write(String(process.versions.node.split('.')[0]))"') do set "NODE_MAJOR=%%v"
    if !NODE_MAJOR! LSS 20 (
        echo [ERROR] Node.js 20+ required. Found: & node --version
        echo   Download from https://nodejs.org/
        exit /b 1
    )
    echo   [OK] Node.js is at version:
    node --version

    if not exist "%~dp0electron" (
        echo [ERROR] electron\ directory not found at %~dp0electron
        exit /b 1
    )

    pushd "%~dp0electron"
    npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed.
        popd
        exit /b 1
    )
    popd
    echo   [OK] Electron npm dependencies installed.
)

:: ── Done ──────────────────────────────────────────────────────────────────
echo.
echo ==================================================
echo   Installation complete
echo ==================================================
echo.
echo   To run the local server:
echo     python app\app.py
echo.
echo   To build the server executable:
echo     python build.py
echo.
if "!INSTALL_ELECTRON!"=="1" (
    echo   To build the Electron desktop app:
    echo     python build.py --app-type electron
    echo.
)
if "!INSTALL_OLLAMA!"=="1" (
    echo   To start Ollama and use a local model:
    echo     ollama serve   (in a separate terminal)
    echo     ollama pull llama3.1:8b-instruct-q4_K_M
    echo.
)
echo   The Gradio web UI will open at http://127.0.0.1:7860
echo.

endlocal
