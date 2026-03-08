# a3s Phase 1 详细设计文档（MVP，v1.4-frozen）

> 日期：2026-03-09  
> 状态：`Frozen（R5）`  
> 冻结版本：`v1.4-frozen`  
> 冻结日期：`2026-03-09`  
> 冻结说明：完成 R5 阻断项修复，作为 Phase 1/2 规范源文档。  
> 基础文档：`02-a3s-first-architecture-design.md`  
> 目标：将 a3s-first 架构细化为可执行实现设计，供多轮复核。  
> 本版定位：`Phase 1 = 只读监督（observe-only）`，主动防护（审批/阻断执行）延后到 Phase 2。

---

## 0. 项目执行原则（强制写入）

本项目所有功能严格遵循以下流程：

`调研 -> 设计文档 -> 循环复核修改 -> 逐步代码实现 -> 每步实现都进行基于真实 API 的验证`

执行要求：

1. 未完成本轮设计复核，不进入对应代码实现。
2. 每个实现步骤必须有对应真实 API 验证记录（通过/失败与原因）。
3. 验证失败时先回到“设计与假设修正”，再继续开发。

---

## 1. Phase 1 范围定义

### 1.1 目标（必须达成）

1. 完成 a3s 事件采集与统一事件模型落地。
2. 完成规则检测与风险评分（轻量版）。
3. 完成只读响应闭环：`allow / alert / recommend_block / recommend_external_approval`（仅建议，不执行阻断）。
4. 完成轨迹构建与风险定位（step/span/path 最小可用）。
5. 完成证据链输出（可回放可审计）。

### 1.2 非目标（本阶段不做）

1. 不实现跨框架工程适配。
2. 不引入重模型推理器作为默认检测路径。
3. 不追求最终 UI，仅输出结构化结果。
4. 不在主执行链启用硬阻断（hard block）。
5. 不把 external approval 作为生产门禁动作执行（只做影子链路验证）。

### 1.3 进入 Phase 2-A（主动防护：审批执行灰度）的启用门禁（Gate-A）

1. 只读监督验证通过：关键事件捕获率 >= 95%。
2. 证据链回放成功率 >= 95%（抽样集）。
3. 纯规则模式额外开销 P95 <= 15%。
4. 风险定位抽样准确率 >= 85%（step/span/path）。
5. 完成审批链路影子演练并确认超时/系统错误默认动作（fail-safe）。
6. `S1-S7` 全部通过（其中 `S6/S6B` 必须覆盖 `timed_out/system_error`）。

`Gate-B`（Phase 2-A 达标并进入 Phase 2-B 灰度）与 `Gate-C`（Phase 2-B 发布）见第 9 节。

---

## 2. 总体技术方案（a3s-only）

```text
a3s Session Stream + Hook + Lane
           │
           ▼
[A3S Ingest Adapter]
  - stream_ingest
  - hook_ingest
  - lane_ingest
           │
           ▼
[Core Kernel]
  - event_normalizer
  - trace_builder
  - rule_engine
  - risk_scorer
  - response_engine
  - provenance_recorder
           │
           ▼
[Storage]
  - events.jsonl
  - traces.jsonl
  - findings.jsonl
  - rule_hits.jsonl
  - approval_events.jsonl
  - gate_decisions.jsonl
  - provenance.jsonl
```

原则：先保证“稳定跑通 + 可复盘”，再做“更强检测能力”。

---

## 3. 模块设计（实现粒度）

### 3.1 `a3s_adapter`

职责：采集与转换。

输入源：

1. `session.stream(prompt)` 事件流。
2. `register_hook` 回调触发事件。
3. `pending_external_tasks` 与 `complete_external_task` 状态事件。

输出：

1. 统一 `EventRecord`。
2. 在 observe-only 模式输出 `GateRecommendation`（建议动作，不执行）。

错误策略：

1. 采集失败不影响主流程时，降级为警告并记录。
2. 关键字段缺失时，标记 `event_quality=partial` 并继续。

### 3.2 `event_normalizer`

职责：将 a3s 原生字段映射为统一语义。

核心映射示例：

1. `pre_tool_use` -> `TOOL_PRECHECK`
2. `tool_start` -> `TOOL_EXEC_START`
3. `tool_end` -> `TOOL_EXEC_END`
4. `post_response` -> `MODEL_RESPONSE`
5. `on_error` -> `RUNTIME_ERROR`
6. `session_start/start` -> `SESSION_START`
7. `turn_start` -> `TURN_START`
8. `turn_end` -> `TURN_END`
9. `session_end/end` -> `SESSION_END`
10. `external_task_pending` -> `EXTERNAL_TASK_PENDING`
11. `external_task_completed` -> `EXTERNAL_TASK_COMPLETED`
12. `confirmation_timeout` -> `CONFIRMATION_TIMEOUT`

