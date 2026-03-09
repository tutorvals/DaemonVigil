"""API usage tracking and cost calculation."""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, Optional, List

from . import config
from .storage import get_user_storage

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
        usage_data: Dict containing usage and cost information.
                   Must include 'user_id' field for per-user tracking.
    """
    if "user_id" not in usage_data:
        logger.warning("Usage data missing user_id - cannot track per-user costs")
        usage_data["user_id"] = "unknown"

    with open(USAGE_FILE, 'a') as f:
        f.write(json.dumps(usage_data) + '\n')


def get_usage_stats(days: int) -> Dict:
    """
    Get global usage statistics for the last N days (all users combined).

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
    Get total spending for today (UTC) across all users.
    Owner pays one bill for all users.

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

    if THRESHOLD_STATE_FILE.exists():
        try:
            with open(THRESHOLD_STATE_FILE, 'r') as f:
                state = json.load(f)

            if state.get("last_reset_date") != today:
                state = {
                    "last_reset_date": today,
                    "notified_thresholds": []
                }
                save_threshold_state(state)

            return state

        except (json.JSONDecodeError, KeyError):
            pass

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

    previous_threshold = math.floor(previous_total)
    new_threshold = math.floor(new_total)

    if new_threshold > previous_threshold:
        for threshold in range(new_threshold, previous_threshold, -1):
            if threshold > 0 and threshold not in notified_thresholds:
                return threshold

    return None


async def check_and_notify_threshold(telegram_bot, last_cost: float, user_id: str = None) -> None:
    """
    Check if a threshold was crossed and send notification if needed.

    This should be called after each API call is logged.

    Args:
        telegram_bot: TelegramBot instance for sending messages
        last_cost: Cost of the most recent API call
        user_id: User ID to send notification to (optional, falls back to config)
    """
    try:
        state = load_threshold_state()
        current_total = get_daily_total()
        previous_total = current_total - last_cost

        threshold = check_threshold_crossed(
            previous_total,
            current_total,
            state["notified_thresholds"]
        )

        if threshold is not None:
            today_stats = get_usage_stats(1)

            message = (
                f"Daily Billing Alert\n\n"
                f"Crossed the ${threshold} threshold today.\n\n"
                f"Today's total: ${current_total:.2f} ({today_stats['request_count']} requests)\n\n"
                f"Track usage with: ...status"
            )

            logger.info(f"Threshold ${threshold} crossed. Sending notification.")

            if telegram_bot:
                chat_id = int(user_id) if user_id else config.TELEGRAM_CHAT_ID
                await telegram_bot.send_message(message, chat_id=chat_id)
            else:
                logger.warning("Telegram bot not available, skipping threshold notification")

            for t in range(int(previous_total) + 1, threshold + 1):
                if t not in state["notified_thresholds"]:
                    state["notified_thresholds"].append(t)

            save_threshold_state(state)
            logger.info(f"Updated threshold state: {state['notified_thresholds']}")

    except Exception as e:
        logger.error(f"Error checking billing threshold: {e}", exc_info=True)


def get_user_usage_stats(user_id: str, days: int) -> Dict:
    """
    Get usage statistics for a SPECIFIC user over last N days.

    Args:
        user_id: User ID to filter by
        days: Number of days to look back

    Returns:
        dict with aggregated usage statistics for that user
    """
    if not USAGE_FILE.exists():
        return {
            "user_id": user_id,
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

                if entry.get("user_id") != user_id:
                    continue

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
        "user_id": user_id,
        "total_cost": round(total_cost, 4),
        "total_tokens": total_input_tokens + total_output_tokens,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "request_count": request_count
    }


