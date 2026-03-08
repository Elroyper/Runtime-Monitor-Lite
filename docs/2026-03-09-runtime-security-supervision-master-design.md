# Runtime Monitor Lite 参考资料索引与安全监督框架总体设计（v0.3-frozen）

> 日期：2026-03-09  
> 状态：`Frozen（R5）`  
> 冻结版本：`v0.3-frozen`  
> 冻结日期：`2026-03-09`  
> 目标：为后续开发提供统一的“资料地图 + 总体设计基线”，先从 `a3s-code` 兼容落地，再演进到框架无关，并逐步兼容 `openclaw`、`ag2/langgraph`、`claude code`、`codex`。

---

## 1. 文档目的与边界

本文件承担两件事：

1. 整理当前仓库内已有参考资料，明确每份材料在后续开发中的作用。
2. 基于现有材料给出可执行的总体设计，覆盖你提出的核心目标：  
   `框架无关（理想目标）`、`轻度`、`运行时安全监督`、`轨迹分析`、`风险定位`、`风险溯源`。

本版不直接进入代码实现细节（接口定义、模块 skeleton、测试用例会在下一阶段文档或实现任务中展开），但会给出可落地的架构与里程碑。

---

## 2. 仓库参考资料总览

### 2.1 核心文档资产

| 路径 | 内容定位 | 对本项目的直接价值 | 使用优先级 |
|---|---|---|---|
| `A3S_CODE_GUIDE.md` | `a3s-code==1.1.0` 的实测型指南，覆盖 Session、Event、Hook、Lane Queue、Orchestrator，并含第 22 节安全监督插件草案 | 是当前“先兼容 a3s-code”阶段的主依据；可直接映射到采集点、拦截点、审批点、编排点 | 最高 |
| `MAS_Observability_Key_Papers_Summary.md` | 4 篇关键论文的结构化解读（LumiMAS / SentinelAgent / AgentOps / TrajAD） | 提供可观测性、图式异常检测、轨迹异常定位、AgentOps 追踪模型的理论锚点 | 高 |
| `MAS安全风险监控轨迹分析Survey.md` | 更宽口径 Survey，覆盖监控、轨迹验证、取证溯源、信任管理、形式化验证等 | 用于扩展中长期路线，尤其是“溯源可信性”“跨组织合规”“协议安全”方向 | 高（中长期） |

### 2.2 原始论文与源材料

| 路径 | 内容定位 | 价值 |
|---|---|---|
| `key_papers_source/LumiMAS.pdf` | LumiMAS 原文 | 框架无关监控层 + 实时检测 + RCA 分层思想 |
| `key_papers_source/SentinelAgent.pdf` | SentinelAgent 原文 | 图结构节点/边/路径级风险检测与告警分级 |
| `key_papers_source/AgentOps.pdf` | AgentOps 原文 | Trace/Span/事件语义规范，可作为通用数据模型参考 |
| `key_papers_source/TrajAD.pdf` | TrajAD 原文 | 轨迹级异常定义与精确步骤定位（支持回滚/重试） |
| `key_papers_source/lumimas.txt` | LumiMAS 文本版（含摘要与章节文本） | 便于快速检索术语与机制，适合作为实现初期的“轻量索引语料” |

### 2.3 实验与验证资产

| 路径 | 内容定位 | 价值 |
|---|---|---|
| `test/test_eventbus.py` | Hook / Lane / Orchestrator 的综合探索脚本 | 能直接作为 PoC 验证入口，复用成本最低 |
| `test/explore_a3s_code.ipynb` | API 探索与事件观察 Notebook | 可复查字段、行为、事件流差异 |
| `test/events_*.json` | 历史对话与工具调用轨迹样本 | 可用于设计“统一事件模型”和早期离线分析 |
| `test/test_events.py` | 流式事件采集并落盘 | 可作为采集层初版模板 |

---

## 3. 从现有材料提炼出的关键设计结论

### 3.1 一致性结论（高置信）

1. 安全监督必须“过程化”，仅看最终输出不够。  
   这与 TrajAD 的轨迹异常观点、AgentOps 的 Trace/Span 追踪思想一致。
2. 仅做单 agent 局部监控会漏检系统级风险。  
   这与 LumiMAS、SentinelAgent 强调的系统级/图级观察一致。