输出要求：

1. 所有事件必须有 `session_id`、`turn_id`、`ts`。
2. 无法映射事件统一落入 `UNKNOWN_RAW_EVENT`，不得丢弃。

### 3.3 `trace_builder`

职责：将离散事件归并为可分析轨迹。

构建规则：

1. `session_id + turn_id` 作为主分组。
2. 工具事件按 `tool_id` 关联 start/end。
3. 对同 turn 的 prompt、tool、response 建立 parent-child。

产出：

1. `Trace`
2. `TraceStep`
3. `TraceEdge`

### 3.4 `rule_engine`

职责：低延迟规则检测。

规则包（首版）：

1. 命令风险：`rm -rf`, `sudo`, `curl|wget` 与执行链组合。
2. 路径风险：`/etc/*`, `../` 穿越模式，敏感写操作。
3. 注入风险：典型 prompt injection 模式词与结构信号。
4. 外泄风险：密钥、token、证书等模式匹配。

确定性破坏规则（`deterministic_destructive`）标记约定：

1. 必须以 `rule_tags` 标记可前置阻断的规则：`rule_tags: ["deterministic_destructive"]`。
2. 仅当命中该标签且风险为 `critical` 时，Phase 1 可升级为 `RECOMMEND_BLOCK`，Phase 2-B 可执行 `BLOCK`。
3. 首版最小清单：`CMD_RM_RF_001`、`CMD_PRIV_ESC_001`、`CMD_DOWNLOAD_EXEC_001`（后续扩展需更新策略版本与变更记录）。

规则输出：

- `RuleHit{rule_hit_id, rule_id, severity, evidence, confidence_base, policy_version}`

### 3.5 `risk_scorer`

职责：合成风险等级。

输入：规则命中 + 上下文因素。

评分公式（v1，固定）：

`score = 0.6 * rule_score + 0.3 * context_score + 0.1 * history_score`

聚合规则（v1）：

1. 同一 finding 的 `rule_score` 取命中规则的加权和（上限 1.0）。
2. 若出现 `critical` 规则命中，最终 `score` 下限提升到 `0.85`。
3. 若多条规则冲突，按 `action_priority` 选择主动作，并写入 `alternative_actions`。

评分执行规约（v1 固化，保证可复现）：

1. `rule_score = min(1.0, Σ(rule_weight * confidence_base * severity_factor))`。其中 `severity_factor` 固定：`critical=1.0`、`high=0.75`、`medium=0.5`、`low=0.25`。
2. `context_score` 固定由四个子项加权：`target_asset(0.35) + privilege_level(0.25) + network_egress(0.20) + write_scope(0.20)`；缺失项按 `0` 处理并在 `explanation` 标记。
3. `history_score` 固定使用“同 `session_id` 最近 24h 同类规则复发率”，公式：`history_score = min(1.0, repeat_count / 5)`。
4. 并列冲突的 tie-break 顺序固定为：`action_priority` -> `max(rule_weight)` -> `min(rule_hit_id lexicographic)`。
5. 每次计算必须产出 `score_components={rule_score, context_score, history_score}` 并写入 `findings.jsonl`。

建议阈值（初版可配置）：

1. `score >= 0.85` => `critical`
2. `0.65 <= score < 0.85` => `high`
3. `0.40 <= score < 0.65` => `medium`
4. `< 0.40` => `low`

### 3.6 `response_engine`

职责：将风险转成动作。

动作枚举（全阶段统一）：

1. `ALLOW`
2. `ALERT`
3. `RECOMMEND_BLOCK`
4. `RECOMMEND_EXTERNAL_APPROVAL`
5. `BLOCK`（Phase 2 执行态）
6. `EXTERNAL_APPROVAL`（Phase 2 执行态）

执行模式（`enforcement_mode`）：

1. `observe_only`（Phase 1，默认）
2. `enforce_approval`（Phase 2-A，先启用审批门禁）
3. `enforce_block`（Phase 2-B，再启用硬阻断）

动作命名标准化（实现与审计统一）：

1. 存储层统一使用大写枚举：`ALLOW/ALERT/RECOMMEND_BLOCK/RECOMMEND_EXTERNAL_APPROVAL/BLOCK/EXTERNAL_APPROVAL`。
2. 配置层使用小写枚举：`allow/alert/recommend_block/recommend_external_approval/block/external_approval`。
3. 必须通过 `ActionCanonicalization` 映射转换，禁止直接字符串比较。

决策矩阵（Phase 1，observe-only）：

