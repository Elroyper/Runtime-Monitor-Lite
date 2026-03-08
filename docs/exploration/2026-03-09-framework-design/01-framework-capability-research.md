# 框架能力调研记录（a3s-first 设计输入）

> 日期：2026-03-09  
> 目标：为“先兼容 a3s-code，后续逐步兼容其他框架”的架构设计提供能力边界依据。

---

## 1. 调研结论先行

1. 当前最强可控面仍是 `a3s-code`（本仓库已有 Hook/Lane/Orchestrator 实测资产）。
2. 后续框架兼容难度随权限减少而上升，兼容顺序应保持：  
   `openclaw -> ag2/langgraph -> claude code -> codex`。
3. 因此总架构必须是“能力感知（capability-aware）”而不是“一刀切同能力假设”。

---

## 2. 框架级能力快照（设计视角）

### 2.1 a3s-code（优先落地）

依据仓库现有实测文档与脚本（`A3S_CODE_GUIDE.md`, `test/test_eventbus.py`）：

- 可观测：流式事件、工具生命周期、错误事件。
- 可拦截：`pre_tool_use` / `pre_prompt` 等 Hook。
- 可决策：Lane external 支持外部审批闭环。
- 可编排：Orchestrator 支持多 agent 协调与并行分析。

结论：可作为“完整监督闭环”的第一实现目标。

### 2.2 OpenClaw（后续优先适配）

公开文档显示其具备 hooks/automation 与 runbook 配置能力，支持事件触发逻辑与执行策略。

- 可观测：命令执行、会话流程等运行事件可纳入 hooks 自动化。
- 可拦截：支持在动作前后执行 hook 逻辑（具体拦截粒度需以目标版本验证）。
- 局限：生态与接口稳定性需按版本核验；文档与实现可能存在差异。

结论：预计比 AG2/LangGraph 更接近“运行时内联控制”。

### 2.3 AG2 / LangGraph（中权限）

AG2 文档给出 runtime logging / event logging / traces 方向；LangGraph 官方强调 interrupt/human-in-the-loop、线程持久化、可观测性。

- 可观测：节点级执行轨迹、状态推进、部分事件回调。
- 可拦截：主要在节点边界/中断点，而非所有底层工具动作。
- 局限：是否可强阻断底层命令，强依赖具体执行器封装方式。

结论：适合“节点级闸门 + 轨迹分析”，不宜默认假设“全量工具前置阻断”。

### 2.4 Claude Code（低权限）

Claude Code 文档显示具备 hooks、permissions、settings policy 等机制。

- 可观测：工具调用与会话事件可通过 hooks/日志感知。
- 可控制：存在权限策略与审批模式，但受宿主执行环境与产品边界约束。
- 局限：深层运行时状态可见性/可控性低于 a3s 内嵌式方案。

结论：更适合“策略约束 + 旁路审计 + 外部环境防护”的组合。

### 2.5 Codex（低权限/更外部化）

OpenAI Codex 文档与 CLI/仓库文档显示具有审批策略、沙箱策略、配置文件控制。

- 可观测：会话与工具动作具备可记录性。
- 可控制：支持 approval/sandbox 策略，但内核级深度插桩能力有限。
- 局限：强控制更依赖环境级隔离与权限边界，而非框架内部 hook 丰富度。

结论：以“环境级控制 + 审计回放 + 风险后验定位”为主。

---

## 3. 能力维度定义（统一矩阵口径）

为避免后续适配时讨论偏差，统一使用以下维度评估框架能力：

1. `E` 可观测性：事件完整度、轨迹可重建性。
2. `G` 可闸门化：是否支持关键动作前置审批/阻断。
3. `I` 注入点丰富度：hook/callback/中断点数量与粒度。
4. `P` 权限承载：框架内置权限模型与外部策略协同能力。
5. `R` 回放与溯源：是否便于重建证据链与根因路径。

---

## 4. a3s-first 原则（强约束）

后续所有实现必须遵循：

1. 先在 a3s 上实现“可跑通、可验证、可回放”的最小闭环。  
2. 未达成 a3s MVP 前，不进入其他框架的工程实现。  
3. 其他框架当前仅做适配设计与能力核验，不做主线开发分流。

---

## 5. 主要参考来源（官方/一手优先）

- A3S 本仓库材料：
  - `A3S_CODE_GUIDE.md`
  - `test/test_eventbus.py`
- OpenClaw：
  - https://github.com/openclaw/openclaw
  - https://docs.openclaw.ai/automation/hooks
  - https://docs.openclaw.ai/runbook/quickstart
- AG2：
  - https://github.com/ag2ai/ag2
  - https://docs.ag2.ai/latest/docs/use-cases/notebooks/notebooks/runtime_logging
  - https://docs.ag2.ai/latest/docs/use-cases/notebooks/notebooks/event_logger
- LangGraph：
  - https://docs.langchain.com/oss/python/langgraph/overview
  - https://docs.langchain.com/oss/python/langgraph/interrupts
  - https://docs.langchain.com/langgraph-platform/observability
- Claude Code：
  - https://docs.anthropic.com/en/docs/claude-code/overview
  - https://docs.anthropic.com/en/docs/claude-code/settings
  - https://docs.anthropic.com/en/docs/claude-code/hooks
  - https://docs.anthropic.com/en/docs/claude-code/security
- Codex：
  - https://developers.openai.com/codex
  - https://openai.com/index/introducing-codex/
  - https://github.com/openai/codex

