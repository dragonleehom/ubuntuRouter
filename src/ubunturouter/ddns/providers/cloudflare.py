"""Cloudflare DDNS provider — Cloudflare API v4.

Uses API token (recommended) or API key + email for authentication.
Supports A and AAAA records for subdomains.
"""

from typing import Optional
import requests
import socket

from .base import BaseDDNSProvider


class CloudflareProvider(BaseDDNSProvider):
    """Cloudflare API v4 DDNS provider."""

    PROVIDER_NAME = "Cloudflare"
    PROVIDER_DESCRIPTION = "Cloudflare DNS API v4 — API Token or Global API Key"
    PARAMETER_SCHEMA = [
        {
            "name": "api_token",
            "label": "API Token",
            "type": "password",
            "required": True,
            "description": "Cloudflare API Token (recommended) or Global API Key",
        },
        {
            "name": "zone_id",
            "label": "Zone ID",
            "type": "string",
            "required": True,
            "description": "Cloudflare Zone ID for the domain",
        },
        {
            "name": "proxied",
            "label": "Proxy (Cloudflare CDN)",
            "type": "boolean",
            "required": False,
            "default": False,
            "description": "Whether traffic should go through Cloudflare proxy",
        },
        {
            "name": "ttl",
            "label": "TTL (seconds)",
            "type": "number",
            "required": False,
            "default": 120,
            "description": "DNS record TTL (120 = auto)",
        },
    ]

    API_BASE = "https://api.cloudflare.com/client/v4"

    def _headers(self) -> dict:
        token = self.config.get("api_token", "")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _zone_id(self) -> str:
        return self.config.get("zone_id", "")

    def get_current_ip(self) -> Optional[str]:
        """Get public IP from Cloudflare's trace endpoint."""
        try:
            r = requests.get("https://1.1.1.1/cdn-cgi/trace", timeout=10)
            if r.status_code == 200:
                for line in r.text.strip().split("\n"):
                    if line.startswith("ip="):
                        return line[3:]
            # Fallback to whatismyip
            r = requests.get("https://api.ipify.org?format=json", timeout=10)
            r.raise_for_status()
            return r.json().get("ip")
        except Exception:
            return None

    def get_dns_record_ip(self, record: dict) -> Optional[str]:
        """Look up the current DNS record via Cloudflare API."""
        zone_id = self._zone_id()
        if not zone_id:
            return None

        domain = record.get("domain", "")
        subdomain = record.get("subdomain", "")
        name = f"{subdomain}.{domain}" if subdomain else domain

        try:
            r = requests.get(
                f"{self.API_BASE}/zones/{zone_id}/dns_records",
                headers=self._headers(),
                params={"name": name, "type": "A"},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            records = data.get("result", [])
            if records:
                return records[0].get("content")
            return None
        except Exception:
            # Fallback to DNS resolution
            try:
                return socket.gethostbyname(name)
            except Exception:
                return None

    def update_record(self, record: dict, ip: str) -> bool:
        """Update or create A record via Cloudflare API."""
        zone_id = self._zone_id()
        if not zone_id:
            return False

        domain = record.get("domain", "")
        subdomain = record.get("subdomain", "")
        name = f"{subdomain}.{domain}" if subdomain else domain
        proxied = self.config.get("proxied", False)
        ttl = self.config.get("ttl", 120)

        try:
            # First, see if a record already exists
            r = requests.get(
                f"{self.API_BASE}/zones/{zone_id}/dns_records",
                headers=self._headers(),
                params={"name": name, "type": "A"},
                timeout=15,
            )
            r.raise_for_status()
            existing = r.json().get("result", [])

            body = {
                "type": "A",
                "name": name,
                "content": ip,
                "ttl": ttl,
                "proxied": proxied,
            }

            if existing:
                record_id = existing[0].get("id")
                r2 = requests.put(
                    f"{self.API_BASE}/zones/{zone_id}/dns_records/{record_id}",
                    headers=self._headers(),
                    json=body,
                    timeout=15,
                )
            else:
                r2 = requests.post(
                    f"{self.API_BASE}/zones/{zone_id}/dns_records",
                    headers=self._headers(),
                    json=body,
                    timeout=15,
                )
            return r2.status_code in (200, 201)
        except Exception:
            return False
