"""Command handlers for Telegram bot commands."""
import logging
from typing import Optional

from . import usage_tracker
from . import config
from . import claude
from .storage import get_user_storage
from .time_utils import (
    get_local_now,
    is_valid_timezone,
    is_within_quiet_hours,
    next_quiet_hours_end,
    parse_hhmm,
)

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
    # Split into command and arguments
    command = command.strip()
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
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

    elif cmd == "quiethours":
        await handle_quiet_hours(args, telegram_bot, user_id)
        return True

    elif cmd == "help":
        await handle_help(telegram_bot, user_id)
        return True

    elif cmd == "clear":
        await handle_clear(telegram_bot, user_id)
        return True

    elif cmd == "showmemory":
        await handle_showmemory(telegram_bot, user_id)
        return True

    elif cmd == "clearmemory":
        await handle_clearmemory(telegram_bot, user_id)
        return True

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
            "sonnet": "Sonnet",
            "sonnet-4.5": "Sonnet 4.5",
            "opus": "Opus",
            "haiku": "Haiku 3.5",
            "haiku-3": "Haiku 3",
        }
        friendly_name = friendly_name_map.get(full_model_name, full_model_name)

        response = f"Model switched to {friendly_name}\n({full_model_name})"
        logger.info(f"User {user_id} model switched to {full_model_name}")
        await telegram_bot.send_message(response, chat_id=int(user_id))
    else:
        # Unknown model alias
        response = f"Unknown model: {model_alias}\n\nAvailable models:\n"
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
    - interval <minutes>: Change heartbeat interval
    """
    from .app_state import get_instance

    subcommand = args.strip().lower() if args else "test"

    if subcommand == "test":
        logger.info(f"Handling manual heartbeat test for user {user_id} (debug mode)")

        # Send initial message
        await telegram_bot.send_message("Running manual heartbeat check...", chat_id=int(user_id))

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
        response = "Heartbeat Debug Report\n\n"

        # Show debug info (timing, tokens, context)
        debug_info = result.get("debug_info", {})
        if debug_info:
            response += f"Model: {debug_info.get('model', '?')}\n"
            response += f"Context: {debug_info.get('message_count', '?')} messages, {debug_info.get('note_count', '?')} notes\n"
            response += f"System prompt: {debug_info.get('system_prompt_length', '?')} chars\n"
            if "input_tokens" in debug_info:
                response += f"Tokens: {debug_info['input_tokens']} in / {debug_info['output_tokens']} out\n"
                response += f"Cost: ${debug_info.get('cost', 0):.6f}\n"
            if "elapsed_seconds" in debug_info:
                response += f"Time: {debug_info['elapsed_seconds']}s\n"
            response += "\n"

        if result["error"]:
            response += f"Error: {result['error']}"
        else:
            # Show Claude's reasoning
            if result["reasoning"]:
                response += f"Claude's Reasoning:\n{result['reasoning']}\n\n"
            else:
                response += "No reasoning provided by Claude\n\n"

            # Show decision
            if result["tool_called"]:
                response += f"Decision: SEND MESSAGE\n\n"
                response += f"Message:\n{result['message_sent']}\n\n"
                response += "Message NOT sent (debug mode)\n"
                response += "This was a dry run - no message was actually sent to you."
            else:
                response += "Decision: STAY SILENT\n\n"
                response += "Claude chose not to send a message this cycle."

        await telegram_bot.send_message(response, chat_id=int(user_id))

    elif subcommand == "on":
        app = get_instance()
        if app and app.scheduler:
            try:
                app.scheduler.resume_user(user_id)
                user_storage = get_user_storage(user_id)
                user_storage.config.update_config(heartbeat_enabled=True)
                response = "Automatic heartbeats ENABLED\n\nThe bot will check in periodically as scheduled."
            except Exception as e:
                logger.error(f"Error enabling heartbeats for user {user_id}: {e}")
                response = f"Error enabling heartbeats: {e}"
        else:
            response = "Scheduler not available"
        await telegram_bot.send_message(response, chat_id=int(user_id))

    elif subcommand == "off":
        app = get_instance()
        if app and app.scheduler:
            try:
                app.scheduler.pause_user(user_id)
                user_storage = get_user_storage(user_id)
                user_storage.config.update_config(heartbeat_enabled=False)
                response = "Automatic heartbeats DISABLED\n\nThe bot will not send scheduled check-ins.\nYou can still use '...heartbeat test' for manual checks."
            except Exception as e:
                logger.error(f"Error disabling heartbeats for user {user_id}: {e}")
                response = f"Error disabling heartbeats: {e}"
        else:
            response = "Scheduler not available"
        await telegram_bot.send_message(response, chat_id=int(user_id))

    elif subcommand == "status":
        app = get_instance()
        if app and app.scheduler:
            try:
                status = app.scheduler.get_user_status(user_id)
                user_storage = get_user_storage(user_id)
                user_config = user_storage.config.get_config()
                response = "Your Heartbeat Status\n\n"
                response += f"State: {'Enabled' if status.get('enabled', True) else 'Disabled'}\n"
                response += f"Interval: {user_config.heartbeat_interval_minutes} minutes\n"
                if status.get('next_run'):
                    response += f"Next run: {status['next_run']}\n"
                else:
                    response += "Next run: Not scheduled\n"
                if user_config.quiet_hours_enabled:
                    response += (
                        f"Quiet hours: {user_config.quiet_hours_start}-{user_config.quiet_hours_end} "
                        f"({user_config.timezone})\n"
                    )
                    response += (
                        f"Quiet hours active now: "
                        f"{'Yes' if status.get('quiet_hours_active_now') else 'No'}\n"
                    )
                else:
                    response += "Quiet hours: Disabled\n"
            except Exception as e:
                logger.error(f"Error getting heartbeat status for user {user_id}: {e}")
                response = f"Error getting status: {e}"
        else:
            response = "Scheduler not available"
        await telegram_bot.send_message(response, chat_id=int(user_id))

    elif subcommand.startswith("interval"):
        # Handle ...heartbeat interval <minutes>
        parts = args.split()
        if len(parts) < 2:
            response = "Usage: ...heartbeat interval <minutes>\n\nExample: ...heartbeat interval 30"
            await telegram_bot.send_message(response, chat_id=int(user_id))
            return

        try:
            minutes = int(parts[1])
            if minutes < 1:
                response = "Interval must be at least 1 minute"
                await telegram_bot.send_message(response, chat_id=int(user_id))
                return

            # Update user-specific config
            user_storage = get_user_storage(user_id)
            user_storage.config.update_config(heartbeat_interval_minutes=minutes)

            # Update scheduler for this user
            app = get_instance()
            if app and app.scheduler:
                enabled = user_storage.config.get_config().heartbeat_enabled
                app.scheduler.remove_user(user_id)
                app.scheduler.add_user(
                    user_id=user_id,
                    interval_minutes=minutes,
                    enabled=enabled
                )
                response = f"Heartbeat interval changed to {minutes} minutes\n\nScheduler updated."
                logger.info(f"User {user_id} heartbeat interval changed to {minutes} minutes")
            else:
                response = "Scheduler not available"

            await telegram_bot.send_message(response, chat_id=int(user_id))

        except ValueError:
            response = "Invalid number. Usage: ...heartbeat interval <minutes>"
            await telegram_bot.send_message(response, chat_id=int(user_id))

    else:
        response = "Unknown heartbeat command\n\nAvailable:\n"
        response += "• ...heartbeat test - Run debug heartbeat\n"
        response += "• ...heartbeat on - Enable automatic heartbeats\n"
        response += "• ...heartbeat off - Disable automatic heartbeats\n"
        response += "• ...heartbeat status - Show status\n"
        response += "• ...heartbeat interval <minutes> - Change interval"
        await telegram_bot.send_message(response, chat_id=int(user_id))


def _format_quiet_hours_status(user_config) -> str:
    """Build a consistent quiet-hours status block."""
    local_now = get_local_now(user_config.timezone)
    response = "Quiet Hours Status\n\n"
    response += f"State: {'Enabled' if user_config.quiet_hours_enabled else 'Disabled'}\n"
    response += f"Timezone: {user_config.timezone}\n"
    response += f"Window: {user_config.quiet_hours_start} - {user_config.quiet_hours_end}\n"
    response += f"Local time now: {local_now.strftime('%Y-%m-%d %H:%M %Z')}\n"
    if user_config.quiet_hours_enabled:
        response += f"Active now: {'Yes' if is_within_quiet_hours(user_config) else 'No'}\n"
        quiet_end = next_quiet_hours_end(user_config)
        if quiet_end is not None:
            response += f"Heartbeats resume: {quiet_end.strftime('%Y-%m-%d %H:%M %Z')}\n"
    return response


async def handle_quiet_hours(args: str, telegram_bot, user_id: str) -> None:
    """Handle the ...quiethours command family."""
    user_storage = get_user_storage(user_id)
    user_config = user_storage.config.get_config()
    parts = args.split()
    subcommand = parts[0].lower() if parts else "status"

    if subcommand == "status":
        response = _format_quiet_hours_status(user_config)

    elif subcommand == "on":
        if not is_valid_timezone(user_config.timezone):
            response = "Quiet hours cannot be enabled until you set a valid timezone.\n\nExample: ...quiethours timezone Europe/Paris"
        else:
            try:
                parse_hhmm(user_config.quiet_hours_start)
                parse_hhmm(user_config.quiet_hours_end)
                if user_config.quiet_hours_start == user_config.quiet_hours_end:
                    raise ValueError
                user_storage.config.update_config(quiet_hours_enabled=True)
                user_config = user_storage.config.get_config()
                response = _format_quiet_hours_status(user_config)
            except ValueError:
                response = "Quiet hours cannot be enabled until the window is valid.\n\nExample: ...quiethours set 22:00 08:00"

    elif subcommand == "off":
        user_storage.config.update_config(quiet_hours_enabled=False)
        user_config = user_storage.config.get_config()
        response = _format_quiet_hours_status(user_config)

    elif subcommand == "set":
        if len(parts) != 3:
            response = "Usage: ...quiethours set <HH:MM> <HH:MM>\n\nExample: ...quiethours set 22:00 08:00"
        else:
            start, end = parts[1], parts[2]
            try:
                parse_hhmm(start)
                parse_hhmm(end)
                if start == end:
                    raise ValueError("equal")
                user_storage.config.update_config(
                    quiet_hours_start=start,
                    quiet_hours_end=end,
                )
                user_config = user_storage.config.get_config()
                response = _format_quiet_hours_status(user_config)
            except ValueError:
                response = "Invalid quiet-hours window. Use 24-hour HH:MM values and make start and end different."

    elif subcommand == "timezone":
        if len(parts) == 1:
            response = f"Current timezone: {user_config.timezone}\n\nExample: ...quiethours timezone Europe/Paris"
        else:
            timezone_name = parts[1]
            if not is_valid_timezone(timezone_name):
                response = (
                    f"Invalid timezone: {timezone_name}\n\n"
                    "Use an IANA timezone such as Europe/Paris or America/New_York."
                )
            else:
                user_storage.config.update_config(timezone=timezone_name)
                user_config = user_storage.config.get_config()
                response = _format_quiet_hours_status(user_config)

    else:
        response = "Unknown quiethours command\n\nAvailable:\n"
        response += "• ...quiethours status - Show quiet-hours status\n"
        response += "• ...quiethours on - Enable quiet hours\n"
        response += "• ...quiethours off - Disable quiet hours\n"
        response += "• ...quiethours set <HH:MM> <HH:MM> - Set quiet window\n"
        response += "• ...quiethours timezone <Area/City> - Set timezone"

    await telegram_bot.send_message(response, chat_id=int(user_id))


async def handle_help(telegram_bot, user_id: str) -> None:
    """Handle the ...help command."""
    help_text = """Available Commands