def get_all_users_usage_stats(days: int) -> List[Dict]:
    """
    Get usage statistics for ALL users (admin function).

    Args:
        days: Number of days to look back

    Returns:
        List of dicts with per-user stats, sorted by cost descending
    """
    if not USAGE_FILE.exists():
        return []

    from datetime import timezone
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    user_stats = defaultdict(lambda: {
        "total_cost": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "request_count": 0
    })

    with open(USAGE_FILE, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line)
                user_id = entry.get("user_id")

                if not user_id or user_id == "unknown":
                    continue

                entry_time = datetime.fromisoformat(
                    entry["timestamp"].replace('Z', '+00:00')
                )

                if entry_time < cutoff_date:
                    continue

                user_stats[user_id]["total_cost"] += entry["total_cost"]
                user_stats[user_id]["input_tokens"] += entry["input_tokens"]
                user_stats[user_id]["output_tokens"] += entry["output_tokens"]
                user_stats[user_id]["request_count"] += 1

            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    result = []
    for user_id, stats in user_stats.items():
        result.append({
            "user_id": user_id,
            "total_cost": round(stats["total_cost"], 4),
            "total_tokens": stats["input_tokens"] + stats["output_tokens"],
            "input_tokens": stats["input_tokens"],
            "output_tokens": stats["output_tokens"],
            "request_count": stats["request_count"]
        })

    result.sort(key=lambda x: x["total_cost"], reverse=True)
    return result


def get_user_calls_in_window(user_id: str, hours: int = 5) -> int:
    """
    Count CLI calls for a user in the last N hours.

    Args:
        user_id: User ID to filter by
        hours: Window size in hours (default 5 for Pro plan)

    Returns:
        Number of calls in the window
    """
    if not USAGE_FILE.exists():
        return 0

    from datetime import timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    count = 0

    with open(USAGE_FILE, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("user_id") != user_id:
                    continue
                entry_time = datetime.fromisoformat(entry["timestamp"].replace('Z', '+00:00'))
                if entry_time >= cutoff:
                    count += 1
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    return count


# Approximate message limits per 5-hour window by plan
PLAN_LIMITS = {
    "pro": 45,
    "max": 225,
}


def format_usage_report(user_id: str) -> str:
    """
    Format a usage report for a specific user.

    Args:
        user_id: User ID to generate report for

    Returns:
        Formatted string with usage statistics for that user
    """
    from main import DaemonVigil

    # Get user-specific storage and config
    user_storage = get_user_storage(user_id)
    user_config = user_storage.config.get_config()

    report = "Status Report\n\n"
    report += f"Model: {user_config.model}\n\n"

    # Heartbeat status (user-specific)
    app = DaemonVigil.get_instance()
    if app and app.scheduler:
        try:
            status = app.scheduler.get_user_status(user_id)
            report += "Heartbeat:\n"
            report += f"State: {'Enabled' if status.get('enabled', True) else 'Disabled'}\n"
            report += f"Interval: {user_config.heartbeat_interval_minutes} minutes\n"
            if status.get('next_run'):
                report += f"Next run: {status['next_run'].strftime('%H:%M:%S UTC')}\n"
            report += "\n"
        except (AttributeError, KeyError):
            report += "Heartbeat:\n"
            report += f"Interval: {user_config.heartbeat_interval_minutes} minutes\n\n"

    # User-specific context information
    messages = user_storage.messages.get_recent_messages()
    notes = user_storage.scratchpad.get_notes()

    report += "Context:\n"
    report += f"Messages in history: {len(messages)}\n"
    report += f"Scratchpad notes: {len(notes)}\n"

    if notes:
        last_note = notes[-1]
        note_preview = last_note['note']
        if len(note_preview) > 80:
            note_preview = note_preview[:77] + "..."
        report += f"Last note: {note_preview}\n"

    # Subscription usage (calls in 5-hour window)
    calls_5h = get_user_calls_in_window(user_id, hours=5)
    plan_limit = PLAN_LIMITS.get("pro", 45)
    usage_pct = min(100.0, (calls_5h / plan_limit) * 100)

    report += f"\nSubscription Usage (5h window):\n"
    report += f"Messages: {calls_5h}/{plan_limit} ({usage_pct:.0f}%)\n"

    # Simple visual bar
    filled = round(usage_pct / 5)
    bar = "█" * filled + "░" * (20 - filled)
    report += f"[{bar}]\n"

    # Also show today's total
    today_stats = get_user_usage_stats(user_id, 1)
    if today_stats["request_count"] > 0:
        report += f"\nToday: {today_stats['request_count']} requests, "
        report += f"{today_stats['total_tokens']:,} tokens"

    return report
