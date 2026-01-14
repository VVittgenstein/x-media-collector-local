from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..scheduler.config import SchedulerConfig
from ..scheduler.scheduler import Scheduler
from ..net.throttle import ThrottleConfig
from ..net.retry import RetryConfig
from ..net.proxy import ProxyConfig
from .models import Credentials, GlobalSettings
from .store import SettingsStore


class CredentialsIn(BaseModel):
    auth_token: str = Field(min_length=1)
    ct0: str = Field(min_length=1)
    twid: Optional[str] = None


class DownloadRootIn(BaseModel):
    download_root: str = Field(min_length=1)


class MaxConcurrentIn(BaseModel):
    max_concurrent: int = Field(ge=1, le=100)


class ThrottleIn(BaseModel):
    min_interval_s: float = Field(ge=0.0, le=60.0, default=1.5)
    jitter_max_s: float = Field(ge=0.0, le=30.0, default=1.0)
    enabled: bool = True


class RetryIn(BaseModel):
    max_retries: int = Field(ge=0, le=10, default=3)
    base_delay_s: float = Field(ge=0.1, le=60.0, default=2.0)
    max_delay_s: float = Field(ge=1.0, le=300.0, default=60.0)
    enabled: bool = True


class ProxyIn(BaseModel):
    enabled: bool = False
    url: str = ""


class CredentialsStatusOut(BaseModel):
    configured: bool
    auth_token_set: bool
    ct0_set: bool
    twid_set: bool


class ThrottleOut(BaseModel):
    min_interval_s: float
    jitter_max_s: float
    enabled: bool


class RetryOut(BaseModel):
    max_retries: int
    base_delay_s: float
    max_delay_s: float
    enabled: bool


class ProxyOut(BaseModel):
    enabled: bool
    url_configured: bool  # Don't expose actual URL for security


class SettingsOut(BaseModel):
    credentials: CredentialsStatusOut
    download_root: str
    max_concurrent: int
    throttle: ThrottleOut
    retry: RetryOut
    proxy: ProxyOut


def _public_settings(settings: GlobalSettings) -> SettingsOut:
    auth_token_set = bool(settings.credentials and settings.credentials.auth_token.strip())
    ct0_set = bool(settings.credentials and settings.credentials.ct0.strip())
    twid_set = bool(settings.credentials and (settings.credentials.twid or "").strip())

    throttle = settings.get_throttle()
    retry = settings.get_retry()
    proxy = settings.get_proxy()

    return SettingsOut(
        credentials=CredentialsStatusOut(
            configured=bool(auth_token_set and ct0_set),
            auth_token_set=auth_token_set,
            ct0_set=ct0_set,
            twid_set=twid_set,
        ),
        download_root=settings.download_root,
        max_concurrent=settings.max_concurrent,
        throttle=ThrottleOut(
            min_interval_s=throttle.min_interval_s,
            jitter_max_s=throttle.jitter_max_s,
            enabled=throttle.enabled,
        ),
        retry=RetryOut(
            max_retries=retry.max_retries,
            base_delay_s=retry.base_delay_s,
            max_delay_s=retry.max_delay_s,
            enabled=retry.enabled,
        ),
        proxy=ProxyOut(
            enabled=proxy.enabled,
            url_configured=bool(proxy.url.strip()),
        ),
    )


def _resolve_download_root(download_root: str, *, repo_root: Path) -> Path:
    raw = download_root.strip()
    if not raw:
        raise ValueError("Download Root 不能为空")

    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (repo_root / p).resolve()
    return p


def _ensure_dir_writable(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise ValueError(f"无法创建目录：{exc}") from exc

    if not path.is_dir():
        raise ValueError("Download Root 不是目录")

    try:
        with tempfile.NamedTemporaryFile(prefix=".xmc_write_test_", dir=str(path), delete=True):
            pass
    except PermissionError as exc:
        raise ValueError("Download Root 无写权限") from exc
    except Exception as exc:
        raise ValueError(f"无法写入 Download Root：{exc}") from exc


def create_settings_router(
    *, store: SettingsStore, scheduler_config: SchedulerConfig, scheduler: Scheduler, repo_root: Path
) -> APIRouter:
    router = APIRouter(prefix="/api/settings", tags=["settings"])

    @router.get("", response_model=SettingsOut)
    def get_settings() -> SettingsOut:
        return _public_settings(store.load())

    @router.post("/credentials", response_model=SettingsOut)
    def set_credentials(body: CredentialsIn) -> SettingsOut:
        twid = body.twid.strip() if body.twid and body.twid.strip() else None
        creds = Credentials(auth_token=body.auth_token.strip(), ct0=body.ct0.strip(), twid=twid)

        def mutate(settings: GlobalSettings) -> GlobalSettings:
            settings.credentials = creds
            return settings

        updated = store.update(mutator=mutate)
        return _public_settings(updated)

    @router.delete("/credentials", response_model=SettingsOut)
    def clear_credentials() -> SettingsOut:
        updated = store.clear_credentials()
        return _public_settings(updated)

    @router.post("/download-root", response_model=SettingsOut)
    def set_download_root(body: DownloadRootIn) -> SettingsOut:
        try:
            root = _resolve_download_root(body.download_root, repo_root=repo_root)
            _ensure_dir_writable(root)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        updated = store.set_value(key="download_root", value=str(root))
        return _public_settings(updated)

    @router.post("/max-concurrent", response_model=SettingsOut)
    async def set_max_concurrent(body: MaxConcurrentIn) -> SettingsOut:
        try:
            scheduler_config.set_max_concurrent(body.max_concurrent)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        updated = store.set_value(key="max_concurrent", value=body.max_concurrent)
        await scheduler.reschedule()
        return _public_settings(updated)

    @router.post("/throttle", response_model=SettingsOut)
    def set_throttle(body: ThrottleIn) -> SettingsOut:
        throttle = ThrottleConfig(
            min_interval_s=body.min_interval_s,
            jitter_max_s=body.jitter_max_s,
            enabled=body.enabled,
        )

        def mutate(settings: GlobalSettings) -> GlobalSettings:
            settings.throttle = throttle
            return settings

        updated = store.update(mutator=mutate)
        return _public_settings(updated)

    @router.post("/retry", response_model=SettingsOut)
    def set_retry(body: RetryIn) -> SettingsOut:
        retry = RetryConfig(
            max_retries=body.max_retries,
            base_delay_s=body.base_delay_s,
            max_delay_s=body.max_delay_s,
            enabled=body.enabled,
        )

        def mutate(settings: GlobalSettings) -> GlobalSettings:
            settings.retry = retry
            return settings

        updated = store.update(mutator=mutate)
        return _public_settings(updated)

    @router.post("/proxy", response_model=SettingsOut)
    def set_proxy(body: ProxyIn) -> SettingsOut:
        proxy = ProxyConfig(
            enabled=body.enabled,
            url=body.url.strip(),
        )

        # Validate proxy URL if enabled
        is_valid, error = proxy.validate()
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)

        def mutate(settings: GlobalSettings) -> GlobalSettings:
            settings.proxy = proxy
            return settings

        updated = store.update(mutator=mutate)
        return _public_settings(updated)

    @router.delete("/proxy", response_model=SettingsOut)
    def clear_proxy() -> SettingsOut:
        def mutate(settings: GlobalSettings) -> GlobalSettings:
            settings.proxy = ProxyConfig(enabled=False, url="")
            return settings

        updated = store.update(mutator=mutate)
        return _public_settings(updated)

    return router
