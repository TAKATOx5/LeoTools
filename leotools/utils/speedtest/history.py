"""Historial local de mediciones en formato JSON Lines."""

import json
import os
from datetime import datetime
from pathlib import Path

from .metrics import summarize_latency, transfer_stats
from .models import SpeedTestResult


def history_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        folder = Path(base) / "LeoTools"
    else:
        folder = Path.home() / ".local" / "share" / "leotools"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "speedtest.jsonl"


def to_record(result: SpeedTestResult) -> dict:
    idle = summarize_latency(result.idle)
    down = transfer_stats(result.down)
    up = transfer_stats(result.up)
    return {
        "ts": result.started_at.isoformat(timespec="seconds"),
        "engine": result.engine,
        "down": round(down["avg"], 2),
        "up": round(up["avg"], 2),
        "down_peak": round(down["peak"], 2),
        "up_peak": round(up["peak"], 2),
        "ping": round(idle["median"], 2),
        "jitter": round(idle["jitter"], 2),
        "loss": round(idle["loss_pct"], 1),
        "down_bloat": round(result.down_bloat.delta_ms, 1)
        if result.down_bloat.delta_ms is not None
        else None,
        "up_bloat": round(result.up_bloat.delta_ms, 1)
        if result.up_bloat.delta_ms is not None
        else None,
        "grade_down": result.down_bloat.grade,
        "grade_up": result.up_bloat.grade,
        "colo": result.colo,
        "ip": result.ip,
    }


def append(result: SpeedTestResult) -> None:
    record = to_record(result)
    with history_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def load(limit: int | None = 20) -> list[dict]:
    path = history_path()
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if limit is not None and limit > 0:
        records = records[-limit:]
    return records


def last() -> dict | None:
    records = load(1)
    return records[0] if records else None


def format_timestamp(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%d/%m %H:%M")
    except (TypeError, ValueError):
        return str(value)
