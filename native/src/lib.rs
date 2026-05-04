use numpy::{PyArray1, PyArray2, PyArray3, PyReadonlyArray1, PyReadonlyArray2, IntoPyArray,
            PyArrayMethods, PyUntypedArrayMethods};
use pyo3::prelude::*;
use rustfft::{FftPlanner, num_complex::Complex};
use std::cell::RefCell;

thread_local! {
    static PLANNER: RefCell<FftPlanner<f32>> = RefCell::new(FftPlanner::new());
}

// ── Spectrogram Colormap ────────────────────────────────────────────────────

/// Apply a 256-entry RGB LUT to spectrogram history columns and write into buffer_data.
///
/// history:     (history_len, display_h)  f32 in [0, 1]
/// lut:         (256, 3)                  u8  RGB
/// buffer_data: (display_h, history_len, 3) u8  BGR output (Qt RGB888)
/// start_col, end_col: column range to update (wrapping around history_len)
#[pyfunction]
fn apply_colormap<'py>(
    _py: Python<'py>,
    history: PyReadonlyArray2<'py, f32>,
    lut: PyReadonlyArray2<'py, u8>,
    buffer_data: &Bound<'py, PyArray3<u8>>,
    start_col: usize,
    end_col: usize,
    history_len: usize,
) -> PyResult<()> {
    let hist = history.as_array();
    let lut_arr = lut.as_array();
    let mut buf = unsafe { buffer_data.as_array_mut() };
    let display_h = buf.shape()[0];

    for raw_idx in start_col..end_col {
        let col = raw_idx % history_len;
        let column = hist.row(col);

        for y in 0..display_h {
            let val = column[y];
            let idx = ((val * 255.0) as i32).clamp(0, 255) as usize;
            // Write reversed (bottom-to-top → top-to-bottom)
            let ry = display_h - 1 - y;
            buf[[ry, col, 0]] = lut_arr[[idx, 0]];
            buf[[ry, col, 1]] = lut_arr[[idx, 1]];
            buf[[ry, col, 2]] = lut_arr[[idx, 2]];
        }
    }
    Ok(())
}


// ── Spectrogram Column Generation ───────────────────────────────────────────

/// Generate a spectrogram column from FFT magnitude data.
///
/// norm:      normalized magnitude [0, 1] per bin
/// px_int:    pixel index mapping for each bin (into display_h)
/// display_h: height of the spectrogram display
///
/// Returns: column array of shape (display_h,) f32
#[pyfunction]
fn generate_spectrogram_column<'py>(
    py: Python<'py>,
    norm: PyReadonlyArray1<'py, f32>,
    px_int: PyReadonlyArray1<'py, i32>,
    n_bins: usize,
    display_h: usize,
) -> PyResult<Bound<'py, PyArray1<f32>>> {
    let norm_arr = norm.as_array();
    let px_arr = px_int.as_array();
    let mut column = vec![0.0f32; display_h];

    let limit = n_bins.min(norm_arr.len()).min(px_arr.len());

    // Maximum scatter
    for i in 0..limit {
        let px = px_arr[i] as usize;
        if px < display_h {
            let val = norm_arr[i];
            if val > column[px] {
                column[px] = val;
            }
        }
    }

    // Linear interpolation to fill gaps between non-zero entries
    let mut first_nz: Option<usize> = None;
    let mut last_nz: Option<usize> = None;
    for i in 0..display_h {
        if column[i] > 0.0 {
            if first_nz.is_none() {
                first_nz = Some(i);
            }
            last_nz = Some(i);
        }
    }

    if let (Some(first), Some(last)) = (first_nz, last_nz) {
        if last > first {
            // Find all non-zero positions
            let mut nz_positions: Vec<usize> = Vec::new();
            let mut nz_values: Vec<f32> = Vec::new();
            for i in first..=last {
                if column[i] > 0.0 {
                    nz_positions.push(i);
                    nz_values.push(column[i]);
                }
            }

            // Interpolate between consecutive non-zero entries
            for seg in 0..nz_positions.len() - 1 {
                let p0 = nz_positions[seg];
                let p1 = nz_positions[seg + 1];
                let v0 = nz_values[seg];
                let v1 = nz_values[seg + 1];
                if p1 > p0 + 1 {
                    let span = (p1 - p0) as f32;
                    for j in (p0 + 1)..p1 {
                        let t = (j - p0) as f32 / span;
                        let interp = v0 + t * (v1 - v0);
                        if interp > column[j] {
                            column[j] = interp;
                        }
                    }
                }
            }
        }
    }

    Ok(column.into_pyarray(py).into())
}


// ── Circular Buffer Write ───────────────────────────────────────────────────

