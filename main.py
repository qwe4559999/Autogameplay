import sys
import os
import logging
import ctypes
import subprocess

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt

from qfluentwidgets import setTheme, Theme, FluentIcon

from core.config_manager import ConfigManager
from core.plugin_manager import PluginManager
from core.runtime_paths import ensure_runtime_layout, logs_dir
from core.task_runner import TaskRunner
from core.scheduler import Scheduler
from ui.main_window import MainWindow

# Configure logging
ensure_runtime_layout()
LOG_DIR = logs_dir()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "autogameplay.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("AutoGamePlay")


def _is_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _ensure_admin() -> bool:
    """Relaunch the app elevated on Windows so MaaEnd can run without per-action UAC."""
    if os.name != "nt" or _is_admin():
        return True

    if getattr(sys, "frozen", False):
        executable = sys.executable
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        executable = sys.executable
        params = subprocess.list2cmdline([os.path.abspath(__file__), *sys.argv[1:]])

    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
    if ret <= 32:
        ctypes.windll.user32.MessageBoxW(
            None,
            "AutoGamePlay 需要管理员权限才能稳定控制 MaaEnd。请允许 UAC 提权后重新打开。",
            "AutoGamePlay",
            0x10,
        )
    return False


def setup_theme(config: ConfigManager):
    theme_map = {
        "light": Theme.LIGHT,
        "dark": Theme.DARK,
        "auto": Theme.AUTO,
    }
    setTheme(theme_map.get(config.theme, Theme.AUTO))


def create_tray_icon(app: QApplication, window: MainWindow,
                     config: ConfigManager) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(app)
    tray.setToolTip("AutoGamePlay - 多游戏日常自动化")

    menu = QMenu()

    show_action = QAction("显示主窗口", menu)
    show_action.triggered.connect(window.show)
    show_action.triggered.connect(window.raise_)
    menu.addAction(show_action)

    menu.addSeparator()

    run_all_action = QAction("一键全部运行", menu)
    run_all_action.triggered.connect(window.dashboard_page._on_run_all)
    menu.addAction(run_all_action)

    stop_all_action = QAction("全部停止", menu)
    stop_all_action.triggered.connect(window.dashboard_page._on_stop_all)
    menu.addAction(stop_all_action)

    menu.addSeparator()

    quit_action = QAction("退出", menu)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: (
        window.show(), window.raise_()
    ) if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)

    tray.show()
    return tray


def main():
    # High DPI support
    app = QApplication(sys.argv)
    app.setApplicationName("AutoGamePlay")

    # Initialize core
    config = ConfigManager()
    setup_theme(config)

    plugin_manager = PluginManager(config)
    plugin_manager.load_all()

    task_runner = TaskRunner(plugin_manager)
    scheduler = Scheduler(config, plugin_manager, task_runner)

    # Create main window
    window = MainWindow(config, plugin_manager, task_runner, scheduler)

    # System tray
    tray = create_tray_icon(app, window, config)

    # Override close event for minimize-to-tray
    original_close = window.closeEvent

    def close_event(event):
        if config.minimize_to_tray:
            event.ignore()
            window.hide()
        else:
            scheduler.stop()
            tray.hide()
            event.accept()

    window.closeEvent = close_event

    # Start scheduler
    scheduler.start()

    # Show window
    window.show()
    logger.info("AutoGamePlay started")

    sys.exit(app.exec())


if __name__ == "__main__":
    if _ensure_admin():
        main()
