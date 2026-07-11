import os
import shutil
import subprocess
import sys
from pathlib import Path

from rich.panel import Panel
from rich.console import Console

console = Console()


def find_opera() -> str | None:
    exe = shutil.which("opera")
    if exe:
        return exe
    candidates = [
        Path.home() / "AppData" / "Local" / "Programs" / "Opera" / "launcher.exe",
        Path("C:/Program Files/Opera/launcher.exe"),
        Path("C:/Program Files (x86)/Opera/launcher.exe"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def open_in_opera(urls: list[str], opera: str | None):
    if not urls:
        console.print("[yellow]No hay URLs para abrir.[/yellow]")
        return
    if not opera:
        console.print(
            Panel(
                "[red]No se encontro Opera instalado.[/red]\n"
                "Se abrira con el navegador predeterminado.",
                title="[red]Opera no encontrado[/red]",
                border_style="red",
            )
        )
        for url in urls:
            if sys.platform == "win32":
                os.startfile(url)
            elif sys.platform == "darwin":
                subprocess.run(["open", url])
            else:
                subprocess.run(["xdg-open", url])
        return
    try:
        subprocess.run([opera, *urls], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error al abrir Opera:[/red] {e}")


def open_summary(count: int):
    console.print(
        Panel(
            f"[green]Abriendo [bold]{count}[/bold] URLs en Opera[/green]",
            border_style="green",
        )
    )
