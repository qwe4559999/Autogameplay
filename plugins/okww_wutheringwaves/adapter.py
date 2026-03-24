import os
import subprocess
from datetime import datetime
from typing import Callable, Optional

from plugins.base import GamePlugin, PluginStatus, TaskDefinition, TaskResult


class OkwwWutheringWavesPlugin(GamePlugin):
    """Adapter for ok-wuthering-waves (OKWW) - Wuthering Waves daily automation."""

    @property
    def plugin_id(self) -> str:
        return "okww_wutheringwaves"

    @property
    def display_name(self) -> str:
        return "鸣潮 (OKWW)"

    @property
    def game_name(self) -> str:
        return "鸣潮"

    @property
    def icon_name(self) -> str:
        return "wutheringwaves.png"

    def validate_installation(self) -> tuple[bool, str]:
        install_path = self.get_install_path()
        if not install_path:
            return False, "未配置 OKWW 安装路径"

        exe_path = os.path.join(install_path, self.get_executable() or "ok-ww.exe")
        if not os.path.isfile(exe_path):
            return False, f"未找到可执行文件: {exe_path}"

        return True, "OKWW 安装验证通过"

    def get_available_tasks(self) -> list[TaskDefinition]:
        return [
            TaskDefinition("daily", "一键日常", "启动 OKWW 执行日常任务 (自动退出模式)"),
            TaskDefinition("farm", "刷本", "启动 OKWW 执行刷本任务"),
        ]

    def _get_task_args(self, task_id: str) -> list[str]:
        """Map task_id to OKWW CLI arguments."""
        task_map = {
            "daily": ["-t", "1", "-e"],  # task 1 with auto-exit
            "farm": ["-t", "2", "-e"],
        }
        return task_map.get(task_id, ["-t", "1", "-e"])

    def run_tasks(self, task_ids: list[str], callback: Callable[[str, str], None]) -> TaskResult:
        start_time = datetime.now().isoformat()
        self._status = PluginStatus.RUNNING

        valid, msg = self.validate_installation()
        if not valid:
            self._status = PluginStatus.FAILED
            return TaskResult(self.plugin_id, ",".join(task_ids), PluginStatus.FAILED,
                              start_time, datetime.now().isoformat(), msg)

        install_path = self.get_install_path()
        exe_name = self.get_executable() or "ok-ww.exe"
        exe_path = os.path.join(install_path, exe_name)

        # Run tasks sequentially
        for task_id in task_ids:
            if self._status == PluginStatus.STOPPED:
                break

            args = self._get_task_args(task_id)
            cmd = [exe_path] + args
            callback("info", f"启动 OKWW: {' '.join(cmd)}")

            try:
                self._process = subprocess.Popen(
                    cmd,
                    cwd=install_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                callback("info", f"OKWW 进程已启动 (PID: {self._process.pid})")

                if self._process.stdout:
                    for line in self._process.stdout:
                        line = line.strip()
                        if line:
                            callback("info", line)

                return_code = self._process.wait()

                if self._status == PluginStatus.STOPPED:
                    return TaskResult(self.plugin_id, ",".join(task_ids), PluginStatus.STOPPED,
                                      start_time, datetime.now().isoformat(), "任务已手动停止")

                if return_code != 0:
                    self._status = PluginStatus.FAILED
                    return TaskResult(self.plugin_id, task_id, PluginStatus.FAILED,
                                      start_time, datetime.now().isoformat(),
                                      f"OKWW 任务 {task_id} 退出码: {return_code}")

                callback("info", f"任务 {task_id} 完成")

            except Exception as e:
                self._status = PluginStatus.FAILED
                return TaskResult(self.plugin_id, task_id, PluginStatus.FAILED,
                                  start_time, datetime.now().isoformat(), str(e))
            finally:
                self._process = None

        end_time = datetime.now().isoformat()
        if self._status == PluginStatus.RUNNING:
            self._status = PluginStatus.SUCCESS
        return TaskResult(self.plugin_id, ",".join(task_ids), self._status,
                          start_time, end_time, "OKWW 所有任务执行完成")

    def stop(self) -> None:
        self._status = PluginStatus.STOPPED
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()


def get_plugin() -> GamePlugin:
    return OkwwWutheringWavesPlugin()
