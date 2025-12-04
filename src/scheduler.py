"""Scheduler for heartbeat checks."""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from . import config
from . import claude

logger = logging.getLogger(__name__)


class HeartbeatScheduler:
    """Manages periodic heartbeat checks."""

    def __init__(self, telegram_bot):
        """
        Initialize the scheduler.

        Args:
            telegram_bot: TelegramBot instance for sending messages
        """
        self.telegram_bot = telegram_bot
        self.scheduler = AsyncIOScheduler()
        self.enabled = True  # Default enabled

    async def heartbeat_job(self):
        """Job that runs on each heartbeat."""
        try:
            logger.info("=" * 50)
            logger.info("HEARTBEAT TRIGGERED")
            logger.info(f"Time: {datetime.utcnow().isoformat()}")
            logger.info(f"Enabled: {self.enabled}")
            logger.info("=" * 50)

            if not self.enabled:
                logger.info("Heartbeat disabled, skipping")
                return

            await claude.process_heartbeat(self.telegram_bot)
            logger.info("Heartbeat completed successfully")

        except Exception as e:
            logger.error(f"Error in heartbeat job: {e}", exc_info=True)

    def start(self):
        """Start the scheduler."""
        interval_minutes = config.HEARTBEAT_INTERVAL_MINUTES
        logger.info(f"Starting scheduler with {interval_minutes} minute interval")

        # Add the job with explicit configuration
        self.scheduler.add_job(
            self.heartbeat_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id='heartbeat',
            replace_existing=True,
            max_instances=1,
            coalesce=True  # If multiple instances pile up, run only one
        )

        self.scheduler.start()
        logger.info("Scheduler started successfully")

        # Log next run time
        job = self.scheduler.get_job('heartbeat')
        if job and job.next_run_time:
            logger.info(f"Next heartbeat scheduled for: {job.next_run_time}")

    def pause(self):
        """Pause automatic heartbeats."""
        self.enabled = False
        logger.info("Heartbeats paused")

    def resume(self):
        """Resume automatic heartbeats."""
        self.enabled = True
        logger.info("Heartbeats resumed")

    def get_status(self) -> dict:
        """Get scheduler status."""
        job = self.scheduler.get_job('heartbeat')
        return {
            "enabled": self.enabled,
            "next_run": job.next_run_time if job else None,
            "interval_minutes": config.HEARTBEAT_INTERVAL_MINUTES
        }

    def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping scheduler...")
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
