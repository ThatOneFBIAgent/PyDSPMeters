"""Shared DSP worker pool for non-Qt audio processing."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor


def _default_worker_count() -> int:
    cpu_count = os.cpu_count() or 2
    return max(1, min(4, cpu_count - 1))


_EXECUTOR = ThreadPoolExecutor(
    max_workers=_default_worker_count(),
    thread_name_prefix="DSPWorker",
)


def submit(fn, *args, **kwargs):
    return _EXECUTOR.submit(fn, *args, **kwargs)