1. `critical` -> 默认 `RECOMMEND_EXTERNAL_APPROVAL`；命中确定性破坏规则时可升级 `RECOMMEND_BLOCK`
2. `high` -> 默认 `RECOMMEND_EXTERNAL_APPROVAL`
3. `medium` -> `ALERT`
4. `low` -> `ALLOW` + audit

决策矩阵（Phase 2-A，`enforce_approval`）：

1. `critical/high`：
   - `approved` -> `ALLOW`，`decision_result=executed_approval_approved`
   - `rejected` -> `EXTERNAL_APPROVAL`（拒绝），`final_action_executed=deny`，`decision_result=executed_approval_rejected`
   - `timed_out` -> `EXTERNAL_APPROVAL`（fail-safe deny），`final_action_executed=deny`，`decision_result=executed_approval_timeout_deny`
   - `system_error` -> `EXTERNAL_APPROVAL`（fail-safe deny），`final_action_executed=deny`，`decision_result=executed_approval_system_error_deny`
2. `medium/low`：
   - `approved` -> `ALLOW`，`decision_result=executed_approval_approved`
   - `rejected` -> `ALERT + ALLOW`，`final_action_executed=alert_allow`，`decision_result=executed_approval_rejected_alert_allow`
   - `timed_out` -> `ALERT + ALLOW`，`final_action_executed=alert_allow`，`decision_result=executed_approval_timeout_alert_allow`
   - `system_error` -> `ALERT + ALLOW`，`final_action_executed=alert_allow`，`decision_result=executed_approval_system_error_alert_allow`

决策矩阵（Phase 2-B，`enforce_block`）：

1. `critical` 且命中确定性破坏规则 -> 直接 `BLOCK`，`decision_result=executed_block`（不进入 external approval）。
2. `high` -> 默认走 `EXTERNAL_APPROVAL`（与 Phase 2-A 同 fail-safe 规则）。
3. `medium` -> `ALERT`，必要时可升级审批（策略可配）。
4. `low` -> `ALLOW` + audit。

与 a3s 对接：

1. Phase 1：不执行 `pre_tool_use` 阻断，不执行 `lane external` 审批门禁；仅记录推荐动作与证据链。
2. Phase 2-A：开启 `EXTERNAL_APPROVAL`（lane external）执行链路，`BLOCK` 仍保持建议态。
3. Phase 2-B：在 Phase 2-A 稳定后开启 `BLOCK`（pre_tool_use）执行链路。

审批状态机（统一）：

1. 状态流：`pending -> approved/rejected/timed_out/system_error`。
2. Phase 1（`observe_only`，仅影子审批）：
   - `approved/rejected`：`decision_result=recorded_only`，`final_action_executed=none`
   - `timed_out`：`decision_result=recorded_only` + `timeout_action_phase1=alert`
   - `system_error`：`decision_result=recorded_only` + `system_error_action_phase1=alert`
3. Phase 2-A（`enforce_approval`）：
   - `critical/high`：`approved -> allow`，`rejected/timed_out/system_error -> deny`
   - `medium/low`：`approved -> allow`，`rejected/timed_out/system_error -> alert_allow`
4. Phase 2-B（`enforce_block`）：审批状态机沿用 Phase 2-A；仅在 `critical` 确定性破坏规则时前置短路为 `BLOCK`。
5. 所有状态迁移必须写入 `GateDecisionRecord` 与 `ProvenanceChain`，并记录 `decision_attempt`。

### 3.7 `provenance_recorder`

职责：固化可审计证据链。

最小记录：

1. 触发事件（event id / raw payload）
2. 规则命中（rule hit refs）
3. 风险评分
4. 决策动作
5. 执行模式（`enforcement_mode`）
6. 执行后动作（`final_action_executed`，如 `allow/alert_allow/deny/block`）
7. 决策结果（`recorded_only`/`executed_allow`/`executed_block`/`executed_approval_approved`/`executed_approval_rejected`/`executed_approval_rejected_alert_allow`/`executed_approval_timeout_deny`/`executed_approval_timeout_alert_allow`/`executed_approval_system_error_deny`/`executed_approval_system_error_alert_allow`/`executed_error`）

---

## 4. 数据结构定义（Phase 1 固化版）

### 4.1 EventRecord

```json
{
  "event_id": "evt_xxx",
  "framework": "a3s",
  "session_id": "...",
  "turn_id": 3,
  "event_type_raw": "tool_start",
  "event_type_norm": "TOOL_EXEC_START",
  "ts": "2026-03-09T10:00:00Z",
  "payload": {},
  "event_quality": "full"
}
```

### 4.2 TraceStep

```json
{
  "trace_id": "tr_xxx",
  "step_id": "st_xxx",
  "parent_step_id": "st_parent",
  "kind": "TOOL_CALL",
  "status": "ok",
  "latency_ms": 231,
  "input_ref": "evt_in",
  "output_ref": "evt_out"
}
```

