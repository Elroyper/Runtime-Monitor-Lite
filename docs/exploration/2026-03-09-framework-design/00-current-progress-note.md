# 当前进度说明（2026-03-09）

## 1. 当前状态

已完成从“总体设计”到“a3s Phase 1 详细设计”的过渡，当前处于：

`R5 阻断项修复完成 -> Phase 1 v1.4-frozen 与 master v0.3-frozen 已冻结`

已进入代码实现阶段（Step 1 按 TDD 与真实 API 验证并行推进）。

---

## 2. 已完成文档

1. `01-framework-capability-research.md`
2. `02-a3s-first-architecture-design.md`
3. `03-capability-matrix-and-roadmap.md`
4. `04-a3s-phase1-detailed-design.md`

---

## 3. 已确认原则（强制执行）

本项目每个功能必须遵循：

`调研 -> 设计文档 -> 循环复核修改 -> 逐步代码实现 -> 每步实现都进行基于真实 API 的验证`

当前我们正处于“Step 1 实施与验证”阶段。

---

## 4. 下一步工作（实施导向）

1. 修复 Step 1 真实 API `session.stream()` 超时阻断项（模型连通性/默认 provider/超时窗口）。
2. 基于 `scripts/validation/run_step1_real_api.py` 重跑并产出非空 `events.jsonl`。
3. 执行 `scripts/validation/calc_step1_metrics.py`，更新 `metrics_summary.json` 与 `validation_report.md`。
4. 继续 Step 2（trace builder）前，先确认 Step 1 的 `event_capture_rate` 达到 Gate-A 前置口径。
5. 复核跨表审计键（`rule_hit_refs/gate_decision_id/provenance_chain_id/decision_attempt`）回放一致性。
6. 变更控制：任何策略变更先更新 `04` 冻结文档再进入实现。

---

## 5. 风险提示

1. 若在复核阶段发现能力假设错误，应先修文档，不应直接绕过到代码。
2. 若真实 API 验证场景不充分，后续实现很容易出现“看似可用但不可验证”的问题。

---

## 6. 决策与复核日志

1. `2026-03-09 R1`：确认 Phase 1 采用只读监督，不执行硬阻断。
2. `2026-03-09 R1`：external approval 在 Phase 1 仅影子验证，不作为生产门禁。
3. `2026-03-09 R1`：主动防护进入条件改为量化门禁触发（覆盖率/开销/定位/回放）。
4. `2026-03-09 R2`：补充 Phase 1 真实 API 检查清单模板（场景、阈值、产物、失败回流）。
5. `2026-03-09 R3`：统一动作枚举与执行模式（`observe_only/enforce_approval/enforce_block`）。
6. `2026-03-09 R3`：将 Phase 2 实施拆分为 `P2-A`（审批执行化）与 `P2-B`（阻断执行化）。
7. `2026-03-09 R3`：补充指标执行规约（固定事件清单、抽样规则、双跑对照、产物哈希）。
8. `2026-03-09 R4`：补齐审批状态机 fail-safe（`timed_out/system_error`，按风险分级）。
9. `2026-03-09 R4`：新增 Phase 2-A/2-B 可执行检查清单（`S8-S12`）与执行态指标口径。
10. `2026-03-09 R4`：补充结构化审计键与 `TraceSpan/TracePath`，修正跨文档阶段语义对齐。
11. `2026-03-09 R5`：修复门禁循环定义，拆分 `Gate-A/Gate-B/Gate-C`。
12. `2026-03-09 R5`：补齐 `Phase 1 system_error` 审批真值与 `S6B`。
13. `2026-03-09 R5`：补齐 `provenance_chain_id` 跨表约束并冻结核心文档版本。
14. `2026-03-09 R5`：验证远程仓库 `git@github.com:Elroyper/Runtime-Monitor-Lite.git` 可达且具备写入权限（`ls-remote` 连通通过、refs=0；`git push --dry-run` 通过）。

---

## 7. Git 协作与更新习惯（实现阶段强制）

远程仓库：

- `git@github.com:Elroyper/Runtime-Monitor-Lite.git`

执行约束：

1. 每完成一个实现步骤（Step N）且通过对应真实 API 验证后，立即提交一次（小步提交）。
2. 每次提交必须包含“代码 + 对应验证产物索引/报告更新”，禁止只提代码不提验证记录。
3. 每日至少一次推送远程，避免本地长期漂移；关键里程碑（`Gate-A/B/C` 达成）必须立即推送。
4. 提交信息建议包含：`step`、`scenario_id`、`gate`（如：`step1 S1-S3 gateA-prep`）。
5. 若验证失败，先提交失败样本与回流 issue，再进行修正提交，确保审计链连续。
6. 首次接入建议先创建初始化提交并推送 `main`，再开始 Step 级小步提交。

---

## 8. 运行环境补充（真实 API 验证）

