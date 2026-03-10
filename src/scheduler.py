"""Scheduler for heartbeat checks - Multi-user support."""
import logging
import threading
from datetime import datetime, timezone
from typing import Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from . import config
from .storage import get_user_storage, get_user_registry
from .time_utils import get_local_now, is_within_quiet_hours, next_quiet_hours_end

logger = logging.getLogger(__name__)


def _get_claude_module():
    """Import Claude integration lazily to reduce cold-start cost."""
    from . import claude
    return claude


class MultiUserHeartbeatScheduler:
    """Manages periodic heartbeat checks for multiple users."""

    def __init__(self, telegram_bot):
        """
        Initialize the multi-user scheduler.

        Args:
            telegram_bot: TelegramBot instance for sending messages
        """
        self.telegram_bot = telegram_bot
        self.scheduler = AsyncIOScheduler()

        # Per-user enabled state (user_id -> bool)
        self.user_states: Dict[str, bool] = {}
        self.state_lock = threading.Lock()

        logger.info("Initialized Multi-User Heartbeat Scheduler")

    async def heartbeat_job(self, user_id: str):
        """
        Job that runs on each heartbeat for a specific user.

        Args:
            user_id: The user ID to process heartbeat for
        """
        try:
            logger.info("=" * 50)
            logger.info(f"HEARTBEAT TRIGGERED for user {user_id}")
            logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
            logger.info("=" * 50)

            # Check if enabled for this user
            if not self.is_enabled(user_id):
                logger.info(f"Heartbeat disabled for user {user_id}, skipping")
                return

            # Get user-specific storage and config
            user_storage = get_user_storage(user_id)
            user_config = user_storage.config.get_config()

            if is_within_quiet_hours(user_config):
                local_now = get_local_now(user_config.timezone)
                quiet_end = next_quiet_hours_end(user_config)
                quiet_end_text = quiet_end.strftime("%Y-%m-%d %H:%M %Z") if quiet_end else "unknown"
                logger.info(
                    "Heartbeat suppressed for user %s during quiet hours "
                    "(local=%s, quiet window=%s-%s, resumes=%s)",
                    user_id,
                    local_now.strftime("%Y-%m-%d %H:%M %Z"),
                    user_config.quiet_hours_start,
                    user_config.quiet_hours_end,
                    quiet_end_text,
                )
                return

            # Process heartbeat with user context
            claude = _get_claude_module()
            await claude.process_heartbeat(
                telegram_bot=self.telegram_bot,
                user_id=user_id,
                user_storage=user_storage,
                user_config=user_config
            )

            logger.info(f"Heartbeat completed successfully for user {user_id}")

        except Exception as e:
            logger.error(f"Error in heartbeat job for user {user_id}: {e}", exc_info=True)

    def add_user(
        self,
        user_id: str,
        interval_minutes: int = None,
        enabled: bool = True
    ):
        """
        Add a user to the scheduler with their own interval.

        Args:
            user_id: User to add
            interval_minutes: Heartbeat interval for this user (defaults to config value)
            enabled: Whether heartbeats are enabled for this user
        """
        if interval_minutes is None:
            interval_minutes = config.get_heartbeat_interval()

        job_id = f"heartbeat_{user_id}"

        self.scheduler.add_job(
            self.heartbeat_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            args=[user_id],
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True
        )

        with self.state_lock:
            self.user_states[user_id] = enabled

        logger.info(
            f"Added user {user_id} to scheduler "
            f"(interval: {interval_minutes}m, enabled: {enabled})"
        )

        # Log next run time (may not be set if scheduler hasn't started yet)
        job = self.scheduler.get_job(job_id)
        if job and getattr(job, 'next_run_time', None):
            logger.info(f"Next heartbeat for user {user_id}: {job.next_run_time}")

    def remove_user(self, user_id: str):
        """Remove a user from the scheduler."""
        job_id = f"heartbeat_{user_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed user {user_id} from scheduler")

        with self.state_lock:
            self.user_states.pop(user_id, None)

    def pause_user(self, user_id: str):
        """Pause heartbeats for a specific user (job continues, but skipped)."""
        with self.state_lock:
            self.user_states[user_id] = False
        logger.info(f"Paused heartbeats for user {user_id}")

    def resume_user(self, user_id: str):
        """Resume heartbeats for a specific user."""
        with self.state_lock:
            self.user_states[user_id] = True
        logger.info(f"Resumed heartbeats for user {user_id}")

    def is_enabled(self, user_id: str) -> bool:
        """Check if heartbeats are enabled for a user."""
        with self.state_lock:
            return self.user_states.get(user_id, True)

    def get_user_status(self, user_id: str) -> dict:
        """Get scheduler status for a specific user."""
        job_id = f"heartbeat_{user_id}"
        job = self.scheduler.get_job(job_id)
        user_storage = get_user_storage(user_id)
        user_config = user_storage.config.get_config()

        return {
            "enabled": self.is_enabled(user_id),
            "next_run": getattr(job, 'next_run_time', None) if job else None,
            "interval_minutes": user_config.heartbeat_interval_minutes,
            "job_exists": job is not None,
            "quiet_hours_enabled": user_config.quiet_hours_enabled,
            "quiet_hours_active_now": is_within_quiet_hours(user_config),
            "quiet_hours_timezone": user_config.timezone,
            "quiet_hours_start": user_config.quiet_hours_start,
            "quiet_hours_end": user_config.quiet_hours_end,
            "quiet_hours_resume_at": next_quiet_hours_end(user_config),
        }

    def start(self):
        """Start the scheduler and load all active users."""
        logger.info("Starting multi-user scheduler...")

        # Load all registered users from user registry
        user_registry = get_user_registry()
        active_users = user_registry.list_users(status="active")

        for user in active_users:
            user_id = user.user_id

            # Load user's config
            user_storage = get_user_storage(user_id)
            user_config = user_storage.config.get_config()

            # Add user with their custom interval and enabled state
            self.add_user(
                user_id=user_id,
                interval_minutes=user_config.heartbeat_interval_minutes,
                enabled=user_config.heartbeat_enabled
            )

        self.scheduler.start()
        logger.info(f"Multi-user scheduler started with {len(active_users)} users")

    def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping multi-user scheduler...")
        if self.scheduler.running:
            self.scheduler.shutdown()
        logger.info("Multi-user scheduler stopped")


# Backward compatibility alias
HeartbeatScheduler = MultiUserHeartbeatScheduler