### 4.3 RiskFinding

```json
{
  "finding_id": "fd_xxx",
  "trace_id": "tr_xxx",
  "severity": "high",
  "score": 0.78,
  "category": "command_injection",
  "location_type": "step",
  "location_id": "st_xxx",
  "rule_hit_refs": ["rh_001", "rh_009"],
  "decision": "RECOMMEND_EXTERNAL_APPROVAL",
  "explanation": "matched rule CMD_001 + sensitive context",
  "policy_version": "p1.1.0"
}
```

### 4.4 ProvenanceChain

```json
{
  "chain_id": "pc_xxx",
  "finding_id": "fd_xxx",
  "gate_decision_id": "gd_xxx",
  "decision_attempt": 1,
  "root_event_id": "evt_xxx",
  "evidence_refs": ["evt_a", "evt_b"],
  "decision": "RECOMMEND_BLOCK",
  "enforcement_mode": "observe_only",
  "decision_result": "recorded_only",
  "final_action_executed": "none",
  "run_id": "run_20260309_001",
  "config_hash": "sha256:xxx",
  "artifact_hash": "sha256:yyy"
}
```

### 4.5 GateRecommendation（Phase 1）

```json
{
  "recommendation_id": "gr_xxx",
  "finding_id": "fd_xxx",
  "recommended_action": "RECOMMEND_EXTERNAL_APPROVAL",
  "alternative_actions": ["RECOMMEND_BLOCK"],
  "reason": "critical command + sensitive path",
  "policy_version": "p1.0.0",
  "ts": "2026-03-09T10:00:00Z"
}
```

### 4.6 Trace

```json
{
  "trace_id": "tr_xxx",
  "session_id": "sess_xxx",
  "turn_id": 3,
  "step_ids": ["st_1", "st_2", "st_3"],
  "edge_ids": ["ed_1", "ed_2"],
  "status": "completed"
}
```

### 4.7 TraceEdge

```json
{
  "edge_id": "ed_xxx",
  "trace_id": "tr_xxx",
  "from_step_id": "st_1",
  "to_step_id": "st_2",
  "edge_type": "parent_child",
  "ts": "2026-03-09T10:00:00Z"
}
```

### 4.8 RuleHitRecord

```json
{
  "rule_hit_id": "rh_xxx",
  "finding_id": "fd_xxx",
  "rule_id": "CMD_001",
  "severity": "critical",
  "confidence_base": 0.92,
  "evidence": ["evt_a", "evt_b"],
  "policy_version": "p1.1.0",
  "ts": "2026-03-09T10:00:00Z"
}
```

### 4.9 GateDecisionRecord

```json
{
  "gate_decision_id": "gd_xxx",
  "finding_id": "fd_xxx",
  "provenance_chain_id": "pc_xxx",
  "decision_attempt": 1,
  "enforcement_mode": "observe_only",
  "primary_action": "RECOMMEND_EXTERNAL_APPROVAL",
  "alternative_actions": ["RECOMMEND_BLOCK"],
  "approval_state": "timed_out",
  "decision_result": "recorded_only",
  "final_action_executed": "none",
  "fail_safe_class": "phase1_record_only",
  "timeout_policy": "phase1_alert",
  "ts": "2026-03-09T10:00:00Z"
}
```

### 4.10 TraceSpan（定位支撑）

```json
{
  "span_id": "sp_xxx",
  "trace_id": "tr_xxx",
  "start_step_id": "st_1",
  "end_step_id": "st_3",
  "span_type": "tool_chain",
  "ts_start": "2026-03-09T10:00:00Z",
  "ts_end": "2026-03-09T10:00:03Z"
}
```

### 4.11 TracePath（定位支撑）

```json
{
  "path_id": "pt_xxx",
  "trace_id": "tr_xxx",
  "node_ids": ["st_1", "st_2", "st_3"],
  "edge_ids": ["ed_1", "ed_2"],
  "path_type": "risk_propagation",
  "confidence": 0.88
}
```

### 4.12 `location_id` 与动作映射契约

1. `location_type=step` 时 `location_id` 必须以 `st_` 开头并可在 `TraceStep.step_id` 命中。
2. `location_type=span` 时 `location_id` 必须以 `sp_` 开头并可在 `TraceSpan.span_id` 命中。
3. `location_type=path` 时 `location_id` 必须以 `pt_` 开头并可在 `TracePath.path_id` 命中。
4. `decision` 与 `primary_action` 必须是大写 canonical enum；配置中的小写动作通过 `ActionCanonicalization` 转换。

### 4.13 ApprovalEventRecord（审批事件）

