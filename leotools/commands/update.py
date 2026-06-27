import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(help="Actualiza LeoTools desde GitHub.", invoke_without_command=True)

console = Console()

REPO_URL = "https://github.com/erikldev/leotools.git"
PROJECT_ROOT = Path(__file__).parent.parent.parent

HELP_TEXT = """
[bold cyan]lt update[/bold cyan] - Actualiza LeoTools desde GitHub

[bold]Uso:[/bold]
  lt update             Descarga ultima version
  lt update --check     Solo verificar si hay actualizaciones

[bold]Ejemplos:[/bold]
  lt update
  lt update --check
"""


def run_git(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git"] + list(args),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip()


def check_git_installed() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True)
        return True
    except FileNotFoundError:
        return False


def check_remote_exists() -> bool:
    code, output = run_git("remote")
    return "origin" in output


@app.callback(invoke_without_command=True)
def main(
    check: bool = typer.Option(False, "--check", "-c", help="Solo verificar actualizaciones"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="update", border_style="cyan"))
        raise typer.Exit()

    if not check_git_installed():
        console.print("[red]Git no esta instalado[/red]")
        raise typer.Exit(1)

    if not check_remote_exists():
        console.print("[yellow]Configurando repositorio remoto...[/yellow]")
        code, _ = run_git("remote", "add", "origin", REPO_URL)
        if code != 0:
            console.print("[red]Error al configurar remoto[/red]")
            raise typer.Exit(1)

    console.print("[cyan]Verificando actualizaciones...[/cyan]")
    code, _ = run_git("fetch", "origin")
    if code != 0:
        console.print("[red]Error al conectar con GitHub[/red]")
        raise typer.Exit(1)

    code, local = run_git("rev-parse", "HEAD")
    code2, remote = run_git("rev-parse", "origin/main")

    if local == remote:
        console.print("[green]LeoTools esta actualizado[/green]")
        raise typer.Exit()

    if check:
        console.print("[yellow]Hay una nueva version disponible[/yellow]")
        console.print(f"  Local:  {local[:8]}")
        console.print(f"  Remote: {remote[:8]}")
        raise typer.Exit()

    console.print("[cyan]Descargando actualizacion...[/cyan]")
    code, output = run_git("pull", "origin", "main")
    if code != 0:
        console.print(f"[red]Error: {output}[/red]")
        raise typer.Exit(1)

    console.print("[green]LeoTools actualizado correctamente[/green]")
