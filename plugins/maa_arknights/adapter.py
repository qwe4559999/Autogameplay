import json
import os
import subprocess
import time
from datetime import datetime
from typing import Callable, Optional

from plugins.base import GamePlugin, PluginStatus, TaskDefinition, TaskResult


class MaaArknightsPlugin(GamePlugin):
    """Adapter for MaaAssistantArknights (MAA) - Arknights daily automation.

    Uses subprocess + gui.json config injection:
    1. Set Start.RunDirectly=True in gui.json so MAA auto-starts tasks on launch
    2. Launch MAA.exe as subprocess
    3. Monitor debug/gui.log for task completion
    4. Restore original config after completion
    """

    @property
    def plugin_id(self) -> str:
        return "maa_arknights"

    @property
    def display_name(self) -> str:
        return "明日方舟 (MAA)"

    @property
    def game_name(self) -> str:
        return "明日方舟"

    @property
    def icon_name(self) -> str:
        return "arknights.png"

    def _gui_json_path(self) -> str:
        return os.path.join(self.get_install_path(), "config", "gui.json")

    def _gui_log_path(self) -> str:
        return os.path.join(self.get_install_path(), "debug", "gui.log")

    def _read_gui_json(self) -> dict:
        path = self._gui_json_path()
        if not os.path.isfile(path):
            return {}
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    def _write_gui_json(self, data: dict) -> None:
        path = self._gui_json_path()
        with open(path, "w", encoding="utf-8-sig") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_current_profile(self, data: dict) -> str:
        return data.get("Current", "Default")

    def validate_installation(self) -> tuple[bool, str]:
        install_path = self.get_install_path()
        if not install_path:
            return False, "未配置 MAA 安装路径"

        exe_path = os.path.join(install_path, self.get_executable() or "MAA.exe")
        if not os.path.isfile(exe_path):
            return False, f"未找到 MAA.exe: {exe_path}"

        gui_json = self._gui_json_path()
        if not os.path.isfile(gui_json):
            return False, f"未找到 gui.json: {gui_json}"

        return True, "MAA 安装验证通过"

    def get_available_tasks(self) -> list[TaskDefinition]:
        return [
            TaskDefinition("daily", "执行已配置的日常任务",
                           "启动 MAA 自动运行其中已勾选的所有任务 (在 MAA 中配置)"),
        ]

    def run_tasks(self, task_ids: list[str], callback: Callable[[str, str], None]) -> TaskResult:
        start_time = datetime.now().isoformat()
        self._status = PluginStatus.RUNNING

        valid, msg = self.validate_installation()
        if not valid:
            self._status = PluginStatus.FAILED
            return TaskResult(self.plugin_id, "daily", PluginStatus.FAILED,
                              start_time, datetime.now().isoformat(), msg)

        install_path = self.get_install_path()
        exe_name = self.get_executable() or "MAA.exe"
        exe_path = os.path.join(install_path, exe_name)

        # Step 1: Inject Start.RunDirectly=True into gui.json
        callback("info", "正在配置 MAA 自动运行...")
        original_run_directly = None
        try:
            gui_data = self._read_gui_json()
            profile = self._get_current_profile(gui_data)
            config = gui_data.get("Configurations", {}).get(profile, {})
            original_run_directly = config.get("Start.RunDirectly", "False")
            config["Start.RunDirectly"] = "True"
            self._write_gui_json(gui_data)
            callback("info", f"已设置 Start.RunDirectly=True (配置档: {profile})")
        except Exception as e:
            self._status = PluginStatus.FAILED
            return TaskResult(self.plugin_id, "daily", PluginStatus.FAILED,
                              start_time, datetime.now().isoformat(),
                              f"修改 gui.json 失败: {e}")

        # Step 2: Record gui.log current position for monitoring
        gui_log_path = self._gui_log_path()
        log_offset = 0
        if os.path.isfile(gui_log_path):
            log_offset = os.path.getsize(gui_log_path)

        # Step 3: Launch MAA.exe
        callback("info", f"启动 MAA: {exe_path}")
        try:
            self._process = subprocess.Popen(
                [exe_path],
                cwd=install_path,
            )
            callback("info", f"MAA 进程已启动 (PID: {self._process.pid})")
        except Exception as e:
            self._restore_config(gui_data, profile, original_run_directly)
            self._status = PluginStatus.FAILED
            return TaskResult(self.plugin_id, "daily", PluginStatus.FAILED,
                              start_time, datetime.now().isoformat(),
                              f"启动 MAA 失败: {e}")

        # Step 4: Monitor gui.log for completion
        callback("info", "正在监控 MAA 任务执行...")
        completed = False
        failed = False
        self._maa_pid = None  # Track PID for update-restart scenario
        try:
            while True:
                # Check if we've been stopped
                if self._status == PluginStatus.STOPPED:
                    break

                # Check if MAA process exited
                if not self._is_maa_alive():
                    old_pid = self._process.pid if self._process else self._maa_pid
                    exit_info = f"退出码: {self._process.returncode}" if self._process else "PID 已消失"
                    callback("info", f"MAA 进程已退出 ({exit_info})")

                    # Final log read to check for completion or restart signal
                    new_offset, found_complete, found_error, found_restarting = \
                        self._read_new_log_lines(gui_log_path, log_offset, callback)
                    log_offset = new_offset

                    if found_complete:
                        completed = True
                        callback("info", "MAA 任务已全部完成！")
                        break

                    if found_restarting:
                        # MAA is restarting after an update — wait for new process
                        callback("info", "MAA 正在更新重启，等待新进程...")
                        self._process = None
                        new_pid = None
                        for _ in range(30):  # Wait up to 30 seconds
                            time.sleep(1)
                            if self._status == PluginStatus.STOPPED:
                                break
                            new_pid = self._find_maa_process(exclude_pid=old_pid)
                            if new_pid:
                                break

                        if new_pid:
                            callback("info", f"检测到新 MAA 进程 (PID: {new_pid})")
                            self._maa_pid = new_pid
                            continue  # Continue monitoring loop
                        else:
                            callback("warning", "等待新 MAA 进程超时")
                            break
                    else:
                        # Normal exit, not an update restart
                        break

                # Read new log lines
                new_offset, found_complete, found_error, found_restarting = \
                    self._read_new_log_lines(gui_log_path, log_offset, callback)
                log_offset = new_offset

                if found_complete:
                    completed = True
                    callback("info", "MAA 任务已全部完成！")
                    break
                if found_error:
                    failed = True
                    callback("error", "MAA 任务执行出错")
                    break

                time.sleep(2)

        finally:
            # Step 5: Restore gui.json
            try:
                gui_data = self._read_gui_json()
                self._restore_config(gui_data, profile, original_run_directly)
                callback("info", "已恢复 MAA 配置")
            except Exception:
                callback("warning", "恢复 gui.json 失败，请手动检查 Start.RunDirectly 设置")

        # Step 6: Auto-close MAA and emulator after completion
        if completed or failed:
            self._cleanup_processes(gui_data, profile, callback)

        end_time = datetime.now().isoformat()

        if self._status == PluginStatus.STOPPED:
            return TaskResult(self.plugin_id, "daily", PluginStatus.STOPPED,
                              start_time, end_time, "任务已手动停止")
        elif completed:
            self._status = PluginStatus.SUCCESS
            return TaskResult(self.plugin_id, "daily", PluginStatus.SUCCESS,
                              start_time, end_time, "MAA 日常任务执行完成")
        elif failed:
            self._status = PluginStatus.FAILED
            return TaskResult(self.plugin_id, "daily", PluginStatus.FAILED,
                              start_time, end_time, "MAA 任务执行出错")
        else:
            # Process exited but no clear completion/error signal
            self._status = PluginStatus.SUCCESS
            return TaskResult(self.plugin_id, "daily", PluginStatus.SUCCESS,
                              start_time, end_time, "MAA 进程已退出")

    def _find_maa_process(self, exclude_pid: int = None) -> Optional[int]:
        """Find a running MAA.exe process, optionally excluding a known PID."""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq MAA.exe", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().splitlines():
                parts = line.strip('"').split('","')
                if len(parts) >= 2:
                    pid = int(parts[1])
                    if exclude_pid and pid == exclude_pid:
                        continue
                    return pid
        except Exception:
            pass
        return None

    def _is_maa_alive(self) -> bool:
        """Check if the monitored MAA process is still running."""
        if self._process is not None:
            return self._process.poll() is None
        if getattr(self, '_maa_pid', None):
            return self._find_maa_process() is not None
        return False

    def _read_new_log_lines(self, log_path: str, offset: int,
                            callback: Callable[[str, str], None]) -> tuple[int, bool, bool, bool]:
        """Read new lines from gui.log starting at offset.
        Returns (new_offset, found_complete, found_error, found_restarting).
        """
        found_complete = False
        found_error = False
        found_restarting = False

        if not os.path.isfile(log_path):
            return offset, False, False, False

        try:
            file_size = os.path.getsize(log_path)
            if file_size <= offset:
                return offset, False, False, False

            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                new_data = f.read()
                new_offset = f.tell()

            for line in new_data.splitlines():
                line = line.strip()
                if not line:
                    continue

                # Extract meaningful log content (format: "timestamp [LEVEL][Source] message")
                if "任务已全部完成" in line:
                    found_complete = True
                elif "TaskQueueViewModel" in line and "Error" in line:
                    found_error = True
                if "restarting application" in line.lower():
                    found_restarting = True

                # Forward interesting log lines to UI
                if any(kw in line for kw in [
                    "任务已全部完成", "开始任务", "任务出错", "连接",
                    "LinkStart", "TaskChain", "完成", "Error",
                    "启动模拟器", "唤醒", "理智", "公招", "基建", "信用", "奖励",
                    "更新", "update", "restarting", "Pending",
                ]):
                    # Clean up the log line - extract just the message part
                    msg = line
                    if "]" in msg:
                        # Remove timestamp and tag prefixes
                        parts = msg.split("]")
                        if len(parts) >= 3:
                            msg = "]".join(parts[2:]).strip()
                        elif len(parts) >= 2:
                            msg = parts[-1].strip()
                    if msg:
                        callback("info", msg)

            return new_offset, found_complete, found_error, found_restarting

        except Exception:
            return offset, False, False, False

    def _restore_config(self, gui_data: dict, profile: str, original_value: str) -> None:
        """Restore Start.RunDirectly to its original value."""
        if original_value is not None:
            config = gui_data.get("Configurations", {}).get(profile, {})
            config["Start.RunDirectly"] = original_value
            self._write_gui_json(gui_data)

    def _cleanup_processes(self, gui_data: dict, profile: str,
                           callback: Callable[[str, str], None]) -> None:
        """Close MAA and emulator processes after task completion."""
        # Close MAA — via Popen handle or taskkill by name
        if self._process and self._process.poll() is None:
            callback("info", "正在关闭 MAA...")
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
            callback("info", "MAA 已关闭")
        elif getattr(self, '_maa_pid', None) or self._find_maa_process():
            callback("info", "正在关闭 MAA...")
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "MAA.exe"],
                    capture_output=True, timeout=10,
                )
            except Exception:
                pass
            callback("info", "MAA 已关闭")
        self._process = None
        self._maa_pid = None

        # Close emulator
        config = gui_data.get("Configurations", {}).get(profile, {})
        connect_config = config.get("Connect.ConnectConfig", "")

        # Determine which emulator processes to kill
        emulator_processes = []
        if "MuMu" in connect_config or "MuMu" in config.get("Connect.MuMu12EmulatorPath", ""):
            emulator_processes = ["MuMuPlayer.exe", "MuMuVMMHeadless.exe", "MuMuVMMSVC.exe"]
        elif "Bluestacks" in connect_config:
            emulator_processes = ["HD-Player.exe"]
        elif "LDPlayer" in connect_config or "Ld" in connect_config:
            emulator_processes = ["dnplayer.exe", "LdVBoxHeadless.exe"]
        elif "Nox" in connect_config:
            emulator_processes = ["Nox.exe", "NoxVMHandle.exe"]

        if emulator_processes:
            time.sleep(2)  # Give MAA time to fully close
            callback("info", f"正在关闭模拟器 ({connect_config})...")
            for proc_name in emulator_processes:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", proc_name],
                        capture_output=True, timeout=10,
                    )
                except Exception:
                    pass
            callback("info", "模拟器已关闭")

    def stop(self) -> None:
        self._status = PluginStatus.STOPPED
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        elif getattr(self, '_maa_pid', None) or self._find_maa_process():
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "MAA.exe"],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass


def get_plugin() -> GamePlugin:
    return MaaArknightsPlugin()
