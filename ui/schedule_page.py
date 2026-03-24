import uuid

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex

from qfluentwidgets import (
    PrimaryPushButton, PushButton, FluentIcon,
    SubtitleLabel, BodyLabel, TableView, LineEdit,
    ComboBox, CheckBox, MessageBox, InfoBar, InfoBarPosition,
    CardWidget,
)

from core.models import ScheduleEntry
from core.scheduler import Scheduler
from core.plugin_manager import PluginManager
from ui.design_system import apply_button_style, apply_card_style


class ScheduleTableModel(QAbstractTableModel):
    HEADERS = ["游戏", "Cron 表达式", "下次运行", "启用"]

    def __init__(self, scheduler: Scheduler, plugin_manager: PluginManager):
        super().__init__()
        self._scheduler = scheduler
        self._plugin_manager = plugin_manager
        self._entries: list[ScheduleEntry] = []
        self.refresh()

    def refresh(self):
        self.beginResetModel()
        self._entries = list(self._scheduler.get_schedules())
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._entries)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        entry = self._entries[index.row()]
        col = index.column()
        if col == 0:
            plugin = self._plugin_manager.get_plugin(entry.plugin_id)
            return plugin.display_name if plugin else entry.plugin_id
        elif col == 1:
            return entry.cron
        elif col == 2:
            return self._scheduler.get_next_run(entry.id) or "未计算"
        elif col == 3:
            return "是" if entry.enabled else "否"
        return None

    def get_entry(self, row: int) -> ScheduleEntry:
        return self._entries[row]


class SchedulePage(QWidget):

    def __init__(self, scheduler: Scheduler, plugin_manager: PluginManager):
        super().__init__()
        self._scheduler = scheduler
        self._plugin_manager = plugin_manager

        self.setObjectName("schedulePage")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 20, 36, 20)
        layout.setSpacing(16)

        # Title
        title_layout = QHBoxLayout()
        title_layout.addWidget(SubtitleLabel("定时任务"))
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # Add form card
        form_card = CardWidget()
        apply_card_style(form_card)
        form_layout = QHBoxLayout(form_card)
        form_layout.setContentsMargins(16, 12, 16, 12)
        form_layout.setSpacing(12)

        form_layout.addWidget(BodyLabel("游戏:"))
        self.game_combo = ComboBox()
        for plugin_id, plugin in self._plugin_manager.get_all_plugins().items():
            self.game_combo.addItem(plugin.display_name, userData=plugin_id)
        form_layout.addWidget(self.game_combo)

        form_layout.addWidget(BodyLabel("Cron:"))
        self.cron_edit = LineEdit()
        self.cron_edit.setPlaceholderText("如: 0 4 * * * (每天4:00)")
        self.cron_edit.setFixedWidth(200)
        form_layout.addWidget(self.cron_edit)

        self.add_btn = PrimaryPushButton(FluentIcon.ADD, "添加")
        self.add_btn.clicked.connect(self._on_add)
        apply_button_style(self.add_btn, prominent=True)
        form_layout.addWidget(self.add_btn)

        layout.addWidget(form_card)

        # Common cron presets
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(CaptionLabelHelper("常用: "))
        presets = [
            ("每天 04:00", "0 4 * * *"),
            ("每天 06:00", "0 6 * * *"),
            ("每天 12:00", "0 12 * * *"),
            ("每天 22:00", "0 22 * * *"),
        ]
        for label, cron in presets:
            btn = PushButton(label)
            apply_button_style(btn)
            btn.clicked.connect(lambda checked, c=cron: self.cron_edit.setText(c))
            preset_layout.addWidget(btn)
        preset_layout.addStretch()
        layout.addLayout(preset_layout)

        # Table
        self._model = ScheduleTableModel(self._scheduler, self._plugin_manager)
        self.table = TableView()
        self.table.setModel(self._model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table, 1)

        # Delete button
        del_layout = QHBoxLayout()
        del_layout.addStretch()
        self.del_btn = PushButton(FluentIcon.DELETE, "删除选中")
        self.del_btn.clicked.connect(self._on_delete)
        apply_button_style(self.del_btn)
        del_layout.addWidget(self.del_btn)

        self.toggle_btn = PushButton(FluentIcon.SYNC, "启用/禁用")
        self.toggle_btn.clicked.connect(self._on_toggle)
        apply_button_style(self.toggle_btn)
        del_layout.addWidget(self.toggle_btn)

        layout.addLayout(del_layout)

    def _on_add(self):
        plugin_id = self.game_combo.currentData()
        cron = self.cron_edit.text().strip()
        if not cron:
            InfoBar.warning("提示", "请输入 Cron 表达式", parent=self,
                            position=InfoBarPosition.TOP)
            return

        plugin = self._plugin_manager.get_plugin(plugin_id)
        if not plugin:
            return

        task_ids = [t.id for t in plugin.get_available_tasks() if t.default_enabled]
        entry = ScheduleEntry(
            id=f"sched_{uuid.uuid4().hex[:8]}",
            plugin_id=plugin_id,
            task_ids=task_ids,
            cron=cron,
            enabled=True,
        )

        try:
            self._scheduler.add_schedule(entry)
            self._model.refresh()
            self.cron_edit.clear()
            InfoBar.success("添加成功", f"已添加 {plugin.display_name} 的定时任务",
                            parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error("添加失败", str(e), parent=self,
                          position=InfoBarPosition.TOP)

    def _on_delete(self):
        indexes = self.table.selectedIndexes()
        if not indexes:
            return
        row = indexes[0].row()
        entry = self._model.get_entry(row)
        self._scheduler.remove_schedule(entry.id)
        self._model.refresh()

    def _on_toggle(self):
        indexes = self.table.selectedIndexes()
        if not indexes:
            return
        row = indexes[0].row()
        entry = self._model.get_entry(row)
        entry.enabled = not entry.enabled
        self._scheduler.update_schedule(entry)
        self._model.refresh()


class CaptionLabelHelper(BodyLabel):
    """Small helper label for preset row."""
    pass
