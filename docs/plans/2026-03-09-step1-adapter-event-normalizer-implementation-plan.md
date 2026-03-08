# Step 1 (Minimal Adapter + Event Normalizer) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不改动冻结语义（动作枚举、状态机、Gate-A/B/C、S1-S12、指标口径）的前提下，完成 Step 1 最小 `a3s_adapter + event_normalizer`，并建立真实 API 验证闭环。

**Architecture:** 真实 `a3s_code` stream/hook/lane 事件先由 `a3s_adapter` 采集，再由 `event_normalizer` 映射 canonical 事件，输出 `EventRecord` 到 JSONL。Step 1 仅做 `observe_only`。

**Tech Stack:** Python 3.x, `a3s_code` (conda env `a3s_code`), pytest, JSONL artifacts.

---

## 0. 冻结约束（强制）

1. 动作枚举固定：`ALLOW/ALERT/RECOMMEND_BLOCK/RECOMMEND_EXTERNAL_APPROVAL/BLOCK/EXTERNAL_APPROVAL`。
2. 执行模式固定：`observe_only/enforce_approval/enforce_block`。
3. 状态机与 fail-safe 真值固定；Step 1 仅记录 `recorded_only` 语义。
4. Gate 阈值判定严格使用 `04-a3s-phase1-detailed-design.md`。
5. 冲突处理：先记 issue 回流文档，再修实现；禁止绕过。

## 1. 环境与前置条件（真实 API）

1. 运行环境：`conda activate a3s_code`。
2. 自检命令：
   - `python -c "import a3s_code,sys; print(sys.executable); print(getattr(a3s_code,'__version__','unknown'))"`
3. 非交互执行推荐：`conda run -n a3s_code python <script.py>`。

## 2. Gate-A/B/C 绑定

| Gate | Step 1 绑定方式 | 说明 |
|---|---|---|
| Gate-A | 直接绑定 | 支撑 `event_capture_rate`、`expected_key_events` canonical 映射、`metrics_spec_version` 与哈希可追溯 |
| Gate-B | 依赖绑定 | 先固定 `approval_events/gate_decisions/provenance` schema 和跨表主键，不做 Gate-B 放行判定 |
| Gate-C | 依赖绑定 | 先固定 `decision/enforcement_mode/final_action_executed` 字段契约，为执行态阻断打底 |

## 3. Step 1 任务分解（子任务/输入输出/完成标准）

### T1. 建立最小模块骨架

- 输入：冻结文档 `3.1/3.2/4.1` 数据结构要求。
- 输出：最小代码骨架。
- 完成标准：模块可导入，测试可发现。
- 文件：
  - Create `src/runtime_monitor_lite/supervision/models.py`
  - Create `src/runtime_monitor_lite/supervision/a3s_adapter.py`
  - Create `src/runtime_monitor_lite/supervision/event_normalizer.py`
  - Create `src/runtime_monitor_lite/storage/jsonl_sink.py`

### T2. 先写失败测试（TDD）

- 输入：raw 事件名与 canonical 清单。
- 输出：失败测试覆盖映射、未知事件、必填字段。
- 完成标准：`pytest tests/step1 -q` 先红。
- 文件：
  - Create `tests/step1/test_event_normalizer.py`
  - Create `tests/step1/test_action_canonicalization.py`

### T3. 实现 event_normalizer

- 输入：a3s 事件对象（dict/attr）。
- 输出：`EventRecord`（`event_type_raw/event_type_norm/event_quality`）。
- 完成标准：T2 转绿；未知事件落 `UNKNOWN_RAW_EVENT`。
- 文件：
  - Modify `src/runtime_monitor_lite/supervision/event_normalizer.py`
  - Modify `src/runtime_monitor_lite/supervision/models.py`

### T4. 实现 a3s_adapter（stream + hook）

