# 分支与进度说明

- 文档日期：2026-03-09
- 仓库：`Runtime-Monitor-Lite`

## 1. 分支角色

- 当前 active 开发分支：`feat/step1-adapter-normalizer`
- 基线分支：`main`
- 当前约束：`main` 仍作为设计基线（frozen baseline），实现代码继续在 `feat/step1-adapter-normalizer` 推进。

## 2. Step1 状态（T1-T5）

- 结论：Step1 的 `T1-T5` 代码与脚本已完成（在 active 分支推进）。
- 当前阻断：真实 API 验证仍被 `session.stream()` 超时阻断。
- 未决 issue：`ISSUE-20260309-STEP1-REALAPI-STREAM-TIMEOUT`
- 下一步：先修复 timeout 根因（模型连通性/默认 provider/超时策略），再重跑 Step1 验证并刷新产物。

## 3. 最近关键提交

### 3.1 main（设计基线）

- `fbc8b9b` `chore: bootstrap repository with frozen design baseline`

### 3.2 feat/step1-adapter-normalizer（active）

- `bc1af43` `docs: record customer-facing progress update`
- `2b7a307` `step1 t1-t3 gateA-prep`
- `e5f1948` `docs: add step1 implementation plan and conda env note`

## 4. 已产物路径（Step1）

- 代码（已落分支）：
  - `src/runtime_monitor_lite/supervision/models.py`
  - `src/runtime_monitor_lite/supervision/event_normalizer.py`
  - `src/runtime_monitor_lite/supervision/a3s_adapter.py`
  - `src/runtime_monitor_lite/storage/jsonl_sink.py`
- 测试（已落分支）：
  - `tests/step1/test_event_normalizer.py`
  - `tests/step1/test_action_canonicalization.py`
- 实施与说明文档：
  - `docs/plans/2026-03-09-step1-adapter-event-normalizer-implementation-plan.md`
  - `docs/exploration/2026-03-09-framework-design/00-current-progress-note.md`
- 真实 API/指标脚本与验证文档（active 工作区产物）：
  - `scripts/validation/run_step1_real_api.py`
  - `scripts/validation/calc_step1_metrics.py`
  - `docs/validation/README.md`

## 5. 接力开发入口

- 接力开发入口分支：`feat/step1-adapter-normalizer`
- 接力执行顺序：修复 timeout -> 重跑真实 API 验证 -> 更新 `metrics_summary.json` 与 `validation_report.md` -> 再评估 Step2 启动条件。
