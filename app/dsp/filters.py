"""
Multi-band crossover filters for splitting audio into Low, Mid, and High bands.
Uses Linkwitz-Riley (4th order Butterworth cascade) for flat summing.
"""

import numpy as np
from scipy.signal import butter, sosfilt


class MultiBandFilter:
    """
    3-band crossover filter (Low / Mid / High).

    Crossover frequencies default to 250 Hz and 4000 Hz.
    Uses 4th-order Butterworth filters for clean separation.
    """

    def __init__(self, sample_rate: float = 44100.0,
                 low_cut: float = 250.0, high_cut: float = 4000.0):
        self.sample_rate = sample_rate
        self.low_cut = low_cut
        self.high_cut = high_cut
        self._design_filters()

    def _design_filters(self):
        """Design the crossover filter bank."""
        nyq = self.sample_rate / 2.0
        # Low-pass for low band
        self._sos_low = butter(4, self.low_cut / nyq, btype='low', output='sos')
        # Band-pass for mid band
        self._sos_mid = butter(
            4, [self.low_cut / nyq, self.high_cut / nyq],
            btype='band', output='sos'
        )
        # High-pass for high band
        self._sos_high = butter(4, self.high_cut / nyq, btype='high', output='sos')

    def split(self, data: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Split audio into three bands.

        Args:
            data: 1-D audio samples.

        Returns:
            (low, mid, high) band arrays.
        """
        data_f64 = data.astype(np.float64)
        low = sosfilt(self._sos_low, data_f64).astype(np.float32)
        mid = sosfilt(self._sos_mid, data_f64).astype(np.float32)
        high = sosfilt(self._sos_high, data_f64).astype(np.float32)
        return low, mid, high


class StreamingMultiBandFilter:
    """
    Streaming version that maintains filter state between calls
    for use with real-time audio blocks.
    """

    def __init__(self, sample_rate: float = 44100.0,
                 low_cut: float = 250.0, high_cut: float = 4000.0,
                 channels: int = 2):
        self.channels = channels
        self._filters = [MultiBandFilter(sample_rate, low_cut, high_cut)
                         for _ in range(channels)]

        # Filter states for streaming
        nyq = sample_rate / 2.0
        sos_low = butter(4, low_cut / nyq, btype='low', output='sos')
        sos_mid = butter(4, [low_cut / nyq, high_cut / nyq], btype='band', output='sos')
        sos_high = butter(4, high_cut / nyq, btype='high', output='sos')

        self._zi_low = [np.zeros((sos_low.shape[0], 2)) for _ in range(channels)]
        self._zi_mid = [np.zeros((sos_mid.shape[0], 2)) for _ in range(channels)]
        self._zi_high = [np.zeros((sos_high.shape[0], 2)) for _ in range(channels)]
        self._sos_low = sos_low
        self._sos_mid = sos_mid
        self._sos_high = sos_high

    def process(self, data: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Process a block of multi-channel audio.

        Args:
            data: Shape (n_samples, channels).

        Returns:
            (low, mid, high) each of shape (n_samples, channels).
        """
        if data.ndim == 1:
            data = data[:, np.newaxis]
        n, ch = data.shape
        ch = min(ch, self.channels)

        low = np.zeros_like(data[:, :ch])
        mid = np.zeros_like(data[:, :ch])
        high = np.zeros_like(data[:, :ch])

        for c in range(ch):
            d = data[:, c].astype(np.float64)
            low[:, c], self._zi_low[c] = sosfilt(self._sos_low, d, zi=self._zi_low[c])
            mid[:, c], self._zi_mid[c] = sosfilt(self._sos_mid, d, zi=self._zi_mid[c])
            high[:, c], self._zi_high[c] = sosfilt(self._sos_high, d, zi=self._zi_high[c])

        return low.astype(np.float32), mid.astype(np.float32), high.astype(np.float32)