- 输入：`session.stream()` + `register_hook()` 实时事件。
- 输出：`events.jsonl`。
- 完成标准：真实 API 至少 1 次完整采集并可复现。
- 文件：
  - Modify `src/runtime_monitor_lite/supervision/a3s_adapter.py`
  - Modify `src/runtime_monitor_lite/storage/jsonl_sink.py`
  - Create `scripts/validation/run_step1_real_api.py`

### T5. 指标与报告落盘

- 输入：`events.jsonl`。
- 输出：`validation_report.md` + `metrics_summary.json`。
- 完成标准：能计算并输出 `event_capture_rate` 与产物哈希。
- 文件：
  - Create `scripts/validation/calc_step1_metrics.py`
  - Create `docs/validation/README.md`

## 4. 真实 API 验证清单（本轮）

| 场景 | 样本数 | 阈值 | 失败回流项 |
|---|---:|---|---|
| V1-stream-capture | >=20 | `event_capture_rate >= 95%` | adapter 采集点与事件缺失映射 |
| V2-hook-capture | >=20 | hook 事件 canonical 映射完整率 `>=95%` | hook matcher/config 与 normalizer 映射 |
| V3-canonical-map | >=50 | canonical 命中率 `=100%`（未知仅 `UNKNOWN_RAW_EVENT`） | raw->norm 映射表修订 |
| V4-required-fields | >=50 | `session_id/turn_id/ts` 完整率 `=100%`（缺失标记 `partial`） | 字段提取与降级策略 |
| V5-artifact-integrity | >=1 run | 产物哈希追溯 `=100%` | hash 生成与落盘顺序 |

## 5. 可执行命令（非 mock-only）

```bash
conda activate a3s_code
python -c "import a3s_code,sys; print('python=', sys.executable); print('a3s_code=', getattr(a3s_code,'__version__','unknown'))"

# 基线真实 API 冒烟（仓库现有脚本）
conda run -n a3s_code python test/test_eventbus.py
conda run -n a3s_code python test/test_events.py

# Step 1 实现后执行
conda run -n a3s_code python scripts/validation/run_step1_real_api.py \
  --config test/all_config.hcl \
  --workspace "$(pwd)" \
  --run-id run_$(date +%Y%m%d_%H%M%S) \
  --random-seed 20260309

conda run -n a3s_code python scripts/validation/calc_step1_metrics.py \
  --artifacts-dir artifacts/runtime_monitor/current \
  --metrics-spec-version v1
```

## 6. 产物路径规划（审计链）

根目录：`artifacts/runtime_monitor/<run_id>/`

1. `validation_report.md`
2. `metrics_summary.json`
3. `events/events.jsonl`
4. `findings/findings.jsonl`
5. `rule_hits/rule_hits.jsonl`
6. `approval_events/approval_events.jsonl`
7. `gate_decisions/gate_decisions.jsonl`
8. `provenance/provenance.jsonl`

说明：Step 1 强制产出 `events/validation_report/metrics_summary`；其余路径先创建空文件（header）保持后续兼容。

## 7. 风险与回滚预案

1. 事件字段与假设不一致：保留 raw payload，映射到 `UNKNOWN_RAW_EVENT`，建 issue 回流文档。
2. hook/stream 重复或乱序：启用幂等键（`session_id+turn_id+event_id`）并保留原始顺序日志。
3. 指标口径偏移：锁定 `metrics_spec_version=v1`，先修脚本后重跑；不得改冻结公式。
4. API 不稳定：失败 run 固化 `run_id` + 原始输入，先复现实验再继续开发。

## 8. Git 计划与提交节奏

1. 分支：`feat/step1-adapter-normalizer`（当前）。
2. 提交粒度：每个子任务一个提交（代码 + 对应验证产物索引同提交）。
3. 提交信息：`step1 <task|scenario> gateA-prep`。
4. 推送时机：每日至少一次；每次真实 API 验证通过立即推送；Gate-A 预检通过立即推送。
