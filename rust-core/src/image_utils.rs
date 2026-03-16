use base64::prelude::*;
use image::{codecs::jpeg::JpegEncoder, RgbaImage};
use pyo3::prelude::*;
use std::io::Cursor;

#[pyfunction]
pub fn encode_jpeg_b64(img_bytes: &[u8], width: u32, height: u32, quality: u8) -> PyResult<String> {
    // Parse the input bytes as an RGBA image
    let img = RgbaImage::from_raw(width, height, img_bytes.to_vec())
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("Invalid image dimensions/bytes"))?;

    // Since JPEG doesn't support alpha, convert RGBA to RGB (image crate handles this internally if needed,
    // or we can explicitly convert it)
    let dynamic_img = image::DynamicImage::ImageRgba8(img);
    let rgb_img = dynamic_img.to_rgb8();

    let mut cursor = Cursor::new(Vec::new());

    // Encode to JPEG
    let mut encoder = JpegEncoder::new_with_quality(&mut cursor, quality);
    encoder
        .encode_image(&rgb_img)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JPEG encode error: {}", e)))?;

    // Encode to Base64
    let buffer = cursor.into_inner();
    let b64_string = BASE64_STANDARD.encode(&buffer);

    Ok(b64_string)
}
