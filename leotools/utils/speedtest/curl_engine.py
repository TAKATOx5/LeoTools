"""Motor alternativo basado en el curl del sistema (TLS nativo)."""

import asyncio
import os
import random
import socket
import tempfile
import time

from .cloudflare import DOWN_URL, UP_URL, USER_AGENT
from .models import TransferResult

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
NULL_DEVICE = "NUL" if os.name == "nt" else "/dev/null"
PAYLOAD_MB = 32
DOWNLOAD_REQUEST = 50_000_000


def _family_flag(family: int | None) -> list[str]:
    if family == socket.AF_INET:
        return ["-4"]
    if family == socket.AF_INET6:
        return ["-6"]
    return []


async def _curl(args: list[str], timeout: float) -> str:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout + 10)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return ""
    return out.decode("utf-8", "replace").strip()


async def download(
    duration: float, streams: int, on_sample=None, family: int | None = None
) -> TransferResult:
    t0 = time.perf_counter()
    deadline = t0 + duration
    state = {"bytes": 0, "errors": 0, "throttled": 0}
    family_args = _family_flag(family)

    async def worker() -> None:
        while time.perf_counter() < deadline:
            remaining = max(0.3, deadline - time.perf_counter())
            url = DOWN_URL.format(
                bytes=DOWNLOAD_REQUEST, nonce=random.randint(0, 2**31)
            )
            out = await _curl(
                [
                    "curl", "-s", "-o", NULL_DEVICE, *family_args,
                    "--connect-timeout", "8",
                    "--max-time", f"{remaining:.2f}",
                    "-A", USER_AGENT,
                    "--write-out", "%{http_code} %{size_download}",
                    url,
                ],
                timeout=remaining,
            )
            try:
                code, size = out.split()[-2:]
                if code in {"200", "100", "000"}:
                    state["bytes"] += int(size)
                elif code == "429":
                    state["throttled"] += 1
                    await asyncio.sleep(1.0)
                else:
                    state["errors"] += 1
            except (ValueError, IndexError):
                state["errors"] += 1
            if on_sample is not None:
                elapsed = max(time.perf_counter() - t0, 0.001)
                mbps = state["bytes"] * 8.0 / elapsed / 1_000_000
                on_sample("down", mbps, mbps)

    await asyncio.gather(*[asyncio.create_task(worker()) for _ in range(streams)])
    elapsed = max(time.perf_counter() - t0, 0.001)
    return TransferResult(
        direction="down",
        samples=[(elapsed, state["bytes"])],
        bytes_total=state["bytes"],
        elapsed=elapsed,
        errors=state["errors"],
        throttled=state["throttled"],
    )


async def upload(
    duration: float, streams: int, on_sample=None, family: int | None = None
) -> TransferResult:
    t0 = time.perf_counter()
    deadline = t0 + duration
    state = {"bytes": 0, "errors": 0, "throttled": 0}
    family_args = _family_flag(family)

    handle = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
    payload_path = handle.name
    try:
        block = b"\0" * (1024 * 1024)
        for _ in range(PAYLOAD_MB):
            handle.write(block)
        handle.close()

        async def worker() -> None:
            while time.perf_counter() < deadline:
                remaining = max(0.3, deadline - time.perf_counter())
                out = await _curl(
                    [
                        "curl", "-s", "-o", NULL_DEVICE, "-X", "POST", *family_args,
                        "--connect-timeout", "8",
                        "--max-time", f"{remaining:.2f}",
                        "-H", "Content-Type: application/octet-stream",
                        "-A", USER_AGENT,
                        "--data-binary", f"@{payload_path}",
                        "--write-out", "%{http_code} %{size_upload}",
                        UP_URL,
                    ],
                    timeout=remaining,
                )
                try:
                    code, size = out.split()[-2:]
                    if code in {"200", "100", "000"}:
                        state["bytes"] += int(size)
                    elif code == "429":
                        state["throttled"] += 1
                        await asyncio.sleep(1.0)
                    else:
                        state["errors"] += 1
                except (ValueError, IndexError):
                    state["errors"] += 1
                if on_sample is not None:
                    elapsed = max(time.perf_counter() - t0, 0.001)
                    mbps = state["bytes"] * 8.0 / elapsed / 1_000_000
                    on_sample("up", mbps, mbps)

        await asyncio.gather(*[asyncio.create_task(worker()) for _ in range(streams)])
    finally:
        try:
            os.unlink(payload_path)
        except OSError:
            pass

    elapsed = max(time.perf_counter() - t0, 0.001)
    return TransferResult(
        direction="up",
        samples=[(elapsed, state["bytes"])],
        bytes_total=state["bytes"],
        elapsed=elapsed,
        errors=state["errors"],
        throttled=state["throttled"],
    )
