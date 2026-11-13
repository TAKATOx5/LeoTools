"""Dashboard TUI con medicion continua, rotacion de servidores y gato animado."""

import asyncio
import time
import traceback
from collections import deque
from contextlib import suppress
from datetime import datetime

from rich import box
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Static

from . import cat, cloudflare, history, metrics, probes
from .models import EngineError

MODES = ("cycle", "continuous", "sample")
MODE_LABELS = {"cycle": "ciclico", "continuous": "continuo", "sample": "muestreo"}
PRESETS = {"cycle": (4, 2), "continuous": (5, 0), "sample": (3, 15)}
SOURCES = [("Cloudflare", None), *cloudflare.FALLBACK_SOURCES]
HISTORY_SIZE = 6


def format_duration(seconds: float) -> str:
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def keys_text() -> Text:
    text = Text()
    legend = [
        ("Esc", "salir"),
        ("p", "pausar"),
        ("m", "cambiar modo"),
        ("1", "ciclico"),
        ("2", "continuo"),
        ("3", "muestreo"),
        ("[ ]", "descanso"),
    ]
    for index, (key, label) in enumerate(legend):
        if index:
            text.append("   ", style="dim")
        text.append(key, style="bold cyan")
        text.append(f" {label}", style="dim")
    return text


class MonitorApp(App):
    """Panel en vivo: rota servidores, mide, anima al gato y guarda historial."""

    CSS = """
    Screen {
        background: $surface;
        layout: vertical;
    }
    #speed {
        height: 2;
        content-align: center middle;
    }
    #spark {
        height: 2;
        content-align: center middle;
    }
    #cat {
        height: 6;
        content-align: center middle;
    }
    #history {
        height: 7;
        padding: 0 2;
    }
    #status {
        height: 3;
        content-align: center middle;
    }
    #keys {
        height: 2;
        content-align: center middle;
    }
    Footer {
        background: $panel;
    }
    """

    BINDINGS = [
        Binding("escape", "quit", "Salir"),
        Binding("ctrl+c", "quit", "Salir"),
        Binding("p", "toggle_pause", "Pausar"),
        Binding("m", "cycle_mode", "Cambiar modo"),
        Binding("1", "mode_cycle", "Ciclico"),
        Binding("2", "mode_continuous", "Continuo"),
        Binding("3", "mode_sample", "Muestreo"),
        Binding("[", "less_rest", "Menos descanso"),
        Binding("]", "more_rest", "Mas descanso"),
    ]

    def __init__(
        self,
        mode: str = "cycle",
        streams: int = 4,
        burst: int | None = None,
        rest: int | None = None,
    ) -> None:
        super().__init__()
        self.mode = mode
        default_burst, default_rest = PRESETS[mode]
        self.burst = default_burst if burst is None else burst
        self.rest = default_rest if rest is None else rest
        self.streams = streams

        self.mbps = 0.0
        self.peak = 0.0
        self.ping: float | None = None
        self.server = "Conectando..."
        self.series: list[float] = []
        self.history: deque[dict] = deque(maxlen=HISTORY_SIZE)
        self.history_dirty = True
        self.cycles = 0
        self.errors = 0
        self.throttled = 0
        self.bytes_total = 0
        self.measured_seconds = 0.0
        self.sources_used: list[str] = []
        self.last_error = ""

        self.paused = False
        self.resting = False
        self.phase = "Iniciando"

        self.source_index = 0
        self.source_name = SOURCES[0][0]
        self.rotation_pos = 0
        self.block_until = [0.0 for _ in SOURCES]

        self.started = time.monotonic()
        self._last_spark = 0.0
        self._anim = 0.0
        self._frame = 0
        self._exiting = False
        self._session = None
        self._task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="speed")
        yield Static(id="spark")
        yield Static(id="cat")
        yield Static(id="history")
        yield Static(id="status")
        yield Static(keys_text(), id="keys")
        yield Footer()

    def on_mount(self) -> None:
        self.started = time.monotonic()
        self._task = asyncio.create_task(self._measure_loop())
        self.set_interval(0.1, self._tick)

    async def on_unmount(self) -> None:
        self._exiting = True
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._task

    # ------------------------------------------------------------------ medicion

    def _current_rest(self) -> int:
        return 0 if self.mode == "continuous" else self.rest

    def _log_error(self, context: str, exc: BaseException) -> None:
        self.last_error = f"{type(exc).__name__}: {exc}"
        try:
            path = history.history_path().parent / "monitor.log"
            with path.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"{datetime.now().isoformat(timespec='seconds')} [{context}] "
                    f"{self.last_error}\n{traceback.format_exc()}\n"
                )
        except OSError:
            pass

    def _pick_source(self) -> tuple[int, str, str | None] | None:
        now = time.monotonic()
        for offset in range(len(SOURCES)):
            index = (self.rotation_pos + offset) % len(SOURCES)
            if self.block_until[index] <= now:
                self.rotation_pos = index
                return index, SOURCES[index][0], SOURCES[index][1]
        return None

    def _advance_source(self) -> None:
        self.rotation_pos = (self.source_index + 1) % len(SOURCES)

    def _block_source(self, index: int, seconds: int) -> None:
        self.block_until[index] = time.monotonic() + seconds

    async def _measure_loop(self) -> None:
        session = cloudflare.make_session(self.streams)
        self._session = session
        try:
            try:
                trace = await cloudflare.fetch_trace(session)
                colo = trace.get("colo", "")
                self.server = f"Cloudflare {colo}".strip()
                await self._refresh_ping()
            except Exception as exc:
                self._log_error("trace", exc)
                self.server = "Sin conexion"
                self.phase = "Reintentando"

            while not self._exiting:
                if self.paused:
                    self.resting = True
                    await asyncio.sleep(0.2)
                    continue

                picked = self._pick_source()
                if picked is None:
                    now = time.monotonic()
                    wait = int(max(5, min(30, min(self.block_until) - now)))
                    self.phase = "Servidores limitados"
                    self.resting = True
                    self.mbps = 0.0
                    await self._rest(wait)
                    continue

                index, name, url = picked
                self.source_index = index
                self.source_name = name
                self.resting = False
                self.phase = "Midiendo"

                try:
                    transfer = await cloudflare.download(
                        session,
                        self.burst,
                        self.streams,
                        self._on_sample,
                        source_url=url,
                    )
                    self.throttled += transfer.throttled
                    if transfer.bytes_total <= 0:
                        if transfer.throttled:
                            self._block_source(index, 90 if index == 0 else 45)
                            self._advance_source()
                            continue
                        if transfer.errors:
                            self._block_source(index, 30)
                            self._advance_source()
                            continue
                        raise EngineError("sin datos")

                    self.bytes_total += transfer.bytes_total
                    self.measured_seconds += transfer.elapsed
                    self.cycles += 1
                    self.last_error = ""
                    if name not in self.sources_used:
                        self.sources_used.append(name)
                    self.history.append(
                        {
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "source": name,
                            "mbps": transfer.bytes_total * 8.0 / transfer.elapsed / 1_000_000,
                            "ping": self.ping,
                        }
                    )
                    self.history_dirty = True
                    self._advance_source()
                    await self._refresh_ping()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._log_error("download", exc)
                    self.errors += 1
                    self.phase = "Reintentando"
                    self.mbps = 0.0
                    await asyncio.sleep(2)
                    continue

                rest = self._current_rest()
                if rest > 0 and not self._exiting:
                    self.phase = "Descansando"
                    self.resting = True
                    self.mbps = 0.0
                    await self._rest(rest)
        finally:
            await session.close()

    def _on_sample(self, direction: str, instant: float, average: float) -> None:
        if self.paused or self._exiting:
            return
        previous = self.mbps
        self.mbps = instant if previous == 0 else previous * 0.65 + instant * 0.35
        self.peak = max(self.peak, self.mbps)
        now = time.monotonic()
        if now - self._last_spark >= 1.0:
            self.series.append(self.mbps)
            self._last_spark = now

    async def _refresh_ping(self) -> None:
        if self._session is None:
            return
        if self.block_until[0] > time.monotonic():
            return
        try:
            stats = await probes.measure_latency(self._session, count=4, interval=0)
        except Exception as exc:
            self._log_error("ping", exc)
            return
        summary = metrics.summarize_latency(stats)
        if summary["count"]:
            self.ping = summary["median"]

    async def _rest(self, seconds: int) -> None:
        mode = self.mode
        end = time.monotonic() + seconds
        next_zero = time.monotonic()
        while time.monotonic() < end and not self._exiting and not self.paused:
            if self.mode != mode:
                break
            now = time.monotonic()
            if now >= next_zero:
                self.series.append(0.0)
                self._last_spark = now
                next_zero = now + 1.0
            await asyncio.sleep(0.2)

    # ------------------------------------------------------------------ pintado

    def _tick(self) -> None:
        tier = cat.tier_for(0 if self.paused or self.resting else self.mbps)
        self._anim += tier.fps * 0.1
        if self._anim >= 1:
            steps = int(self._anim)
            self._anim -= steps
            self._frame += steps
        self._render_speed(tier)
        self._render_spark()
        self._render_cat(tier)
        if self.history_dirty:
            self._render_history()
        self._render_status()

    def _render_speed(self, tier: cat.CatTier) -> None:
        text = Text()
        text.append("↓ ", style=tier.color)
        text.append(metrics.format_mbps(self.mbps), style=f"bold {tier.color}")
        text.append("    pico ", style="dim")
        text.append(metrics.format_mbps(self.peak), style="green")
        text.append("    ping ", style="dim")
        text.append(
            f"{self.ping:.0f} ms" if self.ping is not None else "--",
            style="cyan",
        )
        self.query_one("#speed", Static).update(text)

    def _render_spark(self) -> None:
        line = cat.sparkline(self.series)
        text = Text()
        text.append(line or " ", style="bright_blue")
        text.append("\nultimos 60 s", style="dim")
        self.query_one("#spark", Static).update(text)

    def _render_cat(self, tier: cat.CatTier) -> None:
        text = Text(cat.frame_for(tier, self._frame), style=tier.color)
        text.append(f"\n{tier.label}", style=f"italic {tier.color}")
        self.query_one("#cat", Static).update(text)

    def _render_history(self) -> None:
        self.history_dirty = False
        if not self.history:
            content = Text(
                "Historial de la sesion: esperando la primera medicion...",
                style="dim",
            )
        else:
            table = Table(
                box=box.SIMPLE_HEAD,
                expand=False,
                pad_edge=False,
                padding=(0, 1),
                header_style="bold bright_blue",
            )
            table.add_column("Hora", style="dim", no_wrap=True)
            table.add_column("Fuente", no_wrap=True)
            table.add_column("Bajada", justify="right", no_wrap=True)
            table.add_column("Ping", justify="right", no_wrap=True)
            for entry in self.history:
                ping = entry.get("ping")
                table.add_row(
                    entry["time"],
                    entry["source"],
                    metrics.format_mbps(entry["mbps"]),
                    f"{ping:.0f} ms" if ping is not None else "--",
                )
            content = table
        self.query_one("#history", Static).update(content)

    def _render_status(self) -> None:
        if self.paused:
            state = Text("PAUSADO", style="bold yellow")
        elif self.phase == "Servidores limitados":
            state = Text("SERVIDORES EN ESPERA", style="bold yellow")
        elif self.resting:
            state = Text("DESCANSANDO", style="dim")
        elif self.phase == "Reintentando":
            state = Text("REINTENTANDO", style="bold red")
        else:
            state = Text("MIDIENDO", style="bold green")

        detail = (
            f"{self.burst}s sin descanso"
            if self.mode == "continuous"
            else f"{self.burst}s mide / {self.rest}s descansa"
        )
        text = Text()
        text.append_text(state)
        text.append(
            f"  ·  modo {MODE_LABELS[self.mode]} ({detail})"
            f"  ·  fuente {self.source_index + 1}/{len(SOURCES)} {self.source_name}",
            style="dim",
        )
        text.append(
            f"\nciclos {self.cycles}  ·  {metrics.human_bytes(self.bytes_total)}"
            f"  ·  {format_duration(time.monotonic() - self.started)}",
            style="dim",
        )

        now = time.monotonic()
        blocked = sum(1 for until in self.block_until if until > now)
        if blocked:
            text.append(f"  ·  {blocked} servidor(es) en espera", style="yellow")
        if self.throttled:
            text.append(f"  ·  429 x{self.throttled}", style="yellow")
        if self.errors:
            text.append(f"  ·  errores {self.errors}", style="yellow")
        if self.last_error and self.phase == "Reintentando":
            text.append(f"\n{self.last_error[:70]}", style="red")
        self.query_one("#status", Static).update(text)

    # ------------------------------------------------------------------ acciones

    def _apply_mode(self, mode: str) -> None:
        self.mode = mode
        self.burst, self.rest = PRESETS[mode]
        self.phase = "Midiendo"
        self.resting = False
        self.mbps = 0.0

    def action_quit(self) -> None:
        self._exiting = True
        self.exit()

    def action_toggle_pause(self) -> None:
        self.paused = not self.paused
        if self.paused:
            self.phase = "Pausado"
            self.mbps = 0.0
        else:
            self.phase = "Midiendo"

    def action_cycle_mode(self) -> None:
        index = MODES.index(self.mode)
        self._apply_mode(MODES[(index + 1) % len(MODES)])

    def action_mode_cycle(self) -> None:
        self._apply_mode("cycle")

    def action_mode_continuous(self) -> None:
        self._apply_mode("continuous")

    def action_mode_sample(self) -> None:
        self._apply_mode("sample")

    def action_more_rest(self) -> None:
        if self.mode == "continuous":
            self.burst = min(10, self.burst + 1)
        else:
            self.rest = min(120, self.rest + 3)

    def action_less_rest(self) -> None:
        if self.mode == "continuous":
            self.burst = max(2, self.burst - 1)
        else:
            self.rest = max(0 if self.mode == "cycle" else 3, self.rest - 3)

    def summary(self) -> dict:
        elapsed = max(time.monotonic() - self.started, 1.0)
        measured = max(self.measured_seconds, 0.001)
        return {
            "seconds": elapsed,
            "measured_seconds": self.measured_seconds,
            "peak": self.peak,
            "bytes": self.bytes_total,
            "cycles": self.cycles,
            "errors": self.errors,
            "throttled": self.throttled,
            "avg": self.bytes_total * 8.0 / measured / 1_000_000,
            "mode": self.mode,
            "sources": list(self.sources_used),
        }
