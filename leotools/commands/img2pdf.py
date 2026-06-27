import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from enum import Enum

import typer
from PIL import Image, ImageEnhance, ImageOps
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(help="Convierte imagenes a PDF.", invoke_without_command=True)

console = Console()

EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif"}


class SortMode(str, Enum):
    name = "name"
    date = "date"


class Quality(str, Enum):
    original = "original"
    media = "media"
    baja = "baja"


class EnhanceMode(str, Enum):
    doc = "doc"
    shadows = "shadows"
    binarize = "binarize"
    all = "all"


HELP_TEXT = """
[bold cyan]lt img2pdf[/bold cyan] - Convierte imagenes a PDF

[bold]Uso:[/bold]
  lt img2pdf                     Modo interactivo
  lt img2pdf --output out.pdf    Sin preguntas
  lt img2pdf --sort date         Ordenar por fecha
  lt img2pdf --open              Abrir PDF al terminar
  lt img2pdf --enhance shadows   Mejorar imagen con sombras

[bold]Opciones:[/bold]
  --output, -o      Nombre del PDF (default: output.pdf)
  --sort, -s        Orden: [green]name[/green] (alfabetico) o [green]date[/green] (fecha)
  --quality, -q     Calidad: [green]original[/green], [green]media[/green], [green]baja[/green]
  --enhance, -e     Mejorar imagen:
                      [green]doc[/green]      Brillo + contraste automatico
                      [green]shadows[/green]  Reduce sombras oscuras
                      [green]binarize[/green] Blanco y negro puro
                      [green]all[/green]      Todas las mejoras
  --open, -a        Abrir el PDF despues de crearlo

[bold]Ejemplos:[/bold]
  lt img2pdf
  lt img2pdf -o asistencia.pdf -s date -q media
  lt img2pdf -e shadows -o lista.pdf
  lt img2pdf -e all --open

[bold]Orden manual (modo interactivo):[/bold]
  [green]2,1,4,3[/green]          Orden especifico
  [green]5-8,1,3[/green]          Rangos
  [green]3,2,1,5-8[/green]        Mezcla
  Enter               Mismo orden
"""


def find_images(folder: Path) -> list[Path]:
    images = [
        f
        for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in EXTENSIONS
    ]
    return images


def sort_images(images: list[Path], mode: SortMode) -> list[Path]:
    if mode == SortMode.date:
        return sorted(images, key=lambda x: x.stat().st_mtime)
    return sorted(images, key=lambda x: x.name.lower())


def parse_order(raw: str, total: int) -> list[int]:
    result = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            start, end = int(start.strip()), int(end.strip())
            result.extend(range(start, end + 1))
        else:
            result.append(int(part.strip()))
    if not all(1 <= i <= total for i in result):
        raise ValueError("Indices fuera de rango")
    if len(result) != len(set(result)):
        raise ValueError("Indices duplicados")
    return result


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def enhance_image(img: Image.Image, mode: EnhanceMode) -> Image.Image:
    if mode == EnhanceMode.doc:
        img = ImageEnhance.Brightness(img).enhance(1.3)
        img = ImageEnhance.Contrast(img).enhance(1.5)
        img = ImageEnhance.Sharpness(img).enhance(1.2)
    elif mode == EnhanceMode.shadows:
        img = ImageOps.equalize(img)
        img = ImageEnhance.Contrast(img).enhance(1.3)
        img = ImageEnhance.Brightness(img).enhance(1.1)
    elif mode == EnhanceMode.binarize:
        img = img.convert("L")
        img = img.point(lambda x: 0 if x < 128 else 255)
        img = img.convert("RGB")
    elif mode == EnhanceMode.all:
        img = ImageOps.equalize(img)
        img = ImageEnhance.Brightness(img).enhance(1.3)
        img = ImageEnhance.Contrast(img).enhance(1.5)
        img = ImageEnhance.Sharpness(img).enhance(1.2)
    return img


def show_table(images: list[Path]):
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Archivo")
    table.add_column("Tamano", justify="right")
    table.add_column("Fecha", justify="right", style="dim")

    for i, img in enumerate(images, 1):
        size = format_size(img.stat().st_size)
        date = datetime.fromtimestamp(img.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        table.add_row(str(i), img.name, size, date)

    console.print(table)


def get_quality_size(quality: Quality, img: Image.Image) -> tuple[int, int]:
    w, h = img.size
    if quality == Quality.original:
        return w, h
    if quality == Quality.media:
        return w // 2, h // 2
    return w // 4, h // 4


def create_pdf(images: list[Path], output: Path, quality: Quality, enhance: EnhanceMode = None):
    pil_images = []
    for img_path in images:
        img = Image.open(img_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")
        if enhance:
            img = enhance_image(img, enhance)
        size = get_quality_size(quality, img)
        img = img.resize(size, Image.LANCZOS)
        pil_images.append(img)

    if not pil_images:
        console.print("[red]No hay imagenes para convertir[/red]")
        sys.exit(1)

    pil_images[0].save(
        output,
        "PDF",
        save_all=True,
        append_images=pil_images[1:],
        resolution=150,
    )


def open_file(path: Path):
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])


@app.callback(invoke_without_command=True)
def main(
    output: str = typer.Option(None, "--output", "-o", help="Nombre del PDF"),
    sort: SortMode = typer.Option(None, "--sort", "-s", help="Orden: name o date"),
    quality: Quality = typer.Option(None, "--quality", "-q", help="Calidad: original, media, baja"),
    enhance: EnhanceMode = typer.Option(None, "--enhance", "-e", help="Mejorar imagen: doc, shadows, binarize, all"),
    open_pdf: bool = typer.Option(False, "--open", "-a", help="Abrir PDF al terminar"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="img2pdf", border_style="cyan"))
        raise typer.Exit()

    cwd = Path.cwd()
    images = find_images(cwd)

    if not images:
        console.print("[red]No se encontraron imagenes en esta carpeta[/red]")
        raise typer.Exit(1)

    if sort:
        images = sort_images(images, sort)

    console.print(f"\n[green]Encontradas {len(images)} imagenes[/green]\n")
    show_table(images)

    if output:
        pdf_name = output
        order = list(range(1, len(images) + 1))
    else:
        raw_order = input("\nOrden (Enter = mismo orden):\n> ").strip()
        if raw_order:
            try:
                order = parse_order(raw_order, len(images))
            except (ValueError, IndexError):
                console.print("[yellow]Orden invalido, usando mismo orden[/yellow]")
                order = list(range(1, len(images) + 1))
        else:
            order = list(range(1, len(images) + 1))

        default_name = "output.pdf"
        name_input = input(f"\nNombre PDF:\n[Enter = {default_name}]\n> ").strip()
        pdf_name = name_input if name_input else default_name

    if not pdf_name.endswith(".pdf"):
        pdf_name += ".pdf"

    if output and not quality:
        quality = Quality.original
    elif not quality:
        console.print("\n[bold]Calidad[/bold]")
        console.print("  1) Original")
        console.print("  2) Media")
        console.print("  3) Baja")
        quality_input = input("\n> ").strip()
        quality_num = int(quality_input) if quality_input in "123" else 2
        quality = list(Quality)[quality_num - 1]

    ordered = [images[i - 1] for i in order]
    output_path = cwd / pdf_name

    create_pdf(ordered, output_path, quality, enhance)

    console.print(f"\n[green]PDF creado:[/green]")
    console.print(f"  {output_path.name}\n")

    if open_pdf:
        open_file(output_path)
