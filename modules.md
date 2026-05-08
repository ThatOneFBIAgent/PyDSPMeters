# PyDSPMeters Modules & Settings

This document outlines the available audio visualization modules and the specific settings available within their context menus.

---

## 0. Base Module Settings (`all modules`)
* **Move module**: Moves the module up/down, or left/right.
* **Global Label Scale**: Changes the scale of all labels in the module.
* **Show Module headers**: Toggles the visibility of the module header (Name).
* **Auto-hide title bar**: Hides the title bar when not hovering over the window.

## 1. Spectrum Analyzer (`spectrum`)
Visualizes the frequency content of the audio signal in real-time.

*   **Mode**: Changes the visual representation.
    *   *FFT*: Draws a continuous spline curve.
    *   *Color Bars*: Draws discrete frequency bands.
    *   *Both*: Overlays the continuous curve on top of the bars.
*   **FFT Size**: Determines the frequency resolution. Higher values (up to 32768) provide greater precision in the low end but require more CPU. Lower values (e.g., 1024) are highly responsive.
*   **Speed**: Multiplier for the update rate (1x, 2x, 4x).
*   **Scale**: The horizontal frequency mapping.
    *   *Logarithmic*: Standard representation where each octave takes up equal visual space.
    *   *Linear*: Evenly spaces frequencies (Hz).
    *   *Mel*: A perceptual scale based on human hearing.
*   **Orientation**: *Auto*, *Horizontal*, or *Vertical*.
*   **Channel**: Determines which audio data is analyzed.
    *   *L+R*: Renders a "Stereo Ribbon" where the thickness represents the difference between Left and Right channels.
    *   *Left / Right*: Individual channels.
    *   *Mid / Side*: Mono sum or Stereo difference.
*   **Smoothing**: Applies time-based averaging (0% to 99%).
*   **dB/Hz/Note Info**: Displays a text badge with the Note, Frequency, and Amplitude of the loudest peak.
*   **Floating Note Peak**: Anchors the peak tracking badge dynamically to the highest point on the graph.

---

## 2. Loudness Meter (`loudness`)
Monitors loudness levels according to broadcast and mastering standards.

*   **Mode**: 
    *   *LUFS*: Loudness Units relative to Full Scale (ITU-R BS.1770).
    *   *RMS*: Root Mean Square average of signal power.
    *   *dBTP*: True Peak in decibels (dBTP).
*   **Reactivity**: Changes the responsiveness of the meters.
    *   *Instant*: Instantaneous response (1.0).
    *   *Fast*: Fast response (0.7).
    *   *Medium*: Medium response (0.4).
    *   *Slow*: Slow response (0.15).
    *   *Very Slow*: Very slow response (0.05).
*   **Orientation**: *Auto*, *Horizontal*, or *Vertical*.
*   **Show / Hide Toggles**: Individual toggles for *Fast/Mom*, *Slow/Short*, and *Peak* indicators, **Top Lables**, **Mode Badge**, **Follow Badge**.
*   **Show All Channels**: Splits the meter into individual lanes for every active audio channel.

---

## 3. Stereometer (`stereometer`)
Analyzes the stereo image, phase, and correlation.

*   **Display Mode**:
    *   *Vectorscope*: Standard M/S rotated view (L+R on Y, L-R on X).
    *   *Lissajous*: X/Y representation (Left vs Right).
*   **Guide Map**: Background reference shapes (*None*, *Rhombus*, *Circle*).
*   **Zoom**: Amplitude multiplier (0.5x to 4.0x).
*   **Color**: *Static*, *Multi-Band* (Frequency-based coloring), or *Multi-Band (RGB)*.
*   **Width Gain**: Artificially expands the stereo width of the trace. Use this to "explode" the signal for better visibility of wide images. **Hard-clipped to the guide map boundaries.**
*   **Max Dots (Density)**: Sets the point-cloud resolution (256 to 8192). Higher values provide a premium, dense look.
*   **Correlation Smoothing**: Adjusts the ballistics of the correlation meter.
    *   *None (Fast)*: Instant response.
    *   *Natural*: Professional balanced smoothing (includes a "ghost" peak-hold indicator).
    *   *Smooth / Slow*: High-persistence for tracking long-term phase trends.
*   **Correlation**: Toggles between a single summary bar or 4 frequency-banded phase bars.
*   **Minimal Mode**: Hides labels and correlation bars for a pure graph view.
*   **Show Labels**: Toggles axis text markers.
*   **Halved View**: Crops the bottom half of the scope to save space.

---

## 4. Waveform (`waveform`)
Displays a scrolling history of the audio amplitude over time.

*   **Channel**: *L+R*, *Left*, *Right*, *Mid*, *Side*.
*   **Speed**: Scrolling rate (1x, 2x, 4x, 8x).
*   **Display Mode**:
    *   *Overlay*: Channels are drawn on top of each other.
    *   *Split*: Top half is Left, bottom half is Right.
    *   *Dual*: Channels are drawn in separate horizontal lanes.

---

## 5. Spectrogram (`spectrogram`)
A 2D waterfall graph showing frequency intensity over time.

*   **FFT Size**: Frequency resolution.
*   **Scale**: *Logarithmic*, *Linear*, or *Mel*.
*   **Orientation**: *Horizontal*, or *Vertical*.
*   **Speed**: Draw update rate (1x, 2x, 4x).
*   **Mode**: *Sharper (Blackman-harris)*, *Sharp (Blackman)* or *Classic (Hann)*.
*   **Tilt**: Wether the graph is tilted towards the background or foreground.
*   **Color Map Override**: *Theme Default* or simple *black-blue-red*.
*   **Piano Overlay**: Overlays a piano keyboard on the spectrogram.
*   **Floor**: Adjusts the baseline of the spectrogram.


---

## 6. VU Meter (`vu_meter`)
Analog-style needle meter simulating mechanical ballistics.

*   **Style**: *Modern*, *Classic Dark*, or *LED Bar*.
*   **Channel**: *L+R* (Dual needles), *Left*, *Right*, *Mid*, or *Side*.
*   **Cal (dB)**: Adjusts the calibration offset (where 0 VU sits).
*   **Peak LED**: Toggles the peak indicator light.
*   **Clip LED**: Toggles the digital clip indicator light.

---

## 7. Oscilloscope (`oscilloscope`)
Real-time unbuffered view of the audio waveform with zero-crossing triggering.

*   **Channel**: *L+R*, *Left*, *Right*, *Mid*, or *Side*.
*   **Display Mode**:
    *   *Overlay*: Both channels share the same central axis.
    *   *Dual*: Separates the channels into top and bottom lanes (only available in *L+R* mode).
*   **Zoom Samples**: Adjusts the horizontal "width" of the waveform (256 to 8192 samples). Lower values zoom in, higher values show more cycles.
