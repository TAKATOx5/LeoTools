"""Seleccion del motor de transferencia."""

from . import cloudflare, curl_engine
from .models import TransferResult


async def download(
    session,
    engine: str,
    duration: float,
    streams: int,
    on_sample=None,
    family: int | None = None,
) -> TransferResult:
    if engine == "curl":
        return await curl_engine.download(duration, streams, on_sample, family)
    return await cloudflare.download(session, duration, streams, on_sample)


async def upload(
    session,
    engine: str,
    duration: float,
    streams: int,
    on_sample=None,
    family: int | None = None,
) -> TransferResult:
    if engine == "curl":
        return await curl_engine.upload(duration, streams, on_sample, family)
    return await cloudflare.upload(session, duration, streams, on_sample)
