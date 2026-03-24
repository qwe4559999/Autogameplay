from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QSpinBox
from PyQt6.QtCore import Qt, pyqtSignal

from qfluentwidgets import (
    SubtitleLabel, BodyLabel, CardWidget, LineEdit, ToolButton,
    PushButton, FluentIcon, ComboBox, SwitchButton, InfoBar,
    InfoBarPosition, SettingCardGroup, ExpandLayout,
)

from core.config_manager import ConfigManager
from core.plugin_manager import PluginManager
from ui.design_system import apply_button_style, apply_card_style


class ToolPathCard(CardWidget):
    """Card for configuring a single tool's install path."""

    def __init__(self, tool_key: str, display_name: str, config: ConfigManager,
                 plugin_manager: PluginManager, parent=None):
        super().__init__(parent)
        self._tool_key = tool_key
        self._config = config
        self._plugin_manager = plugin_manager
        apply_card_style(self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        layout.addWidget(BodyLabel(f"{display_name}:"))

        self.path_edit = LineEdit()
        self.path_edit.setPlaceholderText("选择安装目录...")
        current = config.get_tool_config(tool_key)
        self.path_edit.setText(current.get("install_path", ""))
        layout.addWidget(self.path_edit, 1)

        browse_btn = ToolButton(FluentIcon.FOLDER)
        browse_btn.clicked.connect(self._on_browse)
        layout.addWidget(browse_btn)

    def _on_browse(self):
        path = QFileDialog.getExistingDirectory(self, "选择安装目录")
        if path:
            self.path_edit.setText(path)

    def save(self):
        path = self.path_edit.text().strip()
        current = self._config.get_tool_config(self._tool_key)
        current["install_path"] = path
        self._config.set_tool_config(self._tool_key, current)


class SettingsPage(QWidget):

    config_saved = pyqtSignal()  # Emitted after settings are saved

    def __init__(self, config: ConfigManager, plugin_manager: PluginManager):
        super().__init__()
        self._config = config
        self._plugin_manager = plugin_manager

        self.setObjectName("settingsPage")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(16)

        layout.addWidget(SubtitleLabel("设置"))

        # Theme
        theme_card = CardWidget()
        apply_card_style(theme_card)
        theme_layout = QHBoxLayout(theme_card)
        theme_layout.setContentsMargins(16, 12, 16, 12)
        theme_layout.addWidget(BodyLabel("主题:"))
        self.theme_combo = ComboBox()
        self.theme_combo.addItems(["跟随系统", "浅色", "深色"])
        theme_map = {"auto": 0, "light": 1, "dark": 2}
        self.theme_combo.setCurrentIndex(theme_map.get(self._config.theme, 0))
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()
        layout.addWidget(theme_card)

        # Minimize to tray
        tray_card = CardWidget()
        apply_card_style(tray_card)
        tray_layout = QHBoxLayout(tray_card)
        tray_layout.setContentsMargins(16, 12, 16, 12)
        tray_layout.addWidget(BodyLabel("关闭时最小化到托盘:"))
        self.tray_switch = SwitchButton()
        self.tray_switch.setChecked(self._config.minimize_to_tray)
        tray_layout.addWidget(self.tray_switch)
        tray_layout.addStretch()
        layout.addWidget(tray_card)

        # Tool paths
        layout.addWidget(BodyLabel("工具安装路径"))

        self._tool_cards: list[ToolPathCard] = []
        tools = [
            ("maa", "MAA (明日方舟)"),
            ("maaend", "MaaEnd (终末地)"),
            ("okww", "OKWW (鸣潮)"),
        ]
        for key, name in tools:
            card = ToolPathCard(key, name, self._config, self._plugin_manager)
            layout.addWidget(card)
            self._tool_cards.append(card)

        maaend_card = CardWidget()
        apply_card_style(maaend_card)
        maaend_layout = QVBoxLayout(maaend_card)
        maaend_layout.setContentsMargins(16, 12, 16, 12)
        maaend_layout.setSpacing(12)

        game_row = QHBoxLayout()
        game_row.addWidget(BodyLabel("终末地游戏路径:"))
        maaend_config = self._config.get_tool_config("maaend")
        self.maaend_game_path_edit = LineEdit()
        self.maaend_game_path_edit.setPlaceholderText("选择游戏快捷方式或可执行文件...")
        self.maaend_game_path_edit.setText(maaend_config.get("game_path", ""))
        game_row.addWidget(self.maaend_game_path_edit, 1)

        game_browse_btn = ToolButton(FluentIcon.FOLDER)
        game_browse_btn.clicked.connect(self._on_browse_maaend_game)
        game_row.addWidget(game_browse_btn)
        maaend_layout.addLayout(game_row)

        delay_row = QHBoxLayout()
        delay_row.addWidget(BodyLabel("终末地启动等待:"))
        self.maaend_game_delay_spin = QSpinBox()
        self.maaend_game_delay_spin.setRange(0, 600)
        self.maaend_game_delay_spin.setSuffix(" 秒")
        self.maaend_game_delay_spin.setValue(int(maaend_config.get("game_start_delay", 30)))
        delay_row.addWidget(self.maaend_game_delay_spin)
        delay_row.addStretch()
        maaend_layout.addLayout(delay_row)

        layout.addWidget(maaend_card)

        # Save button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = PushButton(FluentIcon.SAVE, "保存设置")
        save_btn.clicked.connect(self._on_save)
        apply_button_style(save_btn, prominent=True)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

    def _on_browse_maaend_game(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择终末地快捷方式或可执行文件",
            "",
            "可执行文件或快捷方式 (*.exe *.lnk);;所有文件 (*)",
        )
        if path:
            self.maaend_game_path_edit.setText(path)

    def _on_save(self):
        # Theme
        theme_values = ["auto", "light", "dark"]
        self._config.theme = theme_values[self.theme_combo.currentIndex()]

        # Tray
        self._config._hub_config["minimize_to_tray"] = self.tray_switch.isChecked()

        # Tool paths
        for card in self._tool_cards:
            card.save()

        maaend_config = self._config.get_tool_config("maaend")
        maaend_config["game_path"] = self.maaend_game_path_edit.text().strip()
        maaend_config["game_start_delay"] = self.maaend_game_delay_spin.value()
        self._config.set_tool_config("maaend", maaend_config)

        self._config.save()

        # Reload plugin configs
        for plugin_id, plugin in self._plugin_manager.get_all_plugins().items():
            key_map = {
                "maa_arknights": "maa",
                "maaend_endfield": "maaend",
                "okww_wutheringwaves": "okww",
            }
            config_key = key_map.get(plugin_id, plugin_id)
            plugin.load_config(self._config.get_tool_config(config_key))

        InfoBar.success("保存成功", "设置已保存", parent=self,
                        position=InfoBarPosition.TOP)

        # Notify other pages to refresh
        self.config_saved.emit()
