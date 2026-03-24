from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional
import subprocess


class PluginStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class TaskDefinition:
    id: str
    name: str
    description: str
    default_enabled: bool = True


@dataclass
class TaskResult:
    plugin_id: str
    task_id: str
    status: PluginStatus
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    message: str = ""


class GamePlugin(ABC):
    """Base class all game adapters must implement."""

    def __init__(self):
        self._status = PluginStatus.IDLE
        self._process: Optional[subprocess.Popen] = None
        self._config: dict = {}

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Unique identifier, e.g. 'maa_arknights'."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name, e.g. '明日方舟 (MAA)'."""
        ...

    @property
    @abstractmethod
    def game_name(self) -> str:
        """Game name, e.g. '明日方舟'."""
        ...

    @property
    @abstractmethod
    def icon_name(self) -> str:
        """Icon filename in resources folder."""
        ...

    @abstractmethod
    def validate_installation(self) -> tuple[bool, str]:
        """Check if the tool is installed at the configured path.
        Returns (is_valid, error_message).
        """
        ...

    @abstractmethod
    def get_available_tasks(self) -> list[TaskDefinition]:
        """Return list of tasks this plugin can perform."""
        ...

    @abstractmethod
    def run_tasks(self, task_ids: list[str], callback: Callable[[str, str], None]) -> TaskResult:
        """Execute the specified tasks.
        callback(level, message) for progress reporting: level is 'info'/'warning'/'error'.
        Returns TaskResult on completion.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Gracefully stop running tasks."""
        ...

    @property
    def status(self) -> PluginStatus:
        return self._status

    def load_config(self, config: dict) -> None:
        self._config = config

    def get_install_path(self) -> str:
        return self._config.get("install_path", "")

    def get_executable(self) -> str:
        return self._config.get("executable", "")

    def get_game_path(self) -> str:
        return self._config.get("game_path", "")

    def get_game_start_delay(self) -> int:
        return int(self._config.get("game_start_delay", 30))
