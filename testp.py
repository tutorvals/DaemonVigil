import asyncio
import json
import os
import time
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query


CLAUDE_CLI_PATH = Path.home() / ".local" / "bin" / "claude"
MODEL = "claude-opus-4-5-20251101"
PROMPT = "Reply with exactly: SDK_DIRECT_TEST_OK"
SYSTEM_PROMPT = "You are a helpful assistant. Respond briefly."


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    env.pop("CLAUDE_CODE", None)
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    env.pop("CLAUDE_TTY", None)
    return env


def summarize_env(env: dict[str, str]) -> dict:
    summary = {
        "HOME": env.get("HOME"),
        "PATH": env.get("PATH"),
        "PWD": env.get("PWD"),
        "SHELL": env.get("SHELL"),
        "CLAUDE_CONFIG_DIR": env.get("CLAUDE_CONFIG_DIR"),
    }
    for key in sorted(env):
        if key.startswith(("CLAUDE", "ANTHROPIC")):
            summary[f"{key}_present"] = bool(env.get(key))
    return summary


def summarize_sdk_message(message) -> dict:
    summary = {
        "class": message.__class__.__name__,
        "type": getattr(message, "type", None),
    }
    for attr in ("subtype", "session_id", "is_error", "result"):
        if hasattr(message, attr):
            value = getattr(message, attr)
            summary[attr] = value[:500] if isinstance(value, str) else value

    content = getattr(message, "content", None)
    if content:
        text_parts = []
        for block in content:
            text = getattr(block, "text", None)
            if text:
                text_parts.append(text)
        if text_parts:
            summary["text_preview"] = "\n".join(text_parts)[:500]

    return summary


def sdk_stderr_logger(line: str) -> None:
    text = line.rstrip()
    if text:
        print(f"[sdk stderr] {text}")


async def run_direct_cli(label: str, prompt: str, system_prompt: str | None) -> None:
    env = build_env()
    cmd = [
        str(CLAUDE_CLI_PATH),
        "-p",
        prompt,
        "--output-format",
        "json",
        "--no-session-persistence",
    ]
    if system_prompt is not None:
        cmd.extend(["--system-prompt", system_prompt])

    print(f"\n=== direct cli: {label} ===")
    print({"cmd": cmd, "env": summarize_env(env)})

    start = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()
    elapsed = time.monotonic() - start

    stdout_text = stdout.decode(errors="replace")
    stderr_text = stderr.decode(errors="replace")

    print({"elapsed": round(elapsed, 2), "returncode": proc.returncode})
    print("stdout:", stdout_text[:2000])
    print("stderr:", stderr_text[:2000])

    if stdout_text.strip():
        try:
            print("parsed_stdout:", json.loads(stdout_text))
        except Exception as exc:
            print(f"stdout json parse failed: {exc}")


async def run_agent_sdk(label: str, prompt: str, system_prompt: str | None, full: bool) -> None:
    env = build_env()
    options_kwargs = {
        "model": MODEL,
        "cwd": str(Path.cwd()),
        "cli_path": str(CLAUDE_CLI_PATH),
        "env": env,
        "stderr": sdk_stderr_logger,
    }
    if full:
        options_kwargs.update(
            {
                "system_prompt": system_prompt,
                "permission_mode": "bypassPermissions",
                "max_turns": 1,
                "extra_args": {"no-session-persistence": None},
            }
        )
    elif system_prompt is not None:
        options_kwargs["system_prompt"] = system_prompt

    options = ClaudeAgentOptions(**options_kwargs)

    print(f"\n=== agent sdk: {label} ===")
    print(
        {
            "options": {
                "model": MODEL,
                "cwd": str(Path.cwd()),
                "cli_path": str(CLAUDE_CLI_PATH),
                "system_prompt": bool(system_prompt),
                "permission_mode": options_kwargs.get("permission_mode"),
                "max_turns": options_kwargs.get("max_turns"),
                "extra_args": options_kwargs.get("extra_args"),
            },
            "env": summarize_env(env),
        }
    )

    start = time.monotonic()
    try:
        async for message in query(prompt=prompt, options=options):
            print("message:", summarize_sdk_message(message))
    except Exception as exc:
        elapsed = time.monotonic() - start
        print({"elapsed": round(elapsed, 2), "exception": repr(exc)})
        return

    elapsed = time.monotonic() - start
    print({"elapsed": round(elapsed, 2), "status": "completed"})


async def main() -> None:
    print("Claude path:", CLAUDE_CLI_PATH)
    print("cwd:", Path.cwd())

    await run_direct_cli("minimal", PROMPT, None)
    await run_agent_sdk("minimal", PROMPT, None, full=False)
    await run_direct_cli("full", PROMPT, SYSTEM_PROMPT)
    await run_agent_sdk("full", PROMPT, SYSTEM_PROMPT, full=True)


if __name__ == "__main__":
    asyncio.run(main())
