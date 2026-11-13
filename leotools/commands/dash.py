from enum import Enum

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from leotools.utils.speedtest import metrics
from leotools.utils.speedtest.dash import DashApp
from leotools.utils.speedtest.monitor import format_duration

app = typer.Typer(
    help="Dashboard de sistema + Ethernet + pruebas de Internet.",
    invoke_without_command=True,
)

console = Console()
ACCENT = "bright_blue"


class DashMode(str, Enum):
    cycle = "cycle"
    continuous = "continuous"
    sample = "sample"


HELP_TEXT = f"""
[bold {ACCENT}]lt dash[/bold {ACCENT}] - Sistema, Ethernet e Internet en una pantalla

[bold]Paneles:[/bold]
  [green]CPU[/green]         uso, hilos y frecuencia
  [green]RAM[/green]         memoria y swap
  [green]Temperaturas[/green] CPU (si hay LibreHardwareMonitor) y GPU (nvidia-smi)
  [green]Ethernet[/green]    interfaz activa, enlace, IP, velocidad y totales
  [green]Disco[/green]       uso del disco del sistema
  [green]Internet[/green]    prueba rotando servidores + gato + historial

[bold]Uso:[/bold]
  [green]lt dash[/green]                    Modo ciclico (4s mide / 2s descansa)
  [green]lt dash --mode continuous[/green]  Sin descanso
  [green]lt dash --mode sample[/green]      Mide 3s cada 15s
  [green]lt dash --streams 6[/green]        Conexiones en paralelo

[bold]Teclas:[/bold]
  [green]Esc / Ctrl+C[/green]   Salir y ver el resumen
  [green]p[/green]              Pausar / reanudar las pruebas de Internet
  [green]m[/green]              Cambiar de modo (ciclico -> continuo -> muestreo)
  [green]1[/green]              Modo ciclico
  [green]2[/green]              Modo continuo
  [green]3[/green]              Modo muestreo
  [green][ / ][/green]          Menos / mas segundos de descanso

[bold]Temperaturas en Windows:[/bold]
  [dim]La GPU NVIDIA se lee con nvidia-smi. Para la CPU, ejecuta
  LibreHardwareMonitor en segundo plano (WMI). Sin el, la CPU sale n/d.[/dim]

[bold]Opciones:[/bold]
  --mode, -m       cycle | continuous | sample
  --streams, -s    Conexiones en paralelo (default: 4)
  --burst, -b      Segundos midiendo por ciclo
  --rest, -r       Segundos de descanso por ciclo
"""


@app.callback(invoke_without_command=True)
def main(
    mode: DashMode = typer.Option(DashMode.cycle, "--mode", "-m", help="Modo inicial"),
    streams: int = typer.Option(4, "--streams", "-s", help="Conexiones en paralelo"),
    burst: int = typer.Option(None, "--burst", "-b", help="Segundos midiendo"),
    rest: int = typer.Option(None, "--rest", "-r", help="Segundos de descanso"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="dash", border_style=ACCENT, expand=False))
        raise typer.Exit()

    if not 1 <= streams <= 32:
        console.print(Panel("[red]Las conexiones deben estar entre 1 y 32.[/red]", border_style="red", expand=False))
        raise typer.Exit(1)
    if burst is not None and not 2 <= burst <= 15:
        console.print(Panel("[red]El burst debe estar entre 2 y 15 segundos.[/red]", border_style="red", expand=False))
        raise typer.Exit(1)
    if rest is not None and not 0 <= rest <= 120:
        console.print(Panel("[red]El descanso debe estar entre 0 y 120 segundos.[/red]", border_style="red", expand=False))
        raise typer.Exit(1)

    app_instance = DashApp(
        mode=mode.value,
        streams=streams,
        burst=burst,
        rest=rest,
    )
    try:
        app_instance.run()
    except KeyboardInterrupt:
        pass

    summary = app_instance.summary()

    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", no_wrap=True)
    table.add_column()

    table.add_row("Tiempo", format_duration(summary["seconds"]))
    table.add_row("Pico", metrics.format_mbps(summary["peak"]))
    table.add_row("Promedio", metrics.format_mbps(summary["avg"]))
    table.add_row("Datos", metrics.human_bytes(summary["bytes"]))
    table.add_row("Ciclos", str(summary["cycles"]))
    if summary["sources"]:
        table.add_row("Fuentes", ", ".join(summary["sources"]))
    if summary["throttled"]:
        table.add_row("429", str(summary["throttled"]))
    if summary["errors"]:
        table.add_row("Errores", str(summary["errors"]))

    table.add_row("CPU", f"{summary['cpu']:.1f}%")
    table.add_row("RAM", f"{summary['ram']:.1f}%")
    if summary["cpu_temp"] is not None:
        table.add_row("Temp CPU", f"{summary['cpu_temp']:.1f}°C")
    if summary["gpu_temp"] is not None:
        table.add_row("Temp GPU", f"{summary['gpu_temp']:.1f}°C")
    table.add_row("Ethernet", f"{summary['nic']} · {summary['link']:.0f} Mbps")

    console.print(
        Panel(
            table,
            title="Resumen de la sesion",
            border_style=ACCENT,
            expand=False,
        )
    )