```json
{
  "approval_event_id": "ae_xxx",
  "finding_id": "fd_xxx",
  "gate_decision_id": "gd_xxx",
  "provenance_chain_id": "pc_xxx",
  "decision_attempt": 1,
  "approval_state": "rejected",
  "source": "lane_external",
  "latency_ms": 42000,
  "ts": "2026-03-09T10:00:00Z"
}
```

### 4.14 跨表主键与回放约束（强制）

1. `RiskFinding.rule_hit_refs[*]` 必须命中 `RuleHitRecord.rule_hit_id`。
2. `ProvenanceChain.gate_decision_id` 必须命中 `GateDecisionRecord.gate_decision_id`。
3. `GateDecisionRecord.provenance_chain_id` 与 `ApprovalEventRecord.provenance_chain_id` 必须命中 `ProvenanceChain.chain_id`。
4. 同一 `finding_id` 的多次决策必须使用相同 `decision_attempt` 序列，且 `GateDecisionRecord/ProvenanceChain/ApprovalEventRecord` 三表一致。
5. 回放最小链路：`finding_id -> rule_hit_refs -> gate_decision_id -> provenance_chain_id -> decision_attempt`。

---

## 5. 配置设计

### 5.1 `supervision_config.yaml`（建议）

```yaml
runtime:
  framework: a3s
  mode: observe_only
  enforcement_mode: observe_only

risk:
  threshold:
    critical: 0.85
    high: 0.65
    medium: 0.40

response:
  critical: recommend_external_approval
  critical_escalation: recommend_block
  high: recommend_external_approval
  medium: alert
  low: allow
  action_priority:
    - recommend_block
    - recommend_external_approval
    - alert
    - allow
  enforce_actions: false

approval:
  shadow_mode: true
  timeout_ms: 60000
  timeout_action_phase1: alert
  timeout_action_phase2:
    critical_high: deny
    medium_low: alert_allow
  system_error_action_phase1: alert
  system_error_action_phase2:
    critical_high: deny
    medium_low: alert_allow
  apply_approval_for_medium_low: false

storage:
  base_dir: ./artifacts/runtime_monitor
  format: jsonl
  files:
    - events.jsonl
    - traces.jsonl
    - findings.jsonl
    - rule_hits.jsonl
    - approval_events.jsonl
    - gate_decisions.jsonl
    - provenance.jsonl

validation:
  enable_real_api_check: true
  metrics_spec_version: v1
```

### 5.2 ActionCanonicalization（强制）

| canonical enum（存储） | config enum（配置） | 说明 |
|---|---|---|
| `ALLOW` | `allow` | 低风险放行 |
| `ALERT` | `alert` | 告警不阻断 |
| `RECOMMEND_BLOCK` | `recommend_block` | Phase 1 建议阻断 |
| `RECOMMEND_EXTERNAL_APPROVAL` | `recommend_external_approval` | Phase 1 建议审批 |
| `BLOCK` | `block` | Phase 2-B 执行阻断 |
| `EXTERNAL_APPROVAL` | `external_approval` | Phase 2-A/2-B 执行审批 |

---

## 6. 真实 API 验证计划（每步必做）

### 6.1 验证原则

1. 使用真实 `a3s_code` API（非 mock-only）执行。
2. 每个功能步骤保留验证日志与产物。
3. 失败必须记录并回流到设计修正。

### 6.2 验证场景清单

1. 正常链路：低风险请求应 `ALLOW`。
2. 命令风险：高危命令应触发 `RECOMMEND_BLOCK/RECOMMEND_EXTERNAL_APPROVAL`。
3. 路径风险：敏感路径写入应触发 `ALERT` 或推荐审批。
4. 注入风险：注入样例应触发规则命中。
5. 影子审批链路：external lane 任务可完成通过/拒绝，但不影响主执行。
6. 超时链路：审批超时触发 `timeout_action_phase1` 并完整落审计日志。
7. 回放链路：从 JSONL 可重建单次 finding 的证据链。
8. 执行态审批链路：`critical/high` 审批通过/拒绝必须影响执行结果。
9. 执行态异常链路：`timed_out/system_error` 必须按风险分级触发 fail-safe。
10. 阻断执行链路：`critical` 确定性破坏规则必须前置 `BLOCK`。

### 6.3 验证产物

1. `validation_report.md`
2. `events.jsonl`
3. `traces.jsonl`
4. `findings.jsonl`
5. `rule_hits.jsonl`
6. `approval_events.jsonl`
7. `gate_decisions.jsonl`
8. `provenance.jsonl`
9. `metrics_summary.json`

### 6.4 可执行检查清单（Phase 1 observe-only）

执行要求：每个场景必须填写“输入、期望、通过阈值、产物路径、失败回流项（issue_id）”。

