"""SambaManager — Samba share and user management via smb.conf + systemctl + smbpasswd"""

import configparser
import os
import re
import subprocess

SMBCONF = "/etc/samba/smb.conf"
SMBCONF_BAK = "/etc/samba/smb.conf.bak"
SERVICES = ["smbd", "nmbd"]

_SHARE_NAME_RE = re.compile(r"^[a-z0-9\-]+$")


# ─── helpers ──────────────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    """Run a command with timeout; raises on non-zero returncode or exception."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _systemctl(action: str, *units: str) -> dict:
    """systemctl <action> <units...> with sudo."""
    results = {}
    for unit in units:
        try:
            r = _run(["sudo", "systemctl", action, unit])
            if r.returncode == 0:
                results[unit] = "ok"
            else:
                results[unit] = r.stderr.strip() or f"return code {r.returncode}"
        except subprocess.TimeoutExpired:
            results[unit] = "timeout"
        except FileNotFoundError:
            results[unit] = "systemctl not found"
    success = all(v == "ok" for v in results.values())
    return {"success": success, "results": results}


def _check_samba_installed() -> bool:
    """Check if smbd binary exists."""
    try:
        subprocess.run(["which", "smbd"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def _check_config_exists() -> bool:
    return os.path.exists(SMBCONF)


def _read_config() -> configparser.RawConfigParser:
    """Read smb.conf with RawConfigParser."""
    config = configparser.RawConfigParser()
    config.optionxform = str  # preserve case of keys
    if not _check_config_exists():
        # Return empty config
        config.add_section("global")
        config.set("global", "workgroup", "WORKGROUP")
        config.set("global", "server string", "%h")
        config.set("global", "security", "user")
        config.set("global", "map to guest", "Bad User")
        return config
    try:
        # RawConfigParser uses the INI format which is close enough to smb.conf
        # We read with empty lines allowed
        with open(SMBCONF, "r") as f:
            content = f.read()
        config.read_string(content)
    except configparser.MissingSectionHeaderError:
        # smb.conf may have initial comments without a section header;
        # prepend a dummy header if needed
        with open(SMBCONF, "r") as f:
            content = f.read()
        content = "[_preamble_]\n" + content
        config.read_string(content)
        # Remove the preamble section — it was just for parsing
        if config.has_section("_preamble_"):
            config.remove_section("_preamble_")
    except Exception as e:
        raise RuntimeError(f"Failed to parse {SMBCONF}: {e}")

    if not config.has_section("global"):
        config.add_section("global")
        config.set("global", "workgroup", "WORKGROUP")
        config.set("global", "server string", "%h")
        config.set("global", "security", "user")
        config.set("global", "map to guest", "Bad User")

    return config


def _write_config(config: configparser.RawConfigParser) -> None:
    """Write config to smb.conf, preserving section ordering.

    Uses sudo tee to handle root-owned config file.
    """
    # Backup original first
    if os.path.exists(SMBCONF):
        try:
            subprocess.run(["sudo", "cp", SMBCONF, SMBCONF_BAK], capture_output=True, timeout=10)
        except Exception:
            pass  # best-effort backup

    lines = []
    for i, section in enumerate(config.sections()):
        if i > 0:
            lines.append("")
        lines.append(f"[{section}]")
        for key, value in config.items(section):
            lines.append(f"    {key} = {value}")
    content = "\n".join(lines) + "\n"

    try:
        proc = subprocess.run(
            ["sudo", "tee", SMBCONF],
            input=content,
            capture_output=True, text=True, timeout=10
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to write {SMBCONF}: {proc.stderr.strip()}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timeout writing {SMBCONF}")
    except FileNotFoundError:
        raise RuntimeError("sudo not found")


def _testparm() -> dict:
    """Run testparm -s to validate the current smb.conf."""
    try:
        r = _run(["sudo", "testparm", "-s"], timeout=15)
        if r.returncode == 0:
            return {"success": True, "message": r.stderr.strip() or "config is valid"}
        else:
            return {"success": False, "message": r.stderr.strip() or r.stdout.strip() or "validation failed"}
    except FileNotFoundError:
        return {"success": False, "message": "testparm not found (samba-common-bin not installed?)"}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "testparm timed out"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def _restore_backup() -> bool:
    """Restore smb.conf from backup using sudo cp."""
    if not os.path.exists(SMBCONF_BAK):
        return False
    try:
        subprocess.run(["sudo", "cp", SMBCONF_BAK, SMBCONF], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


# ─── SambaManager ─────────────────────────────────────────────────────────

class SambaManager:
    """Manage Samba service, shares, and users."""

    CONFIG_PATH = SMBCONF

    # ── Service Control ────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return Samba service status + smbstatus output + config summary."""
        if not _check_samba_installed():
            return {
                "installed": False,
                "message": "Samba is not installed (smbd not found)",
            }

        services = {}
        for svc in SERVICES:
            try:
                r = _run(["systemctl", "is-active", svc])
                services[svc] = r.stdout.strip()
            except Exception:
                services[svc] = "unknown"

        # smbstatus
        smbstatus_output = ""
        try:
            r = _run(["sudo", "smbstatus"], timeout=15)
            if r.returncode == 0:
                smbstatus_output = r.stdout
        except Exception:
            pass

        # Config summary
        config_summary = {}
        try:
            config = _read_config()
            for section in config.sections():
                if section == "global":
                    config_summary["global"] = dict(config.items(section))
                else:
                    if "shares" not in config_summary:
                        config_summary["shares"] = {}
                    config_summary["shares"][section] = dict(config.items(section))
        except Exception as e:
            config_summary = {"error": str(e)}

        return {
            "installed": True,
            "services": services,
            "all_running": all(v == "active" for v in services.values()),
            "smbstatus": smbstatus_output,
            "config": config_summary,
        }

    def start(self) -> dict:
        """systemctl start smbd nmbd."""
        return _systemctl("start", *SERVICES)

    def stop(self) -> dict:
        """systemctl stop smbd nmbd."""
        return _systemctl("stop", *SERVICES)

    def restart(self) -> dict:
        """systemctl restart smbd nmbd."""
        return _systemctl("restart", *SERVICES)

    # ── Share Management ───────────────────────────────────────────────

    def list_shares(self) -> list:
        """Parse smb.conf and return list of share dicts."""
        if not _check_config_exists():
            return []
        try:
            config = _read_config()
        except RuntimeError:
            return []

        shares = []
        for section in config.sections():
            if section == "global":
                continue
            share = {
                "name": section,
                "path": config.get(section, "path", fallback=""),
                "writable": config.get(section, "writable", fallback="no"),
                "guest_ok": config.get(section, "guest ok", fallback="no"),
                "valid_users": config.get(section, "valid users", fallback=""),
                "browsable": config.get(section, "browsable", fallback="yes"),
            }
            # Normalize booleans
            for key in ("writable", "guest_ok", "browsable"):
                raw = share[key]
                share[key] = raw.lower() in ("yes", "true", "1") if raw else False
            shares.append(share)
        return shares

    def add_share(self, name: str, path: str, writable: bool = True,
                  guest_ok: bool = False, valid_users: str = "") -> dict:
        """Add a new Samba share section."""
        if not _check_samba_installed():
            return {"success": False, "message": "Samba is not installed"}

        name = name.strip().lower()
        if not _SHARE_NAME_RE.match(name):
            return {
                "success": False,
                "message": f"Invalid share name '{name}': only lowercase letters, numbers, and hyphens allowed",
            }
        if not path:
            return {"success": False, "message": "Path is required"}

        config = _read_config()

        if config.has_section(name):
            return {"success": False, "message": f"Share '{name}' already exists"}

        config.add_section(name)
        config.set(name, "path", path)
        config.set(name, "browsable", "yes")
        config.set(name, "writable", "yes" if writable else "no")
        config.set(name, "guest ok", "yes" if guest_ok else "no")
        if valid_users:
            config.set(name, "valid users", valid_users)

        # Write config and validate
        _write_config(config)
        t = _testparm()
        if not t["success"]:
            # Restore backup
            _restore_backup()
            return {"success": False, "message": f"testparm failed: {t['message']}"}

        # Reload smbd to pick up changes
        try:
            _run(["sudo", "systemctl", "reload", "smbd"], timeout=10)
        except Exception as e:
            return {"success": True, "warning": f"share added but reload failed: {e}", "name": name}

        return {"success": True, "message": f"Share '{name}' added", "name": name}

    def update_share(self, name: str, path: str | None = None,
                     writable: bool | None = None, guest_ok: bool | None = None,
                     valid_users: str | None = None) -> dict:
        """Update an existing share section."""
        name = name.strip().lower()
        if not _check_config_exists():
            return {"success": False, "message": "smb.conf does not exist"}

        config = _read_config()

        if not config.has_section(name):
            return {"success": False, "message": f"Share '{name}' not found"}

        if path is not None:
            config.set(name, "path", path)
        if writable is not None:
            config.set(name, "writable", "yes" if writable else "no")
        if guest_ok is not None:
            config.set(name, "guest ok", "yes" if guest_ok else "no")
        if valid_users is not None:
            if valid_users.strip() == "":
                # Remove the option if it exists
                if config.has_option(name, "valid users"):
                    config.remove_option(name, "valid users")
            else:
                config.set(name, "valid users", valid_users.strip())

        _write_config(config)
        t = _testparm()
        if not t["success"]:
            _restore_backup()
            return {"success": False, "message": f"testparm failed: {t['message']}"}

        try:
            _run(["sudo", "systemctl", "reload", "smbd"], timeout=10)
        except Exception as e:
            return {"success": True, "warning": f"share updated but reload failed: {e}", "name": name}

        return {"success": True, "message": f"Share '{name}' updated", "name": name}

    def delete_share(self, name: str) -> dict:
        """Remove a share section."""
        name = name.strip().lower()
        if not _check_config_exists():
            return {"success": False, "message": "smb.conf does not exist"}

        config = _read_config()

        if not config.has_section(name):
            return {"success": False, "message": f"Share '{name}' not found"}

        config.remove_section(name)
        _write_config(config)
        t = _testparm()
        if not t["success"]:
            _restore_backup()
            return {"success": False, "message": f"testparm failed: {t['message']}"}

        try:
            _run(["sudo", "systemctl", "reload", "smbd"], timeout=10)
        except Exception as e:
            return {"success": True, "warning": f"share deleted but reload failed: {e}", "name": name}

        return {"success": True, "message": f"Share '{name}' deleted", "name": name}

    # ── User Management ────────────────────────────────────────────────

    def list_users(self) -> list:
        """List Samba users from pdbedit output."""
        users = []
        try:
            r = _run(["sudo", "pdbedit", "-L"], timeout=15)
            if r.returncode == 0:
                for line in r.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    # Format: username:uid:Unix uid:fullname:homedir
                    parts = line.split(":")
                    if len(parts) >= 2:
                        users.append({
                            "username": parts[0],
                            "uid": parts[1] if len(parts) > 1 else "",
                            "full_name": parts[3] if len(parts) > 3 else "",
                        })
        except FileNotFoundError:
            pass  # samba not installed
        except Exception:
            pass
        return users

    def add_user(self, username: str, password: str) -> dict:
        """Add a Samba user via smbpasswd."""
        if not _check_samba_installed():
            return {"success": False, "message": "Samba is not installed"}

        if not username.strip():
            return {"success": False, "message": "Username is required"}

        try:
            # smbpasswd -a requires piping the password twice via -s (stdin)
            proc = subprocess.run(
                ["sudo", "smbpasswd", "-a", username.strip()],
                input=f"{password}\n{password}\n",
                capture_output=True, text=True, timeout=15
            )
            if proc.returncode == 0:
                return {"success": True, "message": f"User '{username}' added"}
            else:
                stderr = proc.stderr.strip()
                if "Failed to add entry for user" in stderr:
                    return {"success": False, "message": f"User '{username}' does not exist in system (/etc/passwd). Create the system user first."}
                return {"success": False, "message": stderr or f"smbpasswd returned {proc.returncode}"}
        except subprocess.TimeoutExpired:
            return {"success": False, "message": "smbpasswd timed out"}
        except FileNotFoundError:
            return {"success": False, "message": "smbpasswd not found"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def delete_user(self, username: str) -> dict:
        """Delete a Samba user via smbpasswd -x."""
        if not _check_samba_installed():
            return {"success": False, "message": "Samba is not installed"}

        if not username.strip():
            return {"success": False, "message": "Username is required"}

        try:
            r = _run(["sudo", "smbpasswd", "-x", username.strip()], timeout=15)
            if r.returncode == 0:
                return {"success": True, "message": f"User '{username}' deleted"}
            else:
                return {"success": False, "message": r.stderr.strip() or f"smbpasswd returned {r.returncode}"}
        except subprocess.TimeoutExpired:
            return {"success": False, "message": "smbpasswd timed out"}
        except FileNotFoundError:
            return {"success": False, "message": "smbpasswd not found"}
        except Exception as e:
            return {"success": False, "message": str(e)}


# Convenience alias
samba_manager = SambaManager()
