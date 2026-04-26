"""DDNSTO provider — free DDNS via ddnsto.com API.

Uses an API token for authentication. Supports multiple subdomains
under a registered domain on ddnsto.com.
"""

from typing import Optional
import requests

from .base import BaseDDNSProvider


class DDNSTOProvider(BaseDDNSProvider):
    """DDNSTO DDNS provider (https://www.ddnsto.com)."""

    PROVIDER_NAME = "DDNSTO"
    PROVIDER_DESCRIPTION = "DDNSTO.com — free DDNS with API token"
    PARAMETER_SCHEMA = [
        {
            "name": "token",
            "label": "API Token",
            "type": "password",
            "required": True,
            "description": "DDNSTO API token",
        },
    ]

    API_BASE = "https://api.ddnsto.com/v1"

    def get_current_ip(self) -> Optional[str]:
        """Get public IP from ddnsto's IP detection endpoint."""
        try:
            r = requests.get(f"{self.API_BASE}/ip", timeout=10)
            r.raise_for_status()
            data = r.json()
            return data.get("ip")
        except Exception:
            return None

    def get_dns_record_ip(self, record: dict) -> Optional[str]:
        """Resolve the configured subdomain via DNS lookup."""
        import socket
        domain = record.get("domain", "")
        subdomain = record.get("subdomain", "")
        fqdn = f"{subdomain}.{domain}" if subdomain else domain
        try:
            return socket.gethostbyname(fqdn)
        except Exception:
            return None

    def update_record(self, record: dict, ip: str) -> bool:
        """Update DDNSTO record with the given IP."""
        token = self.config.get("token", "")
        if not token:
            return False

        domain = record.get("domain", "")
        subdomain = record.get("subdomain", "")
        try:
            r = requests.put(
                f"{self.API_BASE}/dns/update",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "domain": domain,
                    "subdomain": subdomain,
                    "ip": ip,
                },
                timeout=15,
            )
            return r.status_code == 200
        except Exception:
            return False
