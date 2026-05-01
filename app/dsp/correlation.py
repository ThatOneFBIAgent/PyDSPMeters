"""
Stereo correlation and phase analysis utilities.
Provides single-band and multi-band correlation metering.
"""

import numpy as np
from app.dsp import accel as dsp_accel


def correlation(left: np.ndarray, right: np.ndarray) -> float:
    """
    Compute stereo correlation coefficient.

    Returns:
        Value in [-1, +1]. +1 = mono, 0 = unrelated, -1 = out of phase.
    """
    return dsp_accel.correlation(left, right)


def multiband_correlation(left: np.ndarray, right: np.ndarray,
                          sample_rate: float,
                          bands: list[tuple[float, float]] | None = None
                          ) -> dict[str, float]:
    """
    Compute correlation per frequency band using FFT-based band isolation.

    Args:
        left: Left channel samples.
        right: Right channel samples.
        sample_rate: Sample rate in Hz.
        bands: List of (low_hz, high_hz) tuples. Defaults to Low/Mid/High.

    Returns:
        Dict mapping band name to correlation value.
    """
    if bands is None:
        bands_named = [
            ("low", 20.0, 250.0),
            ("mid", 250.0, 4000.0),
            ("high", 4000.0, 20000.0),
        ]
    else:
        bands_named = [(f"band_{i}", lo, hi) for i, (lo, hi) in enumerate(bands)]

    n = len(left)
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate)
    L = np.fft.rfft(left)
    R = np.fft.rfft(right)

    results = {}
    for name, lo, hi in bands_named:
        mask = (freqs >= lo) & (freqs < hi)
        l_band = np.fft.irfft(L * mask, n=n)
        r_band = np.fft.irfft(R * mask, n=n)
        results[name] = correlation(l_band, r_band)

    results["overall"] = correlation(left, right)
    return results


def stereo_to_mid_side(left: np.ndarray,
                       right: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert stereo to Mid/Side."""
    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    return mid, side


def stereo_balance(left: np.ndarray, right: np.ndarray) -> float:
    """
    Compute stereo balance.

    Returns:
        Value in [-1, +1]. -1 = full left, +1 = full right.
    """
    l_rms = np.sqrt(np.mean(left ** 2))
    r_rms = np.sqrt(np.mean(right ** 2))
    total = l_rms + r_rms
    if total < 1e-20:
        return 0.0
    return float((r_rms - l_rms) / total)
