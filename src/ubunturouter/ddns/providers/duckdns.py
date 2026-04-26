"""DuckDNS provider — free DDNS via HTTP GET API.

DuckDNS uses a simple GET-based update API. Supports updating
a single IPv4 address for a subdomain on duckdns.org.
"""

import socket
from typing import Optional
import requests

from .base import BaseDDNSProvider


class DuckDNSProvider(BaseDDNSProvider):
    """DuckDNS DDNS provider (https://www.duckdns.org)."""

    PROVIDER_NAME = "DuckDNS"
    PROVIDER_DESCRIPTION = "DuckDNS.org — free DDNS via HTTP GET API"
    PARAMETER_SCHEMA = [
        {
            "name": "token",
            "label": "Token",
            "type": "password",
            "required": True,
            "description": "DuckDNS token (from duckdns.org)",
        },
    ]

    API_BASE = "https://www.duckdns.org"

    def get_current_ip(self) -> Optional[str]:
        """Get public IP from DuckDNS's IP detection."""
        try:
            r = requests.get(f"{self.API_BASE}/ip", timeout=10)
            if r.status_code == 200:
                ip = r.text.strip()
                if ip:
                    return ip
            # Fallback
            r = requests.get("https://api.ipify.org?format=json", timeout=10)
            r.raise_for_status()
            return r.json().get("ip")
        except Exception:
            return None

    def get_dns_record_ip(self, record: dict) -> Optional[str]:
        """Resolve the subdomain.duckdns.org via DNS."""
        subdomain = record.get("subdomain", "")
        if not subdomain:
            return None
        fqdn = f"{subdomain}.duckdns.org"
        try:
            return socket.gethostbyname(fqdn)
        except Exception:
            return None

    def update_record(self, record: dict, ip: str) -> bool:
        """Update DuckDNS record via GET API."""
        token = self.config.get("token", "")
        subdomain = record.get("subdomain", "")
        if not token or not subdomain:
            return False

        try:
            r = requests.get(
                f"{self.API_BASE}/update",
                params={
                    "domains": subdomain,
                    "token": token,
                    "ip": ip,
                    "verbose": "true",
                },
                timeout=15,
            )
            return r.status_code == 200 and r.text.strip().startswith("OK")
        except Exception:
            return False
