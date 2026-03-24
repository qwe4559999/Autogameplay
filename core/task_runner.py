import logging
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from plugins.base import GamePlugin, PluginStatus, TaskResult
from core.plugin_manager import PluginManager

logger = logging.getLogger(__name__)


class TaskWorker(QThread):
    """Runs a plugin's tasks in a background thread."""

    log_message = pyqtSignal(str, str, str)  # plugin_id, level, message
    task_finished = pyqtSignal(str, object)  # plugin_id, TaskResult

    def __init__(self, plugin: GamePlugin, task_ids: list[str]):
        super().__init__()
        self._plugin = plugin
        self._task_ids = task_ids

    def run(self):
        def callback(level: str, message: str):
            self.log_message.emit(self._plugin.plugin_id, level, message)

        try:
            result = self._plugin.run_tasks(self._task_ids, callback)
            self.task_finished.emit(self._plugin.plugin_id, result)
        except Exception as e:
            logger.exception(f"Task execution error for {self._plugin.plugin_id}")
            result = TaskResult(
                self._plugin.plugin_id,
                ",".join(self._task_ids),
                PluginStatus.FAILED,
                message=str(e),
            )
            self.task_finished.emit(self._plugin.plugin_id, result)


class TaskRunner(QObject):
    """Manages task execution across plugins. Only one task per plugin at a time.

    Inherits QObject so that signal/slot connections use QueuedConnection
    when crossing thread boundaries, making UI updates thread-safe.
    """

    log_received = pyqtSignal(str, str, str)    # plugin_id, level, message
    task_started = pyqtSignal(str)               # plugin_id
    task_completed = pyqtSignal(str, object)     # plugin_id, TaskResult

    def __init__(self, plugin_manager: PluginManager, parent: QObject = None):
        super().__init__(parent)
        self._plugin_manager = plugin_manager
        self._workers: dict[str, TaskWorker] = {}
        self._external_running: set[str] = set()

    def is_running(self, plugin_id: str) -> bool:
        worker = self._workers.get(plugin_id)
        return (worker is not None and worker.isRunning()) or plugin_id in self._external_running

    def any_running(self) -> bool:
        return any(w.isRunning() for w in self._workers.values()) or bool(self._external_running)

    def start_tasks(self, plugin_id: str, task_ids: list[str]) -> bool:
        """Start tasks for a plugin. Returns False if already running."""
        if self.is_running(plugin_id):
            return False

        plugin = self._plugin_manager.get_plugin(plugin_id)
        if not plugin:
            return False

        plugin._status = PluginStatus.RUNNING
        worker = TaskWorker(plugin, task_ids)
        # Connect worker signals → TaskRunner signals (queued across threads)
        worker.log_message.connect(self.log_received)
        worker.task_finished.connect(self._on_task_finished)
        self._workers[plugin_id] = worker
        worker.start()
        self.task_started.emit(plugin_id)
        return True

    def stop_tasks(self, plugin_id: str) -> None:
        """Stop running tasks for a plugin."""
        plugin = self._plugin_manager.get_plugin(plugin_id)
        if plugin:
            plugin.stop()

    def stop_all(self) -> None:
        for plugin_id in list(self._workers.keys()):
            self.stop_tasks(plugin_id)
        for plugin_id in list(self._external_running):
            self.stop_tasks(plugin_id)

    def begin_external_task(self, plugin_id: str) -> bool:
        """Mark a non-TaskWorker execution path as running and emit task_started."""
        if self.is_running(plugin_id):
            return False

        plugin = self._plugin_manager.get_plugin(plugin_id)
        if not plugin:
            return False

        plugin._status = PluginStatus.RUNNING
        self._external_running.add(plugin_id)
        self.task_started.emit(plugin_id)
        return True

    def emit_log(self, plugin_id: str, level: str, message: str) -> None:
        self.log_received.emit(plugin_id, level, message)

    def finish_external_task(self, plugin_id: str, result: TaskResult) -> None:
        self._external_running.discard(plugin_id)
        plugin = self._plugin_manager.get_plugin(plugin_id)
        if plugin:
            plugin._status = result.status
        self.task_completed.emit(plugin_id, result)

    def _on_task_finished(self, plugin_id: str, result: TaskResult) -> None:
        self._workers.pop(plugin_id, None)
        plugin = self._plugin_manager.get_plugin(plugin_id)
        if plugin:
            plugin._status = result.status
        self.task_completed.emit(plugin_id, result)


class SequentialRunner(QThread):
    """Runs multiple plugins sequentially (for scheduled 'Run All' tasks)."""
    all_finished = pyqtSignal(list)  # list of TaskResult

    def __init__(self, plugins: list[tuple[GamePlugin, list[str]]], task_runner: TaskRunner):
        super().__init__()
        self._plugins = plugins  # [(plugin, task_ids), ...]
        self._task_runner = task_runner
        self._stopped = False

    def run(self):
        results = []
        for plugin, task_ids in self._plugins:
            if self._stopped:
                break

            if not self._task_runner.begin_external_task(plugin.plugin_id):
                self._task_runner.emit_log(
                    plugin.plugin_id, "warning", f"{plugin.display_name} 已有任务在运行，跳过本次执行"
                )
                continue

            def callback(level: str, message: str, _pid=plugin.plugin_id):
                self._task_runner.emit_log(_pid, level, message)

            self._task_runner.emit_log(plugin.plugin_id, "info",
                                       f"开始执行 {plugin.display_name} 的任务...")
            try:
                result = plugin.run_tasks(task_ids, callback)
            except Exception as e:
                logger.exception("Sequential task execution error for %s", plugin.plugin_id)
                result = TaskResult(
                    plugin.plugin_id,
                    ",".join(task_ids),
                    PluginStatus.FAILED,
                    message=str(e),
                )

            results.append(result)
            self._task_runner.finish_external_task(plugin.plugin_id, result)

            if result.status == PluginStatus.FAILED:
                self._task_runner.emit_log(plugin.plugin_id, "error",
                                           f"{plugin.display_name} 任务失败: {result.message}")

        self.all_finished.emit(results)

    def stop(self):
        self._stopped = True
        for plugin, _ in self._plugins:
            plugin.stop()
