"""Test Claude integration without burning credits.

This script tests:
1. Basic Claude API connectivity
2. Tool calling (send_message decision-making)
3. Context loading from conversation history
4. Response generation

Uses claude-3-haiku (cheapest model) for testing.
"""
import asyncio
import logging
import sys
from anthropic import Anthropic

from src import config
from src import storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Use Haiku for cheap testing
TEST_MODEL = "claude-3-5-haiku-20241022"

client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

TOOLS = [
    {
        "name": "send_message",
        "description": "Send a message to Vals via Telegram.",
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


async def test_basic_response():
    """Test 1: Basic API call without tools."""
    logger.info("\n=== Test 1: Basic Claude Response ===")

    try:
        response = client.messages.create(
            model=TEST_MODEL,
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Say 'API test successful' in exactly those words."}
            ]
        )

        result = response.content[0].text
        logger.info(f"✓ Claude responded: {result}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed: {e}")
        return False


async def test_tool_calling():
    """Test 2: Tool calling - should Claude send a message?"""
    logger.info("\n=== Test 2: Tool Calling (Heartbeat Decision) ===")

    # Create a test scenario
    system_prompt = """You are Daemon Vigil. You check in periodically with Vals.

## Recent Conversation:
[2025-12-03T10:00:00Z] user: Hey, I'm going to take a break and go for a walk
[2025-12-03T10:00:05Z] assistant: Enjoy your walk!

It's now 10:02 (2 minutes later). Decide whether to send a message or stay silent."""

    try:
        response = client.messages.create(
            model=TEST_MODEL,
            max_tokens=200,
            system=system_prompt,
            messages=[
                {"role": "user", "content": "Heartbeat check - review context and decide."}
            ],
            tools=TOOLS
        )

        # Check what Claude decided
        has_tool_use = any(block.type == "tool_use" for block in response.content)

        if has_tool_use:
            tool_block = next(b for b in response.content if b.type == "tool_use")
            message = tool_block.input["message"]
            logger.info(f"✓ Claude DECIDED TO MESSAGE: '{message}'")
            logger.warning("  (Expected: silent, since user just left for a walk)")
        else:
            logger.info("✓ Claude STAYED SILENT")
            logger.info("  (Expected behavior - user just went for a walk)")

        # Show reasoning if any
        for block in response.content:
            if block.type == "text":
                logger.info(f"  Claude's reasoning: {block.text}")

        return True
    except Exception as e:
        logger.error(f"✗ Failed: {e}")
        return False


async def test_context_loading():
    """Test 3: Load actual conversation history and respond."""
    logger.info("\n=== Test 3: Context Loading & Response ===")

    # Add some test messages to storage
    storage.messages.clear_messages()  # Start fresh
    storage.messages.add_message("user", "Hey, testing the bot!")
    storage.messages.add_message("assistant", "Hi! Test received successfully.")
    storage.messages.add_message("user", "What was my first message?")

    # Load and format messages
    recent_messages = storage.messages.get_recent_messages(10)
    formatted_messages = []
    for msg in recent_messages:
        formatted_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    logger.info(f"Loaded {len(formatted_messages)} messages from storage")

    try:
        response = client.messages.create(
            model=TEST_MODEL,
            max_tokens=100,
            system="You are a helpful assistant. Answer based on conversation history.",
            messages=formatted_messages
        )

        result = response.content[0].text
        logger.info(f"✓ Claude responded: {result}")
        logger.info("  (Should reference 'testing the bot' from history)")
        return True
    except Exception as e:
        logger.error(f"✗ Failed: {e}")
        return False


async def test_scratchpad():
    """Test 4: Scratchpad context."""
    logger.info("\n=== Test 4: Scratchpad Integration ===")

    # Add a test note
    storage.scratchpad.clear_notes()
    storage.scratchpad.add_note("Vals mentioned wanting to work on a Python project")

    notes = storage.scratchpad.get_notes()
    logger.info(f"Loaded {len(notes)} notes from scratchpad")

    # Build context
    context = "## Your Notes:\n"
    for note in notes:
        context += f"- {note['note']}\n"

    try:
        response = client.messages.create(
            model=TEST_MODEL,
            max_tokens=100,
            system=f"You are Daemon Vigil.\n\n{context}",
            messages=[
                {"role": "user", "content": "What do you remember about what I'm working on?"}
            ]
        )

        result = response.content[0].text
        logger.info(f"✓ Claude responded: {result}")
        logger.info("  (Should reference the Python project)")
        return True
    except Exception as e:
        logger.error(f"✗ Failed: {e}")
        return False


async def main():
    logger.info("=== Claude Integration Test Suite ===")
    logger.info(f"Using model: {TEST_MODEL} (cheap for testing)")
    logger.info("This will use minimal tokens/credits\n")

    results = []

    # Run tests
    results.append(await test_basic_response())
    results.append(await test_tool_calling())
    results.append(await test_context_loading())
    results.append(await test_scratchpad())

    # Summary
    logger.info("\n=== Test Summary ===")
    logger.info(f"Passed: {sum(results)}/{len(results)}")

    if all(results):
        logger.info("✓ All tests passed! Claude integration is working.")
        logger.info("\nNext: Run 'python main.py' to test the full system")
    else:
        logger.error("✗ Some tests failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())
