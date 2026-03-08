import asyncio
from a3s_code import Agent


async def main() -> None:
    print("BOOT")
    agent = Agent.create("test/all_config.hcl")
    session = agent.session(
        "/home/kai/Projects/研二下/Runtime Monitor Lite",
        builtin_skills=False,
        permissive=True,
    )
    seen = []
    async for event in session.stream("Reply with exactly: OK"):
        event_type = str(event.event_type)
        seen.append(event_type)
        if event_type == "end":
            break

    print("EVENT_COUNT", len(seen))
    print("EVENT_TYPES", ",".join(seen))


if __name__ == "__main__":
    asyncio.run(main())
