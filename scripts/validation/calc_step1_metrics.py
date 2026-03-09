from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_KEY_EVENTS = [
    "SESSION_START",
    "TURN_START",
    "TOOL_EXEC_START",
    "TOOL_EXEC_END",
    "TURN_END",
    "SESSION_END",
    "RUNTIME_ERROR",
    "EXTERNAL_TASK_PENDING",
    "EXTERNAL_TASK_COMPLETED",
    "CONFIRMATION_TIMEOUT",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate Step1 metrics from artifacts.")
    parser.add_argument(
        "--artifacts-dir",
        required=True,
        help="Run artifact dir or root dir containing run subdirectories.",
    )
    parser.add_argument(
        "--metrics-spec-version",
        default="v1",
        help="Metrics spec version.",
    )
    return parser.parse_args()


def resolve_run_dir(path: Path) -> Path:
    path = path.resolve()
    if (path / "events" / "events.jsonl").exists():
        return path
    if not path.exists():
        raise FileNotFoundError(f"Artifact path does not exist: {path}")

    candidates = sorted(
        d
        for d in path.iterdir()
        if d.is_dir() and (d / "events" / "events.jsonl").exists()
    )
    if not candidates:
        raise FileNotFoundError(f"No run directory with events.jsonl found under: {path}")
    return candidates[-1]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            content = line.strip()
            if not content:
                continue
            rows.append(json.loads(content))
    return rows


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def build_artifact_hashes(run_dir: Path) -> tuple[dict[str, str], str]:
    tracked_rel_paths = [
        "events/events.jsonl",
        "findings/findings.jsonl",
        "rule_hits/rule_hits.jsonl",
        "approval_events/approval_events.jsonl",
        "gate_decisions/gate_decisions.jsonl",
        "provenance/provenance.jsonl",
        "run_meta.json",
    ]
    hash_map: dict[str, str] = {}
    for rel_path in tracked_rel_paths:
        file_path = run_dir / rel_path
        if file_path.exists():
            hash_map[rel_path] = file_sha256(file_path)

    digest = hashlib.sha256()
    for rel_path in sorted(hash_map):
        digest.update(rel_path.encode("utf-8"))
        digest.update(b":")
        digest.update(hash_map[rel_path].encode("utf-8"))
        digest.update(b"\n")
    return hash_map, f"sha256:{digest.hexdigest()}"


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def fmt_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def load_run_meta(run_dir: Path) -> dict[str, Any]:
    meta_path = run_dir / "run_meta.json"
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def write_validation_report(run_dir: Path, metrics: dict[str, Any], run_meta: dict[str, Any]) -> None:
    event_capture_rate = metrics["event_capture_rate"]
    canonical_map_rate = metrics["canonical_map_rate"]
    required_fields_full_rate = metrics["required_fields_full_rate"]
    artifacts_hash = metrics["artifacts_hash"]

    checks = [
        (
            "V1-stream-capture",
            metrics["total_events"],
            event_capture_rate >= 0.95,
            f"event_capture_rate={fmt_percent(event_capture_rate)}",
        ),
        (
            "V3-canonical-map",
            metrics["total_events"],
            canonical_map_rate >= 1.0,
            f"canonical_map_rate={fmt_percent(canonical_map_rate)}",
        ),
        (
            "V4-required-fields",
            metrics["total_events"],
            required_fields_full_rate >= 1.0,
            f"required_fields_full_rate={fmt_percent(required_fields_full_rate)}",
        ),
        (
            "V5-artifact-integrity",
            1,
            bool(artifacts_hash),
            f"artifacts_hash={artifacts_hash}",
        ),
    ]

    phase1_gate_pass = all(item[2] for item in checks)
    issue_ids = run_meta.get("issue_ids") or []
    stream_error = (run_meta.get("stream_result") or {}).get("error")
    run_id = metrics["run_id"]
    derived_issues: list[dict[str, str]] = []

    if event_capture_rate < 0.95:
        derived_issues.append(
            {
                "issue_id": "ISSUE-STEP1-METRIC-EVENT-CAPTURE-RATE",
                "symptom": f"event_capture_rate={event_capture_rate:.6f} < 0.95",
                "root_cause_hypothesis": "captured canonical key events are insufficient in this run",
                "design_fix_proposal": "expand scenario prompts and add session-level event mapping coverage",
            }
        )
    if canonical_map_rate < 1.0:
        derived_issues.append(
            {
                "issue_id": "ISSUE-STEP1-METRIC-CANONICAL-MAP-RATE",
                "symptom": f"canonical_map_rate={canonical_map_rate:.6f} < 1.0",
                "root_cause_hypothesis": "raw events contain unmapped types (e.g. UNKNOWN_RAW_EVENT)",
                "design_fix_proposal": "extend EventNormalizer RAW_EVENT_TO_CANONICAL mapping for observed raw types",
            }
        )
    if required_fields_full_rate < 1.0:
        derived_issues.append(
            {
                "issue_id": "ISSUE-STEP1-METRIC-REQUIRED-FIELDS",
                "symptom": f"required_fields_full_rate={required_fields_full_rate:.6f} < 1.0",
                "root_cause_hypothesis": "required metadata fields are missing in normalized events",
                "design_fix_proposal": "fill session_id/turn_id extraction path for runtime event object schema",
            }
        )

    lines = [
        "# Runtime Supervision Validation Report",
        "",
        "## 1. 环境信息",
        f"- date: {utc_now_iso()}",
        f"- run_id: {run_id}",
        f"- metrics_spec_version: {metrics['metrics_spec_version']}",
        f"- random_seed: {run_meta.get('random_seed', 'unknown')}",
        "",
        "## 2. 场景结果",
        "| scenario_id | samples | pass | fail | key_metrics | artifacts |",
        "|---|---:|---:|---:|---|---|",
    ]

    for scenario_id, samples, passed, key_metrics in checks:
        lines.append(
            f"| {scenario_id} | {samples} | {1 if passed else 0} | {0 if passed else 1} | "
            f"{key_metrics} | events/findings/rule_hits/gate_decisions/provenance |"
        )

    lines.extend(
        [
            "",
            "## 3. 量化指标汇总",
            f"- event_capture_rate: {event_capture_rate:.6f}",
            f"- replay_success_rate: {metrics.get('replay_success_rate', 0.0):.6f}",
            f"- p95_overhead: {metrics.get('p95_overhead', 0.0):.6f}",
            f"- location_accuracy: {metrics.get('location_accuracy', 0.0):.6f}",
            f"- approval_enforcement_accuracy: {metrics.get('approval_enforcement_accuracy', 0.0):.6f}",
            f"- rejected_deny_consistency: {metrics.get('rejected_deny_consistency', 0.0):.6f}",
            f"- timeout_failsafe_consistency: {metrics.get('timeout_failsafe_consistency', 0.0):.6f}",
            f"- system_error_failsafe_consistency: {metrics.get('system_error_failsafe_consistency', 0.0):.6f}",
            f"- block_accuracy: {metrics.get('block_accuracy', 0.0):.6f}",
            f"- stability_error_rate: {metrics.get('stability_error_rate', 0.0):.6f}",
            f"- artifacts_hash: {artifacts_hash}",
            "",
            "## 4. 失败样本与回流项",
        ]
    )

    if issue_ids:
        for issue_id in issue_ids:
            lines.append(f"- issue_id: {issue_id}")
            if stream_error:
                lines.append(f"  - symptom: {stream_error}")
                lines.append("  - root_cause_hypothesis: model/network/connectivity instability")
                lines.append("  - design_fix_proposal: verify model endpoint and rerun with fixed timeout budget")
    if derived_issues:
        for issue in derived_issues:
            lines.append(f"- issue_id: {issue['issue_id']}")
            lines.append(f"  - symptom: {issue['symptom']}")
            lines.append(f"  - root_cause_hypothesis: {issue['root_cause_hypothesis']}")
            lines.append(f"  - design_fix_proposal: {issue['design_fix_proposal']}")
    if not issue_ids and not derived_issues:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## 5. 结论",
            f"- phase1_gate: {'pass' if phase1_gate_pass else 'fail'}",
            "- phase2a_gate: fail",
            "- phase2b_gate: fail",
            "",
        ]
    )

    report_path = run_dir / "validation_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    run_dir = resolve_run_dir(Path(args.artifacts_dir))
    events_path = run_dir / "events" / "events.jsonl"
    records = load_jsonl(events_path)

    total_events = len(records)
    norm_events = [str(item.get("event_type_norm", "")) for item in records]
    captured_key_events = sorted({event for event in norm_events if event in EXPECTED_KEY_EVENTS})
    unknown_raw_event_count = sum(1 for event in norm_events if event == "UNKNOWN_RAW_EVENT")
    known_event_count = total_events - unknown_raw_event_count
    full_quality_count = sum(1 for item in records if str(item.get("event_quality")) == "full")

    event_capture_rate = safe_ratio(len(captured_key_events), len(EXPECTED_KEY_EVENTS))
    canonical_map_rate = safe_ratio(known_event_count, total_events)
    required_fields_full_rate = safe_ratio(full_quality_count, total_events)

    artifact_hashes, artifacts_hash = build_artifact_hashes(run_dir)
    run_meta = load_run_meta(run_dir)

    metrics = {
        "run_id": run_dir.name,
        "generated_at": utc_now_iso(),
        "metrics_spec_version": args.metrics_spec_version,
        "expected_key_events": EXPECTED_KEY_EVENTS,
        "captured_key_events": captured_key_events,
        "total_events": total_events,
        "unknown_raw_event_count": unknown_raw_event_count,
        "event_capture_rate": event_capture_rate,
        "canonical_map_rate": canonical_map_rate,
        "required_fields_full_rate": required_fields_full_rate,
        "replay_success_rate": 0.0,
        "p95_overhead": 0.0,
        "location_accuracy": 0.0,
        "approval_enforcement_accuracy": 0.0,
        "rejected_deny_consistency": 0.0,
        "timeout_failsafe_consistency": 0.0,
        "system_error_failsafe_consistency": 0.0,
        "block_accuracy": 0.0,
        "stability_error_rate": 0.0,
        "artifact_hashes": artifact_hashes,
        "artifacts_hash": artifacts_hash,
    }

    metrics_path = run_dir / "metrics_summary.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    write_validation_report(run_dir, metrics, run_meta)

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    phase1_gate_pass = (
        metrics["event_capture_rate"] >= 0.95
        and metrics["canonical_map_rate"] >= 1.0
        and metrics["required_fields_full_rate"] >= 1.0
        and metrics["total_events"] > 0
    )
    return 0 if phase1_gate_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
