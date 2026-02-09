"""Command handlers for Telegram bot commands."""
import logging
from typing import Optional

from . import usage_tracker
from . import config
from . import claude
from .scheduler import HeartbeatScheduler

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

    elif cmd == "heartbeat":
        await handle_heartbeat(args, telegram_bot, chat_id)
        return True

    elif cmd == "help":
        await handle_help(telegram_bot, chat_id)
        return True

    elif cmd == "clear":
        await handle_clear(telegram_bot, chat_id)
        return True

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


async def handle_heartbeat(args: str, telegram_bot, chat_id: int) -> None:
    """
    Handle the ...heartbeat command with subcommands.

    Subcommands:
    - test: Manual debug heartbeat
    - on: Enable automatic heartbeats
    - off: Disable automatic heartbeats
    - status: Show heartbeat status
    """
    from .app import DaemonVigil

    subcommand = args.strip().lower() if args else "test"

    if subcommand == "test":
        logger.info("Handling manual heartbeat test (debug mode)")

        # Send initial message
        await telegram_bot.send_message("🔍 Running manual heartbeat check...", chat_id)

        # Trigger heartbeat in debug mode
        result = await claude.process_heartbeat(telegram_bot, debug=True)

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

        await telegram_bot.send_message(response, chat_id)

    elif subcommand == "on":
        app = DaemonVigil.get_instance()
        if app and app.scheduler:
            app.scheduler.resume()
            response = "✅ Automatic heartbeats ENABLED\n\nThe bot will check in periodically as scheduled."
        else:
            response = "❌ Scheduler not available"
        await telegram_bot.send_message(response, chat_id)

    elif subcommand == "off":
        app = DaemonVigil.get_instance()
        if app and app.scheduler:
            app.scheduler.pause()
            response = "🔇 Automatic heartbeats DISABLED\n\nThe bot will not send scheduled check-ins.\nYou can still use '...heartbeat test' for manual checks."
        else:
            response = "❌ Scheduler not available"
        await telegram_bot.send_message(response, chat_id)

    elif subcommand == "status":
        app = DaemonVigil.get_instance()
        if app and app.scheduler:
            status = app.scheduler.get_status()
            response = "📊 Heartbeat Status\n\n"
            response += f"State: {'✅ ENABLED' if status['enabled'] else '🔇 DISABLED'}\n"
            response += f"Interval: {status['interval_minutes']} minutes\n"
            if status['next_run']:
                response += f"Next run: {status['next_run']}\n"
            else:
                response += "Next run: Not scheduled\n"
        else:
            response = "❌ Scheduler not available"
        await telegram_bot.send_message(response, chat_id)

    elif subcommand.startswith("interval"):
        # Handle ...heartbeat interval <minutes>
        # Extract the minutes from args (format: "interval <minutes>")
        parts = args.split()
        if len(parts) < 2:
            response = "❌ Usage: ...heartbeat interval <minutes>\n\nExample: ...heartbeat interval 30"
            await telegram_bot.send_message(response, chat_id)
            return

        try:
            minutes = int(parts[1])
            if minutes < 1:
                response = "❌ Interval must be at least 1 minute"
                await telegram_bot.send_message(response, chat_id)
                return

            # Update config
            config.update_config("heartbeat_interval_minutes", minutes)

            # Restart scheduler with new interval
            app = DaemonVigil.get_instance()
            if app and app.scheduler:
                app.scheduler.stop()
                app.scheduler = HeartbeatScheduler(app.telegram_bot)
                app.scheduler.start()
                response = f"✅ Heartbeat interval changed to {minutes} minutes\n\nScheduler restarted with new interval."
                logger.info(f"Heartbeat interval changed to {minutes} minutes")
            else:
                response = "❌ Scheduler not available"

            await telegram_bot.send_message(response, chat_id)

        except ValueError:
            response = "❌ Invalid number. Usage: ...heartbeat interval <minutes>"
            await telegram_bot.send_message(response, chat_id)

    else:
        response = "❌ Unknown heartbeat command\n\nAvailable:\n"
        response += "• ...heartbeat test - Run debug heartbeat\n"
        response += "• ...heartbeat on - Enable automatic heartbeats\n"
        response += "• ...heartbeat off - Disable automatic heartbeats\n"
        response += "• ...heartbeat status - Show status\n"
        response += "• ...heartbeat interval <minutes> - Change interval"
        await telegram_bot.send_message(response, chat_id)


async def handle_help(telegram_bot, chat_id: int) -> None:
    """Handle the ...help command."""
    help_text = """📖 Available Commands

**Status & Information**
• ...status - Show model, costs, context, heartbeat status
• ...help - Show this help message

**Model Switching**
• ...model - Show current model and options
• ...model <name> - Switch model (sonnet/opus/haiku)

**Heartbeat Control**
• ...heartbeat test - Manual debug heartbeat
• ...heartbeat on - Enable automatic heartbeats
• ...heartbeat off - Disable automatic heartbeats
• ...heartbeat status - Show heartbeat status
• ...heartbeat interval <minutes> - Change interval

**Conversation**
• ...clear - Clear conversation history"""

    logger.info("Handling help command")
    await telegram_bot.send_message(help_text, chat_id)


async def handle_clear(telegram_bot, chat_id: int) -> None:
    """Handle the ...clear command."""
    from . import storage

    logger.info("Handling clear command")

    # Get current message counts before clearing
    messages_before = len(storage.messages.get_recent_messages())
    notes_before = len(storage.scratchpad.get_notes())

    # Clear both message history and scratchpad
    storage.messages.clear()
    storage.scratchpad.clear()

    response = f"✅ Conversation cleared\n\n"
    response += f"Deleted {messages_before} messages and {notes_before} notes.\n\n"
    response += "Starting fresh - Claude will have no memory of previous conversations."

    await telegram_bot.send_message(response, chat_id)
