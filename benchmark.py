#!/usr/bin/env python3
"""Standalone benchmark runner for Open Interface.

Run this script directly on any hardware to execute the performance benchmarks:

    python benchmark.py

Optional arguments:

    --ollama-models llama3.2,mistral
        Comma-separated list of Ollama models to benchmark against a real
        Ollama instance.  When provided the script will install Ollama (Linux
        only via the official install script), start ``ollama serve``, pull the
        requested models and run the integration benchmark suite in addition to
        the always-on mock benchmarks.

        The following models are recommended for CPU-heavy environments because
        they run efficiently with llama.cpp / Ollama without a GPU:

            qwen3-vl:30b
            deepseek-coder-v2:16b
            llama3.1:8b-instruct-q4_K_M

    --ollama-endpoint http://localhost:11434
        Base URL of an already-running Ollama instance.  Skips the install /
        start steps and jumps straight to the real-model benchmarks.

    --output benchmark-results.txt
        File to write the combined pytest output to (default:
        ``benchmark-results.txt``).

    --no-xvfb
        Disable automatic Xvfb virtual-display setup on Linux.  Useful when a
        real display is already available.

Examples::

    # Mock-only benchmarks (no GPU / API keys required)
    python benchmark.py

    # Real Ollama benchmarks with a locally running instance
    OLLAMA_ENDPOINT=http://localhost:11434 python benchmark.py

    # Let the script install Ollama and pull the recommended CPU-optimized models (Linux only)
    python benchmark.py --ollama-models qwen3-vl:30b,deepseek-coder-v2:16b,llama3.1:8b-instruct-q4_K_M

    # Benchmark with classic models (Linux only)
    python benchmark.py --ollama-models llama3.2,mistral
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# CPU-optimized Ollama models that work well with llama.cpp on CPU-heavy environments.
# These are used as the default when --ollama-models is not specified but OLLAMA_MODELS is unset.
_CPU_OPTIMIZED_MODELS = [
    'qwen3-vl:30b',
    'deepseek-coder-v2:16b',
    'llama3.1:8b-instruct-q4_K_M',
]


# ── Helpers ──────────────────────────────────────────────────────────


def _run(cmd: list[str], *, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command, streaming output to stdout."""
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(cmd, check=check, env=merged_env)


def _banner(text: str) -> None:
    print(f'\n{"─" * 60}')
    print(f'  {text}')
    print(f'{"─" * 60}')


# ── Dependency installation ───────────────────────────────────────────


def install_python_dependencies() -> None:
    _banner('Installing Python dependencies')
    requirements = os.path.join(_SCRIPT_DIR, 'requirements.txt')
    _run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'])
    _run([sys.executable, '-m', 'pip', 'install', '-r', requirements])
    # pytest is not always in requirements.txt
    _run([sys.executable, '-m', 'pip', 'install', 'pytest'])


# ── Virtual display (Linux / headless) ───────────────────────────────


def start_xvfb() -> subprocess.Popen | None:
    """Start Xvfb on Linux when no DISPLAY is set.  Returns the process or None."""
    if platform.system() != 'Linux':
        return None
    if os.environ.get('DISPLAY'):
        print('Virtual display: using existing DISPLAY=' + os.environ['DISPLAY'])
        return None
    if not shutil.which('Xvfb'):
        print('Xvfb not found — skipping virtual display setup.')
        print('Install it with:  sudo apt-get install -y xvfb')
        return None

    _banner('Starting virtual display (Xvfb :99)')
    proc = subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1920x1080x24'])
    os.environ['DISPLAY'] = ':99'
    time.sleep(1)  # give Xvfb a moment to initialize
    print('Xvfb started (PID %d), DISPLAY=:99' % proc.pid)
    return proc


# ── Ollama helpers ────────────────────────────────────────────────────


def install_ollama() -> None:
    """Install Ollama on Linux using the official install script."""
    if platform.system() != 'Linux':
        print('Automatic Ollama install is only supported on Linux.')
        print('Download Ollama from https://ollama.com and start it manually.')
        sys.exit(1)

    _banner('Installing Ollama')
    install_cmd = 'curl -fsSL https://ollama.com/install.sh | sh'
    subprocess.run(install_cmd, shell=True, check=True)


