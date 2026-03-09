import base64
import io
import string

from PIL import Image, ImageDraw, ImageFont


CELL_SIZE = 24
LABEL_MARGIN = 20  # pixels reserved for row/column labels on the border

# Cache the font at module level so it is loaded from disk only once.
_cached_font = None


def _get_font():
    global _cached_font
    if _cached_font is None:
        try:
            _cached_font = ImageFont.truetype("arial.ttf", 9)
        except (OSError, IOError):
            try:
                _cached_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
            except (OSError, IOError):
                _cached_font = ImageFont.load_default()
    return _cached_font


def _col_label(index: int) -> str:
    """Convert 0-based column index to Excel-style letter label (A, B, ..., Z, AA, AB, ...)."""
    label = ""
    i = index
    while True:
        label = string.ascii_uppercase[i % 26] + label
        i = i // 26 - 1
        if i < 0:
            break
    return label


def _build_cell_map(region: tuple[int, int, int, int], cell_size: int = CELL_SIZE) -> dict[str, tuple[int, int]]:
    """
    Build a mapping from cell name (e.g. "A1") to the center screen coordinate of that cell.

    region: (x, y, width, height) of the captured area in screen coordinates.
    Returns dict like {"A1": (screen_x, screen_y), ...}
    """
    rx, ry, rw, rh = region
    cols = rw // cell_size
    rows = rh // cell_size

    cell_map = {}
    for c in range(cols):
        col_letter = _col_label(c)
        for r in range(rows):
            row_number = r + 1
            cell_name = f"{col_letter}{row_number}"
            # Center of this cell in screen coordinates
            cx = rx + c * cell_size + cell_size // 2
            cy = ry + r * cell_size + cell_size // 2
            cell_map[cell_name] = (cx, cy)

    return cell_map


def draw_grid_overlay(img: Image.Image, cell_size: int = CELL_SIZE) -> Image.Image:
    """
    Draw a grid overlay on the image with labeled borders.
    Returns a new image with the grid and labels drawn.
    """
    w, h = img.size
    cols = w // cell_size
    rows = h // cell_size

    # Create a new image with extra space for labels
    new_w = w + LABEL_MARGIN
    new_h = h + LABEL_MARGIN
    result = Image.new("RGB", (new_w, new_h), (255, 255, 255))
    result.paste(img, (LABEL_MARGIN, LABEL_MARGIN))

    draw = ImageDraw.Draw(result)
    font = _get_font()

    # Draw vertical grid lines and column labels
    for c in range(cols + 1):
        x = LABEL_MARGIN + c * cell_size
        # Grid line
        draw.line([(x, LABEL_MARGIN), (x, LABEL_MARGIN + rows * cell_size)],
                  fill=(255, 0, 0), width=1)
        # Column label at top
        if c < cols:
            label = _col_label(c)
            label_x = x + cell_size // 2
            draw.text((label_x, 2), label, fill=(0, 0, 0), font=font, anchor="mt")

    # Draw horizontal grid lines and row labels
    for r in range(rows + 1):
        y = LABEL_MARGIN + r * cell_size
        # Grid line
        draw.line([(LABEL_MARGIN, y), (LABEL_MARGIN + cols * cell_size, y)],
                  fill=(255, 0, 0), width=1)
        # Row label on left
        if r < rows:
            label = str(r + 1)
            label_y = y + cell_size // 2
            draw.text((2, label_y), label, fill=(0, 0, 0), font=font, anchor="lm")

    return result


def create_gridded_screenshot(img: Image.Image, region: tuple[int, int, int, int],
                              cell_size: int = CELL_SIZE) -> tuple[Image.Image, dict[str, tuple[int, int]]]:
    """
    Given a screenshot image and the screen region it was captured from,
    draw a grid overlay and return (gridded_image, cell_map).

    region: (x, y, width, height) in screen coordinates.
    cell_map: maps cell names like "A1" to (screen_x, screen_y) center coordinates.
    """
    gridded = draw_grid_overlay(img, cell_size)
    cell_map = _build_cell_map(region, cell_size)
    return gridded, cell_map


def gridded_screenshot_to_base64(gridded_img: Image.Image) -> str:
    """Convert a PIL Image to a base64-encoded JPEG string.

    Uses JPEG with quality=72 instead of lossless PNG to significantly reduce
    payload size and speed up API uploads with negligible quality loss for LLM
    vision tasks.
    """
    buf = io.BytesIO()
    # Convert RGBA to RGB if necessary (JPEG doesn't support alpha channel)
    if gridded_img.mode == "RGBA":
        gridded_img = gridded_img.convert("RGB")
    gridded_img.save(buf, format="JPEG", quality=72)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def get_grid_dimensions(region: tuple[int, int, int, int], cell_size: int = CELL_SIZE) -> str:
    """Return a human-readable description of the grid dimensions for context."""
    _, _, rw, rh = region
    cols = rw // cell_size
    rows = rh // cell_size
    last_col = _col_label(cols - 1) if cols > 0 else "A"
    return f"{cols} columns (A to {last_col}) x {rows} rows (1 to {rows}), each cell is {cell_size}x{cell_size} pixels"
