"""API usage tracking and cost calculation."""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, Optional

from . import config

logger = logging.getLogger(__name__)

# Pricing per million tokens (as of Dec 2025)
PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
    "claude-opus-4-5-20251101": {"input": 15.00, "output": 75.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}

USAGE_FILE = config.DATA_DIR / "api_usage.jsonl"
THRESHOLD_STATE_FILE = config.DATA_DIR / "billing_thresholds.json"


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> Dict:
    """
    Calculate cost for a Claude API call.

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        dict with token counts, costs, model, and timestamp
    """
    pricing = PRICING.get(model, PRICING["claude-sonnet-4-20250514"])

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    total_cost = input_cost + output_cost

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "total_cost": round(total_cost, 6),
        "model": model,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


def log_api_usage(usage_data: Dict) -> None:
    """
    Log API usage to JSONL file.

    Args:
        usage_data: Dict containing usage and cost information
    """
    with open(USAGE_FILE, 'a') as f:
        f.write(json.dumps(usage_data) + '\n')


def get_usage_stats(days: int) -> Dict:
    """
    Get usage statistics for the last N days.

    Args:
        days: Number of days to look back

    Returns:
        dict with aggregated usage statistics
    """
    if not USAGE_FILE.exists():
        return {
            "total_cost": 0.0,
            "total_tokens": 0,
            "request_count": 0,
            "input_tokens": 0,
            "output_tokens": 0
        }

    from datetime import timezone
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    request_count = 0

    with open(USAGE_FILE, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line)
                entry_time = datetime.fromisoformat(entry["timestamp"].replace('Z', '+00:00'))

                if entry_time < cutoff_date:
                    continue

                total_input_tokens += entry["input_tokens"]
                total_output_tokens += entry["output_tokens"]
                total_cost += entry["total_cost"]
                request_count += 1

            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    return {
        "total_cost": round(total_cost, 4),
        "total_tokens": total_input_tokens + total_output_tokens,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "request_count": request_count
    }


def get_daily_total() -> float:
    """
    Get total spending for today (UTC).

    Returns:
        Total cost in dollars for today
    """
    today_stats = get_usage_stats(1)
    return today_stats["total_cost"]


def load_threshold_state() -> Dict:
    """
    Load threshold state from disk and reset if it's a new day.

    Returns:
        dict with 'last_reset_date' and 'notified_thresholds' list
    """
    from datetime import timezone
    today = datetime.now(timezone.utc).date().isoformat()

    # Try to load existing state
    if THRESHOLD_STATE_FILE.exists():
        try:
            with open(THRESHOLD_STATE_FILE, 'r') as f:
                state = json.load(f)

            # Check if it's a new day - reset if so
            if state.get("last_reset_date") != today:
                state = {
                    "last_reset_date": today,
                    "notified_thresholds": []
                }
                save_threshold_state(state)

            return state

        except (json.JSONDecodeError, KeyError):
            pass  # Fall through to create new state

    # Create new state
    state = {
        "last_reset_date": today,
        "notified_thresholds": []
    }
    save_threshold_state(state)
    return state


