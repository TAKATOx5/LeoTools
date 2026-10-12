import subprocess
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(help="Conecta a la red WiFi SL_Hills.", invoke_without_command=True)

console = Console()

COLOR_ACCENT = "bright_blue"

SSID = "SL_Hills"
ENV_FILE = Path(__file__).parent.parent.parent / ".env"

HELP_TEXT = f"""
[bold {COLOR_ACCENT}]lt hills[/bold {COLOR_ACCENT}] - Conecta a la red WiFi SL_Hills

[bold]Uso:[/bold]
  [green]lt hills[/green]              Conecta a la red
  [green]lt hills --check[/green]    Solo verifica el estado

[bold]Contrasena:[/bold] se lee del archivo [dim].env[/dim] (gitignored)
"""


def load_password() -> str:
    if not ENV_FILE.exists():
        console.print(
            Panel(
                f"[red]Archivo .env no encontrado en:[/red]\n  {ENV_FILE}\n\n"
                "Crea el archivo con la variable WIFI_HILLS_PASSWORD=tu_password",
                title="[red]Error de configuracion[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("WIFI_HILLS_PASSWORD="):
            return line.split("=", 1)[1].strip()
    console.print(
        Panel(
            "[red]Variable WIFI_HILLS_PASSWORD no encontrada en .env[/red]",
            title="[red]Error de configuracion[/red]",
            border_style="red",
        )
    )
    raise typer.Exit(1)


def check_connection() -> bool:
    result = subprocess.run(
        ["netsh", "wlan", "show", "interfaces"],
        capture_output=True,
        text=True,
    )
    return SSID in result.stdout


def run_netsh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["netsh", "wlan"] + list(args),
        capture_output=True,
        text=True,
    )


@app.callback(invoke_without_command=True)
def main(
    check: bool = typer.Option(False, "--check", "-c", help="Solo verificar estado de la conexion"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="hills", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()

    if check:
        if check_connection():
            console.print(f"[green]Conectado a:[/green] [bold]{SSID}[/bold]")
        else:
            console.print(f"[yellow]No conectado a:[/yellow] [bold]{SSID}[/bold]")
        raise typer.Exit()

    password = load_password()

    console.print(f"[cyan]Conectando a [bold]{SSID}[/bold]...[/cyan]")

    r = run_netsh("set", "profileparameter", f"name={SSID}", f"keyMaterial={password}")

    time.sleep(1)

    r = run_netsh("connect", f"name={SSID}")

    if r.returncode != 0:
        err = r.stderr.strip() or r.stdout.strip()
        console.print(
            Panel(
                f"[yellow]No se pudo conectar automaticamente.[/yellow]\n"
                f"{err}\n\n"
                "[dim]Prueba a olvidar la red en Windows y volver a ejecutar [green]lt hills[/green].[/dim]",
                title="[yellow]Error[/yellow]",
                border_style="yellow",
            )
        )
        raise typer.Exit(1)

    time.sleep(2)

    if check_connection():
        console.print(
            Panel(
                f"[green]Conectado exitosamente a:[/green] [bold]{SSID}[/bold]",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[yellow]Conectando... espera unos segundos y verifica manualmente.[/yellow]",
                border_style="yellow",
            )
        )
