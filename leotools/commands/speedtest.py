import asyncio
import shutil
import socket
from enum import Enum

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from leotools.utils.speedtest import cloudflare, engine, history, metrics, probes, render, system
from leotools.utils.speedtest.models import EngineError, SpeedTestResult

app = typer.Typer(
    help="Mide la velocidad de tu conexion a Internet.",
    invoke_without_command=True,
)

console = Console()
ACCENT = "bright_blue"


class EngineChoice(str, Enum):
    python = "python"
    curl = "curl"


def parse_plan(value: str | None) -> tuple[float, float | None] | None:
    if not value:
        return None
    try:
        if "/" in value:
            down_raw, up_raw = value.split("/", 1)
            return float(down_raw), (float(up_raw) if up_raw else None)
        return float(value), None
    except ValueError as exc:
        raise typer.BadParameter("Usa el formato MEGAS o BAJADA/SUBIDA (ej: 500/50)") from exc


async def run_test(
    engine_name: str,
    duration: float,
    streams: int,
    do_upload: bool,
    family: int | None,
) -> SpeedTestResult:
    result = SpeedTestResult(engine=engine_name)
    dashboard = render.SpeedDashboard(console)
    session = cloudflare.make_session(streams, family)
    probe_session = cloudflare.make_session(1, family)

    dashboard.start()
    dashboard.set_upload_enabled(do_upload)
    try:
        dashboard.set_phase("Contactando Cloudflare...")
        trace = await cloudflare.fetch_trace(session)
        result.colo = trace.get("colo", "")
        result.location = trace.get("loc", "")
        result.ip = trace.get("ip", "")
        label = f"Cloudflare · {result.colo}" if result.colo else "Cloudflare"
        if result.location:
            label += f" ({result.location})"
        dashboard.set_server(label)

        dashboard.set_phase("Midiendo latencia en reposo...")
        result.idle = await probes.measure_latency(session)
        dashboard.set_idle(result.idle)

        result.dns_ms = await probes.dns_lookup_ms("speed.cloudflare.com")
        result.ttfb_ms = await probes.ttfb_ms(session, cloudflare.TRACE_URL)

        dashboard.set_phase("Midiendo descarga...")
        stop = asyncio.Event()
        loaded = asyncio.create_task(
            probes.loaded_latency(probe_session, stop)
        )
        try:
            result.down = await engine.download(
                session, engine_name, duration, streams, dashboard.sample, family
            )
        finally:
            stop.set()
            loaded_down = await loaded
        result.down_bloat = metrics.bufferbloat(result.idle, loaded_down)

        if do_upload:
            dashboard.set_phase("Midiendo subida...")
            stop = asyncio.Event()
            loaded = asyncio.create_task(
                probes.loaded_latency(probe_session, stop)
            )
            try:
                result.up = await engine.upload(
                    session, engine_name, duration, streams, dashboard.sample, family
                )
            finally:
                stop.set()
                loaded_up = await loaded
            result.up_bloat = metrics.bufferbloat(result.idle, loaded_up)

        dashboard.set_phase("Listo")
    finally:
        dashboard.stop()
        console.print()
        await session.close()
        await probe_session.close()

    return result


def build_warnings(result: SpeedTestResult) -> list[str]:
    warnings: list[str] = []
    for transfer in (result.down, result.up):
        if transfer is not None and transfer.errors:
            warnings.append(
                f"{transfer.errors} conexion(es) fallaron durante la prueba; "
                "el resultado puede ser mas bajo de lo real."
            )

    link, vpn = system.detect_network()
    if vpn:
        warnings.append(
            f"Hay una VPN activa ({vpn}); los resultados pueden no reflejar tu conexion real."
        )
    if link:
        down = metrics.transfer_stats(result.down)["avg"]
        up = metrics.transfer_stats(result.up)["avg"]
        best = max(down, up)
        if best > link * 0.95:
            warnings.append(
                f"El resultado ({metrics.format_mbps(best)}) supera el 95% del enlace "
                f"detectado ({metrics.format_mbps(link)}); puede haber cache o trafico local."
            )
    return warnings


