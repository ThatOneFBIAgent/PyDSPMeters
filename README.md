# PyDSPMeters 🎛️

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![PySide6](https://img.shields.io/badge/UI-PySide6-brightgreen.svg)

PyDSPMeters is a modular, high-performance audio visualization suite for producers and sound engineers. Built with PySide6 and NumPy, it provides real-time, low-latency monitoring with a focus on visual clarity and workflow integration.

## 🚀 Key Features

- **Modular Layout**: Dynamic, resizable UI with freely added/removed modules.
- **Context-Aware Control**: Instant access to module settings via right-click.
- **Performance Optimized**: Hardware-accelerated rendering and optimized DSP paths for high-resolution displays.
- **Ghost Mode**: Transparent, borderless overlay for seamless DAW integration.
- **Input Overdrive**: On-the-fly gain adjustment for monitoring quiet signals.

## 🎚️ Included Modules

- **Loudness Meter**: LUFS & RMS metering with True-Peak monitoring.
- **Spectrum Analyzer**: High-resolution FFT analyzer with spatial smoothing and log/mel mapping.
- **Stereometer**: Multi-band phase correlation and Lissajous rendering.
- **Spectrogram**: Continuous frequency history (waterfall) with heat-mapping.
- **Waveform View**: Mirrored amplitude wave with intensity-based coloring.
- **VU Meter**: Classic analog-style VU meters.

## 📦 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Launch application
python main.py
```

- Using venv is recommended: 
    ```bash
    python -m venv venv
    # Windows:
    venv\Scripts\activate
    # macOS/Linux:
    source venv/bin/activate
    ```

## ⌨️ Shortcuts & Tips
- **Right-Click**: Open context-specific settings for any module.
- **⚙ Icon**: Global settings (Device selection, Themes, Overdrive).
- **+ Icon**: Add new visualization modules to the stack.
- **Edge Snapping**: Drag near screen edges for automatic alignment.

## 🛠️ Development
Tests are maintained with `pytest`:
```bash
python -m pytest
```

## 📜 License
This project is licensed under the [MIT License](LICENSE).
