"""
Timebox helper:
- Simple context manager to measure durations and emit structured logs.
- Not a hard timeout (planner executes timeouts via futures).
"""

import time
from contextlib import contextmanager
from typing import Iterator
from src.utils.logger import log


@contextmanager
def timebox(event: str, **fields) -> Iterator[None]:
    start = time.time()
    log(f"{event}.start", **fields)
    try:
        yield
    finally:
        dur = time.time() - start
        log(f"{event}.finish", duration_sec=round(dur, 3), **fields)
