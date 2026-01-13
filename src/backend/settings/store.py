from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Optional

from .models import GlobalSettings


class SettingsStore:
    def __init__(self, *, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> GlobalSettings:
        with self._lock:
            if not self._path.exists():
                return GlobalSettings()

            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                return GlobalSettings()

            if not isinstance(raw, dict):
                return GlobalSettings()

            return GlobalSettings.from_persist_dict(raw)

    def save(self, settings: GlobalSettings) -> None:
        payload = settings.to_persist_dict()

        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            tmp_path.replace(self._path)

    def update(self, *, mutator) -> GlobalSettings:
        with self._lock:
            current = self.load()
            updated = mutator(current)
            if not isinstance(updated, GlobalSettings):
                raise TypeError("mutator must return GlobalSettings")
            self.save(updated)
            return updated

    def clear_credentials(self) -> GlobalSettings:
        def mutate(settings: GlobalSettings) -> GlobalSettings:
            settings.credentials = None
            return settings

        return self.update(mutator=mutate)

    def set_value(self, *, key: str, value: Any) -> GlobalSettings:
        def mutate(settings: GlobalSettings) -> GlobalSettings:
            if not hasattr(settings, key):
                raise KeyError(key)
            setattr(settings, key, value)
            return settings

        return self.update(mutator=mutate)