/// Write filtered + raw audio data into circular buffers (for LoudnessMeter).
///
/// Replaces the Python per-sample loop with a bulk memcpy.
/// buffer:      (buf_len, channels) f64  — K-weighted circular buffer
/// raw_buffer:  (buf_len, channels) f64  — raw circular buffer
/// filtered:    (n_samples, channels) f64 — new K-weighted data
/// raw_data:    (n_samples, channels) f64 — new raw data
/// buf_pos:     current write position
///
/// Returns: new buf_pos after writing
#[pyfunction]
fn circular_buffer_write<'py>(
    _py: Python<'py>,
    buffer: &Bound<'py, PyArray2<f64>>,
    raw_buffer: &Bound<'py, PyArray2<f64>>,
    filtered: PyReadonlyArray2<'py, f64>,
    raw_data: PyReadonlyArray2<'py, f64>,
    buf_pos: usize,
) -> PyResult<usize> {
    let mut buf = unsafe { buffer.as_array_mut() };
    let mut raw_buf = unsafe { raw_buffer.as_array_mut() };
    let filt = filtered.as_array();
    let raw = raw_data.as_array();

    let buf_len = buf.shape()[0];
    let channels = buf.shape()[1].min(filt.shape()[1]);
    let n = filt.shape()[0];
    let mut pos = buf_pos;

    // Bulk write — if the block fits without wrapping, do a single slice copy
    let end_pos = pos + n;
    if end_pos <= buf_len {
        for c in 0..channels {
            for i in 0..n {
                buf[[pos + i, c]] = filt[[i, c]];
                raw_buf[[pos + i, c]] = raw[[i, c]];
            }
        }
        pos = end_pos;
    } else {
        // Wrapping write
        for i in 0..n {
            let wp = (pos + i) % buf_len;
            for c in 0..channels {
                buf[[wp, c]] = filt[[i, c]];
                raw_buf[[wp, c]] = raw[[i, c]];
            }
        }
        pos = (pos + n) % buf_len;
    }

    Ok(pos)
}


// ── Waveform Chunk Reduction ────────────────────────────────────────────────

/// Reduce audio data into min/max/rms per chunk for waveform display.
///
/// data:       (n_samples, channels) f32
/// chunk_size: number of samples per output pixel
///
/// Returns: (max_buf, min_buf, rms_buf) each (n_chunks, channels) f32
#[pyfunction]
fn waveform_reduce<'py>(
    py: Python<'py>,
    data: PyReadonlyArray2<'py, f32>,
    chunk_size: usize,
) -> PyResult<(
    Bound<'py, PyArray2<f32>>,
    Bound<'py, PyArray2<f32>>,
    Bound<'py, PyArray2<f32>>,
)> {
    let arr = data.as_array();
    let n = arr.shape()[0];
    let channels = arr.shape()[1];
    let chunk_size = chunk_size.max(1);
    let n_chunks = (n + chunk_size - 1) / chunk_size;

    let mut max_buf = vec![0.0f32; n_chunks * channels];
    let mut min_buf = vec![0.0f32; n_chunks * channels];
    let mut rms_buf = vec![0.0f32; n_chunks * channels];

    for chunk_idx in 0..n_chunks {
        let start = chunk_idx * chunk_size;
        let end = (start + chunk_size).min(n);
        let len = end - start;
        if len == 0 {
            continue;
        }

        for c in 0..channels {
            let mut mx = f32::NEG_INFINITY;
            let mut mn = f32::INFINITY;
            let mut sum_sq = 0.0f32;

            for i in start..end {
                let v = arr[[i, c]];
                if v > mx { mx = v; }
                if v < mn { mn = v; }
                sum_sq += v * v;
            }

            let idx = chunk_idx * channels + c;
            max_buf[idx] = mx;
            min_buf[idx] = mn;
            rms_buf[idx] = (sum_sq / len as f32).sqrt();
        }
    }

    let max_arr = numpy::ndarray::Array2::from_shape_vec((n_chunks, channels), max_buf)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let min_arr = numpy::ndarray::Array2::from_shape_vec((n_chunks, channels), min_buf)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let rms_arr = numpy::ndarray::Array2::from_shape_vec((n_chunks, channels), rms_buf)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    Ok((
        max_arr.into_pyarray(py).into(),
        min_arr.into_pyarray(py).into(),
        rms_arr.into_pyarray(py).into(),
    ))
}


// ── Colormap Builder ────────────────────────────────────────────────────────

/// Build a 256-entry RGB LUT from a list of (position, r, g, b) stops.
///
/// stops: list of (f32, u8, u8, u8) — position [0..1] and RGB values
///
/// Returns: (256, 3) u8 array
#[pyfunction]
fn build_colormap<'py>(
    py: Python<'py>,
    stops: Vec<(f32, u8, u8, u8)>,
) -> PyResult<Bound<'py, PyArray2<u8>>> {
    let n = 256usize;
    let mut lut = vec![0u8; n * 3];

    for i in 0..n {
        let t = i as f32 / (n - 1) as f32;

        for j in 0..stops.len() - 1 {
            let (t0, r0, g0, b0) = stops[j];
            let (t1, r1, g1, b1) = stops[j + 1];
            if t >= t0 && t <= t1 {
                let frac = if t1 > t0 { (t - t0) / (t1 - t0) } else { 0.0 };
                lut[i * 3] = (r0 as f32 + (r1 as f32 - r0 as f32) * frac) as u8;
                lut[i * 3 + 1] = (g0 as f32 + (g1 as f32 - g0 as f32) * frac) as u8;
                lut[i * 3 + 2] = (b0 as f32 + (b1 as f32 - b0 as f32) * frac) as u8;
                break;
            }
        }
    }

    let arr = numpy::ndarray::Array2::from_shape_vec((n, 3), lut)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok(arr.into_pyarray(py).into())
}


