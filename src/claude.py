"""Claude API integration."""
import logging
from pathlib import Path
from datetime import datetime
from anthropic import Anthropic

from . import config
from . import storage
from .storage import UserStorageManager, UserConfig
from . import usage_tracker

logger = logging.getLogger(__name__)


def format_timestamp(iso_timestamp: str) -> str:
    """
    Format ISO timestamp to human-readable format.

    Args:
        iso_timestamp: ISO format timestamp string

    Returns:
        Formatted string like "2025-12-03 15:30:42 UTC"
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except:
        return iso_timestamp


def get_current_time_str() -> str:
    """Get current time as formatted string."""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

# Initialize Anthropic client
client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

# Tool definition for Claude
TOOLS = [
    {
        "name": "send_message",
        "description": "Send a message to Vals via Telegram. Use this to check in, ask how he's doing, offer help, or gently prompt. You may also choose NOT to call this tool if silence is more appropriate (e.g., user just said they're going for a run).",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to send"
                }
            },
            "required": ["message"]
        }
    }
]


def load_system_prompt() -> str:
    """Load the system prompt from prompts/system.md."""
    prompt_file = config.ROOT_DIR / "prompts" / "system.md"
    if prompt_file.exists():
        return prompt_file.read_text()
    else:
        # Fallback basic prompt if file doesn't exist yet
        return """You are Daemon Vigil, a proactive AI companion for Vals.

You run on a heartbeat, periodically checking in. You have access to conversation history and can choose whether to send a message or stay silent.

