# a3s-first 安全监督框架架构设计（冻结归档输入）

> 日期：2026-03-09  
> 状态：归档输入文档（R5）；规范源为 `04-a3s-phase1-detailed-design.md`（`v1.4-frozen`）

---

## 1. 设计目标（实现导向）

先在 `a3s-code` 上落地一个轻量但闭环的运行时安全监督内核，具备：

1. 运行时检测：对 prompt、工具调用、工具输出进行在线风险判断。
2. 轨迹建模：将流式事件归并为可分析的 trace/step/path。
3. 风险定位：给出具体 step/span/path 级定位结果。
4. 风险溯源：产出可追溯证据链（触发点、传播路径、响应动作）。

阶段边界说明：

1. `Phase 1`：只读监督（产生决策建议，不执行硬阻断）。
2. `Phase 2`：主动防护（`P2-A` 先执行 `EXTERNAL_APPROVAL`，`P2-B` 再执行 `BLOCK`）。

非目标（本阶段不做）：

1. 不追求跨框架同日实现。
2. 不先做复杂模型推理器（默认规则+统计优先）。

---

## 2. 逻辑架构

```text
A3S Runtime
  ├─ stream events
  ├─ hooks
  ├─ lane external approval
  └─ orchestrator (optional)
        │
        ▼
A3S Adapter
  ├─ event_ingest
  ├─ hook_gateway
  └─ lane_bridge
        │
        ▼
Supervision Kernel
  ├─ Event Normalizer
  ├─ Trace Builder
  ├─ Rule Detector
  ├─ Risk Scorer
  ├─ Locator (step/span/path)
  ├─ Response Engine (allow/alert/recommend_block/recommend_external_approval)
  └─ Provenance Recorder
        │
        ▼
Storage + Query
  ├─ event log
  ├─ trace store
  ├─ findings
  └─ audit export
```

---

## 3. 核心模块与职责

### 3.1 `A3SAdapter`

职责：把 a3s 原生事件和 hook 回调统一转换为内核输入。

输入：

- `session.stream()` 事件流
- hook 触发（`pre_tool_use`、`post_tool_use`、`pre_prompt`、`post_response`、`on_error`）
- lane external 任务状态

输出：

- 统一 `EventRecord`（见第 4 节）
- 风险动作建议 `GateRecommendation`（Phase 1）
- 动作闸门请求 `GateRequest`（Phase 2）

### 3.2 `TraceBuilder`

职责：从离散事件构建运行轨迹。

关键逻辑：

1. 按 `session_id + turn_id` 聚合。
2. 将工具调用映射为 `TOOL_CALL`/`TOOL_RESULT` 成对 step。
3. 维护 parent-child 依赖（prompt -> tool -> response）。

### 3.3 `RuleDetector`

职责：低延迟规则判定（默认开启）。

首批规则建议：

1. 命令类：危险命令、越权命令、疑似下载执行链。
2. 文件类：敏感路径写入、路径穿越模式。
3. 输入类：prompt 注入关键模式。
4. 输出类：敏感信息外泄模式。

### 3.4 `RiskScorer`

职责：将多条证据合成为可排序风险分值。

建议公式（首版可简化）：

`score = w_rule * rule_score + w_context * context_score + w_history * history_score`

其中：

- `rule_score`：规则命中严重度。
- `context_score`：上下文风险（目标资产、权限级别、执行环境）。
- `history_score`：历史复发/关联风险。

### 3.5 `ResponseEngine`

职责：根据策略执行响应。

响应类型：

1. `ALLOW`：放行并记录。
2. `ALERT`：告警但不阻断。
3. `RECOMMEND_BLOCK`：建议阻断（Phase 1）。
4. `RECOMMEND_EXTERNAL_APPROVAL`：建议外部审批（Phase 1）。

Phase 2 升级后（分段）：

1. `P2-A`：先启用 `EXTERNAL_APPROVAL`（lane external）审批闸门。
2. `P2-B`：在 `P2-A` 稳定后启用 `BLOCK`（pre_tool_use）阻断。

实现说明：动作枚举、审批状态机、执行态决策矩阵与门禁指标以 `04-a3s-phase1-detailed-design.md`（R4 及后续冻结版）为准。

### 3.6 `ProvenanceRecorder`

职责：记录“发现 -> 定位 -> 响应”的可审计链。

最小输出字段：

- `finding_id`
- `trace_id`
- `root_step`
- `evidence_refs`
- `decision`
- `operator_or_policy`
- `timestamp`

---

## 4. 数据模型（Phase 1 最小集）

### 4.1 `EventRecord`

- `event_id`
- `framework` (fixed=`a3s`)
- `session_id`
- `turn_id`
- `event_type_raw`
- `event_type_norm`
- `ts`
- `payload`

### 4.2 `TraceStep`

- `trace_id`
- `step_id`
- `parent_step_id`
- `kind`
- `input_ref`
- `output_ref`
- `status`
- `latency_ms`

### 4.3 `RiskFinding`

- `finding_id`
- `trace_id`
- `severity`
- `category`
- `location_type` (`step|span|path`)
- `location_id`
- `score`
- `decision`
- `explanation`

---

## 5. 运行流程（a3s 实现序列）

1. 启动 session，注册 hooks。
2. 接收流式事件，持续写入 `EventRecord`。
3. 在关键节点触发 `RuleDetector`（pre-tool / pre-prompt / post-response）。
4. 若风险达到阈值：
   - 高危：`RECOMMEND_BLOCK` 或 `RECOMMEND_EXTERNAL_APPROVAL`（Phase 1）
   - 中危：`ALERT`
5. turn 结束后更新 trace、生成 finding、输出 provenance。

---

## 6. 轻量化与稳定性策略

1. 检测优先同步规则，不默认调用重模型。
2. 审计落盘异步化，主链路只保留必要字段。
3. 每轮只计算增量轨迹，不全量重建。
4. 所有外部审批设置超时与默认动作（fail-safe）。

---

## 7. Phase 1 验收门禁（必须满足）

1. 能在 a3s 中稳定捕获关键事件并重建基本轨迹。
2. 至少 4 类风险规则可触发并给出定位结果。
3. `allow/alert/recommend_*` 响应可跑通；建议动作均有证据链记录。
4. 能输出完整证据链 JSON（finding -> evidence -> decision）。

Phase 2 门禁（另行验收）：

1. `P2-A`：审批链路在真实 API 下可稳定通过/拒绝/超时/系统错误，且 fail-safe 默认动作通过异常场景验证。
2. `P2-B`：`BLOCK` 执行不破坏主流程稳定性，并在 critical 样本上达到阻断准确率目标。

未达以上门禁，不进入后续框架工程兼容。

---

## 8. 与后续兼容的接口预留

在不影响 a3s 首先落地的前提下，预留以下扩展点：

1. `Adapter.capabilities()`
2. `Adapter.normalize_event()`
3. `Kernel.degrade_by_capability()`

即：先实现 a3s，后续框架通过适配器接入并自动降级能力，而不是改写内核。

---

## 9. 修订记录（2026-03-09 R3）

1. 统一响应术语：`recommend_approve` 更正为 `recommend_external_approval`。
2. 将 Phase 2 路线明确为 `P2-A`（审批执行化）-> `P2-B`（阻断执行化）。
