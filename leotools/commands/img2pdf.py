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
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.prompt import Prompt, IntPrompt
from rich import box
from rich.text import Text

app = typer.Typer(help="Convierte imagenes de la carpeta actual a un PDF.", invoke_without_command=True)

console = Console()

EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif"}

COLOR_ACCENT = "bright_blue"
COLOR_TABLE_HEADER = f"bold {COLOR_ACCENT}"
COLOR_NUM = f"bold {COLOR_ACCENT}"


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


HELP_TEXT = f"""
[bold {COLOR_ACCENT}]lt img2pdf[/bold {COLOR_ACCENT}] - Convierte tus imagenes en un PDF al instante

[bold]Uso rapido:[/bold]
  [green]lt img2pdf[/green]                     Modo interactivo (te guia paso a paso)
  [green]lt img2pdf -o salida.pdf[/green]       Modo automatico (sin preguntas)

[bold]Opciones:[/bold]
  --output, -o [{COLOR_ACCENT}]ARCHIVO[/{COLOR_ACCENT}]      Nombre del PDF (ej: clase.pdf)
  --sort, -s [{COLOR_ACCENT}]MODO[/{COLOR_ACCENT}]           Orden: [green]name[/green] (A-Z) o [green]date[/green] (mas antiguo primero)
  --quality, -q [{COLOR_ACCENT}]NIVEL[/{COLOR_ACCENT}]       Calidad: [green]original[/green], [green]media[/green] (mitad), [green]baja[/green] (cuarto)
  --enhance, -e [{COLOR_ACCENT}]MODO[/{COLOR_ACCENT}]        Mejora automatica de imagen:
                 [green]doc[/green]        Brillo + contraste + nitidez (ideal documentos)
                 [green]shadows[/green]    Reduce sombras y ecualiza
                 [green]binarize[/green]   Blanco y negro puro (texto escaneado)
                 [green]all[/green]        Aplica todo junto
  --open, -a              Abrir el PDF al terminar

[bold]Ejemplos:[/bold]
  lt img2pdf                                         Modo interactivo
  lt img2pdf -o apuntes.pdf                           Directo
  lt img2pdf -o tarea.pdf -s date -q media            Ordenado por fecha, calidad media
  lt img2pdf -e doc -o documentos.pdf                 Ideal para fotos de documentos
  lt img2pdf -e binarize --open                       Blanco y negro, abre al terminar

[bold]Orden manual (solo interactivo):[/bold]
  Puedes reordenar las paginas escribiendo los numeros en el orden que quieras:
  [green]2,1,4,3,2[/green]      Paginas: 2, 1, 4, 3, 2 (repetir paginas)
  [green]5-8,1,3[/green]        Paginas 5 a 8, luego 1, luego 3
  [green]3,2,1[/green]          Orden inverso (solo las primeras 3)
  Enter               Deja el orden actual
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
    return result


def get_image_dimensions(img_path: Path) -> str:
    try:
        with Image.open(img_path) as img:
            w, h = img.size
            return f"{w}x{h}"
    except Exception:
        return "?"


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


def enhance_description(mode: EnhanceMode) -> str:
    descriptions = {
        EnhanceMode.doc: "Brillo + Contraste + Nitidez (ideal para documentos)",
        EnhanceMode.shadows: "Reduce sombras y ecualiza colores",
        EnhanceMode.binarize: "Convierte a blanco y negro puro",
        EnhanceMode.all: "Todas las mejoras combinadas",
    }
    return descriptions.get(mode, str(mode))


def quality_description(quality: Quality) -> str:
    descriptions = {
        Quality.original: "Tamano original (maxima calidad)",
        Quality.media: "Mitad del tamano (buen equilibrio)",
        Quality.baja: "Cuarto del tamano (PDF mas ligero)",
    }
    return descriptions.get(quality, str(quality))


COUNT_COLORS = ["bold bright_blue", "green", "yellow", "red", "magenta", "bright_magenta"]


def count_color(count: int) -> str:
    return COUNT_COLORS[min(count, len(COUNT_COLORS) - 1)]


def show_table(images: list[Path], title: str = "Imagenes encontradas", counts: dict[int, int] = None):
    table = Table(
        show_header=True,
        header_style=COLOR_TABLE_HEADER,
        box=box.ROUNDED,
        title=title,
        title_style="bold green",
    )
    table.add_column("#", justify="right", width=4)
    table.add_column("Archivo", style="white")
    table.add_column("Dimensiones", justify="center", style="blue")
    table.add_column("Fecha modificacion", justify="right", style="dim")

    for i, img in enumerate(images, 1):
        c = counts.get(i, 0) if counts else 0
        style = count_color(c)
        dims = get_image_dimensions(img)
        date = datetime.fromtimestamp(img.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        table.add_row(f"[{style}]{str(i)}[/{style}]", img.name, dims, date)

    console.print(table)


def create_pdf(images: list[Path], output: Path, quality: Quality, enhance: EnhanceMode = None):
    pil_images = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task(f"[{COLOR_ACCENT}]Procesando imagenes...", total=len(images))

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
            progress.advance(task)

    if not pil_images:
        console.print("[red]No hay imagenes para convertir[/red]")
        sys.exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"[{COLOR_ACCENT}]Generando PDF...", total=None)
        pil_images[0].save(
            output,
            "PDF",
            save_all=True,
            append_images=pil_images[1:],
            resolution=150,
        )
        progress.update(task, completed=True)


def get_quality_size(quality: Quality, img: Image.Image) -> tuple[int, int]:
    w, h = img.size
    if quality == Quality.original:
        return w, h
    if quality == Quality.media:
        return w // 2, h // 2
    return w // 4, h // 4


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
        console.print(Panel(HELP_TEXT, title="img2pdf", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()

    cwd = Path.cwd()
    images = find_images(cwd)

    if not images:
        console.print(Panel(
            "[red]No se encontraron imagenes en:[/red]\n"
            f"  [yellow]{cwd}[/yellow]\n\n"
            f"Formatos soportados: {', '.join(sorted(EXTENSIONS))}",
            title="[red]Sin imagenes[/red]",
            border_style="red",
        ))
        raise typer.Exit(1)

    if sort:
        images = sort_images(images, sort)

    summary = Panel(
        f"[green]Encontradas [bold]{len(images)}[/bold] imagenes en[/green]\n"
        f"[dim]{cwd}[/dim]",
        border_style="green",
    )
    console.print(summary)

    show_table(images)

    if output:
        pdf_name = output
        order = list(range(1, len(images) + 1))
    else:
        console.print("\n[bold]Orden de paginas[/bold]")
        console.print("[dim]Enter = mismo orden | Ej: [green]5-8,1,3,2,2[/green] para reordenar (repite si quieres)[/dim]")
        raw_order = Prompt.ask("> ").strip()
        if raw_order:
            try:
                order = parse_order(raw_order, len(images))
            except (ValueError, IndexError):
                console.print("[yellow]Orden invalido. Usando el orden actual.[/yellow]")
                order = list(range(1, len(images) + 1))
        else:
            order = list(range(1, len(images) + 1))

        count = {}
        for idx in order:
            count[idx] = count.get(idx, 0) + 1
        show_table(images, title="Seleccion (color por repeticion)", counts=count)

        ordered_preview = [images[i - 1] for i in order]
        if order != list(range(1, len(images) + 1)):
            show_table(ordered_preview, title="Vista previa", counts=count)

        default_name = "output.pdf"
        name_input = Prompt.ask(
            "\n[bold]Nombre del PDF[/bold]",
            default=default_name,
        )
        pdf_name = name_input if name_input else default_name

    if not pdf_name.endswith(".pdf"):
        pdf_name += ".pdf"

    if output and not quality:
        quality = Quality.original
    elif not quality:
        quality_options = {
            "1": ("Original", Quality.original),
            "2": ("Media", Quality.media),
            "3": ("Baja", Quality.baja),
        }
        console.print("\n[bold]Calidad de imagen[/bold]")
        console.print("[dim]A menor calidad, menor peso del PDF[/dim]")
        for key, (label, _) in quality_options.items():
            console.print(f"  [{key}] {label}")
        quality_input = Prompt.ask("> ", choices=list(quality_options.keys()), default="2")
        quality = quality_options[quality_input][1]

    ordered = [images[i - 1] for i in order]
    output_path = cwd / pdf_name

    quality_desc = quality_description(quality)
    enhance_text = ""
    if enhance:
        enhance_text = f"\n  Mejora: [{COLOR_ACCENT}]{enhance_description(enhance)}[/{COLOR_ACCENT}]"

    console.print(Panel(
        f"  Paginas: [bold]{len(ordered)}[/bold] imagenes\n"
        f"  Calidad: [yellow]{quality.value}[/yellow] ({quality_desc})\n"
        f"  Destino: [green]{output_path.name}[/green]"
        f"{enhance_text}",
        title="[bold]Resumen final[/bold]",
        border_style=COLOR_ACCENT,
    ))

    create_pdf(ordered, output_path, quality, enhance)

    console.print(Panel(
        f"  [green]PDF creado exitosamente:[/green] [bold]{output_path.name}[/bold]\n"
        f"  Ubicacion: [dim]{output_path.parent}[/dim]",
        title="[bold green]Listo[/bold green]",
        border_style="green",
    ))

    if open_pdf:
        console.print("[dim]Abriendo PDF...[/dim]")
        open_file(output_path)
