from datetime import datetime

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt

from qfluentwidgets import (
    PushButton, FluentIcon, SubtitleLabel, TextEdit, ComboBox, BodyLabel,
)
from ui.design_system import apply_button_style, apply_log_style


class LogPage(QWidget):

    def __init__(self):
        super().__init__()
        self.setObjectName("logPage")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(12)

        # Title bar
        title_layout = QHBoxLayout()
        title_layout.addWidget(SubtitleLabel("运行日志"))
        title_layout.addStretch()

        title_layout.addWidget(BodyLabel("筛选:"))
        self.filter_combo = ComboBox()
        self.filter_combo.addItem("全部", userData="all")
        self.filter_combo.setFixedWidth(160)
        title_layout.addWidget(self.filter_combo)

        clear_btn = PushButton(FluentIcon.DELETE, "清空")
        clear_btn.clicked.connect(self._on_clear)
        apply_button_style(clear_btn)
        title_layout.addWidget(clear_btn)

        layout.addLayout(title_layout)

        # Log text
        self.log_text = TextEdit()
        self.log_text.setReadOnly(True)
        apply_log_style(self.log_text)
        layout.addWidget(self.log_text, 1)

    def add_plugin_filter(self, plugin_id: str, display_name: str):
        self.filter_combo.addItem(display_name, userData=plugin_id)

    def append_log(self, plugin_id: str, level: str, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_colors = {
            "info": "#cccccc",
            "warning": "#c4841d",
            "error": "#c42b1c",
        }
        color = level_colors.get(level, "#cccccc")
        plugin_tag = f"[{plugin_id}]"
        self.log_text.append(
            f'<span style="color:#888">[{timestamp}]</span> '
            f'<span style="color:#0078d4">{plugin_tag}</span> '
            f'<span style="color:{color}">{message}</span>'
        )

    def _on_clear(self):
        self.log_text.clear()
