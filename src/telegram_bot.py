"""Telegram bot integration."""
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from . import config
from . import storage

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot for Daemon Vigil."""

    def __init__(self, on_user_message_callback=None):
        """
        Initialize the bot.

        Args:
            on_user_message_callback: Async function to call when user sends a message.
                                     Signature: async def callback(message: str, chat_id: int)
        """
        self.app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        self.on_user_message_callback = on_user_message_callback

        # Register handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        chat_id = update.effective_chat.id

        # Save chat_id to config if not already set
        if not config.TELEGRAM_CHAT_ID:
            config.update_config("telegram_chat_id", chat_id)
            logger.info(f"Set telegram_chat_id to {chat_id}")

        await update.message.reply_text(
            "Hey Vals! Daemon Vigil is online. I'll check in with you periodically."
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages."""
        message_text = update.message.text
        chat_id = update.effective_chat.id

        # Log the user message
        storage.messages.add_message("user", message_text)
        logger.info(f"User message: {message_text}")

        # Call the callback if provided (this will trigger Claude response)
        if self.on_user_message_callback:
            await self.on_user_message_callback(message_text, chat_id)

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
