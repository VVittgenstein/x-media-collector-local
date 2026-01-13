from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .scheduler.config import SchedulerConfig
from .scheduler.api import create_scheduler_router
from .scheduler.scheduler import Scheduler
from .settings.api import create_settings_router
from .settings.store import SettingsStore
from .pipeline.account_runner import create_account_runner
from .fs import AccountStorageManager
from .lifecycle.api import create_lifecycle_router
from .os.api import create_os_router


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def create_app() -> FastAPI:
    repo_root = _repo_root()
    data_dir = repo_root / "data"
    config_path = data_dir / "config.json"
    runs_dir = data_dir / "runs"
    frontend_dir = repo_root / "src" / "frontend"

    store = SettingsStore(path=config_path)
    scheduler_config = SchedulerConfig(max_concurrent=store.load().max_concurrent)
    runner = create_account_runner(store=store)
    scheduler = Scheduler(config=scheduler_config, runs_dir=runs_dir, runner=runner)

    # Create storage manager for lifecycle operations
    download_root = Path(store.load().download_root or (repo_root / "downloads"))
    storage = AccountStorageManager(download_root=download_root)

    app = FastAPI(title="x-media-collector-local")
    app.include_router(
        create_settings_router(store=store, scheduler_config=scheduler_config, scheduler=scheduler, repo_root=repo_root)
    )
    app.include_router(create_scheduler_router(scheduler=scheduler))
    app.include_router(create_lifecycle_router(storage=storage))
    app.include_router(create_os_router(repo_root=repo_root))

    app.state.settings_store = store
    app.state.scheduler_config = scheduler_config
    app.state.scheduler = scheduler
    app.state.repo_root = repo_root
    app.state.storage = storage

    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    return app


app = create_app()
