# R4 实现前复核修订记录（2026-03-09）

## 1. 高影响项评估（先评估后改动）

本轮按“先评估后修改”执行，先处理阻断级风险，再做跨文档一致性收口。

1. 影响级别：高
   - 议题：审批异常流（`timed_out/system_error`）未形成可验证 fail-safe 真值表。
   - 风险：Phase 2-A 执行态不可审计，不可作为门禁依据。
   - 决策：先补状态机与决策结果枚举，再改检查清单。
2. 影响级别：高
   - 议题：Phase 2-A/2-B 量化门禁缺可执行检查清单。
   - 风险：门禁无法落地执行，冻结后仍存在实施歧义。
   - 决策：新增 `S8-S12` 场景与指标口径后再收口门禁条款。
3. 影响级别：中高
   - 议题：跨文档阶段语义冲突（`observe-only` 与执行态动作混用）。
   - 风险：实现可能提前启用阻断或审批执行，违反 DR 基线。
   - 决策：保持 `04` 为规范源，`master/02/03` 做最小同步声明。

## 2. 已执行修订（文件级）

### 2.1 `04-a3s-phase1-detailed-design.md`

1. 新增评分执行规约（`rule/context/history` 固定口径、tie-break 规则、score_components 输出）。
2. 新增 Phase 2-A/2-B 决策矩阵，明确 `approved/rejected/timed_out/system_error` 的动作与 `decision_result`。
3. 补齐审批状态机 fail-safe：`timed_out/system_error` 按风险分级映射到 `deny`/`alert_allow`。
4. 扩展审计字段：`gate_decision_id`、`provenance_chain_id`、`decision_attempt`、`final_action_executed`、`fail_safe_class`。
5. 新增 `TraceSpan`/`TracePath` 与 `location_id` 引用契约，支撑 step/span/path 可审计定位。
6. 增加 `ActionCanonicalization`，统一配置层与存储层动作枚举。
7. 扩展验证：新增 `S8-S12`（Phase 2-A/2-B），补充执行态指标与样本要求。
8. 门禁条款与实施步骤同步引用 `S8-S12`。
9. Changelog 增补 R4 修订项。
10. P0 定向复核修补：将 `critical/high + rejected` 明确为 `final_action_executed=deny`。
11. P0 定向复核修补：新增 `S8B-approval-medium-low`，补齐 `medium/low` 的 `approved/rejected` 分支验证。
12. P0 定向复核修补：总览存储清单补 `approval_events.jsonl`，避免与配置/验证产物不一致。
13. P0 定向复核修补：Phase 2-A 前置条件同步为“超时/系统错误”双异常口径。

### 2.2 `2026-03-09-runtime-security-supervision-master-design.md`

1. 响应语义改为阶段化（Phase 1 建议态，Phase 2 执行态）。
2. 架构图动作枚举补齐 `recommend_*`。
3. `pre_tool_use` 映射补充阶段说明（Phase 1 仅建议，Phase 2-B 执行阻断）。
4. 数据模型补充 `RuleHitRecord`、`GateDecisionRecord`、跨表主键约束。
5. 主流程与分阶段路线补充 `observe-only`/`timed_out/system_error` 的一致性表达。
6. 决策日志增补 R4 条目。
7. 修正版本一致性：`v0.2` 标题与架构章节版本号对齐。

### 2.3 其他同步文档

1. `00-current-progress-note.md`：状态更新为 `v1.3-draft（R4 修订完成，待冻结评审）`，并更新下一步任务与 R4 记录。
2. `02-a3s-first-architecture-design.md`：补充“详细规范以 `04` 为准”，并将异常流从“超时”扩展到“超时/系统错误”。
3. `03-capability-matrix-and-roadmap.md`：补充 Stage A2 验收引用 `S8-S12` 与执行态指标规约。

## 3. 仍需关注的残余风险

1. `04` 当前仍是 `v1.3-draft`，尚未完成冻结标记与签署流程。
2. 执行态指标依赖真实 API 场景数据，需在下一轮复核核验可执行性。
3. 若后续调整动作枚举，必须同步更新 `ActionCanonicalization` 与审计 schema。

## 4. 下轮复核建议

1. 先做一次“仅 P0 条款”定向复核（状态机、门禁、语义一致性）。
2. 再做一次“可审计性”复核（跨表主键、回放链、产物完整性）。
3. 通过后再评估是否进入冻结流程。

## 5. R5 关闭记录（2026-03-09）

1. `04-a3s-phase1-detailed-design.md` 已更新为 `v1.4-frozen`，并补齐门禁分层（`Gate-A/Gate-B/Gate-C`）。
2. `master` 已更新为 `v0.3-frozen`，并对齐 `provenance_chain_id` 跨表约束。
3. `00` 已更新当前状态为“R5 阻断项修复完成，核心文档已冻结”。
4. 本文第 3 节“残余风险”第 1 条（`04` 仍为 draft）在 R5 中已关闭，仅保留为 R4 历史记录。
