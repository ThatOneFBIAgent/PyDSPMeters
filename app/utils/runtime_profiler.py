"""
Runtime profiling helpers for full application sessions.

By default this uses low-overhead stack sampling so the Qt app remains usable.
Deterministic cProfile tracing is available as an explicit heavy mode.
"""

from __future__ import annotations

import cProfile
import json
import pstats
import sys
import threading
import time
import tracemalloc
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import FrameType
from typing import Any, Callable

from app.utils import perf_stats


@dataclass(frozen=True)
class ProfilerConfig:
    output_dir: Path
    sample_interval: float = 0.05
    top: int = 80
    cprofile: bool = False
    trace_memory: bool = False
    max_stack_depth: int = 80


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _format_seconds(value: float) -> str:
    if value >= 10:
        return f"{value:.2f}s"
    if value >= 1:
        return f"{value:.3f}s"
    return f"{value * 1000:.2f}ms"


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "n/a"
    units = ["B", "KiB", "MiB", "GiB"]
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} GiB"


def _process_memory_bytes() -> int | None:
    if sys.platform != "win32":
        try:
            import resource

            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys.platform == "darwin":
                return int(rss)
            return int(rss) * 1024
        except Exception:
            return None

    try:
        import ctypes
        import ctypes.wintypes as wt

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wt.DWORD),
                ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32.dll")
        kernel32.GetCurrentProcess.restype = wt.HANDLE
        handle = kernel32.GetCurrentProcess()
        psapi = ctypes.WinDLL("psapi.dll")
        psapi.GetProcessMemoryInfo.argtypes = [
            wt.HANDLE,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
            wt.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wt.BOOL
        ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        if ok:
            return int(counters.WorkingSetSize)
    except Exception:
        return None
    return None


class RuntimeProfiler:
    def __init__(self, config: ProfilerConfig):
        self.config = config
        self.session_name = f"pydsp_profile_{_now_stamp()}"
        self.session_dir = config.output_dir / self.session_name
        self._profiler = cProfile.Profile() if config.cprofile else None
        self._stop = threading.Event()
        self._sampler: threading.Thread | None = None
        self._start_wall = 0.0
        self._start_cpu = 0.0
        self._end_wall = 0.0
        self._end_cpu = 0.0
        self._sample_ticks = 0
        self._thread_samples: Counter[str] = Counter()
        self._leaf_samples: Counter[str] = Counter()
        self._inclusive_samples: Counter[str] = Counter()
        self._stack_samples: Counter[str] = Counter()
        self._memory_points: list[dict[str, Any]] = []
        self._frame_cache: dict[tuple[str, int, str], str] = {}

    def run(self, func: Callable[[], Any]) -> int:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        if self.config.trace_memory:
            tracemalloc.start(25)

        exit_code = 0
        result: Any = None
        self._start_wall = time.perf_counter()
        self._start_cpu = time.process_time()
        perf_stats.set_enabled(True)
        self._start_sampler()

        try:
            if self._profiler:
                self._profiler.enable()
            result = func()
        except SystemExit as exc:
            exit_code = int(exc.code) if isinstance(exc.code, int) else 0
        finally:
            if self._profiler:
                self._profiler.disable()
            self._end_cpu = time.process_time()
            self._end_wall = time.perf_counter()
            self._stop_sampler()
            self._write_report(exit_code)
            perf_stats.set_enabled(False)
            if self.config.trace_memory:
                tracemalloc.stop()

        if isinstance(result, int):
            return result
        return exit_code

    @property
    def wall_seconds(self) -> float:
        end = self._end_wall or time.perf_counter()
        return max(1e-9, end - self._start_wall)

    @property
    def cpu_seconds(self) -> float:
        end = self._end_cpu or time.process_time()
        return max(0.0, end - self._start_cpu)

    def _start_sampler(self) -> None:
        self._sampler = threading.Thread(
            target=self._sample_loop,
            name="ProfilerSampler",
            daemon=True,
        )
        self._sampler.start()

    def _stop_sampler(self) -> None:
        self._stop.set()
        if self._sampler:
            self._sampler.join(timeout=max(1.0, self.config.sample_interval * 4))

    def _sample_loop(self) -> None:
        current_thread_id = threading.get_ident()
        next_memory_at = 0.0

        while not self._stop.wait(self.config.sample_interval):
            now = time.perf_counter()
            self._sample_ticks += 1
            frames = sys._current_frames()
            names = {t.ident: t.name for t in threading.enumerate()}

            for thread_id, frame in frames.items():
                if thread_id == current_thread_id:
                    continue

                thread_name = names.get(thread_id, f"Thread-{thread_id}")
                stack = self._walk_stack(frame)
                if not stack:
                    continue

                self._thread_samples[thread_name] += 1
                leaf = stack[-1]
                self._leaf_samples[f"{thread_name} | {leaf}"] += 1

                folded = []
                seen_in_stack = set()
                for frame_key in stack:
                    folded.append(frame_key)
                    inclusive_key = f"{thread_name} | {frame_key}"
                    if inclusive_key not in seen_in_stack:
                        self._inclusive_samples[inclusive_key] += 1
                        seen_in_stack.add(inclusive_key)
                self._stack_samples[f"{thread_name};" + ";".join(folded)] += 1

            if now >= next_memory_at:
                next_memory_at = now + 1.0
                self._record_memory_point()

    def _record_memory_point(self) -> None:
        point: dict[str, Any] = {
            "t_wall_s": round(self.wall_seconds, 3),
            "rss_bytes": _process_memory_bytes(),
        }
        if self.config.trace_memory and tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            point["tracemalloc_current_bytes"] = current
            point["tracemalloc_peak_bytes"] = peak
        self._memory_points.append(point)

    def _walk_stack(self, frame: FrameType) -> list[str]:
        stack = []
        depth = 0
        while frame is not None and depth < self.config.max_stack_depth:
            code = frame.f_code
            stack.append(self._format_frame(code.co_filename, frame.f_lineno, code.co_name))
            frame = frame.f_back
            depth += 1
        stack.reverse()
        return stack

    def _format_frame(self, filename: str, lineno: int, name: str) -> str:
        key = (filename, lineno, name)
        cached = self._frame_cache.get(key)
        if cached is not None:
            return cached

        path = Path(filename)
        try:
            rel_filename = str(path.relative_to(Path.cwd()))
        except ValueError:
            rel_filename = path.name
        formatted = f"{rel_filename}:{lineno} in {name}"
        self._frame_cache[key] = formatted
        return formatted

    def _write_report(self, exit_code: int) -> None:
        self._record_memory_point()

        raw_profile_path = self.session_dir / "profile.prof"
        if self._profiler:
            self._profiler.dump_stats(raw_profile_path)
            stats = pstats.Stats(self._profiler)
            rows = self._profile_rows(stats)
        else:
            raw_profile_path = None
            rows = []

        runtime_metrics = perf_stats.snapshot()

        payload = {
            "session": self.session_name,
            "exit_code": exit_code,
            "cprofile_enabled": self.config.cprofile,
            "tracemalloc_enabled": self.config.trace_memory,
            "wall_seconds": self.wall_seconds,
            "cpu_seconds": self.cpu_seconds,
            "cpu_pct_of_one_core": (self.cpu_seconds / self.wall_seconds) * 100.0,
            "sample_interval_seconds": self.config.sample_interval,
            "sample_ticks": self._sample_ticks,
            "profile_rows": rows,
            "thread_samples": dict(self._thread_samples),
            "leaf_samples": dict(self._leaf_samples),
            "inclusive_samples": dict(self._inclusive_samples),
            "memory_points": self._memory_points,
            "runtime_metrics": runtime_metrics,
        }

        json_path = self.session_dir / "profile.json"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        stacks_path = self.session_dir / "stacks.folded"
        with stacks_path.open("w", encoding="utf-8") as f:
            for stack, count in self._stack_samples.most_common():
                f.write(f"{stack} {count}\n")

        report_path = self.session_dir / "profile_report.txt"
        report_path.write_text(self._format_report(rows, raw_profile_path, runtime_metrics), encoding="utf-8")

        print("")
        print(f"[Profiler] Report written to: {report_path}")
        if raw_profile_path:
            print(f"[Profiler] Raw cProfile data: {raw_profile_path}")
        print(f"[Profiler] JSON data: {json_path}")

    def _profile_rows(self, stats: pstats.Stats) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        wall = self.wall_seconds

        for func, raw in stats.stats.items():
            primitive_calls, total_calls, total_time, cumulative_time, callers = raw
            filename, line, name = func
            try:
                rel_filename = str(Path(filename).relative_to(Path.cwd()))
            except ValueError:
                rel_filename = Path(filename).name

            rows.append(
                {
                    "function": f"{rel_filename}:{line} in {name}",
                    "primitive_calls": primitive_calls,
                    "total_calls": total_calls,
                    "total_time_s": total_time,
                    "cumulative_time_s": cumulative_time,
                    "total_time_pct_wall": (total_time / wall) * 100.0,
                    "cumulative_time_pct_wall": (cumulative_time / wall) * 100.0,
                    "total_time_s_per_wall_s": total_time / wall,
                    "cumulative_time_s_per_wall_s": cumulative_time / wall,
                    "calls_per_wall_s": total_calls / wall,
                    "caller_count": len(callers),
                }
            )

        rows.sort(key=lambda item: item["cumulative_time_s"], reverse=True)
        return rows

    def _format_report(
        self,
        rows: list[dict[str, Any]],
        raw_profile_path: Path | None,
        runtime_metrics: dict[str, Any],
    ) -> str:
        top = self.config.top
        wall = self.wall_seconds
        cpu = self.cpu_seconds
        lines: list[str] = []

        lines.append("PyDSPMeters Runtime Profile")
        lines.append("=" * 80)
        lines.append(f"Session: {self.session_name}")
        lines.append(f"cProfile enabled: {self.config.cprofile}")
        lines.append(f"tracemalloc enabled: {self.config.trace_memory}")
        lines.append(f"Wall time: {_format_seconds(wall)}")
        lines.append(f"Process CPU time: {_format_seconds(cpu)}")
        lines.append(f"CPU normalized: {(cpu / wall) * 100.0:.1f}% of one core")
        lines.append(f"Stack sample interval: {self.config.sample_interval:.3f}s")
        lines.append(f"Stack sample ticks: {self._sample_ticks}")
        sample_span = self._sample_ticks * self.config.sample_interval
        sample_coverage = min(100.0, (sample_span / wall) * 100.0)
        lines.append(f"Approx sampler coverage: {sample_coverage:.1f}% of wall time")
        lines.append(f"Raw profile: {raw_profile_path.name if raw_profile_path else 'disabled'}")
        lines.append("")

        lines.append("How To Read The Normalized Columns")
        lines.append("- cum/wall%: cumulative Python time divided by total session wall time.")
        lines.append("- self/wall%: direct Python time in that function divided by wall time.")
        lines.append("- cum/s and self/s: seconds consumed per wall-clock second.")
        lines.append("- calls/s: call rate normalized across the whole session.")
        lines.append("- sample%: percentage of sampled thread stacks, useful for Qt/event-loop wait time.")
        lines.append("")

        if rows:
            lines.append(f"Top {top} Python Functions By Cumulative Time")
            lines.append("-" * 80)
            lines.append(
                f"{'cum':>10} {'self':>10} {'cum/wall%':>10} {'self/wall%':>11} "
                f"{'cum/s':>8} {'calls/s':>9} function"
            )
            for row in rows[:top]:
                lines.append(
                    f"{_format_seconds(row['cumulative_time_s']):>10} "
                    f"{_format_seconds(row['total_time_s']):>10} "
                    f"{row['cumulative_time_pct_wall']:>10.2f} "
                    f"{row['total_time_pct_wall']:>11.2f} "
                    f"{row['cumulative_time_s_per_wall_s']:>8.4f} "
                    f"{row['calls_per_wall_s']:>9.2f} "
                    f"{row['function']}"
                )
            lines.append("")

            by_self = sorted(rows, key=lambda item: item["total_time_s"], reverse=True)
            lines.append(f"Top {top} Python Functions By Self Time")
            lines.append("-" * 80)
            lines.append(
                f"{'self':>10} {'cum':>10} {'self/wall%':>11} {'calls/s':>9} function"
            )
            for row in by_self[:top]:
                lines.append(
                    f"{_format_seconds(row['total_time_s']):>10} "
                    f"{_format_seconds(row['cumulative_time_s']):>10} "
                    f"{row['total_time_pct_wall']:>11.2f} "
                    f"{row['calls_per_wall_s']:>9.2f} "
                    f"{row['function']}"
                )
            lines.append("")
        else:
            lines.append("Deterministic cProfile Sections")
            lines.append("-" * 80)
            lines.append("Disabled for this run. Use --cprofile for exact Python call timings.")
            lines.append("")

        thread_total = max(1, sum(self._thread_samples.values()))
        lines.extend(self._format_counter_section("Thread Wall-Time Samples", self._thread_samples, top, thread_total))
        lines.extend(self._format_counter_section("Leaf Stack Samples", self._leaf_samples, top, thread_total))
        lines.extend(self._format_counter_section("Inclusive Stack Samples", self._inclusive_samples, top, thread_total))
        lines.extend(self._format_runtime_metrics(runtime_metrics, top))

        lines.append("Memory Samples")
        lines.append("-" * 80)
        if not self._memory_points:
            lines.append("No memory samples recorded.")
        else:
            first = self._memory_points[0]
            last = self._memory_points[-1]
            rss_values = [p.get("rss_bytes") for p in self._memory_points if p.get("rss_bytes") is not None]
            current_values = [
                p.get("tracemalloc_current_bytes")
                for p in self._memory_points
                if p.get("tracemalloc_current_bytes") is not None
            ]
            peak_values = [
                p.get("tracemalloc_peak_bytes")
                for p in self._memory_points
                if p.get("tracemalloc_peak_bytes") is not None
            ]
            lines.append(f"RSS first: {_format_bytes(first.get('rss_bytes'))}")
            lines.append(f"RSS last:  {_format_bytes(last.get('rss_bytes'))}")
            lines.append(f"RSS max:   {_format_bytes(max(rss_values) if rss_values else None)}")
            lines.append(
                "Python traced current last: "
                f"{_format_bytes(last.get('tracemalloc_current_bytes'))}"
            )
            lines.append(
                "Python traced current max:  "
                f"{_format_bytes(max(current_values) if current_values else None)}"
            )
            lines.append(
                "Python traced peak max:     "
                f"{_format_bytes(max(peak_values) if peak_values else None)}"
            )
        lines.append("")

        lines.append("Generated Files")
        lines.append("-" * 80)
        lines.append("profile_report.txt  Human-readable report")
        lines.append("profile.json        Structured data with normalized metrics")
        if raw_profile_path:
            lines.append("profile.prof        Raw cProfile data, open with snakeviz or pstats")
        else:
            lines.append("profile.prof        Not generated; use --cprofile to create it")
        lines.append("stacks.folded       Folded stack samples, usable for flamegraph tools")
        lines.append("")

        return "\n".join(lines)

    def _format_runtime_metrics(self, runtime_metrics: dict[str, Any], top: int) -> list[str]:
        lines = ["Runtime Timing Counters", "-" * 80]
        timings = runtime_metrics.get("timings", {})
        counters = runtime_metrics.get("counters", {})

        if not timings and not counters:
            lines.append("No runtime counters recorded.")
            lines.append("")
            return lines

        if timings:
            lines.append(f"{'calls':>8} {'total':>10} {'avg':>10} {'max':>10} {'rate/s':>9} item")
            sorted_timings = sorted(
                timings.items(),
                key=lambda item: item[1].get("total_s", 0.0),
                reverse=True,
            )
            for name, data in sorted_timings[:top]:
                count = int(data.get("count", 0))
                total_s = float(data.get("total_s", 0.0))
                avg_ms = float(data.get("avg_ms", 0.0))
                max_ms = float(data.get("max_ms", 0.0))
                rate = count / self.wall_seconds
                lines.append(
                    f"{count:>8} {_format_seconds(total_s):>10} "
                    f"{avg_ms:>9.2f}ms {max_ms:>9.2f}ms {rate:>9.2f} {name}"
                )

            interval_rows = [
                (name, data) for name, data in timings.items()
                if name.endswith("_interval") or "interval." in name
            ]
            if interval_rows:
                lines.append("")
                lines.append(f"{'events':>8} {'avg gap':>10} {'max gap':>10} {'est fps':>9} item")
                for name, data in sorted(interval_rows, key=lambda item: item[0])[:top]:
                    count = int(data.get("count", 0))
                    avg_ms = float(data.get("avg_ms", 0.0))
                    max_ms = float(data.get("max_ms", 0.0))
                    fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
                    lines.append(
                        f"{count:>8} {avg_ms:>9.2f}ms {max_ms:>9.2f}ms {fps:>9.2f} {name}"
                    )

        if counters:
            lines.append("")
            lines.append(f"{'events':>8} {'total':>12} {'avg':>10} {'max':>10} item")
            for name, data in sorted(counters.items(), key=lambda item: item[0])[:top]:
                count = int(data.get("count", 0))
                total = float(data.get("total", 0.0))
                avg = float(data.get("avg", 0.0))
                max_value = float(data.get("max", 0.0))
                lines.append(f"{count:>8} {total:>12.1f} {avg:>10.2f} {max_value:>10.2f} {name}")

        lines.append("")
        return lines

    def _format_counter_section(
        self,
        title: str,
        counter: Counter[str],
        top: int,
        denominator: int | None = None,
    ) -> list[str]:
        lines = [title, "-" * 80]
        total = denominator or sum(counter.values())
        if total == 0:
            lines.append("No samples recorded.")
            lines.append("")
            return lines

        lines.append(f"{'samples':>9} {'sample%':>8} {'wall share':>10} item")
        for key, count in counter.most_common(top):
            pct = (count / total) * 100.0
            estimated_wall = (count / total) * self.wall_seconds
            lines.append(
                f"{count:>9} {pct:>8.2f} {_format_seconds(estimated_wall):>10} {key}"
            )
        lines.append("")
        return lines
