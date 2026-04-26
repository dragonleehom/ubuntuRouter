"""Disk discovery and partition info using lsblk"""

import json
import subprocess
from typing import Optional


def list_disks() -> list[dict]:
    """List physical block devices using lsblk, filtering out virtual devices.

    Returns a list of dicts with: name, size_bytes, type, mountpoint, fs_type,
    model, serial, is_ssd, transport, vendor.
    """
    try:
        r = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL,SERIAL,ROTA,TRAN,VENDOR"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return _error_result("lsblk returned non-zero exit", stderr=r.stderr.strip())
    except FileNotFoundError:
        return _error_result("lsblk not installed")
    except subprocess.TimeoutExpired:
        return _error_result("lsblk timed out")
    except PermissionError:
        return _error_result("insufficient permissions to list disks")
    except Exception as exc:
        return _error_result(f"failed to list disks: {exc}")

    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return _error_result("failed to parse lsblk output")

    devices = data.get("blockdevices", [])
    return _flatten_and_filter(devices)


def _flatten_and_filter(devices: list[dict]) -> list[dict]:
    """Flatten the lsblk tree, filter virtual devices, return cleaned list."""
    results: list[dict] = []

    def _walk(items: list[dict], parent: Optional[str] = None):
        for item in items:
            children = item.pop("children", None)
            name: str = item.get("name", "")

            # Filter virtual devices
            if name.startswith("loop") or name.startswith("ram") or name.startswith("dm-"):
                if children:
                    _walk(children, parent)
                continue

            parsed = _parse_device(item)
            results.append(parsed)

            if children:
                _walk(children, name)

    _walk(devices, None)
    return results


def _parse_device(item: dict) -> dict:
    """Parse a single lsblk device entry into a clean dict."""
    raw_size = item.get("size", "0")
    rota = item.get("rota")

    def _strip(val):
        """Strip whitespace from a string value, returning None if empty."""
        if val is None:
            return None
        stripped = val.strip()
        return stripped if stripped else None

    return {
        "name": item.get("name", ""),
        "size_bytes": _parse_size(raw_size),
        "type": item.get("type", ""),
        "mountpoint": item.get("mountpoint"),
        "fs_type": item.get("fstype") or None,
        "model": _strip(item.get("model")),
        "serial": _strip(item.get("serial")),
        "is_ssd": rota == "0" if rota is not None else None,
        "transport": item.get("tran") or None,
        "vendor": _strip(item.get("vendor")),
    }


def _parse_size(raw: str) -> int:
    """Convert lsblk size string (e.g. '238.5G') to bytes."""
    if not raw:
        return 0
    raw = raw.strip().upper()
    if raw == "0":
        return 0
    try:
        if raw.endswith("B"):
            raw = raw[:-1]
        if raw.endswith("P"):
            return int(float(raw[:-1]) * 1024 ** 5)
        if raw.endswith("T"):
            return int(float(raw[:-1]) * 1024 ** 4)
        if raw.endswith("G"):
            return int(float(raw[:-1]) * 1024 ** 3)
        if raw.endswith("M"):
            return int(float(raw[:-1]) * 1024 ** 2)
        if raw.endswith("K"):
            return int(float(raw[:-1]) * 1024)
        return int(raw)
    except (ValueError, TypeError):
        return 0


def _error_result(message: str, stderr: str = "") -> list[dict]:
    """Return a list with a single error entry."""
    entry: dict = {"error": message}
    if stderr:
        entry["stderr"] = stderr
    return [entry]
