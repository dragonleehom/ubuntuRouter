"""Base DDNS provider — abstract interface for all providers."""

from abc import ABC, abstractmethod
from typing import Optional


class BaseDDNSProvider(ABC):
    """Abstract base class for DDNS providers.

    Each provider implements the three core methods for detecting
    the current public IP, resolving the current DNS record, and
    updating the record.
    """

    PROVIDER_NAME: str = ""
    PROVIDER_DESCRIPTION: str = ""
    PARAMETER_SCHEMA: list[dict] = []

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def get_current_ip(self) -> Optional[str]:
        """Check the current public IP of this router."""
        ...

    @abstractmethod
    def get_dns_record_ip(self, record: dict) -> Optional[str]:
        """Resolve the current DNS record's IP address."""
        ...

    @abstractmethod
    def update_record(self, record: dict, ip: str) -> bool:
        """Update the DNS record to point to the given IP."""
        ...

    def update(self, record: dict) -> bool:
        """Convenience: check current IP and update if needed.

        Returns True if an update was performed (IP changed), False
        if no update was needed (same IP).
        """
        current_ip = self.get_current_ip()
        if not current_ip:
            return False

        dns_ip = self.get_dns_record_ip(record)
        if dns_ip == current_ip:
            return False

        return self.update_record(record, current_ip)
