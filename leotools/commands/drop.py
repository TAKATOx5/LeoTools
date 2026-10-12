from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from leotools.commands.db import (
    COLOR_ACCENT,
    DEFAULT_DB,
    complete_databases,
    complete_path,
    perform_import,
    print_summary,
)

app = typer.Typer(
    help="Borra los datos de las tablas e importa un dump en un paso.",
    invoke_without_command=True,
)

console = Console()

HELP_TEXT = f"""
[bold {COLOR_ACCENT}]lt drop tables[/bold {COLOR_ACCENT}] - Borra DATOS e importa un .sql

[bold]Uso:[/bold]
  [green]lt drop tables -d baseproject --path=C:\\ruta\\dump.sql[/green]
  [green]lt drop tables --path="C:\\ruta con espacios\\dump.sql" -y[/green]

[bold]Que hace:[/bold]
  1. Crea un respaldo de la base (rollback automatico si algo falla)
  2. Borra los DATOS de las tablas (no borra la estructura)
  3. Importa el .sql con las llaves foraneas desactivadas

[bold]Opciones:[/bold]
  -p, --path      Ruta del archivo .sql a importar (obligatorio)
  -d, --db        Nombre de la base de datos (default: {DEFAULT_DB})
  -y, --yes       No pedir confirmacion

[dim]Tip: pega la ruta despues de --path= (entre comillas si tiene espacios).[/dim]
"""


@app.command("tables")
def drop_tables(
    path: Path = typer.Option(..., "--path", "-p", help="Ruta del archivo .sql a importar", autocompletion=complete_path),
    db: str = typer.Option(DEFAULT_DB, "--db", "-d", help="Nombre de la base de datos", autocompletion=complete_databases),
    yes: bool = typer.Option(False, "--yes", "-y", help="No pedir confirmacion"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="drop tables", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()

    if not path.exists():
        console.print(
            Panel(
                f"[red]Archivo no encontrado:[/red]\n  {path}",
                title="[red]Error[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    if not yes:
        if not Confirm.ask(
            f"[bold red]Borrar los DATOS de las tablas de [green]{db}[/green] "
            f"e importar [green]{path.name}[/green]?[/bold red]",
            default=False,
        ):
            console.print("[yellow]Cancelado[/yellow]")
            raise typer.Exit()

    summary = perform_import(db, path, do_truncate=True)
    print_summary(summary)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help or ctx.invoked_subcommand is None:
        console.print(Panel(HELP_TEXT, title="drop tables", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()
