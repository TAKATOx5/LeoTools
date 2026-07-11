from leotools.utils.browser import find_opera, open_in_opera, open_summary

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

app = typer.Typer(help="Abre los domicilios en Opera.", invoke_without_command=True)

console = Console()

COLOR_ACCENT = "bright_blue"

PAGINA_PRINCIPAL = "https://tudomicilio.mx"

MKT_URLS = [
    "https://analytics.google.com/analytics/web/?authuser=5#/a398037509p541715651/reports/intelligenthome?params=_u..nav%3Dmaui",
    "https://search.google.com/u/5/search-console?resource_id=sc-domain%3Atudomicilio.mx",
    "https://adsense.google.com/adsense/u/5/pub-7659942477210447/onboarding",
]

DEV_URLS = [
    "https://vercel.com/takatox5s-projects/domicilios-app",
    "https://supabase.com/dashboard/project/qovbadeircihpwbaiqcd",
]


def resolve_urls(mkt: bool, dev: bool, all_: bool) -> list[str]:
    if all_:
        return [PAGINA_PRINCIPAL, *MKT_URLS, *DEV_URLS]
    urls: list[str] = []
    if mkt:
        urls.extend([PAGINA_PRINCIPAL, *MKT_URLS])
    if dev:
        urls.extend([PAGINA_PRINCIPAL, *DEV_URLS])
    if not urls:
        urls = [PAGINA_PRINCIPAL]
    return urls


def show_menu() -> tuple[bool, bool, bool]:
    table = Table(
        show_header=True,
        header_style=f"bold {COLOR_ACCENT}",
        box=None,
    )
    table.add_column("Opcion")
    table.add_column("Abre")
    table.add_row("[green]1[/green]", "Marketing (pagina principal + marketing)")
    table.add_row("[green]2[/green]", "Dev (pagina principal + dev)")
    table.add_row("[green]3[/green]", "Todo (pagina principal + marketing + dev)")
    console.print(table)
    choice = Prompt.ask(
        "\n[bold]Que quieres abrir?[/bold]",
        choices=["1", "2", "3"],
        default="3",
    )
    if choice == "1":
        return True, False, False
    if choice == "2":
        return False, True, False
    return False, False, True


@app.callback(invoke_without_command=True)
def main(
    mkt: bool = typer.Option(False, "--mkt", "-m", help="Abrir marketing"),
    dev: bool = typer.Option(False, "--dev", "-d", help="Abrir dev"),
    all_: bool = typer.Option(False, "--all", "-a", help="Abrir todo"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(
            f"[bold {COLOR_ACCENT}]lt domicilios[/bold {COLOR_ACCENT}] - Abre los domicilios en Opera\n\n"
            "[bold]Uso:[/bold]\n"
            "  [green]lt domicilios[/green]            Te pregunta que abrir\n"
            "  [green]lt domicilios -m[/green]         Solo marketing\n"
            "  [green]lt domicilios -d[/green]         Solo dev\n"
            "  [green]lt domicilios -a[/green]         Todo\n"
            "  [green]lt domicilios -m -d[/green]      Marketing + dev\n",
            title="domicilios",
            border_style=COLOR_ACCENT,
            expand=False,
        ))
        raise typer.Exit()

    if not (mkt or dev or all_):
        mkt, dev, all_ = show_menu()

    urls = resolve_urls(mkt, dev, all_)
    opera = find_opera()
    open_in_opera(urls, opera)
    open_summary(len(urls))
