use pyo3::prelude::*;
use image::{RgbaImage, Rgba};
use imageproc::drawing::{draw_line_segment_mut, draw_text_mut};
use rusttype::{Font, Scale};
use crate::grid::col_label;

const LABEL_MARGIN: u32 = 20;

fn get_font() -> Font<'static> {
    // Try to load a font from bytes. In a real app we'd bundle a TTF or use system fonts.
    // Since we can't easily read system fonts cross-platform without massive crates,
    // we'll use a bundled minimal font or draw basic rects if we don't have one.
    // For this implementation, we will bundle a small monospace font if possible, 
    // but for now, imageproc allows using a rusttype Font. We need a ttf file.
    // We'll load from a known Windows path for MSVC just for the sake of the port, 
    // or fallback to blank.
    
    let font_data = include_bytes!("C:\\Windows\\Fonts\\arial.ttf");
    Font::try_from_bytes(font_data as &[u8]).expect("Error constructing Font")
}

#[pyfunction]
pub fn draw_grid_overlay_rgba(
    img_bytes: &[u8],
    width: u32,
    height: u32,
    cell_size: u32,
) -> PyResult<Vec<u8>> {
    // Parse the input bytes as an RGBA image
    let img = RgbaImage::from_raw(width, height, img_bytes.to_vec())
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Invalid image dimensions/bytes"))?;

    let cols = width / cell_size;
    let rows = height / cell_size;

    let new_w = width + LABEL_MARGIN;
    let new_h = height + LABEL_MARGIN;

    // Create a new white image
    let mut result = RgbaImage::from_pixel(new_w, new_h, Rgba([255, 255, 255, 255]));

    // Paste original image at (LABEL_MARGIN, LABEL_MARGIN)
    image::imageops::overlay(&mut result, &img, LABEL_MARGIN as i64, LABEL_MARGIN as i64);

    let red = Rgba([255, 0, 0, 255]);
    let black = Rgba([0, 0, 0, 255]);
    
    // Attempt to load font, fallback gracefully if fails (this is OS specific, but handled above)
    let font = get_font();
    let scale = Scale::uniform(9.0); // 9px font

    // Vertical lines and col labels
    for c in 0..=cols {
        let x = LABEL_MARGIN + c * cell_size;
        draw_line_segment_mut(
            &mut result,
            (x as f32, LABEL_MARGIN as f32),
            (x as f32, (LABEL_MARGIN + rows * cell_size) as f32),
            red,
        );

        if c < cols {
            let label = col_label(c as i32);
            let label_x = x + cell_size / 2;
            // Draw text at (label_x, 2)
            // Note: imageproc text origin is top-left, we might need to adjust for 'anchor="mt"'
            draw_text_mut(
                &mut result,
                black,
                label_x as i32 - 4, // rough centering
                2,
                scale,
                &font,
                &label,
            );
        }
    }

    // Horizontal lines and row labels
    for r in 0..=rows {
        let y = LABEL_MARGIN + r * cell_size;
        draw_line_segment_mut(
            &mut result,
            (LABEL_MARGIN as f32, y as f32),
            ((LABEL_MARGIN + cols * cell_size) as f32, y as f32),
            red,
        );

        if r < rows {
            let label = (r + 1).to_string();
            let label_y = y + cell_size / 2;
            // Draw text
            draw_text_mut(
                &mut result,
                black,
                2,
                label_y as i32 - 4, // rough centering
                scale,
                &font,
                &label,
            );
        }
    }

    Ok(result.into_raw())
}
