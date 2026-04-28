# PyDSPMeters 🎛️

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![PySide6](https://img.shields.io/badge/UI-PySide6-brightgreen.svg)

PyDSPMeters is a modular, high-performance audio visualization suite for producers and sound engineers. Built with PySide6 and NumPy, it provides real-time, low-latency monitoring with a focus on visual clarity and workflow integration.

## 🚀 Key Features

- **Modular Layout**: Dynamic, resizable UI with freely added/removed modules. Supports both **Vertical** and **Horizontal** stacking.
- **Ultra-Thin Design**: Windows can be resized to extremely thin strips (as narrow as 60px) while maintaining readability via dynamic font scaling.
- **Settings Persistence**: Automatically saves window position, size, themes, active modules, and audio settings to a local `settings.json`.
- **Context-Aware Control**: Instant access to module settings via right-click.
- **Performance Optimized**: Hardware-accelerated rendering and optimized DSP paths for high-resolution displays.
- **Ghost Mode & Glass Themes**: Transparent, borderless overlays for seamless DAW integration.
- **Input Overdrive**: On-the-fly gain adjustment for monitoring quiet signals.

## 🎚️ Included Modules

- **Loudness Meter**: LUFS & RMS metering with True-Peak monitoring.
- **Spectrum Analyzer**: High-resolution FFT analyzer with spatial smoothing and log/mel mapping.
- **Stereometer**: Multi-band phase correlation and Lissajous rendering.
- **Spectrogram**: Continuous frequency history (waterfall) with heat-mapping.
- **Waveform View**: Mirrored amplitude wave with intensity-based coloring.
- **VU Meter**: Classic analog-style VU meters.
- **Oscilloscope**: Real-time waveform visualization.

## ♾️ Infinite modularity

![1](demos/1.png)
![1](demos/2.png)
![3](demos/3.png)
![4](demos/4.png)
![5](demos/5.png)

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
- **⚙ Icon**: Global settings (Device selection, Themes, Overdrive, Text Scaling).
- **+ Icon**: Add new visualization modules to the stack.
- **▥/▤ Icon**: Toggle between Vertical and Horizontal layouts.
- **Edge Snapping**: Drag near screen edges for automatic alignment.
- **Portability**: All settings are stored in `settings.json` next to the application, making it fully portable.

## 🛠️ Development
Tests are maintained with `pytest`:
```bash
python -m pytest
```

## 📜 License
This project is licensed under the [MIT License](LICENSE).
