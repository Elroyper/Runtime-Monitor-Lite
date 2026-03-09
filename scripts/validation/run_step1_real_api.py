from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import a3s_code

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from runtime_monitor_lite.storage.jsonl_sink import JsonlSink
from runtime_monitor_lite.supervision.a3s_adapter import A3SAdapter, StreamTimeoutError


PROXY_ENV_KEYS = (
    "http_proxy",
    "https_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "all_proxy",
    "ALL_PROXY",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Step1 real API stream capture.")
    parser.add_argument("--config", required=True, help="Path to a3s_code hcl config.")
    parser.add_argument("--workspace", required=True, help="Workspace path for a3s session.")
    parser.add_argument("--run-id", required=True, help="Run identifier.")
    parser.add_argument(
        "--output-root",
        default="artifacts/runtime_monitor",
        help="Root artifact directory.",
    )
    parser.add_argument(
        "--prompt",
        default="List three files in the current workspace.",
        help="Prompt used for stream capture.",
    )
    parser.add_argument(
        "--probe-prompt",
        default="Reply with exactly: OK",
        help="Minimal prompt used for stream readiness probe.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=90, help="Stream timeout.")
    parser.add_argument(
        "--probe-timeout-seconds",
        type=int,
        default=20,
        help="Timeout budget for model readiness probe.",
    )
    parser.add_argument(
        "--first-event-timeout-seconds",
        type=float,
        default=20.0,
        help="Timeout for first stream event.",
    )
    parser.add_argument(
        "--per-event-timeout-seconds",
        type=float,
        default=30.0,
        help="Timeout for each subsequent stream event.",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=400,
        help="Hard cap for collected events.",
    )
    parser.add_argument(
        "--metrics-spec-version",
        default="v1",
        help="Metrics spec version tag.",
    )
    parser.add_argument("--random-seed", type=int, default=20260309, help="Run seed.")
    parser.add_argument(
        "--builtin-skills",
        action="store_true",
        help="Enable builtin skills when creating session.",
    )
    parser.add_argument(
        "--permissive",
        action="store_true",
        help="Set permissive mode when fallback session factory is used.",
    )
    parser.add_argument(
        "--default-security",
        action="store_true",
        help="Enable default security when SessionOptions supports it.",
    )
    parser.add_argument(
        "--model",
        help="Explicit model id (provider/model) for session.stream().",
    )
    parser.add_argument(
        "--fallback-model",
        action="append",
        default=[],
        help="Optional fallback models (repeatable).",
    )
    parser.add_argument(
        "--keep-proxy-env",
        action="store_true",
        help="Keep proxy env vars. Default behavior clears proxy env to avoid dead local proxy.",
    )
    return parser.parse_args()


def build_artifact_paths(output_root: Path, run_id: str) -> dict[str, Path]:
    run_dir = output_root / run_id
    return {
        "run_dir": run_dir,
        "events": run_dir / "events" / "events.jsonl",
        "findings": run_dir / "findings" / "findings.jsonl",
        "rule_hits": run_dir / "rule_hits" / "rule_hits.jsonl",
        "approval_events": run_dir / "approval_events" / "approval_events.jsonl",
        "gate_decisions": run_dir / "gate_decisions" / "gate_decisions.jsonl",
        "provenance": run_dir / "provenance" / "provenance.jsonl",
        "run_meta": run_dir / "run_meta.json",
        "validation_report": run_dir / "validation_report.md",
    }


def ensure_artifact_layout(paths: dict[str, Path]) -> None:
    for key, path in paths.items():
        if key == "run_dir" or key in {"run_meta", "validation_report"}:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
    paths["run_dir"].mkdir(parents=True, exist_ok=True)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def init_session(
    config_path: str,
    workspace: str,
    *,
    builtin_skills: bool,
    permissive: bool,
    default_security: bool,
    model: str | None,
) -> Any:
    agent = a3s_code.Agent.create(config_path)
    options_cls = getattr(a3s_code, "SessionOptions", None)
    if options_cls is not None:
        opts = options_cls()
        if hasattr(opts, "builtin_skills"):
            opts.builtin_skills = builtin_skills
        if hasattr(opts, "use_memory_session_store"):
            opts.use_memory_session_store = True
        if hasattr(opts, "default_security"):
            opts.default_security = default_security
        if model and hasattr(opts, "model"):
            opts.model = model
        try:
            return agent.session(workspace, opts, model=model)
        except TypeError:
            return agent.session(workspace, opts)

    kwargs: dict[str, Any] = {
        "builtin_skills": builtin_skills,
        "permissive": permissive,
    }
    if model:
        kwargs["model"] = model
    return agent.session(workspace, **kwargs)


def clear_proxy_env() -> dict[str, str]:
    removed: dict[str, str] = {}
    for key in PROXY_ENV_KEYS:
        value = os.environ.pop(key, None)
        if value is not None:
            removed[key] = value
    return removed


def default_model_from_config(config_path: str) -> str | None:
    text = Path(config_path).read_text(encoding="utf-8")
    match = re.search(r'^\s*default_model\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip() or None


def provider_models_from_config(config_path: str) -> list[str]:
    lines = Path(config_path).read_text(encoding="utf-8").splitlines()
    models: list[str] = []
    active_provider: str | None = None
    provider_level = 0
    brace_level = 0

    for line in lines:
        stripped = line.strip()
        open_count = stripped.count("{")
        close_count = stripped.count("}")

        if stripped.startswith("providers") and "{" in stripped:
            active_provider = None
            provider_level = brace_level + 1

        if provider_level and brace_level >= provider_level - 1:
            name_match = re.match(r'^name\s*=\s*"([^"]+)"', stripped)
            if name_match and active_provider is None:
                active_provider = name_match.group(1).strip()

            id_match = re.match(r'^id\s*=\s*"([^"]+)"', stripped)
            if id_match and active_provider:
                models.append(f"{active_provider}/{id_match.group(1).strip()}")

        brace_level += open_count
        brace_level -= close_count

        if provider_level and brace_level < provider_level:
            provider_level = 0
            active_provider = None

    deduped: list[str] = []
    seen: set[str] = set()
    for item in models:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def resolve_model_candidates(args: argparse.Namespace) -> list[str | None]:
    candidates: list[str | None] = []
    if args.model:
        candidates.append(args.model)

    cfg_default = default_model_from_config(args.config)
    if cfg_default:
        candidates.append(cfg_default)

    candidates.extend(provider_models_from_config(args.config))
    candidates.extend(args.fallback_model)

    deduped: list[str | None] = []
    seen: set[str] = set()
    for item in candidates:
        key = item or ""
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped or [None]


class NullSink:
    def write_event(self, _event: Any) -> None:
        return


async def probe_stream_ready(
    args: argparse.Namespace,
    adapter: A3SAdapter,
    *,
    model: str | None,
) -> dict[str, Any]:
    begin = time.monotonic()
    session = init_session(
        args.config,
        args.workspace,
        builtin_skills=args.builtin_skills,
        permissive=args.permissive,
        default_security=args.default_security,
        model=model,
    )
    try:
        summary = await asyncio.wait_for(
            adapter.collect_stream(
                session,
                args.probe_prompt,
                NullSink(),
                max_events=1,
                first_event_timeout_seconds=args.first_event_timeout_seconds,
                per_event_timeout_seconds=args.per_event_timeout_seconds,
            ),
            timeout=args.probe_timeout_seconds,
        )
        return {
            "model": model,
            "status": "ok" if summary.total_events > 0 else "empty",
            "first_event_count": summary.total_events,
            "duration_seconds": round(time.monotonic() - begin, 3),
            "error": None if summary.total_events > 0 else "probe yielded zero events",
        }
    except Exception as exc:  # pragma: no cover - runtime dependent
        return {
            "model": model,
            "status": "failed",
            "first_event_count": 0,
            "duration_seconds": round(time.monotonic() - begin, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }


def write_initial_report(path: Path, run_id: str, status: str, stream_error: str | None) -> None:
    lines = [
        "# Runtime Supervision Validation Report",
        "",
        "## 1. Environment",
        f"- run_id: {run_id}",
        "- phase: step1",
        "",
        "## 2. Run Status",
        f"- status: {status}",
        f"- stream_error: {stream_error or 'none'}",
        "",
        "## 3. Next",
        "- Run `calc_step1_metrics.py` to generate metrics_summary.json and final gate hints.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


async def run_capture(args: argparse.Namespace) -> int:
    random.seed(args.random_seed)
    removed_proxy_env: dict[str, str] = {}
    if not args.keep_proxy_env:
        removed_proxy_env = clear_proxy_env()

    output_root = Path(args.output_root).resolve()
    paths = build_artifact_paths(output_root, args.run_id)
    ensure_artifact_layout(paths)

    adapter = A3SAdapter()
    sink = JsonlSink(paths["events"])
    start_ts = utc_now_iso()
    model_candidates = resolve_model_candidates(args)

    probe_attempts: list[dict[str, Any]] = []
    selected_model: str | None = None
    for model in model_candidates:
        result = await probe_stream_ready(args, adapter, model=model)
        probe_attempts.append(result)
        if result["status"] == "ok":
            selected_model = model
            break
    if selected_model is None and model_candidates:
        selected_model = model_candidates[0]

    session = init_session(
        args.config,
        args.workspace,
        builtin_skills=args.builtin_skills,
        permissive=args.permissive,
        default_security=args.default_security,
        model=selected_model,
    )

    hook_ids: list[str] = []
    hook_error: str | None = None
    try:
        hook_ids = adapter.register_default_hooks(session, hook_prefix=f"rml_{args.run_id}")
    except Exception as exc:  # pragma: no cover - depends on runtime
        hook_error = f"{type(exc).__name__}: {exc}"

    status = "passed"
    stream_error: str | None = None
    timed_out = False
    stream_summary: dict[str, Any] = {
        "total_events": 0,
        "raw_event_counts": {},
        "norm_event_counts": {},
    }

    try:
        summary = await asyncio.wait_for(
            adapter.collect_stream(
                session,
                args.prompt,
                sink,
                max_events=args.max_events,
                first_event_timeout_seconds=args.first_event_timeout_seconds,
                per_event_timeout_seconds=args.per_event_timeout_seconds,
            ),
            timeout=args.timeout_seconds,
        )
        stream_summary = summary.to_dict()
        if summary.total_events <= 0:
            status = "failed"
            stream_error = "No events captured from stream."
    except StreamTimeoutError as exc:
        timed_out = True
        status = "failed"
        stream_error = str(exc)
    except asyncio.TimeoutError:
        timed_out = True
        status = "failed"
        stream_error = f"stream overall timeout after {args.timeout_seconds}s"
    except Exception as exc:  # pragma: no cover - depends on runtime
        status = "failed"
        stream_error = f"{type(exc).__name__}: {exc}"

    end_ts = utc_now_iso()
    issue_ids: list[str] = []
    if timed_out:
        issue_ids.append("ISSUE-20260309-STEP1-REALAPI-STREAM-TIMEOUT")
    elif stream_error:
        issue_ids.append("ISSUE-20260309-STEP1-REALAPI-STREAM-ERROR")

    artifact_hashes: dict[str, str] = {}
    for key, path in paths.items():
        if key == "run_dir":
            continue
        if path.exists():
            artifact_hashes[str(path.relative_to(paths["run_dir"]))] = file_sha256(path)

    run_meta = {
        "run_id": args.run_id,
        "started_at": start_ts,
        "ended_at": end_ts,
        "status": status,
        "metrics_spec_version": args.metrics_spec_version,
        "enforcement_mode": "observe_only",
        "config_path": str(Path(args.config).resolve()),
        "workspace": str(Path(args.workspace).resolve()),
        "session_id": getattr(session, "session_id", None),
        "prompt": args.prompt,
        "probe_prompt": args.probe_prompt,
        "random_seed": args.random_seed,
        "proxy_env": {
            "cleared": not args.keep_proxy_env,
            "removed_keys": sorted(removed_proxy_env.keys()),
        },
        "model_selection": {
            "requested_model": args.model,
            "selected_model": selected_model,
            "candidates": model_candidates,
            "probe_attempts": probe_attempts,
        },
        "timeout_policy": {
            "overall_timeout_seconds": args.timeout_seconds,
            "probe_timeout_seconds": args.probe_timeout_seconds,
            "first_event_timeout_seconds": args.first_event_timeout_seconds,
            "per_event_timeout_seconds": args.per_event_timeout_seconds,
        },
        "hook_registration": {
            "registered_hook_ids": hook_ids,
            "hook_error": hook_error,
        },
        "stream_result": {
            "timed_out": timed_out,
            "error": stream_error,
            **stream_summary,
        },
        "issue_ids": issue_ids,
        "artifact_hashes": artifact_hashes,
    }

    paths["run_meta"].write_text(
        json.dumps(run_meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_initial_report(paths["validation_report"], args.run_id, status, stream_error)

    print(json.dumps(run_meta, ensure_ascii=False, indent=2))
    return 0 if status == "passed" else 2


def main() -> int:
    args = parse_args()
    return asyncio.run(run_capture(args))


if __name__ == "__main__":
    raise SystemExit(main())
