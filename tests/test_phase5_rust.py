import io
import time
from unittest.mock import patch
import base64

import pytest
from PIL import Image

try:
    import noclip_rs
    HAS_RUST = True
except ImportError:
    HAS_RUST = False

from utils.grid import _col_label, CELL_SIZE, LABEL_MARGIN, _build_cell_map, draw_grid_overlay
from utils.grid import _USE_RUST as GRID_USE_RUST
from utils.screen import _USE_RUST as SCREEN_USE_RUST

@pytest.fixture
def sample_image():
    # Create a 800x600 test image with some colors
    img = Image.new("RGBA", (800, 600), (100, 150, 200, 255))
    return img

def pure_python_build_cell_map(region, cell_size=CELL_SIZE):
    """The original pure-Python implementation for parity testing."""
    rx, ry, rw, rh = region
    cols = rw // cell_size
    rows = rh // cell_size

    cell_map = {}
    for c in range(cols):
        col_letter = _col_label(c)
        for r in range(rows):
            row_number = r + 1
            cell_name = f"{col_letter}{row_number}"
            cx = rx + c * cell_size + cell_size // 2
            cy = ry + r * cell_size + cell_size // 2
            cell_map[cell_name] = (cx, cy)
    return cell_map

def pure_python_encode_jpeg_b64(gridded_img: Image.Image) -> str:
    """The original pure-Python base64 JPEG encoder for parity testing."""
    buf = io.BytesIO()
    if gridded_img.mode == "RGBA":
        gridded_img = gridded_img.convert("RGB")
    gridded_img.save(buf, format="JPEG", quality=72)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

def test_rust_module_loaded():
    """Verify the Rust PyO3 module compiled and loaded successfully."""
    assert HAS_RUST is True, "noclip_rs module is not installed or failed to load"
    assert GRID_USE_RUST is True, "grid.py did not enable the Rust hotpath"
    assert SCREEN_USE_RUST is True, "screen.py did not enable the Rust hotpath"

def test_build_cell_map_parity():
    """Verify the Rust cell map matches the pure Python cell map exactly."""
    region = (100, 200, 1920, 1080)
    
    # Python
    py_map = pure_python_build_cell_map(region)
    
    # Rust (called via grid.py wrapper which now uses Rust)
    rs_map = _build_cell_map(region)
    
    assert len(py_map) == len(rs_map)
    assert py_map == rs_map

def test_draw_grid_overlay_parity(sample_image):
    """Verify the Rust grid overlay produces an image of the identical size as Python."""
    # Since fonts and antialiasing might render slightly differently between PIL and Rust's imageproc,
    # we only strictly assert the dimensions and pixel counts.
    
    # 1. Python path (mocking `_USE_RUST` to force pure python)
    with patch("utils.grid._USE_RUST", False):
        py_result = draw_grid_overlay(sample_image.copy())
    
    # 2. Rust path
    rs_result = draw_grid_overlay(sample_image.copy())
    
    assert py_result.size == rs_result.size
    assert py_result.mode == rs_result.mode
    
def test_encode_jpeg_b64_parity(sample_image):
    """Verify the Rust JPEG encoder outputs valid base64 that decodes to a valid image."""
    rs_b64 = noclip_rs.encode_jpeg_b64(sample_image.tobytes(), sample_image.width, sample_image.height, 72)
    
    # Decode it back and verify it's a valid JPEG
    img_data = base64.b64decode(rs_b64)
    img = Image.open(io.BytesIO(img_data))
    assert img.format == "JPEG"
    assert img.size == sample_image.size

@pytest.mark.skipif(not HAS_RUST, reason="Rust module not available")
def test_performance_benchmark():
    """Ensure the Rust implementations are measurably faster for grid logic."""
    region = (0, 0, 1920, 1080)
    
    # Benchmark grid logic (pure python loop)
    py_start = time.perf_counter()
    for _ in range(500):
        pure_python_build_cell_map(region)
    py_time = time.perf_counter() - py_start
    
    # Rust logic
    rs_start = time.perf_counter()
    for _ in range(500):
        _build_cell_map(region)
    rs_time = time.perf_counter() - rs_start
    
    print(f"\nGrid Calculation Benchmark (500 iterations, 1920x1080):")
    print(f"  Python: {py_time:.4f}s")
    print(f"  Rust:   {rs_time:.4f}s")
    print(f"  Speedup: {py_time / rs_time:.1f}x")
    
    # Rust should easily be 2x+ faster on these pure loops
    assert rs_time < py_time * 0.8  
