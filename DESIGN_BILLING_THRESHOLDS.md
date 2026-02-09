# Billing Threshold Notifications - Architecture Design

## Current Implementation Analysis

### Components
1. **usage_tracker.py** - Tracks API usage and costs
   - `calculate_cost()`: Calculates cost per API call
   - `log_api_usage()`: Logs to `data/api_usage.jsonl`
   - `get_usage_stats(days)`: Aggregates usage for time period

2. **claude.py** - Makes API calls
   - Calls `calculate_cost()` after each API response
   - Logs usage immediately with `log_api_usage()`
   - Two entry points: `process_heartbeat()` and `respond_to_user()`

3. **telegram_bot.py** - Sends messages
   - `send_message(text, chat_id)`: Sends notification to user

### Current Flow
```
API Call → Calculate Cost → Log to JSONL → Continue
```

## Proposed Feature: Dollar Threshold Notifications

### Requirements
- Send a Telegram message when daily spending crosses each whole dollar threshold ($1, $2, $3, etc.)
- Only notify once per threshold per day
- Reset tracking at midnight UTC
- Non-intrusive: Don't interrupt normal bot operations

### Architecture Design

#### 1. Threshold State Management

**New File: `data/billing_thresholds.json`**
```json
{
  "last_reset_date": "2025-12-08",
  "notified_thresholds": [1, 2, 3]
}
```

This tracks:
- Which dollar thresholds have been notified today
- When the last reset occurred (for detecting new days)

#### 2. Core Logic Flow

```
API Call
  ↓
Calculate Cost
  ↓
Log to JSONL
  ↓
Check if new threshold crossed ← NEW
  ↓
Send notification if needed ← NEW
  ↓
Update threshold state ← NEW
  ↓
Continue
```

#### 3. Implementation Components

**A. New Functions in `usage_tracker.py`**

```python
def get_daily_total() -> float:
    """
    Get total spending for today (UTC).
    Returns the sum of all costs from midnight UTC to now.
    """
    # Reuse existing get_usage_stats(1) but return just total_cost

def load_threshold_state() -> dict:
    """
    Load threshold state from data/billing_thresholds.json.
    Reset if it's a new day.
    """

def save_threshold_state(state: dict) -> None:
    """Save threshold state to disk."""

def check_threshold_crossed(previous_total: float, new_total: float,
                           notified_thresholds: list) -> Optional[int]:
    """
    Check if a new dollar threshold was crossed.

    Args:
        previous_total: Total before this API call
        new_total: Total after this API call
        notified_thresholds: List of thresholds already notified

    Returns:
        The threshold number that was crossed (e.g., 3 for $3), or None
    """
    # Example: If previous was $2.70 and new is $3.10, return 3
    # If 3 is already in notified_thresholds, return None

async def check_and_notify_threshold(telegram_bot, chat_id: int = None) -> None:
    """
    Check if a threshold was crossed and send notification if needed.

    This should be called after each API call is logged.
    """
    # 1. Load threshold state (resets if new day)
    # 2. Get current daily total
    # 3. Calculate previous total (current - last_api_cost)
    # 4. Check if threshold crossed
    # 5. If yes, send notification and update state
```

**B. Integration Points**

Modify `claude.py` to call threshold check after logging:

```python
# In process_heartbeat() - around line 152
usage_tracker.log_api_usage(usage_data)

# NEW: Check threshold
await usage_tracker.check_and_notify_threshold(telegram_bot)

# In respond_to_user() - similar change around line 253
```

**C. Notification Message Format**

```
💰 Daily Billing Alert

You've crossed the $X threshold today.

Today's total: $X.XX (Y requests)

Track usage with: ...status
```

#### 4. Edge Cases & Considerations

**Multiple Thresholds in One Call**
- If a single expensive API call crosses multiple thresholds (e.g., $2.50 → $5.20)
- Solution: Notify for the highest threshold only, mark all crossed ones as notified

**Midnight Reset**
- Use UTC timezone for consistency
- Reset happens automatically when `load_threshold_state()` detects date change
- Old state is discarded, new empty state created

**Telegram Bot Not Available**
- If bot is None or offline, log warning but don't crash
- Threshold state still updates (prevents duplicate notifications later)

**First API Call of the Day**
- If first call is $1.50, should notify for $1 threshold
- Solution: Compare against $0.00 as previous total

**Notification Spam Prevention**
- Already built-in: Only notify once per threshold per day
- State persists across bot restarts

#### 5. Testing Strategy

**Manual Testing Checklist**
1. Start fresh day, make API call that costs $0.50 - no notification
2. Make call that brings total to $1.20 - expect $1 notification
3. Make another call to $1.80 - no notification (already notified $1)
4. Make call to $2.10 - expect $2 notification
5. Restart bot, make call to $2.50 - no duplicate notifications
6. Test with expensive call that crosses multiple thresholds

**Data Validation**
- Check `data/billing_thresholds.json` state after each operation
- Verify `api_usage.jsonl` entries match expected costs
- Cross-check manual calculation of daily total

#### 6. Configuration Options (Future Enhancement)

Could add to `config.yaml`:
```yaml
billing:
  threshold_notifications: true
  threshold_interval: 1  # dollars (could make 5, 10, etc.)
  notification_time_quiet_hours: false  # suppress during certain hours
```

For initial implementation, keep it simple:
- Always enabled
- $1 intervals
- No quiet hours

#### 7. Performance Impact

**Minimal**
- Threshold check adds ~2-3 file operations per API call
- Computation is trivial (comparing floats, checking list membership)
- No external API calls
- Async, doesn't block main flow

**File I/O**
- Read: `data/billing_thresholds.json` (~100 bytes)
- Write: Only when threshold crossed or new day
- Read: `data/api_usage.jsonl` (already done by `get_usage_stats`)

Total overhead: <10ms per API call

#### 8. Implementation Order

1. **Phase 1**: Core functions (no Telegram integration)
   - `load_threshold_state()`
   - `save_threshold_state()`
   - `check_threshold_crossed()`
   - `get_daily_total()`

2. **Phase 2**: Integration
   - `check_and_notify_threshold()`
   - Integrate into `claude.py`

3. **Phase 3**: Testing
   - Manual testing with real API calls
   - Edge case validation

## Summary

This design adds billing threshold notifications as a lightweight, non-intrusive feature that:
- ✅ Notifies once per threshold per day
- ✅ Resets automatically at midnight UTC
- ✅ Handles edge cases gracefully
- ✅ Minimal performance impact
- ✅ Easy to disable or modify
- ✅ Follows existing code patterns

The implementation integrates cleanly into the existing architecture without requiring major refactoring.
