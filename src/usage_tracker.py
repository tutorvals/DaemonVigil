"""API usage tracking and cost calculation."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, Optional

from . import config

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


def format_usage_report() -> str:
    """
    Format a usage report for display.

    Returns:
        Formatted string with usage statistics
    """
    today_stats = get_usage_stats(1)
    week_stats = get_usage_stats(7)
    month_stats = get_usage_stats(30)

    report = "📊 Status Report\n\n"
    report += f"Model: {config.get_claude_model()}\n\n"
    report += "💰 API Costs:\n"

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
