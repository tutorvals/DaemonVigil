"""Scheduler for heartbeat checks."""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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

    async def heartbeat_job(self):
        """Job that runs on each heartbeat."""
        logger.info("Heartbeat triggered")
        await claude.process_heartbeat(self.telegram_bot)

    def start(self):
        """Start the scheduler."""
        interval_minutes = config.HEARTBEAT_INTERVAL_MINUTES
        logger.info(f"Starting scheduler with {interval_minutes} minute interval")

        self.scheduler.add_job(
            self.heartbeat_job,
            'interval',
            minutes=interval_minutes,
            id='heartbeat',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping scheduler...")
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