def start_ollama_server() -> subprocess.Popen:
    """Start ``ollama serve`` in the background."""
    _banner('Starting Ollama server')
    proc = subprocess.Popen(['ollama', 'serve'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)  # allow the server to become ready
    print('Ollama server started (PID %d)' % proc.pid)
    return proc


def pull_ollama_models(models: list[str]) -> None:
    """Pull the given Ollama models."""
    _banner(f'Pulling Ollama models: {", ".join(models)}')
    for model in models:
        model = model.strip()
        if not model:
            continue
        print(f'\nPulling: {model}')
        _run(['ollama', 'pull', model])


# ── Benchmark runner ──────────────────────────────────────────────────


def run_benchmarks(output_file: str, extra_env: dict | None = None, append: bool = False) -> int:
    """Run pytest benchmark suite, tee-ing output to *output_file*.

    Returns the pytest exit code.
    """
    tests_dir = os.path.join(_SCRIPT_DIR, 'tests')
    cmd = [
        sys.executable, '-m', 'pytest',
        tests_dir,
        '-v', '--tb=short', '-x',
        '--ignore=' + os.path.join(tests_dir, 'simple_test.py'),  # legacy integration test
    ]

    mode = 'a' if append else 'w'
    env = {**os.environ, **(extra_env or {})}

    print(f'\nRunning: {" ".join(cmd)}\n')
    with open(output_file, mode) as fh:
        # Use Popen to stream output to both stdout and the results file
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        stdout = proc.stdout or []
        for line in stdout:
            sys.stdout.write(line)
            fh.write(line)
        proc.wait()
        return proc.returncode


# ── Main ──────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run Open Interface performance benchmarks.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--ollama-models',
        metavar='MODEL[,MODEL...]',
        default=os.environ.get('OLLAMA_MODELS', ''),
        help=(
            'Comma-separated Ollama models to benchmark (enables real-LLM tests). '
            f'Recommended CPU-optimized models: {", ".join(_CPU_OPTIMIZED_MODELS)}'
        ),
    )
    parser.add_argument(
        '--ollama-endpoint',
        metavar='URL',
        default=os.environ.get('OLLAMA_ENDPOINT', ''),
        help='URL of an existing Ollama instance (skips install/start)',
    )
    parser.add_argument(
        '--output',
        metavar='FILE',
        default='benchmark-results.txt',
        help='File to write benchmark output to (default: benchmark-results.txt)',
    )
    parser.add_argument(
        '--no-xvfb',
        action='store_true',
        help='Disable automatic Xvfb virtual-display setup on Linux',
    )
    parser.add_argument(
        '--skip-install',
        action='store_true',
        help='Skip pip install step (assumes dependencies are already installed)',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    xvfb_proc = None
    ollama_proc = None

    try:
        # 1. Python dependencies
        if not args.skip_install:
            install_python_dependencies()

        # 2. Virtual display (Linux / headless)
        if not args.no_xvfb:
            xvfb_proc = start_xvfb()

        # 3. Mock-only benchmarks (always run)
        _banner('Running mock benchmarks')
        rc = run_benchmarks(args.output, append=False)
        if rc != 0:
            print(f'\nMock benchmarks failed (exit code {rc})')
            sys.exit(rc)

        # 4. Real Ollama benchmarks (opt-in)
        ollama_models_raw = args.ollama_models.strip()
        if ollama_models_raw:
            models = [m.strip() for m in ollama_models_raw.split(',') if m.strip()]
            endpoint = args.ollama_endpoint.strip()

            if endpoint:
                # Use an already-running instance
                print(f'\nUsing existing Ollama instance at {endpoint}')
            else:
                # Install + start Ollama ourselves
                if not shutil.which('ollama'):
                    install_ollama()
                ollama_proc = start_ollama_server()
                endpoint = 'http://localhost:11434'

            pull_ollama_models(models)

            _banner('Running real Ollama benchmarks')
            ollama_env = {
                'OLLAMA_ENDPOINT': endpoint,
                'OLLAMA_MODELS': ollama_models_raw,
            }
            rc = run_benchmarks(args.output, extra_env=ollama_env, append=True)
            if rc != 0:
                print(f'\nOllama benchmarks failed (exit code {rc})')
                sys.exit(rc)

        _banner('Benchmark complete')
        print(f'Results written to: {args.output}')

    finally:
        if ollama_proc is not None:
            ollama_proc.terminate()
        if xvfb_proc is not None:
            xvfb_proc.terminate()


if __name__ == '__main__':
    main()
