# Scheduler Enhancement Design

## Current Issues

1. **Heartbeat not firing**: No heartbeat logs in production
2. **Potential bug**: Scheduler may not be awaiting async job correctly
3. **No control**: Can't pause/resume heartbeats
4. **No time windows**: Always active, no quiet hours

## Proposed Architecture

### 1. Active/Inactive Time Windows

**Configuration** (`config.yaml`):
```yaml
heartbeat_interval_minutes: 15
active_hours:
  # UTC hours when heartbeat is active
  # Format: list of hour ranges or "all"
  enabled: true
  windows:
    - start: "08:00"  # 8 AM UTC
      end: "23:00"    # 11 PM UTC
  # Or: windows: "all" for 24/7
```

**Behavior**:
- Check current time before each heartbeat
- If outside active window, skip heartbeat
- Log when skipping due to time window

### 2. Manual Control Commands

**...heartbeat test** (renamed from ...heartbeat):
- Trigger immediate debug heartbeat
- Shows reasoning, doesn't send message
- Works regardless of active/inactive state

**...heartbeat on**:
- Enable automatic heartbeats
- Persisted to config
- Shows confirmation

**...heartbeat off**:
- Disable automatic heartbeats
- Persisted to config
- Shows confirmation
- Manual test still works

**...heartbeat status**:
- Shows: enabled/disabled
- Shows: next scheduled time
- Shows: active hours config

### 3. Custom Future Heartbeat (for Claude)

**New tool for Claude**: `schedule_heartbeat`
```python
{
    "name": "schedule_heartbeat",
    "description": "Schedule a custom heartbeat at a specific time in the future. Use this to remind yourself to check in with Vals at an appropriate time.",
    "input_schema": {
        "properties": {
            "minutes_from_now": {
                "type": "integer",
                "description": "Minutes from now to trigger heartbeat (e.g., 30, 120)"
            },
            "reason": {
                "type": "string",
                "description": "Why you're scheduling this (for logging)"
            }
        }
    }
}
```

**Example Claude usage**:
```
User: "I'm going for a run, back in an hour"
Claude reasoning: "Good time to schedule a check-in for after the run"
Claude calls: schedule_heartbeat(minutes_from_now=75, reason="Check in after run")
```

### 4. Scheduler State Management

**State file** (`data/scheduler_state.json`):
```json
{
  "enabled": true,
  "custom_heartbeats": [
    {
      "scheduled_for": "2025-12-04T15:30:00Z",
      "reason": "Check in after run",
      "job_id": "custom_hb_12345"
    }
  ]
}
```

## Implementation Plan

### Phase 1: Fix Current Bug
1. Audit scheduler.start() - ensure async job works
2. Add logging to heartbeat_job
3. Test that basic interval works

### Phase 2: Add Control Commands
1. Add enabled flag to config
2. Implement ...heartbeat on/off/test/status
3. Persist enabled state

### Phase 3: Active Hours
1. Add active_hours to config.yaml
2. Check time window before heartbeat
3. Skip if outside window

### Phase 4: Custom Heartbeats
1. Add schedule_heartbeat tool for Claude
2. Implement one-time job scheduling
3. Track custom heartbeats in state file
4. Allow Claude to see upcoming scheduled heartbeats

## Technical Details

### APScheduler Job Types

**Current** (interval):
```python
scheduler.add_job(heartbeat_job, 'interval', minutes=15)
```

**One-time** (for custom):
```python
scheduler.add_job(heartbeat_job, 'date', run_date=datetime.utcnow() + timedelta(minutes=60))
```

### Time Window Check

```python
def is_in_active_window() -> bool:
    now = datetime.utcnow()
    current_time = now.strftime("%H:%M")

    if not config.active_hours["enabled"]:
        return True

    if config.active_hours["windows"] == "all":
        return True

    for window in config.active_hours["windows"]:
        if window["start"] <= current_time <= window["end"]:
            return True
    return False
```

## Migration Path

1. Keep existing behavior as default (24/7, enabled)
2. Add new features incrementally
3. Backward compatible config (old config.yaml still works)
