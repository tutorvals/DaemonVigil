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
from src.storage import get_user_storage
from src import config
from src.app_state import set_instance

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('daemon_vigil.log')
    ]
)

# Reduce Telegram HTTP request logging unless it errors
logging.getLogger('httpx').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class DaemonVigil:
    """Main application class."""

    def __init__(self, silent: bool = False):
        self.telegram_bot = None
        self.scheduler = None
        self.shutdown_event = asyncio.Event()
        self.silent = silent
        set_instance(self)

    async def on_user_message(self, message: str, user_id: str):
        """
        Callback when user sends a message with user context.

        Args:
            message: The message text
            user_id: User ID (Telegram chat ID as string)
        """
        try:
            logger.info(f"User {user_id} message received: {message[:50]}...")

            # Get user-specific storage and config
            user_storage = get_user_storage(user_id)
            user_config = user_storage.config.get_config()

            # Respond with user context
            from src import claude
            await claude.respond_to_user(
                user_message=message,
                telegram_bot=self.telegram_bot,
                user_id=user_id,
                user_storage=user_storage,
                user_config=user_config
            )

        except Exception as e:
            logger.error(f"Error responding to user {user_id}: {e}", exc_info=True)
            # Send error message to user
            try:
                await self.telegram_bot.send_message(
                    "Sorry, I encountered an error processing your message. "
                    "Please try again.",
                    chat_id=int(user_id)
                )
            except:
                pass  # Best effort

    async def start(self):
        """Start all components."""
        logger.info("Starting Daemon Vigil...")

        # Initialize Telegram bot
        self.telegram_bot = TelegramBot(on_user_message_callback=self.on_user_message)
        await self.telegram_bot.start()

        # Send startup notification to primary user
        if not self.silent and config.TELEGRAM_CHAT_ID:
            await self.telegram_bot.send_message(
                "🟢 Daemon Vigil service started",
                chat_id=config.TELEGRAM_CHAT_ID
            )

        # Initialize and start multi-user scheduler
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

        # Send shutdown notification to primary user
        if self.telegram_bot and not self.silent and config.TELEGRAM_CHAT_ID:
            await self.telegram_bot.send_message(
                "🔴 Daemon Vigil service shutdown",
                chat_id=config.TELEGRAM_CHAT_ID
            )

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
