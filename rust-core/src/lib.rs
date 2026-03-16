use pyo3::prelude::*;

mod grid;
mod image_grid;
mod image_utils;

/// A Python module implemented in Rust for Noclip Desktop performance hotpaths.
#[pymodule]
fn noclip_rs(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(grid::build_cell_map, m)?)?;
    m.add_function(wrap_pyfunction!(image_grid::draw_grid_overlay_rgba, m)?)?;
    m.add_function(wrap_pyfunction!(image_utils::encode_jpeg_b64, m)?)?;
    Ok(())
}
