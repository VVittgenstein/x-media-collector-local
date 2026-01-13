from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SchedulerConfig:
    max_concurrent: int = 3

    def set_max_concurrent(self, value: int) -> None:
        if value < 1:
            raise ValueError("Max Concurrent 必须 >= 1")
        self.max_concurrent = value

