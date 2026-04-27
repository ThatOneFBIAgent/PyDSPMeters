# PyDSPMeters

A modular, high-performance, and frameless real-time audio visualization utility built with Python, PySide6, and NumPy. Inspired by professional studio meters, it provides a highly customizable suite of audio analysis tools designed to sit cleanly on your screen while you work.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)
![PySide6](https://img.shields.io/badge/PySide6-Qt-green?style=for-the-badge&logo=qt)
![NumPy](https://img.shields.io/badge/NumPy-DSP-blue?style=for-the-badge&logo=numpy)
![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)

## ✨ Features

- **Frameless & Always-on-Top:** Designed to live alongside your DAW or editing software without getting in the way.
- **Edge Snapping:** Seamlessly snaps to screen edges or the top of your taskbar.
- **Modular Layout:** Stack meters vertically or horizontally (▥/⬤ toggle). Add, remove, and resize individual modules on the fly.
- **Hardware Accelerated DSP:** Real-time audio processing using `numpy` and `scipy` for low-latency FFTs, RMS, and LUFS calculations.
- **Theming System:** Switch between 5 premium color palettes instantly (Midnight, Abyss, Neon, Ember, Amethyst).

## 🎛️ Included Modules

1. **Oscilloscope**: Real-time waveform display with zero-crossing trigger stabilization.
2. **Loudness Meter**: EBU R128 compliant. View Momentary/Short-term LUFS or RMS, alongside a true peak indicator.
3. **VU Meter**: Classic analog-style needle meter with adjustable ballistics, calibration, and peak/clip LEDs.
4. **Stereometer**: View stereo correlation via Lissajous, Linear, or Scaled modes. Includes single-band or multi-band correlation metering.
5. **Spectrum Analyzer**: FFT-based frequency display with Mel/Log/Linear scaling, bar or line modes, and musical note detection.
6. **Spectrogram**: High-performance scrolling heatmap of frequency content over time. Includes an optional piano-roll overlay.
7. **Waveform**: Scrolling time-domain history with multi-band coloring and peak history overlays.

## 🚀 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ThatOneFBIAgent/pydspmeters.git
   cd pydspmeters
   ```

2. **Install dependencies:**
   Ensure you have Python 3.10+ installed, then run:
   ```bash
   pip install -r requirements.txt
   ```
   *Required packages:* `PySide6`, `sounddevice`, `numpy`, `scipy`, `soundfile`.

3. **Run the application:**
   ```bash
   python main.py
   ```

## 🎮 Usage

- **Moving the window:** Click and drag the ultra-compact title bar (`DSP`).
- **Resizing:** Grab the bottom-right corner or the splitters between modules.
- **Adding Modules:** Click the `+` icon in the title bar to open the module registry.
- **Settings & Audio Devices:** Click the `⚙` (Gear) icon to change your audio input device (fully supports Voicemeeter) or switch the active theme.
- **Module Settings:** Click the `⚙` icon inside any specific module to tweak its display mode, colors, or FFT sizes.
- **Closing Modules:** Click the `×` on a module's header to remove it.

## 🛠️ Testing

The DSP and math functions are fully covered by `pytest`. To run the test suite:
```bash
python -m pytest tests/ -v
```

## 📝 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
