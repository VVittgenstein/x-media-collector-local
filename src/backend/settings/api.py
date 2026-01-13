from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..scheduler.config import SchedulerConfig
from ..scheduler.scheduler import Scheduler
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


class CredentialsStatusOut(BaseModel):
    configured: bool
    auth_token_set: bool
    ct0_set: bool
    twid_set: bool


class SettingsOut(BaseModel):
    credentials: CredentialsStatusOut
    download_root: str
    max_concurrent: int


def _public_settings(settings: GlobalSettings) -> SettingsOut:
    auth_token_set = bool(settings.credentials and settings.credentials.auth_token.strip())
    ct0_set = bool(settings.credentials and settings.credentials.ct0.strip())
    twid_set = bool(settings.credentials and (settings.credentials.twid or "").strip())

    return SettingsOut(
        credentials=CredentialsStatusOut(
            configured=bool(auth_token_set and ct0_set),
            auth_token_set=auth_token_set,
            ct0_set=ct0_set,
            twid_set=twid_set,
        ),
        download_root=settings.download_root,
        max_concurrent=settings.max_concurrent,
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

    return router