Status & Information
• ...status - Show model, costs, context, heartbeat status
• ...help - Show this help message

Model Switching
• ...model - Show current model and options
• ...model <name> - Switch model (sonnet/opus/haiku)

Heartbeat Control
• ...heartbeat test - Manual debug heartbeat
• ...heartbeat on - Enable automatic heartbeats
• ...heartbeat off - Disable automatic heartbeats
• ...heartbeat status - Show heartbeat status
• ...heartbeat interval <minutes> - Change interval
• ...quiethours status - Show quiet-hours status
• ...quiethours on/off - Enable or disable quiet hours
• ...quiethours set <HH:MM> <HH:MM> - Set quiet-hours window
• ...quiethours timezone <Area/City> - Set quiet-hours timezone

Conversation
• ...clear - Clear conversation history
• ...showmemory - Show scratchpad memory
• ...clearmemory - Clear scratchpad memory"""

    logger.info(f"Handling help command for user {user_id}")
    await telegram_bot.send_message(help_text, chat_id=int(user_id))


async def handle_clear(telegram_bot, user_id: str) -> None:
    """Handle the ...clear command."""
    logger.info(f"Handling clear command for user {user_id}")

    # Get user-specific storage
    user_storage = get_user_storage(user_id)

    # Get current count before clearing
    messages_before = len(user_storage.messages.get_recent_messages())

    # Clear only message history for this user
    user_storage.messages.clear_messages()

    response = f"Conversation cleared\n\n"
    response += f"Deleted {messages_before} messages.\n\n"
    response += "Scratchpad memory was kept. Use ...clearmemory to wipe stored notes."

    await telegram_bot.send_message(response, chat_id=int(user_id))


async def handle_showmemory(telegram_bot, user_id: str) -> None:
    """Handle the ...showmemory command."""
    logger.info(f"Handling showmemory command for user {user_id}")

    user_storage = get_user_storage(user_id)
    notes = user_storage.scratchpad.get_notes()

    if not notes:
        response = "Scratchpad memory is empty."
        await telegram_bot.send_message(response, chat_id=int(user_id))
        return

    response = "Scratchpad Memory\n\n"
    for note in notes[-20:]:
        timestamp = claude.format_timestamp(note["timestamp"])
        response += f"- [{timestamp}] {note['note']}\n"

    if len(notes) > 20:
        response += f"\nShowing last 20 of {len(notes)} notes."

    await telegram_bot.send_message(response, chat_id=int(user_id))


async def handle_clearmemory(telegram_bot, user_id: str) -> None:
    """Handle the ...clearmemory command."""
    logger.info(f"Handling clearmemory command for user {user_id}")

    user_storage = get_user_storage(user_id)
    notes_before = len(user_storage.scratchpad.get_notes())
    user_storage.scratchpad.clear_notes()

    response = "Scratchpad memory cleared\n\n"
    response += f"Deleted {notes_before} notes."

    await telegram_bot.send_message(response, chat_id=int(user_id))
