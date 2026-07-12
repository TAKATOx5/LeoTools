import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from leotools.commands import code, domicilios, img2pdf, mei, update

console = Console()

app = typer.Typer(
    help="LeoTools - Herramientas para automatizacion",
    no_args_is_help=True,
)

GUIDE = f"""
[bold cyan]LeoTools[/bold cyan] - Conjunto de utilidades de linea de comandos

[bold]Que es?[/bold]
Una coleccion de comandos utiles para convertir imagenes a PDF, abrir tus
proyectos en Opera y mantener la propia herramienta actualizada.

[bold]Como ejecutarla[/bold]
  Instalada (disponible en cualquier carpeta):
    [green]lt <comando>[/green]            Ej: lt img2pdf
  Sin instalar (desde la carpeta del proyecto):
    [green]python -m leotools <comando>[/green]

  Ayuda de un comando:
    [green]lt <comando> ??[/green]         Ej: lt domicilios ??
    [green]lt <comando> --help[/green]

[bold]Comandos disponibles[/bold]
"""


def show_guide():
    table = Table(
        show_header=True,
        header_style="bold bright_blue",
        box=None,
    )
    table.add_column("Comando", style="green")
    table.add_column("Para que sirve")
    table.add_column("Ejemplo", style="dim")
    table.add_row(
        "code",
        "Abre VS Code con proyectos (ligero / scopio: local + SSH)",
        "lt code ligero",
    )
    table.add_row(
        "img2pdf",
        "Convierte imagenes de la carpeta actual a un PDF",
        "lt img2pdf -o clase.pdf",
    )
    table.add_row(
        "domicilios",
        "Seguimiento a la plataforma Domicilios Fiscales",
        "lt domicilios -a",
    )
    table.add_row(
        "mei",
        "Seguimiento al desarrollo de Novedades MeiMei",
        "lt mei -d",
    )
    table.add_row(
        "update",
        "Baja/sube cambios de LeoTools con Git/GitHub",
        "lt update -p -m \"cambios\"",
    )

    console.print(Panel(GUIDE, title="Guia de LeoTools", border_style="cyan", expand=False))
    console.print(table)
    console.print(
        Panel(
            "[dim]Tip: usa [green]lt ??[/green] para ver esta guia y "
            "[green]lt <comando> ??[/green] para ayuda especifica de cada comando.[/dim]",
            border_style="cyan",
            expand=False,
        )
    )


@app.callback(invoke_without_command=True)
def root(
    guide: bool = typer.Option(False, "??", help="Ver la guia completa de LeoTools"),
):
    if guide:
        show_guide()
        raise typer.Exit()


app.add_typer(
    code.app,
    name="code",
)

app.add_typer(
    img2pdf.app,
    name="img2pdf",
)

app.add_typer(
    domicilios.app,
    name="domicilios",
)

app.add_typer(
    mei.app,
    name="mei",
)

app.add_typer(
    update.app,
    name="update",
)

if __name__ == "__main__":
    app()
