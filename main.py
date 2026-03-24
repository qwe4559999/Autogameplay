import sys
import os
import logging

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt

from qfluentwidgets import setTheme, Theme, FluentIcon

from core.config_manager import ConfigManager
from core.plugin_manager import PluginManager
from core.task_runner import TaskRunner
from core.scheduler import Scheduler
from ui.main_window import MainWindow

# Configure logging
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "autogameplay.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("AutoGamePlay")


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
    main()