1. Step 1 及后续真实 API 验证统一使用 conda 环境：`a3s_code`。
2. 执行前先激活环境：`conda activate a3s_code`。
3. 建议先做环境自检：`python -c "import a3s_code,sys; print(sys.executable); print(getattr(a3s_code, '__version__', 'unknown'))"`。
4. 非交互执行可用：`conda run -n a3s_code python <script.py>`。

---

## 9. 实施进度更新（2026-03-09）

### 9.1 本轮已完成

1. Git 接入完成：`main` 初始化提交并推送；已创建实现分支 `feat/step1-adapter-normalizer`。
2. Step 1 实施计划已落盘：`docs/plans/2026-03-09-step1-adapter-event-normalizer-implementation-plan.md`。
3. 已进入下一步（Step 1 实装）并完成：
   - `T1` 最小代码骨架（`models/a3s_adapter/event_normalizer/jsonl_sink`）。
   - `T2` 失败测试先行（RED）。
   - `T3` 最小实现转绿（GREEN）。

### 9.2 本轮验证结果（真实 API）

1. 测试命令（conda 环境）：`conda run -n a3s_code --no-capture-output python -u test/test_eventbus.py`（`timeout 40s` 包裹）。
2. 已验证通过：
   - Hook 注册/注销、matcher/config 能力可用（11 类事件可注册）。
   - Lane handler / Queue 统计 API 可调用。
   - Orchestrator / SubAgent API 可调用并返回状态。
3. 未通过项：
   - Streaming + Hooks 集成在本轮超时窗口内未返回（`Part 4` 在 prompt 后超时）。
4. 回流 issue：
   - `ISSUE-20260309-STEP1-REALAPI-STREAM-TIMEOUT`
   - 现象：`session.stream()` 在 40s/150s 超时窗口内无返回事件。
   - 回流方向：排查模型端连通性、`test/all_config.hcl` 默认模型可用性、网络抖动与超时策略。

### 9.3 协作与提交记录（2026-03-09）

1. 已完成“普通客户视角”说明同步：覆盖最终预期效果、三阶段能力（observe/approval/block）与使用方式。
2. 本次 Git 保存目标：将进度文档更新单独提交，确保“沟通说明 -> 进度记录 -> 版本留痕”闭环。
3. 关联分支：`feat/step1-adapter-normalizer`（持续小步提交）。

### 9.4 Step1 代码推进（T4/T5，2026-03-09）

1. 已完成 `T4`：
   - 增强 `A3SAdapter`（默认 hook 注册、stream 采集统计、可配置 stop/max_events）。
   - 增强 `JsonlSink`（自动建文件、`default=str` 序列化降级）。
   - 新增真实采集脚本：`scripts/validation/run_step1_real_api.py`。
2. 已完成 `T5`：
   - 新增指标脚本：`scripts/validation/calc_step1_metrics.py`。
   - 新增验证说明：`docs/validation/README.md`。
3. 单元测试结果：
   - `conda run -n a3s_code --no-capture-output python -m unittest discover -s tests/step1 -v` 通过（12/12）。
4. 本轮真实 API 结果：
   - run_id：`run_20260309_124225`
   - 结果：`session.stream()` 在 90s 超时，无事件采集（`events.jsonl` 空文件）。
   - 产物：`run_meta.json`、`metrics_summary.json`、`validation_report.md` 已落盘。
   - 回流 issue：`ISSUE-20260309-STEP1-REALAPI-STREAM-TIMEOUT`（持续开放）。

### 9.5 Step1 超时阻断修复与验证闭环（2026-03-09）

1. 已完成阻断修复（保持 `observe_only` 不变）：
   - `A3SAdapter.collect_stream` 新增首事件/逐事件 timeout 策略，避免 `session.stream()` 长时间无事件盲等。
   - `run_step1_real_api.py` 新增最小 prompt 探测路径（`probe_prompt`）与模型候选探测（按可达性选择）。
   - 默认清理代理环境变量（`HTTP_PROXY/HTTPS_PROXY/ALL_PROXY` 等），规避本地失效代理导致的连通性阻断；可用 `--keep-proxy-env` 保留。
2. 真实 API 重跑结果：
   - run_id：`run_20260309_150054`
   - 结果：`status=passed`，`events/events.jsonl` 非空（6 条事件），`stream timeout` 阻断解除。
   - 关键证据：`run_meta.json` 记录 `model_selection.probe_attempts` 与 `timeout_policy`，可审计追溯。
3. 本轮指标与 gate：
   - `calc_step1_metrics.py` 已更新 `metrics_summary.json` 与 `validation_report.md`。
   - `phase1_gate: fail`（非 timeout 原因），回流项已在报告中明确：
     - `ISSUE-STEP1-METRIC-EVENT-CAPTURE-RATE`
     - `ISSUE-STEP1-METRIC-CANONICAL-MAP-RATE`
     - `ISSUE-STEP1-METRIC-REQUIRED-FIELDS`
