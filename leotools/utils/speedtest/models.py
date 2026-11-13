"""Modelos de datos del speedtest."""

from dataclasses import dataclass, field
from datetime import datetime


class EngineError(Exception):
    """Error de comunicacion con el servidor de medicion."""


@dataclass
class LatencyStats:
    samples_ms: list[float] = field(default_factory=list)
    failed: int = 0

    @property
    def total(self) -> int:
        return len(self.samples_ms) + self.failed


@dataclass
class TransferResult:
    direction: str
    samples: list[tuple[float, int]] = field(default_factory=list)
    bytes_total: int = 0
    elapsed: float = 0.0
    errors: int = 0


@dataclass
class Bufferbloat:
    idle_ms: float | None = None
    loaded_ms: float | None = None
    delta_ms: float | None = None

    @property
    def grade(self) -> str:
        if self.delta_ms is None:
            return "-"
        if self.delta_ms <= 30:
            return "A"
        if self.delta_ms <= 60:
            return "B"
        if self.delta_ms <= 100:
            return "C"
        if self.delta_ms <= 200:
            return "D"
        return "F"


@dataclass
class SpeedTestResult:
    engine: str = "cloudflare"
    colo: str = ""
    ip: str = ""
    location: str = ""
    idle: LatencyStats = field(default_factory=LatencyStats)
    down: TransferResult | None = None
    up: TransferResult | None = None
    down_bloat: Bufferbloat = field(default_factory=Bufferbloat)
    up_bloat: Bufferbloat = field(default_factory=Bufferbloat)
    dns_ms: float | None = None
    ttfb_ms: float | None = None
    warnings: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
