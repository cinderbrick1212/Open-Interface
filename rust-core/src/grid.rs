use pyo3::prelude::*;
use std::collections::HashMap;

pub fn col_label(mut index: i32) -> String {
    let mut label = String::new();
    loop {
        let remainder = index % 26;
        let char_code = b'A' + remainder as u8;
        label.insert(0, char_code as char);
        index = (index / 26) - 1;
        if index < 0 {
            break;
        }
    }
    label
}

pub fn build_cell_map_core(
    rx: i32,
    ry: i32,
    rw: i32,
    rh: i32,
    cell_size: i32,
) -> HashMap<String, (i32, i32)> {
    let cols = rw / cell_size;
    let rows = rh / cell_size;

    let mut cell_map = HashMap::with_capacity((cols * rows) as usize);

    for c in 0..cols {
        let col_letter = col_label(c);
        for r in 0..rows {
            let row_number = r + 1;
            let cell_name = format!("{}{}", col_letter, row_number);
            
            let cx = rx + c * cell_size + cell_size / 2;
            let cy = ry + r * cell_size + cell_size / 2;
            
            cell_map.insert(cell_name, (cx, cy));
        }
    }

    cell_map
}

#[pyfunction]
pub fn build_cell_map(rx: i32, ry: i32, rw: i32, rh: i32, cell_size: i32) -> PyResult<HashMap<String, (i32, i32)>> {
    Ok(build_cell_map_core(rx, ry, rw, rh, cell_size))
}