3. 监督框架应分层而不是单点大模型裁判。  
   规则层负责低延迟硬约束，模型层负责高语义判断，溯源层负责证据闭环。
4. `a3s-code v1.1.0` 已具备“可插拔实时监督”的关键技术面。  
   Hook（拦截/观测）、Lane（审批/隔离执行）、Orchestrator（并行分析）三者可形成完整最小闭环。

### 3.2 当前仓库已具备的优势

1. 有实测文档，不是纯理论资料。
2. 有事件样本，可立即做轨迹 schema 设计。
3. 有安全插件雏形（`A3S_CODE_GUIDE.md` 第 22 节），可直接继承再抽象。

### 3.3 当前缺口

1. 缺统一的“框架无关事件模型”（现在仍偏 `a3s` 原生字段）。
2. 缺“风险定位到证据链”的标准输出格式（发现 -> 定位 -> 溯源未完全打通）。
3. 缺分阶段验收指标（误报率、延迟开销、定位精度、回放可重建率等）。

---

## 4. 总体目标与成功标准

### 4.1 目标定义

构建一个“理想上框架无关、现实中先兼容 `a3s-code`”的轻量运行时安全监督框架，实现：

1. 运行时监督：在线观测并按阶段策略响应（Phase 1: `allow/alert/recommend_*`；Phase 2: `external_approval/block` 执行态）。
2. 轨迹分析：将多轮多工具行为重建为可分析轨迹。
3. 风险定位：定位到节点（动作）、边（调用关系）、路径（攻击链）。
4. 风险溯源：给出可追溯证据与因果链，支持复盘。
5. 框架扩展：按 `openclaw -> ag2/langgraph -> claude code -> codex` 的顺序推进兼容。

### 4.2 约束条件

1. 轻度：默认部署不显著影响主流程延迟和稳定性。
2. 增量接入：不要求重写业务 agent。
3. 可迁移：核心能力不绑定单一 SDK 的字段命名和事件枚举。

### 4.3 成功标准（建议作为里程碑验收指标）

1. 监督覆盖率：关键生命周期事件可捕获率 >= 95%（a3s 阶段）。
2. 运行开销：纯规则模式平均额外延迟控制在可接受范围（建议 < 10%-15%）。
3. 定位质量：高危事件能定位到具体工具调用与输入上下文。
4. 溯源可用性：一次风险可还原“触发点 -> 传播路径 -> 响应动作”完整链路。

---

## 5. 方案探索与取舍记录

### 5.1 路线 A：规则优先（最轻）

- 核心：以事件匹配和策略规则引擎为主，不引入重模型。
- 优点：延迟低、可解释性强、工程落地快。
- 缺点：对语义攻击、跨步隐蔽风险识别能力有限。

### 5.2 路线 B：模型优先（最强语义）

- 核心：大量依赖 LLM/Judge 或专门检测模型进行在线判定。
- 优点：语义识别上限高，适合复杂注入与多跳共谋。
- 缺点：成本高、延迟高、稳定性和可重复性风险更大。

### 5.3 路线 C：分层混合（推荐）

- 核心：规则层兜底 + 轨迹统计层 + 可选模型层，按风险等级逐级升级判定。
- 优点：在性能、可解释性、检测上限之间平衡最好；适配“先 a3s、后框架无关”。
- 缺点：架构设计稍复杂，需要清晰模块边界。

### 5.4 结论

推荐路线 C。  
原因：它最符合“轻度可落地”与“中长期可扩展”双目标，且能直接继承当前 `a3s-code` 的 Hook/Lane/Orchestrator 能力。

---

## 6. 推荐总体架构（v0.3）

```text
Framework Adapter Layer
  ├─ A3S Adapter (first)
  └─ Future Adapters (LangGraph/CrewAI/AutoGen/...)
          │
          ▼
Core Supervision Kernel
  ├─ Event Normalizer
  ├─ Trace Builder (node/edge/path)
  ├─ Risk Engine
  │    ├─ Rule Detector (default on)
  │    ├─ Statistical Detector (optional)
  │    └─ Model Verifier (optional)
  ├─ Risk Locator (step / span / path)
  ├─ Provenance Recorder (evidence chain)
  └─ Response Orchestrator (allow / alert / recommend_* / external_approval / block)
          │
          ▼
Storage & API
  ├─ Audit Log
  ├─ Trace Store
  ├─ Risk Findings
  └─ Query/Export API
```

