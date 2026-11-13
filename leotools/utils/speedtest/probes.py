"""Sondas de latencia, DNS y tiempo hasta el primer byte."""

import asyncio
import socket
import time

import aiohttp

from .models import LatencyStats

LATENCY_URL = "https://speed.cloudflare.com/__down?bytes=0"
PROBE_TIMEOUT = 3.0


async def _probe(session: aiohttp.ClientSession, url: str) -> float:
    t0 = time.perf_counter()
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=PROBE_TIMEOUT)) as resp:
        await resp.read()
        if resp.status != 200:
            raise aiohttp.ClientResponseError(
                resp.request_info, resp.history, status=resp.status,
                message=f"HTTP {resp.status}", headers=resp.headers,
            )
    return (time.perf_counter() - t0) * 1000.0


async def measure_latency(
    session: aiohttp.ClientSession,
    url: str = LATENCY_URL,
    count: int = 20,
    interval: float = 0.05,
) -> LatencyStats:
    """RTT secuenciales. La primera sonda se descarta (DNS + handshake TLS)."""
    samples: list[float] = []
    failed = 0
    for index in range(count):
        try:
            rtt = await _probe(session, url)
            if index > 0:
                samples.append(rtt)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            if index > 0:
                failed += 1
        if interval:
            await asyncio.sleep(interval)
    return LatencyStats(samples_ms=samples, failed=failed)


async def loaded_latency(
    session: aiohttp.ClientSession,
    stop: asyncio.Event,
    url: str = LATENCY_URL,
    interval: float = 0.3,
) -> list[float]:
    """Mide RTT mientras hay trafico de fondo hasta que se active `stop`."""
    samples: list[float] = []
    while not stop.is_set():
        try:
            samples.append(await _probe(session, url))
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue
    return samples


async def dns_lookup_ms(host: str) -> float | None:
    loop = asyncio.get_running_loop()
    t0 = time.perf_counter()
    try:
        await loop.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        return None
    return (time.perf_counter() - t0) * 1000.0


async def ttfb_ms(session: aiohttp.ClientSession, url: str) -> float | None:
    """Tiempo hasta recibir las cabeceras de respuesta."""
    t0 = time.perf_counter()
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            await resp.read()
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        return None
    return (time.perf_counter() - t0) * 1000.0
