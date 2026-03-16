"""Build helper for noclip_rs Rust crate.

Ensures the Rust toolchain is on PATH before invoking maturin.
Run from the project root: python rust-core/build.py
"""
import os
import subprocess
import sys

def main():
    # Ensure cargo/rustc are on PATH
    cargo_bin = os.path.join(os.path.expanduser("~"), ".cargo", "bin")
    env = os.environ.copy()
    env["PATH"] = cargo_bin + os.pathsep + env.get("PATH", "")
    env["PYO3_USE_ABI3_FORWARD_COMPATIBILITY"] = "1"
    
    crate_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"Building noclip_rs from {crate_dir}")
    print(f"Using cargo from: {cargo_bin}")
    
    # Verify rustc is accessible
    try:
        result = subprocess.run(
            ["rustc", "--version"], env=env, capture_output=True, text=True
        )
        print(f"rustc: {result.stdout.strip()}")
    except FileNotFoundError:
        print("ERROR: rustc not found. Install Rust via https://rustup.rs/")
        sys.exit(1)
    
    env["CARGO_BUILD_JOBS"] = "1"
    
    cmd = [sys.executable, "-m", "maturin", "develop", "--release"]
    print(f"Running maturin build in a retry loop to bypass Windows file locks...")
    
    max_retries = 25
    for attempt in range(1, max_retries + 1):
        print(f"\n[Attempt {attempt}/{max_retries}] {' '.join(cmd)}")
        proc = subprocess.run(cmd, env=env, cwd=crate_dir)
        if proc.returncode == 0:
            print("Maturin build succeeded!")
            break
        else:
            print(f"Maturin build failed (likely OS error 32). Retrying...")
    else:
        print("ERROR: Maturin build failed after maximum retries.")
        sys.exit(1)

if __name__ == "__main__":
    main()