### 6.1 a3s-code 兼容映射（第一阶段）

| a3s 机制 | 对应内核能力 | 说明 |
|---|---|---|
| `pre_tool_use` | 运行前风险评估 | Phase 1 仅记录建议；Phase 2-B 才执行阻断 |
| `post_tool_use` | 执行后证据补全 | 记录输出、退出码、副作用 |
| `pre_prompt` / `post_response` | 输入/输出语义检查 | 注入检测、敏感外泄检测 |
| `tool_input_delta` | 细粒度轨迹片段 | 构建更精细的 step 级轨迹 |
| `Lane external` | 人机或外部策略审批闸门 | 高风险操作转外部决策 |
| `Orchestrator` | 并行分析/解释 worker | 异常解释、RCA、策略建议 |

说明：Phase 语义、审批状态机、量化门禁与审计 schema 的规范性定义以 `docs/exploration/2026-03-09-framework-design/04-a3s-phase1-detailed-design.md`（`v1.4-frozen`）为准。

### 6.2 框架无关抽象接口（内核视角）

建议定义最小适配接口（概念层）：

1. `capture_event()`：接收原生运行时事件。
2. `normalize_event()`：映射到统一事件模型。
3. `request_action_gate()`：对高风险动作发起阻断/审批。
4. `emit_observation()`：将风险结果与证据写出。
5. `capabilities()`：声明适配器支持的能力（是否可阻断、是否有 tool 输入流等）。

### 6.3 目标兼容框架与难度梯度（新增）

核心判断：未来兼容难度将逐步增加，主要因为“可用权限/可见性/可控性”逐步下降。

| 目标框架 | 预估权限水平 | 主要可用能力 | 主要缺口 | 预估难度 |
|---|---|---|---|---|
| `openclaw` | 相对高 | 通常可在执行链路中接入拦截与审计点 | 生态标准化程度可能不足 | 中 |
| `ag2/langgraph` | 中等 | 可通过 agent/node/callback 层采集轨迹 | 对底层工具执行的硬拦截能力取决于封装方式 | 中高 |
| `claude code` | 较低 | 可观测流式事件、有限审批与外部策略配合 | 深层内部状态和执行器控制权有限 | 高 |
| `codex` | 较低/更受限 | 可观测会话与工具事件，便于审计回放 | 框架内细粒度策略注入空间更小，更多依赖外部执行环境 | 高+ |

### 6.4 按权限差异的架构调整策略（新增）

1. 高权限框架（如 `openclaw`）：  
   优先采用“内联拦截 + 同步决策”，实现强实时阻断。
2. 中权限框架（如 `ag2/langgraph`）：  
   优先采用“执行器包装 + 回调采集 + 关键节点闸门”，在节点边界实施策略。
3. 低权限框架（如 `claude code`、`codex`）：  
   优先采用“旁路监督 + 环境级约束 + 审计回放”，以检测、告警、溯源为主，阻断能力更多依赖外部执行环境（沙箱、权限最小化、命令白名单）。
4. 统一策略：  
   所有适配器必须先输出 `capabilities()`，由内核自动降级功能，避免在低权限框架中假设不存在的控制能力。

---

## 7. 统一数据模型（建议）

### 7.1 `EventRecord`

- `event_id`
- `timestamp`
- `framework`（如 `a3s`）
- `session_id`
- `turn_id`
- `actor`（agent/tool/user/system）
- `event_type`（normalized）
- `payload_raw`
- `payload_normalized`

### 7.2 `TraceStep`

- `trace_id`
- `step_id`
- `parent_step_id`
- `kind`（prompt/tool_call/tool_output/model_response/...）
- `inputs`
- `outputs`
- `status`
- `latency_ms`

### 7.3 `RiskFinding`

- `finding_id`
- `trace_id`
- `severity`（low/medium/high/critical）
- `category`（injection/leakage/privilege/path/...）
- `location`（step/span/path）
- `confidence`
- `explanation`
- `evidence_refs`
- `recommended_action`

### 7.4 `ProvenanceChain`

- `chain_id`
- `root_cause_step`
- `propagation_path`
- `affected_assets`
- `mitigation_actions`
- `verification_status`

