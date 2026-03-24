from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
)
from PyQt6.QtCore import Qt

from qfluentwidgets import (
    PrimaryPushButton, PushButton, CardWidget, FluentIcon,
    SubtitleLabel, CaptionLabel, BodyLabel, InfoBar, InfoBarPosition,
    ProgressRing,
)

from plugins.base import PluginStatus
from core.plugin_manager import PluginManager
from core.task_runner import TaskRunner, SequentialRunner
from core.scheduler import Scheduler


class GameStatusCard(CardWidget):
    """Card showing a single game's status."""

    def __init__(self, plugin_id: str, display_name: str, parent=None):
        super().__init__(parent)
        self.plugin_id = plugin_id
        self.setFixedHeight(140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)

        # Title
        self.title_label = SubtitleLabel(display_name)
        layout.addWidget(self.title_label)

        # Status
        self.status_label = BodyLabel("状态: 空闲")
        layout.addWidget(self.status_label)

        # Last run
        self.last_run_label = CaptionLabel("上次运行: 暂无记录")
        self.last_run_label.setTextColor("#888888", "#aaaaaa")
        layout.addWidget(self.last_run_label)

        # Next scheduled
        self.next_run_label = CaptionLabel("下次定时: 未设置")
        self.next_run_label.setTextColor("#888888", "#aaaaaa")
        layout.addWidget(self.next_run_label)

    def update_status(self, status: PluginStatus, last_run: str = "",
                      next_run: str = ""):
        status_text = {
            PluginStatus.IDLE: "空闲",
            PluginStatus.RUNNING: "运行中...",
            PluginStatus.SUCCESS: "上次成功",
            PluginStatus.FAILED: "上次失败",
            PluginStatus.STOPPED: "已停止",
        }
        status_colors = {
            PluginStatus.IDLE: "#888888",
            PluginStatus.RUNNING: "#0078d4",
            PluginStatus.SUCCESS: "#0f7b0f",
            PluginStatus.FAILED: "#c42b1c",
            PluginStatus.STOPPED: "#c4841d",
        }
        color = status_colors.get(status, "#888888")
        self.status_label.setText(f"状态: {status_text.get(status, '未知')}")
        self.status_label.setStyleSheet(f"color: {color};")

        if last_run:
            self.last_run_label.setText(f"上次运行: {last_run}")
        if next_run:
            self.next_run_label.setText(f"下次定时: {next_run}")
        else:
            self.next_run_label.setText("下次定时: 未设置")


class DashboardPage(QWidget):

    def __init__(self, plugin_manager: PluginManager, task_runner: TaskRunner,
                 scheduler: Scheduler):
        super().__init__()
        self._plugin_manager = plugin_manager
        self._task_runner = task_runner
        self._scheduler = scheduler
        self._seq_runner = None

        self.setObjectName("dashboardPage")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(16)

        # Title bar
        title_layout = QHBoxLayout()
        title_label = SubtitleLabel("仪表盘")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self.run_all_btn = PrimaryPushButton(FluentIcon.PLAY, "一键全部运行")
        self.run_all_btn.clicked.connect(self._on_run_all)
        title_layout.addWidget(self.run_all_btn)

        self.stop_all_btn = PushButton(FluentIcon.CLOSE, "全部停止")
        self.stop_all_btn.clicked.connect(self._on_stop_all)
        self.stop_all_btn.setEnabled(False)
        title_layout.addWidget(self.stop_all_btn)

        layout.addLayout(title_layout)

        # Game status cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self._cards: dict[str, GameStatusCard] = {}
        for plugin_id, plugin in self._plugin_manager.get_all_plugins().items():
            card = GameStatusCard(plugin_id, plugin.display_name)
            cards_layout.addWidget(card)
            self._cards[plugin_id] = card

        layout.addLayout(cards_layout)
        layout.addStretch()

        self.refresh_status()

    def refresh_status(self):
        for plugin_id, card in self._cards.items():
            plugin = self._plugin_manager.get_plugin(plugin_id)
            if plugin:
                # Find next scheduled run
                next_run = ""
                for sched in self._scheduler.get_schedules():
                    if sched.plugin_id == plugin_id and sched.enabled:
                        nr = self._scheduler.get_next_run(sched.id)
                        if nr:
                            next_run = nr
                            break
                card.update_status(plugin.status, next_run=next_run)

    def _on_run_all(self):
        plugins_and_tasks = []
        for plugin_id, plugin in self._plugin_manager.get_all_plugins().items():
            valid, _ = plugin.validate_installation()
            if valid:
                task_ids = [t.id for t in plugin.get_available_tasks() if t.default_enabled]
                if task_ids:
                    plugins_and_tasks.append((plugin, task_ids))

        if not plugins_and_tasks:
            InfoBar.warning("提示", "没有可运行的游戏工具，请先配置安装路径",
                            parent=self, position=InfoBarPosition.TOP)
            return

        self.run_all_btn.setEnabled(False)
        self.stop_all_btn.setEnabled(True)

        self._seq_runner = SequentialRunner(plugins_and_tasks, self._task_runner)
        self._seq_runner.all_finished.connect(self._on_seq_finished)
        self._seq_runner.start()

        InfoBar.info("开始运行", f"正在按序执行 {len(plugins_and_tasks)} 个游戏的日常任务...",
                     parent=self, position=InfoBarPosition.TOP)

    def _on_stop_all(self):
        if self._seq_runner:
            self._seq_runner.stop()
        self._task_runner.stop_all()

    def _on_seq_finished(self, results):
        self.run_all_btn.setEnabled(True)
        self.stop_all_btn.setEnabled(False)
        self._seq_runner = None

        success = sum(1 for r in results if r.status == PluginStatus.SUCCESS)
        total = len(results)
        if success == total:
            InfoBar.success("完成", f"全部 {total} 个游戏任务执行成功",
                            parent=self, position=InfoBarPosition.TOP)
        else:
            InfoBar.warning("完成", f"{success}/{total} 个游戏任务执行成功",
                            parent=self, position=InfoBarPosition.TOP)
        self.refresh_status()
