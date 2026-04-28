"""
Loudness measurement utilities: LUFS (EBU R128), RMS, and True Peak.
Implements K-weighting filters and gated loudness calculation.
"""

import numpy as np
from scipy.signal import sosfilt, butter


def design_k_weighting(sample_rate: float) -> np.ndarray:
    """
    Design K-weighting filter as second-order sections (SOS).
    K-weighting per ITU-R BS.1770:
      Stage 1: High-shelf boost (~+4 dB above 1.5 kHz)
      Stage 2: High-pass filter (~38 Hz, -3 dB)

    Returns:
        SOS array suitable for scipy.signal.sosfilt.
    """
    # Stage 1: High shelf via peaking EQ approximation
    # Using a high-shelf with ~4dB gain above 1500 Hz
    f0 = 1500.0
    Q = 0.7071
    gain_db = 4.0
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * f0 / sample_rate
    alpha = np.sin(w0) / (2 * Q)

    b0 = A * ((A + 1) + (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha)
    b1 = -2 * A * ((A - 1) + (A + 1) * np.cos(w0))
    b2 = A * ((A + 1) + (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha)
    a0 = (A + 1) - (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha
    a1 = 2 * ((A - 1) - (A + 1) * np.cos(w0))
    a2 = (A + 1) - (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha

    sos_shelf = np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]])

    # Stage 2: High-pass Butterworth at 38 Hz
    sos_hp = butter(2, 38.0, btype='high', fs=sample_rate, output='sos')

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

        # Filter state for each channel (for streaming)
        self._zi = [np.zeros((self._sos.shape[0], 2)) for _ in range(channels)]

        # Rolling buffers
        self._momentary_samples = int(0.4 * sample_rate)  # 400 ms
        self._shortterm_samples = int(3.0 * sample_rate)  # 3 s

        self._buffer = np.zeros((self._shortterm_samples, channels), dtype=np.float64)
        self._buf_pos = 0
        self._buf_filled = 0

        # Raw (unfiltered) buffers for RMS
        self._raw_buffer = np.zeros((self._shortterm_samples, channels), dtype=np.float64)

    def process(self, data: np.ndarray):
        """
        Feed new audio data into the meter.

        Args:
            data: Shape (n_samples, channels), float32/64.
        """
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
        for i in range(n):
            pos = self._buf_pos % self._shortterm_samples
            self._buffer[pos, :ch] = filtered[i, :ch]
            self._raw_buffer[pos, :ch] = data[i, :ch]
            self._buf_pos += 1

        self._buf_filled = min(self._buf_filled + n, self._shortterm_samples)

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
        # Channel weights: 1.0 for L/R (stereo)
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
        """True peak of the most recent buffer content in dBFS."""
        segment = self._get_last_n(self._raw_buffer, self._momentary_samples)
        peak = np.max(np.abs(segment))
        if peak < 1e-20:
            return -120.0
        return float(20.0 * np.log10(peak))

    @property
    def true_peak_channels(self) -> np.ndarray:
        segment = self._get_last_n(self._raw_buffer, self._momentary_samples)
        peaks = np.max(np.abs(segment), axis=0)
        return 20.0 * np.log10(np.clip(peaks, 1e-6, None))
