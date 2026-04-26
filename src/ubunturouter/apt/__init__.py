"""APT Sources Manager — manage APT software sources for UbuntuRouter

Provides source listing, add/remove, mirror switching, and apt update.
Operates on /etc/apt/sources.list and /etc/apt/sources.list.d/.
"""

import logging
import os
import re
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────
SOURCES_LIST = Path("/etc/apt/sources.list")
SOURCES_D_DIR = Path("/etc/apt/sources.list.d")
BACKUP_DIR = Path("/etc/ubunturouter/backups/apt")

# Predefined mirror maps for popular Ubuntu mirrors
# Key: short name, Value: (display_name, base_url)
MIRRORS = {
    "archive.ubuntu.com": ("Official (US)", "http://archive.ubuntu.com/ubuntu/"),
    "mirrors.tuna.tsinghua.edu.cn": ("Tsinghua (China)", "https://mirrors.tuna.tsinghua.edu.cn/ubuntu/"),
    "mirrors.aliyun.com": ("Aliyun (China)", "https://mirrors.aliyun.com/ubuntu/"),
    "mirrors.ustc.edu.cn": ("USTC (China)", "https://mirrors.ustc.edu.cn/ubuntu/"),
    "mirrors.huaweicloud.com": ("Huawei Cloud (China)", "https://mirrors.huaweicloud.com/ubuntu/"),
    "mirrors.zju.edu.cn": ("ZJU (China)", "https://mirrors.zju.edu.cn/ubuntu/"),
}


