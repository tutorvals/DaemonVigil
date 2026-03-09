"""Claude integration via CLI subprocess."""
import asyncio
import json
import logging
import os
import time
from datetime import datetime

from . import config
from .storage import UserStorageManager, UserConfig
from . import usage_tracker

logger = logging.getLogger(__name__)

# JSON schema for heartbeat structured output
HEARTBEAT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["send_message", "stay_silent"]
        },
        "message": {
            "type": "string",
            "description": "Message to send if action is send_message"
        },
        "reasoning": {
            "type": "string",
            "description": "Brief reasoning for the decision"
        }
    },
    "required": ["action", "reasoning"]
})


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


async def _run_claude_cli(
    prompt: str,
    system_prompt: str,
    model: str,
    json_schema: str = None,
    timeout: int = 120
) -> dict:
    """
    Run claude CLI non-interactively and return parsed JSON output.

    Args:
        prompt: The user prompt to send
        system_prompt: System prompt text
        model: Model name or alias
        json_schema: Optional JSON schema for structured output
        timeout: Timeout in seconds

    Returns:
        dict with keys: result, usage, model, session_id

    Raises:
        RuntimeError: On CLI failure or timeout
    """
    cmd = [
        'claude', '-p', prompt,
        '--output-format', 'json',
        '--no-session-persistence',
        '--system-prompt', system_prompt,
    ]

    if json_schema:
        cmd.extend(['--json-schema', json_schema])

    # Allow running even if launched from within a claude session
    env = os.environ.copy()
    env.pop('CLAUDE_CODE', None)
    env.pop('CLAUDECODE', None)
    env.pop('ANTHROPIC_API_KEY', None)

    logger.debug(f"CLI command: {' '.join(cmd[:6])}... (prompt length: {len(prompt)} chars)")

    start_time = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        elapsed = time.monotonic() - start_time
        raise RuntimeError(f"Claude CLI timed out after {elapsed:.1f}s (limit: {timeout}s)")

    elapsed = time.monotonic() - start_time
    stderr_text = stderr.decode().strip()
    if stderr_text:
        logger.debug(f"CLI stderr: {stderr_text[:500]}")

    if proc.returncode != 0:
        raise RuntimeError(
            f"Claude CLI failed (exit {proc.returncode}) after {elapsed:.1f}s: "
            f"stderr={stderr_text} stdout={stdout.decode()[:500]}"
        )

    logger.debug(f"CLI completed in {elapsed:.1f}s (exit 0)")

    try:
        parsed = json.loads(stdout.decode())
    except json.JSONDecodeError as e:
        raw = stdout.decode()
        raise RuntimeError(
            f"CLI returned invalid JSON after {elapsed:.1f}s: {e}. "
            f"Raw output: {raw[:500]}"
        )

    return parsed


