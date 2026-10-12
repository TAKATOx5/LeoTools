import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

app = typer.Typer(
    help="Automatiza git add + commit + push en el proyecto actual.",
    invoke_without_command=True,
)

console = Console()

COLOR_ACCENT = "bright_blue"

HELP_TEXT = f"""
[bold {COLOR_ACCENT}]lt git[/bold {COLOR_ACCENT}] - Automatiza add + commit + push

[bold]Uso:[/bold]
  [green]lt git push "mensaje"[/green]                Guarda y sube cambios
  [green]lt git push "mensaje" "descripcion"[/green]  Con descripcion (cuerpo)
  [green]lt git push[/green]                          Pregunta el mensaje
  [green]lt git push -m "msg" -d "detalle"[/green]    Con banderas

[bold]Que hace:[/bold]
  1. git add -A
  2. git commit -m "mensaje" [-m "descripcion"]
  3. git push (configura el upstream si hace falta)

[bold]Opciones:[/bold]
  -m, --message   Mensaje del commit
  -d, --desc      Descripcion / cuerpo del commit (opcional)
"""


def run_git(*args: str) -> tuple[int, str, str]:
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def is_repo() -> bool:
    code, _, _ = run_git("rev-parse", "--is-inside-work-tree")
    return code == 0


def current_branch() -> str:
    code, out, _ = run_git("rev-parse", "--abbrev-ref", "HEAD")
    return out if code == 0 and out else "main"


def has_uncommitted_changes() -> bool:
    code, out, _ = run_git("status", "--porcelain")
    return bool(out)


def has_upstream() -> bool:
    code, _, _ = run_git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    return code == 0


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="git", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(Panel(HELP_TEXT, title="git", border_style=COLOR_ACCENT, expand=False))


@app.command(name="push")
def push(
    mensaje: str = typer.Argument(None, help="Mensaje del commit"),
    descripcion: str = typer.Argument(None, help="Descripcion del commit (opcional)"),
    message: str = typer.Option(None, "--message", "-m", help="Mensaje del commit"),
    desc: str = typer.Option(None, "--desc", "-d", help="Descripcion del commit (opcional)"),
):
    if not is_repo():
        console.print(
            Panel(
                f"[red]No estas dentro de un repositorio Git:[/red]\n  {Path.cwd()}",
                title="[red]Error[/red]",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(1)

    msg = mensaje or message
    body = descripcion or desc

    if not msg:
        msg = Prompt.ask("[bold]Mensaje del commit[/bold]")
    if not body:
        body = Prompt.ask("[bold]Descripcion (opcional)[/bold]", default="")

    if not has_uncommitted_changes():
        console.print("[yellow]No hay cambios para guardar.[/yellow]")
    else:
        console.print("[cyan]Guardando cambios (git add + commit)...[/cyan]")
        run_git("add", "-A")
        commit_args = ["commit", "-m", msg]
        if body:
            commit_args += ["-m", body]
        code, out, err = run_git(*commit_args)
        if code != 0:
            console.print(Panel(f"[red]Error al hacer commit:[/red]\n{err or out}", border_style="red", expand=False))
            raise typer.Exit(1)
        console.print(f"[green]Commit creado:[/green] {msg}")

    branch = current_branch()
    console.print(f"[cyan]Subiendo cambios (git push)...[/cyan]")

    if has_upstream():
        code, out, err = run_git("push")
    else:
        console.print(f"[dim]Configurando upstream origin/{branch}...[/dim]")
        code, out, err = run_git("push", "-u", "origin", branch)

    if code != 0:
        console.print(Panel(f"[red]Error al hacer push:[/red]\n{err or out}", border_style="red", expand=False))
        raise typer.Exit(1)

    console.print(Panel("[green]Cambios subidos correctamente[/green]", border_style="green", expand=False))
