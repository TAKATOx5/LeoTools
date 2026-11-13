from enum import Enum

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from leotools.utils.speedtest import metrics
from leotools.utils.speedtest.monitor import MonitorApp, format_duration

app = typer.Typer(
    help="Dashboard en vivo con medicion continua y gato animado. "
    "Teclas: Esc salir, p pausa, m cambia modo, 1/2/3 eligen modo, [ ] descanso.",
    invoke_without_command=True,
)

console = Console()
ACCENT = "bright_blue"


class MonitorMode(str, Enum):
    cycle = "cycle"
    continuous = "continuous"
    sample = "sample"


HELP_TEXT = f"""
[bold {ACCENT}]lt monitor[/bold {ACCENT}] - Dashboard en vivo con gato animado

[bold]Que hace:[/bold]
  Mide la descarga en bucle mientras el panel esta abierto y anima un gato
  segun la velocidad. Al salir muestra el resumen de la sesion.

[bold]Uso:[/bold]
  [green]lt monitor[/green]                    Modo ciclico (4s mide / 6s descansa)
  [green]lt monitor --mode continuous[/green]  Sin descanso (usa mas ancho de banda)
  [green]lt monitor --mode sample[/green]      Mide 3s cada 27s
  [green]lt monitor --streams 8[/green]        Conexiones en paralelo

[bold]Teclas:[/bold]
  [green]Esc / Ctrl+C[/green]   Salir y ver resumen
  [green]p[/green]              Pausar / reanudar
  [green]m[/green]              Cambiar de modo (ciclico -> continuo -> muestreo)
  [green]1 / 2 / 3[/green]      Elegir modo directamente
  [green][ / ][/green]          Menos / mas descanso

[bold]Opciones:[/bold]
  --mode, -m       cycle | continuous | sample
  --streams, -s    Conexiones en paralelo (default: 6)
  --burst, -b      Segundos midiendo por ciclo
  --rest, -r       Segundos de descanso por ciclo
"""


@app.callback(invoke_without_command=True)
def main(
    mode: MonitorMode = typer.Option(
        MonitorMode.cycle, "--mode", "-m", help="Modo inicial"
    ),
    streams: int = typer.Option(4, "--streams", "-s", help="Conexiones en paralelo"),
    burst: int = typer.Option(None, "--burst", "-b", help="Segundos midiendo"),
    rest: int = typer.Option(None, "--rest", "-r", help="Segundos de descanso"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="monitor", border_style=ACCENT, expand=False))
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

    app_instance = MonitorApp(
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
    table.add_row("Medido", format_duration(summary["measured_seconds"]))
    table.add_row("Pico", metrics.format_mbps(summary["peak"]))
    table.add_row("Promedio", metrics.format_mbps(summary["avg"]))
    table.add_row("Datos", metrics.human_bytes(summary["bytes"]))
    table.add_row("Ciclos", str(summary["cycles"]))
    if summary["errors"]:
        table.add_row("Errores", str(summary["errors"]))

    console.print(
        Panel(
            table,
            title="Sesion de monitor",
            border_style=ACCENT,
            expand=False,
        )
    )
