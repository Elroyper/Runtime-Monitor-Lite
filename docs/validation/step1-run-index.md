# Step1 Real API Run Index

## 2026-03-09 最新验证

- run_id: `run_20260309_150054`
- status: `passed` (stream 采集执行成功)
- enforcement_mode: `observe_only`
- timeout_blocker: `resolved` (`stream_result.timed_out=false`)
- selected_model: `openai/kimi-k2.5`
- events_count: `6` (`events/events.jsonl` 非空)
- phase1_gate: `fail`（非 timeout 问题）

## Gate 结论与回流项

- gate_conclusion: `phase1_gate=fail`
- reflux_items:
  - `ISSUE-STEP1-METRIC-EVENT-CAPTURE-RATE`
  - `ISSUE-STEP1-METRIC-CANONICAL-MAP-RATE`
  - `ISSUE-STEP1-METRIC-REQUIRED-FIELDS`

## Artifact Hash Index

- run_meta: `artifacts/runtime_monitor/run_20260309_150054/run_meta.json`
- metrics_summary: `artifacts/runtime_monitor/run_20260309_150054/metrics_summary.json`
- validation_report: `artifacts/runtime_monitor/run_20260309_150054/validation_report.md`
- events_hash: `sha256:91189c41c7dba8ec0c0bb2aed7e0ddfaa43a3649a9ea20d2f246961b3ae96d94`
- artifacts_hash: `sha256:9d84bdcd26e285ae3e4f7057ef2c9b3e375f872955b4546bf7fa1fca0d6a601a`

## 对照失败样本

- run_id: `run_20260309_124225`
- issue_id: `ISSUE-20260309-STEP1-REALAPI-STREAM-TIMEOUT`
- symptom: `session.stream() 在 90s 窗口超时且 events.jsonl 为空`
