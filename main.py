"""Daemon Vigil - Proactive AI Companion

Entry point for the application.
"""
import argparse
import asyncio
import logging
import signal
import sys

from src.app import DaemonVigil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('daemon_vigil.log')
    ]
)

# Reduce Telegram HTTP request logging unless it errors
logging.getLogger('httpx').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main(silent: bool = False):
    """Main entry point."""
    app = DaemonVigil(silent=silent)

    # Register signal handlers
    signal.signal(signal.SIGINT, lambda s, f: app.handle_shutdown(s, f))
    signal.signal(signal.SIGTERM, lambda s, f: app.handle_shutdown(s, f))

    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await app.stop()


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Daemon Vigil - Proactive AI Companion")
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Suppress startup and shutdown notifications in Telegram"
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(silent=args.silent))
    except KeyboardInterrupt:
        logger.info("Exiting...")
