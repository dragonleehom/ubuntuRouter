"""S.M.A.R.T status and information via smartctl"""

import subprocess
import re
from typing import Optional


SMARTCTL_NOT_FOUND = "smartctl not installed (install smartmontools package)"


def _run_smartctl(args: list[str], timeout: int = 15) -> tuple[Optional[str], Optional[str]]:
    """Run smartctl with the given args; returns (stdout, error_message).

    Returns (None, error_message) on any failure.
    """
    try:
        r = subprocess.run(
            ["smartctl", *args],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.stdout, None
    except FileNotFoundError:
        return None, SMARTCTL_NOT_FOUND
    except subprocess.TimeoutExpired:
        return None, "smartctl timed out"
    except PermissionError:
        return None, "insufficient permissions to read SMART data"
    except Exception as exc:
        return None, f"failed to run smartctl: {exc}"


def get_smart_info(device: str) -> dict:
    """Get full SMART info for a device using smartctl -a.

    Returns dict with parsed SMART attributes plus a 'raw_output' field
    containing the full smartctl output.
    """
    stdout, error = _run_smartctl(["-a", f"/dev/{device}"])
    if error:
        return {"device": device, "error": error}
    if stdout is None:
        return {"device": device, "error": "no output from smartctl"}

    # Check if device is non-SMART (USB drives etc.)
    if "Device does not support SMART" in stdout or "Unknown USB bridge" in stdout:
        return {
            "device": device,
            "smart_available": False,
            "message": "Device does not support SMART (USB or non-SMART device)",
        }

    return {
        "device": device,
        "smart_available": True,
        **(_parse_smart_info(stdout)),
        "raw_output": stdout,
    }


def get_smart_status(device: str) -> dict:
    """Get SMART health status via smartctl -H.

    Returns dict with overall_health and parsed attributes summary.
    """
    stdout, error = _run_smartctl(["-H", f"/dev/{device}"])
    if error:
        return {"device": device, "error": error}
    if stdout is None:
        return {"device": device, "error": "no output from smartctl"}

    if "Device does not support SMART" in stdout or "Unknown USB bridge" in stdout:
        return {
            "device": device,
            "smart_available": False,
            "message": "Device does not support SMART",
        }

    # Parse overall health
    health = "unknown"
    m = re.search(r"SMART overall-health self-assessment test result:\s*(\S+)", stdout)
    if m:
        health = m.group(1).lower()
    else:
        m = re.search(r"SMART Health Status:\s*(\S+)", stdout)
        if m:
            health = m.group(1).lower()

    # Try to get a few key attributes from full info as well
    attrs = {}
    for line in stdout.split("\n"):
        line_stripped = line.strip()
        if "Reallocated_Sector_Ct" in line_stripped or "Reallocated_Event_Count" in line_stripped:
            parts = line_stripped.split()
            if len(parts) >= 10:
                attrs["reallocated_sector_count"] = _parse_attr_raw(parts[9])
        if "Temperature_Celsius" in line_stripped:
            parts = line_stripped.split()
            if len(parts) >= 10:
                attrs["temperature"] = _parse_attr_raw(parts[9])
        if "Power_On_Hours" in line_stripped or "Power_On_Minutes" in line_stripped:
            parts = line_stripped.split()
            if len(parts) >= 10:
                attrs["power_on_hours"] = _parse_attr_raw(parts[9])

    return {
        "device": device,
        "smart_available": True,
        "overall_health": health,
        "smart_status_output": stdout,
        **attrs,
    }


def _parse_smart_info(stdout: str) -> dict:
    """Parse SMART attributes from full smartctl -a output."""
    result: dict = {}

    # overall health
    health = "unknown"
    m = re.search(r"SMART overall-health self-assessment test result:\s*(\S+)", stdout)
    if m:
        health = m.group(1).lower()
    else:
        m = re.search(r"SMART Health Status:\s*(\S+)", stdout)
        if m:
            health = m.group(1).lower()
    result["overall_health"] = health

    # Parse SMART ID# attributes table
    # Lines look like:
    #   5 Reallocated_Sector_Ct   0x0033   100   100   010    Pre-fail  Always       -      0
    # We look for lines with known attribute names
    attr_patterns = {
        "reallocated_sector_count": r"Reallocated_Sector_Ct",
        "power_on_hours": r"Power_On_Hours",
        "temperature": r"Temperature_Celsius",
        "pending_sectors": r"Current_Pending_Sector",
        "offline_uncorrectable": r"Offline_Uncorrectable",
        "raw_read_error_rate": r"Raw_Read_Error_Rate",
        "reallocated_event_count": r"Reallocated_Event_Count",
    }

    for key, pattern in attr_patterns.items():
        for line in stdout.split("\n"):
            if pattern in line:
                parts = line.strip().split()
                if len(parts) >= 10:
                    raw_val = _parse_attr_raw(parts[9])
                    if raw_val is not None:
                        result[key] = raw_val
                    # Also grab the normalized value (column 3 or 4 depending on format)
                    # smartctl -a format: ID# ATTRIBUTE_NAME FLAG VALUE WORST THRESH TYPE UPDATED WHEN_FAILED RAW_VALUE
                    # VALUE is index 3 (0-indexed), so column 4 in 1-indexed
                    if len(parts) >= 4:
                        try:
                            result[f"{key}_normalized"] = int(parts[3])
                        except (ValueError, IndexError):
                            pass
                break

    return result


def _parse_attr_raw(raw: str) -> Optional[int]:
    """Parse a SMART RAW_VALUE string to int.

    Some SMART values have hex or multi-value formats like '100' or '100 (avg 50)'.
    We take the first integer we can parse.
    """
    if not raw:
        return None
    # Handle hex prefixes
    if raw.startswith("0x") or raw.startswith("0X"):
        try:
            return int(raw, 16)
        except ValueError:
            return None
    # Handle "123 (avg 45)" style
    raw = raw.split()[0]
    # Handle things like "100h" or "100m"
    raw = raw.rstrip("hm")
    try:
        return int(raw)
    except ValueError:
        return None