| 场景ID | 输入（真实 API） | 期望结果 | 通过阈值 | 必交产物 | 失败回流项（必填） |
|---|---|---|---|---|---|
| `S1-low-allow` | 正常任务（无危险命令/敏感路径） | 产出 `ALLOW`，无高危命中 | 连续 20 次误报 <= 1 次 | `events.jsonl` + `findings.jsonl` | 误报超阈值：回流规则词表与阈值 |
| `S2-cmd-critical` | `rm -rf` / `sudo` / `curl|wget` 样例 | 产出 `RECOMMEND_EXTERNAL_APPROVAL`（必要时 `RECOMMEND_BLOCK`） | 命中率 >= 95%（20 样本） | `findings.jsonl` + `rule_hits.jsonl` | 漏报样本：回流命令模式与上下文权重 |
| `S3-path-risk` | `/etc/*` 写入与 `../` 穿越样例 | 产出 `ALERT` 或推荐审批 | 命中率 >= 90%（20 样本） | `events.jsonl` + `findings.jsonl` | 误判路径：回流路径规则与正则 |
| `S4-prompt-injection` | 注入模式 prompt 集 | 注入规则命中且有解释字段 | 命中率 >= 85%（20 样本） | `findings.jsonl` + `rule_hits.jsonl` | 漏检注入：回流注入词典与结构特征 |
| `S5-shadow-approval` | lane external 通过/拒绝样例 | 影子审批状态完整记录，不影响主执行 | 通过/拒绝状态记录完整率 100% | `events.jsonl` + `approval_events.jsonl` + `gate_decisions.jsonl` | 状态缺失：回流审批状态映射 |
| `S6-approval-timeout` | 人工不完成审批直到超时 | 触发 `timeout_action_phase1=alert` 并落盘 | 超时行为一致率 100%（10 样本） | 超时日志 + `gate_decisions.jsonl` + `provenance.jsonl` | 超时异常：回流超时策略与状态机 |
| `S6B-approval-system-error` | 注入影子审批系统错误（external 通道异常） | 触发 `system_error_action_phase1=alert` 并落盘 | 系统错误行为一致率 100%（10 样本） | 错误日志 + `gate_decisions.jsonl` + `provenance.jsonl` | 系统错误异常：回流 system_error 策略与状态机 |
| `S7-replay` | 从单次 finding 回放证据链 | 可重建 `finding -> rule_hits -> decision` | 回放成功率 >= 95%（20 样本） | 回放报告 + `provenance.jsonl` | 回放断链：回流 schema 引用关系 |

### 6.4A 可执行检查清单（Phase 2-A/2-B）

执行要求：以下场景仅在 Phase 1 门禁通过后执行，且每次执行必须标记 `enforcement_mode`。

| 场景ID | 适用阶段 | 输入（真实 API） | 期望结果 | 通过阈值 | 必交产物 | 失败回流项（必填） |
|---|---|---|---|---|---|---|
| `S8-approval-enforced` | Phase 2-A | 对 `critical/high` 样例发起真实 external approval | `approved -> allow`；`rejected -> deny`；且两分支均可审计 | `approval_enforcement_accuracy >= 95%`（20 样本）且 `rejected_deny_consistency = 100%`（`critical/high` 拒绝样本 >= 10） | `approval_events.jsonl` + `gate_decisions.jsonl` + `provenance.jsonl` | 状态与结果不一致：回流审批执行映射 |
| `S8B-approval-medium-low` | Phase 2-A | 对 `medium/low` 样例发起审批（策略显式开启） | `approved -> allow`，`rejected -> alert_allow` | 分支覆盖率 100%（每分支 >= 10 样本） | `approval_events.jsonl` + `gate_decisions.jsonl` + `provenance.jsonl` | 状态与策略不一致：回流审批分级策略 |
| `S9-timeout-failsafe` | Phase 2-A | 人工不完成审批直到超时 | `critical/high -> deny`，`medium/low -> alert_allow` | `timeout_failsafe_consistency = 100%`（20 样本） | `approval_events.jsonl` + `gate_decisions.jsonl` | 超时行为漂移：回流 timeout 策略 |
| `S10-system-error-failsafe` | Phase 2-A | 注入审批系统错误（模拟 external 通道不可用） | `critical/high -> deny`，`medium/low -> alert_allow` | `system_error_failsafe_consistency = 100%`（20 样本） | 错误日志 + `gate_decisions.jsonl` + `provenance.jsonl` | 异常退化错误：回流 system_error 策略 |
| `S11-block-accuracy` | Phase 2-B | `critical` 确定性破坏样例 | 命中即 `BLOCK`，不进入审批 | `block_accuracy >= 95%`（20 样本） | `events.jsonl` + `findings.jsonl` + `gate_decisions.jsonl` | 漏断/误断：回流阻断规则边界 |
| `S12-enforcement-stability` | Phase 2-B | 混合业务流（正常+风险） | 执行态不引发致命中断且可恢复 | `stability_error_rate <= 2%`（>=50 样本） | 稳定性报告 + `metrics_summary.json` | 主流程异常：回流执行链异常处理 |

