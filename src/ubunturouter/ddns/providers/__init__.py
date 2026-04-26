"""DDNS providers - provider auto-detection and factory"""

from .base import BaseDDNSProvider
from .ddnsto import DDNSTOProvider
from .cloudflare import CloudflareProvider
from .alidns import AlidnsProvider
from .dnspod import DnspodProvider
from .duckdns import DuckDNSProvider

_providers: dict[str, type[BaseDDNSProvider]] = {
    "ddnsto": DDNSTOProvider,
    "cloudflare": CloudflareProvider,
    "alidns": AlidnsProvider,
    "dnspod": DnspodProvider,
    "duckdns": DuckDNSProvider,
}


def get_provider(provider_type: str, config: dict) -> BaseDDNSProvider:
    """Get a provider instance by type name."""
    cls = _providers.get(provider_type)
    if not cls:
        raise ValueError(f"Unknown DDNS provider type: {provider_type}")
    return cls(config)


def list_providers() -> list[dict]:
    """List all available provider types with their parameter schemas."""
    result = []
    for ptype, cls in _providers.items():
        result.append({
            "type": ptype,
            "name": cls.PROVIDER_NAME,
            "description": cls.PROVIDER_DESCRIPTION,
            "schema": cls.PARAMETER_SCHEMA,
        })
    return result
