import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

COLOR_ACCENT = "bright_blue"

DEFAULT_A = r"C:\Users\erikl\Downloads\1791068229_HCOJSON25SEP_1.json"
DEFAULT_B = r"C:\Users\erikl\Downloads\1790170331_HCOCjson3SEP.json"

HELP_TEXT = f"""
[bold {COLOR_ACCENT}]lt jsoncmp[/bold {COLOR_ACCENT}] - Compara dos archivos JSON

[bold]Uso:[/bold]
  [green]lt jsoncmp A.json B.json[/green]        Compara los dos archivos
  [green]lt jsoncmp[/green]                       Usa los archivos por defecto
  [green]lt jsoncmp A.json B.json -o diff.json[/green]  Exporta las diferencias

[bold]Opciones:[/bold]
  -o, --output    Guarda el reporte de diferencias en un JSON
  -l, --limit     Maximo de diferencias a mostrar en pantalla (0 = todas)

[bold]Archivos por defecto:[/bold]
  [dim]A: {DEFAULT_A}[/dim]
  [dim]B: {DEFAULT_B}[/dim]
"""


def load_json(path: Path) -> Any:
    if not path.exists():
        console.print(
            Panel(
                f"[red]Archivo no encontrado:[/red]\n  {path}",
                title="[red]Error[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        console.print(
            Panel(
                f"[red]JSON invalido:[/red]\n  {path}\n{exc}",
                title="[red]Error[/red]",
                border_style="red",
            )
        )
        raise typer.Exit(1)


def value_diff(a: Any, b: Any) -> dict | None:
    if a == b:
        return None
    if isinstance(a, dict) and isinstance(b, dict):
        changes = {}
        for key in sorted(set(a) | set(b)):
            if key not in a:
                changes[key] = {"estado": "solo en B", "nuevo": b[key]}
            elif key not in b:
                changes[key] = {"estado": "solo en A", "anterior": a[key]}
            else:
                sub = value_diff(a[key], b[key])
                if sub is not None:
                    changes[key] = sub
        return changes or None
    if isinstance(a, list) and isinstance(b, list):
        changes = {}
        for i in range(max(len(a), len(b))):
            if i >= len(a):
                changes[f"[{i}]"] = {"estado": "solo en B", "nuevo": b[i]}
            elif i >= len(b):
                changes[f"[{i}]"] = {"estado": "solo en A", "anterior": a[i]}
            else:
                sub = value_diff(a[i], b[i])
                if sub is not None:
                    changes[f"[{i}]"] = sub
        return changes or None
    return {"estado": "cambiado", "anterior": a, "nuevo": b}


def leaf_changes(node: dict, prefix: str = "") -> list[tuple[str, dict]]:
    result = []
    if not isinstance(node, dict):
        return result
    if "estado" in node:
        return [(prefix or "valor", node)]
    for key, child in node.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        result.extend(leaf_changes(child, path))
    return result


def compare(data_a: Any, data_b: Any) -> dict:
    if not isinstance(data_a, dict) or not isinstance(data_b, dict):
        diff = value_diff(data_a, data_b)
        return {"tipo": "raiz", "diferencias": diff} if diff else {"tipo": "raiz", "diferencias": None}

    keys_a, keys_b = set(data_a), set(data_b)
    solo_a = sorted(keys_a - keys_b)
    solo_b = sorted(keys_b - keys_a)
    comunes = sorted(keys_a & keys_b)

    cambios = {}
    for key in comunes:
        sub = value_diff(data_a[key], data_b[key])
        if sub is not None:
            cambios[key] = sub

    return {
        "solo_en_a": solo_a,
        "solo_en_b": solo_b,
        "cambiados": cambios,
    }


def run(
    archivo_a: Path = typer.Argument(None, help="Primer archivo JSON (A)"),
    archivo_b: Path = typer.Argument(None, help="Segundo archivo JSON (B)"),
    output: Path = typer.Option(None, "--output", "-o", help="Guardar diferencias en un JSON"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximo de diferencias a mostrar (0 = todas)"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        console.print(Panel(HELP_TEXT, title="jsoncmp", border_style=COLOR_ACCENT, expand=False))
        raise typer.Exit()

    path_a = archivo_a or Path(DEFAULT_A)
    path_b = archivo_b or Path(DEFAULT_B)

    console.print(f"[cyan]Comparando:[/cyan]\n  A: {path_a}\n  B: {path_b}\n")

    data_a = load_json(path_a)
    data_b = load_json(path_b)

    resultado = compare(data_a, data_b)

    if "tipo" in resultado:
        if resultado["diferencias"] is None:
            console.print(Panel("[green]Los archivos son identicos.[/green]", border_style="green"))
        else:
            console.print(Panel("[yellow]La raiz de los archivos es diferente.[/yellow]", border_style="yellow"))
        return

    solo_a = resultado["solo_en_a"]
    solo_b = resultado["solo_en_b"]
    cambiados = resultado["cambiados"]

    table = Table(show_header=True, header_style="bold bright_blue", box=None)
    table.add_column("Resultado", style="green")
    table.add_column("Cantidad", justify="right")
    table.add_row("Solo en A", f"[yellow]{len(solo_a)}[/yellow]")
    table.add_row("Solo en B", f"[yellow]{len(solo_b)}[/yellow]")
    table.add_row("Valor distinto", f"[red]{len(cambiados)}[/red]")
    table.add_row("Sin cambios", f"[green]{len(set(data_a) - set(solo_a) - set(cambiados))}[/green]")

    console.print(Panel(table, title="Resumen", border_style=COLOR_ACCENT, expand=False))

    if solo_a or solo_b:
        detalle = Table(show_header=True, header_style="bold bright_blue", box=None)
        detalle.add_column("Tipo", style="magenta")
        detalle.add_column("Clave / ID")
        detalle.add_column("Contenido", style="dim")
        max_rows = limit if limit > 0 else len(solo_a) + len(solo_b)
        mostrados = 0
        for key in solo_a:
            detalle.add_row("Solo en A", str(key), json.dumps(data_a[key], ensure_ascii=False))
            mostrados += 1
            if mostrados >= max_rows:
                break
        for key in solo_b:
            if mostrados >= max_rows:
                break
            detalle.add_row("Solo en B", str(key), json.dumps(data_b[key], ensure_ascii=False))
            mostrados += 1
        console.print(Panel(detalle, title="Claves faltantes", border_style="magenta", expand=False))
        if max_rows < len(solo_a) + len(solo_b):
            console.print(f"[dim]... y {len(solo_a) + len(solo_b) - max_rows} mas (usa -o para exportar todo)[/dim]")

    if cambiados:
        hojas = []
        for key, cambio in cambiados.items():
            for path, leaf in leaf_changes(cambio, str(key)):
                hojas.append((path, leaf))
        detalle = Table(show_header=True, header_style="bold bright_blue", box=None)
        detalle.add_column("Clave / ID")
        detalle.add_column("Antes (A)", style="yellow")
        detalle.add_column("Despues (B)", style="green")
        max_rows = limit if limit > 0 else len(hojas)
        for i, (path, leaf) in enumerate(hojas):
            if i >= max_rows:
                break
            estado = leaf.get("estado")
            antes = leaf.get("anterior", "[sin valor]" if estado == "solo en B" else None)
            despues = leaf.get("nuevo", "[sin valor]" if estado == "solo en A" else None)
            detalle.add_row(
                path,
                json.dumps(antes, ensure_ascii=False),
                json.dumps(despues, ensure_ascii=False),
            )
        console.print(Panel(detalle, title="Valores distintos", border_style="yellow", expand=False))
        if max_rows < len(hojas):
            console.print(f"[dim]... y {len(hojas) - max_rows} mas (usa -o para exportar todo)[/dim]")

    if output:
        reporte = {
            "archivo_a": str(path_a),
            "archivo_b": str(path_b),
            "solo_en_a": {k: data_a[k] for k in solo_a},
            "solo_en_b": {k: data_b[k] for k in solo_b},
            "valores_distintos": cambiados,
        }
        with output.open("w", encoding="utf-8") as fh:
            json.dump(reporte, fh, ensure_ascii=False, indent=2)
        console.print(f"[green]Reporte guardado en:[/green] {output}")

    total = len(solo_a) + len(solo_b) + len(cambiados)
    if total == 0:
        console.print(Panel("[green]Los archivos son identicos.[/green]", border_style="green"))
    else:
        console.print(
            Panel(
                f"[yellow]Se encontraron {total} diferencia(s).[/yellow]",
                border_style="yellow",
            )
        )