@app.callback(invoke_without_command=True)
def main(
    quick: bool = typer.Option(False, "--quick", "-q", help="Prueba rapida (5s por sentido)"),
    full: bool = typer.Option(False, "--full", "-f", help="Prueba exhaustiva (20s por sentido)"),
    duration: int = typer.Option(None, "--duration", "-t", help="Segundos por sentido"),
    streams: int = typer.Option(None, "--streams", "-s", help="Conexiones en paralelo"),
    no_upload: bool = typer.Option(False, "--no-upload", help="Omitir la prueba de subida"),
    ipv4: bool = typer.Option(False, "--ipv4", "-4", help="Forzar IPv4"),
    ipv6: bool = typer.Option(False, "--ipv6", "-6", help="Forzar IPv6"),
    engine_name: EngineChoice = typer.Option(
        EngineChoice.python, "--engine", "-e", help="Motor de transferencia"
    ),
    show_history: int = typer.Option(
        None, "--history", "-H", help="Mostrar las ultimas N mediciones"
    ),
    compare: bool = typer.Option(False, "--compare", "-c", help="Comparar con la medicion anterior"),
    plan: str = typer.Option(None, "--plan", "-p", help="Plan contratado: BAJADA/SUBIDA en Mbps"),
    min_down: float = typer.Option(None, "--min-down", help="Bajada minima aceptable (Mbps)"),
    min_up: float = typer.Option(None, "--min-up", help="Subida minima aceptable (Mbps)"),
    help: bool = typer.Option(False, "??", help="Mostrar ayuda"),
):
    if help:
        render.render_help(console)
        raise typer.Exit()

    if show_history is not None:
        render.render_history(history.load(show_history), console)
        raise typer.Exit()

    if quick and full:
        console.print(Panel("[red]Usa --quick o --full, no ambos.[/red]", border_style="red", expand=False))
        raise typer.Exit(1)
    if ipv4 and ipv6:
        console.print(Panel("[red]Usa --ipv4 o --ipv6, no ambos.[/red]", border_style="red", expand=False))
        raise typer.Exit(1)

    if engine_name is EngineChoice.curl and shutil.which("curl") is None:
        console.print(
            Panel(
                "[red]No se encontro curl en el PATH.[/red]\n"
                "Usa [green]--engine python[/green] o instala curl.",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(1)

    plan_values = parse_plan(plan)

    if duration is not None:
        seconds = duration
    elif quick:
        seconds = 5
    elif full:
        seconds = 20
    else:
        seconds = 10

    if streams is not None:
        parallel = streams
    elif quick:
        parallel = 4
    elif full:
        parallel = 8
    else:
        parallel = 6

    if seconds < 3:
        console.print(Panel("[red]La duracion minima es 3 segundos.[/red]", border_style="red", expand=False))
        raise typer.Exit(1)
    if not 1 <= parallel <= 32:
        console.print(Panel("[red]Las conexiones deben estar entre 1 y 32.[/red]", border_style="red", expand=False))
        raise typer.Exit(1)

    family = socket.AF_INET if ipv4 else socket.AF_INET6 if ipv6 else None
    previous = history.last() if compare else None

    try:
        result = asyncio.run(
            run_test(engine_name.value, seconds, parallel, not no_upload, family)
        )
    except EngineError as exc:
        console.print(
            Panel(
                f"[red]No se pudo completar la prueba[/red]\n{exc}",
                title="[red]Error de conexion[/red]",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print(
            Panel(
                "[yellow]Prueba cancelada. No se guardo en el historial.[/yellow]",
                border_style="yellow",
                expand=False,
            )
        )
        raise typer.Exit(130)
    except Exception as exc:  # noqa: BLE001 - se muestra al usuario
        console.print(
            Panel(
                f"[red]Error inesperado:[/red] {exc}",
                title="[red]Error[/red]",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(1)

    result.warnings = build_warnings(result)
    if result.down is None or result.down.bytes_total == 0:
        console.print(
            Panel(
                "[red]No se recibieron datos durante la prueba.[/red]\n"
                "Prueba con [green]--engine python[/green] o revisa tu conexion.",
                title="[red]Medicion fallida[/red]",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(1)
    render.render_result(result, console, previous, plan_values)
    history.append(result)
    console.print(Text(f"Guardado en {history.history_path()}", style="dim"))

    down = metrics.transfer_stats(result.down)["avg"]
    up = metrics.transfer_stats(result.up)["avg"]
    failures: list[str] = []
    if min_down is not None and down < min_down:
        failures.append(f"bajada {metrics.format_mbps(down)} < {metrics.format_mbps(min_down)}")
    if min_up is not None and result.up is not None and up < min_up:
        failures.append(f"subida {metrics.format_mbps(up)} < {metrics.format_mbps(min_up)}")
    if failures:
        console.print(
            Panel(
                "[red]Umbral no alcanzado:[/red] " + "; ".join(failures),
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(2)
