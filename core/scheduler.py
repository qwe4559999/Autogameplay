import logging
from typing import Optional

from apscheduler.schedulers.qt import QtScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore

from core.models import ScheduleEntry
from core.config_manager import ConfigManager
from core.plugin_manager import PluginManager
from core.task_runner import TaskRunner

logger = logging.getLogger(__name__)


class Scheduler:
    """Wraps APScheduler for cron-based daily task automation."""

    def __init__(self, config: ConfigManager, plugin_manager: PluginManager,
                 task_runner: TaskRunner):
        self._config = config
        self._plugin_manager = plugin_manager
        self._task_runner = task_runner
        self._scheduler = QtScheduler()
        self._scheduler.add_jobstore(MemoryJobStore(), "default")

    def start(self) -> None:
        """Load schedules from config and start the scheduler."""
        self._load_schedules()
        self._scheduler.start()
        logger.info("Scheduler started")

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    def reload(self) -> None:
        """Reload all schedules from config."""
        self._scheduler.remove_all_jobs()
        self._load_schedules()

    def add_schedule(self, entry: ScheduleEntry) -> None:
        self._config.add_schedule(entry)
        self._config.save()
        if entry.enabled:
            self._add_job(entry)

    def remove_schedule(self, schedule_id: str) -> None:
        try:
            self._scheduler.remove_job(schedule_id)
        except Exception:
            pass
        self._config.remove_schedule(schedule_id)
        self._config.save()

    def update_schedule(self, entry: ScheduleEntry) -> None:
        try:
            self._scheduler.remove_job(entry.id)
        except Exception:
            pass
        self._config.update_schedule(entry)
        self._config.save()
        if entry.enabled:
            self._add_job(entry)

    def get_schedules(self) -> list[ScheduleEntry]:
        return self._config.schedules

    def get_next_run(self, schedule_id: str) -> Optional[str]:
        job = self._scheduler.get_job(schedule_id)
        if job and job.next_run_time:
            return job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        return None

    def _load_schedules(self) -> None:
        for entry in self._config.schedules:
            if entry.enabled:
                self._add_job(entry)

    def _add_job(self, entry: ScheduleEntry) -> None:
        try:
            trigger = CronTrigger.from_crontab(entry.cron)
            self._scheduler.add_job(
                self._execute_schedule,
                trigger=trigger,
                id=entry.id,
                args=[entry],
                replace_existing=True,
            )
            logger.info(f"Scheduled job: {entry.id} ({entry.cron})")
        except Exception as e:
            logger.error(f"Failed to schedule {entry.id}: {e}")

    def _execute_schedule(self, entry: ScheduleEntry) -> None:
        """Called by APScheduler when a scheduled time arrives."""
        logger.info(f"Executing scheduled task: {entry.id} -> {entry.plugin_id}")
        self._task_runner.start_tasks(entry.plugin_id, entry.task_ids)