### 7.5 `RuleHitRecord`（R3 对齐）

- `rule_hit_id`
- `finding_id`
- `rule_id`
- `severity`
- `confidence_base`
- `evidence`

### 7.6 `GateDecisionRecord`（R3 对齐）

- `gate_decision_id`
- `finding_id`
- `provenance_chain_id`
- `enforcement_mode`
- `primary_action`
- `approval_state`
- `decision_result`

### 7.7 跨表主键约束（R4 对齐）

1. `RiskFinding.rule_hit_refs` 必须可在 `RuleHitRecord.rule_hit_id` 命中。
2. `ProvenanceChain.gate_decision_id` 必须可在 `GateDecisionRecord.gate_decision_id` 命中。
3. `GateDecisionRecord.provenance_chain_id` 必须可在 `ProvenanceChain.chain_id` 命中。
4. 同一 `finding_id` 的多次决策必须使用 `decision_attempt` 递增编号。

---

## 8. 关键流程设计

### 8.1 在线监督主流程

1. 采集：Adapter 接收运行时事件。
2. 规范化：转统一事件模型并关联 session/turn。
3. 建轨迹：Trace Builder 构建 step 与依赖关系。
4. 检测：Risk Engine 执行规则/统计/模型判定。
5. 定位：Risk Locator 给出节点/边/路径级定位结果。
6. 响应：Response Orchestrator 按 `enforcement_mode` 处理（Phase 1 只输出建议；Phase 2-A 执行审批；Phase 2-B 执行阻断+审批协同）。
7. 溯源：Provenance Recorder 形成证据链并持久化。

### 8.2 轻量化策略

1. 默认只启用规则层和基础统计层。
2. 模型验证器仅在高风险或不确定场景触发（按阈值升级）。
3. 审计写入采用异步化，避免阻塞主业务路径。

---

## 9. 分阶段实施路线

### Phase 0（当前基线整理）

- 完成资料索引与总体设计（即本文档）。
- 固化术语与目标指标，建立统一词汇表。

### Phase 1（a3s 只读监督 MVP）

- 基于 Hook/Stream 建立事件采集与统一模型映射。
- 实现只读风险检测（不阻断），输出 `allow/alert/recommend_*` 与证据日志。
- external approval 仅影子链路验证，不影响主执行。
- 可用 `test/events_*.json` 做离线回放验证。

### Phase 2-A（a3s 主动防护：审批执行化）

- 接入 Lane external 审批闸门并启用执行。
- 固化审批 `timed_out/system_error` fail-safe 默认动作并完成真实 API 验证。
- 保持 `BLOCK` 为建议态，先验证审批路径稳定性。
- 具体进入与发布门禁以 `04` 的 `Gate-A/Gate-B` 为准（避免在总纲中重复定义阈值）。

### Phase 2-B（a3s 主动防护：阻断执行化）

- 在 Phase 2-A 达标后启用 `pre_tool_use` 阻断执行。
- 验证 `critical` 场景阻断准确率与主流程稳定性。
- 与审批路径协同形成执行态闭环。
- 发布门禁以 `04` 的 `Gate-C` 为准。

### Phase 3（轨迹分析与定位增强）

- 引入路径级风险定位（节点/边/路径）。
- 增加 RCA 解释结果（可先规则模板化，再模型增强）。
- 支持“单次事件 -> 全链路复盘”。

### Phase 4（框架无关演进）

- 抽象并固化 Adapter SDK。
- 按难度阶梯扩展适配器：`openclaw`（先）-> `ag2/langgraph` -> `claude code` -> `codex`（后）。
- 沉淀跨框架一致的风险 schema 与查询接口。

---

## 10. 风险与应对

1. 误报过高导致不可用。  
   应对：默认只读模式灰度上线，阈值分层，人工反馈闭环。
2. 开销过大影响主流程。  
   应对：检测分级触发、异步写入、模型调用配额化。
3. 框架抽象过早导致实现空转。  
   应对：坚持“a3s 先跑通，再抽象泛化”，以第二适配器做真实性验证。
4. 溯源记录不完整。  
   应对：先强制最小证据字段，再逐步扩展证据类型。
