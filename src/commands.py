"""Command handlers for Telegram bot commands."""
import logging
from typing import Optional

from . import usage_tracker
from . import config

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
    command_lower = command.strip().lower()

    # Split into command and arguments
    parts = command_lower.split(maxsplit=1)
    cmd = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "status":
        await handle_status(telegram_bot, chat_id)
        return True

    elif cmd == "model":
        await handle_model(args, telegram_bot, chat_id)
        return True

    # Add more commands here in the future
    # elif cmd == "help":
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


async def handle_model(args: str, telegram_bot, chat_id: int) -> None:
    """
    Handle the ...model command.

    Switch the Claude model being used.

    Args:
        args: Model alias (e.g., "opus", "sonnet", "haiku")
    """
    logger.info(f"Handling model command with args: {args}")

    if not args:
        # Show current model
        current = config.get_claude_model()
        response = f"Current model: {current}\n\nAvailable models:\n"
        response += "• ...model sonnet (Sonnet 4)\n"
        response += "• ...model sonnet-4.5 (Sonnet 4.5)\n"
        response += "• ...model opus (Opus 4.5)\n"
        response += "• ...model haiku (Haiku 3.5)\n"
        await telegram_bot.send_message(response, chat_id)
        return

    # Try to resolve alias
    model_alias = args.strip().lower()

    if model_alias in config.MODEL_ALIASES:
        full_model_name = config.MODEL_ALIASES[model_alias]

        # Update config
        config.update_config("claude_model", full_model_name)

        # Get friendly name for confirmation
        friendly_name_map = {
            "claude-sonnet-4-20250514": "Sonnet 4",
            "claude-sonnet-4-5-20250929": "Sonnet 4.5",
            "claude-opus-4-5-20251101": "Opus 4.5",
            "claude-3-5-haiku-20241022": "Haiku 3.5",
            "claude-3-haiku-20240307": "Haiku 3",
        }
        friendly_name = friendly_name_map.get(full_model_name, full_model_name)

        response = f"✅ Model switched to {friendly_name}\n({full_model_name})"
        logger.info(f"Model switched to {full_model_name}")
        await telegram_bot.send_message(response, chat_id)
    else:
        # Unknown model alias
        response = f"❌ Unknown model: {model_alias}\n\nAvailable models:\n"
        response += "• sonnet, sonnet-4, sonnet-4.5\n"
        response += "• opus, opus-4, opus-4.5\n"
        response += "• haiku, haiku-3, haiku-3.5"
        await telegram_bot.send_message(response, chat_id)


# Future command handlers can be added here
# async def handle_help(telegram_bot, chat_id: int) -> None:
#     """Handle the ...help command."""
#     help_text = """
# Available commands:
# ...status - Show current model and API costs
# ...help - Show this help message
#     """
#     await telegram_bot.send_message(help_text.strip(), chat_id)
