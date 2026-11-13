"""Deteccion del enlace local y de posibles VPN activas."""

import json
import os
import re
import subprocess

VPN_PATTERN = re.compile(
    r"vpn|wireguard|tailscale|zerotier|openvpn|nordlynx|proton|tap|tun",
    re.IGNORECASE,
)
SPEED_PATTERN = re.compile(r"([\d.]+)\s*(Gbps|Mbps|Kbps)", re.IGNORECASE)
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _parse_speed(value: str) -> float | None:
    match = SPEED_PATTERN.search(value or "")
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2).lower()
    if unit == "gbps":
        return amount * 1000
    if unit == "kbps":
        return amount / 1000
    return amount


def detect_network() -> tuple[float | None, str | None]:
    """Devuelve (velocidad maxima del enlace en Mbps, nombre de VPN activa)."""
    if os.name != "nt":
        return None, None
    script = (
        "Get-NetAdapter | Select-Object Name,Status,LinkSpeed "
        "| ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            timeout=6,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None

    raw = (completed.stdout or b"").decode("utf-8", "replace").strip()
    if not raw:
        return None, None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, None
    if isinstance(data, dict):
        data = [data]

    link: float | None = None
    vpn: str | None = None
    for adapter in data:
        if str(adapter.get("Status", "")).lower() != "up":
            continue
        name = str(adapter.get("Name", ""))
        speed = _parse_speed(str(adapter.get("LinkSpeed", "")))
        if VPN_PATTERN.search(name):
            if vpn is None:
                vpn = name
            continue
        if speed and (link is None or speed > link):
            link = speed
    return link, vpn
