from contextlib import asynccontextmanager
from time import perf_counter

from ..schemas import SearchDebugInfo


@asynccontextmanager
async def track_latency(debug: SearchDebugInfo | None, name: str):
    start = perf_counter()
    try:
        yield
    finally:
        if debug is not None:
            debug.latency_ms[name] = (perf_counter() - start) * 1000
