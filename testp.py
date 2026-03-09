import asyncio
import json
import os



async def test_claude_cli():
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE", None)

    cmd = [
        "claude", "-p", "just respond test123",
        "--no-session-persistence",
        "--output-format", "json",
 #       "--system-prompt", "You are a test assistant. Respond briefly.",
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

    print(f"returncode: {proc.returncode}")
    print(f"stderr: {stderr.decode()}")
    print(f"stdout: {stdout.decode()[:500]}")

    if proc.returncode == 0:
        response = json.loads(stdout.decode())
        print(f"result: {response.get('result', '')}")
    else:
        print("FAILED")


asyncio.run(test_claude_cli())
