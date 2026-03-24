import ctypes
import os
import subprocess
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QSpinBox
)
from PyQt6.QtCore import Qt

from qfluentwidgets import (
    PrimaryPushButton, PushButton, CardWidget, FluentIcon,
    SubtitleLabel, BodyLabel, CaptionLabel, LineEdit, ToolButton,
    TextEdit, InfoBar, InfoBarPosition,
)

from plugins.base import GamePlugin, PluginStatus, TaskResult
from core.task_runner import TaskRunner
from core.config_manager import ConfigManager


class GamePage(QWidget):

    def __init__(self, plugin: GamePlugin, task_runner: TaskRunner,
                 config: ConfigManager):
        super().__init__()
        self._plugin = plugin
        self._task_runner = task_runner
        self._config = config

        self.setObjectName(f"gamePage_{plugin.plugin_id}")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(16)

        is_maaend = self._plugin.plugin_id == "maaend_endfield"

        if is_maaend:
            hero_card = CardWidget()
            hero_card.setStyleSheet(
                "CardWidget {"
                "background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #f4fbff, stop:1 #eef8f3);"
                "border:1px solid rgba(0,140,140,0.16);"
                "border-radius:18px;"
                "}"
            )
            hero_layout = QVBoxLayout(hero_card)
            hero_layout.setContentsMargins(22, 18, 22, 18)
            hero_layout.setSpacing(6)

            title = SubtitleLabel("终末地自动接管")
            title.setStyleSheet("font-size: 20px; font-weight: 700;")
            hero_layout.addWidget(title)

            subtitle = CaptionLabel(
                "统一拉起游戏与 MaaEnd，检测到终末地在运行后会主动补发一次开始任务指令。"
            )
            subtitle.setTextColor("#356f6f", "#9bd1d1")
            hero_layout.addWidget(subtitle)
            layout.addWidget(hero_card)
        else:
            title = SubtitleLabel(self._plugin.display_name)
            layout.addWidget(title)

        # Install path config card
        path_card = CardWidget()
        if is_maaend:
            path_card.setStyleSheet("CardWidget { border-radius:16px; }")
        path_layout = QHBoxLayout(path_card)
        path_layout.setContentsMargins(16, 12, 16, 12)

        path_label = BodyLabel("安装路径:")
        path_layout.addWidget(path_label)

        self.path_edit = LineEdit()
        self.path_edit.setPlaceholderText("选择工具安装目录...")
        self.path_edit.setText(self._plugin.get_install_path())
        path_layout.addWidget(self.path_edit, 1)

        browse_btn = ToolButton(FluentIcon.FOLDER)
        browse_btn.clicked.connect(self._on_browse)
        path_layout.addWidget(browse_btn)

        self.validate_btn = PushButton(FluentIcon.ACCEPT, "验证")
        self.validate_btn.clicked.connect(self._on_validate)
        path_layout.addWidget(self.validate_btn)

        layout.addWidget(path_card)

        self.game_path_edit = None
        self.game_delay_spin = None
        if self._plugin.plugin_id == "maaend_endfield":
            game_card = CardWidget()
            game_card.setStyleSheet("CardWidget { border-radius:16px; }")
            game_layout = QVBoxLayout(game_card)
            game_layout.setContentsMargins(16, 12, 16, 12)
            game_layout.setSpacing(10)

            helper = CaptionLabel("终末地运行后，MaaEnd 会优先尝试自动开跑；若失败则补发开始任务热键。")
            helper.setTextColor("#5d7d7d", "#88b8b8")
            game_layout.addWidget(helper)

            path_row = QHBoxLayout()
            path_row.addWidget(BodyLabel("游戏路径:"))
            self.game_path_edit = LineEdit()
            self.game_path_edit.setPlaceholderText("选择游戏快捷方式或可执行文件...")
            self.game_path_edit.setText(self._plugin.get_game_path())
            path_row.addWidget(self.game_path_edit, 1)

            game_browse_btn = ToolButton(FluentIcon.FOLDER)
            game_browse_btn.clicked.connect(self._on_browse_game)
            path_row.addWidget(game_browse_btn)
            game_layout.addLayout(path_row)

            delay_row = QHBoxLayout()
            delay_row.addWidget(BodyLabel("启动等待:"))
            self.game_delay_spin = QSpinBox()
            self.game_delay_spin.setRange(0, 600)
            self.game_delay_spin.setSuffix(" 秒")
            self.game_delay_spin.setValue(self._plugin.get_game_start_delay())
            delay_row.addWidget(self.game_delay_spin)
            delay_row.addStretch()
            game_layout.addLayout(delay_row)

            layout.addWidget(game_card)

        # Info card
        info_card = CardWidget()
        if is_maaend:
            info_card.setStyleSheet(
                "CardWidget { background: rgba(0, 128, 128, 0.04); border-radius:16px; }"
            )
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(16, 12, 16, 12)

        info_text = (
            "任务配置请在各工具自带的 GUI 中完成。本平台负责启动、提权、监控和收尾。"
            if is_maaend else
            "任务配置请在各工具自带的 GUI 中完成。本平台仅负责启动、调度和监控。"
        )
        info_label = CaptionLabel(info_text)
        info_label.setTextColor("#6f6f6f", "#aaaaaa")
        info_layout.addWidget(info_label)

        layout.addWidget(info_card)

        # Action buttons
        btn_layout = QHBoxLayout()

        self.run_btn = PrimaryPushButton(FluentIcon.PLAY, "立即运行")
        self.run_btn.clicked.connect(self._on_run)
        if is_maaend:
            self.run_btn.setMinimumHeight(42)
        btn_layout.addWidget(self.run_btn)

        self.stop_btn = PushButton(FluentIcon.CLOSE, "停止")
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        if is_maaend:
            self.stop_btn.setMinimumHeight(42)
        btn_layout.addWidget(self.stop_btn)

        self.open_tool_btn = PushButton(FluentIcon.SETTING, "打开工具配置")
        self.open_tool_btn.clicked.connect(self._on_open_tool)
        if is_maaend:
            self.open_tool_btn.setMinimumHeight(42)
        btn_layout.addWidget(self.open_tool_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Log output
        log_label = CaptionLabel("运行日志:")
        layout.addWidget(log_label)

        self.log_text = TextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 12px;"
        )
        layout.addWidget(self.log_text, 1)

    def _on_browse(self):
        path = QFileDialog.getExistingDirectory(self, "选择安装目录")
        if path:
            self.path_edit.setText(path)
            self._save_path(path)

    def _save_path(self, path: str):
        self._save_config(install_path=path)

    def _save_config(self, install_path: str | None = None,
                     game_path: str | None = None,
                     game_start_delay: int | None = None):
        plugin_id = self._plugin.plugin_id
        key_map = {
            "maa_arknights": "maa",
            "maaend_endfield": "maaend",
            "okww_wutheringwaves": "okww",
        }
        config_key = key_map.get(plugin_id, plugin_id)
        current = self._config.get_tool_config(config_key)
        if install_path is not None:
            current["install_path"] = install_path
        if game_path is not None:
            current["game_path"] = game_path
        if game_start_delay is not None:
            current["game_start_delay"] = game_start_delay
        self._config.set_tool_config(config_key, current)
        self._config.save()
        self._plugin.load_config(current)

    def _on_browse_game(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择游戏快捷方式或可执行文件",
            "",
            "可执行文件或快捷方式 (*.exe *.lnk);;所有文件 (*)",
        )
        if path and self.game_path_edit is not None:
            self.game_path_edit.setText(path)
            delay = self.game_delay_spin.value() if self.game_delay_spin is not None else None
            self._save_config(game_path=path, game_start_delay=delay)

    def _on_validate(self):
        path = self.path_edit.text().strip()
        if path:
            self._save_path(path)

        valid, msg = self._plugin.validate_installation()
        if valid:
            InfoBar.success("验证通过", msg, parent=self, position=InfoBarPosition.TOP)
        else:
            InfoBar.error("验证失败", msg, parent=self, position=InfoBarPosition.TOP)

    def _on_run(self):
        # Save path if changed
        path = self.path_edit.text().strip()
        if path and path != self._plugin.get_install_path():
            self._save_path(path)
        elif path:
            self._save_config(install_path=path)

        if self.game_path_edit is not None and self.game_delay_spin is not None:
            self._save_config(
                game_path=self.game_path_edit.text().strip(),
                game_start_delay=self.game_delay_spin.value(),
            )

        # Get default task IDs from plugin
        task_ids = [t.id for t in self._plugin.get_available_tasks() if t.default_enabled]
        if not task_ids:
            task_ids = ["daily"]

        self.log_text.clear()
        started = self._task_runner.start_tasks(self._plugin.plugin_id, task_ids)
        if started:
            self.on_task_started()
            self.append_log("info", "任务已启动...")
        else:
            InfoBar.warning("提示", "该游戏已有任务在运行", parent=self,
                            position=InfoBarPosition.TOP)

    def _on_stop(self):
        self._task_runner.stop_tasks(self._plugin.plugin_id)
        self.append_log("warning", "正在停止任务...")

    def _on_open_tool(self):
        """Launch the tool's GUI for configuration (without auto-run)."""
        install_path = self._plugin.get_install_path()
        exe_name = self._plugin.get_executable()
        if not install_path or not exe_name:
            InfoBar.warning("提示", "请先配置安装路径", parent=self,
                            position=InfoBarPosition.TOP)
            return

        exe_path = os.path.join(install_path, exe_name)
        if not os.path.isfile(exe_path):
            InfoBar.error("错误", f"未找到: {exe_path}", parent=self,
                          position=InfoBarPosition.TOP)
            return

        try:
            if self._plugin.plugin_id == "maaend_endfield":
                if ctypes.windll.shell32.IsUserAnAdmin():
                    subprocess.Popen([exe_path], cwd=install_path)
                else:
                    ret = ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", exe_path, None, install_path, 1
                    )
                    if ret <= 32:
                        raise RuntimeError("MaaEnd 启动失败，可能是 UAC 被取消")
            else:
                subprocess.Popen([exe_path], cwd=install_path)
            InfoBar.info("已启动", f"已打开 {exe_name}，请在其中配置任务",
                         parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error("启动失败", str(e), parent=self,
                          position=InfoBarPosition.TOP)

    def refresh_config(self):
        """Refresh the displayed path from the plugin's current config."""
        self.path_edit.setText(self._plugin.get_install_path())
        if self.game_path_edit is not None:
            self.game_path_edit.setText(self._plugin.get_game_path())
        if self.game_delay_spin is not None:
            self.game_delay_spin.setValue(self._plugin.get_game_start_delay())

    def on_task_started(self):
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def append_log(self, level: str, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = {"info": "#cccccc", "warning": "#c4841d", "error": "#c42b1c"}.get(level, "#cccccc")
        self.log_text.append(
            f'<span style="color:#888">[{timestamp}]</span> '
            f'<span style="color:{color}">{message}</span>'
        )

    def on_task_finished(self, result: TaskResult):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if result.status == PluginStatus.SUCCESS:
            self.append_log("info", f"任务完成: {result.message}")
            InfoBar.success("完成", result.message, parent=self,
                            position=InfoBarPosition.TOP)
        elif result.status == PluginStatus.STOPPED:
            self.append_log("warning", "任务已停止")
        else:
            self.append_log("error", f"任务失败: {result.message}")
            InfoBar.error("失败", result.message, parent=self,
                          position=InfoBarPosition.TOP)
