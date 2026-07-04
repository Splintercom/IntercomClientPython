import threading
import time
from typing import Any

import psutil
from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor

_lock = threading.Lock()
_cache: dict[str, Any] = {}
_cache_time: float = 0.0
_CACHE_TTL = 1.0


def _read() -> dict[str, Any]:
    cpu_pct = psutil.cpu_percent(interval=None)
    cpu_times = psutil.cpu_times_percent(interval=None)
    vm = psutil.virtual_memory()
    load = psutil.getloadavg()

    metrics: dict[str, Any] = {
        "host.cpu.usage_pct": cpu_pct,
        "host.cpu.iowait_pct": getattr(cpu_times, "iowait", 0.0),
        "host.memory.used_pct": vm.percent,
        "host.memory.available_bytes": vm.available,
        "host.load.1m": load[0],
        "host.load.5m": load[1],
        "host.load.15m": load[2],
    }

    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            key = part.mountpoint.strip("/").replace("/", ".") or "root"
            metrics[f"host.disk.{key}.used_pct"] = usage.percent
        except (PermissionError, OSError):
            pass

    return metrics


def _get() -> dict[str, Any]:
    global _cache, _cache_time
    now = time.monotonic()
    with _lock:
        if now - _cache_time >= _CACHE_TTL:
            _cache = _read()
            _cache_time = now
        return dict(_cache)


def warmup() -> None:
    # First call to cpu_percent/cpu_times_percent always returns 0 — prime the baseline.
    psutil.cpu_percent(interval=None)
    psutil.cpu_times_percent(interval=None)


class HostMetricsSpanProcessor(SpanProcessor):
    def on_start(
        self, span: ReadableSpan, parent_context: Context | None = None
    ) -> None:
        for key, value in _get().items():
            span.set_attribute(key, value)  # type: ignore[arg-type]

    def on_end(self, span: ReadableSpan) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True
