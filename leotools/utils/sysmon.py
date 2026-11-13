"""Muestreo de CPU, RAM, discos, Ethernet y temperaturas para el dashboard."""

import json
import os
import re
import socket
import subprocess
import time
from dataclasses import dataclass, field

import psutil

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
VIRTUAL_NIC = re.compile(
    r"loopback|pseudo|vethernet|hyper-v|virtual|vmware|virtualbox|bluetooth|area local",
    re.IGNORECASE,
)


@dataclass
class Temps:
    cpu: float | None = None
    gpu: float | None = None
    gpu_util: float | None = None
    gpu_mem_used: int | None = None
    gpu_mem_total: int | None = None
    source: str = ""
    note: str = ""


@dataclass
class Snapshot:
    cpu_percent: float = 0.0
    per_core: list[float] = field(default_factory=list)
    freq_mhz: float = 0.0
    cores: int = 0
    ram_percent: float = 0.0
    ram_used: int = 0
    ram_total: int = 0
    swap_percent: float = 0.0
    swap_used: int = 0
    swap_total: int = 0
    disk_percent: float = 0.0
    disk_used: int = 0
    disk_total: int = 0
    net_name: str = "-"
    net_ip: str = "-"
    net_link_mbps: float = 0.0
    net_down_mbps: float = 0.0
    net_up_mbps: float = 0.0
    net_sent: int = 0
    net_recv: int = 0
    net_errors: int = 0
    net_drops: int = 0


def rate_mbps(delta_bytes: int, seconds: float) -> float:
    if seconds <= 0 or delta_bytes <= 0:
        return 0.0
    return delta_bytes * 8.0 / seconds / 1_000_000


def parse_nvidia_smi(text: str) -> Temps | None:
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    if not line:
        return None
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 5:
        return None
    try:
        return Temps(
            gpu=float(parts[1]),
            gpu_util=float(parts[2]),
            gpu_mem_used=int(float(parts[3])),
            gpu_mem_total=int(float(parts[4])),
            source="nvidia-smi",
        )
    except ValueError:
        return None


def parse_lhm(text: str) -> float | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return None

    cpu_values: list[tuple[str, float]] = []
    for sensor in data:
        if not isinstance(sensor, dict):
            continue
        name = str(sensor.get("Name", ""))
        value = sensor.get("Value")
        if "cpu" not in name.lower() or value is None:
            continue
        try:
            cpu_values.append((name, float(value)))
        except (TypeError, ValueError):
            continue
    if not cpu_values:
        return None
    for name, value in cpu_values:
        if "package" in name.lower() or "tctl" in name.lower():
            return value
    return sum(value for _, value in cpu_values) / len(cpu_values)


def parse_acpi(text: str) -> float | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        data = [data]
    values: list[float] = []
    for zone in data if isinstance(data, list) else []:
        value = zone.get("CurrentTemperature") if isinstance(zone, dict) else None
        if value is None:
            continue
        celsius = float(value) / 10.0 - 273.15
        if 15 <= celsius <= 115:
            values.append(celsius)
    return max(values) if values else None


def _powershell(script: str, timeout: float = 4.0) -> str:
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (completed.stdout or b"").decode("utf-8", "replace")


