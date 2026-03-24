import ctypes
import os
import subprocess
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QSpinBox,
    QScrollArea, QFrame, QLabel
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
            self._build_maaend_ui(layout)
        else:
            self._build_standard_ui(layout)

    def _build_standard_ui(self, layout: QVBoxLayout):
        title = SubtitleLabel(self._plugin.display_name)
        layout.addWidget(title)

        # Install path config card
        path_card = CardWidget()
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
        self._add_standard_game_controls(layout)

    def _build_maaend_ui(self, layout: QVBoxLayout):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 1)

        content = QWidget()
        scroll.setWidget(content)

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        hero_card = CardWidget()
        hero_card.setObjectName("maaendHeroCard")
        hero_card.setStyleSheet(
            "#maaendHeroCard {"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #f2fbff, stop:0.55 #f7fbf6, stop:1 #eef7ff);"
            "border:1px solid rgba(15, 120, 140, 0.14);"
            "border-radius:20px;"
            "}"
        )
        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(24, 20, 24, 20)
        hero_layout.setSpacing(10)

        title = SubtitleLabel("明日方舟:终末地自动接管")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        hero_layout.addWidget(title)

        subtitle = CaptionLabel(
            "统一启动游戏与 MaaEnd，先拉起终末地，再等待状态稳定后触发任务执行。"
        )
        subtitle.setTextColor("#37656e", "#8fbac1")
        hero_layout.addWidget(subtitle)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        for text, bg, fg in [
            ("自动启动", "rgba(17, 131, 157, 0.12)", "#117f95"),
            ("任务接管", "rgba(70, 134, 72, 0.12)", "#3e7d42"),
            ("热键兜底", "rgba(110, 86, 186, 0.12)", "#6b57b2"),
        ]:
            badge_row.addWidget(self._make_badge(text, bg, fg))
        badge_row.addStretch()
        hero_layout.addLayout(badge_row)

        content_layout.addWidget(hero_card)

        summary_card = CardWidget()
        summary_card.setObjectName("maaendSummaryCard")
        summary_card.setStyleSheet(
            "#maaendSummaryCard {"
            "background: rgba(255, 255, 255, 0.92);"
            "border:1px solid rgba(120, 140, 160, 0.14);"
            "border-radius:18px;"
            "}"
        )
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        summary_layout.setSpacing(10)

        summary_title = BodyLabel("当前配置概览")
        summary_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        summary_layout.addWidget(summary_title)

        grid = QHBoxLayout()
        grid.setSpacing(12)
        self._maaend_summary_install = self._create_summary_block("安装路径", self._plugin.get_install_path())
        self._maaend_summary_game = self._create_summary_block("游戏路径", self._plugin.get_game_path())
        self._maaend_summary_delay = self._create_summary_block(
            "启动等待", f"{self._plugin.get_game_start_delay()} 秒"
        )
        grid.addWidget(self._maaend_summary_install)
        grid.addWidget(self._maaend_summary_game)
        grid.addWidget(self._maaend_summary_delay)
        summary_layout.addLayout(grid)

        content_layout.addWidget(summary_card)

        config_card = CardWidget()
        config_card.setObjectName("maaendConfigCard")
        config_card.setStyleSheet(
            "#maaendConfigCard {"
            "background: rgba(248, 251, 252, 0.96);"
            "border:1px solid rgba(140, 150, 165, 0.16);"
            "border-radius:18px;"
            "}"
        )
        config_layout = QVBoxLayout(config_card)
        config_layout.setContentsMargins(18, 16, 18, 16)
        config_layout.setSpacing(12)

        config_header = QHBoxLayout()
        config_header.setSpacing(8)
        header_label = BodyLabel("启动配置")
        header_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        config_header.addWidget(header_label)
        config_header.addStretch()
        config_hint = CaptionLabel("修改后自动保存到本地配置")
        config_hint.setTextColor("#7a7f87", "#9fa7b2")
        config_header.addWidget(config_hint)
        config_layout.addLayout(config_header)

        install_row = QHBoxLayout()
        install_row.setSpacing(12)
        install_row.addWidget(BodyLabel("安装路径"))
        self.path_edit = LineEdit()
        self.path_edit.setPlaceholderText("选择 MaaEnd 安装目录...")
        self.path_edit.setText(self._plugin.get_install_path())
        install_row.addWidget(self.path_edit, 1)

        browse_btn = ToolButton(FluentIcon.FOLDER)
        browse_btn.clicked.connect(self._on_browse)
        install_row.addWidget(browse_btn)

        self.validate_btn = PushButton(FluentIcon.ACCEPT, "验证")
        self.validate_btn.clicked.connect(self._on_validate)
        install_row.addWidget(self.validate_btn)
        config_layout.addLayout(install_row)

        self.game_path_edit = LineEdit()
        self.game_delay_spin = QSpinBox()

        game_row = QHBoxLayout()
        game_row.setSpacing(12)
        game_row.addWidget(BodyLabel("游戏路径"))
        self.game_path_edit.setPlaceholderText("选择终末地快捷方式或可执行文件...")
        self.game_path_edit.setText(self._plugin.get_game_path())
        game_row.addWidget(self.game_path_edit, 1)

        game_browse_btn = ToolButton(FluentIcon.FOLDER)
        game_browse_btn.clicked.connect(self._on_browse_game)
        game_row.addWidget(game_browse_btn)
        config_layout.addLayout(game_row)

        delay_row = QHBoxLayout()
        delay_row.setSpacing(12)
        delay_row.addWidget(BodyLabel("启动等待"))
        self.game_delay_spin.setRange(0, 600)
        self.game_delay_spin.setSuffix(" 秒")
        self.game_delay_spin.setValue(self._plugin.get_game_start_delay())
        self.game_delay_spin.setFixedWidth(160)
        delay_row.addWidget(self.game_delay_spin)
        delay_row.addStretch()
        delay_note = CaptionLabel("建议先等待终末地窗口稳定，再让 MaaEnd 接管。")
        delay_note.setTextColor("#7a7f87", "#9fa7b2")
        delay_row.addWidget(delay_note)
        config_layout.addLayout(delay_row)

        content_layout.addWidget(config_card)

        guide_card = CardWidget()
        guide_card.setObjectName("maaendGuideCard")
        guide_card.setStyleSheet(
            "#maaendGuideCard {"
            "background: rgba(245, 248, 250, 0.96);"
            "border:1px solid rgba(140, 150, 165, 0.14);"
            "border-radius:18px;"
            "}"
        )
        guide_layout = QVBoxLayout(guide_card)
        guide_layout.setContentsMargins(18, 16, 18, 16)
        guide_layout.setSpacing(8)

        guide_title = BodyLabel("执行说明")
        guide_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        guide_layout.addWidget(guide_title)

        for text in [
            "先启动终末地，再等待指定时间后让 MaaEnd 补发开始指令。",
            "如果 MaaEnd 已经以管理员权限运行，不会重复弹出 UAC。",
            "日志区会实时显示启动、等待、接管与关闭过程。",
        ]:
            guide_layout.addWidget(self._make_hint_line(text))

        content_layout.addWidget(guide_card)

        action_card = CardWidget()
        action_card.setObjectName("maaendActionCard")
        action_card.setStyleSheet(
            "#maaendActionCard {"
            "background: rgba(255, 255, 255, 0.96);"
            "border:1px solid rgba(120, 140, 160, 0.14);"
            "border-radius:18px;"
            "}"
        )
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(18, 16, 18, 16)
        action_layout.setSpacing(10)

        action_header = BodyLabel("操作")
        action_header.setStyleSheet("font-size: 15px; font-weight: 600;")
        action_layout.addWidget(action_header)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.run_btn = PrimaryPushButton(FluentIcon.PLAY, "立即运行")
        self.run_btn.clicked.connect(self._on_run)
        self.run_btn.setMinimumHeight(44)
        btn_layout.addWidget(self.run_btn)

        self.stop_btn = PushButton(FluentIcon.CLOSE, "停止")
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(44)
        btn_layout.addWidget(self.stop_btn)

        self.open_tool_btn = PushButton(FluentIcon.SETTING, "打开工具配置")
        self.open_tool_btn.clicked.connect(self._on_open_tool)
        self.open_tool_btn.setMinimumHeight(44)
        btn_layout.addWidget(self.open_tool_btn)

        btn_layout.addStretch()
        action_layout.addLayout(btn_layout)
        content_layout.addWidget(action_card)

        log_card = CardWidget()
        log_card.setObjectName("maaendLogCard")
        log_card.setStyleSheet(
            "#maaendLogCard {"
            "background: rgba(255, 255, 255, 0.98);"
            "border:1px solid rgba(120, 140, 160, 0.14);"
            "border-radius:18px;"
            "}"
        )
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(18, 16, 18, 16)
        log_layout.setSpacing(8)

        log_header = QHBoxLayout()
        log_header.setSpacing(8)
        log_title = BodyLabel("运行日志")
        log_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        log_header.addWidget(log_title)
        log_header.addStretch()
        log_hint = CaptionLabel("按时间顺序展示 MaaEnd 与终末地的关键状态")
        log_hint.setTextColor("#7a7f87", "#9fa7b2")
        log_header.addWidget(log_hint)
        log_layout.addLayout(log_header)

        self.log_text = TextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("任务运行后，日志会在这里滚动显示。")
        self.log_text.setMinimumHeight(280)
        self.log_text.setStyleSheet(
            "background: #fbfcfd;"
            "border: 1px solid rgba(120, 140, 160, 0.18);"
            "border-radius: 14px;"
            "font-family: 'Cascadia Code', 'Consolas', monospace;"
            "font-size: 12px;"
            "padding: 8px;"
        )
        log_layout.addWidget(self.log_text)

        content_layout.addWidget(log_card)
        content_layout.addStretch()

        self._apply_maaend_page_style()

    def _apply_maaend_page_style(self):
        self.setStyleSheet(
            "QLabel { color: #1f2933; }"
            "CardWidget { border: none; }"
        )

    def _make_badge(self, text: str, background: str, color: str) -> QLabel:
        badge = QLabel(text)
        badge.setStyleSheet(
            f"QLabel {{"
            f"padding: 5px 12px;"
            f"border-radius: 999px;"
            f"background: {background};"
            f"color: {color};"
            f"font-weight: 600;"
            f"}}"
        )
        return badge

    def _create_summary_block(self, title: str, value: str) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        block.setStyleSheet(
            "QWidget {"
            "background: rgba(245, 248, 250, 0.9);"
            "border: 1px solid rgba(135, 145, 160, 0.12);"
            "border-radius: 14px;"
            "}"
        )

        title_label = CaptionLabel(title)
        title_label.setTextColor("#6f7a86", "#97a3af")
        layout.addWidget(title_label)

        value_label = BodyLabel(value or "未配置")
        value_label.setWordWrap(True)
        value_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(value_label)

        if title == "安装路径":
            self._maaend_summary_install_value = value_label
        elif title == "游戏路径":
            self._maaend_summary_game_value = value_label
        elif title == "启动等待":
            self._maaend_summary_delay_value = value_label

        return block

    def _make_hint_line(self, text: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        dot = QLabel("•")
        dot.setStyleSheet("color: #6ca8b0; font-size: 18px;")
        layout.addWidget(dot)

        label = CaptionLabel(text)
        label.setWordWrap(True)
        label.setTextColor("#54606a", "#8fa0ad")
        layout.addWidget(label, 1)
        return row

    def _add_standard_game_controls(self, layout: QVBoxLayout):
        # Info card
        info_card = CardWidget()
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(16, 12, 16, 12)

        info_label = CaptionLabel(
            "任务配置请在各工具自带的 GUI 中完成。本平台仅负责启动、调度和监控。"
        )
        info_label.setTextColor("#888888", "#aaaaaa")
        info_layout.addWidget(info_label)

        layout.addWidget(info_card)

        # Action buttons
        btn_layout = QHBoxLayout()

        self.run_btn = PrimaryPushButton(FluentIcon.PLAY, "立即运行")
        self.run_btn.clicked.connect(self._on_run)
        btn_layout.addWidget(self.run_btn)

        self.stop_btn = PushButton(FluentIcon.CLOSE, "停止")
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)

        self.open_tool_btn = PushButton(FluentIcon.SETTING, "打开工具配置")
        self.open_tool_btn.clicked.connect(self._on_open_tool)
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

    def _refresh_maaend_summary(self):
        if hasattr(self, "_maaend_summary_install_value"):
            self._maaend_summary_install_value.setText(self._plugin.get_install_path() or "未配置")
        if hasattr(self, "_maaend_summary_game_value"):
            self._maaend_summary_game_value.setText(self._plugin.get_game_path() or "未配置")
        if hasattr(self, "_maaend_summary_delay_value"):
            self._maaend_summary_delay_value.setText(f"{self._plugin.get_game_start_delay()} 秒")

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
        self._refresh_maaend_summary()

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
