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
    # Validate user_id presence
    if "user_id" not in usage_data:
        logger.warning("⚠️  Usage data missing user_id - cannot track per-user costs")
        usage_data["user_id"] = "unknown"

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

                # Filter by user_id
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

    # Aggregate stats by user_id
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

    # Convert to list and sort by cost
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

    # Get user-specific usage stats
    today_stats = get_user_usage_stats(user_id, 1)
    week_stats = get_user_usage_stats(user_id, 7)
    month_stats = get_user_usage_stats(user_id, 30)

    report = "📊 Status Report\n\n"
    report += f"Model: {user_config.model}\n\n"

    # Heartbeat status (user-specific)
    app = DaemonVigil.get_instance()
    if app and app.scheduler:
        # Try to get user-specific status (will work after Phase 3)
        try:
            status = app.scheduler.get_user_status(user_id)
            report += "💓 Heartbeat:\n"
            report += f"State: {'✅ Enabled' if status.get('enabled', True) else '🔇 Disabled'}\n"
            report += f"Interval: {user_config.heartbeat_interval_minutes} minutes\n"
            if status.get('next_run'):
                report += f"Next run: {status['next_run'].strftime('%H:%M:%S UTC')}\n"
            report += "\n"
        except (AttributeError, KeyError):
            # Fallback for old scheduler (before Phase 3)
            report += "💓 Heartbeat:\n"
            report += f"Interval: {user_config.heartbeat_interval_minutes} minutes\n"
            report += "(Multi-user scheduler not yet active)\n\n"

    # User-specific context information
    messages = user_storage.messages.get_recent_messages()
    notes = user_storage.scratchpad.get_notes()

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

    report += "\n💰 API Costs (Your Usage Only):\n"

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
