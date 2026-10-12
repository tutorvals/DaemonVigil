"""Claude integration via the Claude Agent SDK using Claude Code auth."""
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from datetime import datetime, timezone

from claude_agent_sdk import ClaudeAgentOptions, query

from . import config
from .storage import UserStorageManager, UserConfig

logger = logging.getLogger(__name__)
CLAUDE_CLI_PATH = Path.home() / ".local" / "bin" / "claude"


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
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _extract_text_from_sdk_message(message) -> str:
    """Extract plain text content from an SDK message."""
    content = getattr(message, "content", None)
    if not content:
        return ""

    parts = []
    for block in content:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if text:
            parts.append(text)

    return "\n".join(parts).strip()


def _normalize_usage(usage) -> dict:
    """Convert SDK usage objects into the dict shape expected elsewhere."""
    if isinstance(usage, dict):
        return usage

    if usage is None:
        return {}

    return {
        "input_tokens": getattr(usage, "input_tokens", 0),
        "output_tokens": getattr(usage, "output_tokens", 0),
        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0),
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0),
    }


def _build_sdk_env() -> dict[str, str]:
    """Build SDK environment for a minimal stateless Claude Code-backed request."""
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    env.pop("CLAUDE_CODE", None)
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    env.pop("CLAUDE_TTY", None)
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    return env


async def _collect_sdk_response(prompt: str, options: ClaudeAgentOptions) -> dict:
    """Run a Claude Agent SDK query and normalize the final response shape."""
    assistant_parts = []
    result_message = None

    async for message in query(prompt=prompt, options=options):
        message_type = getattr(message, "type", None)
        message_class = message.__class__.__name__

        if message_type == "assistant" or message_class == "AssistantMessage":
            text = _extract_text_from_sdk_message(message)
            if text:
                assistant_parts.append(text)
        elif message_type == "result" or message_class == "ResultMessage":
            result_message = message

    if result_message is None:
        raise RuntimeError("Claude Agent SDK returned no result message")

    if getattr(result_message, "is_error", False):
        raise RuntimeError(
            f"Claude Agent SDK returned an error result: "
            f"{getattr(result_message, 'subtype', 'error')}"
        )

    usage = _normalize_usage(getattr(result_message, "usage", None))
    result_text = getattr(result_message, "result", "") or "\n".join(assistant_parts).strip()

    return {
        "result": result_text,
        "assistant_text": "\n".join(assistant_parts).strip(),
        "structured_output": getattr(result_message, "structured_output", None),
        "session_id": getattr(result_message, "session_id", None),
        "usage": usage,
        "modelUsage": usage,
        "duration_ms": getattr(result_message, "duration_ms", None),
        "duration_api_ms": getattr(result_message, "duration_api_ms", None),
        "total_cost_usd": getattr(result_message, "total_cost_usd", None),
        "subtype": getattr(result_message, "subtype", None),
        "is_error": getattr(result_message, "is_error", False),
    }


