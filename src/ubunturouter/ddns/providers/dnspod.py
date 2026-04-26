"""DNSPod DDNS provider — Tencent Cloud DNS (DNSPod).

Uses ID and Token for API authentication. Supports A record
updates via the DNSPod HTTP API (v1).
"""

import socket
from typing import Optional
import requests

from .base import BaseDDNSProvider


class DnspodProvider(BaseDDNSProvider):
    """DNSPod / Tencent Cloud DNS DDNS provider."""

    PROVIDER_NAME = "DNSPod"
    PROVIDER_DESCRIPTION = "DNSPod / Tencent Cloud DNS — API ID + Token authentication"
    PARAMETER_SCHEMA = [
        {
            "name": "login_token",
            "label": "Login Token",
            "type": "password",
            "required": True,
            "description": "DNSPod Login Token (format: ID,Token)",
        },
    ]

    API_BASE = "https://dnsapi.cn"

    def _post(self, action: str, data: dict) -> Optional[dict]:
        """Post to DNSPod API."""
        token = self.config.get("login_token", "")
        if not token:
            return None

        data["login_token"] = token
        data["format"] = "json"

        try:
            r = requests.post(
                f"{self.API_BASE}/{action}",
                data=data,
                timeout=15,
                headers={
                    "User-Agent": "UbuntuRouter-DDNS/1.0",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def _get_domain_id(self, domain: str) -> Optional[str]:
        """Get DNSPod domain ID by domain name."""
        result = self._post("Domain.List", {})
        if not result or result.get("status", {}).get("code") != "1":
            return None
        for d in result.get("domains", []):
            if d.get("name") == domain or d.get("domain") == domain:
                return str(d.get("id"))
        return None

    def get_current_ip(self) -> Optional[str]:
        """Get public IP from DNSPod's IP detection."""
        try:
            r = requests.get("https://api.ipify.org?format=json", timeout=10)
            r.raise_for_status()
            return r.json().get("ip")
        except Exception:
            return None

    def get_dns_record_ip(self, record: dict) -> Optional[str]:
        """Resolve the configured subdomain via DNS lookup."""
        domain = record.get("domain", "")
        subdomain = record.get("subdomain", "")
        fqdn = f"{subdomain}.{domain}" if subdomain else domain
        try:
            return socket.gethostbyname(fqdn)
        except Exception:
            return None

    def update_record(self, record: dict, ip: str) -> bool:
        """Update or create a DNSPod A record."""
        domain = record.get("domain", "")
        subdomain = record.get("subdomain", "")

        domain_id = self._get_domain_id(domain)
        if not domain_id:
            return False

        # Record.List to find existing record
        result = self._post("Record.List", {
            "domain_id": domain_id,
            "sub_domain": subdomain,
            "record_type": "A",
        })
        if result is None:
            return False

        records = result.get("records", [])
        existing = [r for r in records if r.get("type") == "A"]

        if existing:
            record_id = existing[0].get("id")
            result2 = self._post("Record.Ddns", {
                "domain_id": domain_id,
                "record_id": record_id,
                "sub_domain": subdomain,
                "value": ip,
                "record_type": "A",
                "record_line": "默认",
            })
        else:
            result2 = self._post("Record.Create", {
                "domain_id": domain_id,
                "sub_domain": subdomain,
                "value": ip,
                "record_type": "A",
                "record_line": "默认",
            })

        if result2 is None:
            return False
        status = result2.get("status", {})
        return status.get("code") == "1"
