"""Command handlers for Telegram bot commands."""
import logging
from typing import Optional

from . import usage_tracker

logger = logging.getLogger(__name__)


async def handle_command(command: str, telegram_bot, chat_id: int) -> bool:
    """
    Handle a command message.

    Args:
        command: The command string (without the "..." prefix)
        telegram_bot: TelegramBot instance for sending responses
        chat_id: Telegram chat_id to send response to

    Returns:
        True if command was handled, False if invalid command
    """
    command = command.strip().lower()

    if command == "status":
        await handle_status(telegram_bot, chat_id)
        return True

    # Add more commands here in the future
    # elif command == "help":
    #     await handle_help(telegram_bot, chat_id)
    #     return True

    # Unknown command - return False to silently ignore
    return False


async def handle_status(telegram_bot, chat_id: int) -> None:
    """
    Handle the ...status command.

    Shows current model and API cost breakdown.
    """
    logger.info("Handling status command")

    report = usage_tracker.format_usage_report()
    await telegram_bot.send_message(report, chat_id)


# Future command handlers can be added here
# async def handle_help(telegram_bot, chat_id: int) -> None:
#     """Handle the ...help command."""
#     help_text = """
# Available commands:
# ...status - Show current model and API costs
# ...help - Show this help message
#     """
#     await telegram_bot.send_message(help_text.strip(), chat_id)
