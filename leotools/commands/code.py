import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(help="Abre VS Code con proyectos.", no_args_is_help=True)

console = Console()

COLOR_ACCENT = "bright_blue"


def find_vscode() -> str | None:
    if sys.platform == "win32":
        candidates = [
            Path.home() / "AppData" / "Local" / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd",
            Path("C:/Program Files/Microsoft VS Code/bin/code.cmd"),
            Path("C:/Program Files (x86)/Microsoft VS Code/bin/code.cmd"),
        ]
        for c in candidates:
            if c.exists():
                return str(c)
    import shutil
    exe = shutil.which("code")
    if exe:
        return exe
    return None


def open_local(vscode: str, folder: str):
    if not Path(folder).exists():
        console.print(f"[red]Carpeta local no encontrada:[/red] {folder}")
        return
    console.print(f"[cyan]Abriendo carpeta local:[/cyan] {folder}")
    subprocess.Popen([vscode, folder])


def open_ssh(vscode: str, host: str, path: str):
    console.print(f"[cyan]Abriendo conexion SSH:[/cyan] {host}:{path}")
    remote = f"ssh-remote+{host}"
    subprocess.Popen([vscode, "--remote", remote, path])


def ensure_vscode() -> str:
    vscode = find_vscode()
    if not vscode:
        console.print(
            Panel(
                "[red]No se encontro Visual Studio Code.[/red]\n"
                "Asegurate de que este instalado y en el PATH del sistema.",
                title="[red]VS Code no encontrado[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)
    return vscode


LIGERO_LOCAL = r"C:\Users\erikl\Dev\catorcePlatform"
LIGERO_SSH_HOST = "134.209.37.142"
LIGERO_SSH_PATH = "/var/www/catorcePlatform"

LIGERO_HELP = f"""
[bold {COLOR_ACCENT}]lt code ligero[/bold {COLOR_ACCENT}] - Abre VS Code con el proyecto ligero

[bold]Uso:[/bold]
  [green]lt code ligero[/green]              Abre ambas instancias (local + SSH)
  [green]lt code ligero -l[/green]           Solo abre la carpeta local
  [green]lt code ligero -s[/green]           Solo abre la conexion SSH

[bold]Carpetas:[/bold]
  Local:   {LIGERO_LOCAL}
  SSH:     {LIGERO_SSH_HOST}:{LIGERO_SSH_PATH}
"""


SCOPIO_LOCAL = r"C:\Users\erikl\Dev\scopioPlatform"
SCOPIO_SSH_HOST = "24.144.80.191"
SCOPIO_SSH_PATH = "/var/www/scopioPlatform"

SCOPIO_HELP = f"""
[bold {COLOR_ACCENT}]lt code scopio[/bold {COLOR_ACCENT}] - Abre VS Code con el proyecto scopio

[bold]Uso:[/bold]
  [green]lt code scopio[/green]              Abre ambas instancias (local + SSH)
  [green]lt code scopio -l[/green]           Solo abre la carpeta local
  [green]lt code scopio -s[/green]           Solo abre la conexion SSH

[bold]Carpetas:[/bold]
  Local:   {SCOPIO_LOCAL}
  SSH:     {SCOPIO_SSH_HOST}:{SCOPIO_SSH_PATH}
"""


ligero_app = typer.Typer(help="Proyecto ligero (catorcePlatform).", invoke_without_command=True)


@ligero_app.callback(invoke_without_command=True)
def ligero(
    local: bool = typer.Option(False, "--local", "-l", help="Solo abrir carpeta local"),
    ssh: bool = typer.Option(False, "--ssh", "-s", help="Solo abrir conexion SSH"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(LIGERO_HELP, title="code ligero", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()

    vscode = ensure_vscode()

    if local:
        open_local(vscode, LIGERO_LOCAL)
    elif ssh:
        open_ssh(vscode, LIGERO_SSH_HOST, LIGERO_SSH_PATH)
    else:
        open_local(vscode, LIGERO_LOCAL)
        open_ssh(vscode, LIGERO_SSH_HOST, LIGERO_SSH_PATH)

    console.print(Panel("[green]VS Code abierto correctamente[/green]", border_style="green"))


scopio_app = typer.Typer(help="Proyecto scopio (scopioPlatform).", invoke_without_command=True)


@scopio_app.callback(invoke_without_command=True)
def scopio(
    local: bool = typer.Option(False, "--local", "-l", help="Solo abrir carpeta local"),
    ssh: bool = typer.Option(False, "--ssh", "-s", help="Solo abrir conexion SSH"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(SCOPIO_HELP, title="code scopio", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()

    vscode = ensure_vscode()

    if local:
        open_local(vscode, SCOPIO_LOCAL)
    elif ssh:
        open_ssh(vscode, SCOPIO_SSH_HOST, SCOPIO_SSH_PATH)
    else:
        open_local(vscode, SCOPIO_LOCAL)
        open_ssh(vscode, SCOPIO_SSH_HOST, SCOPIO_SSH_PATH)

    console.print(Panel("[green]VS Code abierto correctamente[/green]", border_style="green"))


app.add_typer(ligero_app, name="ligero")
app.add_typer(scopio_app, name="scopio")
