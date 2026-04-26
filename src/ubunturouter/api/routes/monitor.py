"""System Monitoring API & Background Metrics Collector

Provides real-time system monitoring endpoints and a background metrics
collector that persists per-minute CSV snapshots to disk for trend analysis.

Endpoints at /api/v1/monitor/
"""

import csv
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from ..deps import require_auth

router = APIRouter()

# ── Background collector configuration ──────────────────────────────────
MONITOR_DIR = Path("/opt/ubunturouter/data/monitor")
COLLECT_INTERVAL = 60  # seconds

# Thread control
_collector_thread: Optional[threading.Thread] = None
_collector_stop = threading.Event()

# In-memory snapshot for network traffic delta
_previous_net: dict = {}
_previous_net_time: float = 0.0
_net_lock = threading.Lock()

# ── Helper utilities ────────────────────────────────────────────────────


def _read_proc_file(path: str, timeout: int = 5) -> str:
    """Read a /proc or /sys file safely via subprocess."""
    try:
        r = subprocess.run(
            ["cat", path], capture_output=True, text=True, timeout=timeout
        )
        return r.stdout
    except Exception:
        return ""


def _run_cmd(cmd: list, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run a subprocess command with a timeout, returning the result."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


# ── Data collection helpers ─────────────────────────────────────────────


def _get_cpu_usage() -> float:
    """Read CPU usage percentage from /proc/stat."""
    try:
        data = _read_proc_file("/proc/stat")
        lines = data.strip().split("\n")
        for line in lines:
            if line.startswith("cpu "):
                parts = line.split()
                # user, nice, system, idle, iowait, irq, softirq, steal
                fields = [int(v) for v in parts[1:]]
                total = sum(fields)
                idle = fields[3]  # idle
                # Use the first call for baseline (no previous delta)
                return round(100 * (1 - idle / total), 1)
        return 0.0
    except Exception:
        return 0.0


def _get_cpu_usage_delta() -> float:
    """Compute CPU usage as delta between two /proc/stat samples.

    This is more accurate than a single snapshot.  We keep a running
    baseline inside the closure.
    """
    # We'll do a simple approach: two reads 100ms apart
    try:
        prev = _read_proc_file("/proc/stat")
        time.sleep(0.1)
        curr = _read_proc_file("/proc/stat")

        def _parse_cpu_line(text: str):
            for line in text.strip().split("\n"):
                if line.startswith("cpu "):
                    parts = line.split()
                    vals = [int(v) for v in parts[1:9]]
                    return sum(vals), vals[3]  # (total, idle)
            return 0, 0

        prev_total, prev_idle = _parse_cpu_line(prev)
        cur_total, cur_idle = _parse_cpu_line(curr)
        delta_total = cur_total - prev_total
        delta_idle = cur_idle - prev_idle
        if delta_total == 0:
            return 0.0
        return round(100 * (1 - delta_idle / delta_total), 1)
    except Exception:
        return 0.0


def _get_loadavg() -> dict:
    """Read load averages from /proc/loadavg."""
    try:
        data = _read_proc_file("/proc/loadavg").strip()
        parts = data.split()
        if len(parts) >= 3:
            return {
                "load_1": float(parts[0]),
                "load_5": float(parts[1]),
                "load_15": float(parts[2]),
            }
    except Exception:
        pass
    return {"load_1": 0.0, "load_5": 0.0, "load_15": 0.0}


def _get_cores() -> int:
    """Get number of CPU cores."""
    try:
        r = _run_cmd(["nproc", "--all"])
        return int(r.stdout.strip() or 1)
    except Exception:
        return 1


def _get_memory_usage() -> dict:
    """Read memory info from /proc/meminfo."""
    try:
        data = _read_proc_file("/proc/meminfo")
        mem = {}
        for line in data.strip().split("\n"):
            m = re.match(r"^(\w+):\s+(\d+)", line)
            if m:
                key = m.group(1)
                val_kb = int(m.group(2))
                mem[key] = val_kb * 1024  # convert to bytes

        total = mem.get("MemTotal", 0)
        avail = mem.get("MemAvailable", total)
        used = total - avail
        usage_pct = round(100 * used / total, 1) if total > 0 else 0.0
        return {
            "total_bytes": total,
            "used_bytes": used,
            "available_bytes": avail,
            "usage_pct": usage_pct,
        }
    except Exception:
        return {"total_bytes": 0, "used_bytes": 0, "available_bytes": 0, "usage_pct": 0.0}


def _get_disk_usage() -> list:
    """Get disk usage for all mount points using df -B1 (exact bytes)."""
    try:
        r = _run_cmd(["df", "-B1", "--exclude-type=tmpfs", "--exclude-type=devtmpfs"])
        lines = r.stdout.strip().split("\n")[1:]  # skip header
        disks = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 6:
                # Filesystem 1B-blocks Used Available Use% Mounted on
                try:
                    total = int(parts[1])
                    used = int(parts[2])
                    avail = int(parts[3])
                    use_pct_str = parts[4].rstrip("%")
                    use_pct = float(use_pct_str) if use_pct_str != "-" else 0.0
                    mount = parts[5]
                    disks.append({
                        "mount": mount,
                        "total_bytes": total,
                        "used_bytes": used,
                        "available_bytes": avail,
                        "use_pct": use_pct,
                    })
                except (ValueError, IndexError):
                    continue
        return disks
    except Exception:
        return []


def _get_temperatures() -> list:
    """Read thermal zone temperatures from /sys/class/thermal/."""
    temps = []
    try:
        base = Path("/sys/class/thermal")
        for tz in sorted(base.glob("thermal_zone*")):
            name_file = tz / "type"
            temp_file = tz / "temp"
            if temp_file.exists() and name_file.exists():
                try:
                    name = name_file.read_text().strip()
                    raw = temp_file.read_text().strip()
                    temp_c = round(int(raw) / 1000, 1)
                    temps.append({"name": name, "temp_c": temp_c})
                except (ValueError, OSError):
                    continue
    except Exception:
        pass
    return temps


def _get_network_interfaces() -> list:
    """Read network interface stats from /proc/net/dev, filtering out lo."""
    ifaces = []
    try:
        data = _read_proc_file("/proc/net/dev")
        for line in data.strip().split("\n")[2:]:  # skip headers
            parts = line.split()
            if len(parts) < 10:
                continue
            name = parts[0].rstrip(":")
            if name == "lo":
                continue
            ifaces.append({
                "name": name,
                "rx_bytes": int(parts[1]),
                "tx_bytes": int(parts[9]),
                "rx_packets": int(parts[2]),
                "tx_packets": int(parts[10]),
            })
    except Exception:
        pass
    return ifaces


def _get_uptime() -> float:
    """Read system uptime in seconds from /proc/uptime."""
    try:
        data = _read_proc_file("/proc/uptime").strip()
        return float(data.split()[0])
    except Exception:
        return 0.0


def _get_net_traffic() -> dict:
    """Get raw network traffic counters keyed by interface name."""
    traffic = {}
    try:
        data = _read_proc_file("/proc/net/dev")
        for line in data.strip().split("\n")[2:]:
            parts = line.split()
            if len(parts) < 10:
                continue
            name = parts[0].rstrip(":")
            if name == "lo":
                continue
            traffic[name] = {
                "rx": int(parts[1]),
                "tx": int(parts[9]),
            }
    except Exception:
        pass
    return traffic


def _compute_network_speed() -> dict:
    """Compute network speed (bytes/sec) by comparing with previous snapshot."""
    global _previous_net, _previous_net_time
    current = _get_net_traffic()
    now = time.time()

    with _net_lock:
        if not _previous_net or not _previous_net_time:
            # First call — store and return zeros
            _previous_net = current
            _previous_net_time = now
            result = {}
            for iface in current:
                result[iface] = {"rx_bytes_sec": 0.0, "tx_bytes_sec": 0.0}
            return result

        elapsed = now - _previous_net_time
        if elapsed <= 0:
            elapsed = 0.1

        result = {}
        for iface, cur_data in current.items():
            prev_data = _previous_net.get(iface, {"rx": 0, "tx": 0})
            rx_delta = max(0, cur_data["rx"] - prev_data["rx"])
            tx_delta = max(0, cur_data["tx"] - prev_data["tx"])
            result[iface] = {
                "rx_bytes_sec": round(rx_delta / elapsed, 1),
                "tx_bytes_sec": round(tx_delta / elapsed, 1),
            }

        # Update snapshot
        _previous_net = current
        _previous_net_time = now

    return result


def _get_process_list() -> list:
    """Get top 50 processes by CPU usage from ps."""
    try:
        r = _run_cmd([
            "ps", "-eo", "pid,user,%cpu,%mem,rss,comm",
            "--sort=-%cpu", "--no-headers",
        ])
        processes = []
        for line in r.stdout.strip().split("\n")[:50]:
            parts = line.split(maxsplit=5)
            if len(parts) >= 6:
                try:
                    rss_kb = int(parts[4])
                    rss_mb = round(rss_kb / 1024, 1)
                except ValueError:
                    rss_mb = 0.0
                processes.append({
                    "pid": int(parts[0]),
                    "user": parts[1],
                    "cpu_pct": float(parts[2]),
                    "mem_pct": float(parts[3]),
                    "rss_mb": rss_mb,
                    "command": parts[5],
                })
        return processes
    except Exception:
        return []


def _get_process_detail(pid: int) -> dict:
    """Get detailed info about a single process from /proc/<pid>/."""
    base = Path(f"/proc/{pid}")
    if not base.exists():
        return {"error": f"Process {pid} not found"}

    result = {"pid": pid}
    try:
        # status file
        status_file = base / "status"
        if status_file.exists():
            status_data = status_file.read_text()
            for line in status_data.split("\n"):
                if line.startswith("Name:"):
                    result["name"] = line.split(":", 1)[1].strip()
                elif line.startswith("State:"):
                    result["state"] = line.split(":", 1)[1].strip()
                elif line.startswith("Threads:"):
                    result["threads"] = int(line.split(":", 1)[1].strip())
                elif line.startswith("VmRSS:"):
                    parts = line.split(":", 1)[1].strip().split()
                    if parts:
                        result["memory_bytes"] = int(parts[0]) * 1024 if parts[0].isdigit() else 0

        if "name" not in result:
            result["name"] = ""

        # cmdline
        cmdline_file = base / "cmdline"
        if cmdline_file.exists():
            cmd = cmdline_file.read_text().replace("\0", " ").strip()
            result["command"] = cmd if cmd else ""
        else:
            result["command"] = ""

        # stat file for cpu and uptime
        stat_file = base / "stat"
        if stat_file.exists():
            stat_data = stat_file.read_text()
            # Format: pid (comm) state ppid ... utime stime ... starttime
            # Find closing paren after comm
            try:
                rparen = stat_data.rfind(")")
                after = stat_data[rparen + 2:]
                fields = after.split()
                if len(fields) >= 19:
                    utime = int(fields[11])
                    stime = int(fields[12])
                    starttime = int(fields[19])
                    hertz = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
                    total_time = (utime + stime) / hertz

                    # Uptime seconds
                    uptime = _get_uptime()
                    seconds = uptime - (starttime / hertz)
                    result["uptime_seconds"] = round(max(0, seconds), 1)

                    # Rough CPU % over process lifetime
                    if seconds > 0:
                        result["cpu_pct"] = round(
                            100 * total_time / seconds, 1
                        )
                    else:
                        result["cpu_pct"] = 0.0
            except (ValueError, IndexError):
                pass

        result.setdefault("state", "")
        result.setdefault("threads", 0)
        result.setdefault("memory_bytes", 0)
        result.setdefault("cpu_pct", 0.0)
        result.setdefault("uptime_seconds", 0.0)
        result.setdefault("command", "")
        result.setdefault("name", "")

    except Exception as e:
        return {"error": str(e)}

    return result


# ── CSV persistence helpers ─────────────────────────────────────────────


def _append_csv(path: Path, row: list) -> None:
    """Append a row to a CSV file, creating it with a header if needed."""
    is_new = not path.exists()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", newline="") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(["timestamp"] + [f"col{i}" for i in range(1, len(row))])
            writer.writerow(row)
    except Exception:
        pass


def _cleanup_old_csvs() -> None:
    """Delete CSV files older than 24 hours to prevent disk bloat."""
    now = time.time()
    cutoff = now - 86400  # 24 hours
    try:
        MONITOR_DIR.mkdir(parents=True, exist_ok=True)
        for f in MONITOR_DIR.glob("*.csv"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except OSError:
                pass
    except Exception:
        pass


# ── Background collector ────────────────────────────────────────────────


def _collect_and_save() -> None:
    """Collect system metrics and append to CSV files.

    Called every 60 seconds by the background thread.
    """
    MONITOR_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.time()

    # CPU (using delta method for better accuracy)
    cpu = _get_cpu_usage_delta()
    _append_csv(MONITOR_DIR / "cpu.csv", [ts, cpu])

    # Memory
    mem = _get_memory_usage()
    _append_csv(MONITOR_DIR / "memory.csv", [ts, mem["usage_pct"]])

    # Network (per interface)
    net = _get_net_traffic()
    for iface, data in net.items():
        safe_name = iface.replace("/", "_")
        _append_csv(MONITOR_DIR / f"net_{safe_name}.csv", [ts, data["rx"], data["tx"]])

    # Temperature
    temps = _get_temperatures()
    for entry in temps:
        safe = entry["name"].replace("/", "_")
        _append_csv(MONITOR_DIR / f"temp_{safe}.csv", [ts, entry["temp_c"]])

    # Cleanup old files
    _cleanup_old_csvs()


def _collector_loop() -> None:
    """Background thread loop: collect every COLLECT_INTERVAL seconds."""
    while not _collector_stop.is_set():
        try:
            _collect_and_save()
        except Exception:
            pass
        _collector_stop.wait(COLLECT_INTERVAL)


def start_collector() -> None:
    """Start the background metrics collector thread."""
    global _collector_thread
    if _collector_thread is not None and _collector_thread.is_alive():
        return
    _collector_stop.clear()
    _collector_thread = threading.Thread(target=_collector_loop, daemon=True)
    _collector_thread.start()


def stop_collector() -> None:
    """Stop the background metrics collector thread."""
    _collector_stop.set()
    if _collector_thread:
        _collector_thread.join(timeout=5)


# ── History reader ──────────────────────────────────────────────────────


def _read_history(metric: str, range_seconds: int) -> dict:
    """Read historical CSV data for a given metric.

    Args:
        metric: Metric name (e.g., 'cpu', 'memory', 'net_eth0').
        range_seconds: Lookback window in seconds (3600, 21600, 86400).

    Returns:
        dict with 'data' (list of [timestamp, ...] rows) and optional 'message'.
    """
    safe = metric.replace("/", "_").replace("..", "_")
    csv_path = MONITOR_DIR / f"{safe}.csv"

    if not csv_path.exists():
        return {"data": [], "message": f"No data available for metric '{metric}'"}

    cutoff = time.time() - range_seconds
    rows = []
    try:
        with open(csv_path, "r") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) < 2:
                    continue
                try:
                    ts = float(row[0])
                    if ts >= cutoff:
                        values = [ts] + [float(v) if v.replace(".", "", 1).lstrip("-").isdigit() else v for v in row[1:]]
                        rows.append(values)
                except (ValueError, IndexError):
                    continue
    except Exception as e:
        return {"data": [], "error": str(e)}

    return {"data": rows}


def _parse_range(range_str: str) -> int:
    """Parse range string (1h, 6h, 24h) into seconds."""
    mapping = {
        "1h": 3600,
        "6h": 21600,
        "24h": 86400,
    }
    return mapping.get(range_str, 3600)


# ══════════════════════════════════════════════════════════════════════
#  API Endpoints
# ══════════════════════════════════════════════════════════════════════


@router.get("/realtime")
async def monitor_realtime(auth=Depends(require_auth)):
    """Live system snapshot with CPU, memory, disk, temperature,
    network, uptime, and timestamp."""
    try:
        cpu_usage = _get_cpu_usage_delta()
        loadavg = _get_loadavg()
        cores = _get_cores()
        mem = _get_memory_usage()
        disks = _get_disk_usage()
        temps = _get_temperatures()
        net = _get_network_interfaces()
        uptime = _get_uptime()

        return {
            "cpu": {
                "usage_pct": cpu_usage,
                **loadavg,
                "cores": cores,
            },
            "memory": mem,
            "disk": disks,
            "temperature": temps,
            "network": net,
            "uptime_seconds": uptime,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/history")
async def monitor_history(
    metric: str = Query("cpu", description="Metric name (e.g., cpu, memory, net_eth0)"),
    range: str = Query("1h", pattern="^(1h|6h|24h)$", description="Time range: 1h, 6h, 24h"),
    auth=Depends(require_auth),
):
    """Historical trend data for a given metric.

    Returns an array of [timestamp, value, ...] rows from the CSV file.
    """
    try:
        range_seconds = _parse_range(range)
        return _read_history(metric, range_seconds)
    except Exception as e:
        return {"error": str(e), "data": []}


@router.get("/network/traffic")
async def monitor_network_traffic(auth=Depends(require_auth)):
    """Network traffic delta in bytes/sec for each interface.

    Compares current /proc/net/dev values against the previous snapshot
    stored in memory.
    """
    try:
        speeds = _compute_network_speed()
        return {"interfaces": speeds}
    except Exception as e:
        return {"error": str(e)}


@router.get("/processes")
async def monitor_processes(auth=Depends(require_auth)):
    """Process list sorted by CPU usage (top 50)."""
    try:
        procs = _get_process_list()
        return {"processes": procs, "count": len(procs)}
    except Exception as e:
        return {"error": str(e), "processes": []}


@router.get("/processes/{pid}")
async def monitor_process_detail(pid: int, auth=Depends(require_auth)):
    """Detailed info about a single process by PID."""
    try:
        return _get_process_detail(pid)
    except Exception as e:
        return {"error": str(e)}


# ── Auto-start the collector on module import ───────────────────────────
# The collector starts as a daemon thread.  To stop it, call stop_collector().
start_collector()