// ── Stereo Correlation ──────────────────────────────────────────────────────

/// Compute stereo correlation coefficient.
/// Returns value in [-1, +1]. +1 = mono, 0 = unrelated, -1 = out of phase.
#[pyfunction]
fn correlation<'py>(
    _py: Python<'py>,
    left: PyReadonlyArray1<'py, f32>,
    right: PyReadonlyArray1<'py, f32>,
) -> PyResult<f64> {
    let l = left.as_array();
    let r = right.as_array();
    let n = l.len().min(r.len());

    let mut l_energy = 0.0f64;
    let mut r_energy = 0.0f64;
    let mut cross = 0.0f64;

    for i in 0..n {
        let lv = l[i] as f64;
        let rv = r[i] as f64;
        l_energy += lv * lv;
        r_energy += rv * rv;
        cross += lv * rv;
    }

    let denom = (l_energy * r_energy).sqrt();
    if denom < 1e-20 {
        Ok(0.0)
    } else {
        Ok(cross / denom)
    }
}


// ── Audio Gain Application ──────────────────────────────────────────────────

/// Apply gain multiplier to audio blocks in-place.
/// blocks: list of (n_samples, channels) f32 arrays
/// Returns: concatenated result as single array
#[pyfunction]
fn apply_gain_and_concat<'py>(
    py: Python<'py>,
    blocks: Vec<PyReadonlyArray2<'py, f32>>,
    gain: f32,
    target_channels: usize,
) -> PyResult<Bound<'py, PyArray2<f32>>> {
    // Calculate total size
    let total_samples: usize = blocks.iter().map(|b| b.shape()[0]).sum();
    if total_samples == 0 || blocks.is_empty() {
        let empty = numpy::ndarray::Array2::<f32>::zeros((0, target_channels));
        return Ok(empty.into_pyarray(py).into());
    }

    let mut result = vec![0.0f32; total_samples * target_channels];
    let mut offset = 0;

    for block in &blocks {
        let arr = block.as_array();
        let n = arr.shape()[0];
        let ch = arr.shape()[1].min(target_channels);

        if gain == 1.0 {
            for i in 0..n {
                for c in 0..ch {
                    result[(offset + i) * target_channels + c] = arr[[i, c]];
                }
            }
        } else {
            for i in 0..n {
                for c in 0..ch {
                    result[(offset + i) * target_channels + c] = arr[[i, c]] * gain;
                }
            }
        }
        offset += n;
    }

    let arr = numpy::ndarray::Array2::from_shape_vec((total_samples, target_channels), result)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok(arr.into_pyarray(py).into())
}


// ── FFT Processing ──────────────────────────────────────────────────────────

/// Compute the magnitude spectrum of audio data.
/// Returns (magnitude_db)
#[pyfunction]
fn compute_fft<'py>(
    py: Python<'py>,
    data: PyReadonlyArray1<'py, f32>,
    window: PyReadonlyArray1<'py, f32>,
    fft_size: usize,
) -> PyResult<Bound<'py, PyArray1<f32>>> {
    let input = data.as_array();
    let win = window.as_array();
    
    let n = input.len().min(fft_size).min(win.len());
    
    let mut buffer = vec![Complex { re: 0.0, im: 0.0 }; fft_size];
    for i in 0..n {
        buffer[i].re = input[i] * win[i];
    }
    
    PLANNER.with(|planner| {
        let fft = planner.borrow_mut().plan_fft_forward(fft_size);
        fft.process(&mut buffer);
    });
    
    let out_size = fft_size / 2 + 1;
    let mut mag_db = vec![0.0f32; out_size];
    
    let norm = fft_size as f32 / 4.0;
    
    for i in 0..out_size {
        let mag = (buffer[i].re * buffer[i].re + buffer[i].im * buffer[i].im).sqrt();
        let mut m = mag / norm;
        if m < 1e-10 { m = 1e-10; }
        mag_db[i] = 20.0 * m.log10();
    }
    
    let arr = numpy::ndarray::Array1::from_vec(mag_db);
    Ok(arr.into_pyarray(py).into())
}


// ── Module Registration ─────────────────────────────────────────────────────

#[pymodule]
fn dsp_accel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(apply_colormap, m)?)?;
    m.add_function(wrap_pyfunction!(generate_spectrogram_column, m)?)?;
    m.add_function(wrap_pyfunction!(circular_buffer_write, m)?)?;
    m.add_function(wrap_pyfunction!(waveform_reduce, m)?)?;
    m.add_function(wrap_pyfunction!(build_colormap, m)?)?;
    m.add_function(wrap_pyfunction!(correlation, m)?)?;
    m.add_function(wrap_pyfunction!(apply_gain_and_concat, m)?)?;
    m.add_function(wrap_pyfunction!(compute_fft, m)?)?;
    Ok(())
}
