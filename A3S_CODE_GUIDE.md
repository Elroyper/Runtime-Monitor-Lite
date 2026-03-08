# a3s-code 完整入门指南

> 版本：`a3s-code == 1.1.0`（升级自 1.0.2）| 环境：`conda a3s_code`（Python 3.12）  
> 本文档基于 `test/explore_a3s_code.ipynb` 及 `test/test_eventbus.py` 实测结果整理。

---

## 目录

1. [a3s-code 是什么](#1-a3s-code-是什么)
2. [核心架构概览](#2-核心架构概览)
3. [快速上手](#3-快速上手)
4. [配置文件 (HCL)](#4-配置文件-hcl)
5. [Agent：门面对象](#5-agentAgent门面对象)
6. [Session：核心交互单元](#6-session核心交互单元)
7. [三种调用方式](#7-三种调用方式)
8. [内置工具清单](#8-内置工具清单)
9. [Skills 技能系统](#9-skills-技能系统)
10. [数据类型参考](#10-数据类型参考)
11. [SessionOptions 高级配置](#11-sessionoptions-高级配置)
12. [内存系统 (Memory)](#12-内存系统-memory)
13. [MCP 服务器集成](#13-mcp-服务器集成)
14. [多智能体团队 (Team)](#14-多智能体团队-team)
15. [EventType 事件类型参考](#15-eventtype-事件类型参考)
16. [性能基准参考](#16-性能基准参考)
17. [异常处理规律](#17-异常处理规律)
18. [常见使用模式](#18-常见使用模式)
19. [v1.1.0 新增：EventBus / Hook 系统](#19-v110-新增eventbus--hook-系统)
20. [v1.1.0 新增：Lane Queue 调度系统](#20-v110-新增lane-queue-调度系统)
21. [v1.1.0 新增：Orchestrator 多 Agent 协调](#21-v110-新增orchestrator-多-agent-协调)
22. [实时安全监督插件设计方案](#22-实时安全监督插件设计方案)

---

## 1. a3s-code 是什么

`a3s-code` 是一个 **Python AI 编程 Agent SDK**，让你可以用几行代码就创建一个能够：

- 🗂️ **读写文件**（`read`、`write`、`edit`、`patch`）
- 🔍 **搜索代码库**（`grep`、`glob`、`ls`）
- 💻 **执行 Shell 命令**（`bash`）
- 🌐 **联网搜索**（`web_search`、`web_fetch`）
- 🔀 **并行执行任务**（`parallel_task`、`batch`）
- 🧠 **记忆跨会话信息**（Memory 系统）
- 🤝 **组成多 Agent 团队**（Team API）

的 AI 编码助手。它本质上是 **a3s-code Rust 核心库的 Python 绑定**（`.so` 文件），通过 HCL 配置文件管理 LLM 提供商。

---

## 2. 核心架构概览

```
a3s-code SDK
│
├── Agent               ← 门面对象，持有 LLM 配置
│   └── Session         ← 工作区绑定的交互会话
│       ├── tools       ← 内置工具（ls/grep/bash/...）
│       ├── skills      ← 技能（内置 + 自定义 .md 文件）
│       ├── memory      ← 跨会话记忆存储
│       └── mcp         ← MCP 服务器协议集成
│
├── Team / TeamRunner   ← 多 Agent 协作框架
│
└── EventType           ← 流式事件类型枚举
```

---

## 3. 快速上手

### 最小示例

```python
from a3s_code import Agent

# 1. 创建 Agent（从 HCL 配置文件加载 LLM 提供商）
agent = Agent.create("test/all_config.hcl")

# 2. 创建 Session（绑定工作区目录）
session = agent.session("/path/to/your/project")

# 3. 发送消息（同步，等待完整回答）
result = session.send("这个项目是做什么的？")
print(result.text)
```

### 流式示例（推荐）

```python
import asyncio, nest_asyncio
nest_asyncio.apply()   # 在 Jupyter 中必须加这一行

async def chat():
    async for event in session.stream("分析项目结构并找出潜在 bug"):
        if event.event_type == "text_delta":
            print(event.text, end="", flush=True)
        elif event.event_type == "tool_start":
            print(f"\n🔧 {event.tool_name}...", end="")
        elif event.event_type == "end":
            print(f"\n完成！共 {event.total_tokens} tokens")
            break

asyncio.run(chat())
```

---

## 4. 配置文件 (HCL)

a3s-code 使用 **HCL（HashiCorp Configuration Language）** 格式配置 LLM 提供商，类似 Terraform 的配置风格。

### 最小配置

```hcl
default_model = "anthropic/claude-sonnet-4-20250514"

providers {
  name     = "anthropic"
  api_key  = "你的_API_KEY"
  base_url = "https://api.anthropic.com"     # 可选，默认官方地址

  models {
    id        = "claude-sonnet-4-20250514"
    tool_call = true
  }
}
```

### 多 Provider 配置示例（`all_config.hcl`）

```hcl
default_model = "openai/kimi-k2.5"

providers {
  name     = "anthropic"
  api_key  = "sk-ant-..."
  base_url = "https://your-proxy/api/v1"

  models {
    id           = "claude-sonnet-4-20250514"
    attachment   = true      # 支持图片/PDF 附件
    reasoning    = false     # 是否启用扩展推理
    tool_call    = true      # 必须为 true 才能使用工具
    temperature  = true

    modalities {
      input  = ["text", "image", "pdf"]
      output = ["text"]
    }

    cost {
      input  = 3.0    # 美元/百万 tokens
      output = 15.0
    }

    limit {
      context = 200000
      output  = 64000
    }
  }
}

providers {
  name = "openai"

  models {
    id       = "kimi-k2.5"
    api_key  = "sk-..."          # 也可在 model 级别覆盖 key
    base_url = "http://your-endpoint/v1"
    tool_call = true

    limit {
      context = 256000
      output  = 8192
    }
  }
}
```

### 配置查找优先级

当不传 config 路径时，`Agent.create()` 按以下顺序查找配置：

1. 传入的路径参数
2. `./` 当前目录中的 `config.hcl`
3. 向上递归查找 `.a3s/config.hcl`（类似 git 查找 `.git`）
4. `~/.config/a3s-code/config.hcl`

---

## 5. Agent：门面对象

```python
from a3s_code import Agent

agent = Agent.create("path/to/config.hcl")
```

### Agent 方法

| 方法 | 说明 |
|------|------|
| `Agent.create(config_source)` | **类方法**，从 HCL 文件路径或 HCL 字符串创建 Agent |
| `agent.session(workspace, ...)` | 创建绑定到 workspace 路径的 Session |
| `agent.resume_session(session_id, store_dir)` | 从磁盘恢复历史 Session |
| `agent.refresh_mcp_tools()` | 刷新 MCP 服务器工具列表 |

### session() 参数详解

```python
session = agent.session(
    workspace       = "/path/to/project",  # 工作区根目录（必填）
    options         = None,                # SessionOptions 对象
    model           = None,                # 覆盖默认模型，如 "anthropic/claude-sonnet-4-20250514"
    builtin_skills  = True,                # 启用 7 个内置 Skill
    skill_dirs      = ["path/to/skills"],  # 加载自定义 Skill 目录
    agent_dirs      = None,                # 加载自定义子 Agent 目录
    queue_config    = None,                # SessionQueueConfig 对象
    permissive      = True,                # True = 自动确认所有操作，不问用户
    planning        = None,                # 启用规划模式
    goal_tracking   = None,               # 启用目标跟踪
    max_parse_retries = None,             # 最大 JSON 解析重试次数
    tool_timeout_ms = None,               # 工具超时（毫秒）
    circuit_breaker_threshold = None,     # 工具连续失败熔断阈值
)
```

> **`permissive=True`**：跳过所有需要用户确认的交互，适合自动化场景。

---

## 6. Session：核心交互单元

Session 是真正执行 LLM 对话和工具调用的对象，**绑定到一个工作区目录**。

### Session 属性

```python
session.session_id    # UUID 字符串，唯一标识此 Session
session.workspace     # 绑定的工作区路径
session.has_memory    # bool，是否配置了记忆存储
session.init_warning  # str | None，初始化时的警告信息
```

### Session 核心方法

```python
# 对话
result = session.send(prompt)             # 同步调用，返回 AgentResult
stream = session.stream(prompt)           # 流式调用，返回 EventStream

# 带附件（图片/PDF，模型需支持 attachment=true）
result = session.send_with_attachments(prompt, attachments=["/path/to/img.png"])
stream = session.stream_with_attachments(prompt, attachments=[...])

# 直接工具调用（不经过 LLM）
tool_result = session.tool("ls", {"path": "/some/dir"})
tool_result = session.bash("cat README.md")
tool_result = session.glob("**/*.py")
tool_result = session.grep("TODO", path="./src")
tool_result = session.read_file("src/main.py")

# 历史与状态
history = session.history()              # 完整对话历史
session.clear_short_term()               # 清空短期上下文
session.clear_working()                  # 清空工作记忆
session.save()                           # 持久化到磁盘
session.tool_names()                     # 列出所有可用工具名
session.hook_count()                     # 注册的 hook 数量
session.has_queue()                      # 是否启用了队列
```

---

## 7. 三种调用方式

### 方式 A：直接工具调用（最快，无 LLM）

适合需要直接读写文件、执行命令，不需要 AI 推理时。

```python
result = session.tool("ls", {"path": "/path/to/dir"})
print(result.exit_code)  # 0 = 成功
print(result.output)     # 输出内容

# 简便语法
result = session.bash("grep -r 'TODO' ./src")
result = session.glob("**/*.py")
```

**耗时：< 5ms**（本地执行）

---

### 方式 B：同步 `send()`（简单，等待完整结果）

```python
result = session.send("解释一下 src/main.py 的功能")

print(result.text)                # AI 回答
print(result.total_tokens)        # 总 token 数
print(result.prompt_tokens)       # 输入 token
print(result.completion_tokens)   # 输出 token
print(result.tool_calls_count)    # LLM 调用了几次工具
```

**耗时：约 10-35 秒**（依赖模型和问题复杂度）

---

### 方式 C：流式 `stream()`（实时，生产推荐）

在 Jupyter 中必须先 `nest_asyncio.apply()`，在普通脚本中直接 `asyncio.run()` 即可。

```python
# 同步迭代（普通 Python 脚本）
for event in session.stream("分析这个项目"):
    if event.event_type == "text_delta":
        print(event.text, end="", flush=True)
    elif event.event_type == "end":
        break

# 异步迭代（async 函数内）
async def main():
    async for event in session.stream("分析这个项目"):
        if event.event_type == "text_delta":
            print(event.text, end="", flush=True)
        elif event.event_type == "end":
            break
```

---

## 8. 内置工具清单

Session 创建后自动可用以下 **14 个工具**（无需 `builtin_skills`）：

| 工具名 | 功能 |
|--------|------|
| `ls` | 列出目录内容 |
| `glob` | 按 glob 模式匹配文件 |
| `grep` | 在文件中搜索文本 |
| `read` | 读取文件内容 |
| `write` | 写入文件（完整覆盖） |
| `edit` | 编辑文件（定位替换） |
| `patch` | 应用 diff patch |
| `bash` | 执行 Shell 命令 |
| `web_search` | 网络搜索 |
| `web_fetch` | 抓取网页内容 |
| `batch` | 批量顺序执行工具 |
| `parallel_task` | 并行执行多个任务 |
| `task` | 创建子任务（委托给子 Agent） |
| `git_worktree` | Git worktree 操作 |

### 直接调用示例

```python
# 列目录
r = session.tool("ls", {"path": "/my/project"})

# 读文件
r = session.tool("read", {"path": "src/main.py"})

# 写文件
r = session.tool("write", {"path": "output.txt", "content": "Hello World"})

# 执行命令
r = session.tool("bash", {"command": "pytest tests/ -v"})

# 网络搜索
r = session.tool("web_search", {"query": "Python asyncio best practices"})
```

---

## 9. Skills 技能系统

Skills 是**提示词模板**（Instruction 类型）或**工具扩展**（Tool 类型），用来给 Agent 注入特定领域的行为规范。

### 内置 7 个 Skills

| Skill 名 | 用途 |
|----------|------|
| `explain-code` | 用简洁语言解释代码工作原理 |
| `code-review` | 代码审查：最佳实践、Bug、改进建议 |
| `code-search` | 在代码库中搜索模式/函数/类型 |
| `find-bugs` | 识别潜在 Bug、漏洞和代码异味 |
| `builtin-tools` | 内置文件操作和 Shell 工具的使用说明 |
| `delegate-task` | 将复杂任务委托给专门子 Agent |
| `find-skills` | 帮用户发现并安装 Agent Skills |

启用方式：

```python
session = agent.session(workspace, builtin_skills=True)
```

### 自定义 Skill（`.a3s/skills/` 目录）

在项目的 `.a3s/skills/<skill-name>/SKILL.md` 中编写，格式：

```markdown
---
name: api-docs
description: Generate OpenAPI documentation from code
triggers:
  - "generate docs"
  - "document api"
---

When asked to generate API documentation:
1. Read all handler files to understand the API surface
2. Extract route definitions, parameters, and response types
3. Generate OpenAPI 3.0 YAML format
4. Write to docs/openapi.yaml
```

加载方式：

```python
session = agent.session(
    workspace,
    skill_dirs=["/path/to/.a3s/skills"],  # 指定 Skill 目录
    builtin_skills=True,                   # 同时启用内置 Skills
)
```

### 在 Prompt 中调用 Skill

直接在 prompt 中提及 skill 名即可触发：

```python
result = session.send("使用 explain-code skill 分析 src/main.py")
result = session.send("使用 api-docs skill 为本项目生成 API 文档")
result = session.send("使用 find-bugs skill 检查 auth/ 目录")
```

---

## 10. 数据类型参考

### `AgentResult`（`send()` 的返回值）

```python
result.text               # str，AI 的完整回答
result.total_tokens       # int，总 token 数
result.prompt_tokens      # int，输入 token 数
result.completion_tokens  # int，输出 token 数
result.tool_calls_count   # int，LLM 共调用了几次工具
```

### `AgentEvent`（`stream()` 产出的事件）

```python
event.event_type    # str，事件类型（见 EventType 常量）
event.text          # str，文本增量（text_delta 事件）
event.tool_name     # str，工具名（tool_start/tool_end 事件）
event.tool_id       # str，工具调用 ID
event.tool_output   # str，工具输出（tool_end 事件）
event.exit_code     # int，工具退出码（0 = 成功）
event.turn          # int，当前 turn 编号（turn_end 事件）
event.total_tokens  # int，累计 token 数（turn_end / end 事件）
event.error         # str，错误信息（error 事件）
event.prompt        # str，发送给 LLM 的 prompt（start 事件）
```

### `ToolResult`（`session.tool()` 的返回值）

```python
result.name       # str，工具名
result.exit_code  # int，0 = 成功，非 0 = 失败
result.output     # str，工具执行的输出内容
```

---

## 11. SessionOptions 高级配置

`SessionOptions` 允许对 Session 进行精细控制：

```python
from a3s_code import SessionOptions

opts = SessionOptions()

# 注入自定义指令（追加到系统 prompt）
opts.add_instruction("coding-style", "Always use snake_case for variables.")
opts.add_instruction("language", "Reply in Chinese.")

# 设置 AI 角色人格
opts.add_persona("expert", "You are a senior Python architect with 10 years experience.")

# 回答风格
opts.response_style = "concise"   # 或 "detailed"、"markdown"

# 指导原则（全局 guidelines）
opts.guidelines = "Focus on security and performance."

# 记忆目录（启用跨会话记忆）
opts.memory_dir = "/path/to/.a3s/memory"
opts.use_memory_session_store = True

# 自动压缩上下文（防止超出 context window）
opts.auto_compact = True
opts.auto_compact_threshold = 0.8  # 达到 80% 时自动压缩

# 使用时
session = agent.session(workspace, options=opts)
```

---

## 12. 内存系统 (Memory)

内存系统让 Agent 能**跨会话记住**重要信息。

### 启用内存

```python
from a3s_code import SessionOptions

opts = SessionOptions()
opts.memory_dir = "/path/to/.a3s/memory"  # 指定存储目录
opts.use_memory_session_store = True

session = agent.session(workspace, options=opts)
print(session.has_memory)   # True
```

### 内存 API

```python
# 统计
stats = session.memory_stats()

# 最近的记忆条目
items = session.memory_recent(limit=10)

# 语义相似度搜索
items = session.recall_similar("Python async programming", limit=5)

# 按标签搜索
items = session.recall_by_tags(["bug", "security"], limit=10)

# 手动写入记忆（Agent 自动调用，也可手动）
session.remember_success(task="写了单元测试", tools=["write", "bash"], result="所有测试通过")
session.remember_failure(task="部署到生产", error="权限不足", tools=["bash"])

# 工作记忆
wm = session.get_working()         # 获取当前工作记忆
session.clear_working()            # 清空工作记忆
session.clear_short_term()        # 清空短期记忆（对话历史）
```

---

## 13. MCP 服务器集成

MCP（Model Context Protocol）允许你扩展 Agent 的工具能力，接入外部服务。

```python
# 添加 stdio 类型 MCP 服务器
session.add_mcp_server(
    name      = "my-mcp-server",
    transport = "stdio",
    command   = "npx",
    args      = ["-y", "@modelcontextprotocol/server-filesystem", "/data"],
    env       = {"MY_ENV": "value"},
)

# 添加 HTTP/SSE 类型 MCP 服务器
session.add_mcp_server(
    name      = "remote-server",
    transport = "http",
    url       = "http://localhost:3000/sse",
    headers   = {"Authorization": "Bearer token"},
)

# 查看 MCP 服务器状态
status = session.mcp_status()   # dict，key = server_name

# 移除 MCP 服务器
session.remove_mcp_server("my-mcp-server")

# 刷新工具列表（添加 MCP 后需调用）
agent.refresh_mcp_tools()
```

---

## 14. 多智能体团队 (Team)

`Team` API 允许创建多个 Session 协作完成复杂任务，支持 **lead（协调者）**、**worker（执行者）**、**reviewer（审核者）** 三种角色。

```python
from a3s_code import Agent, Team, TeamRunner, TeamConfig

agent = Agent.create("config.hcl")
cfg = TeamConfig(max_rounds=10, poll_interval_ms=200)

# 1. 创建团队并分配角色
team = Team("refactor-project", config=cfg)
team.add_member("lead",       "lead")
team.add_member("worker-1",   "worker")
team.add_member("worker-2",   "worker")
team.add_member("reviewer",   "reviewer")

# 2. 为每个角色创建 Session
lead_session     = agent.session(workspace, builtin_skills=True)
worker1_session  = agent.session(workspace, builtin_skills=True)
worker2_session  = agent.session(workspace)
reviewer_session = agent.session(workspace, builtin_skills=True)

# 3. 绑定 Session 到角色
runner = TeamRunner(team)
runner.bind_session("lead",     lead_session)
runner.bind_session("worker-1", worker1_session)
runner.bind_session("worker-2", worker2_session)
runner.bind_session("reviewer", reviewer_session)

# 4. 执行任务（阻塞直到完成）
result = runner.run_until_done("重构 auth 模块，添加单元测试，并生成 API 文档")

# 5. 查看结果
for task in result.done_tasks:
    print(f"  [{task.id}] {task.description[:50]} → {task.result[:100]}")
```

### TaskBoard API（手动任务管理）

```python
board = runner.task_board()   # 或 team.task_board()

task_id = board.post("实现登录功能", posted_by="lead")
board.claim("worker-1")        # worker-1 认领任务
board.complete(task_id, "实现完成，已通过测试")
board.approve(task_id)         # reviewer 批准

stats = board.stats()          # 任务统计
pending = board.by_status("pending")   # 按状态过滤
```

---

## 15. EventType 事件类型参考

`stream()` 返回的事件流中，每个事件的 `event_type` 为以下常量之一：

| 常量 | 值 | 说明 |
|------|----|------|
| `EventType.START` | `"start"` | 会话开始，含 `prompt` 字段 |
| `EventType.TURN_START` | `"turn_start"` | 新 turn 开始 |
| `EventType.TEXT_DELTA` | `"text_delta"` | AI 文本增量，含 `text` 字段 |
| `EventType.TOOL_START` | `"tool_start"` | 工具开始执行，含 `tool_name`、`tool_id` |
| `EventType.TOOL_OUTPUT_DELTA` | `"tool_output_delta"` | 工具输出增量（大输出时） |
| `EventType.TOOL_END` | `"tool_end"` | 工具完成，含 `exit_code`、`tool_output` |
| `EventType.TURN_END` | `"turn_end"` | turn 结束，含 `turn`、`total_tokens` |
| `EventType.END` | `"end"` | 整个会话结束，含 `total_tokens` |
| `EventType.ERROR` | `"error"` | 发生错误，含 `error` 字段 |
| `EventType.CONFIRMATION_REQUIRED` | `"confirmation_required"` | 需要用户确认（`permissive=False` 时出现） |
| `EventType.CONFIRMATION_RECEIVED` | `"confirmation_received"` | 用户已确认 |
| `EventType.CONFIRMATION_TIMEOUT` | `"confirmation_timeout"` | 确认超时 |
| `EventType.PERMISSION_DENIED` | `"permission_denied"` | 操作被拒绝 |
| `EventType.EXTERNAL_TASK_PENDING` | `"external_task_pending"` | 外部任务等待中 |
| `EventType.EXTERNAL_TASK_COMPLETED` | `"external_task_completed"` | 外部任务完成 |

### 推荐的事件处理模板

```python
from a3s_code import EventType

async for event in session.stream(prompt):
    t = event.event_type
    if t == EventType.TEXT_DELTA:
        print(event.text, end="", flush=True)
    elif t == EventType.TOOL_START:
        print(f"\n🔧 {event.tool_name} (id={event.tool_id})...", end="")
    elif t == EventType.TOOL_END:
        status = "✓" if event.exit_code == 0 else "✗"
        print(f" {status}")
    elif t == EventType.TURN_END:
        print(f"\n└─ Turn {event.turn} ({event.total_tokens} tokens)")
    elif t == EventType.END:
        print(f"\n■ Done — {event.total_tokens} tokens")
        break
    elif t == EventType.ERROR:
        print(f"\n❌ {event.error}")
        break
    elif t == EventType.CONFIRMATION_REQUIRED:
        # permissive=False 时需要手动确认
        print(f"\n⚠️  需要确认：{event.text}")
```

---

## 16. 性能基准参考

以下数据来自实测（模型：`kimi-k2.5`，API 位于内网）：

| 调用方式 | 耗时 | 备注 |
|----------|------|------|
| `session.tool()` 直接工具调用 | **< 5ms** | 无 LLM，本地执行 |
| `session.send()` 简单问答 | **10-35s** | 取决于问题复杂度 |
| `session.send()` 复杂分析 | **30-40s** | 多次工具调用 |
| `session.stream()` 流式 | **与 send 相同** | 但用户可实时看到输出 |

### Token 用量参考（基于 5 个 prompt 批量测试）

| 指标 | 数值 |
|------|------|
| 平均总 tokens / 请求 | ~18,593 |
| 最小（简单问题） | 9,026 |
| 最大（复杂分析） | 32,936 |
| 平均工具调用次数 | 4.6 次/请求 |

> **注意**：token 数量会随对话历史增长而累积，长对话建议启用 `auto_compact`。

---

## 17. 异常处理规律

从边界测试中总结的 a3s-code 异常行为：

| 情景 | 行为 | 异常类型 |
|------|------|----------|
| 无效 config 路径（文件不存在） | HCL 解析失败 | `RuntimeError` |
| 空字符串 config | `default_model` 缺失 | `RuntimeError` |
| **不存在的 workspace 路径** | **正常创建 Session，不报错** | 无异常 |
| 空字符串 prompt | 正常发送，AI 自动处理 | 无异常 |
| 超长 prompt（10k+ chars） | 正常处理（模型截断或分析） | 无异常 |
| 不存在的工具名 | `exit_code=1`，不抛异常 | 无异常 |
| 工具参数类型错误（如 int 给 path） | 自动转换，尽力执行 | 无异常 |
| `recall_similar()` 未配置 memory | 抛异常 | `RuntimeError` |
| `get_short_term()` 未配置 memory | 抛异常 | `RuntimeError` |

**关键结论**：
- workspace 路径合法性**延迟校验**（到实际工具调用时才报错）
- 工具调用失败通过 `exit_code != 0` 表示，不抛异常
- Memory API 需要 `SessionOptions.memory_dir` 预先配置

---

## 18. 常见使用模式

### 模式 1：代码分析助手

```python
agent = Agent.create("config.hcl")
session = agent.session("./my-project", builtin_skills=True, permissive=True)

# 一次性分析整个项目
result = session.send("使用 explain-code skill 分析这个项目的整体架构")
print(result.text)
```

### 模式 2：自动化代码审查

```python
# 找出所有 Bug
result = session.send("使用 find-bugs skill 审查 src/ 目录下的所有 Python 文件")
print(result.text)
```

### 模式 3：保存历史并恢复

```python
# 第一次对话
session = agent.session(workspace)
session.send("分析这个项目")
session.save()
saved_id = session.session_id

# 之后恢复对话
session2 = agent.resume_session(saved_id, session_store_dir="./.a3s/sessions")
session2.send("继续刚才的分析，重点看 auth 模块")
```

### 模式 4：事件存档（参考 `test_events.py`）

```python
import json, asyncio
from datetime import datetime

turns = []
current_turn = {"turn": 1, "text": "", "tools": []}

async for event in session.stream("分析项目"):
    if event.event_type == "text_delta":
        current_turn["text"] += event.text
    elif event.event_type == "tool_end":
        current_turn["tools"].append({
            "tool_name": event.tool_name,
            "exit_code": event.exit_code,
        })
    elif event.event_type == "turn_end":
        turns.append(current_turn)
        current_turn = {"turn": event.turn + 1, "text": "", "tools": []}
    elif event.event_type == "end":
        break

# 保存为 JSON
with open(f"events_{datetime.now():%Y%m%d_%H%M%S}.json", "w") as f:
    json.dump({"turns": turns}, f, ensure_ascii=False, indent=2)
```

### 模式 5：Jupyter Notebook 中使用

```python
# 在 Notebook 最开头必须执行（解决 event loop 冲突）
import nest_asyncio
nest_asyncio.apply()

# 之后正常使用 asyncio.run()
import asyncio
asyncio.run(my_async_function())

# 或者直接 await（在 ipython/jupyter 中可用）
await my_async_function()
```

---

## 19. v1.1.0 新增：EventBus / Hook 系统

> 实测日期：2026-03-06 | 测试脚本：`test/test_eventbus.py`

### 19.1 概述

v1.1.0 引入了**生命周期 Hook 系统**，允许在 Agent 运行的关键阶段注册拦截器。这是构建安全监督、审计日志、策略执行等插件的基础。

```
Agent 请求流程 + Hook 触发点
─────────────────────────────────
  session_start ──▶ pre_prompt ──▶ generate_start
                                       │
                                  LLM 生成中...
                                       │
                                  generate_end ──▶ post_response
                                       │
                              ┌── pre_tool_use ──┐
                              │   工具执行中...    │
                              └── post_tool_use ──┘
                                       │
                                  (循环 turn)
                                       │
                                  session_end
                                       │
                           on_error (任何阶段出错时)
                           skill_load / skill_unload
```

### 19.2 支持的 11 个 Hook 事件类型

| 事件类型 | 触发时机 | 安全用途 |
|---|---|---|
| `pre_tool_use` | 工具执行**前** | ⭐ 拦截危险命令、审计工具调用 |
| `post_tool_use` | 工具执行**后** | 审计执行结果、检测异常输出 |
| `generate_start` | LLM 开始生成 | 记录生成开始时间 |
| `generate_end` | LLM 生成结束 | 计算生成耗时、token 统计 |
| `session_start` | 会话开始 | 初始化安全上下文 |
| `session_end` | 会话结束 | 生成审计报告 |
| `skill_load` | 技能加载 | 验证技能来源、白名单检查 |
| `skill_unload` | 技能卸载 | 记录技能生命周期 |
| `pre_prompt` | prompt 发送前 | ⭐ 过滤/修改 prompt、注入安全指令 |
| `post_response` | LLM 响应后 | ⭐ 检测输出中的敏感信息 |
| `on_error` | 错误发生时 | 错误告警、异常审计 |

### 19.3 API 用法

```python
# 注册 hook
session.register_hook(
    hook_id="security_bash_guard",     # 唯一标识
    event_type="pre_tool_use",         # 事件类型
    matcher={                          # 可选：过滤条件
        "tool": "bash",                # 只匹配 bash 工具
        "command_pattern": "rm *",     # 匹配 rm 命令
    },
    config={                           # 可选：hook 配置
        "priority": 0,                 # 优先级 (0=最高)
        "timeout_ms": 5000,            # 超时
        "async_execution": True,       # 异步执行
        "max_retries": 3,              # 最大重试
    },
)

# 查询 hook 数量
count = session.hook_count()  # -> int

# 注销 hook
removed = session.unregister_hook("security_bash_guard")  # -> bool
```

### 19.4 Matcher 字段参考

| 字段 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `tool` | str | 工具名匹配 | `"bash"`, `"write"`, `"read"` |
| `path_pattern` | str | 文件路径 glob | `"*.py"`, `"/etc/*"`, `"src/**/*.rs"` |
| `command_pattern` | str | 命令模式匹配 | `"rm *"`, `"chmod *"`, `"curl *"` |
| `session_id` | str | 特定会话 ID | `session.session_id` |
| `skill` | str | 技能名匹配 | `"api-docs"` |

**支持组合使用**（AND 逻辑）：

```python
matcher={"tool": "bash", "command_pattern": "rm -rf *"}  # 同时满足
matcher={"tool": "write", "path_pattern": "/etc/*"}       # 拦截写入 /etc
```

### 19.5 v1.1.0 新增 Stream EventType

v1.1.0 流式事件新增 `tool_input_delta`（工具输入参数的流式增量），但**尚未加入 `EventType` 枚举**：

```python
async for event in session.stream(prompt):
    et = str(event.event_type)
    if et == "tool_input_delta":   # 需要用字符串比较
        pass  # 工具输入参数正在流式传入
```

完整 EventType 列表（v1.1.0）：

| 枚举成员 | 值 | 新增 |
|---|---|---|
| `START` | `start` | |
| `TURN_START` | `turn_start` | |
| `TEXT_DELTA` | `text_delta` | |
| `TOOL_START` | `tool_start` | |
| *(未在枚举中)* | `tool_input_delta` | ✅ v1.1.0 |
| `TOOL_OUTPUT_DELTA` | `tool_output_delta` | |
| `TOOL_END` | `tool_end` | |
| `TURN_END` | `turn_end` | |
| `END` | `end` | |
| `ERROR` | `error` | |
| `CONFIRMATION_REQUIRED` | `confirmation_required` | |
| `CONFIRMATION_RECEIVED` | `confirmation_received` | |
| `CONFIRMATION_TIMEOUT` | `confirmation_timeout` | |
| `PERMISSION_DENIED` | `permission_denied` | |
| `EXTERNAL_TASK_PENDING` | `external_task_pending` | |
| `EXTERNAL_TASK_COMPLETED` | `external_task_completed` | |

---

## 20. v1.1.0 新增：Lane Queue 调度系统

### 20.1 概述

Lane Queue 将工具执行分成 4 条**优先级通道**，支持并发控制、死信队列、外部任务委托。

```
┌─────────────────────────────────────────┐
│              Session Queue               │
├──────────┬──────────┬──────────┬────────┤
│ control  │  query   │ execute  │generate│
│ (最高优先)│ (只读,高并发)│(读写,中并发)│(生成,低并发)│
│          │ max=4    │ max=2    │ max=1  │
├──────────┴──────────┴──────────┴────────┤
│  DLQ (死信队列) │ Metrics │ Alerts     │
└─────────────────────────────────────────┘
```

### 20.2 Queue 配置

```python
qc = a3s_code.SessionQueueConfig()
qc.set_query_concurrency(8)       # Query 并发上限
qc.set_execute_concurrency(2)     # Execute 并发上限
qc.set_generate_concurrency(1)    # Generate 并发上限
qc.set_timeout(30000)             # 默认超时 (ms)
qc.enable_dlq(max_size=100)       # 启用死信队列
qc.enable_metrics()               # 启用指标收集
qc.enable_alerts()                # 启用告警
# 或一键启用全部:
# qc.with_lane_features()

opts = a3s_code.SessionOptions()
opts.queue_config = qc
```

### 20.3 Lane Handler 模式

每条 Lane 可设置 3 种处理模式：

| 模式 | 说明 | 安全用途 |
|---|---|---|
| `internal` | 内部处理（默认） | 正常执行 |
| `external` | 外部处理 | ⭐ 将工具调用委托给外部安全审批系统 |
| `hybrid` | 混合模式 | 部分内部、部分委托 |

```python
# 设置 execute lane 为外部审批模式
session.set_lane_handler("execute", mode="external", timeout_ms=60000)

# 获取待审批任务
pending = session.pending_external_tasks()
# -> [{"task_id": "...", "lane": "execute", "command_type": "...", "payload": {...}}]

# 审批通过
session.complete_external_task(task_id, success=True, result={"approved": True})

# 审批拒绝
session.complete_external_task(task_id, success=False, error="Blocked by policy")
```

### 20.4 Submit API

直接向指定 Lane 提交 Python callable：

```python
# 单个提交
result = session.submit("query", lambda: {"scan": "injection", "risk": 0.0})

# 批量提交
results = session.submit_batch("query", [
    lambda: {"scan": "path_traversal", "risk": 0.1},
    lambda: {"scan": "privilege_escalation", "risk": 0.3},
])
```

### 20.5 监控 API

```python
session.queue_stats()    # -> {"total_pending", "total_active", "external_pending", "lanes"}
session.queue_metrics()  # -> {"counters", "gauges", "histograms"} 或 None
session.dead_letters()   # -> [{"command_id", "command_type", "lane", "error", "attempts"}]
```

---

## 21. v1.1.0 新增：Orchestrator 多 Agent 协调

### 21.1 概述

`Orchestrator` 提供**主-子 Agent 协调机制**，可动态 spawn 多个子 Agent 并监控其状态和活动。

### 21.2 核心类

```python
# 创建 Orchestrator (内存通信)
orch = a3s_code.Orchestrator.create()

# SubAgent 配置
config = a3s_code.SubAgentConfig(
    agent_type="security_scanner",      # 类型标识
    prompt="Scan for vulnerabilities",  # 子 Agent 任务描述
    description="安全扫描子 Agent",      # 可选描述
    permissive=False,                   # 是否宽松模式
    max_steps=10,                       # 最大步数
    timeout_ms=30000,                   # 超时 (ms)
    parent_id=None,                     # 可选父 Agent ID
)

# Spawn 子 Agent -> SubAgentHandle
handle = orch.spawn_subagent(config)
```

### 21.3 SubAgentHandle 控制

```python
handle.id          # 子 Agent ID (e.g. "subagent-1")
handle.state()     # 状态: "Initializing" | "Running" | "Paused" | ...
handle.pause()     # 暂停
handle.resume()    # 恢复
handle.cancel()    # 取消
handle.wait()      # 等待完成并获取结果
```

### 21.4 Orchestrator 监控

```python
orch.active_count()          # 活跃子 Agent 数
orch.list_subagents()        # -> [SubAgentInfo, ...]
orch.get_all_states()        # 所有子 Agent 状态列表
orch.get_active_activities() # 活跃活动列表
orch.get_subagent_info(id)   # 特定子 Agent 信息
orch.wait_all()              # 等待所有子 Agent 完成
```

### 21.5 SubAgentInfo 属性

```python
info = orch.get_subagent_info("subagent-1")
info.id              # "subagent-1"
info.agent_type      # "security_scanner"
info.state           # "Running"
info.description     # "安全扫描子 Agent"
info.parent_id       # None
info.created_at      # Unix timestamp (ms)
info.updated_at      # Unix timestamp (ms)
info.current_activity  # SubAgentActivity or None
```

### 21.6 SubAgentActivity

```python
act = info.current_activity
act.activity_type  # "idle" | "calling_tool" | "requesting_llm" | "waiting_for_control"
act.data           # JSON string, e.g. '{"args":{"path":"/tmp/file.txt"},"tool_name":"read"}'
```

---

## 22. 实时安全监督插件设计方案

基于 v1.1.0 的 Hook + Lane Queue + Orchestrator 三大机制，可构建完整的实时安全监督插件：

### 22.1 架构设计

```
┌──────────────────────────────────────────────────────────────┐
│                    SafetyPlugin (主控)                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐   ┌──────────────┐   ┌───────────────────┐   │
│  │  Hook层   │──▶│  分析引擎    │──▶│  策略执行器        │   │
│  │ (拦截事件) │   │ (风险评估)   │   │ (允许/阻止/告警)   │   │
│  └──────────┘   └──────────────┘   └───────────────────┘   │
│       │                                     │               │
│       ▼                                     ▼               │
│  ┌──────────┐                        ┌────────────┐        │
│  │ 审计日志  │                        │  Orchestrator│       │
│  │ (全量记录) │                        │ (子Agent协调) │       │
│  └──────────┘                        └────────────┘        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 22.2 核心实现思路

#### (1) Hook 层：事件拦截

```python
def register_safety_hooks(session):
    """注册安全监控 hook 集合。"""
    # 工具调用前置检查 (最高优先级)
    session.register_hook("safety_pre_tool", "pre_tool_use",
        config={"priority": 0, "timeout_ms": 5000})
    
    # 危险命令拦截
    session.register_hook("safety_rm_guard", "pre_tool_use",
        matcher={"tool": "bash", "command_pattern": "rm *"},
        config={"priority": 0})
    
    # 敏感路径写入拦截
    session.register_hook("safety_etc_guard", "pre_tool_use",
        matcher={"tool": "write", "path_pattern": "/etc/*"},
        config={"priority": 0})
    
    # prompt 注入检测
    session.register_hook("safety_prompt_scan", "pre_prompt",
        config={"priority": 0})
    
    # 输出敏感信息检测
    session.register_hook("safety_output_scan", "post_response",
        config={"priority": 0})
    
    # 工具结果审计
    session.register_hook("safety_audit_tool", "post_tool_use",
        config={"priority": 1, "async_execution": True})
    
    # 错误追踪
    session.register_hook("safety_error_track", "on_error",
        config={"priority": 0, "async_execution": True})
```

#### (2) Lane Queue：外部安全审批

```python
def enable_security_approval(session):
    """将 execute lane 设为外部审批模式。"""
    session.set_lane_handler("execute", mode="external", timeout_ms=60000)
    
async def security_approval_loop(session):
    """持续检查待审批任务并进行安全评估。"""
    while True:
        pending = session.pending_external_tasks()
        for task in pending:
            risk = assess_risk(task["payload"])
            if risk > THRESHOLD:
                session.complete_external_task(
                    task["task_id"], success=False,
                    error=f"Blocked: risk={risk:.2f}")
            else:
                session.complete_external_task(
                    task["task_id"], success=True,
                    result={"approved": True, "risk": risk})
        await asyncio.sleep(0.1)
```

#### (3) Orchestrator：子 Agent 安全扫描

```python
def spawn_security_agents(orch):
    """启动安全监控子 Agent 集群。"""
    agents = {}
    
    # 威胁检测 Agent
    agents["threat"] = orch.spawn_subagent(a3s_code.SubAgentConfig(
        agent_type="threat_detector",
        prompt="Monitor for injection, path traversal, privilege escalation",
        permissive=False, max_steps=100, timeout_ms=300000,
    ))
    
    # 合规检查 Agent
    agents["compliance"] = orch.spawn_subagent(a3s_code.SubAgentConfig(
        agent_type="compliance_checker",
        prompt="Verify all operations comply with security policy",
        permissive=False, max_steps=50, timeout_ms=60000,
    ))
    
    return agents
```

#### (4) 流式监控集成

```python
async def monitored_stream(session, prompt):
    """带安全监控的流式请求。"""
    events_log = []
    
    async for event in session.stream(prompt):
        et = str(event.event_type)
        
        # 记录所有事件到审计日志
        events_log.append({
            "type": et,
            "ts": datetime.now().isoformat(),
            "tool": getattr(event, "tool_name", None),
            "error": getattr(event, "error", None),
        })
        
        # tool_input_delta: 实时监控工具输入参数
        if et == "tool_input_delta":
            # 可在此检测注入模式
            pass
        
        # tool_start: 记录工具调用
        elif et == "tool_start":
            log_tool_call(event.tool_name, event.tool_id)
        
        # tool_end: 检查执行结果
        elif et == "tool_end":
            if event.exit_code != 0:
                alert_tool_failure(event.tool_name, event.exit_code)
        
        yield event  # 透传给上层
    
    # 生成审计摘要
    generate_audit_summary(events_log)
```

### 22.3 安全策略矩阵

| 威胁类型 | Hook 事件 | Matcher | 处理方式 |
|---|---|---|---|
| 命令注入 | `pre_tool_use` | `tool=bash` | 分析命令，阻止高危 |
| 路径穿越 | `pre_tool_use` | `path_pattern=../*` | 检测 `../`，拒绝 |
| 权限提升 | `pre_tool_use` | `command_pattern=sudo *` | 直接阻止 |
| 敏感文件访问 | `pre_tool_use` | `path_pattern=/etc/*` | 告警 + 审批 |
| Prompt 注入 | `pre_prompt` | — | NLP 检测注入模式 |
| 数据泄露 | `post_response` | — | 扫描输出中的密钥/密码 |
| 异常工具输出 | `post_tool_use` | — | 检测异常模式 |
| 网络访问 | `pre_tool_use` | `tool=bash,command_pattern=curl *` | 白名单策略 |

### 22.4 下一步实施计划

1. **Phase 1**: 基于 Hook 实现只读审计日志插件
2. **Phase 2**: 添加策略引擎（规则匹配 + 风险评分）
3. **Phase 3**: 集成 Lane Queue 外部审批流程
4. **Phase 4**: 使用 Orchestrator 实现多 Agent 协同安全分析
5. **Phase 5**: 与 SafeClaw 的 `AuditEventBus` / NATS 桥接打通

---

## 附录：项目目录结构说明

```
test/
├── all_config.hcl           # 多 Provider 完整配置（anthropic + openai）
├── config.hcl               # 简单配置示例（用于参考）
├── test.py                  # 基础流式调用测试
├── test_events.py           # 带事件存档的流式测试
├── test_skills.py           # Skills 功能测试
├── test_notflush.py         # 同步 send() 测试
├── test_eventbus.py         # v1.1.0 EventBus/Hook/Orchestrator 完整探索
├── test_lane_hooks.py       # Lane Handler 和 Hook 快速测试
├── test_eventbus_integration.py  # Streaming + Hooks 集成测试
├── explore_a3s_code.ipynb   # 全方面探索 Notebook
├── events_20260225_*.json   # 历史事件记录（9 个 turn）
├── events_20260303_*.json   # 历史事件记录（5 个 turn）
└── .a3s/
    └── skills/
        └── api-docs/
            └── SKILL.md     # 自定义 Skill：生成 OpenAPI 文档
```

---

*文档基于 `a3s-code==1.1.0` 实测生成，2026-03-06（v1.0.2 部分 2026-03-05）*
