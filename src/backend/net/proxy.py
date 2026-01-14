"""
Proxy configuration for routing scraper/downloader requests through proxy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse


@dataclass
class ProxyConfig:
    """
    Proxy configuration.

    Attributes:
        enabled: Whether proxy is enabled.
        url: Proxy URL (e.g., "http://host:port", "socks5://host:port").
    """
    enabled: bool = False
    url: str = ""

    def is_active(self) -> bool:
        """Check if proxy is enabled and URL is configured."""
        return self.enabled and bool(self.url.strip())

    def get_url(self) -> Optional[str]:
        """Get proxy URL if active, else None."""
        if self.is_active():
            return self.url.strip()
        return None

    def to_persist_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "url": self.url,
        }

    @classmethod
    def from_persist_dict(cls, data: dict[str, Any]) -> "ProxyConfig":
        enabled = bool(data.get("enabled", False))
        url = str(data.get("url", "") or "")
        return cls(enabled=enabled, url=url)

    def validate(self) -> tuple[bool, str]:
        """
        Validate the proxy configuration.

        Returns:
            (is_valid, error_message) tuple.
        """
        if not self.enabled:
            return True, ""

        url = self.url.strip()
        if not url:
            return False, "Proxy is enabled but URL is empty"

        try:
            parsed = urlparse(url)
        except Exception as exc:
            return False, f"Invalid proxy URL: {exc}"

        if not parsed.scheme:
            return False, "Proxy URL must include scheme (e.g., http://, socks5://)"

        valid_schemes = {"http", "https", "socks4", "socks5"}
        if parsed.scheme.lower() not in valid_schemes:
            return False, f"Unsupported proxy scheme: {parsed.scheme}. Use: {', '.join(sorted(valid_schemes))}"

        if not parsed.netloc:
            return False, "Proxy URL must include host (and optionally port)"

        return True, ""


def get_urllib_proxy_handlers(config: Optional[ProxyConfig]) -> dict[str, str]:
    """
    Get proxy handlers dict for urllib.

    Returns:
        Dict like {"http": "http://proxy:port", "https": "http://proxy:port"}
        or empty dict if proxy is not active.
    """
    if config is None or not config.is_active():
        return {}

    url = config.get_url()
    if not url:
        return {}

    # For urllib, we need to specify per-protocol handlers
    return {
        "http": url,
        "https": url,
    }
