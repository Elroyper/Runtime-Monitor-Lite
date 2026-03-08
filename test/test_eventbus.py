"""
a3s-code v1.1.0 EventBus 完整探索脚本

覆盖三大新机制：
  1. Hook System — 生命周期事件拦截 (register_hook / unregister_hook)
  2. Lane Queue System — 优先级调度 + 外部任务 (submit / set_lane_handler)
  3. Orchestrator System — 主-子 Agent 协调 (spawn_subagent / SubAgentHandle)

测试结果用于后续开发实时安全监督插件。
"""

import a3s_code
import asyncio
import json
from datetime import datetime


# ============================================================
# Part 1: Hook System
# ============================================================

# 11 个支持的 hook 事件类型:
VALID_HOOK_EVENTS = [
    "pre_tool_use",     # 工具执行前 (可拦截/阻止)
    "post_tool_use",    # 工具执行后 (可审计结果)
    "generate_start",   # LLM 生成开始
    "generate_end",     # LLM 生成结束
    "session_start",    # 会话开始
    "session_end",      # 会话结束
    "skill_load",       # 技能加载
    "skill_unload",     # 技能卸载
    "pre_prompt",       # prompt 发送前 (可修改/过滤)
    "post_response",    # LLM 响应后 (可审计/过滤)
    "on_error",         # 错误发生时
]

# Hook matcher 支持的字段:
# - tool: 匹配工具名 (e.g. "bash", "read", "write", "glob", "grep")
# - path_pattern: 文件路径 glob 模式 (e.g. "*.py", "src/**/*.rs")
# - command_pattern: 命令模式匹配 (e.g. "rm *", "chmod *")
# - session_id: 匹配特定会话
# - skill: 匹配技能名 (e.g. "api-docs")

# Hook config 支持的字段:
# - priority: int, 越小越高优先级 (0=最高)
# - timeout_ms: int, 超时毫秒数
# - async_execution: bool, 是否异步执行
# - max_retries: int, 最大重试次数


def test_hook_registration():
    """测试 hook 注册/注销系统。"""
    print("=" * 60)
    print("Part 1: Hook System")
    print("=" * 60)

    agent = a3s_code.Agent.create("test/all_config.hcl")
    opts = a3s_code.SessionOptions()
    opts.use_memory_session_store = True
    opts.builtin_skills = True

    session = agent.session("/tmp/eventbus_test", opts)
    print(f"Session: {session.session_id}")
    print(f"Initial hook_count: {session.hook_count()}\n")

    # 注册所有 11 个有效事件类型
    print("--- 注册所有有效事件类型 ---")
    for evt in VALID_HOOK_EVENTS:
        session.register_hook(f"test_{evt}", evt, config={"priority": 5})
        print(f"  ✅ {evt} (count={session.hook_count()})")

    print(f"\n总计: {session.hook_count()} hooks")

    # 测试 matcher 组合
    print("\n--- 测试 Matcher 组合 ---")
    matcher_tests = [
        ("单一 tool", {"tool": "bash"}),
        ("path_pattern", {"path_pattern": "*.py"}),
        ("command_pattern", {"command_pattern": "rm -rf *"}),
        ("session_id", {"session_id": session.session_id}),
        ("skill", {"skill": "api-docs"}),
        ("组合: tool+command", {"tool": "bash", "command_pattern": "curl *"}),
        ("组合: tool+path", {"tool": "write", "path_pattern": "/etc/*"}),
    ]
    for name, matcher in matcher_tests:
        try:
            session.register_hook(f"matcher_{name}", "pre_tool_use", matcher=matcher)
            print(f"  ✅ {name}: {matcher}")
            session.unregister_hook(f"matcher_{name}")
        except Exception as e:
            print(f"  ❌ {name}: {e}")

    # 测试 config 选项
    print("\n--- 测试 Config 选项 ---")
    session.register_hook("full_config", "pre_tool_use", config={
        "priority": 0,
        "timeout_ms": 5000,
        "async_execution": True,
        "max_retries": 3,
    })
    print(f"  ✅ 全配置 hook (count={session.hook_count()})")

    # 注销
    ok = session.unregister_hook("full_config")
    print(f"  注销 full_config: {ok}")
    not_ok = session.unregister_hook("nonexistent")
    print(f"  注销 nonexistent: {not_ok}")

    # 清理
    for evt in VALID_HOOK_EVENTS:
        session.unregister_hook(f"test_{evt}")
    print(f"\n清理后 hook_count: {session.hook_count()}")

    return session


