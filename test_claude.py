"""Test Claude CLI integration.

This script tests:
1. Basic Claude CLI connectivity
2. Structured JSON output (heartbeat decision-making)
3. Context loading from conversation history
4. Scratchpad integration

Uses haiku (cheapest model) for testing.
"""
import asyncio
import json
import logging
import sys

from src.claude import _run_claude_cli, HEARTBEAT_SCHEMA
from src.storage import get_user_storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

TEST_MODEL = "haiku"
TEST_USER_ID = "test_user"


async def test_basic_response():
    """Test 1: Basic CLI call."""
    logger.info("\n=== Test 1: Basic Claude Response ===")

    try:
        response = await _run_claude_cli(
            prompt="Say 'CLI test successful' in exactly those words.",
            system_prompt="You are a helpful assistant.",
            model=TEST_MODEL
        )

        result = response.get("result", "")
        logger.info(f"Claude responded: {result}")
        return True
    except Exception as e:
        logger.error(f"Failed: {e}")
        return False


async def test_heartbeat_decision():
    """Test 2: Structured JSON output - should Claude stay silent?"""
    logger.info("\n=== Test 2: Heartbeat Decision (JSON Schema) ===")

    system_prompt = """You are Daemon Vigil. You check in periodically with a user.

## Recent Conversation:
[2025-12-03T10:00:00Z] user: Hey, I'm going to take a break and go for a walk
[2025-12-03T10:00:05Z] assistant: Enjoy your walk!

It's now 10:02 (2 minutes later). Decide whether to send a message or stay silent.

## Your Decision Format
Output a JSON decision with:
- action: "send_message" or "stay_silent"
- message: The message to send (if action is "send_message")
- reasoning: Brief explanation of your decision"""

    try:
        response = await _run_claude_cli(
            prompt="Heartbeat check - review context and decide.",
            system_prompt=system_prompt,
            model=TEST_MODEL,
            json_schema=HEARTBEAT_SCHEMA
        )

        raw_result = response.get("result", "")
        try:
            decision = json.loads(raw_result)
        except (json.JSONDecodeError, TypeError):
            decision = raw_result if isinstance(raw_result, dict) else {}

        action = decision.get("action", "unknown")
        reasoning = decision.get("reasoning", "")

        if action == "send_message":
            logger.info(f"Claude DECIDED TO MESSAGE: '{decision.get('message', '')}'")
            logger.warning("  (Expected: silent, since user just left for a walk)")
        elif action == "stay_silent":
            logger.info("Claude STAYED SILENT")
            logger.info("  (Expected behavior - user just went for a walk)")
        else:
            logger.warning(f"Unexpected action: {action}")

        logger.info(f"  Reasoning: {reasoning}")
        return True
    except Exception as e:
        logger.error(f"Failed: {e}")
        return False


async def test_context_loading():
    """Test 3: Load conversation history and respond."""
    logger.info("\n=== Test 3: Context Loading & Response ===")

    user_storage = get_user_storage(TEST_USER_ID)
    user_storage.messages.clear_messages()
    user_storage.messages.add_message("user", "Hey, testing the bot!")
    user_storage.messages.add_message("assistant", "Hi! Test received successfully.")
    user_storage.messages.add_message("user", "What was my first message?")

    recent_messages = user_storage.messages.get_recent_messages(10)
    conversation = "\n".join(
        f"{msg['role']}: {msg['content']}" for msg in recent_messages
    )

    logger.info(f"Loaded {len(recent_messages)} messages from storage")

    try:
        response = await _run_claude_cli(
            prompt=f"Here is the conversation:\n{conversation}\n\nRespond to the user's latest message.",
            system_prompt="You are a helpful assistant. Answer based on conversation history.",
            model=TEST_MODEL
        )

        result = response.get("result", "")
        logger.info(f"Claude responded: {result}")
        logger.info("  (Should reference 'testing the bot' from history)")
        return True
    except Exception as e:
        logger.error(f"Failed: {e}")
        return False


async def test_scratchpad():
    """Test 4: Scratchpad context."""
    logger.info("\n=== Test 4: Scratchpad Integration ===")

    user_storage = get_user_storage(TEST_USER_ID)
    user_storage.scratchpad.clear_notes()
    user_storage.scratchpad.add_note("User mentioned wanting to work on a Python project")

    notes = user_storage.scratchpad.get_notes()
    logger.info(f"Loaded {len(notes)} notes from scratchpad")

    context = "## Your Notes:\n"
    for note in notes:
        context += f"- {note['note']}\n"

    try:
        response = await _run_claude_cli(
            prompt="What do you remember about what I'm working on?",
            system_prompt=f"You are Daemon Vigil.\n\n{context}",
            model=TEST_MODEL
        )

        result = response.get("result", "")
        logger.info(f"Claude responded: {result}")
        logger.info("  (Should reference the Python project)")
        return True
    except Exception as e:
        logger.error(f"Failed: {e}")
        return False


async def main():
    logger.info("=== Claude CLI Integration Test Suite ===")
    logger.info(f"Using model: {TEST_MODEL} (cheap for testing)")
    logger.info("Uses your Claude Code OAuth subscription\n")

    results = []

    results.append(await test_basic_response())
    results.append(await test_heartbeat_decision())
    results.append(await test_context_loading())
    results.append(await test_scratchpad())

    logger.info("\n=== Test Summary ===")
    logger.info(f"Passed: {sum(results)}/{len(results)}")

    if all(results):
        logger.info("All tests passed! Claude CLI integration is working.")
        logger.info("\nNext: Run 'python main.py' to test the full system")
    else:
        logger.error("Some tests failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())
