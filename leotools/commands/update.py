import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

app = typer.Typer(help="Actualiza o sube cambios de LeoTools con Git/GitHub.", invoke_without_command=True)

console = Console()

REPO_URL = "https://github.com/erikldev/leotools.git"
PROJECT_ROOT = Path(__file__).parent.parent.parent

DEFAULT_BRANCH = "main"

HELP_TEXT = f"""
[bold cyan]lt update[/bold cyan] - Actualiza o sube cambios de LeoTools

[bold]Uso:[/bold]
  lt update                 Verifica y pregunta que hacer (bajar/subir)
  lt update --check         Solo verificar si hay cambios
  lt update --push         Sube cambios locales (commit + push) sin preguntar
  lt update -p -m "msg"     Sube con un mensaje de commit especifico

[bold]Flujo interactivo:[/bold]
  1. Si hay actualizaciones en GitHub, pregunta si hacer pull
  2. Si hay cambios locales sin subir, pregunta si hacer commit + push

[bold]Ejemplos:[/bold]
  lt update
  lt update --check
  lt update --push -m "Agrega comando mei"
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


def ensure_remote():
    if not check_remote_exists():
        console.print("[yellow]Configurando repositorio remoto...[/yellow]")
        code, _ = run_git("remote", "add", "origin", REPO_URL)
        if code != 0:
            console.print("[red]Error al configurar remoto[/red]")
            raise typer.Exit(1)


def has_uncommitted_changes() -> bool:
    code, output = run_git("status", "--porcelain")
    return bool(output.strip())


def ahead_count() -> int:
    code, out = run_git("rev-list", "--count", f"origin/{DEFAULT_BRANCH}..HEAD")
    try:
        return int(out)
    except ValueError:
        return 0


def behind_count() -> int:
    code, out = run_git("rev-list", "--count", f"HEAD..origin/{DEFAULT_BRANCH}")
    try:
        return int(out)
    except ValueError:
        return 0


def commit_changes(message: str | None):
    console.print("[cyan]Guardando cambios (git add + commit)...[/cyan]")
    run_git("add", "-A")
    msg = message or Prompt.ask("Mensaje del commit", default="Actualizacion de LeoTools")
    code, output = run_git("commit", "-m", msg)
    if code != 0:
        console.print(f"[red]Error al hacer commit:[/red] {output}")
        raise typer.Exit(1)
    console.print("[green]Cambios guardados localmente[/green]")


def pull_updates():
    console.print("[cyan]Bajando actualizaciones (git pull)...[/cyan]")
    code, output = run_git("pull", "origin", DEFAULT_BRANCH)
    if code != 0:
        console.print(f"[red]Error al hacer pull:[/red] {output}")
        raise typer.Exit(1)
    console.print("[green]LeoTools actualizado desde GitHub[/green]")


def push_updates():
    console.print("[cyan]Subiendo cambios (git push)...[/cyan]")
    code, output = run_git("push", "origin", DEFAULT_BRANCH)
    if code != 0:
        console.print(f"[red]Error al hacer push:[/red] {output}")
        raise typer.Exit(1)
    console.print("[green]Cambios subidos a GitHub[/green]")


def report_status():
    dirty = has_uncommitted_changes()
    ahead = ahead_count()
    behind = behind_count()
    if dirty:
        console.print("[yellow]Tienes cambios locales sin guardar[/yellow]")
    if ahead:
        console.print(f"[yellow]Tienes {ahead} commit(s) local(es) sin subir[/yellow]")
    if behind:
        console.print(f"[yellow]Hay {behind} actualizacion(es) en GitHub sin bajar[/yellow]")
    if not (dirty or ahead or behind):
        console.print("[green]LeoTools esta actualizado y sin cambios pendientes[/green]")


@app.callback(invoke_without_command=True)
def main(
    check: bool = typer.Option(False, "--check", "-c", help="Solo verificar cambios"),
    push: bool = typer.Option(False, "--push", "-p", help="Subir cambios (commit + push) sin preguntar"),
    message: str = typer.Option(None, "--message", "-m", help="Mensaje de commit al subir"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="update", border_style="cyan"))
        raise typer.Exit()

    if not check_git_installed():
        console.print("[red]Git no esta instalado[/red]")
        raise typer.Exit(1)

    ensure_remote()

    console.print("[cyan]Verificando repositorio...[/cyan]")
    run_git("fetch", "origin")
    if run_git("rev-parse", f"origin/{DEFAULT_BRANCH}")[0] != 0:
        console.print("[yellow]La rama remota aun no existe. Se subira como nueva.[/yellow]")

    if check:
        report_status()
        raise typer.Exit()

    if push:
        if behind_count() > 0:
            pull_updates()
        if has_uncommitted_changes():
            commit_changes(message)
        if ahead_count() > 0 or has_uncommitted_changes():
            push_updates()
        elif behind_count() == 0:
            console.print("[green]Nada que subir: ya esta actualizado[/green]")
        raise typer.Exit()

    behind = behind_count()
    dirty = has_uncommitted_changes()
    ahead = ahead_count()

    if not (behind or dirty or ahead):
        console.print("[green]LeoTools esta actualizado y sin cambios pendientes[/green]")
        raise typer.Exit()

    if behind > 0:
        if Confirm.ask(f"[bold]Hay {behind} actualizacion(es) en GitHub. ¿Bajar (pull)?[/bold]", default=True):
            pull_updates()

    if has_uncommitted_changes():
        if Confirm.ask("[bold]Hay cambios locales sin subir. ¿Hacer commit y push?[/bold]", default=True):
            commit_changes(message)

    if ahead_count() > 0 or has_uncommitted_changes():
        if Confirm.ask("[bold]¿Subir cambios a GitHub (push)?[/bold]", default=True):
            push_updates()

    console.print(Panel("[green]Listo[/green]", border_style="green"))