### 6.5 验证报告模板（`validation_report.md`）

```markdown
# Runtime Supervision Validation Report

## 1. 环境信息
- date:
- a3s_code_version:
- config_hash:
- run_id:
- metrics_spec_version:
- random_seed:

## 2. 场景结果
| scenario_id | samples | pass | fail | key_metrics | artifacts |
|---|---:|---:|---:|---|---|

## 3. 量化指标汇总
- event_capture_rate:
- replay_success_rate:
- p95_overhead:
- location_accuracy:
- approval_enforcement_accuracy:
- rejected_deny_consistency:
- timeout_failsafe_consistency:
- system_error_failsafe_consistency:
- block_accuracy:
- stability_error_rate:
- artifacts_hash:

## 4. 失败样本与回流项
- issue_id:
  - symptom:
  - root_cause_hypothesis:
  - design_fix_proposal:

## 5. 结论
- phase1_gate: pass/fail
- phase2a_gate: pass/fail
- phase2b_gate: pass/fail
```

### 6.6 指标口径（统一判定）

1. `event_capture_rate = captured_events / expected_key_events`
2. `replay_success_rate = successful_replays / replay_attempts`
3. `p95_overhead = p95(latency_with_monitor - baseline_latency) / p95(baseline_latency)`
4. `location_accuracy = correct_locations / audited_findings`
5. `approval_enforcement_accuracy = matched_execution_outcomes / total_approval_cases`
6. `timeout_failsafe_consistency = timeout_cases_following_policy / total_timeout_cases`
7. `system_error_failsafe_consistency = error_cases_following_policy / total_system_error_cases`
8. `block_accuracy = correct_block_cases / audited_block_cases`
9. `stability_error_rate = fatal_or_unrecoverable_errors / total_runs`
10. `rejected_deny_consistency = critical_high_rejected_to_deny_cases / critical_high_rejected_cases`

### 6.7 指标执行规约（可审计）

1. 固定 `run_id` 与 `random_seed`，每次验证必须可复现。
2. `expected_key_events` 采用固定 canonical 清单：`SESSION_START/TURN_START/TOOL_EXEC_START/TOOL_EXEC_END/TURN_END/SESSION_END/RUNTIME_ERROR/EXTERNAL_TASK_PENDING/EXTERNAL_TASK_COMPLETED/CONFIRMATION_TIMEOUT`；如底层为 raw 名称，必须在 `event_normalizer` 中映射后统计。
3. `audited_findings` 采用分层抽样：按风险等级（critical/high/medium/low）与类型（command/path/injection/leakage）抽样，最低 40 条。
4. `p95_overhead` 必须基于同一批输入做“监控关闭 vs 监控开启”双跑对照，样本数不少于 30。
5. 指标计算必须产出 `metrics_summary.json`，并附计算脚本路径与版本。
6. `approval_enforcement_accuracy/timeout_failsafe_consistency/system_error_failsafe_consistency/block_accuracy` 的每项样本数不得低于 20。
7. 门禁判定必须同时满足：阈值达标 + 规约版本匹配 + 产物哈希可追溯。
8. `S8` 中 `critical/high` 的 `rejected` 分支样本数不得低于 10，且必须 100% 映射到 `final_action_executed=deny`。

---

## 7. 复核循环设计（为多次复核准备）

### 7.1 复核轮次建议

1. `R1` 架构复核：模块边界与主流程。
2. `R2` 数据模型复核：字段最小集与可扩展性。
3. `R3` 风险策略复核：规则覆盖与阈值。
4. `R4` 验证方案复核：真实 API 场景是否充分。

### 7.2 每轮输出

1. 差异清单（新增/删除/修改）。
2. 风险清单（变更引入的潜在问题）。
3. 下一轮重点问题。

---

## 8. 实施拆分（为后续编码准备）

### Step 1

- 建立最小 adapter + event normalizer。
- 验证：真实 stream/hook 采集。

### Step 2

- 建立 trace builder。
- 验证：可从事件重建 step 链。

### Step 3

- 建立 rule engine + scorer。
- 验证：风险样例触发正确等级。

### Step 4

- 建立 response engine（observe-only）。
- 验证：allow/alert/recommend_* 全链路。

### Step 5

- 建立 provenance recorder + 影子审批日志。
- 验证：finding 到 evidence 可追溯，审批超时可审计。

### Step 6（Phase 2-A：审批执行化）

