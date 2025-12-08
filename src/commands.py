"""Command handlers for Telegram bot commands."""
import logging
from typing import Optional

from . import usage_tracker
from . import config
from . import claude
from .storage import get_user_storage

logger = logging.getLogger(__name__)


async def handle_command(command: str, telegram_bot, user_id: str) -> bool:
    """
    Handle a command message with user context.

    Args:
        command: The command string (without the "..." prefix)
        telegram_bot: TelegramBot instance for sending responses
        user_id: User ID (Telegram chat ID as string)

    Returns:
        True if command was handled, False if invalid command
    """
    command_lower = command.strip().lower()

    # Split into command and arguments
    parts = command_lower.split(maxsplit=1)
    cmd = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "status":
        await handle_status(telegram_bot, user_id)
        return True

    elif cmd == "model":
        await handle_model(args, telegram_bot, user_id)
        return True

    elif cmd == "heartbeat":
        await handle_heartbeat(args, telegram_bot, user_id)
        return True

    # Add more commands here in the future
    # elif cmd == "help":
    #     await handle_help(telegram_bot, user_id)
    #     return True

    # Unknown command - return False to silently ignore
    return False


async def handle_status(telegram_bot, user_id: str) -> None:
    """
    Handle the ...status command.

    Shows current model and API cost breakdown for the user.
    """
    logger.info(f"Handling status command for user {user_id}")

    # Get user-specific report
    report = usage_tracker.format_usage_report(user_id)
    await telegram_bot.send_message(report, chat_id=int(user_id))


async def handle_model(args: str, telegram_bot, user_id: str) -> None:
    """
    Handle the ...model command.

    Switch the Claude model being used for this user.

    Args:
        args: Model alias (e.g., "opus", "sonnet", "haiku")
    """
    logger.info(f"Handling model command for user {user_id} with args: {args}")

    # Get user storage
    user_storage = get_user_storage(user_id)
    user_config = user_storage.config.get_config()

    if not args:
        # Show current model for this user
        current = user_config.model
        response = f"Your current model: {current}\n\nAvailable models:\n"
        response += "• ...model sonnet (Sonnet 4)\n"
        response += "• ...model sonnet-4.5 (Sonnet 4.5)\n"
        response += "• ...model opus (Opus 4.5)\n"
        response += "• ...model haiku (Haiku 3.5)\n"
        await telegram_bot.send_message(response, chat_id=int(user_id))
        return

    # Try to resolve alias
    model_alias = args.strip().lower()

    if model_alias in config.MODEL_ALIASES:
        full_model_name = config.MODEL_ALIASES[model_alias]

        # Update user-specific config
        user_storage.config.update_config(model=full_model_name)

        # Get friendly name for confirmation
        friendly_name_map = {
            "claude-sonnet-4-20250514": "Sonnet 4",
            "claude-sonnet-4-5-20250929": "Sonnet 4.5",
            "claude-opus-4-5-20251101": "Opus 4.5",
            "claude-3-5-haiku-20241022": "Haiku 3.5",
            "claude-3-haiku-20240307": "Haiku 3",
        }
        friendly_name = friendly_name_map.get(full_model_name, full_model_name)

        response = f"✅ Your model switched to {friendly_name}\n({full_model_name})"
        logger.info(f"User {user_id} model switched to {full_model_name}")
        await telegram_bot.send_message(response, chat_id=int(user_id))
    else:
        # Unknown model alias
        response = f"❌ Unknown model: {model_alias}\n\nAvailable models:\n"
        response += "• sonnet, sonnet-4, sonnet-4.5\n"
        response += "• opus, opus-4, opus-4.5\n"
        response += "• haiku, haiku-3, haiku-3.5"
        await telegram_bot.send_message(response, chat_id=int(user_id))


