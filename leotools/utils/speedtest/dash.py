"""Dashboard combinado: sistema, Ethernet y pruebas de Internet."""

import asyncio
import time
from contextlib import suppress

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Static

from leotools.utils import sysmon

from . import metrics
from .monitor import MonitorApp, keys_text


def _bar(percent: float, width: int = 24) -> str:
    value = max(0.0, min(100.0, percent))
    filled = int(round(value / 100 * width))
    return "█" * filled + "░" * (width - filled)


def _color(percent: float) -> str:
    if percent >= 85:
        return "red"
    if percent >= 65:
        return "yellow"
    return "green"


def _link(mbps: float) -> str:
    if not mbps:
        return "n/d"
    if mbps >= 1000:
        return f"{mbps / 1000:.1f} Gbps"
    return f"{mbps:.0f} Mbps"


def _temp_color(value: float | None) -> str:
    if value is None:
        return "dim"
    if value >= 85:
        return "red"
    if value >= 70:
        return "yellow"
    return "green"


class DashApp(MonitorApp):
    """Sistema + red + pruebas de Internet en una sola pantalla."""

    CSS = """
    Screen {
        background: $surface;
        layout: vertical;
    }
    #main {
        height: 1fr;
    }
    #left {
        width: 46%;
        padding: 0 1;
    }
    #right {
        width: 54%;
        padding: 0 1;
        border-left: solid $primary;
    }
    #cpu {
        height: 2;
    }
    #mem {
        height: 3;
    }
    #temps {
        height: 4;
    }
    #eth {
        height: 6;
    }
    #disk {
        height: 3;
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
        height: 5;
        content-align: center middle;
    }
    #history {
        height: 7;
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
        height: 1;
        background: $panel;
    }
    """

    def __init__(
        self,
        mode: str = "cycle",
        streams: int = 4,
        burst: int | None = None,
        rest: int | None = None,
    ) -> None:
        super().__init__(mode=mode, streams=streams, burst=burst, rest=rest)
        self.sys = sysmon.SystemSampler()
        self.system = self.sys.sample()
        self.temps = sysmon.Temps(note="midiendo...")
        self.sys_error = ""
        self._sys_task: asyncio.Task | None = None
        self._last_temps = 0.0

    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield Static(id="cpu")
                yield Static(id="mem")
                yield Static(id="temps")
                yield Static(id="eth")
                yield Static(id="disk")
            with Vertical(id="right"):
                yield Static(id="speed")
                yield Static(id="spark")
                yield Static(id="cat")
                yield Static(id="history")
        yield Static(id="status")
        yield Static(keys_text(), id="keys")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        self._render_system()
        self._sys_task = asyncio.create_task(self._system_loop())

    async def on_unmount(self) -> None:
        if self._sys_task is not None:
            self._sys_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._sys_task
        await super().on_unmount()

    async def _system_loop(self) -> None:
        try:
            while not self._exiting:
                try:
                    self.system = self.sys.sample()
                    self.sys_error = ""
                except Exception as exc:  # noqa: BLE001 - se muestra en pantalla
                    self.sys_error = f"{type(exc).__name__}: {exc}"
                now = time.monotonic()
                if now - self._last_temps >= 5:
                    self._last_temps = now
                    try:
                        self.temps = await asyncio.to_thread(self.sys.sample_temps)
                    except Exception:
                        pass
                self._render_system()
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            raise

    # ------------------------------------------------------------------ pintado

    def _render_system(self) -> None:
        snapshot = self.system
        dom = snapshot.cpu_percent
        color = _color(dom)
        cpu = Text()
        cpu.append("CPU ", style="bold")
        cpu.append(f"{dom:5.1f}%", style=f"bold {color}")
        cpu.append(f"  {snapshot.cores}h  {snapshot.freq_mhz / 1000:.2f} GHz", style="dim")
        cpu.append("\n")
        cpu.append(_bar(dom), style=color)
        self.query_one("#cpu", Static).update(cpu)

        ram_color = _color(snapshot.ram_percent)
        mem = Text()
        mem.append("RAM ", style="bold")
        mem.append(f"{snapshot.ram_percent:5.1f}%", style=f"bold {ram_color}")
        mem.append(
            f"   {metrics.human_bytes(snapshot.ram_used)} / {metrics.human_bytes(snapshot.ram_total)}",
            style="dim",
        )
        mem.append("\n")
        mem.append(_bar(snapshot.ram_percent), style=ram_color)
        mem.append(
            f"\nSwap {metrics.human_bytes(snapshot.swap_used)}"
            f" / {metrics.human_bytes(snapshot.swap_total)} ({snapshot.swap_percent:.0f}%)",
            style="dim",
        )
        self.query_one("#mem", Static).update(mem)

        temps = Text()
        temps.append("Temperaturas\n", style="bold")
        cpu_temp = self.temps.cpu
        gpu_temp = self.temps.gpu
        temps.append("CPU ", style="dim")
        temps.append(
            f"{cpu_temp:.1f}°C" if cpu_temp is not None else "n/d",
            style=f"bold {_temp_color(cpu_temp)}",
        )
        temps.append("    GPU ", style="dim")
        temps.append(
            f"{gpu_temp:.1f}°C" if gpu_temp is not None else "n/d",
            style=f"bold {_temp_color(gpu_temp)}",
        )
        if self.temps.gpu_util is not None:
            temps.append(f"  ({self.temps.gpu_util:.0f}%)", style="dim")
        temps.append("\n")
        if self.temps.note:
            temps.append(self.temps.note, style="dim")
        else:
            temps.append(f"fuente: {self.temps.source or '-'}", style="dim")
        if gpu_temp is not None and self.temps.gpu_mem_total:
            temps.append(
                f"  ·  VRAM {self.temps.gpu_mem_used or 0}/{self.temps.gpu_mem_total} MB",
                style="dim",
            )
        self.query_one("#temps", Static).update(temps)

        eth = Text()
        eth.append("Ethernet\n", style="bold")
        eth.append(f"{snapshot.net_name}  ·  {_link(snapshot.net_link_mbps)}", style="cyan")
        eth.append(f"\nIP {snapshot.net_ip}", style="dim")
        eth.append("\n")
        eth.append(f"↓ {metrics.format_mbps(snapshot.net_down_mbps)}", style="bold green")
        eth.append(f"    ↑ {metrics.format_mbps(snapshot.net_up_mbps)}", style="bold magenta")
        eth.append(
            f"\nTotal ↓ {metrics.human_bytes(snapshot.net_recv)}"
            f"   ↑ {metrics.human_bytes(snapshot.net_sent)}",
            style="dim",
        )
        eth.append(f"\nerrores {snapshot.net_errors}  ·  drops {snapshot.net_drops}", style="dim")
        self.query_one("#eth", Static).update(eth)

        disk_color = _color(snapshot.disk_percent)
        disk = Text()
        disk.append("Disco ", style="bold")
        disk.append(f"{snapshot.disk_percent:5.1f}%", style=f"bold {disk_color}")
        disk.append(
            f"   {metrics.human_bytes(snapshot.disk_used)}"
            f" / {metrics.human_bytes(snapshot.disk_total)}",
            style="dim",
        )
        disk.append("\n")
        disk.append(_bar(snapshot.disk_percent), style=disk_color)
        if self.sys_error:
            disk.append(f"\n{self.sys_error[:34]}", style="red")
        else:
            free = max(snapshot.disk_total - snapshot.disk_used, 0)
            disk.append(f"\nLibre {metrics.human_bytes(free)}", style="dim")
        self.query_one("#disk", Static).update(disk)

    def summary(self) -> dict:
        data = super().summary()
        data.update(
            {
                "cpu": self.system.cpu_percent,
                "ram": self.system.ram_percent,
                "cpu_temp": self.temps.cpu,
                "gpu_temp": self.temps.gpu,
                "nic": self.system.net_name,
                "link": self.system.net_link_mbps,
            }
        )
        return data
