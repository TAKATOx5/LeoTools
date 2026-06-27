import typer

from leotools.commands import img2pdf, update

app = typer.Typer(
    help="LeoTools - Herramientas para automatizacion",
    no_args_is_help=True,
)

app.add_typer(
    img2pdf.app,
    name="img2pdf",
)

app.add_typer(
    update.app,
    name="update",
)

if __name__ == "__main__":
    app()