def load_system_prompt() -> str:
    """Load the system prompt from prompts/system.md."""
    prompt_file = config.ROOT_DIR / "prompts" / "system.md"
    if prompt_file.exists():
        return prompt_file.read_text()
    else:
        return """You are Daemon Vigil, a proactive AI companion for Vals.

You run on a heartbeat, periodically checking in. You have access to conversation history and can choose whether to send a message or stay silent.

Be warm, patient, and genuinely helpful"""


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
    logger.info(f"Processing heartbeat for user {user_id}" + (" (DEBUG MODE)" if debug else ""))
    heartbeat_start = time.monotonic()

    result = {
        "tool_called": False,
        "message_sent": None,
        "reasoning": None,
        "error": None,
        "debug_info": {}
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

    # Build prompts
    system_prompt = load_system_prompt()
    full_system_prompt = f"{system_prompt}\n\n{context}"

    prompt = f"[{current_time}] This is a heartbeat check. Review the conversation history and your notes. Decide whether to reach out to the user or stay silent."

    logger.debug(f"Heartbeat context for user {user_id}: "
                 f"{len(recent_messages)} messages, {len(notes)} notes, "
                 f"system prompt {len(full_system_prompt)} chars, "
                 f"model={user_config.model}")

    result["debug_info"]["message_count"] = len(recent_messages)
    result["debug_info"]["note_count"] = len(notes)
    result["debug_info"]["model"] = user_config.model
    result["debug_info"]["system_prompt_length"] = len(full_system_prompt)

    # Call Claude CLI
    try:
        model = user_config.model
        cli_response = await _run_claude_cli(
            prompt=prompt,
            system_prompt=full_system_prompt,
            model=model,
            json_schema=HEARTBEAT_SCHEMA
        )

        # Extract usage from CLI response (prefer modelUsage over usage)
        usage = cli_response.get("modelUsage", cli_response.get("usage", {}))
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        # Track usage and cost
        usage_data = usage_tracker.calculate_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        usage_data["request_type"] = "heartbeat"
        usage_data["user_id"] = user_id
        usage_tracker.log_api_usage(usage_data)

        # Check billing threshold
        await usage_tracker.check_and_notify_threshold(
            telegram_bot=telegram_bot,
            last_cost=usage_data['total_cost'],
            user_id=user_id
        )

        elapsed = time.monotonic() - heartbeat_start
        logger.info(f"API Usage (user {user_id}) - Input: {input_tokens}, "
                   f"Output: {output_tokens}, "
                   f"Cost: ${usage_data['total_cost']:.6f}, "
                   f"Time: {elapsed:.1f}s")

        result["debug_info"]["input_tokens"] = input_tokens
        result["debug_info"]["output_tokens"] = output_tokens
        result["debug_info"]["cost"] = usage_data['total_cost']
        result["debug_info"]["elapsed_seconds"] = round(elapsed, 1)

        # Parse structured JSON decision — CLI puts it in structured_output, not result
        raw_result = cli_response.get("structured_output", cli_response.get("result", ""))
        logger.info(f"Heartbeat output for user {user_id} (type={type(raw_result).__name__}): {str(raw_result)[:500]}")

        try:
            decision = json.loads(raw_result)
        except (json.JSONDecodeError, TypeError):
            # If result is already a dict (some CLI versions)
            decision = raw_result if isinstance(raw_result, dict) else {
                "action": "stay_silent",
                "reasoning": f"Failed to parse CLI output: {str(raw_result)[:200]}"
            }
            logger.warning(f"Failed to parse heartbeat decision as JSON for user {user_id}, "
                          f"type={type(raw_result).__name__}")

        logger.debug(f"Heartbeat decision for user {user_id}: action={decision.get('action')}")
        result["reasoning"] = decision.get("reasoning")

        if decision.get("action") == "send_message" and decision.get("message"):
            message = decision["message"]
            logger.info(f"Claude decided to send message to user {user_id}: {message[:50]}...")

            result["tool_called"] = True
            result["message_sent"] = message

            # Send via Telegram to specific user (unless debug mode)
            if not debug:
                await telegram_bot.send_message(message, chat_id=int(user_id))
                user_storage.messages.add_message("assistant", message)
        else:
            logger.info("Claude chose not to send a message this cycle")

    except Exception as e:
        logger.error(f"Error in Claude CLI call: {e}", exc_info=True)
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
    logger.info(f"Responding to user {user_id}: {user_message[:50]}...")

    # Load user's recent messages
    recent_messages = user_storage.messages.get_recent_messages(user_config.max_context_messages)

    # Flatten conversation history into the prompt
    conversation_lines = []
    for msg in recent_messages:
        timestamp = format_timestamp(msg["timestamp"])
        conversation_lines.append(f"[{timestamp}] {msg['role']}: {msg['content']}")
    conversation_text = "\n".join(conversation_lines)

    # Build system prompt with scratchpad context and current time
    notes = user_storage.scratchpad.get_notes()
    context_parts = []

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

    # Build prompt with conversation history
    prompt = f"Here is the recent conversation:\n{conversation_text}\n\nRespond to the user's latest message."

    # Call Claude CLI
    try:
        model = user_config.model
        cli_response = await _run_claude_cli(
            prompt=prompt,
            system_prompt=full_system_prompt,
            model=model
        )

        # Extract usage (prefer modelUsage over usage)
        usage = cli_response.get("modelUsage", cli_response.get("usage", {}))
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        # Track usage and cost
        usage_data = usage_tracker.calculate_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        usage_data["request_type"] = "user_response"
        usage_data["user_id"] = user_id
        usage_data["user_message_preview"] = user_message[:50]
        usage_tracker.log_api_usage(usage_data)

        # Check billing threshold
        await usage_tracker.check_and_notify_threshold(
            telegram_bot=telegram_bot,
            last_cost=usage_data['total_cost'],
            user_id=user_id
        )

        logger.info(f"API Usage (user {user_id}) - Input: {input_tokens}, "
                   f"Output: {output_tokens}, "
                   f"Cost: ${usage_data['total_cost']:.6f}")

        # Extract text response
        response_text = cli_response.get("result", "") or ""

        if not response_text:
            logger.warning(f"Empty 'result' for user {user_id}, CLI keys: {list(cli_response.keys())}")

        if response_text:
            logger.info(f"Claude response to user {user_id}: {response_text[:50]}...")
            await telegram_bot.send_message(response_text, chat_id=int(user_id))
            user_storage.messages.add_message("assistant", response_text)
        else:
            logger.warning(f"Claude returned empty response for user {user_id}")

    except Exception as e:
        logger.error(f"Error in Claude CLI call for user {user_id}: {e}", exc_info=True)
        raise
