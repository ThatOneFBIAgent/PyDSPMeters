# PyDSPMeters 🎛️
> **Professional-grade, high-performance audio visualization suite built for modern workflows.**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://python.org)
[![PySide6](https://img.shields.io/badge/UI-PySide6-brightgreen.svg)](https://pyside.org)
[![Performance](https://img.shields.io/badge/DSP-NumPy-orange.svg)](https://numpy.org)

PyDSPMeters is a modular, ultra-responsive audio monitoring suite designed to rival professional desktop solutions. It provides a flexible, always-on-top interface for engineers, producers, and audiophiles who need critical signal feedback without sacrificing screen real estate.

## ♾️ Infinite Modularity

![1](demos/1.png)
![2](demos/2.png)
![3](demos/3.png)
![4](demos/4.png)
![5](demos/5.png)
![6](demos/6.png)

---

## ⚡ Engineered for Performance

Built from the ground up to handle high-resolution displays and high-density audio streams, PyDSPMeters utilizes a optimized processing pipeline:

*   **Zero-Copy DSP**: Leveraging NumPy's vectorized operations for lightning-fast FFT calculations and signal analysis.
*   **Circular Buffer Rendering**: Advanced `QImage` caching for modules like the Spectrogram ensures 60+ FPS even at 4K/8K resolutions.
*   **Low-Latency Hooking**: Direct interface with system audio drivers via PyAudio with minimal buffer overhead.
*   **Adaptive UI**: Dynamic text scaling and intelligent layout distribution that keeps meters readable from 60px to full-screen.

---

## 🏗️ Infinite Modularity

PyDSPMeters adapts to *your* workflow, not the other way around.

*   **Stackable Architecture**: Add, remove, and reorder modules on the fly. Build exactly the monitoring rig you need.
*   **Omni-Layout**: Seamlessly toggle between **Vertical** and **Horizontal** modes. Fit the meters into a side-bar, a bottom-strip, or a dedicated second monitor.
*   **Ghost Mode**: Transparent and Glass presets combined with an auto-hiding title bar allow the meters to "float" over your DAW or editor.
*   **Edge Snapping**: Intelligent window management that locks to screen edges for a pixel-perfect setup.

---

## 🎚️ The Visualization Suite

| Module | Description | Key Features |
| :--- | :--- | :--- |
| **Loudness** | EBU R128 Compliant | Integrated LUFS, RMS, and Peak monitoring. |
| **Spectrum** | High-Res FFT | Mel/Log scales, spatial smoothing, and peak tracking. |
| **Stereo** | Phase Analysis | Lissajous rendering and multi-band correlation. |
| **Spectrogram** | Frequency History | Optimized circular heatmap with customizable palettes. |
| **Waveform** | Amplitude History | Mirrored intensity-based waveform with real-time scaling. |
| **VU Meter** | Analog Classic | Precision ballistics with themed LED status indicators. |
| **Oscilloscope** | Signal Detail | Ultra-responsive waveform plotting at high zoom levels. |

---

## 🎨 Theme Engine

Express your aesthetic with a wide range of built-in presets:

*   **Midnight**: Deep studio dark with vibrant cyan accents.
*   **Modern Light**: Clean, professional light theme with indigo/blue meters.
*   **Abyss**: Pure black OLED-ready interface.
*   **Transparent Ghost**: Borderless, floating UI for minimal distraction.
*   **Aurora, Crimson, Solar**: High-contrast, color-focused palettes for visibility.

---

## 📦 Getting Started

### Prerequisites
*   Python 3.9+
*   Audio Input Device (Microphone, Stereo Mix, or Virtual Cable)

### Installation
```bash
# Clone the repository
git clone https://github.com/ThatOneFBIAgent/PyDSPMeters.git
cd PyDSPMeters

# Install dependencies
pip install -r requirements.txt

# Launch
python main.py
```

---

## ⌨️ Shortcuts & Workflow

*   **Right-Click**: Access deep settings for any specific module (Scale, Speed, Channels).
*   **⚙ Gear Icon**: Global configuration (Device selection, Themes, Input Gain, Label Scaling).
*   **+ Plus Icon**: Instantly append new modules to the current layout.
*   **▥/▤ Layout Icon**: Switch between vertical stacking and horizontal strips.
*   **Portability**: PyDSPMeters is fully portable; all configurations are stored in `settings.json` within the root directory.

---

## 🛠️ Development & Testing

We utilize `pytest` for ensuring DSP accuracy and stability:
```bash
python -m pytest
```

## 📜 License
Licensed under the [MIT License](LICENSE). Build, modify, and share.
