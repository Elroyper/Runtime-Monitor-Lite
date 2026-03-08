import asyncio
import json
import time
from datetime import datetime
from a3s_code import Agent

agent = Agent.create("test/all_config.hcl")
session = agent.session(r"D:\project\safety\SafeClaw", builtin_skills=True, permissive=True)


async def main():
    turns = []            # 按 turn 聚合的结果
    current_turn = {"turn": 1, "text": "", "tools": []}
    current_tool = None

    async for event in session.stream("使用explain-code skills分析下本项目如何工作的"):
        t = event.event_type

        # 实时打印
        if t == "text_delta":
            print(event.text, end="", flush=True)
            current_turn["text"] += event.text
        elif t == "tool_start":
            print(f"\n🔧 {event.tool_name} (id={event.tool_id})...", end="", flush=True)
            current_tool = {"tool_name": event.tool_name, "tool_id": event.tool_id}
        elif t == "tool_end":
            print(f" ✓ (exit={event.exit_code})")
            if current_tool:
                current_tool["exit_code"] = event.exit_code
                current_tool["tool_output"] = event.tool_output
                current_turn["tools"].append(current_tool)
                current_tool = None
        elif t == "turn_end":
            current_turn["total_tokens"] = getattr(event, "total_tokens", None)
            print(f"\n└─ Turn {event.turn} done ({current_turn['total_tokens']} tokens)")
            turns.append(current_turn)
            current_turn = {"turn": event.turn + 1, "text": "", "tools": []}
        elif t == "end":
            print(f"\n■ Done — {event.total_tokens} tokens total")
            break
        else:
            print(f"\n[{t}]")

    # 聚合结果
    output = {
        "summary": {
            "total_turns": len(turns),
        },
        "turns": turns,
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"test/events_{timestamp}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n共 {len(turns)} 个 turn，已保存到 {output_path}")

asyncio.run(main())
