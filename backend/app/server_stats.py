from __future__ import annotations

import os
import platform
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import psutil

HOSTFS_ROOT = Path("/hostfs")


def hostfs_root() -> Path | None:
    if HOSTFS_ROOT.is_dir() and (HOSTFS_ROOT / "proc" / "meminfo").is_file():
        return HOSTFS_ROOT
    return None


def _read_meminfo(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        parts = raw.strip().split()
        if not parts:
            continue
        values[key.strip()] = int(parts[0]) * 1024
    return values


@dataclass(frozen=True)
class MemorySnapshot:
    total_bytes: int
    available_bytes: int
    used_bytes: int
    percent: float
    scope: str


def memory_snapshot() -> MemorySnapshot:
    host = hostfs_root()
    if host is not None:
        info = _read_meminfo(host / "proc" / "meminfo")
        total = info.get("MemTotal", 0)
        available = info.get("MemAvailable", info.get("MemFree", 0))
        used = max(total - available, 0)
        percent = (used / total * 100.0) if total else 0.0
        return MemorySnapshot(total, available, used, percent, "host")

    vm = psutil.virtual_memory()
    return MemorySnapshot(
        int(vm.total),
        int(vm.available),
        int(vm.used),
        float(vm.percent),
        "container" if Path("/.dockerenv").is_file() else "host",
    )


def swap_snapshot() -> MemorySnapshot | None:
    host = hostfs_root()
    if host is not None:
        info = _read_meminfo(host / "proc" / "meminfo")
        total = info.get("SwapTotal", 0)
        if total <= 0:
            return None
        free = info.get("SwapFree", 0)
        used = max(total - free, 0)
        percent = (used / total * 100.0) if total else 0.0
        return MemorySnapshot(total, free, used, percent, "host")

    swap = psutil.swap_memory()
    if swap.total <= 0:
        return None
    return MemorySnapshot(
        int(swap.total),
        int(swap.free),
        int(swap.used),
        float(swap.percent),
        "container" if Path("/.dockerenv").is_file() else "host",
    )


@dataclass(frozen=True)
class DiskSnapshot:
    path: str
    mountpoint: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float


def disk_snapshots() -> list[DiskSnapshot]:
    seen: set[str] = set()
    out: list[DiskSnapshot] = []

    def add_usage(path: str, mountpoint: str) -> None:
        key = f"{path}:{mountpoint}"
        if key in seen:
            return
        try:
            usage = psutil.disk_usage(path)
        except OSError:
            return
        seen.add(key)
        out.append(
            DiskSnapshot(
                path=path,
                mountpoint=mountpoint,
                total_bytes=int(usage.total),
                used_bytes=int(usage.used),
                free_bytes=int(usage.free),
                percent=float(usage.percent),
            )
        )

    host = hostfs_root()
    if host is not None:
        add_usage(str(host), "/ (host)")

    for part in psutil.disk_partitions(all=False):
        if part.fstype in {"", "tmpfs", "devtmpfs", "overlay"}:
            continue
        add_usage(part.mountpoint, part.mountpoint)

    if not out:
        add_usage("/", "/")

    by_usage: dict[tuple[int, int, int], DiskSnapshot] = {}
    for disk in out:
        key = (disk.total_bytes, disk.used_bytes, disk.free_bytes)
        prev = by_usage.get(key)
        if prev is None or len(disk.mountpoint) < len(prev.mountpoint):
            by_usage[key] = disk
    ranked = sorted(by_usage.values(), key=lambda d: d.percent, reverse=True)
    return ranked[:8]


@dataclass(frozen=True)
class CpuSnapshot:
    percent: float
    count: int
    load_avg_1m: float | None
    load_avg_5m: float | None
    load_avg_15m: float | None


def cpu_snapshot() -> CpuSnapshot:
    load = os.getloadavg() if hasattr(os, "getloadavg") else (None, None, None)
    return CpuSnapshot(
        percent=float(psutil.cpu_percent(interval=0.2)),
        count=int(psutil.cpu_count(logical=True) or 0),
        load_avg_1m=float(load[0]) if load[0] is not None else None,
        load_avg_5m=float(load[1]) if load[1] is not None else None,
        load_avg_15m=float(load[2]) if load[2] is not None else None,
    )


def uptime_seconds() -> float:
    host = hostfs_root()
    uptime_path = (host / "proc" / "uptime") if host is not None else Path("/proc/uptime")
    try:
        return float(uptime_path.read_text(encoding="utf-8").split()[0])
    except OSError:
        return max(time.time() - psutil.boot_time(), 0.0)


def collect_server_stats_sync() -> dict[str, object]:
    memory = memory_snapshot()
    swap = swap_snapshot()
    cpu = cpu_snapshot()
    disks = disk_snapshots()
    return {
        "collected_at": datetime.now(UTC),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "uptime_seconds": uptime_seconds(),
        "memory": {
            "total_bytes": memory.total_bytes,
            "available_bytes": memory.available_bytes,
            "used_bytes": memory.used_bytes,
            "percent": memory.percent,
            "scope": memory.scope,
        },
        "swap": None
        if swap is None
        else {
            "total_bytes": swap.total_bytes,
            "available_bytes": swap.available_bytes,
            "used_bytes": swap.used_bytes,
            "percent": swap.percent,
            "scope": swap.scope,
        },
        "cpu": {
            "percent": cpu.percent,
            "count": cpu.count,
            "load_avg_1m": cpu.load_avg_1m,
            "load_avg_5m": cpu.load_avg_5m,
            "load_avg_15m": cpu.load_avg_15m,
        },
        "disks": [
            {
                "path": d.path,
                "mountpoint": d.mountpoint,
                "total_bytes": d.total_bytes,
                "used_bytes": d.used_bytes,
                "free_bytes": d.free_bytes,
                "percent": d.percent,
            }
            for d in disks
        ],
    }
