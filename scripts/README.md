# Migration Scripts

This directory contains scripts for migrating and managing DaemonVigil data.

## migrate_to_multi_user.py

Migrates existing single-user data to the new multi-user format.

### Prerequisites

1. Stop Daemon Vigil if it's running
2. Ensure `TELEGRAM_CHAT_ID` is set in your `.env` file

### Usage

```bash
# From the DaemonVigil root directory
python scripts/migrate_to_multi_user.py
```

### What it does

1. **Creates user directory structure:**
   - `data/users/<your_chat_id>/`

2. **Migrates existing data:**
   - Moves `messages.json` → `data/users/<your_chat_id>/messages.json`
   - Moves `scratchpad.json` → `data/users/<your_chat_id>/scratchpad.json`
   - Creates `data/users/<your_chat_id>/user_config.json` with your settings

3. **Creates user registry:**
   - Creates `data/users.json` with your user entry

4. **Updates API usage logs:**
   - Adds `user_id` field to all entries in `api_usage.jsonl`

5. **Creates backups:**
   - `messages.json.backup`
   - `scratchpad.json.backup`
   - `api_usage.jsonl.backup`

### After Migration

1. **Verify migration:**
   ```bash
   ls -la data/users/<your_chat_id>/
   # Should see: messages.json, scratchpad.json, user_config.json
   ```

2. **Start Daemon Vigil:**
   ```bash
   python main.py
   ```

3. **Test functionality:**
   - Send a message to your bot
   - Try `...status` command
   - Verify heartbeats still work

4. **Clean up backups (optional):**
   ```bash
   # Only after confirming everything works!
   rm data/*.backup
   ```

### Finding Your Telegram Chat ID

If you don't know your chat ID:

1. Start the old version of Daemon Vigil (before migration)
2. Send a message to your bot
3. Check `daemon_vigil.log` for a line like:
   ```
   Received /start from chat_id: 123456789
   ```
4. Add this to your `.env`:
   ```
   TELEGRAM_CHAT_ID=123456789
   ```

### Troubleshooting

**Error: "TELEGRAM_CHAT_ID not set"**
- Solution: Add `TELEGRAM_CHAT_ID=<your_id>` to your `.env` file

**Error: "Permission denied"**
- Solution: `chmod +x scripts/migrate_to_multi_user.py`

**Migration completed but bot doesn't work:**
- Check logs: `tail -f daemon_vigil.log`
- Verify files were created: `ls -la data/users/<your_chat_id>/`
- Ensure you restarted the bot after migration

### Rollback

If something goes wrong, you can rollback:

1. Stop Daemon Vigil
2. Restore from backups:
   ```bash
   mv data/messages.json.backup data/messages.json
   mv data/scratchpad.json.backup data/scratchpad.json
   mv data/api_usage.jsonl.backup data/api_usage.jsonl
   ```
3. Remove multi-user directories:
   ```bash
   rm -rf data/users
   rm data/users.json
   ```
4. Checkout the previous version of the code (before multi-user changes)
