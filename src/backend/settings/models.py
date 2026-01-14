from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..net.throttle import ThrottleConfig
from ..net.retry import RetryConfig
from ..net.proxy import ProxyConfig


DEFAULT_MAX_CONCURRENT = 3
DEFAULT_DOWNLOAD_ROOT = "downloads"


@dataclass(frozen=True)
class Credentials:
    auth_token: str
    ct0: str
    twid: Optional[str] = None

    def is_complete(self) -> bool:
        return bool(self.auth_token.strip()) and bool(self.ct0.strip())

    def to_persist_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "auth_token": self.auth_token,
            "ct0": self.ct0,
        }
        if self.twid:
            data["twid"] = self.twid
        return data

    @classmethod
    def from_persist_dict(cls, data: dict[str, Any]) -> "Credentials":
        return cls(
            auth_token=str(data.get("auth_token", "") or ""),
            ct0=str(data.get("ct0", "") or ""),
            twid=(str(data.get("twid")) if data.get("twid") is not None else None),
        )


@dataclass
class GlobalSettings:
    credentials: Optional[Credentials] = None
    download_root: str = DEFAULT_DOWNLOAD_ROOT
    max_concurrent: int = DEFAULT_MAX_CONCURRENT
    throttle: Optional[ThrottleConfig] = None
    retry: Optional[RetryConfig] = None
    proxy: Optional[ProxyConfig] = None

    def credentials_configured(self) -> bool:
        return self.credentials is not None and self.credentials.is_complete()

    def get_throttle(self) -> ThrottleConfig:
        """Get throttle config, using defaults if not set."""
        return self.throttle or ThrottleConfig()

    def get_retry(self) -> RetryConfig:
        """Get retry config, using defaults if not set."""
        return self.retry or RetryConfig()

    def get_proxy(self) -> ProxyConfig:
        """Get proxy config, using defaults if not set."""
        return self.proxy or ProxyConfig()

    def to_persist_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "version": 2,
            "download_root": self.download_root,
            "max_concurrent": self.max_concurrent,
        }
        if self.credentials is not None:
            data["credentials"] = self.credentials.to_persist_dict()
        if self.throttle is not None:
            data["throttle"] = self.throttle.to_persist_dict()
        if self.retry is not None:
            data["retry"] = self.retry.to_persist_dict()
        if self.proxy is not None:
            data["proxy"] = self.proxy.to_persist_dict()
        return data

    @classmethod
    def from_persist_dict(cls, data: dict[str, Any]) -> "GlobalSettings":
        raw_creds = data.get("credentials")
        credentials = None
        if isinstance(raw_creds, dict):
            credentials = Credentials.from_persist_dict(raw_creds)

        download_root = str(data.get("download_root", DEFAULT_DOWNLOAD_ROOT) or DEFAULT_DOWNLOAD_ROOT)
        try:
            max_concurrent = int(data.get("max_concurrent", DEFAULT_MAX_CONCURRENT) or DEFAULT_MAX_CONCURRENT)
        except (TypeError, ValueError):
            max_concurrent = DEFAULT_MAX_CONCURRENT

        raw_throttle = data.get("throttle")
        throttle = None
        if isinstance(raw_throttle, dict):
            throttle = ThrottleConfig.from_persist_dict(raw_throttle)

        raw_retry = data.get("retry")
        retry = None
        if isinstance(raw_retry, dict):
            retry = RetryConfig.from_persist_dict(raw_retry)

        raw_proxy = data.get("proxy")
        proxy = None
        if isinstance(raw_proxy, dict):
            proxy = ProxyConfig.from_persist_dict(raw_proxy)

        return cls(
            credentials=credentials,
            download_root=download_root,
            max_concurrent=max_concurrent,
            throttle=throttle,
            retry=retry,
            proxy=proxy,
        )

