import asyncio
import os
from a3s_code import Agent

agent = Agent.create("test/all_config.hcl")

session1 = agent.session("D:\project\safety\SafeClaw", builtin_skills=True, permissive=True, skill_dirs=["D:\project\safety\A3SCode\test\.a3s\skills"])
# # Non-streaming
# print('*****' * 10)
# print("# Non-streaming")
# result = session.send("What does this project do?")
# print(result.text)

# Streaming
async def main():
    print('*****' * 10)
    print("# Streaming")
    async for event in session1.stream("使用api-docs skills生成本项目的文档文件"):  # 使用explain-code skills分析下本项目如何工作的
        t = event.event_type
        if t == "text_delta":
            print(event.text, end="", flush=True)
        elif t == "tool_start":
            print(f"\n🔧 {event.tool_name}...", end="")
        elif t == "tool_end":
            print(f" ✓ (exit={event.exit_code})")
        elif t == "turn_end":
            print(f"\n└─ Turn {event.turn} done ({event.total_tokens} tokens)")
        elif t == "end":
            print(f"\n■ Done — {event.total_tokens} tokens total")
            break

asyncio.run(main())