class SystemSampler:
    def __init__(self) -> None:
        self._last_net: tuple[int, int] | None = None
        self._last_time = time.monotonic()
        self._nic = self._pick_nic()
        psutil.cpu_percent(interval=None, percpu=True)
        self.sample()

    def _pick_nic(self) -> str:
        counters = psutil.net_io_counters(pernic=True)
        stats = psutil.net_if_stats()
        best: tuple[int, str] | None = None
        for name, values in counters.items():
            if VIRTUAL_NIC.search(name):
                continue
            info = stats.get(name)
            if info is None or not info.isup:
                continue
            traffic = values.bytes_recv + values.bytes_sent
            if best is None or traffic > best[0]:
                best = (traffic, name)
        if best is not None:
            return best[1]
        for name, info in stats.items():
            if info.isup and not VIRTUAL_NIC.search(name):
                return name
        return "Ethernet"

    def _ipv4(self, name: str) -> str:
        for address in psutil.net_if_addrs().get(name, []):
            if address.family == socket.AF_INET:
                return address.address
        return "-"

    def sample(self) -> Snapshot:
        now = time.monotonic()
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        try:
            disk = psutil.disk_usage(os.environ.get("SystemDrive", os.path.abspath(os.sep)) + os.sep)
        except OSError:
            disk = None

        try:
            freq = psutil.cpu_freq()
            freq_mhz = freq.current if freq else 0.0
        except (AttributeError, OSError):
            freq_mhz = 0.0

        stats = psutil.net_if_stats()
        counters = psutil.net_io_counters(pernic=True)
        if self._nic not in counters or not stats.get(self._nic, None) or not stats[self._nic].isup:
            self._nic = self._pick_nic()
        nic = counters.get(self._nic)
        down = up = 0.0
        if nic is not None:
            if self._last_net is not None:
                down = rate_mbps(nic.bytes_recv - self._last_net[0], now - self._last_time)
                up = rate_mbps(nic.bytes_sent - self._last_net[1], now - self._last_time)
            self._last_net = (nic.bytes_recv, nic.bytes_sent)
        self._last_time = now

        link = stats[self._nic].speed if self._nic in stats else 0.0
        return Snapshot(
            cpu_percent=(sum(per_core) / len(per_core)) if per_core else 0.0,
            per_core=per_core,
            freq_mhz=freq_mhz,
            cores=len(per_core),
            ram_percent=memory.percent,
            ram_used=memory.used,
            ram_total=memory.total,
            swap_percent=swap.percent,
            swap_used=swap.used,
            swap_total=swap.total,
            disk_percent=disk.percent if disk else 0.0,
            disk_used=disk.used if disk else 0,
            disk_total=disk.total if disk else 0,
            net_name=self._nic,
            net_ip=self._ipv4(self._nic),
            net_link_mbps=float(link or 0),
            net_down_mbps=down,
            net_up_mbps=up,
            net_sent=nic.bytes_sent if nic else 0,
            net_recv=nic.bytes_recv if nic else 0,
            net_errors=(nic.errin + nic.errout) if nic else 0,
            net_drops=(nic.dropin + nic.dropout) if nic else 0,
        )

    def sample_temps(self) -> Temps:
        temps = Temps()
        if os.name == "nt":
            try:
                completed = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    timeout=3,
                    creationflags=CREATE_NO_WINDOW,
                )
                text = (completed.stdout or b"").decode("utf-8", "replace")
                parsed = parse_nvidia_smi(text)
                if parsed is not None:
                    temps.gpu = parsed.gpu
                    temps.gpu_util = parsed.gpu_util
                    temps.gpu_mem_used = parsed.gpu_mem_used
                    temps.gpu_mem_total = parsed.gpu_mem_total
                    temps.source = "nvidia-smi"
            except (OSError, subprocess.SubprocessError):
                pass

            for namespace in ("root/LibreHardwareMonitor", "root/OpenHardwareMonitor"):
                script = (
                    f"Get-CimInstance -Namespace {namespace} -ClassName Sensor "
                    "-ErrorAction Stop | Where-Object SensorType -eq 'Temperature' "
                    "| Select-Object Name,Value | ConvertTo-Json -Compress"
                )
                value = parse_lhm(_powershell(script))
                if value is not None:
                    temps.cpu = value
                    temps.source = "LibreHardwareMonitor" if "Libre" in namespace else "OpenHardwareMonitor"
                    break

            if temps.cpu is None:
                script = (
                    "Get-CimInstance -Namespace root/wmi "
                    "-ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop "
                    "| Select-Object CurrentTemperature | ConvertTo-Json -Compress"
                )
                value = parse_acpi(_powershell(script))
                if value is not None:
                    temps.cpu = value
                    temps.note = "ACPI"
                    if not temps.source:
                        temps.source = "ACPI"

        if temps.cpu is None:
            temps.note = "CPU: instala LibreHardwareMonitor"
        return temps
