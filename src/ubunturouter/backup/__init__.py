"""System Backup Manager — configuration backup and restore

Creates tar.gz archives of system configuration, supports restore with
preview, and keeps a history of backups.
"""

import datetime
import json
import logging
import os
import subprocess
import tarfile
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────
BACKUP_DIR = Path("/etc/ubunturouter/backups")
BACKUP_META_FILE = "backup_manifest.json"

# Directories and files to include in backup
BACKUP_SOURCES = [
    Path("/etc/ubunturouter"),
    Path("/etc/dnsmasq.d"),
    Path("/etc/netplan"),
    Path("/etc/ppp/peers/ubunturouter"),
]

BACKUP_FILE_PATTERNS = [
    "*.yaml",
    "*.yml",
    "*.conf",
    "*.list",
    "*.rules",
    "*.json",
]

# Exclude patterns
EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "node_modules",
    ".git",
    "backups",  # Don't backup the backups directory itself
]


class BackupManager:
    """Manage system configuration backups."""

    def __init__(self):
        self._backup_dir = BACKUP_DIR
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self._backup_dir / BACKUP_META_FILE

    # ─── Manifest ────────────────────────────────────────────────

    def _load_manifest(self) -> dict:
        """Load backup manifest from disk."""
        if not self._manifest_path.exists():
            return {"backups": []}
        try:
            return json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load backup manifest: %s", e)
            return {"backups": []}

    def _save_manifest(self, manifest: dict):
        """Save backup manifest."""
        self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._manifest_path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self._manifest_path)
        except OSError as e:
            logger.error("Failed to save manifest: %s", e)
            raise

    def _add_to_manifest(self, entry: dict):
        """Add a backup entry to the manifest."""
        manifest = self._load_manifest()
        manifest["backups"].insert(0, entry)  # Newest first
        # Keep max 50 entries
        manifest["backups"] = manifest["backups"][:50]
        self._save_manifest(manifest)

    # ─── Create Backup ───────────────────────────────────────────

    def create_backup(self, description: str = "") -> dict:
        """Create a full configuration backup as tar.gz.

        Collects all configuration files from known locations
        and packages them into a compressed archive.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"backup_{timestamp}"
        filename = f"{backup_id}.tar.gz"
        filepath = self._backup_dir / filename

        # Count collected files
        collected = []
        total_size = 0

        try:
            with tarfile.open(filepath, "w:gz") as tar:
                # Add ubunturouter config directory
                config_dir = Path("/etc/ubunturouter")
                if config_dir.exists():
                    for f in config_dir.rglob("*"):
                        if f.is_file() and not any(f.match(p) for p in EXCLUDE_PATTERNS):
                            # Skip backups dir
                            if "backups" in f.parts:
                                continue
                            try:
                                arcname = f"etc/ubunturouter/{f.relative_to(config_dir)}"
                                tar.add(f, arcname=arcname)
                                collected.append(str(arcname))
                                total_size += f.stat().st_size
                            except (ValueError, OSError):
                                pass

                # Add dnsmasq config
                dnsmasq_dir = Path("/etc/dnsmasq.d")
                if dnsmasq_dir.exists():
                    for f in dnsmasq_dir.glob("*.conf"):
                        if f.is_file():
                            try:
                                arcname = f"etc/dnsmasq.d/{f.name}"
                                tar.add(f, arcname=arcname)
                                collected.append(str(arcname))
                                total_size += f.stat().st_size
                            except OSError:
                                pass

                # Add netplan config
                netplan_dir = Path("/etc/netplan")
                if netplan_dir.exists():
                    for f in netplan_dir.glob("*.yaml"):
                        if f.is_file():
                            try:
                                arcname = f"etc/netplan/{f.name}"
                                tar.add(f, arcname=arcname)
                                collected.append(str(arcname))
                                total_size += f.stat().st_size
                            except OSError:
                                pass

                # Add PPP peers config
                peers_file = Path("/etc/ppp/peers/ubunturouter")
                if peers_file.exists():
                    try:
                        tar.add(peers_file, arcname="etc/ppp/peers/ubunturouter")
                        collected.append("etc/ppp/peers/ubunturouter")
                        total_size += peers_file.stat().st_size
                    except OSError:
                        pass

                # Add system info file
                info = self._collect_system_info()
                info_bytes = json.dumps(info, indent=2).encode("utf-8")
                info_buf = BytesIO(info_bytes)
                info_tar = tarfile.TarInfo(name="system_info.json")
                info_tar.size = len(info_bytes)
                tar.addfile(info_tar, info_buf)

            # Get file size
            archive_size = filepath.stat().st_size

            # Add to manifest
            entry = {
                "id": backup_id,
                "filename": filename,
                "description": description or f"Auto backup {timestamp}",
                "created_at": timestamp,
                "timestamp": time.time(),
                "file_size_bytes": archive_size,
                "file_count": len(collected),
                "total_config_size_bytes": total_size,
            }
            self._add_to_manifest(entry)

            return {
                "success": True,
                "backup": entry,
                "message": f"Backup created: {filename} ({archive_size} bytes, {len(collected)} files)",
            }

        except Exception as e:
            logger.error("Backup creation failed: %s", e)
            # Clean up partial file
            if filepath.exists():
                filepath.unlink()
            return {"success": False, "message": str(e)}

    def _collect_system_info(self) -> dict:
        """Collect system information to include in backup."""
        info = {"timestamp": time.time(), "hostname": "", "os": "", "kernel": ""}
        try:
            r = subprocess.run(["hostname"], capture_output=True, text=True, timeout=5)
            info["hostname"] = r.stdout.strip()
        except Exception:
            pass
        try:
            r = subprocess.run(["lsb_release", "-ds"], capture_output=True, text=True, timeout=5)
            info["os"] = r.stdout.strip()
        except Exception:
            pass
        try:
            r = subprocess.run(["uname", "-r"], capture_output=True, text=True, timeout=5)
            info["kernel"] = r.stdout.strip()
        except Exception:
            pass
        return info

    # ─── List Backups ────────────────────────────────────────────

    def list_backups(self) -> dict:
        """List all available backups."""
        manifest = self._load_manifest()
        backups = manifest.get("backups", [])

        # Verify files still exist
        valid_backups = []
        for b in backups:
            fp = self._backup_dir / b.get("filename", "")
            if fp.exists():
                valid_backups.append(b)
            else:
                logger.warning("Backup file missing: %s", fp)

        return {"backups": valid_backups, "count": len(valid_backups), "backup_dir": str(self._backup_dir)}

    # ─── Delete Backup ───────────────────────────────────────────

    def delete_backup(self, backup_id: str) -> dict:
        """Delete a backup by ID."""
        manifest = self._load_manifest()
        backups = manifest.get("backups", [])
        found = None

        for b in backups:
            if b.get("id") == backup_id:
                found = b
                break

        if not found:
            return {"success": False, "message": f"Backup {backup_id} not found"}

        # Delete the file
        fp = self._backup_dir / found.get("filename", "")
        if fp.exists():
            try:
                fp.unlink()
            except OSError as e:
                return {"success": False, "message": str(e)}

        # Update manifest
        manifest["backups"] = [b for b in backups if b.get("id") != backup_id]
        self._save_manifest(manifest)

        return {"success": True, "message": f"Backup {backup_id} deleted"}

    # ─── Download Backup ─────────────────────────────────────────

    def get_backup_path(self, backup_id: str) -> Optional[Path]:
        """Get the file path for a backup by ID."""
        manifest = self._load_manifest()
        for b in manifest.get("backups", []):
            if b.get("id") == backup_id:
                fp = self._backup_dir / b.get("filename", "")
                if fp.exists():
                    return fp
        return None

    def get_backup_content(self, backup_id: str) -> Optional[bytes]:
        """Get the raw bytes of a backup archive."""
        fp = self.get_backup_path(backup_id)
        if fp:
            return fp.read_bytes()
        return None

    # ─── Restore ─────────────────────────────────────────────────

    def preview_restore(self, backup_id: str) -> dict:
        """Preview what would be restored from a backup."""
        fp = self.get_backup_path(backup_id)
        if not fp:
            return {"success": False, "message": f"Backup {backup_id} not found"}

        files = []
        try:
            with tarfile.open(fp, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        files.append({
                            "path": member.name,
                            "size": member.size,
                            "mtime": member.mtime,
                        })
            return {"success": True, "files": files, "count": len(files)}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def restore_backup(self, backup_id: str) -> dict:
        """Restore configuration from a backup file.

        Creates a current-state backup first, then extracts the
        backup archive to restore system configuration.
        """
        # Create safety backup first
        safety = self.create_backup(description=f"Pre-restore safety backup (restoring {backup_id})")
        if not safety.get("success"):
            return {"success": False, "message": f"Failed to create safety backup: {safety.get('message')}"}

        fp = self.get_backup_path(backup_id)
        if not fp:
            return {"success": False, "message": f"Backup {backup_id} not found"}

        restored_count = 0
        errors = []

        try:
            with tarfile.open(fp, "r:gz") as tar:
                for member in tar.getmembers():
                    if not member.isfile():
                        continue

                    # Map archive path to filesystem path
                    if member.name.startswith("etc/"):
                        dest = Path(f"/{member.name}")
                    else:
                        continue

                    try:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        tar.extract(member, dest.parent)
                        restored_count += 1
                    except Exception as e:
                        errors.append(f"{member.name}: {e}")

            return {
                "success": True,
                "restored_count": restored_count,
                "errors": errors,
                "error_count": len(errors),
                "safety_backup_id": safety.get("backup", {}).get("id"),
                "message": f"Restored {restored_count} files with {len(errors)} errors",
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
