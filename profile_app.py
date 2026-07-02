"""
Run PyDSPMeters with low-overhead full-session profiling enabled.

Usage:
    python profile_app.py
    python profile_app.py --interval 0.2 --top 120
    python profile_app.py --cprofile --tracemalloc

Close the app normally. A report folder will be written under profile_logs/.
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import sys
from pathlib import Path

from app.utils.runtime_profiler import ProfilerConfig, RuntimeProfiler


def _load_main_module():
    main_path = Path(__file__).resolve().with_name("main.pyw")
    loader = importlib.machinery.SourceFileLoader("pydspmeters_profiled_main", str(main_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"Could not create import spec for {main_path}")

    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PyDSPMeters with profiling enabled.")
    parser.add_argument(
        "--out",
        default="profile_logs",
        help="Directory where profiling sessions are written.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.1,
        help="Stack sampling interval in seconds. Lower is more detailed but heavier.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=80,
        help="Number of rows to show in each report section.",
    )
    parser.add_argument(
        "--cprofile",
        action="store_true",
        help="Enable deterministic cProfile tracing. Very detailed, but can make Qt rendering much slower.",
    )
    parser.add_argument(
        "--tracemalloc",
        action="store_true",
        help="Enable Python allocation tracing. Useful for leaks, but adds overhead.",
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Deprecated compatibility flag. RSS memory samples are always lightweight.",
    )
    parser.add_argument(
        "--stack-depth",
        type=int,
        default=80,
        help="Maximum Python stack depth captured per sample.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parent
    output_dir = Path(args.out)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir

    config = ProfilerConfig(
        output_dir=output_dir,
        sample_interval=max(0.005, float(args.interval)),
        top=max(1, int(args.top)),
        cprofile=bool(args.cprofile),
        trace_memory=bool(args.tracemalloc),
        max_stack_depth=max(1, int(args.stack_depth)),
    )

    main_module = _load_main_module()
    profiler = RuntimeProfiler(config)
    return profiler.run(main_module.main)


if __name__ == "__main__":
    raise SystemExit(main())
