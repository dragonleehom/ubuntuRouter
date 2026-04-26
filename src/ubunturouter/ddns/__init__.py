"""DDNS Manager — unified entry point for Dynamic DNS management.

Handles configuration storage at /etc/ubunturouter/ddns.yaml.
Supports multiple DDNS records simultaneously with different
providers. Coordinates provider selection and record lifecycle.
"""

import os
import uuid
import yaml
import logging
from pathlib import Path
from typing import Optional

from .providers import get_provider, list_providers

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("/etc/ubunturouter/ddns.yaml")


class DDNSManager:
    """Central DDNS manager for configuration and updates."""

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or DEFAULT_CONFIG_PATH

    # ─── Configuration I/O ─────────────────────────────────────

    def load_config(self) -> dict:
        """Load DDNS configuration from YAML file.

        Returns the config dict. Creates a default empty config
        if the file does not exist.
        """
        if not self._config_path.exists():
            return {"records": []}

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return {"records": []}
            return data
        except (yaml.YAMLError, OSError, PermissionError) as e:
            logger.error("Failed to load DDNS config: %s", e)
            return {"records": []}

    def save_config(self, cfg: dict):
        """Save DDNS configuration to YAML file."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._config_path.with_suffix(".yaml.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, default_flow_style=False, allow_unicode=True)
            tmp_path.replace(self._config_path)
        except (OSError, PermissionError) as e:
            logger.error("Failed to save DDNS config: %s", e)
            raise

    # ─── Record Management ─────────────────────────────────────

    def get_records(self) -> list:
        """Get all configured DDNS records."""
        cfg = self.load_config()
        return cfg.get("records", [])

    def add_record(self, record: dict) -> dict:
        """Add a new DDNS record.

        The record dict must include at minimum:
          - type: provider type (e.g., "cloudflare", "duckdns")
          - domain: domain name
          - subdomain: subdomain (or empty for root)

        Returns the saved record with an auto-generated ID.
        """
        record["id"] = str(uuid.uuid4())
        record.setdefault("enabled", True)
        record.setdefault("subdomain", "")
        record.setdefault("ttl", 120)

        cfg = self.load_config()
        cfg.setdefault("records", [])
        cfg["records"].append(record)
        self.save_config(cfg)
        return record

    def remove_record(self, record_id: str) -> dict:
        """Remove a DDNS record by ID.

        Returns dict with success status and message.
        """
        cfg = self.load_config()
        records = cfg.get("records", [])
        new_records = [r for r in records if r.get("id") != record_id]

        if len(new_records) == len(records):
            return {"success": False, "message": f"Record {record_id} not found"}

        cfg["records"] = new_records
        self.save_config(cfg)
        return {"success": True, "message": "Record removed"}

    def force_update(self, record_id: str) -> dict:
        """Force an immediate update of a specific record.

        Returns dict with success status and details.
        """
        records = self.get_records()
        record = None
        for r in records:
            if r.get("id") == record_id:
                record = r
                break

        if record is None:
            return {"success": False, "message": f"Record {record_id} not found"}

        provider_type = record.get("type", "")
        if not provider_type:
            return {"success": False, "message": "Record has no provider type"}

        try:
            provider = get_provider(provider_type, record)
            current_ip = provider.get_current_ip()
            if not current_ip:
                return {"success": False, "message": "Failed to detect public IP"}

            success = provider.update_record(record, current_ip)
            if success:
                return {
                    "success": True,
                    "message": "Record updated",
                    "ip": current_ip,
                    "provider": provider_type,
                }
            else:
                return {"success": False, "message": "Provider returned failure"}
        except ValueError as e:
            return {"success": False, "message": str(e)}
        except Exception as e:
            logger.exception("Force update failed for record %s", record_id)
            return {"success": False, "message": str(e)}

    def get_providers(self) -> list:
        """List available provider types and their schemas."""
        return list_providers()

    # ─── Bulk Check / Update ──────────────────────────────────

    def check_and_update(self) -> dict:
        """Check all enabled records and update if IP has changed.

        Returns a summary dict with counts of checked/updated/errors.
        """
        records = self.get_records()
        checked = 0
        updated = 0
        errors = 0
        details = []

        for record in records:
            if not record.get("enabled", True):
                continue

            provider_type = record.get("type", "")
            if not provider_type:
                continue

            try:
                provider = get_provider(provider_type, record)
                current_ip = provider.get_current_ip()
                if not current_ip:
                    errors += 1
                    details.append({
                        "id": record.get("id"),
                        "domain": record.get("domain", ""),
                        "subdomain": record.get("subdomain", ""),
                        "status": "error",
                        "message": "Failed to detect public IP",
                    })
                    continue

                dns_ip = provider.get_dns_record_ip(record)
                if dns_ip == current_ip:
                    checked += 1
                    details.append({
                        "id": record.get("id"),
                        "domain": record.get("domain", ""),
                        "subdomain": record.get("subdomain", ""),
                        "status": "unchanged",
                        "ip": current_ip,
                    })
                    continue

                success = provider.update_record(record, current_ip)
                if success:
                    checked += 1
                    updated += 1
                    details.append({
                        "id": record.get("id"),
                        "domain": record.get("domain", ""),
                        "subdomain": record.get("subdomain", ""),
                        "status": "updated",
                        "old_ip": dns_ip or "unknown",
                        "new_ip": current_ip,
                    })
                else:
                    errors += 1
                    details.append({
                        "id": record.get("id"),
                        "domain": record.get("domain", ""),
                        "subdomain": record.get("subdomain", ""),
                        "status": "error",
                        "message": "Update failed",
                    })
            except Exception as e:
                errors += 1
                logger.exception("DDNS check error for record %s", record.get("id"))
                details.append({
                    "id": record.get("id"),
                    "domain": record.get("domain", ""),
                    "subdomain": record.get("subdomain", ""),
                    "status": "error",
                    "message": str(e),
                })

        return {
            "checked": checked,
            "updated": updated,
            "errors": errors,
            "total": len(records),
            "details": details,
        }

    # ─── Status ────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Get current DDNS status summary."""
        records = self.get_records()
        enabled = sum(1 for r in records if r.get("enabled", True))
        return {
            "total_records": len(records),
            "enabled_records": enabled,
            "disabled_records": len(records) - enabled,
            "config_path": str(self._config_path),
        }
