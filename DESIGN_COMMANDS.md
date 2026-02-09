# Command System Design

## Overview
Messages starting with "..." are interpreted as commands and NOT forwarded to Claude LLM.

## Architecture
### Message Flow
```
User sends message
    ↓
Is it a command? (starts with "...")
    ↓ YES                           ↓ NO
Parse command                   Forward to Claude
    ↓
Execute & respond              (normal flow)
    ↓
Skip Claude
```

### Command Format
- Prefix: `...` (three dots)
- Command: alphanumeric word after prefix
- Examples: `...status`, `...help`, `...clear`

### Implementation Location
- **telegram_bot.py**: Intercept commands in `handle_message()`
- **commands.py**: New module with command handlers
- **usage_tracker.py**: New module for cost tracking

## Command: ...status
### What It Returns
1. Current model being used
2. API costs for:
   - Today
   - This week (last 7 days)
   - This month (last 30 days)

### Data Source
- Track token usage from every API response
- Log to `data/api_usage.jsonl` (append-only log)
- Calculate costs using pricing table

### Cost Tracking Strategy
**Real-time tracking** (not Admin API):
- API responses include `usage.input_tokens` and `usage.output_tokens`
- Apply pricing: Sonnet 4 = $3/M input, $15/M output
- Log each call with timestamp, tokens, cost, request type
- Aggregate on demand for reporting

### Example Response
```
📊 Status Report

Model: claude-sonnet-4-20250514

💰 API Costs:
Today:      $0.45 (150 requests)
This Week:  $2.13 (780 requests)
This Month: $8.67 (2,940 requests)

📈 Usage:
Total tokens today: 145K (120K in, 25K out)
```

### Edge Cases
- No usage data yet → "No API usage recorded yet"
- Invalid command → Silent ignore (no response)
- Command during active conversation → Still skip Claude