# ============================================================
# Part 2: Lane Handler & Queue System
# ============================================================

def test_lane_and_queue():
    """测试 Lane Handler 和 Queue 系统。"""
    print("\n" + "=" * 60)
    print("Part 2: Lane Handler & Queue System")
    print("=" * 60)

    agent = a3s_code.Agent.create("test/all_config.hcl")
    opts = a3s_code.SessionOptions()
    opts.use_memory_session_store = True

    # 配置 Queue
    qc = a3s_code.SessionQueueConfig()
    qc.set_query_concurrency(8)
    qc.set_execute_concurrency(2)
    qc.set_generate_concurrency(1)
    qc.set_timeout(30000)
    qc.enable_dlq(max_size=100)
    qc.enable_metrics()
    qc.enable_alerts()
    print(f"Queue config: {repr(qc)}")
    opts.queue_config = qc

    session = agent.session("/tmp/eventbus_queue_test", opts)
    print(f"has_queue: {session.has_queue()}\n")

    # Lane handler 模式
    print("--- Lane Handler 模式 ---")
    for lane in ["control", "query", "execute", "generate"]:
        for mode in ["internal", "external", "hybrid"]:
            session.set_lane_handler(lane, mode=mode, timeout_ms=30000)
            print(f"  {lane:10s} -> {mode:10s} ✅")

    # 重置
    for lane in ["control", "query", "execute", "generate"]:
        session.set_lane_handler(lane, mode="internal")

    # Queue stats
    print("\n--- Queue Stats ---")
    stats = session.queue_stats()
    print(f"  {json.dumps(stats, indent=4)}")

    metrics = session.queue_metrics()
    print(f"\n--- Queue Metrics ---\n  {metrics}")

    dl = session.dead_letters()
    print(f"\n--- Dead Letters ---\n  {dl}")

    # Submit
    print("\n--- Submit ---")
    try:
        result = session.submit("query", lambda: {
            "check": "file_permissions",
            "timestamp": datetime.now().isoformat(),
            "status": "ok"
        })
        print(f"  Submit result: {result}")
    except Exception as e:
        print(f"  Submit error: {e}")

    try:
        results = session.submit_batch("query", [
            lambda: {"scan": "path_traversal", "risk": 0.1},
            lambda: {"scan": "injection", "risk": 0.0},
            lambda: {"scan": "privilege_escalation", "risk": 0.3},
        ])
        print(f"  Batch results: {results}")
    except Exception as e:
        print(f"  Batch error: {e}")

    return session


# ============================================================
# Part 3: Orchestrator / SubAgent System (v1.1.0 NEW)
# ============================================================

def test_orchestrator():
    """测试 Orchestrator 多 Agent 协调系统。"""
    print("\n" + "=" * 60)
    print("Part 3: Orchestrator / SubAgent System (NEW in v1.1.0)")
    print("=" * 60)

    orch = a3s_code.Orchestrator.create()
    print(f"Orchestrator: {repr(orch)}")
    print(f"Initial active: {orch.active_count()}\n")

    security_agents = {
        "threat_detector": a3s_code.SubAgentConfig(
            agent_type="threat_detector",
            prompt="Detect security threats in tool calls",
            description="威胁检测子 Agent",
            permissive=False,
            max_steps=10,
            timeout_ms=30000,
        ),
        "audit_logger": a3s_code.SubAgentConfig(
            agent_type="audit_logger",
            prompt="Log all activities with timestamps and risk scores",
            description="审计日志子 Agent",
            permissive=True,
            max_steps=50,
            timeout_ms=60000,
        ),
        "policy_enforcer": a3s_code.SubAgentConfig(
            agent_type="policy_enforcer",
            prompt="Enforce: block dangerous commands, restrict network",
            description="策略执行子 Agent",
            permissive=False,
            max_steps=5,
            timeout_ms=10000,
        ),
    }

    handles = {}
    for name, cfg in security_agents.items():
        handle = orch.spawn_subagent(cfg)
        handles[name] = handle
        print(f"  Spawned '{name}': id={handle.id}")

    print(f"\nActive count: {orch.active_count()}")

    print("\n--- SubAgent Details ---")
    for info in orch.list_subagents():
        print(f"  [{info.id}] type={info.agent_type} state={info.state}")
        print(f"    desc: {info.description}")
        if info.current_activity:
            act = info.current_activity
            print(f"    activity: {act.activity_type} data={act.data}")

    # 控制操作
    if handles:
        h = handles["threat_detector"]
        print(f"\n--- Control (threat_detector, id={h.id}) ---")
        print(f"  state: {h.state()}")
        try:
            h.pause()
            print(f"  pause -> {h.state()}")
        except Exception as e:
            print(f"  pause: {e}")
        try:
            h.resume()
            print(f"  resume -> {h.state()}")
        except Exception as e:
            print(f"  resume: {e}")

    for name, h in handles.items():
        try:
            h.cancel()
        except:
            pass

    print(f"\nFinal active: {orch.active_count()}")
    return orch


