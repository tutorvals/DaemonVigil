"""Configuration loading for Daemon Vigil."""
import os
from pathlib import Path
from dotenv import load_dotenv
import yaml

# Load environment variables from .env file
load_dotenv()

# Project root directory
ROOT_DIR = Path(__file__).parent.parent

# Data directory
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Paths to data files
MESSAGES_FILE = DATA_DIR / "messages.json"
SCRATCHPAD_FILE = DATA_DIR / "scratchpad.json"

# Load config.yaml
CONFIG_FILE = ROOT_DIR / "config.yaml"
with open(CONFIG_FILE, 'r') as f:
    config = yaml.safe_load(f)

# Environment variables (required)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Validate required environment variables
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")

# Config values with defaults
HEARTBEAT_INTERVAL_MINUTES = config.get("heartbeat_interval_minutes", 15)
MAX_CONTEXT_MESSAGES = config.get("max_context_messages", 50)
TELEGRAM_CHAT_ID = config.get("telegram_chat_id")
CLAUDE_MODEL = config.get("claude_model", "claude-sonnet-4-20250514")


def update_config(key: str, value) -> None:
    """Update a configuration value and save to config.yaml."""
    config[key] = value
    with open(CONFIG_FILE, 'w') as f:
        yaml.safe_dump(config, f, default_flow_style=False)


def get_config(key: str, default=None):
    """Get a configuration value."""
    return config.get(key, default)