async def _run_claude_sdk(
    prompt: str,
    system_prompt: str,
    model: str,
    json_schema: str = None,
    timeout: int = 120
) -> dict:
    """
    Run Claude via the Agent SDK and return a normalized response.

    Args:
        prompt: The user prompt to send
        system_prompt: System prompt text
        model: Model name or alias
        json_schema: Optional JSON schema for structured output
        timeout: Timeout in seconds

    Returns:
        dict with keys: result, usage, modelUsage, session_id

    Raises:
        RuntimeError: On SDK failure or timeout
    """
    output_format = None
    if json_schema:
        output_format = {
            "type": "json_schema",
            "schema": json.loads(json_schema),
        }

    sdk_env = _build_sdk_env()

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        model=model,
        output_format=output_format,
        cwd=str(config.ROOT_DIR),
        cli_path=str(CLAUDE_CLI_PATH),
        env=sdk_env,
        # Keep the SDK call as close as possible to a plain API-style request.
        tools=[],
        setting_sources=[],
        max_turns=1,
        extra_args={"no-session-persistence": None},
        thinking={"type": "disabled"},
    )

    logger.debug(
        "Agent SDK query: model=%s prompt_length=%s system_prompt_length=%s",
        model,
        len(prompt),
        len(system_prompt),
    )
    start_time = time.monotonic()
    try:
        response = await asyncio.wait_for(
            _collect_sdk_response(prompt=prompt, options=options),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - start_time
        raise RuntimeError(f"Claude Agent SDK timed out after {elapsed:.1f}s (limit: {timeout}s)")
    except Exception as e:
        elapsed = time.monotonic() - start_time
        raise RuntimeError(f"Claude Agent SDK failed after {elapsed:.1f}s: {e}") from e

    elapsed = time.monotonic() - start_time
    logger.debug("Agent SDK query completed in %.1fs", elapsed)
    return response


def _parse_heartbeat_decision(sdk_response: dict) -> dict:
    """Normalize the heartbeat decision from SDK output into a dict."""
    def parse_json_candidate(raw_text: str) -> dict | None:
        candidate = raw_text.strip()
        if not candidate:
            return None

        parse_attempts = [candidate]
        if candidate.startswith("```") and candidate.endswith("```"):
            fence_lines = candidate.splitlines()
            if len(fence_lines) >= 3:
                parse_attempts.append("\n".join(fence_lines[1:-1]).strip())

        for attempt in parse_attempts:
            if not attempt:
                continue
            try:
                parsed = json.loads(attempt)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

        return None

    raw_structured = sdk_response.get("structured_output")
    if isinstance(raw_structured, dict):
        return raw_structured

    raw_candidates = [
        raw_structured,
        sdk_response.get("result"),
        sdk_response.get("assistant_text"),
    ]

    for raw_candidate in raw_candidates:
        if not isinstance(raw_candidate, str):
            continue

        parsed = parse_json_candidate(raw_candidate)
        if parsed is not None:
            return parsed

    details = []
    if raw_structured is not None:
        details.append(f"structured_output={type(raw_structured).__name__}")
    if sdk_response.get("result") is not None:
        details.append(f"result={type(sdk_response.get('result')).__name__}:{len(str(sdk_response.get('result')))}")
    if sdk_response.get("assistant_text") is not None:
        details.append(
            f"assistant_text={type(sdk_response.get('assistant_text')).__name__}:{len(str(sdk_response.get('assistant_text')))}"
        )

    detail_text = ", ".join(details) if details else "no SDK output fields were populated"
    return {
        "action": "stay_silent",
        "reasoning": f"Claude returned no parseable heartbeat decision ({detail_text})"
    }


def _heartbeat_decision_missing(decision: dict) -> bool:
    """Return True when the parsed decision is the empty-output fallback."""
    reasoning = decision.get("reasoning", "")
    return isinstance(reasoning, str) and reasoning.startswith(
        "Claude returned no parseable heartbeat decision"
    )


def _build_heartbeat_json_prompt(current_time: str, retry: bool = False) -> str:
    """Build the heartbeat prompt that asks Claude to emit plain JSON only."""
    prompt = (
        f"[{current_time}] This is a heartbeat check. Review the conversation history and "
        "your notes. Decide whether to reach out to the user or stay silent.\n\n"
        "Return ONLY a valid JSON object with keys: "
        "\"action\" (send_message or stay_silent), "
        "\"reasoning\" (short string), "
        "\"message\" (required only if action is send_message)."
    )

    if retry:
        prompt += (
            "\nDo not include markdown fences, commentary, or any text before or after the JSON object."
        )

    return prompt


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

    prompt = _build_heartbeat_json_prompt(current_time)

    logger.debug(f"Heartbeat context for user {user_id}: "
                 f"{len(recent_messages)} messages, {len(notes)} notes, "
                 f"system prompt {len(full_system_prompt)} chars, "
                 f"model={user_config.model}")

    result["debug_info"]["message_count"] = len(recent_messages)
    result["debug_info"]["note_count"] = len(notes)
    result["debug_info"]["model"] = user_config.model
    result["debug_info"]["system_prompt_length"] = len(full_system_prompt)

    # Call Claude Agent SDK
    try:
        model = config.resolve_model_name(user_config.model)
        
        async def run_heartbeat_attempt(attempt_name: str, attempt_prompt: str, attempt_schema: str | None) -> dict:
            sdk_response = await _run_claude_sdk(
                prompt=attempt_prompt,
                system_prompt=full_system_prompt,
                model=model,
                json_schema=attempt_schema
            )

            usage = sdk_response.get("modelUsage", sdk_response.get("usage", {}))
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            logger.debug(
                "Heartbeat SDK response for user %s attempt=%s input_tokens=%s output_tokens=%s "
                "subtype=%s stop_reason=%s result_len=%s assistant_len=%s",
                user_id,
                attempt_name,
                input_tokens,
                output_tokens,
                sdk_response.get("subtype"),
                sdk_response.get("stop_reason"),
                len(sdk_response.get("result") or ""),
                len(sdk_response.get("assistant_text") or ""),
            )
            return sdk_response

        sdk_response = await run_heartbeat_attempt(
            attempt_name="plain_json_primary",
            attempt_prompt=prompt,
            attempt_schema=None,
        )

        decision = _parse_heartbeat_decision(sdk_response)
        if _heartbeat_decision_missing(decision):
            logger.warning(
                "Heartbeat JSON decision missing for user %s, retrying with stricter JSON prompt: %s",
                user_id,
                decision["reasoning"],
            )
            fallback_prompt = _build_heartbeat_json_prompt(current_time, retry=True)
            fallback_response = await run_heartbeat_attempt(
                attempt_name="plain_json_strict_retry",
                attempt_prompt=fallback_prompt,
                attempt_schema=None,
            )
            fallback_decision = _parse_heartbeat_decision(fallback_response)
            if not _heartbeat_decision_missing(fallback_decision):
                logger.info("Heartbeat strict JSON retry succeeded for user %s", user_id)
                sdk_response = fallback_response
                decision = fallback_decision
            else:
                logger.warning(
                    "Heartbeat strict JSON retry still missing/invalid for user %s: %s",
                    user_id,
                    fallback_decision["reasoning"],
                )

        logger.info(
            "Heartbeat decision for user %s: action=%s",
            user_id,
            decision.get("action"),
        )
        result["reasoning"] = decision.get("reasoning")

        if decision.get("action") == "send_message" and decision.get("message"):
            message = decision["message"]
            logger.info("Heartbeat sending message to user %s", user_id)

            result["tool_called"] = True
            result["message_sent"] = message

            # Send via Telegram to specific user (unless debug mode)
            if not debug:
                logger.info("Sending heartbeat Telegram message to user %s", user_id)
                await telegram_bot.send_message(message, chat_id=int(user_id))
                user_storage.messages.add_message("assistant", message)
                logger.info("Heartbeat Telegram send complete for user %s", user_id)
        else:
            logger.info("Heartbeat stayed silent for user %s", user_id)

        total_usage = sdk_response.get("modelUsage", sdk_response.get("usage", {}))
        result["debug_info"]["input_tokens"] = total_usage.get("input_tokens", 0)
        result["debug_info"]["output_tokens"] = total_usage.get("output_tokens", 0)
        result["debug_info"]["elapsed_seconds"] = round(time.monotonic() - heartbeat_start, 1)

    except Exception as e:
        logger.error(f"Error in Claude Agent SDK call: {e}", exc_info=True)
        result["error"] = str(e)

    logger.info(
        "Heartbeat processing complete for user %s: tool_called=%s error=%s elapsed=%.2fs",
        user_id,
        result["tool_called"],
        result["error"],
        time.monotonic() - heartbeat_start,
    )
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

    # Call Claude Agent SDK
    try:
        model = config.resolve_model_name(user_config.model)
        sdk_response = await _run_claude_sdk(
            prompt=prompt,
            system_prompt=full_system_prompt,
            model=model
        )

        # Extract usage from SDK response
        usage = sdk_response.get("modelUsage", sdk_response.get("usage", {}))
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        logger.info(
            "Claude SDK usage for user %s - Input: %s, Output: %s, subtype=%s stop_reason=%s",
            user_id,
            input_tokens,
            output_tokens,
            sdk_response.get("subtype"),
            sdk_response.get("stop_reason"),
        )

        # Extract text response
        response_text = sdk_response.get("result", "") or ""

        if not response_text:
            logger.warning(f"Empty 'result' for user {user_id}, SDK keys: {list(sdk_response.keys())}")

        if response_text:
            logger.info(f"Claude response to user {user_id}: {response_text[:50]}...")
            await telegram_bot.send_message(response_text, chat_id=int(user_id))
            user_storage.messages.add_message("assistant", response_text)
        else:
            logger.warning(f"Claude returned empty response for user {user_id}")

    except Exception as e:
        logger.error(f"Error in Claude Agent SDK call for user {user_id}: {e}", exc_info=True)
        raise