Be warm, patient, and genuinely helpful. No pressure, no "shoulds", no productivity guilt. Just a supportive presence."""


async def process_heartbeat(
    telegram_bot,
    user_id: str,
    user_storage: UserStorageManager,
    user_config: UserConfig,
    debug: bool = False
) -> dict:
    """
    Process a heartbeat cycle for a specific user: load context, call Claude, handle response.

    Args:
        telegram_bot: TelegramBot instance for sending messages
        user_id: User ID (Telegram chat ID as string)
        user_storage: User's storage manager
        user_config: User's configuration
        debug: If True, return full Claude response including reasoning

    Returns:
        dict with response details (for debug mode)
    """
    logger.info(f"💓 Processing heartbeat for user {user_id}" + (" (DEBUG MODE)" if debug else ""))

    result = {
        "tool_called": False,
        "message_sent": None,
        "reasoning": None,
        "error": None
    }

    # Load user's recent messages as context
    recent_messages = user_storage.messages.get_recent_messages(user_config.max_context_messages)

    # Load user's scratchpad notes
    notes = user_storage.scratchpad.get_notes()

    # Build context string for system prompt
    context_parts = []

    # Add current time
    current_time = get_current_time_str()
    context_parts.append(f"## Current Time: {current_time}")
    context_parts.append("")

    if notes:
        context_parts.append("## Your Notes (Scratchpad):")
        for note in notes[-10:]:  # Last 10 notes
            timestamp = format_timestamp(note['timestamp'])
            context_parts.append(f"- [{timestamp}] {note['note']}")
        context_parts.append("")

    if recent_messages:
        context_parts.append("## Recent Conversation:")
        for msg in recent_messages:
            timestamp = format_timestamp(msg['timestamp'])
            context_parts.append(f"[{timestamp}] {msg['role']}: {msg['content']}")
    else:
        context_parts.append("## Recent Conversation:")
        context_parts.append("(No conversation history yet)")

    context = "\n".join(context_parts)

    # Build messages for Claude
    system_prompt = load_system_prompt()
    full_system_prompt = f"{system_prompt}\n\n{context}"

    messages = [
        {
            "role": "user",
            "content": f"[{current_time}] This is a heartbeat check. Review the conversation history and your notes. Decide whether to reach out to Vals or stay silent."
        }
    ]

    # Call Claude API
    try:
        # Use user's preferred model
        model = user_config.model
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=full_system_prompt,
            messages=messages,
            tools=TOOLS
        )

        # Track usage and cost with user_id
        usage_data = usage_tracker.calculate_cost(
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )
        usage_data["request_type"] = "heartbeat"
        usage_data["user_id"] = user_id  # Track per-user costs
        usage_tracker.log_api_usage(usage_data)

        logger.info(f"💰 API Usage (user {user_id}) - Input: {response.usage.input_tokens}, "
                   f"Output: {response.usage.output_tokens}, "
                   f"Cost: ${usage_data['total_cost']:.6f}")

        # Process response
        for block in response.content:
            if block.type == "tool_use" and block.name == "send_message":
                message = block.input["message"]
                logger.info(f"Claude decided to send message to user {user_id}: {message[:50]}...")

                result["tool_called"] = True
                result["message_sent"] = message

                # Send via Telegram to specific user (unless debug mode)
                if not debug:
                    await telegram_bot.send_message(message, chat_id=int(user_id))
                    # Log as assistant message in user's storage
                    user_storage.messages.add_message("assistant", message)

            elif block.type == "text":
                # Claude's internal reasoning
                result["reasoning"] = block.text
                logger.debug(f"Claude reasoning: {block.text}")

        # If no tool was called, Claude chose silence
        if not any(block.type == "tool_use" for block in response.content):
            logger.info("Claude chose not to send a message this cycle")

    except Exception as e:
        logger.error(f"Error in Claude API call: {e}", exc_info=True)
        result["error"] = str(e)

    return result


async def respond_to_user(
    user_message: str,
    telegram_bot,
    user_id: str,
    user_storage: UserStorageManager,
    user_config: UserConfig
) -> None:
    """
    Respond immediately to a user message (outside of heartbeat).

    Args:
        user_message: The message from the user
        telegram_bot: TelegramBot instance for sending messages
        user_id: User ID (Telegram chat ID as string)
        user_storage: User's storage manager
        user_config: User's configuration
    """
    logger.info(f"🤖 Responding to user {user_id}: {user_message[:50]}...")

    # Load user's recent messages
    recent_messages = user_storage.messages.get_recent_messages(user_config.max_context_messages)

    # Build conversation for Claude with timestamps in content
    messages = []
    for msg in recent_messages:
        timestamp = format_timestamp(msg["timestamp"])
        # Prepend timestamp to message content
        content_with_time = f"[{timestamp}] {msg['content']}"
        messages.append({
            "role": msg["role"],
            "content": content_with_time
        })

    # Load system prompt with user's scratchpad context and current time
    notes = user_storage.scratchpad.get_notes()
    context_parts = []

    # Add current time
    current_time = get_current_time_str()
    context_parts.append(f"## Current Time: {current_time}")
    context_parts.append("")

    if notes:
        context_parts.append("## Your Notes (Scratchpad):")
        for note in notes[-10:]:
            timestamp = format_timestamp(note['timestamp'])
            context_parts.append(f"- [{timestamp}] {note['note']}")
        context_parts.append("")

    system_prompt = load_system_prompt()
    if context_parts:
        full_system_prompt = f"{system_prompt}\n\n" + "\n".join(context_parts)
    else:
        full_system_prompt = system_prompt

    # Call Claude API
    try:
        # Use user's preferred model
        model = user_config.model
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=full_system_prompt,
            messages=messages
        )

        # Track usage and cost with user_id
        usage_data = usage_tracker.calculate_cost(
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )
        usage_data["request_type"] = "user_response"
        usage_data["user_id"] = user_id  # Track per-user costs
        usage_data["user_message_preview"] = user_message[:50]
        usage_tracker.log_api_usage(usage_data)

        logger.info(f"💰 API Usage (user {user_id}) - Input: {response.usage.input_tokens}, "
                   f"Output: {response.usage.output_tokens}, "
                   f"Cost: ${usage_data['total_cost']:.6f}")

        # Extract text response
        response_text = ""
        for block in response.content:
            if block.type == "text":
                response_text += block.text

        if response_text:
            logger.info(f"Claude response to user {user_id}: {response_text[:50]}...")

            # Send via Telegram to specific user
            await telegram_bot.send_message(response_text, chat_id=int(user_id))

            # Log as assistant message in user's storage
            user_storage.messages.add_message("assistant", response_text)
        else:
            logger.warning(f"Claude returned empty response for user {user_id}")

    except Exception as e:
        logger.error(f"Error in Claude API call for user {user_id}: {e}", exc_info=True)
        raise