class APTManager:
    """Manage APT software sources and updates."""

    def __init__(self):
        self._backup_dir = BACKUP_DIR

    # ─── Ubuntu Version Detection ─────────────────────────────────

    @staticmethod
    def _get_ubuntu_codename() -> Optional[str]:
        """Detect Ubuntu version codename (e.g. 'noble', 'jammy')."""
        try:
            r = subprocess.run(
                ["lsb_release", "-sc"],
                capture_output=True, text=True, timeout=5,
            )
            codename = r.stdout.strip()
            if codename:
                return codename
        except Exception:
            pass
        # Fallback: read /etc/os-release
        try:
            data = Path("/etc/os-release").read_text()
            for line in data.split("\n"):
                if line.startswith("VERSION_CODENAME="):
                    return line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass
        return None

    # ─── Backup ───────────────────────────────────────────────────

    def _backup(self) -> Optional[Path]:
        """Backup all APT source files before modification."""
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self._backup_dir / f"sources_backup_{ts}"
        backup_path.mkdir(parents=True, exist_ok=True)

        try:
            if SOURCES_LIST.exists():
                shutil.copy2(SOURCES_LIST, backup_path / "sources.list")
            for f in SOURCES_D_DIR.glob("*.list"):
                if f.is_file():
                    shutil.copy2(f, backup_path / f.name)
            return backup_path
        except Exception as e:
            logger.error("Failed to backup APT sources: %s", e)
            return None

    # ─── List Sources ─────────────────────────────────────────────

    def list_sources(self) -> list:
        """List all APT sources with their details."""
        sources = []

        # Read main sources.list
        if SOURCES_LIST.exists():
            try:
                content = SOURCES_LIST.read_text(encoding="utf-8")
                for line in content.split("\n"):
                    parsed = self._parse_source_line(line)
                    if parsed:
                        parsed["file"] = "sources.list"
                        sources.append(parsed)
            except Exception as e:
                logger.error("Error reading %s: %s", SOURCES_LIST, e)

        # Read sources.list.d files
        if SOURCES_D_DIR.exists():
            for f in sorted(SOURCES_D_DIR.glob("*.list")):
                try:
                    content = f.read_text(encoding="utf-8")
                    for line in content.split("\n"):
                        parsed = self._parse_source_line(line)
                        if parsed:
                            parsed["file"] = f.name
                            sources.append(parsed)
                except Exception as e:
                    logger.error("Error reading %s: %s", f, e)

        return sources

    @staticmethod
    def _parse_source_line(line: str) -> Optional[dict]:
        """Parse a single APT sources line."""
        line = line.strip()
        if not line or line.startswith("#"):
            return None

        # Match: deb [option1=val1 option2=val2] uri distribution [component1 component2]
        # Also match: deb uri distribution [component1 component2]
        parts = line.split()
        if len(parts) < 3:
            return None

        entry = {
            "type": parts[0],  # deb or deb-src
            "uri": "",
            "distribution": "",
            "components": [],
            "options": {},
            "raw": line,
            "disabled": line.startswith("#"),
        }

        idx = 1
        # Check for options bracket
        if parts[idx].startswith("["):
            opts_str = parts[idx].strip("[]")
            for opt in opts_str.split():
                if "=" in opt:
                    k, v = opt.split("=", 1)
                    entry["options"][k] = v
            idx += 1

        if idx < len(parts):
            entry["uri"] = parts[idx]
            idx += 1

        if idx < len(parts):
            entry["distribution"] = parts[idx]
            idx += 1

        if idx < len(parts):
            entry["components"] = parts[idx:]

        return entry

    # ─── Add/Remove Sources ───────────────────────────────────────

    def add_source(self, line: str) -> dict:
        """Add a new APT source line to sources.list.d/."""
        parsed = self._parse_source_line(line)
        if not parsed:
            return {"success": False, "message": "Invalid sources.list line format"}

        self._backup()
        codename = self._get_ubuntu_codename()
        # Replace {codename} placeholder if present
        line = line.replace("{codename}", codename or "noble")

        # Sanitize filename from URI
        from urllib.parse import urlparse
        try:
            parsed_uri = urlparse(parsed["uri"])
            filename = f"ubunturouter-{parsed_uri.hostname or 'custom'}.list"
        except Exception:
            filename = "ubunturouter-custom.list"

        filepath = SOURCES_D_DIR / filename
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            return {"success": True, "message": f"Added source to {filename}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def remove_source(self, uri: str) -> dict:
        """Remove all lines matching a given URI from sources files."""
        self._backup()
        removed = 0

        for file_path in [SOURCES_LIST] + list(sorted(SOURCES_D_DIR.glob("*.list"))):
            if not file_path.exists():
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.split("\n")
                new_lines = []
                for line in lines:
                    if uri in line:
                        removed += 1
                    else:
                        new_lines.append(line)
                file_path.write_text("\n".join(new_lines), encoding="utf-8")
            except Exception as e:
                logger.error("Error modifying %s: %s", file_path, e)

        if removed > 0:
            return {"success": True, "message": f"Removed {removed} line(s)"}
        else:
            return {"success": False, "message": f"No sources matching '{uri}' found"}

    # ─── Mirror Switching ─────────────────────────────────────────

    def switch_mirror(self, mirror_key: str) -> dict:
        """Switch all primary Ubuntu sources to a different mirror."""
        if mirror_key not in MIRRORS:
            return {"success": False, "message": f"Unknown mirror: {mirror_key}. Available: {list(MIRRORS.keys())}"}

        codename = self._get_ubuntu_codename()
        if not codename:
            return {"success": False, "message": "Could not detect Ubuntu codename"}

        new_base = MIRRORS[mirror_key][1]
        self._backup()

        # Replace main sources.list with mirror content
        new_content = f"""# UbuntuRouter - APT sources (mirror: {mirror_key})
deb {new_base} {codename} main restricted universe multiverse
deb {new_base} {codename}-updates main restricted universe multiverse
deb {new_base} {codename}-backports main restricted universe multiverse
deb {new_base} {codename}-security main restricted universe multiverse

# Source packages
deb-src {new_base} {codename} main restricted universe multiverse
deb-src {new_base} {codename}-updates main restricted universe multiverse
deb-src {new_base} {codename}-backports main restricted universe multiverse
deb-src {new_base} {codename}-security main restricted universe multiverse
"""
        try:
            SOURCES_LIST.write_text(new_content, encoding="utf-8")
        except PermissionError:
            # Try with sudo
            import tempfile
            tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8")
            tmp.write(new_content)
            tmp.close()
            r = subprocess.run(
                ["sudo", "cp", tmp.name, str(SOURCES_LIST)],
                capture_output=True, text=True, timeout=10,
            )
            os.unlink(tmp.name)
            if r.returncode != 0:
                return {"success": False, "message": f"Failed to write sources.list: {r.stderr}"}

        return {
            "success": True,
            "message": f"Switched to {MIRRORS[mirror_key][0]}",
            "mirror": mirror_key,
            "codename": codename,
        }

    def get_mirrors(self) -> list:
        """Get list of available mirrors."""
        current_mirror = self._detect_current_mirror()
        result = []
        for key, (display, url) in MIRRORS.items():
            result.append({
                "key": key,
                "display": display,
                "url": url,
                "active": key == current_mirror,
            })
        return result

    def _detect_current_mirror(self) -> Optional[str]:
        """Detect which mirror is currently configured in sources.list."""
        if not SOURCES_LIST.exists():
            return None
        try:
            content = SOURCES_LIST.read_text(encoding="utf-8")
            for key, (_, url) in MIRRORS.items():
                if url.rstrip("/") in content or key in content:
                    return key
        except Exception:
            pass
        return None

    # ─── apt update ───────────────────────────────────────────────

    def run_update(self) -> dict:
        """Run apt update and return results."""
        try:
            r = subprocess.run(
                ["apt-get", "update", "-qq"],
                capture_output=True, text=True, timeout=300,
            )
            return {
                "success": r.returncode == 0,
                "returncode": r.returncode,
                "stdout": r.stdout.strip().split("\n")[-20:],  # Last 20 lines
                "stderr": r.stderr.strip().split("\n")[-20:],
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "message": "apt update timed out after 300s"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ─── Status ───────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Get APT source management status."""
        sources = self.list_sources()
        current_mirror = self._detect_current_mirror()

        # Get last update time from /var/log/apt/
        last_update = None
        apt_hist = Path("/var/log/apt/history.log")
        if apt_hist.exists():
            try:
                for line in reversed(apt_hist.read_text().split("\n")):
                    m = re.match(r"Start-Date:\s+(.+)", line)
                    if m:
                        last_update = m.group(1).strip()
                        break
            except Exception:
                pass

        return {
            "total_sources": len(sources),
            "current_mirror": current_mirror,
            "current_mirror_display": MIRRORS.get(current_mirror, ["Unknown"])[0] if current_mirror else "Unknown",
            "active_sources": sum(1 for s in sources if not s.get("disabled")),
            "codename": self._get_ubuntu_codename(),
            "last_update": last_update,
        }