def save_threshold_state(state: Dict) -> None:
    """
    Save threshold state to disk.

    Args:
        state: dict with 'last_reset_date' and 'notified_thresholds'
    """
    with open(THRESHOLD_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def check_threshold_crossed(previous_total: float, new_total: float,
                            notified_thresholds: list) -> Optional[int]:
    """
    Check if a new dollar threshold was crossed.

    Args:
        previous_total: Total cost before the latest API call
        new_total: Total cost after the latest API call
        notified_thresholds: List of thresholds already notified today

    Returns:
        The highest threshold number that was crossed (e.g., 3 for $3),
        or None if no new threshold was crossed
    """
    import math

    # Find the highest threshold crossed
    previous_threshold = math.floor(previous_total)
    new_threshold = math.floor(new_total)

    # Check if we crossed into a new dollar threshold
    if new_threshold > previous_threshold:
        # Find the highest new threshold not yet notified
        for threshold in range(new_threshold, previous_threshold, -1):
            if threshold > 0 and threshold not in notified_thresholds:
                return threshold

    return None


async def check_and_notify_threshold(telegram_bot, last_cost: float, chat_id: int = None) -> None:
    """
    Check if a threshold was crossed and send notification if needed.

    This should be called after each API call is logged.

    Args:
        telegram_bot: TelegramBot instance for sending messages
        last_cost: Cost of the most recent API call
        chat_id: Optional chat ID to send notification to
    """
    try:
        # Load threshold state (auto-resets if new day)
        state = load_threshold_state()

        # Get current daily total
        current_total = get_daily_total()

        # Calculate previous total (before this API call)
        previous_total = current_total - last_cost

        # Check if threshold was crossed
        threshold = check_threshold_crossed(
            previous_total,
            current_total,
            state["notified_thresholds"]
        )

        if threshold is not None:
            # Threshold crossed! Send notification
            today_stats = get_usage_stats(1)

            message = (
                f"💰 Daily Billing Alert\n\n"
                f"You've crossed the ${threshold} threshold today.\n\n"
                f"Today's total: ${current_total:.2f} ({today_stats['request_count']} requests)\n\n"
                f"Track usage with: ...status"
            )

            logger.info(f"Threshold ${threshold} crossed. Sending notification.")

            # Send notification via Telegram
            if telegram_bot:
                await telegram_bot.send_message(message, chat_id=chat_id)
            else:
                logger.warning("Telegram bot not available, skipping threshold notification")

            # Mark all crossed thresholds as notified (in case we jumped multiple)
            for t in range(int(previous_total) + 1, threshold + 1):
                if t not in state["notified_thresholds"]:
                    state["notified_thresholds"].append(t)

            # Save updated state
            save_threshold_state(state)
            logger.info(f"Updated threshold state: {state['notified_thresholds']}")

    except Exception as e:
        logger.error(f"Error checking billing threshold: {e}", exc_info=True)


def format_usage_report() -> str:
    """
    Format a usage report for display.

    Returns:
        Formatted string with usage statistics
    """
    from . import storage
    from main import DaemonVigil

    today_stats = get_usage_stats(1)
    week_stats = get_usage_stats(7)
    month_stats = get_usage_stats(30)

    report = "📊 Status Report\n\n"
    report += f"Model: {config.get_claude_model()}\n\n"

    # Heartbeat status
    app = DaemonVigil.get_instance()
    if app and app.scheduler:
        status = app.scheduler.get_status()
        report += "💓 Heartbeat:\n"
        report += f"State: {'✅ Enabled' if status['enabled'] else '🔇 Disabled'}\n"
        report += f"Interval: {status['interval_minutes']} minutes\n"
        if status['next_run']:
            report += f"Next run: {status['next_run'].strftime('%H:%M:%S UTC')}\n"
        report += "\n"

    # Context information
    messages = storage.messages.get_recent_messages()
    notes = storage.scratchpad.get_notes()

    report += "📚 Context:\n"
    report += f"Messages in history: {len(messages)}\n"
    report += f"Scratchpad notes: {len(notes)}\n"

    if notes:
        last_note = notes[-1]
        # Truncate if too long
        note_preview = last_note['note']
        if len(note_preview) > 80:
            note_preview = note_preview[:77] + "..."
        report += f"Last note: {note_preview}\n"

    report += "\n💰 API Costs:\n"

    if today_stats["request_count"] == 0:
        report += "No API usage recorded yet\n"
    else:
        report += f"Today:      ${today_stats['total_cost']:.4f} ({today_stats['request_count']} requests)\n"
        report += f"This Week:  ${week_stats['total_cost']:.4f} ({week_stats['request_count']} requests)\n"
        report += f"This Month: ${month_stats['total_cost']:.4f} ({month_stats['request_count']} requests)\n"

        report += "\n📈 Usage Today:\n"
        report += f"Total tokens: {today_stats['total_tokens']:,} "
        report += f"({today_stats['input_tokens']:,} in, {today_stats['output_tokens']:,} out)"

    return report
