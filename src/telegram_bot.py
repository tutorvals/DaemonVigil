"""Telegram bot integration."""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from . import config
from . import storage
from .storage import get_user_storage, get_user_registry
from . import commands

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot for Daemon Vigil."""

    def __init__(self, on_user_message_callback=None):
        """
        Initialize the bot.

        Args:
            on_user_message_callback: Async function to call when user sends a message.
                                     Signature: async def callback(message: str, user_id: str)
                                     Note: user_id is the Telegram chat ID as a string
        """
        self.app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        self.on_user_message_callback = on_user_message_callback

        # Register handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        chat_id = update.effective_chat.id
        logger.info(f"Received /start from chat_id: {chat_id}")

        await update.message.reply_text(
            "Hey Vals! Daemon Vigil is online. I'll check in with you periodically."
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages with multi-user support."""
        message_text = update.message.text
        chat_id = update.effective_chat.id
        user_id = str(chat_id)  # Convert to string for consistency

        # Extract user info for registration
        telegram_user = update.effective_user
        username = telegram_user.username
        first_name = telegram_user.first_name or "Unknown"

        # Auto-register user if new
        user_registry = get_user_registry()
        user = user_registry.get_user(user_id)

        if not user:
            user_registry.register_user(
                user_id=user_id,
                username=username,
                first_name=first_name
            )
            logger.info(f"✨ New user registered: {user_id} (@{username})")

            # Send welcome message
            await self.send_message(
                f"Welcome, {first_name}! I'm Daemon Vigil. "
                f"I'll check in with you periodically. "
                f"Type ...help for commands.",
                chat_id=chat_id
            )

        # Update last seen
        user_registry.update_last_seen(user_id)

        # Check if this is a command (starts with "...")
        if message_text.startswith("..."):
            command = message_text[3:].strip()
            logger.info(f"Command received from user {user_id}: {command}")

            # Handle command with user_id (don't forward to Claude)
            handled = await commands.handle_command(command, self, user_id)

            if handled:
                logger.info(f"Command '{command}' handled successfully for user {user_id}")
            else:
                logger.info(f"Unknown command '{command}' from user {user_id} - ignoring")

            # Don't log commands to message history or forward to Claude
            return

        # Not a command - process normally
        # Get user-specific storage
        user_storage = get_user_storage(user_id)

        # Log the user message to their storage
        user_storage.messages.add_message("user", message_text)
        logger.info(f"💬 User {user_id}: {message_text[:50]}...")

        # Call the callback if provided (this will trigger Claude response)
        # Changed signature: now passes user_id instead of chat_id
        if self.on_user_message_callback:
            await self.on_user_message_callback(message_text, user_id)

    async def send_message(self, text: str, chat_id: int = None):
        """Send a message to the user."""
        if chat_id is None:
            chat_id = config.TELEGRAM_CHAT_ID

        if not chat_id:
            logger.error("Cannot send message: chat_id not set")
            return

        await self.app.bot.send_message(chat_id=chat_id, text=text)
        logger.info(f"Sent message: {text[:50]}...")

    async def start(self):
        """Start the bot (polling mode)."""
        logger.info("Starting Telegram bot...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        logger.info("Telegram bot is running")

    async def stop(self):
        """Stop the bot gracefully."""
        logger.info("Stopping Telegram bot...")
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        logger.info("Telegram bot stopped")
