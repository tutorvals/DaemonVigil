#!/usr/bin/env python3
"""Forced command for the laptop's bridge key (authorized_keys: command="...bridge-ssh.py",restrict).

Only two verbs, taken from SSH_ORIGINAL_COMMAND:
  fetch  print the vigil session's outgoing messages as a JSON array, then move them to spool/sent/
  put    read one JSON object {"text": ...} from stdin into spool/inbox/ for the vigil session
Anything else exits 2. Standard library only.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SPOOL = Path(os.environ.get("BRIDGE_SPOOL", Path.home() / "vigil" / "spool"))
MAX_IN_BYTES = 16_000
MAX_CHARS = 8000


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%fZ")


def fetch() -> int:
    outbox, sent = SPOOL / "outbox", SPOOL / "sent"
    sent.mkdir(parents=True, exist_ok=True)
    msgs, paths = [], sorted(outbox.glob("*.json"))[:50] if outbox.exists() else []
    for p in paths:
        try:
            msg = json.loads(p.read_text())
            msgs.append({"at": str(msg.get("at", "")), "text": str(msg.get("text", ""))[:MAX_CHARS]})
        except (ValueError, OSError):
            pass
    print(json.dumps(msgs))
    sys.stdout.flush()
    for p in paths:
        p.rename(sent / p.name)
    return 0


def put() -> int:
    raw = sys.stdin.buffer.read(MAX_IN_BYTES + 1)
    if len(raw) > MAX_IN_BYTES:
        print("too large", file=sys.stderr)
        return 1
    try:
        text = json.loads(raw)["text"]
    except (ValueError, KeyError, TypeError):
        print("bad json", file=sys.stderr)
        return 1
    if not isinstance(text, str) or not text.strip():
        print("empty", file=sys.stderr)
        return 1
    inbox = SPOOL / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    name = f"{stamp()}-coordinator.json"
    tmp = inbox / f".{name}"
    tmp.write_text(json.dumps({"from": "coordinator", "at": stamp(), "text": text[:MAX_CHARS]}))
    tmp.rename(inbox / name)
    print("ok")
    return 0


if __name__ == "__main__":
    verb = os.environ.get("SSH_ORIGINAL_COMMAND", "").strip()
    sys.exit({"fetch": fetch, "put": put}.get(verb, lambda: 2)())
