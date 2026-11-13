import typer
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from leotools.commands import (
    code,
    db,
    domicilios,
    drop,
    git,
    hills,
    img2pdf,
    jsoncmp,
    mei,
    monitor,
    speedtest,
    update,
)

console = Console()

app = typer.Typer(
    help="LeoTools - Herramientas para automatizacion",
    no_args_is_help=True,
)

def show_guide():
    header = Text()
    header.append("LeoTools", style="bold cyan")
    header.append(" · Herramientas de automatizacion en Python\n\n")
    header.append("  lt <comando>        ", style="green")
    header.append("Ejecutar desde cualquier carpeta\n", style="dim")
    header.append("  lt <comando> ??     ", style="green")
    header.append("Ayuda detallada de un comando", style="dim")

    table = Table(
        show_header=True,
        header_style="bold bright_blue",
        box=None,
        pad_edge=False,
        padding=(0, 1),
    )
    table.add_column("Comando", style="green", no_wrap=True)
    table.add_column("Que hace", no_wrap=True)
    table.add_column("Ejemplo", style="dim", no_wrap=True)
    rows = [
        ("img2pdf", "Imagenes de la carpeta a PDF", "lt img2pdf -o clase.pdf"),
        ("speedtest", "Velocidad y bufferbloat", "lt speedtest --quick"),
        ("monitor", "Panel en vivo + gato", "lt monitor"),
        ("jsoncmp", "Diferencias entre dos JSON", "lt jsoncmp a.json b.json"),
        ("db", "MySQL: import / export", "lt db"),
        ("drop", "Borra datos e importa .sql", "lt drop tables -p x.sql"),
        ("code", "VS Code local + SSH", "lt code ligero"),
        ("hills", "WiFi SL_Hills", "lt hills"),
        ("domicilios", "Panel Domicilios (Opera)", "lt domicilios -a"),
        ("mei", "Panel MeiMei (Opera)", "lt mei -d"),
        ("git", "add + commit + push", 'lt git push "msg"'),
        ("update", "Actualiza LeoTools", "lt update"),
    ]
    for command, description, example in rows:
        table.add_row(command, description, example)

    console.print(
        Panel(
            Group(header, Text(""), table),
            title="LeoTools",
            border_style="cyan",
            expand=False,
            padding=(0, 2),
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
    db.app,
    name="db",
)

app.add_typer(
    drop.app,
    name="drop",
)

app.add_typer(
    img2pdf.app,
    name="img2pdf",
)

app.command(name="jsoncmp")(jsoncmp.run)

app.add_typer(
    speedtest.app,
    name="speedtest",
)

app.add_typer(
    monitor.app,
    name="monitor",
)

app.add_typer(
    domicilios.app,
    name="domicilios",
)

app.add_typer(
    git.app,
    name="git",
)

app.add_typer(
    hills.app,
    name="hills",
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