# ============================================================
# Part 4: Streaming + Hooks Integration
# ============================================================

async def test_streaming_integration():
    """Hooks + streaming 集成测试。"""
    print("\n" + "=" * 60)
    print("Part 4: Streaming + Hooks Integration")
    print("=" * 60)

    agent = a3s_code.Agent.create("test/all_config.hcl")
    opts = a3s_code.SessionOptions()
    opts.builtin_skills = True
    opts.use_memory_session_store = True
    opts.default_security = True

    workspace = "/home/kai/Projects/研二下/a3scode_safe"
    session = agent.session(workspace, opts)
    print(f"Session: {session.session_id}")

    # 注册安全 hooks
    hooks = [
        ("sec_pre_tool",  "pre_tool_use",  None, {"priority": 0}),
        ("sec_post_tool", "post_tool_use", None, {"priority": 0}),
        ("sec_bash",      "pre_tool_use",  {"tool": "bash"}, {"priority": 0}),
        ("sec_write",     "pre_tool_use",  {"tool": "write"}, {"priority": 0}),
        ("sec_gen_s",     "generate_start", None, {"priority": 5}),
        ("sec_gen_e",     "generate_end",   None, {"priority": 5}),
        ("sec_prompt",    "pre_prompt",     None, {"priority": 0}),
        ("sec_resp",      "post_response",  None, {"priority": 0}),
        ("sec_error",     "on_error",       None, {"priority": 0, "async_execution": True}),
    ]
    for hook_id, evt, matcher, config in hooks:
        session.register_hook(hook_id, evt, matcher=matcher, config=config)
    print(f"Hooks: {session.hook_count()}\n")

    prompt = "What files are in the test/ directory? List them briefly."
    print(f"Prompt: {prompt}")
    print("-" * 50)

    events_count = {}
    text_buf = ""
    tool_calls = []

    async for event in session.stream(prompt):
        et = str(event.event_type)
        events_count[et] = events_count.get(et, 0) + 1

        if et == "turn_start":
            print(f"  ▶ Turn {event.turn}")
        elif et == "text_delta":
            text_buf += event.text
        elif et == "tool_start":
            tool_calls.append({"tool": event.tool_name, "id": event.tool_id})
            print(f"  🔧 {event.tool_name} (id={event.tool_id})")
        elif et == "tool_end":
            print(f"  ✅ {event.tool_name} exit={event.exit_code}")
        elif et == "turn_end":
            print(f"  ◼ Turn end (tokens={event.total_tokens})")
        elif et == "error":
            print(f"  ❌ {event.error}")

    print("-" * 50)
    print(f"\nResponse ({len(text_buf)} chars):")
    print(text_buf[:500])

    print(f"\n--- Event Counts ---")
    for k, v in sorted(events_count.items()):
        print(f"  {k:30s}: {v}")

    print(f"\n--- Tool Calls ---")
    for tc in tool_calls:
        print(f"  {tc}")

    print(f"\nActive hooks: {session.hook_count()}")
    return session


# ============================================================
# Main
# ============================================================

async def main():
    print(f"╔══════════════════════════════════════════════════════════╗")
    print(f"║  a3s-code v1.1.0 EventBus 完整探索                     ║")
    print(f"║  {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^52s}  ║")
    print(f"╚══════════════════════════════════════════════════════════╝\n")

    test_hook_registration()
    test_lane_and_queue()
    test_orchestrator()

    try:
        await test_streaming_integration()
    except Exception as e:
        print(f"\n⚠️ Streaming test error: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'=' * 60}")
    print("探索完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