async def handle_heartbeat(args: str, telegram_bot, user_id: str) -> None:
    """
    Handle the ...heartbeat command with subcommands.

    Subcommands:
    - test: Manual debug heartbeat
    - on: Enable automatic heartbeats
    - off: Disable automatic heartbeats
    - status: Show heartbeat status
    """
    from main import DaemonVigil

    subcommand = args.strip().lower() if args else "test"

    if subcommand == "test":
        logger.info(f"Handling manual heartbeat test for user {user_id} (debug mode)")

        # Send initial message
        await telegram_bot.send_message("🔍 Running manual heartbeat check...", chat_id=int(user_id))

        # Get user context
        user_storage = get_user_storage(user_id)
        user_config = user_storage.config.get_config()

        # Trigger heartbeat in debug mode with user context
        result = await claude.process_heartbeat(
            telegram_bot=telegram_bot,
            user_id=user_id,
            user_storage=user_storage,
            user_config=user_config,
            debug=True
        )

        # Build debug response
        response = "📊 Heartbeat Debug Report\n\n"

        if result["error"]:
            response += f"❌ Error: {result['error']}"
        else:
            # Show Claude's reasoning
            if result["reasoning"]:
                response += f"💭 Claude's Reasoning:\n{result['reasoning']}\n\n"
            else:
                response += "💭 No reasoning provided by Claude\n\n"

            # Show decision
            if result["tool_called"]:
                response += f"✅ Decision: SEND MESSAGE\n\n"
                response += f"📨 Message:\n{result['message_sent']}\n\n"
                response += "⚠️ Message NOT sent (debug mode)\n"
                response += "This was a dry run - no message was actually sent to you."
            else:
                response += "🔇 Decision: STAY SILENT\n\n"
                response += "Claude chose not to send a message this cycle."

        await telegram_bot.send_message(response, chat_id=int(user_id))

    elif subcommand == "on":
        app = DaemonVigil.get_instance()
        if app and app.scheduler:
            # Try multi-user scheduler first, fallback to single-user
            try:
                if hasattr(app.scheduler, 'resume_user'):
                    # Multi-user scheduler
                    app.scheduler.resume_user(user_id)
                    user_storage = get_user_storage(user_id)
                    user_storage.config.update_config(heartbeat_enabled=True)
                else:
                    # Old single-user scheduler
                    app.scheduler.resume()
                response = "✅ Automatic heartbeats ENABLED\n\nThe bot will check in periodically as scheduled."
            except Exception as e:
                logger.error(f"Error enabling heartbeats for user {user_id}: {e}")
                response = f"❌ Error enabling heartbeats: {e}"
        else:
            response = "❌ Scheduler not available"
        await telegram_bot.send_message(response, chat_id=int(user_id))

    elif subcommand == "off":
        app = DaemonVigil.get_instance()
        if app and app.scheduler:
            # Try multi-user scheduler first, fallback to single-user
            try:
                if hasattr(app.scheduler, 'pause_user'):
                    # Multi-user scheduler
                    app.scheduler.pause_user(user_id)
                    user_storage = get_user_storage(user_id)
                    user_storage.config.update_config(heartbeat_enabled=False)
                else:
                    # Old single-user scheduler
                    app.scheduler.pause()
                response = "🔇 Automatic heartbeats DISABLED\n\nThe bot will not send scheduled check-ins.\nYou can still use '...heartbeat test' for manual checks."
            except Exception as e:
                logger.error(f"Error disabling heartbeats for user {user_id}: {e}")
                response = f"❌ Error disabling heartbeats: {e}"
        else:
            response = "❌ Scheduler not available"
        await telegram_bot.send_message(response, chat_id=int(user_id))

    elif subcommand == "status":
        app = DaemonVigil.get_instance()
        if app and app.scheduler:
            try:
                # Try multi-user scheduler first
                if hasattr(app.scheduler, 'get_user_status'):
                    # Multi-user scheduler
                    status = app.scheduler.get_user_status(user_id)
                    user_storage = get_user_storage(user_id)
                    user_config = user_storage.config.get_config()
                    response = "📊 Your Heartbeat Status\n\n"
                    response += f"State: {'✅ ENABLED' if status.get('enabled', True) else '🔇 DISABLED'}\n"
                    response += f"Interval: {user_config.heartbeat_interval_minutes} minutes\n"
                    if status.get('next_run'):
                        response += f"Next run: {status['next_run']}\n"
                    else:
                        response += "Next run: Not scheduled\n"
                else:
                    # Old single-user scheduler
                    status = app.scheduler.get_status()
                    response = "📊 Heartbeat Status\n\n"
                    response += f"State: {'✅ ENABLED' if status['enabled'] else '🔇 DISABLED'}\n"
                    response += f"Interval: {status['interval_minutes']} minutes\n"
                    if status['next_run']:
                        response += f"Next run: {status['next_run']}\n"
                    else:
                        response += "Next run: Not scheduled\n"
            except Exception as e:
                logger.error(f"Error getting heartbeat status for user {user_id}: {e}")
                response = f"❌ Error getting status: {e}"
        else:
            response = "❌ Scheduler not available"
        await telegram_bot.send_message(response, chat_id=int(user_id))

    else:
        response = "❌ Unknown heartbeat command\n\nAvailable:\n"
        response += "• ...heartbeat test - Run debug heartbeat\n"
        response += "• ...heartbeat on - Enable automatic heartbeats\n"
        response += "• ...heartbeat off - Disable automatic heartbeats\n"
        response += "• ...heartbeat status - Show status"
        await telegram_bot.send_message(response, chat_id=int(user_id))


# Future command handlers can be added here
# async def handle_help(telegram_bot, chat_id: int) -> None:
#     """Handle the ...help command."""
#     help_text = """
# Available commands:
# ...status - Show current model and API costs
# ...help - Show this help message
#     """
#     await telegram_bot.send_message(help_text.strip(), chat_id)
