"""Main application class for Daemon Vigil."""
import asyncio
import logging

from .telegram_bot import TelegramBot
from .scheduler import HeartbeatScheduler
from . import claude

logger = logging.getLogger(__name__)


class DaemonVigil:
    """Main application class."""

    # Class variable to store instance for command access
    _instance = None

    def __init__(self, silent: bool = False):
        self.telegram_bot = None
        self.scheduler = None
        self.shutdown_event = asyncio.Event()
        self.silent = silent
        DaemonVigil._instance = self

    async def on_user_message(self, message: str, chat_id: int):
        """Callback when user sends a message."""
        logger.info(f"User message received: {message[:50]}...")
        await claude.respond_to_user(message, self.telegram_bot)

    @classmethod
    def get_instance(cls):
        """Get the current DaemonVigil instance."""
        return cls._instance

    async def start(self):
        """Start all components."""
        logger.info("Starting Daemon Vigil...")

        # Initialize Telegram bot
        self.telegram_bot = TelegramBot(on_user_message_callback=self.on_user_message)
        await self.telegram_bot.start()

        # Send startup notification
        if not self.silent:
            await self.telegram_bot.send_message("🟢 Daemon Vigil service started")

        # Initialize and start scheduler
        self.scheduler = HeartbeatScheduler(self.telegram_bot)
        self.scheduler.start()

        logger.info("Daemon Vigil is running. Press Ctrl+C to stop.")

        # Wait for shutdown signal
        await self.shutdown_event.wait()

    async def stop(self):
        """Stop all components gracefully."""
        logger.info("Shutting down Daemon Vigil...")

        if self.scheduler:
            self.scheduler.stop()

        # Send shutdown notification
        if self.telegram_bot and not self.silent:
            await self.telegram_bot.send_message("🔴 Daemon Vigil service shutdown")

        if self.telegram_bot:
            await self.telegram_bot.stop()

        logger.info("Daemon Vigil stopped")

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()
