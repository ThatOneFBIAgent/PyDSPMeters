# PyDSPMeters

> Professional-grade, high-performance audio visualization suite built for modern workflows.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://python.org)
[![PySide6](https://img.shields.io/badge/UI-PySide6-brightgreen.svg)](https://pyside.org)
[![Performance](https://img.shields.io/badge/DSP-NumPy%20%2B%20Rust-orange.svg)](https://numpy.org)

PyDSPMeters is a modular, always-on-top audio monitoring suite for engineers, producers, and audio nerds who want critical signal feedback without giving up screen real estate. It targets Windows 10/11 and should also run on common Linux desktops, though Linux builds are less tested.

---

## Engineered For Performance

PyDSPMeters is built around compact audio blocks, vectorized DSP, and Qt painting that stays on the main thread where it belongs.

* **Vectorized DSP**: NumPy/SciPy handle FFTs, filters, loudness metering, and signal analysis.
* **Rust native acceleration**: The optional `dsp_accel` module speeds up hot paths such as bulk array operations, circular buffers, waveform reduction, spectrogram column generation, and correlation helpers.
* **Worker-thread audio processing**: Heavy module processing can run through a latest-only DSP worker pool. The Qt main thread stays focused on painting and window management while stale audio jobs are dropped instead of queued into lag.
* **Runtime profiling tools**: `profile_app.py` records stack samples, paint cadence, audio queue drain timing, module worker timing, and memory snapshots under `profile_logs/`.
* **Circular buffer rendering**: Modules such as Spectrogram use cached image buffers for smooth scrolling.
* **Low-latency capture**: SoundDevice/PortAudio feeds compact blocks into a Qt-side queue bridge.
* **Adaptive UI**: Dynamic text scaling and layout distribution keep meters readable from tiny strips to full-height panels.

---

## Infinite Modularity

PyDSPMeters adapts to your workflow.

* **Stackable architecture**: Add, remove, and reorder modules on the fly.
* **Omni-layout**: Toggle between vertical stacking and horizontal strips.
* **Ghost mode**: Transparent and glass presets combine with an auto-hiding title bar for floating meters.
* **Edge snapping**: Window management that locks to screen edges.
* **AppBar functionality**: Windows-only docking mode that reserves desktop space for PyDSPMeters.

![1](demos/1.png)
![2](demos/2.png)
![3](demos/3.png)
![4](demos/4.png)
![5](demos/5.png)
![6](demos/6.png)
![7](demos/7.png)
![8](demos/8.png)
![9](demos/9.png)

---

## Visualization Suite

| Module | Description | Key Features |
| :--- | :--- | :--- |
| **Loudness** | EBU R128 style metering | Integrated LUFS, RMS, true peak, worker-thread processing. |
| **Spectrum** | High-resolution FFT | Mel/log/linear scales, tilt, smoothing, and peak tracking. |
| **Stereo** | Phase analysis | Lissajous/vectorscope rendering and multi-band correlation. |
| **Spectrogram** | Frequency history | Circular heatmap buffer with customizable palettes. |
| **Waveform** | Amplitude history | Mirrored intensity-based waveform with real-time scaling. |
| **VU Meter** | Analog classic | Precision ballistics with themed peak and clip indicators. |
| **Oscilloscope** | Signal detail | Responsive waveform plotting at high zoom levels. |

---

## Theme Engine

Built-in presets include Midnight, Modern Light, Abyss, Transparent Ghost, Aurora, Crimson, Solar, and more. Custom themes can be created by editing the generated `themes.json` in the app data directory, or by using `app/theme.py` as a base.

---

## Getting Started

### Prerequisites

* Python 3.9+
* An audio input device, Stereo Mix, loopback device, or virtual cable

### Installation

```bash
git clone https://github.com/ThatOneFBIAgent/PyDSPMeters.git
cd PyDSPMeters
pip install -r requirements.txt
pip install --find-links ./wheels dsp_accel
python main.pyw
```

To launch without a console on Windows, create a shortcut to `pythonw`:

```bash
pythonw "path/to/main.pyw"
```

---

## Building A Standalone Executable

The build helper uses PyInstaller, includes `icon.ico` when available, streams colored build logs, and includes the Rust accelerator when it is installed:

```bash
python build_dist.py --yes
```

If `dist/PyDSPMeters.exe` is locked because the previous build is still running, the helper automatically writes a timestamped executable beside it instead of failing late in the build. To fail immediately on a locked output file:

```powershell
python build_dist.py --yes --locked-output fail
```

The output will be written to:

```text
dist/PyDSPMeters.exe
```

The application logs whether the Rust accelerator is active at startup:

```text
DSP accelerator active: True
```

---

## Rust Native Acceleration

PyDSPMeters includes a custom Rust crate, `dsp_accel`, built with PyO3 and maturin. If it is unavailable, the app falls back to Python/NumPy implementations so it can still run, just with less headroom.

Precompiled wheels are included under `wheels/`:

```bash
pip install --find-links ./wheels dsp_accel
```

To build the native module yourself:

```bash
cd native
maturin build --release
pip install target/wheels/dsp_accel-*.whl --force-reinstall
```

On Windows, install the Visual Studio "Desktop development with C++" workload if maturin cannot find a compiler.

---

## Profiling

Run a full app session with lightweight profiling:

```bash
python profile_app.py --interval 0.1 --top 80
```

Close the app normally. A report folder will be written under `profile_logs/`, including:

* `profile_report.txt`: human-readable timing report.
* `profile.json`: structured metrics.
* `stacks.folded`: sampled stacks for flamegraph tooling.
* `profile.prof`: generated only when `--cprofile` is used.

Useful report sections include paint cadence, audio queue drain timing, module audio time, worker-thread time, and ghost-titlebar update time.

---

## Shortcuts & Workflow

* **Right-click**: Open module-specific settings.
* **Gear icon**: Device selection, themes, input gain, and label scaling.
* **Plus icon**: Add a module.
* **Layout icon**: Switch between vertical and horizontal layouts.
* **Move mode**: Rearrange modules without fighting splitter handles.
* **Portability**: Settings are stored in the app data directory, with source-run `settings.json` ignored by git.

### Multiple OBS-Friendly Instances

Launch the same executable with different profiles to give each instance a distinct window title, Windows app ID, settings file, and log file:

```powershell
dist/PyDSPMeters.exe --profile stream-left
dist/PyDSPMeters.exe --profile stream-right
```

OBS Window Capture can then target `PyDSPMeters - stream-left` or `PyDSPMeters - stream-right` instead of guessing between identical windows. `--instance` and `--instance-name` are aliases for `--profile`.

Do note these instances will be as if you've started the program for the first time, due to it not being able to find it's default config file.

---

## Development & Testing

```bash
python -m pytest --basetemp profile_logs/pytest_tmp
```

The explicit `--basetemp` keeps pytest's temporary files inside the workspace on locked-down Windows environments.

---

## Known Issues

* Python 3.14 plus SoundDevice/CFFI can soft-crash after extended silence on some systems. PyDSPMeters includes a keep-alive workaround, but Python 3.13 or 3.12 may be more stable.
* Onefile executables built with PyInstaller/Nuitka can trigger antivirus false positives. Build from source if you want to inspect the full chain yourself.
* Linux support is community-tested. PRs and issue reports are welcome.

---

## License

Licensed under the [MIT License](LICENSE). Build, modify, and share.
