import os
import shutil
import sys
from pathlib import Path


APP_NAME = "AutoGamePlay"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return project_root()


def _local_appdata_dir() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_NAME
    return Path.home() / "AppData" / "Local" / APP_NAME


def _is_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def data_root() -> Path:
    if getattr(sys, "frozen", False):
        portable_root = Path(sys.executable).resolve().parent / "data"
        if _is_writable(portable_root):
            return portable_root
        fallback = _local_appdata_dir()
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    return project_root()


def config_dir() -> Path:
    path = data_root() / "config"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = data_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_config_dir() -> Path:
    return bundle_root() / "config"


def ensure_runtime_layout() -> None:
    target_config_dir = config_dir()
    source_config_dir = default_config_dir()

    default_hub = source_config_dir / "hub.example.yaml"
    if not default_hub.exists():
        default_hub = source_config_dir / "hub.yaml"

    defaults = {
        "hub.yaml": default_hub,
        "schedules.yaml": source_config_dir / "schedules.yaml",
    }

    for filename, source in defaults.items():
        target = target_config_dir / filename
        if target.exists() or not source.exists():
            continue
        shutil.copyfile(source, target)

    logs_dir()
