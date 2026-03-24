from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from qfluentwidgets import (
    FluentIcon, NavigationItemPosition, MSFluentWindow, SplashScreen
)

from ui.dashboard_page import DashboardPage
from ui.game_page import GamePage
from ui.schedule_page import SchedulePage
from ui.log_page import LogPage
from ui.settings_page import SettingsPage

from core.config_manager import ConfigManager
from core.plugin_manager import PluginManager
from core.task_runner import TaskRunner
from core.scheduler import Scheduler
from ui.design_system import APP_STYLESHEET


class MainWindow(MSFluentWindow):

    def __init__(self, config: ConfigManager, plugin_manager: PluginManager,
                 task_runner: TaskRunner, scheduler: Scheduler):
        super().__init__()
        self._config = config
        self._plugin_manager = plugin_manager
        self._task_runner = task_runner
        self._scheduler = scheduler

        self.setWindowTitle("AutoGamePlay - 多游戏日常自动化")
        self.resize(1180, 760)
        self.setStyleSheet(APP_STYLESHEET)

        # Center window
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                (geo.width() - self.width()) // 2,
                (geo.height() - self.height()) // 2,
            )

        self._init_pages()

    def _init_pages(self):
        # Dashboard
        self.dashboard_page = DashboardPage(
            self._plugin_manager, self._task_runner, self._scheduler
        )
        self.addSubInterface(self.dashboard_page, FluentIcon.HOME, "仪表盘")

        # Per-game pages
        self.game_pages: dict[str, GamePage] = {}
        game_icons = {
            "maa_arknights": FluentIcon.GAME,
            "maaend_endfield": FluentIcon.IOT,
            "okww_wutheringwaves": FluentIcon.SPEED_HIGH,
        }
        for plugin_id, plugin in self._plugin_manager.get_all_plugins().items():
            page = GamePage(plugin, self._task_runner, self._config)
            icon = game_icons.get(plugin_id, FluentIcon.GAME)
            self.addSubInterface(page, icon, plugin.game_name)
            self.game_pages[plugin_id] = page

        # Schedule page
        self.schedule_page = SchedulePage(
            self._scheduler, self._plugin_manager
        )
        self.addSubInterface(self.schedule_page, FluentIcon.CALENDAR, "定时任务")

        # Log page
        self.log_page = LogPage()
        self.addSubInterface(self.log_page, FluentIcon.DOCUMENT, "日志")

        # Settings (bottom)
        self.settings_page = SettingsPage(self._config, self._plugin_manager)
        self.addSubInterface(
            self.settings_page, FluentIcon.SETTING, "设置",
            position=NavigationItemPosition.BOTTOM,
        )

        # Connect TaskRunner signals (QueuedConnection across threads)
        self._task_runner.log_received.connect(self._on_log)
        self._task_runner.task_started.connect(self._on_task_started)
        self._task_runner.task_completed.connect(self._on_task_finished)

        # Connect settings save → game page refresh
        self.settings_page.config_saved.connect(self._on_config_saved)

    def _on_log(self, plugin_id: str, level: str, message: str):
        self.log_page.append_log(plugin_id, level, message)
        page = self.game_pages.get(plugin_id)
        if page:
            page.append_log(level, message)

    def _on_task_started(self, plugin_id: str):
        self.dashboard_page.refresh_status()
        page = self.game_pages.get(plugin_id)
        if page:
            page.on_task_started()

    def _on_task_finished(self, plugin_id: str, result):
        self.dashboard_page.refresh_status()
        page = self.game_pages.get(plugin_id)
        if page:
            page.on_task_finished(result)

    def _on_config_saved(self):
        """Refresh all game pages after settings are saved."""
        for page in self.game_pages.values():
            page.refresh_config()
