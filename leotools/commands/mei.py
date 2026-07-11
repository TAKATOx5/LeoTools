from leotools.utils.browser import find_opera, open_in_opera, open_summary

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

app = typer.Typer(help="Abre mei en Opera.", invoke_without_command=True)

console = Console()

COLOR_ACCENT = "bright_blue"

DEV_URLS = [
    "https://vercel.com/takatox5s-projects/mei-mei-app",
    "https://supabase.com/dashboard/project/nwzuugxprwtiortpgtuh",
]


def resolve_urls(dev: bool, all_: bool) -> list[str]:
    if all_ or dev:
        return list(DEV_URLS)
    return list(DEV_URLS)


def show_menu() -> tuple[bool, bool]:
    table = Table(
        show_header=True,
        header_style=f"bold {COLOR_ACCENT}",
        box=None,
    )
    table.add_column("Opcion")
    table.add_column("Abre")
    table.add_row("[green]1[/green]", "Dev (Vercel + Supabase)")
    table.add_row("[green]2[/green]", "Todo (lo mismo por ahora)")
    console.print(table)
    choice = Prompt.ask(
        "\n[bold]Que quieres abrir?[/bold]",
        choices=["1", "2"],
        default="1",
    )
    if choice == "1":
        return True, False
    return False, True


@app.callback(invoke_without_command=True)
def main(
    dev: bool = typer.Option(False, "--dev", "-d", help="Abrir dev"),
    all_: bool = typer.Option(False, "--all", "-a", help="Abrir todo"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(
            f"[bold {COLOR_ACCENT}]lt mei[/bold {COLOR_ACCENT}] - Abre mei en Opera\n\n"
            "[bold]Uso:[/bold]\n"
            "  [green]lt mei[/green]            Te pregunta que abrir\n"
            "  [green]lt mei -d[/green]         Solo dev\n"
            "  [green]lt mei -a[/green]         Todo\n",
            title="mei",
            border_style=COLOR_ACCENT,
            expand=False,
        ))
        raise typer.Exit()

    if not (dev or all_):
        dev, all_ = show_menu()

    urls = resolve_urls(dev, all_)
    opera = find_opera()
    open_in_opera(urls, opera)
    open_summary(len(urls))