- 启用 external approval 执行链路（非影子）。
- 验证：执行 `S8/S8B/S9/S10`，审批通过/拒绝/超时/系统错误对执行结果产生确定影响（含 fail-safe）。

### Step 7（Phase 2-B：阻断执行化）

- 启用 hard block（pre_tool_use）。
- 验证：执行 `S11/S12`，高危命令被阻断且不破坏主流程稳定性。

---

## 9. 进入代码阶段与阶段升级门禁

### 9.1 进入代码实现门禁（Phase 1）

仅当以下全部满足，才进入代码实现：

1. 本文档完成至少一轮复核并冻结 v1。
2. 规则集合、阈值、响应矩阵经确认。
3. 真实 API 验证场景清单确认无缺项。
4. 已明确本轮只实现 `observe-only`，并记录主动防护延后决策。

### 9.2 Gate-A：进入 Phase 2-A（审批执行灰度）门禁

1. 关键事件捕获率 >= 95%。
2. 证据链回放成功率 >= 95%。
3. 规则模式额外开销 P95 <= 15%。
4. 风险定位抽样准确率 >= 85%。
5. `S1-S7` 全部通过，且 `S6/S6B` 对 `timed_out/system_error` 的影子 fail-safe 验证完成。
6. 指标产物满足 `6.7` 规约（`metrics_spec_version` 一致、产物哈希可追溯）。

### 9.3 Gate-B：Phase 2-A 达标并进入 Phase 2-B（阻断执行灰度）门禁

1. `S8/S8B/S9/S10` 全部通过。
2. `approval_enforcement_accuracy >= 95%`、`rejected_deny_consistency = 100%`、`timeout_failsafe_consistency = 100%`、`system_error_failsafe_consistency = 100%`。
3. Phase 2-A 连续两轮验证通过（同一 `metrics_spec_version`，不同 `run_id`）。
4. 指标与产物继续满足 `6.7` 规约（可追溯哈希、版本一致）。

### 9.4 Gate-C：Phase 2-B 发布门禁

1. `S11-block-accuracy` 通过，且 `block_accuracy >= 95%`（20 样本）。
2. `S12-enforcement-stability` 通过，且 `stability_error_rate <= 2%`（>=50 样本）。
3. `BLOCK` 执行对主流程稳定性影响可控（无致命中断、可恢复）。

---

## 10. 决策点与变更日志（2026-03-09）

### 10.1 决策点（Decision Records）

1. `DR-20260309-01`：Phase 1 采用只读监督，不执行阻断。
2. `DR-20260309-02`：external approval 在 Phase 1 仅影子运行，不作为生产门禁。
3. `DR-20260309-03`：主动防护升级以量化门禁触发，不按时间点触发。
4. `DR-20260309-04`：Phase 1 验证采用可执行检查清单（场景阈值 + 失败回流）。

### 10.2 变更日志（Changelog）

1. 将 Phase 1 目标从“执行闭环”调整为“建议闭环（observe-only）”。
2. 新增 `GateRecommendation` 结构与审批超时配置。
3. 将实现拆分扩展为 Phase 1 + Phase 2 两段路线。
4. 新增主动防护进入门禁的量化阈值。
5. 新增真实 API 可执行检查清单、报告模板与指标口径。
6. （R3）统一动作枚举与执行模式：`observe_only/enforce_approval/enforce_block`。
7. （R3）补充 `RuleHitRecord`、`GateDecisionRecord`、`TraceEdge` 等结构化审计字段。
8. （R3）补充指标执行规约（`expected_key_events`、抽样规则、双跑对照、产物哈希）。
9. （R3）将 Phase 2 入口拆分为 `Phase 2-A`（审批执行化）与 `Phase 2-B`（阻断执行化）。
10. （R4）补齐审批状态机 fail-safe 真值：`timed_out/system_error` 按风险分级映射到 `deny` 或 `alert_allow`。
11. （R4）新增 Phase 2-A/2-B 可执行检查清单（`S8-S12`）与执行态指标口径。
12. （R4）补充 `TraceSpan/TracePath`、跨表主键关联（`gate_decision_id/provenance_chain_id/decision_attempt`）与动作标准化映射。
13. （R5）修复阶段门禁循环定义：拆分 `Gate-A/Gate-B/Gate-C`，区分“进入灰度”与“发布达标”。
14. （R5）补齐 Phase 1 审批状态机 `system_error` 真值与 `S6B` 可执行检查项。
15. （R5）将 `critical/high + rejected -> deny` 显式固化到状态机与 `S8` 验证阈值。
16. （R5）新增 `ApprovalEventRecord` 及跨表强约束（含 `provenance_chain_id`、`decision_attempt` 三表一致）。
17. （R5）补充确定性破坏规则标签契约（`deterministic_destructive`）与最小规则清单。
