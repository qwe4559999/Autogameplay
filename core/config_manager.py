import os
import yaml
from typing import Any

from core.models import ScheduleEntry

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")


class ConfigManager:
    """Manages YAML configuration files."""

    def __init__(self, config_dir: str = CONFIG_DIR):
        self._config_dir = config_dir
        self._hub_config: dict = {}
        self._schedules: list[ScheduleEntry] = []
        self.load()

    def load(self) -> None:
        self._hub_config = self._read_yaml("hub.yaml")
        sched_data = self._read_yaml("schedules.yaml")
        self._schedules = [
            ScheduleEntry.from_dict(s)
            for s in sched_data.get("schedules", [])
        ]

    def save(self) -> None:
        self._write_yaml("hub.yaml", self._hub_config)
        self._write_yaml("schedules.yaml", {
            "schedules": [s.to_dict() for s in self._schedules]
        })

    # --- Hub config ---

    @property
    def theme(self) -> str:
        return self._hub_config.get("theme", "auto")

    @theme.setter
    def theme(self, value: str) -> None:
        self._hub_config["theme"] = value

    @property
    def minimize_to_tray(self) -> bool:
        return self._hub_config.get("minimize_to_tray", True)

    def get_tool_config(self, tool_key: str) -> dict:
        """Get tool config by key: 'maa', 'maaend', 'okww'."""
        return self._hub_config.get("tools", {}).get(tool_key, {})

    def set_tool_config(self, tool_key: str, config: dict) -> None:
        if "tools" not in self._hub_config:
            self._hub_config["tools"] = {}
        self._hub_config["tools"][tool_key] = config

    # --- Schedules ---

    @property
    def schedules(self) -> list[ScheduleEntry]:
        return self._schedules

    def add_schedule(self, entry: ScheduleEntry) -> None:
        self._schedules.append(entry)

    def remove_schedule(self, schedule_id: str) -> None:
        self._schedules = [s for s in self._schedules if s.id != schedule_id]

    def update_schedule(self, entry: ScheduleEntry) -> None:
        for i, s in enumerate(self._schedules):
            if s.id == entry.id:
                self._schedules[i] = entry
                return
        self._schedules.append(entry)

    # --- YAML helpers ---

    def _read_yaml(self, filename: str) -> dict:
        path = os.path.join(self._config_dir, filename)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}

    def _write_yaml(self, filename: str, data: Any) -> None:
        path = os.path.join(self._config_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
