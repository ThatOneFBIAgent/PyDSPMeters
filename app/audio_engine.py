"""
Audio Engine: Captures audio from input devices and distributes it to modules.
Uses sounddevice for low-latency capture with a thread-safe queue bridge to Qt.
"""

import queue
import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Signal, QTimer, Slot


class AudioEngine(QObject):
    """
    Real-time audio capture engine.

    Captures stereo audio via sounddevice and emits Qt signals
    with new data blocks for consumption by visualization modules.
    Also maintains a circular buffer for modules that need history (e.g. LUFS).
    """

    # Emits (np.ndarray) of shape (block_size, 2), float32
    data_ready = Signal(np.ndarray)
    # Emits when the stream starts/stops
    stream_started = Signal()
    stream_stopped = Signal()
    # Emits (str) on error
    error_occurred = Signal(str)

    def __init__(self, sample_rate: int = 44100, block_size: int = 1024,
                 buffer_seconds: float = 10.0, parent=None):
        super().__init__(parent)
        self.sample_rate = sample_rate
        self.block_size = block_size
        self._stream = None
        self._device = None

        # Thread-safe queue for bridging callback → Qt main thread
        self._queue = queue.Queue(maxsize=200)

        # Circular history buffer
        buf_len = int(sample_rate * buffer_seconds)
        self.buffer = np.zeros((buf_len, 2), dtype=np.float32)
        self._write_pos = 0
        self._total_written = 0

        # Timer to drain the queue on the main thread
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(8)  # ~120 Hz polling
        self._poll_timer.timeout.connect(self._drain_queue)

    # ── Device Enumeration ──────────────────────────────────────────────────

    @staticmethod
    def list_devices() -> list[dict]:
        """Return list of available input devices."""
        devices = sd.query_devices()
        inputs = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                inputs.append({
                    "index": i,
                    "name": d["name"],
                    "channels": d["max_input_channels"],
                    "sample_rate": d["default_samplerate"],
                    "hostapi": sd.query_hostapis(d["hostapi"])["name"],
                })
        return inputs

    @staticmethod
    def get_default_device() -> int | None:
        """Get the default input device index."""
        try:
            return sd.default.device[0]
        except Exception:
            return None

    # ── Stream Control ──────────────────────────────────────────────────────

    def start(self, device_index: int | None = None):
        """Start capturing audio from the given device."""
        self.stop()
        self._device = device_index

        try:
            self._stream = sd.InputStream(
                device=device_index,
                channels=2,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype="float32",
                callback=self._audio_callback,
                latency="low",
            )
            self._stream.start()
            self._poll_timer.start()
            self.stream_started.emit()
        except Exception as e:
            # Try mono fallback
            try:
                self._stream = sd.InputStream(
                    device=device_index,
                    channels=1,
                    samplerate=self.sample_rate,
                    blocksize=self.block_size,
                    dtype="float32",
                    callback=self._audio_callback_mono,
                    latency="low",
                )
                self._stream.start()
                self._poll_timer.start()
                self.stream_started.emit()
            except Exception as e2:
                self.error_occurred.emit(f"Audio error: {e2}")

    def stop(self):
        """Stop the audio stream."""
        self._poll_timer.stop()
        if self._stream is not None:
            try:
                # Use abort() instead of stop() to prevent hanging the main thread
                # while waiting for the audio buffer to flush during application exit.
                self._stream.abort()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
            self.stream_stopped.emit()

    @property
    def is_running(self) -> bool:
        return self._stream is not None and self._stream.active

    # ── Callbacks (run on audio thread) ─────────────────────────────────────

    def _audio_callback(self, indata, frames, time_info, status):
        """Sounddevice callback for stereo input."""
        try:
            self._queue.put_nowait(indata.copy())
        except queue.Full:
            pass  # Drop oldest if queue full

    def _audio_callback_mono(self, indata, frames, time_info, status):
        """Sounddevice callback for mono input — duplicated to stereo."""
        stereo = np.column_stack([indata[:, 0], indata[:, 0]])
        try:
            self._queue.put_nowait(stereo)
        except queue.Full:
            pass

    # ── Queue Drain (runs on Qt main thread) ────────────────────────────────

    @Slot()
    def _drain_queue(self):
        """Pull all available audio blocks from the queue and emit signals."""
        blocks = []
        while True:
            try:
                blocks.append(self._queue.get_nowait())
            except queue.Empty:
                break

        for data in blocks:
            n = len(data)
            buf_len = len(self.buffer)

            # Write to circular buffer
            end = self._write_pos + n
            if end <= buf_len:
                self.buffer[self._write_pos:end] = data
            else:
                first = buf_len - self._write_pos
                self.buffer[self._write_pos:] = data[:first]
                self.buffer[:n - first] = data[first:]
            self._write_pos = end % buf_len
            self._total_written += n

            # Emit to all connected modules
            self.data_ready.emit(data)

    # ── Buffer Access ───────────────────────────────────────────────────────

    def get_history(self, seconds: float) -> np.ndarray:
        """
        Get the last N seconds of audio from the circular buffer.

        Returns:
            Array of shape (n_samples, 2), float32.
        """
        n_samples = min(int(seconds * self.sample_rate), len(self.buffer))
        available = min(n_samples, self._total_written)
        if available == 0:
            return np.zeros((1, 2), dtype=np.float32)

        end = self._write_pos
        if end >= available:
            return self.buffer[end - available:end].copy()
        else:
            return np.concatenate([
                self.buffer[-(available - end):],
                self.buffer[:end],
            ])