5. 低权限框架无法实现同等级阻断能力。  
   应对：采用能力分级与功能降级策略；把“强阻断”从框架内能力迁移到外部环境控制（执行沙箱、系统权限、网络策略）并在文档中明确能力边界。

---

## 11. 冻结后下一步建议（进入实现前）

1. 严格按 `04(v1.4-frozen)` 的 `Gate-A/Gate-B/Gate-C` 推进实现与验收。
2. 用真实 API 执行 `S1-S12`，并沉淀 `validation_report.md` 与 `metrics_summary.json`。
3. 若变更动作枚举、状态机或门禁阈值，必须先更新 `04` 冻结文档并记录 DR。
4. 在 a3s 实现完成前，其他框架保持“设计与能力核验”状态，不进入主线编码。
5. 实现协作建议使用远程仓库 `git@github.com:Elroyper/Runtime-Monitor-Lite.git`（已完成连通与写权限 dry-run 验证），保持“小步提交、当日推送、验证与代码同提交”的 Git 习惯。

---

## 12. a3s-first 执行约束（新增）

1. 先兼容并跑通 `a3s-code` 的监督闭环（检测、定位、溯源、响应）后，再进入其他框架工程实现。  
2. `openclaw`、`ag2/langgraph`、`claude code`、`codex` 当前阶段只做设计与能力核验，不分流主线实现资源。  
3. 若 `a3s` 阶段验收指标未达标（覆盖率、开销、定位质量、溯源可用性），后续兼容阶段自动延后。

---

## 13. 中间探索文档索引（新增）

中间文档统一存放于 `docs/exploration/2026-03-09-framework-design/`：

1. `00-current-progress-note.md`：当前进度说明与下一步复核重点。
2. `01-framework-capability-research.md`：多框架能力调研记录与来源。
3. `02-a3s-first-architecture-design.md`：a3s 优先落地的架构归档输入文档。
4. `03-capability-matrix-and-roadmap.md`：能力矩阵、降级策略与分期路线。
5. `04-a3s-phase1-detailed-design.md`：基于第 2 份文档展开的 Phase 1 冻结规范文档。

---

## 14. 附：本次探索结论摘要

1. 你要的目标是可行的，且仓库现有资料足以支撑第一阶段落地。  
2. 最优路径不是“纯规则”或“纯模型”，而是“分层混合、按风险升级判定”。  
3. `a3s-code` 已提供关键插桩面，可在不大改业务逻辑的情况下构建运行时监督闭环。  
4. 下一阶段重点不在“再找论文”，而在“统一模型与接口先定，再快速做 MVP 验证”。

---

## 15. 复核决策日志（2026-03-09 R1-R5）

1. `DR-20260309-01`：Phase 1 固化为只读监督（observe-only），不执行硬阻断。  
2. `DR-20260309-02`：external approval 在 Phase 1 仅做影子链路验证，不作为生产门禁。  
3. `DR-20260309-03`：主动防护（Phase 2）以量化门禁触发，不按固定日程触发。  
4. `DR-20260309-04`：Phase 1 验证改为“可执行检查清单”驱动，强制记录场景阈值与失败回流。  
5. `2026-03-09 R3`：Phase 2 执行路线细化为 `Phase 2-A`（审批执行化）-> `Phase 2-B`（阻断执行化）。  
6. `2026-03-09 R3`：补充动作枚举、审批状态机、量化指标执行规约与结构化审计产物。  
7. `2026-03-09 R4`：补充 Phase 2-A/2-B 可执行检查清单与 fail-safe 可验证口径（`timed_out/system_error`）。  
8. `2026-03-09 R4`：明确跨表审计键（`rule_hit_refs`、`gate_decision_id`、`provenance_chain_id`、`decision_attempt`）与阶段语义对照。  
9. `2026-03-09 R5`：修复阶段门禁循环定义，拆分 `Gate-A/Gate-B/Gate-C`，区分灰度启用与发布门禁。  
10. `2026-03-09 R5`：完成 `04(v1.4-frozen)` 与 `master(v0.3-frozen)` 冻结，并补齐 `Phase 1 system_error` 真值与 `ApprovalEventRecord` 约束。  
11. 关联文档：`00-current-progress-note.md`、`02-a3s-first-architecture-design.md`、`03-capability-matrix-and-roadmap.md`、`04-a3s-phase1-detailed-design.md`。
