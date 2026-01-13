from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .open_folder import OpenFolderError, open_folder


class OpenFolderIn(BaseModel):
    path: str = Field(min_length=1)


class OpenFolderOut(BaseModel):
    success: bool
    opened_path: str


def _resolve_path(raw: str, *, repo_root: Path) -> Path:
    p = Path(raw.strip()).expanduser()
    if not p.is_absolute():
        p = (repo_root / p).resolve()
    return p


def create_os_router(*, repo_root: Path) -> APIRouter:
    router = APIRouter(prefix="/api/os", tags=["os"])

    @router.post("/open-folder", response_model=OpenFolderOut)
    def open_folder_endpoint(body: OpenFolderIn) -> OpenFolderOut:
        path = _resolve_path(body.path, repo_root=repo_root)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"目录不存在或已被删除：{path}")
        if not path.is_dir():
            raise HTTPException(status_code=400, detail=f"不是目录：{path}")

        try:
            open_folder(path)
        except OpenFolderError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return OpenFolderOut(success=True, opened_path=str(path))

    return router

