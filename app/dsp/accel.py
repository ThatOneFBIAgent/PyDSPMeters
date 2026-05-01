"""
DSP Accelerator: Python wrapper with graceful fallback.

Imports the Rust-compiled `dsp_accel` module when available,
otherwise provides pure-Python/NumPy fallback implementations
so the application runs identically (just slower) without the
compiled native extension.
"""

import numpy as np

# ── Try to import the Rust accelerator ──────────────────────────────────────

_HAS_NATIVE = False
try:
    import dsp_accel as _native
    _HAS_NATIVE = True
except ImportError:
    _native = None


def is_accelerated() -> bool:
    """Returns True if the Rust DSP accelerator is loaded."""
    return _HAS_NATIVE


# ── Colormap ────────────────────────────────────────────────────────────────

def build_colormap(stops, n=256):
    """Build a 256-entry RGB LUT from heatmap stops.
    
    stops: list of (position_float, "#hexcolor") tuples
    Returns: (256, 3) uint8 numpy array
    """
    from PySide6.QtGui import QColor
    
    # Convert hex stops to (pos, r, g, b) tuples for Rust
    parsed = []
    for pos, color_str in stops:
        c = QColor(color_str)
        parsed.append((float(pos), c.red(), c.green(), c.blue()))
    
    if _HAS_NATIVE:
        return _native.build_colormap(parsed)
    
    # Pure Python fallback
    lut = np.zeros((n, 3), dtype=np.uint8)
    for i in range(n):
        t = i / (n - 1)
        for j in range(len(parsed) - 1):
            t0, r0, g0, b0 = parsed[j]
            t1, r1, g1, b1 = parsed[j + 1]
            if t0 <= t <= t1:
                frac = (t - t0) / (t1 - t0) if t1 > t0 else 0
                lut[i] = [
                    int(r0 + (r1 - r0) * frac),
                    int(g0 + (g1 - g0) * frac),
                    int(b0 + (b1 - b0) * frac),
                ]
                break
    return lut


def apply_colormap(history, lut, buffer_data, start_col, end_col, history_len):
    """Apply LUT to spectrogram history columns → buffer_data.
    
    history:     (history_len, display_h) f32
    lut:         (256, 3) u8
    buffer_data: (display_h, history_len, 3) u8 — modified in-place
    """
    if _HAS_NATIVE:
        _native.apply_colormap(history, lut, buffer_data, start_col, end_col, history_len)
        return
    
    # Pure Python fallback
    display_h = buffer_data.shape[0]
    for raw_idx in range(start_col, end_col):
        col = raw_idx % history_len
        indices = np.clip((history[col] * 255).astype(np.int32), 0, 255)
        rgb_col = lut[indices]
        buffer_data[:, col] = rgb_col[::-1]


# ── Spectrogram Column ──────────────────────────────────────────────────────

def generate_spectrogram_column(norm, px_int, n_bins, display_h):
    """Generate a spectrogram column from normalized FFT data.
    
    Returns: (display_h,) f32 array
    """
    if _HAS_NATIVE:
        return _native.generate_spectrogram_column(
            norm.astype(np.float32), px_int.astype(np.int32), n_bins, display_h
        )
    
    # Pure Python fallback
    column = np.zeros(display_h, dtype=np.float32)
    np.maximum.at(column, px_int[:n_bins], norm[:n_bins])
    
    nonzero = np.where(column > 0)[0]
    if len(nonzero) > 1:
        from scipy.interpolate import interp1d
        f = interp1d(nonzero, column[nonzero], kind='linear', fill_value="nearest")
        full_idx = np.arange(nonzero[0], nonzero[-1] + 1)
        column[full_idx] = np.maximum(column[full_idx], f(full_idx))
    
    return column


# ── Circular Buffer ─────────────────────────────────────────────────────────

def circular_buffer_write(buffer, raw_buffer, filtered, raw_data, buf_pos):
    """Write filtered + raw data into circular buffers.
    
    Returns: new buf_pos
    """
    if _HAS_NATIVE:
        return _native.circular_buffer_write(buffer, raw_buffer, filtered, raw_data, buf_pos)
    
    # Pure Python fallback
    buf_len = len(buffer)
    n = len(filtered)
    ch = min(buffer.shape[1], filtered.shape[1])
    for i in range(n):
        pos = (buf_pos + i) % buf_len
        buffer[pos, :ch] = filtered[i, :ch]
        raw_buffer[pos, :ch] = raw_data[i, :ch]
    return (buf_pos + n) % buf_len


# ── Waveform Reduction ──────────────────────────────────────────────────────

def waveform_reduce(data, chunk_size):
    """Reduce audio data into min/max/rms per chunk.
    
    Returns: (max_buf, min_buf, rms_buf) each (n_chunks, channels) f32
    """
    if _HAS_NATIVE:
        return _native.waveform_reduce(data.astype(np.float32), chunk_size)
    
    # Pure Python fallback
    n = len(data)
    chunk_size = max(1, chunk_size)
    n_chunks = (n + chunk_size - 1) // chunk_size
    channels = data.shape[1]
    
    max_buf = np.zeros((n_chunks, channels), dtype=np.float32)
    min_buf = np.zeros((n_chunks, channels), dtype=np.float32)
    rms_buf = np.zeros((n_chunks, channels), dtype=np.float32)
    
    for i in range(n_chunks):
        start = i * chunk_size
        end = min(start + chunk_size, n)
        chunk = data[start:end]
        if len(chunk) == 0:
            continue
        max_buf[i] = np.max(chunk, axis=0)
        min_buf[i] = np.min(chunk, axis=0)
        rms_buf[i] = np.sqrt(np.mean(chunk ** 2, axis=0))
    
    return max_buf, min_buf, rms_buf


# ── Correlation ─────────────────────────────────────────────────────────────

def correlation(left, right):
    """Compute stereo correlation coefficient [-1, +1]."""
    if _HAS_NATIVE:
        return _native.correlation(
            left.astype(np.float32), right.astype(np.float32)
        )
    
    # Pure Python fallback (numpy)
    l_energy = np.sum(left ** 2)
    r_energy = np.sum(right ** 2)
    denom = np.sqrt(l_energy * r_energy)
    if denom < 1e-20:
        return 0.0
    return float(np.sum(left * right) / denom)


# ── Gain + Concatenation ───────────────────────────────────────────────────

def apply_gain_and_concat(blocks, gain):
    """Apply gain to audio blocks and concatenate.
    
    blocks: list of (n, channels) f32 arrays
    gain: float multiplier
    Returns: single (total_n, channels) f32 array
    """
    if _HAS_NATIVE and blocks:
        f32_blocks = [b.astype(np.float32) if b.dtype != np.float32 else b for b in blocks]
        return _native.apply_gain_and_concat(f32_blocks, float(gain))
    
    # Pure Python fallback (numpy)
    if not blocks:
        return np.zeros((0, 2), dtype=np.float32)
    
    if gain != 1.0:
        blocks = [b * gain for b in blocks]
    return np.concatenate(blocks)
