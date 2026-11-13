"""Calculos estadisticos de las mediciones de velocidad."""

import math

from .models import Bufferbloat, LatencyStats, TransferResult


def percentile(values: list[float], p: float) -> float:
    """Percentil con interpolacion lineal (p entre 0 y 100)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (p / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[int(rank)]
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def jitter_ms(samples: list[float]) -> float:
    """Variacion media entre RTTs consecutivos (estilo RFC 3550)."""
    if len(samples) < 2:
        return 0.0
    diffs = [abs(b - a) for a, b in zip(samples, samples[1:])]
    return mean(diffs)


def summarize_latency(stats: LatencyStats) -> dict:
    samples = stats.samples_ms
    return {
        "count": len(samples),
        "failed": stats.failed,
        "min": min(samples) if samples else 0.0,
        "median": percentile(samples, 50),
        "mean": mean(samples),
        "p95": percentile(samples, 95),
        "max": max(samples) if samples else 0.0,
        "jitter": jitter_ms(samples),
        "loss_pct": (stats.failed / stats.total * 100.0) if stats.total else 0.0,
    }


def _windows(
    samples: list[tuple[float, int]], warmup: float, bucket: float = 0.5
) -> list[float]:
    """Velocidad media en ventanas de ~0.5s, sin el ramp-up."""
    result: list[float] = []
    base_t: float | None = None
    base_b = 0
    for timestamp, total in samples:
        if timestamp < warmup:
            continue
        if base_t is None:
            base_t, base_b = timestamp, total
            continue
        span = timestamp - base_t
        if span >= bucket:
            mbps = (total - base_b) * 8.0 / span / 1_000_000
            if mbps > 0:
                result.append(mbps)
            base_t, base_b = timestamp, total
    return result


def transfer_stats(transfer: TransferResult | None, warmup: float = 1.5) -> dict:
    """Resumen de una transferencia descartando el arranque (slow start)."""
    if transfer is None or transfer.bytes_total <= 0 or transfer.elapsed <= 0:
        return {"avg": 0.0, "p90": 0.0, "peak": 0.0, "samples": 0, "errors": 0}

    overall = transfer.bytes_total * 8.0 / transfer.elapsed / 1_000_000
    samples = transfer.samples
    if len(samples) < 3:
        return {
            "avg": overall,
            "p90": overall,
            "peak": overall,
            "samples": 0,
            "errors": transfer.errors,
        }

    cutoff = min(max(warmup, transfer.elapsed * 0.15), transfer.elapsed * 0.4)
    start = next((i for i, (ts, _) in enumerate(samples) if ts >= cutoff), 0)
    ts0, b0 = samples[start]
    ts1, b1 = samples[-1]
    steady = (b1 - b0) * 8.0 / (ts1 - ts0) / 1_000_000 if ts1 > ts0 else overall

    windows = _windows(samples, cutoff)
    p90 = percentile(windows, 90) if windows else steady
    peak = max(windows) if windows else steady
    return {
        "avg": steady,
        "p90": p90,
        "peak": peak,
        "samples": len(windows),
        "errors": transfer.errors,
    }


def bufferbloat(idle: LatencyStats, loaded_samples: list[float]) -> Bufferbloat:
    """Latencia bajo carga menos latencia en reposo."""
    if not idle.samples_ms or not loaded_samples:
        return Bufferbloat()
    idle_ms = percentile(idle.samples_ms, 50)
    loaded_ms = percentile(loaded_samples, 50)
    delta = max(0.0, loaded_ms - idle_ms)
    return Bufferbloat(idle_ms=idle_ms, loaded_ms=loaded_ms, delta_ms=delta)


def format_mbps(value: float) -> str:
    if value >= 1000:
        return f"{value / 1000:.2f} Gbps"
    return f"{value:.1f} Mbps"


def format_ms(value: float | None) -> str:
    if value is None:
        return "n/d"
    return f"{value:.1f} ms"


def human_bytes(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"


def delta_pct(current: float, previous: float) -> float | None:
    if not previous:
        return None
    return (current - previous) / previous * 100.0


def grade_style(grade: str) -> str:
    return {
        "A": "bold green",
        "B": "green",
        "C": "yellow",
        "D": "dark_orange",
        "F": "bold red",
    }.get(grade, "dim")
