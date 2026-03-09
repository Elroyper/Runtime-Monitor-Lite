# Step1 Validation Guide

This directory records how to run Step1 real API validation for `Runtime-Monitor-Lite`.

## Preconditions

1. Activate env: `conda activate a3s_code`
2. Ensure `a3s_code` is importable:

```bash
python -c "import a3s_code,sys; print(sys.executable); print(getattr(a3s_code, '__version__', 'unknown'))"
```

## 1) Run real API capture

```bash
conda run -n a3s_code python scripts/validation/run_step1_real_api.py \
  --config test/all_config.hcl \
  --workspace "$(pwd)" \
  --run-id run_$(date +%Y%m%d_%H%M%S) \
  --random-seed 20260309
```

可选参数（用于 stream 超时排障）：

- `--prompt "Reply with exactly: OK"`：主采集走最小 prompt。
- `--probe-prompt "Reply with exactly: OK"`：预检模型首事件可达性。
- `--model openai/model--zhipuai--glm-4.7`：显式指定模型。
- `--fallback-model <provider/model>`：追加候选模型（可重复）。
- 默认会清理代理环境变量（`HTTP_PROXY/HTTPS_PROXY/ALL_PROXY`）；若需保留，传 `--keep-proxy-env`。

Artifacts are written to:

- `artifacts/runtime_monitor/<run_id>/events/events.jsonl`
- `artifacts/runtime_monitor/<run_id>/findings/findings.jsonl` (placeholder in Step1)
- `artifacts/runtime_monitor/<run_id>/rule_hits/rule_hits.jsonl` (placeholder in Step1)
- `artifacts/runtime_monitor/<run_id>/approval_events/approval_events.jsonl` (placeholder in Step1)
- `artifacts/runtime_monitor/<run_id>/gate_decisions/gate_decisions.jsonl` (placeholder in Step1)
- `artifacts/runtime_monitor/<run_id>/provenance/provenance.jsonl` (placeholder in Step1)
- `artifacts/runtime_monitor/<run_id>/run_meta.json`
- `artifacts/runtime_monitor/<run_id>/validation_report.md`

## 2) Calculate metrics and generate final report

```bash
conda run -n a3s_code python scripts/validation/calc_step1_metrics.py \
  --artifacts-dir artifacts/runtime_monitor/<run_id> \
  --metrics-spec-version v1
```

Outputs:

- `artifacts/runtime_monitor/<run_id>/metrics_summary.json`
- `artifacts/runtime_monitor/<run_id>/validation_report.md` (updated)

## Notes

1. Step1 is `observe_only`; no enforce action is executed.
2. A non-zero exit code means one or more gate checks failed; keep artifacts and log issue IDs.
3. Re-run with a new `run_id` for reproducibility and auditability.
