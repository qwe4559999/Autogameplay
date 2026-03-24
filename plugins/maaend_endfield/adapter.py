import ctypes
import json
import os
import subprocess
import time
from datetime import datetime
from typing import Callable, Optional

from plugins.base import GamePlugin, PluginStatus, TaskDefinition, TaskResult


class MaaEndEndfieldPlugin(GamePlugin):
    """Adapter for MaaEnd - Arknights: Endfield daily automation.

    Uses UAC elevation + config injection + log monitoring:
    1. Optionally launch the game first
    2. Inject autoRunOnLaunch=true into mxu-MaaEnd.json
    3. Launch MaaEnd.exe with UAC elevation (ShellExecuteW + runas)
    4. Monitor debug/go-service.log for "Agent server shutdown"
    5. Restore config and close processes after completion
    """

    @property
    def plugin_id(self) -> str:
        return "maaend_endfield"

    @property
    def display_name(self) -> str:
        return "明日方舟:终末地 (MaaEnd)"

    @property
    def game_name(self) -> str:
        return "明日方舟:终末地"

    @property
    def icon_name(self) -> str:
        return "endfield.png"

    def _config_json_path(self) -> str:
        return os.path.join(self.get_install_path(), "config", "mxu-MaaEnd.json")

    def _go_service_log_path(self) -> str:
        return os.path.join(self.get_install_path(), "debug", "go-service.log")

    def _maa_log_path(self) -> str:
        return os.path.join(self.get_install_path(), "debug", "maa.log")

    def _read_config_json(self) -> dict:
        path = self._config_json_path()
        if not os.path.isfile(path):
            return {}
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    def _write_config_json(self, data: dict) -> None:
        path = self._config_json_path()
        with open(path, "w", encoding="utf-8-sig") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def validate_installation(self) -> tuple[bool, str]:
        install_path = self.get_install_path()
        if not install_path:
            return False, "未配置 MaaEnd 安装路径"

        exe_path = os.path.join(install_path, self.get_executable() or "MaaEnd.exe")
        if not os.path.isfile(exe_path):
            return False, f"未找到可执行文件: {exe_path}"

        config_json = self._config_json_path()
        if not os.path.isfile(config_json):
            return False, f"未找到配置文件: {config_json}"

        return True, "MaaEnd 安装验证通过"

    def get_available_tasks(self) -> list[TaskDefinition]:
        return [
            TaskDefinition("daily", "一键日常", "启动 MaaEnd 执行预配置的日常任务"),
        ]

    def _find_process(self, name: str) -> Optional[int]:
        """Find a running process by image name, return PID or None."""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().splitlines():
                parts = line.strip('"').split('","')
                if len(parts) >= 2:
                    return int(parts[1])
        except Exception:
            pass
        return None

    def _launch_elevated(self, exe_path: str, cwd: str) -> bool:
        """Launch an exe with UAC elevation via ShellExecuteW."""
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe_path, None, cwd, 1  # SW_SHOWNORMAL
        )
        return ret > 32

    def run_tasks(self, task_ids: list[str], callback: Callable[[str, str], None]) -> TaskResult:
        start_time = datetime.now().isoformat()
        self._status = PluginStatus.RUNNING

        valid, msg = self.validate_installation()
        if not valid:
            self._status = PluginStatus.FAILED
            return TaskResult(self.plugin_id, "daily", PluginStatus.FAILED,
                              start_time, datetime.now().isoformat(), msg)

        install_path = self.get_install_path()
        exe_name = self.get_executable() or "MaaEnd.exe"
        exe_path = os.path.join(install_path, exe_name)

        # Step 1: Optionally launch the game
        game_path = self.get_game_path()
        if game_path and os.path.exists(game_path):
            callback("info", f"启动终末地游戏: {game_path}")
            try:
                os.startfile(game_path)
                delay = self.get_game_start_delay()
                callback("info", f"等待游戏启动 ({delay} 秒)...")
                for i in range(delay):
                    if self._status == PluginStatus.STOPPED:
                        return TaskResult(self.plugin_id, "daily", PluginStatus.STOPPED,
                                          start_time, datetime.now().isoformat(), "任务已手动停止")
                    time.sleep(1)
                callback("info", "游戏启动等待完成")
            except Exception as e:
                callback("warning", f"启动游戏失败: {e}，继续尝试启动 MaaEnd...")

        # Step 2: Inject autoRunOnLaunch=true
        callback("info", "正在配置 MaaEnd 自动运行...")
        original_auto_run = None
        try:
            config_data = self._read_config_json()
            original_auto_run = config_data.get("autoRunOnLaunch", False)
            config_data["autoRunOnLaunch"] = True
            self._write_config_json(config_data)
            callback("info", "已设置 autoRunOnLaunch=true")
        except Exception as e:
            self._status = PluginStatus.FAILED
            return TaskResult(self.plugin_id, "daily", PluginStatus.FAILED,
                              start_time, datetime.now().isoformat(),
                              f"修改配置文件失败: {e}")

        # Step 3: Record log positions for monitoring
        go_log_path = self._go_service_log_path()
        maa_log_path = self._maa_log_path()
        go_log_offset = os.path.getsize(go_log_path) if os.path.isfile(go_log_path) else 0
        maa_log_offset = os.path.getsize(maa_log_path) if os.path.isfile(maa_log_path) else 0

        # Step 4: Launch MaaEnd with UAC elevation
        callback("info", f"启动 MaaEnd (需要管理员权限): {exe_path}")
        try:
            success = self._launch_elevated(exe_path, install_path)
            if not success:
                raise RuntimeError("ShellExecuteW 返回错误 (用户可能取消了 UAC)")
            callback("info", "MaaEnd UAC 提权启动请求已发送")
        except Exception as e:
            self._restore_config(config_data, original_auto_run)
            self._status = PluginStatus.FAILED
            return TaskResult(self.plugin_id, "daily", PluginStatus.FAILED,
                              start_time, datetime.now().isoformat(),
                              f"启动 MaaEnd 失败: {e}")

        # Wait for MaaEnd process to appear
        callback("info", "等待 MaaEnd 进程启动...")
        maaend_pid = None
        for _ in range(15):
            time.sleep(1)
            if self._status == PluginStatus.STOPPED:
                break
            maaend_pid = self._find_process("MaaEnd.exe")
            if maaend_pid:
                break

        if not maaend_pid:
            self._restore_config(config_data, original_auto_run)
            if self._status == PluginStatus.STOPPED:
                return TaskResult(self.plugin_id, "daily", PluginStatus.STOPPED,
                                  start_time, datetime.now().isoformat(), "任务已手动停止")
            self._status = PluginStatus.FAILED
            return TaskResult(self.plugin_id, "daily", PluginStatus.FAILED,
                              start_time, datetime.now().isoformat(),
                              "MaaEnd 进程未启动（UAC 可能被取消）")

        callback("info", f"MaaEnd 进程已启动 (PID: {maaend_pid})")

        # Step 5: Monitor logs for completion
        callback("info", "正在监控 MaaEnd 任务执行...")
        completed = False
        failed = False
        try:
            while True:
                if self._status == PluginStatus.STOPPED:
                    break

                # Check if MaaEnd process is still alive
                if not self._find_process("MaaEnd.exe"):
                    callback("info", "MaaEnd 进程已退出")
                    # Final log check
                    _, found_shutdown = self._read_go_service_log(
                        go_log_path, go_log_offset, callback)
                    self._read_maa_log(maa_log_path, maa_log_offset, callback)
                    if found_shutdown:
                        completed = True
                        callback("info", "MaaEnd 任务已全部完成！")
                    break

                # Read go-service.log for completion signal
                new_go_offset, found_shutdown = self._read_go_service_log(
                    go_log_path, go_log_offset, callback)
                go_log_offset = new_go_offset

                # Read maa.log for task progress
                new_maa_offset, found_error = self._read_maa_log(
                    maa_log_path, maa_log_offset, callback)
                maa_log_offset = new_maa_offset

                if found_shutdown:
                    completed = True
                    callback("info", "MaaEnd 任务已全部完成！")
                    break

                time.sleep(2)

        finally:
            # Step 6: Restore config
            try:
                config_data = self._read_config_json()
                self._restore_config(config_data, original_auto_run)
                callback("info", "已恢复 MaaEnd 配置")
            except Exception:
                callback("warning", "恢复配置文件失败，请手动检查 autoRunOnLaunch 设置")

        # Step 7: Auto-close processes
        if completed or failed:
            self._cleanup_processes(callback)

        end_time = datetime.now().isoformat()

        if self._status == PluginStatus.STOPPED:
            return TaskResult(self.plugin_id, "daily", PluginStatus.STOPPED,
                              start_time, end_time, "任务已手动停止")
        elif completed:
            self._status = PluginStatus.SUCCESS
            return TaskResult(self.plugin_id, "daily", PluginStatus.SUCCESS,
                              start_time, end_time, "MaaEnd 日常任务执行完成")
        elif failed:
            self._status = PluginStatus.FAILED
            return TaskResult(self.plugin_id, "daily", PluginStatus.FAILED,
                              start_time, end_time, "MaaEnd 任务执行出错")
        else:
            self._status = PluginStatus.SUCCESS
            return TaskResult(self.plugin_id, "daily", PluginStatus.SUCCESS,
                              start_time, end_time, "MaaEnd 进程已退出")

    def _read_go_service_log(self, log_path: str, offset: int,
                              callback: Callable[[str, str], None]) -> tuple[int, bool]:
        """Read go-service.log for completion signal.
        Returns (new_offset, found_shutdown).
        """
        found_shutdown = False

        if not os.path.isfile(log_path):
            return offset, False

        try:
            file_size = os.path.getsize(log_path)
            if file_size <= offset:
                return offset, False

            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                new_data = f.read()
                new_offset = f.tell()

            for line in new_data.splitlines():
                line = line.strip()
                if not line:
                    continue

                if "Agent server shutdown" in line:
                    found_shutdown = True

            return new_offset, found_shutdown

        except Exception:
            return offset, False

    def _read_maa_log(self, log_path: str, offset: int,
                       callback: Callable[[str, str], None]) -> tuple[int, bool]:
        """Read maa.log for task progress.
        Returns (new_offset, found_error).
        """
        found_error = False

        if not os.path.isfile(log_path):
            return offset, False

        try:
            file_size = os.path.getsize(log_path)
            if file_size <= offset:
                return offset, False

            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                new_data = f.read()
                new_offset = f.tell()

            for line in new_data.splitlines():
                line = line.strip()
                if not line:
                    continue

                # Forward task status to UI
                if "Tasker.Task.Succeeded" in line:
                    # Extract task entry name from JSON details
                    entry = self._extract_entry(line)
                    if entry:
                        callback("info", f"任务完成: {entry}")
                elif "Tasker.Task.Failed" in line:
                    entry = self._extract_entry(line)
                    if entry:
                        callback("warning", f"任务失败: {entry}")
                elif "Tasker.Task.Starting" in line:
                    entry = self._extract_entry(line)
                    if entry:
                        callback("info", f"开始任务: {entry}")

            return new_offset, found_error

        except Exception:
            return offset, False

    def _extract_entry(self, line: str) -> str:
        """Extract task entry name from a log line containing JSON details."""
        try:
            # Find JSON in the log line: details={"entry":"xxx",...}
            idx = line.find('"entry":"')
            if idx >= 0:
                start = idx + len('"entry":"')
                end = line.index('"', start)
                return line[start:end]
        except (ValueError, IndexError):
            pass
        return ""

    def _restore_config(self, config_data: dict, original_value) -> None:
        """Restore autoRunOnLaunch to its original value."""
        if original_value is not None:
            config_data["autoRunOnLaunch"] = original_value
            self._write_config_json(config_data)

    def _cleanup_processes(self, callback: Callable[[str, str], None]) -> None:
        """Close MaaEnd and game processes after task completion."""
        # Close MaaEnd and its child processes
        for proc_name in ["MaaEnd.exe", "go-service.exe", "cpp-algo.exe"]:
            if self._find_process(proc_name):
                callback("info", f"正在关闭 {proc_name}...")
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", proc_name],
                        capture_output=True, timeout=10,
                    )
                except Exception:
                    pass

        callback("info", "MaaEnd 已关闭")

        # Close the game - find by window title "Endfield"
        time.sleep(2)
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "WINDOWTITLE eq Endfield", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().splitlines():
                parts = line.strip('"').split('","')
                if len(parts) >= 2 and parts[0] != "INFO:":
                    game_proc = parts[0]
                    callback("info", f"正在关闭终末地游戏 ({game_proc})...")
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/IM", game_proc],
                            capture_output=True, timeout=10,
                        )
                    except Exception:
                        pass
                    callback("info", "终末地游戏已关闭")
                    break
        except Exception:
            pass

    def stop(self) -> None:
        self._status = PluginStatus.STOPPED
        # Kill MaaEnd and its child processes
        for proc_name in ["MaaEnd.exe", "go-service.exe", "cpp-algo.exe"]:
            if self._find_process(proc_name):
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", proc_name],
                        capture_output=True, timeout=5,
                    )
                except Exception:
                    pass


def get_plugin() -> GamePlugin:
    return MaaEndEndfieldPlugin()
