"""Aliyun DNS (Alidns) DDNS provider — Alibaba Cloud DNS API.

Uses AccessKey ID and Secret for authentication. Supports A record
updates for subdomains under a domain managed by Alibaba Cloud DNS.
"""

import socket
from typing import Optional
from hashlib import sha1
import hmac
import base64
import urllib.parse
import time

import requests

from .base import BaseDDNSProvider


class AlidnsProvider(BaseDDNSProvider):
    """Aliyun DNS (Alidns) DDNS provider."""

    PROVIDER_NAME = "Aliyun DNS"
    PROVIDER_DESCRIPTION = "Alibaba Cloud DNS (Alidns) — AccessKey authentication"
    PARAMETER_SCHEMA = [
        {
            "name": "access_key_id",
            "label": "AccessKey ID",
            "type": "string",
            "required": True,
            "description": "Alibaba Cloud AccessKey ID",
        },
        {
            "name": "access_key_secret",
            "label": "AccessKey Secret",
            "type": "password",
            "required": True,
            "description": "Alibaba Cloud AccessKey Secret",
        },
    ]

    API_ENDPOINT = "https://alidns.aliyuncs.com/"

    def _sign(self, params: dict, secret: str) -> str:
        """Generate Aliyun API signature."""
        sorted_params = sorted(params.items())
        canonical = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
            for k, v in sorted_params
        )
        string_to_sign = f"GET&{urllib.parse.quote('/', safe='')}&{urllib.parse.quote(canonical, safe='')}"
        h = hmac.new(
            (secret + "&").encode("utf-8"),
            string_to_sign.encode("utf-8"),
            sha1,
        )
        return base64.b64encode(h.digest()).decode("utf-8")

    def _api_request(self, action: str, params: dict) -> Optional[dict]:
        """Make an Aliyun API request with signature."""
        access_key_id = self.config.get("access_key_id", "")
        access_key_secret = self.config.get("access_key_secret", "")

        if not access_key_id or not access_key_secret:
            return None

        common_params = {
            "Action": action,
            "Format": "JSON",
            "Version": "2015-01-09",
            "AccessKeyId": access_key_id,
            "SignatureMethod": "HMAC-SHA1",
            "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "SignatureVersion": "1.0",
            "SignatureNonce": str(int(time.time() * 1000000)),
        }
        common_params.update(params)
        signature = self._sign(common_params, access_key_secret)
        common_params["Signature"] = signature

        try:
            r = requests.get(
                self.API_ENDPOINT,
                params=common_params,
                timeout=15,
            )
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def get_current_ip(self) -> Optional[str]:
        """Get public IP from ipify."""
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
        """Update or create an Aliyun DNS A record."""
        domain = record.get("domain", "")
        subdomain = record.get("subdomain", "")
        rr = subdomain if subdomain else "@"

        # First, query existing record
        result = self._api_request("DescribeDomainRecords", {
            "DomainName": domain,
            "RRKeyWord": rr,
            "Type": "A",
        })
        if result is None:
            return False

        records = result.get("DomainRecords", {}).get("Record", [])
        existing = [r for r in records if r.get("RR") == rr and r.get("Type") == "A"]

        if existing:
            record_id = existing[0].get("RecordId")
            result2 = self._api_request("UpdateDomainRecord", {
                "RecordId": record_id,
                "RR": rr,
                "Type": "A",
                "Value": ip,
            })
        else:
            result2 = self._api_request("AddDomainRecord", {
                "DomainName": domain,
                "RR": rr,
                "Type": "A",
                "Value": ip,
            })

        return result2 is not None and result2.get("RecordId") is not None
