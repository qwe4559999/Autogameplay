from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScheduleEntry:
    id: str
    plugin_id: str
    task_ids: list[str]
    cron: str  # cron expression e.g. "0 4 * * *"
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plugin_id": self.plugin_id,
            "task_ids": self.task_ids,
            "cron": self.cron,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduleEntry":
        return cls(
            id=data["id"],
            plugin_id=data["plugin_id"],
            task_ids=data.get("task_ids", []),
            cron=data["cron"],
            enabled=data.get("enabled", True),
        )


@dataclass
class RunHistory:
    plugin_id: str
    task_ids: list[str]
    status: str  # "success" / "failed" / "stopped"
    start_time: str
    end_time: str
    message: str = ""
