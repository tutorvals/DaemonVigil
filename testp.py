import asyncio
from claude_agent_sdk import ClaudeAgentOptions, query


async def test_claude_sdk():
    options = ClaudeAgentOptions(max_turns=1)

    async for message in query(prompt="just respond test123", options=options):
        print(message)


asyncio.run(test_claude_sdk())
