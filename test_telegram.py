"""Simple test script for Telegram bot functionality.

This script tests:
1. Receiving messages from Telegram
2. Writing received messages to JSON
3. Sending a response back

Run with: python test_telegram.py
"""
import asyncio
import logging
import sys
from src.telegram_bot import TelegramBot
from src import storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


async def on_user_message(message: str, chat_id: int):
    """Handle incoming messages - just echo back for now."""
    logger.info(f"Received message: '{message}' from chat_id: {chat_id}")

    # The message is already saved to storage by the bot handler
    # Let's send a simple response
    response = f"Got it! You said: '{message}'"
    await bot.send_message(response, chat_id)

    # Also log the response to storage
    storage.messages.add_message("assistant", response)
    logger.info(f"Sent response: '{response}'")


async def main():
    global bot

    logger.info("Starting Telegram bot test...")
    logger.info("Send a message to your bot in Telegram!")
    logger.info("Press Ctrl+C to stop")

    # Create bot with callback
    bot = TelegramBot(on_user_message_callback=on_user_message)

    try:
        # Start the bot
        await bot.start()

        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Stopping bot...")
    finally:
        await bot.stop()

        # Show what was saved
        logger.info("\n=== Messages saved to JSON ===")
        messages = storage.messages.get_recent_messages()
        for msg in messages:
            logger.info(f"[{msg['timestamp']}] {msg['role']}: {msg['content']}")


if __name__ == "__main__":
    asyncio.run(main())
