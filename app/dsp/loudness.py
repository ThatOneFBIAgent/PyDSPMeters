"""
Loudness measurement utilities: LUFS (EBU R128), RMS, and True Peak.
Implements K-weighting filters and gated loudness calculation.
"""

import numpy as np
from scipy.signal import sosfilt, butter
from app.dsp import accel as dsp_accel


def design_k_weighting(sample_rate: float) -> np.ndarray:
    """
    Design K-weighting filter as second-order sections (SOS).
    K-weighting per ITU-R BS.1770-4:
      Stage 1: High-shelf boost (~+4 dB, f0 ≈ 1682 Hz)
      Stage 2: High-pass filter (f0 ≈ 38 Hz)

    Returns:
        SOS array suitable for scipy.signal.sosfilt.
    """
    # Stage 1: High shelf
    # Official coefficients derived for 48kHz, but we recalculate for sample_rate
    f0 = 1681.97445095229
    G = 3.999843853973347
    Q = 0.7071752369554193
    
    A = 10 ** (G / 40.0)
    w0 = 2 * np.pi * f0 / sample_rate
    alpha = np.sin(w0) / (2 * Q)

    b0 = A * ((A + 1) + (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha)
    b1 = -2 * A * ((A - 1) + (A + 1) * np.cos(w0))
    b2 = A * ((A + 1) + (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha)
    a0 = (A + 1) - (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha
    a1 = 2 * ((A - 1) - (A + 1) * np.cos(w0))
    a2 = (A + 1) - (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha

    sos_shelf = np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]])

    # Stage 2: High-pass (Recalculated for better BS.1770 matching)
    f0_hp = 38.13547087602444
    Q_hp = 0.5003270373253902 # Not 0.707 for BS.1770
    
    w0_hp = 2 * np.pi * f0_hp / sample_rate
    alpha_hp = np.sin(w0_hp) / (2 * Q_hp)
    
    b0_hp = (1 + np.cos(w0_hp)) / 2
    b1_hp = -(1 + np.cos(w0_hp))
    b2_hp = (1 + np.cos(w0_hp)) / 2
    a0_hp = 1 + alpha_hp
    a1_hp = -2 * np.cos(w0_hp)
    a2_hp = 1 - alpha_hp
    
    sos_hp = np.array([[b0_hp / a0_hp, b1_hp / a0_hp, b2_hp / a0_hp, 1.0, a1_hp / a0_hp, a2_hp / a0_hp]])

    return np.vstack([sos_shelf, sos_hp])


class LoudnessMeter:
    """
    Real-time loudness meter implementing EBU R128 (LUFS) and RMS.

    Maintains rolling buffers for:
      - Momentary (400 ms window)
      - Short-term (3 s window)
      - RMS Momentary (~400 ms)
      - RMS Short-term (~3 s)
    """

    def __init__(self, sample_rate: float = 44100.0, channels: int = 2):
        self.sample_rate = sample_rate
        self.channels = channels
        self._sos = design_k_weighting(sample_rate)

        # Filter state for each channel
        self._zi = [np.zeros((self._sos.shape[0], 2)) for _ in range(channels)]

        # Rolling buffers
        self._momentary_samples = int(0.4 * sample_rate)  # 400 ms
        self._shortterm_samples = int(3.0 * sample_rate)  # 3 s

        self._buffer = np.zeros((self._shortterm_samples, channels), dtype=np.float64)
        self._raw_buffer = np.zeros((self._shortterm_samples, channels), dtype=np.float64)
        self._buf_pos = 0
        self._buf_filled = 0

        # Gated Integrated Loudness state
        self._integrated_blocks = [] # List of 400ms (75% overlap) mean square values
        self._int_block_size = int(0.4 * sample_rate)
        self._int_step_size = int(0.1 * sample_rate) # 75% overlap
        self._int_accum_samples = 0

    def process(self, data: np.ndarray):
        """Feed new audio data into the meter."""
        if data.ndim == 1:
            data = data[:, np.newaxis]
        n = data.shape[0]
        ch = min(data.shape[1], self.channels)

        # Apply K-weighting per channel
        filtered = np.zeros_like(data[:, :ch], dtype=np.float64)
        for c in range(ch):
            filtered[:, c], self._zi[c] = sosfilt(
                self._sos, data[:, c].astype(np.float64), zi=self._zi[c]
            )

        # Write to circular buffers
        self._buf_pos = dsp_accel.circular_buffer_write(
            self._buffer, self._raw_buffer, filtered, 
            data[:, :ch].astype(np.float64), self._buf_pos
        )
        self._buf_filled = min(self._buf_filled + n, self._shortterm_samples)

        # Integrated Accumulation
        self._int_accum_samples += n
        if self._int_accum_samples >= self._int_step_size:
            self._update_integrated_blocks()
            self._int_accum_samples %= self._int_step_size

    def _update_integrated_blocks(self):
        """Calculate mean square for the last 400ms and store for gated average."""
        ms = self._mean_square_lufs(self._int_block_size)
        if ms > 0:
            self._integrated_blocks.append(ms)
            # Keep history to ~1 hour to prevent memory leaks
            if len(self._integrated_blocks) > 36000: # 1 hour at 0.1s steps
                self._integrated_blocks.pop(0)

    def reset_integrated(self):
        """Reset the integrated loudness calculation."""
        self._integrated_blocks = []

    def _get_last_n(self, buf: np.ndarray, n_samples: int) -> np.ndarray:
        """Extract last n_samples from circular buffer."""
        available = min(n_samples, self._buf_filled)
        if available == 0:
            return np.zeros((1, self.channels), dtype=np.float64)
        end = self._buf_pos % self._shortterm_samples
        if end >= available:
            return buf[end - available:end].copy()
        else:
            return np.concatenate([buf[-(available - end):], buf[:end]])

    def _mean_square_lufs(self, n_samples: int) -> float:
        """Compute mean square of K-weighted signal over window."""
        segment = self._get_last_n(self._buffer, n_samples)
        ms_per_ch = np.mean(segment ** 2, axis=0)
        # ITU-R BS.1770 weights: 1.0 for main channels, 1.41 for surrounds (not implemented)
        return float(np.sum(ms_per_ch))

    def _rms_db(self, n_samples: int) -> float:
        """Compute RMS in dB over raw signal."""
        segment = self._get_last_n(self._raw_buffer, n_samples)
        ms = np.mean(segment ** 2)
        if ms < 1e-20:
            return -120.0
        return float(10.0 * np.log10(ms))

    @property
    def lufs_momentary(self) -> float:
        """Momentary loudness (400 ms) in LUFS."""
        ms = self._mean_square_lufs(self._momentary_samples)
        if ms < 1e-20:
            return -120.0
        return -0.691 + 10.0 * np.log10(ms)

    @property
    def lufs_shortterm(self) -> float:
        """Short-term loudness (3 s) in LUFS."""
        ms = self._mean_square_lufs(self._shortterm_samples)
        if ms < 1e-20:
            return -120.0
        return -0.691 + 10.0 * np.log10(ms)

    @property
    def lufs_integrated(self) -> float:
        """Gated Integrated Loudness per ITU-R BS.1770-4."""
        if not self._integrated_blocks:
            return -120.0
        
        blocks = np.array(self._integrated_blocks)
        # 1. Absolute Threshold (-70 LUFS)
        abs_thresh = 10**((-70 + 0.691) / 10.0)
        indices = np.where(blocks > abs_thresh)[0]
        if len(indices) == 0: return -120.0
        
        # 2. Relative Threshold (-10 LU relative to absolute-gated average)
        gated_abs = blocks[indices]
        avg_abs = np.mean(gated_abs)
        rel_thresh = avg_abs * (10**(-10/10.0))
        
        indices_rel = np.where(gated_abs > rel_thresh)[0]
        if len(indices_rel) == 0: return -120.0
        
        final_avg = np.mean(gated_abs[indices_rel])
        return -0.691 + 10.0 * np.log10(final_avg)

    @property
    def lufs_momentary_channels(self) -> np.ndarray:
        segment = self._get_last_n(self._buffer, self._momentary_samples)
        ms = np.mean(segment**2, axis=0)
        return -0.691 + 10.0 * np.log10(np.clip(ms, 1e-12, None))

    @property
    def lufs_shortterm_channels(self) -> np.ndarray:
        segment = self._get_last_n(self._buffer, self._shortterm_samples)
        ms = np.mean(segment**2, axis=0)
        return -0.691 + 10.0 * np.log10(np.clip(ms, 1e-12, None))

    @property
    def rms_momentary(self) -> float:
        """Momentary RMS (~400 ms) in dB."""
        return self._rms_db(self._momentary_samples)

    @property
    def rms_shortterm(self) -> float:
        """Short-term RMS (~3 s) in dB."""
        return self._rms_db(self._shortterm_samples)

    @property
    def rms_momentary_channels(self) -> np.ndarray:
        segment = self._get_last_n(self._raw_buffer, self._momentary_samples)
        ms = np.mean(segment**2, axis=0)
        return 10.0 * np.log10(np.clip(ms, 1e-12, None))

    @property
    def rms_shortterm_channels(self) -> np.ndarray:
        segment = self._get_last_n(self._raw_buffer, self._shortterm_samples)
        ms = np.mean(segment**2, axis=0)
        return 10.0 * np.log10(np.clip(ms, 1e-12, None))

    @property
    def true_peak(self) -> float:
        """True peak (oversampled) of the most recent buffer content in dBTP."""
        segment = self._get_last_n(self._raw_buffer, int(self.sample_rate * 0.1)) # 100ms window
        return float(np.max(self._calculate_tp_channels(segment)))

    @property
    def true_peak_channels(self) -> np.ndarray:
        segment = self._get_last_n(self._raw_buffer, int(self.sample_rate * 0.1))
        return self._calculate_tp_channels(segment)

    def _calculate_tp_channels(self, data: np.ndarray) -> np.ndarray:
        """Estimate True Peak via 4x oversampling."""
        if len(data) < 16:
            return np.zeros(data.shape[1]) - 120.0
        
        try:
            from scipy.signal import resample_poly
            # 4x oversampling is standard for 'true peak' estimation
            up = resample_poly(data, 4, 1, axis=0)
            peaks = np.max(np.abs(up), axis=0)
            return 20.0 * np.log10(np.clip(peaks, 1e-6, None))
        except:
            # Fallback to sample peak if scipy is having issues
            peaks = np.max(np.abs(data), axis=0)
            return 20.0 * np.log10(np.clip(peaks, 1e-6, None))
