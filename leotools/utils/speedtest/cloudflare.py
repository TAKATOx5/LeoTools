"""Motor de medicion sobre los endpoints publicos de Cloudflare."""

import asyncio
import random
import socket
import time

import aiohttp

from .models import EngineError, TransferResult

BASE = "https://speed.cloudflare.com"
TRACE_URL = f"{BASE}/cdn-cgi/trace"
DOWN_URL = f"{BASE}/__down?bytes={{bytes}}&r={{nonce}}"
UP_URL = f"{BASE}/__up"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LeoTools/0.1"
CHUNK = 256 * 1024
DOWNLOAD_REQUEST = 25_000_000
SAMPLE_INTERVAL = 0.1


def make_session(streams: int, family: int | None = None) -> aiohttp.ClientSession:
    connector = aiohttp.TCPConnector(
        limit=streams * 2 + 4,
        ttl_dns_cache=300,
        family=socket.AF_UNSPEC if family is None else family,
        enable_cleanup_closed=True,
    )
    return aiohttp.ClientSession(
        connector=connector,
        timeout=aiohttp.ClientTimeout(total=None, sock_connect=8, sock_read=60),
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
    )


async def fetch_trace(session: aiohttp.ClientSession) -> dict:
    """Datos del nodo que nos atiende (IP, PoP, pais)."""
    try:
        async with session.get(TRACE_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                raise EngineError(f"Cloudflare respondio HTTP {resp.status}")
            text = await resp.text()
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
        raise EngineError(f"No se pudo contactar a Cloudflare: {exc}") from exc

    data = dict(
        line.split("=", 1)
        for line in text.splitlines()
        if "=" in line
    )
    if "colo" not in data:
        raise EngineError(
            "Respuesta inesperada de Cloudflare (posible portal cautivo o proxy)."
        )
    return data


class _Counter:
    __slots__ = ("total",)

    def __init__(self) -> None:
        self.total = 0

    def add(self, value: int) -> None:
        self.total += value


async def _sample_loop(
    counter: _Counter,
    samples: list[tuple[float, int]],
    stop: asyncio.Event,
    direction: str,
    duration: float,
    on_sample,
) -> None:
    t0 = time.perf_counter()
    last_t = t0
    last_b = 0
    while not stop.is_set() and time.perf_counter() - t0 < duration:
        await asyncio.sleep(SAMPLE_INTERVAL)
        now = time.perf_counter()
        total = counter.total
        samples.append((now - t0, total))
        instant = (total - last_b) * 8.0 / (now - last_t) / 1_000_000 if now > last_t else 0.0
        average = total * 8.0 / (now - t0) / 1_000_000 if now > t0 else 0.0
        if on_sample is not None:
            on_sample(direction, instant, average)
        last_t, last_b = now, total


async def _finish(workers: list[asyncio.Task], duration: float) -> None:
    """Espera a los workers y corta los que sigan con la conexion abierta."""
    await asyncio.wait(workers, timeout=duration + 0.3)
    for task in workers:
        if not task.done():
            task.cancel()
    await asyncio.gather(*workers, return_exceptions=True)


async def download(
    session: aiohttp.ClientSession,
    duration: float,
    streams: int,
    on_sample=None,
) -> TransferResult:
    counter = _Counter()
    samples: list[tuple[float, int]] = []
    errors = 0
    stop = asyncio.Event()
    deadline = time.perf_counter() + duration

    async def worker() -> None:
        nonlocal errors
        while time.perf_counter() < deadline:
            nonce = random.randint(0, 2**31)
            url = DOWN_URL.format(bytes=DOWNLOAD_REQUEST, nonce=nonce)
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise EngineError(f"HTTP {resp.status}")
                    async for chunk in resp.content.iter_chunked(CHUNK):
                        counter.add(len(chunk))
                        if time.perf_counter() >= deadline:
                            return
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError, EngineError):
                errors += 1
                await asyncio.sleep(0.2)

    t0 = time.perf_counter()
    sampler = asyncio.create_task(
        _sample_loop(counter, samples, stop, "down", duration, on_sample)
    )
    workers = [asyncio.create_task(worker()) for _ in range(streams)]
    try:
        await _finish(workers, duration)
    finally:
        stop.set()
        await sampler

    elapsed = max(time.perf_counter() - t0, 0.001)
    samples.append((elapsed, counter.total))
    return TransferResult(
        direction="down",
        samples=samples,
        bytes_total=counter.total,
        elapsed=elapsed,
        errors=errors,
    )


async def upload(
    session: aiohttp.ClientSession,
    duration: float,
    streams: int,
    on_sample=None,
) -> TransferResult:
    counter = _Counter()
    samples: list[tuple[float, int]] = []
    errors = 0
    stop = asyncio.Event()
    deadline = time.perf_counter() + duration
    block = b"\0" * CHUNK

    async def worker() -> None:
        nonlocal errors
        while time.perf_counter() < deadline:
            async def body():
                while time.perf_counter() < deadline:
                    counter.add(len(block))
                    yield block

            try:
                async with session.post(
                    UP_URL,
                    data=body(),
                    headers={"Content-Type": "application/octet-stream"},
                ) as resp:
                    await resp.read()
                    if resp.status != 200:
                        raise EngineError(f"HTTP {resp.status}")
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError, EngineError):
                errors += 1
                await asyncio.sleep(0.2)

    t0 = time.perf_counter()
    sampler = asyncio.create_task(
        _sample_loop(counter, samples, stop, "up", duration, on_sample)
    )
    workers = [asyncio.create_task(worker()) for _ in range(streams)]
    try:
        await _finish(workers, duration)
    finally:
        stop.set()
        await sampler

    elapsed = max(time.perf_counter() - t0, 0.001)
    samples.append((elapsed, counter.total))
    return TransferResult(
        direction="up",
        samples=samples,
        bytes_total=counter.total,
        elapsed=elapsed,
        errors=errors,
    )
