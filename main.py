"""Daemon Vigil - Proactive AI Companion

Entry point for the application.
"""
import argparse
import asyncio
import logging
import signal
import sys

from src.telegram_bot import TelegramBot
from src.scheduler import HeartbeatScheduler
from src import claude

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('daemon_vigil.log')
    ]
)

logger = logging.getLogger(__name__)


class DaemonVigil:
    """Main application class."""

    def __init__(self, silent: bool = False):
        self.telegram_bot = None
        self.scheduler = None
        self.shutdown_event = asyncio.Event()
        self.silent = silent

    async def on_user_message(self, message: str, chat_id: int):
        """Callback when user sends a message."""
        logger.info(f"User message received: {message[:50]}...")
        await claude.respond_to_user(message, self.telegram_bot)

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


async def main(silent: bool = False):
    """Main entry point."""
    app = DaemonVigil(silent=silent)

    # Register signal handlers
    signal.signal(signal.SIGINT, lambda s, f: app.handle_shutdown(s, f))
    signal.signal(signal.SIGTERM, lambda s, f: app.handle_shutdown(s, f))

    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await app.stop()


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Daemon Vigil - Proactive AI Companion")
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Suppress startup and shutdown notifications in Telegram"
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(silent=args.silent))
    except KeyboardInterrupt:
        logger.info("Exiting...")
