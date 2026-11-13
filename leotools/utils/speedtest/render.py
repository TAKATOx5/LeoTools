"""Interfaz de consola del speedtest."""

import math
import time
from collections import deque

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import history, metrics
from .models import LatencyStats, SpeedTestResult

ACCENT = "bright_blue"
SPARK = "▁▂▃▄▅▆▇█"


def _sparkline(values: list[float], width: int = 24) -> str:
    if not values:
        return ""
    peak = max(values) or 1.0
    recent = values[-width:]
    return "".join(
        SPARK[min(len(SPARK) - 1, int(value / peak * (len(SPARK) - 1)))]
        for value in recent
    )


def _bar(value: float, scale: float, width: int = 30) -> str:
    fraction = min(1.0, value / scale) if scale else 0.0
    filled = int(round(fraction * width))
    return "█" * filled + "░" * (width - filled)


class SpeedDashboard:
    """Panel en vivo con el progreso de cada fase."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self.phase = "Iniciando"
        self.server = ""
        self.idle: LatencyStats | None = None
        self.show_upload = True
        self._series = {"down": deque(maxlen=40), "up": deque(maxlen=40)}
        self._current = {"down": 0.0, "up": 0.0}
        self._peak = {"down": 0.0, "up": 0.0}
        self._phase_started = time.monotonic()
        self._live: Live | None = None

    def start(self) -> None:
        self._live = Live(
            self._render(), console=self.console, refresh_per_second=12
        )
        self._live.start(refresh=True)

    def stop(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render())

    def set_phase(self, phase: str) -> None:
        self.phase = phase
        self._phase_started = time.monotonic()
        self._refresh()

    def set_server(self, text: str) -> None:
        self.server = text
        self._refresh()

    def set_idle(self, stats: LatencyStats) -> None:
        self.idle = stats
        self._refresh()

    def set_upload_enabled(self, enabled: bool) -> None:
        self.show_upload = enabled

    def sample(self, direction: str, instant: float, average: float) -> None:
        if direction not in self._series:
            return
        now = time.monotonic()
        previous = self._current[direction]
        smoothed = instant if previous == 0 else previous * 0.6 + instant * 0.4
        self._current[direction] = smoothed
        # Ignora el arranque (slow start) para no inflar el pico mostrado.
        if now - self._phase_started >= 1.5:
            self._peak[direction] = max(self._peak[direction], smoothed)
            self._series[direction].append(smoothed)
        self._refresh()

    def _line(self, key: str, label: str) -> Text:
        value = self._current[key]
        peak = self._peak[key]
        scale = max(50.0, math.ceil(max(peak, value, 10.0) / 50.0) * 50.0)
        color = ACCENT if key == "down" else "magenta"
        line = Text()
        line.append(f"{label:<9}", style="bold")
        line.append(f"{metrics.format_mbps(value):>12}", style=f"bold {color}")
        line.append("  ")
        line.append(_bar(value, scale, width=18), style=color)
        line.append(f"  {_sparkline(list(self._series[key]), width=14)}", style="green")
        line.append(f"  pico {metrics.format_mbps(peak)}", style="dim")
        return line

    def _render(self) -> Group:
        header = Text("Speed Test", style=f"bold {ACCENT}")
        if self.server:
            header.append(f"  ·  {self.server}", style="dim")
        parts: list = [Panel(header, border_style=ACCENT, expand=False)]

        latency = Text()
        if self.idle is not None and self.idle.samples_ms:
            stats = metrics.summarize_latency(self.idle)
            latency.append("Ping ", style="bold")
            latency.append(f"{stats['median']:.1f} ms", style="cyan")
            latency.append(
                f"   ·   jitter {stats['jitter']:.1f} ms   ·   p95 {stats['p95']:.1f} ms",
                style="dim",
            )
        else:
            latency.append("Ping     midiendo...", style="dim")
        parts.append(latency)
        parts.append(self._line("down", "Descarga"))
        if self.show_upload:
            parts.append(self._line("up", "Subida"))
        parts.append(Text(f"» {self.phase}", style=f"bold {ACCENT}"))
        return Group(*parts)


def _add(table: Table, label: str, value: Text) -> None:
    table.add_row(Text(label, style="dim"), value)


def render_result(
    result: SpeedTestResult,
    console: Console,
    previous: dict | None = None,
    plan: tuple[float, float | None] | None = None,
) -> None:
    idle = metrics.summarize_latency(result.idle)
    down = metrics.transfer_stats(result.down)
    up = metrics.transfer_stats(result.up)

    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", no_wrap=True)
    table.add_column()

    server = Text("Cloudflare", style=f"bold {ACCENT}")
    if result.colo:
        server.append(f" · {result.colo}", style="bold")
    if result.location:
        server.append(f" ({result.location})", style="dim")
    if result.ip:
        server.append(f" · {result.ip}", style="dim")
    server.append(f" · motor {result.engine}", style="dim")
    _add(table, "Servidor", server)

    ping = Text()
    ping.append(f"{idle['median']:.1f} ms", style="bold cyan")
    ping.append(
        f"   min {idle['min']:.1f} · p95 {idle['p95']:.1f} · máx {idle['max']:.1f}",
        style="dim",
    )
    _add(table, "Ping", ping)

    jitter = Text(
        f"{idle['jitter']:.1f} ms", style="bold cyan" if idle["jitter"] < 10 else "yellow"
    )
    if idle["failed"]:
        jitter.append(f"   ·   sondas fallidas {idle['failed']} ({idle['loss_pct']:.1f}%)", style="yellow")
    _add(table, "Jitter", jitter)

    down_text = Text()
    down_text.append(metrics.format_mbps(down["avg"]), style="bold green")
    down_text.append(
        f"   p90 {metrics.format_mbps(down['p90'])} · pico {metrics.format_mbps(down['peak'])}",
        style="dim",
    )
    _add(table, "Bajada", down_text)

    up_text = Text()
    if result.up is None:
        up_text.append("omitida (--no-upload)", style="dim")
    else:
        up_text.append(metrics.format_mbps(up["avg"]), style="bold green")
        up_text.append(
            f"   p90 {metrics.format_mbps(up['p90'])} · pico {metrics.format_mbps(up['peak'])}",
            style="dim",
        )
    _add(table, "Subida", up_text)

    bloat = Text()
    if result.down_bloat.delta_ms is None:
        bloat.append("no medido", style="dim")
    else:
        down_grade = result.down_bloat.grade
        bloat.append(
            f"bajada +{result.down_bloat.delta_ms:.0f} ms ",
            style=metrics.grade_style(down_grade),
        )
        bloat.append(f"({down_grade})", style=f"bold {metrics.grade_style(down_grade)}")
        if result.up_bloat.delta_ms is not None:
            up_grade = result.up_bloat.grade
            bloat.append("   ·   subida ", style="dim")
            bloat.append(
                f"+{result.up_bloat.delta_ms:.0f} ms ",
                style=metrics.grade_style(up_grade),
            )
            bloat.append(f"({up_grade})", style=f"bold {metrics.grade_style(up_grade)}")
    _add(table, "Bufferbloat", bloat)

    context = Text()
    if result.dns_ms is not None:
        context.append(f"DNS {result.dns_ms:.0f} ms", style="dim")
    if result.ttfb_ms is not None:
        context.append(f"   ·   TTFB {result.ttfb_ms:.0f} ms", style="dim")
    if result.dns_ms is not None or result.ttfb_ms is not None:
        _add(table, "Contexto", context)

    if plan is not None and plan[0]:
        plan_text = Text()
        plan_text.append(
            f"{down['avg'] / plan[0] * 100:.1f}%", style="bold green"
        )
        plan_text.append(
            f" de {plan[0]:g} Mbps contratados", style="dim"
        )
        if plan[1] and result.up is not None:
            plan_text.append("   ·   ")
            plan_text.append(f"{up['avg'] / plan[1] * 100:.1f}%", style="bold green")
            plan_text.append(f" de {plan[1]:g} Mbps", style="dim")
        _add(table, "Plan", plan_text)

    if previous:
        compare = Text()
        down_delta = metrics.delta_pct(down["avg"], float(previous.get("down") or 0))
        up_delta = (
            metrics.delta_pct(up["avg"], float(previous.get("up") or 0))
            if result.up is not None
            else None
        )
        if down_delta is not None:
            arrow = "▲" if down_delta >= 0 else "▼"
            style = "green" if down_delta >= 0 else "red"
            compare.append(f"{arrow} {abs(down_delta):.1f}% bajada", style=style)
        if up_delta is not None:
            if compare.plain:
                compare.append("   ·   ", style="dim")
            arrow = "▲" if up_delta >= 0 else "▼"
            style = "green" if up_delta >= 0 else "red"
            compare.append(f"{arrow} {abs(up_delta):.1f}% subida", style=style)
        if compare.plain:
            compare.append(
                f"   (vs {history.format_timestamp(previous.get('ts', ''))})",
                style="dim",
            )
            _add(table, "Comparación", compare)

    title = Text("Resultado", style=f"bold {ACCENT}")
    title.append(f"  {result.started_at.strftime('%Y-%m-%d %H:%M')}", style="dim")
    console.print(
        Panel(table, title=title, border_style=ACCENT, expand=False, padding=(0, 2))
    )

    if result.warnings:
        console.print(
            Panel(
                "\n".join(f"• {warning}" for warning in result.warnings),
                title="[yellow]Avisos[/yellow]",
                border_style="yellow",
                expand=False,
            )
        )


def render_history(records: list[dict], console: Console) -> None:
    if not records:
        console.print(
            Panel(
                "Todavia no hay mediciones guardadas.\nEjecuta [green]lt speedtest[/green] primero.",
                title="Historial",
                border_style=ACCENT,
                expand=False,
            )
        )
        return

    table = Table(
        box=box.SIMPLE_HEAD,
        header_style=f"bold {ACCENT}",
        expand=False,
        pad_edge=False,
        padding=(0, 1),
    )
    table.add_column("Fecha", no_wrap=True)
    table.add_column("Bajada", justify="right", no_wrap=True)
    table.add_column("Subida", justify="right", no_wrap=True)
    table.add_column("Ping", justify="right", no_wrap=True)
    table.add_column("Jitter", justify="right", no_wrap=True)
    table.add_column("Buffer", no_wrap=True)
    table.add_column("PoP", style="dim", no_wrap=True)

    for record in records:
        bloat = record.get("grade_down") or "-"
        delta = record.get("down_bloat")
        bloat_text = Text(f"{bloat} {float(delta or 0):+.0f}ms")
        bloat_text.stylize(metrics.grade_style(bloat))
        table.add_row(
            history.format_timestamp(record.get("ts", "")),
            metrics.format_mbps(float(record.get("down") or 0)),
            metrics.format_mbps(float(record.get("up") or 0)),
            f"{float(record.get('ping') or 0):.1f} ms",
            f"{float(record.get('jitter') or 0):.1f} ms",            bloat_text,
            record.get("colo") or "-",
        )

    console.print(
        Panel(
            table,
            title=f"Últimas {len(records)} mediciones",
            border_style=ACCENT,
            expand=False,
        )
    )

    downs = [float(record.get("down") or 0) for record in records]
    ups = [float(record.get("up") or 0) for record in records]
    summary = Text("Promedio: ", style="dim")
    summary.append(metrics.format_mbps(metrics.mean(downs)), style="green")
    summary.append(" / ", style="dim")
    summary.append(metrics.format_mbps(metrics.mean(ups)), style="green")
    summary.append("   ·   Mejor: ", style="dim")
    summary.append(metrics.format_mbps(max(downs)), style="green")
    summary.append(" / ", style="dim")
    summary.append(metrics.format_mbps(max(ups)), style="green")
    console.print(summary)
    console.print(Text(f"Historial: {history.history_path()}", style="dim"))


def render_help(console: Console) -> None:
    text = Text()
    text.append("lt speedtest", style=f"bold {ACCENT}")
    text.append(" - Mide tu conexion real (Cloudflare, sin publicidad)\n\n", style="dim")
    text.append("Uso:\n", style="bold")
    text.append("  lt speedtest                     Test equilibrado (10s + 10s, 6 streams)\n")
    text.append("  lt speedtest --quick             Rápido (5s + 5s, 4 streams)\n")
    text.append("  lt speedtest --full              Exhaustivo (20s + 20s, 8 streams)\n")
    text.append("  lt speedtest --no-upload         Solo bajada y latencia\n\n")
    text.append("Historial:\n", style="bold")
    text.append("  lt speedtest --history 10        Ver las ultimas 10 mediciones\n")
    text.append("  lt speedtest --compare           Comparar con la medicion anterior\n")
    text.append("  lt speedtest --plan 500/50       % del plan contratado (Mbps bajada/subida)\n\n")
    text.append("Automatizacion:\n", style="bold")
    text.append("  lt speedtest --min-down 300 --min-up 30   Exit code 2 si no cumple\n\n")
    text.append("Tecnico:\n", style="bold")
    text.append("  --duration, -t SEGUNDOS          Duracion por sentido\n")
    text.append("  --streams, -s N                  Conexiones paralelas\n")
    text.append("  --engine, -e python|curl         Motor de transferencia\n")
    text.append("  --ipv4, -4 / --ipv6, -6          Forzar familia de IP\n")
    text.append("  ??                               Mostrar esta ayuda\n\n")
    text.append("Mide latencia, jitter, descarga, subida y bufferbloat (latencia bajo carga).\n", style="dim")
    text.append(f"Historial en: {history.history_path()}", style="dim")
    console.print(Panel(text, title="speedtest", border_style=ACCENT, expand=False))
