#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Iterable, List

import yaml

try:
    from scripts.materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest, write_text_atomic
except ModuleNotFoundError:
    from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest, write_text_atomic


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_CONFIG = ROOT / "config" / "projects" / "fleet.yaml"
DEFAULT_OUT = ROOT / ".codex-studio" / "published" / "PROOF_ORCHESTRATION.generated.json"


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize Fleet proof/materializer jobs from project configuration."
    )
    parser.add_argument("--project-config", default=str(DEFAULT_PROJECT_CONFIG), help="project config YAML path")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output path for PROOF_ORCHESTRATION.generated.json")
    parser.add_argument("--now", default=None, help="optional ISO timestamp for deterministic tests")
    return parser.parse_args(argv)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"project config must be a mapping: {path}")
    return payload


def _parse_now(raw: str | None) -> dt.datetime:
    if not raw:
        return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    clean = raw.strip().replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(clean)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).replace(microsecond=0)


def _parse_timestamp(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _read_payload(path: Path) -> Any:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError:
            return None
    return {"generated_at": None}


def _payload_generated_at(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("generated_at", "generatedAt", "published_at", "created_at"):
            value = payload.get(key)
            if value:
                return str(value)
    return None


def _payload_status(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("status") or payload.get("state") or "").strip().lower()


def _acceptable_statuses(output: dict[str, Any]) -> list[str]:
    values = output.get("acceptable_statuses")
    if values is None:
        values = output.get("required_statuses")
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    return [str(value).strip().lower() for value in values if str(value).strip()]


def _output_state(output: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    path = Path(str(output.get("path") or "")).expanduser()
    required = bool(output.get("required", True))
    window_minutes = int(output.get("freshness_window_minutes") or 0)
    acceptable_statuses = _acceptable_statuses(output)
    payload = _read_payload(path)
    payload_status = _payload_status(payload)
    generated_at = _payload_generated_at(payload)
    if not generated_at and path.exists():
        generated_at = (
            dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    generated_dt = _parse_timestamp(generated_at)
    exists = path.exists()
    age_minutes = None
    state = "missing" if required else "optional_missing"
    if exists and generated_dt is not None and window_minutes > 0:
        age_minutes = max(0, int((now - generated_dt).total_seconds() // 60))
        state = "fresh" if age_minutes <= window_minutes else "stale"
    elif exists and window_minutes <= 0:
        state = "present"
    elif exists:
        state = "unknown_freshness"
    status_ok = True
    if acceptable_statuses:
        status_ok = bool(payload_status) and payload_status in set(acceptable_statuses)
        if exists and state in {"fresh", "present"} and not status_ok:
            state = "failed_status" if payload_status else "unknown_status"
    return {
        "path": str(path),
        "required": required,
        "freshness_window_minutes": window_minutes,
        "exists": exists,
        "generated_at": generated_at,
        "age_minutes": age_minutes,
        "payload_status": payload_status,
        "acceptable_statuses": acceptable_statuses,
        "status_ok": status_ok,
        "state": state,
    }


def _validate_jobs(jobs: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    for index, job in enumerate(jobs):
        job_id = str(job.get("id") or "").strip()
        if not job_id:
            errors.append(f"job at index {index} is missing id")
            continue
        if job_id in ids:
            errors.append(f"duplicate job id: {job_id}")
        ids.add(job_id)
        if int(job.get("freshness_window_minutes") or 0) <= 0:
            errors.append(f"job {job_id} must define positive freshness_window_minutes")
        retry = job.get("retry") or {}
        if int(retry.get("max_attempts") or 0) < 1:
            errors.append(f"job {job_id} must define retry.max_attempts >= 1")
        outputs = job.get("outputs") or []
        if not isinstance(outputs, list) or not outputs:
            errors.append(f"job {job_id} must define at least one output")
        elif not all(isinstance(output, dict) for output in outputs):
            errors.append(f"job {job_id} outputs must be mappings")
    for job in jobs:
        job_id = str(job.get("id") or "").strip()
        for dep in job.get("dependencies") or []:
            if str(dep) not in ids:
                errors.append(f"job {job_id} depends on unknown job {dep}")
    errors.extend(_cycle_errors(jobs))
    return errors


def _cycle_errors(jobs: list[dict[str, Any]]) -> list[str]:
    graph = {str(job.get("id")): [str(dep) for dep in job.get("dependencies") or []] for job in jobs}
    visiting: set[str] = set()
    visited: set[str] = set()
    errors: list[str] = []

    def visit(node: str, trail: list[str]) -> None:
        if node in visited:
            return
        if node in visiting:
            errors.append("dependency cycle: " + " -> ".join(trail + [node]))
            return
        visiting.add(node)
        for dep in graph.get(node, []):
            visit(dep, trail + [node])
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node, [])
    return errors


def _topological_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(job.get("id")): job for job in jobs}
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(job_id: str) -> None:
        if job_id in seen:
            return
        for dep in by_id[job_id].get("dependencies") or []:
            add(str(dep))
        seen.add(job_id)
        ordered.append(by_id[job_id])

    for job in jobs:
        add(str(job.get("id")))
    return ordered


def _flatten_output_states(jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for job in jobs:
        for output in job.get("output_states") or []:
            states.append(output)
    return states


def build_payload(project_cfg: dict[str, Any], *, now: dt.datetime, project_config_path: Path) -> dict[str, Any]:
    contract = project_cfg.get("supervisor_contract") or {}
    raw_jobs = contract.get("proof_jobs") or []
    if not isinstance(raw_jobs, list):
        raise ValueError("supervisor_contract.proof_jobs must be a list")
    jobs = [dict(job) for job in raw_jobs if isinstance(job, dict)]
    errors = _validate_jobs(jobs)
    if errors:
        return {
            "contract_name": "fleet.proof_orchestration",
            "schema_version": 1,
            "generated_at": now.isoformat().replace("+00:00", "Z"),
            "source": str(project_config_path),
            "status": "fail",
            "errors": errors,
            "jobs": jobs,
        }
    materialized_jobs: list[dict[str, Any]] = []
    for index, job in enumerate(_topological_jobs(jobs), start=1):
        retry = job.get("retry") or {}
        output_states = [_output_state(output, now) for output in job.get("outputs") or []]
        state = "ready"
        if any(item["state"] == "missing" for item in output_states):
            state = "missing"
        elif any(item["state"] == "stale" for item in output_states):
            state = "stale"
        elif any(item["state"] == "unknown_freshness" for item in output_states):
            state = "unknown_freshness"
        materialized_jobs.append(
            {
                "id": str(job.get("id")),
                "order": index,
                "title": str(job.get("title") or job.get("id")),
                "kind": str(job.get("kind") or "materializer"),
                "command": str(job.get("command") or ""),
                "dependencies": [str(dep) for dep in job.get("dependencies") or []],
                "freshness_window_minutes": int(job.get("freshness_window_minutes") or 0),
                "retry": {
                    "max_attempts": int(retry.get("max_attempts") or 1),
                    "delay_seconds": int(retry.get("delay_seconds") or 0),
                    "retry_on": list(retry.get("retry_on") or []),
                },
                "output_states": output_states,
                "state": state,
            }
        )
    output_states = _flatten_output_states(materialized_jobs)
    required_outputs = [item for item in output_states if item.get("required")]
    stale_count = sum(1 for item in required_outputs if item.get("state") == "stale")
    missing_count = sum(1 for item in required_outputs if item.get("state") == "missing")
    unknown_count = sum(1 for item in required_outputs if item.get("state") == "unknown_freshness")
    failed_status_count = sum(1 for item in required_outputs if item.get("state") == "failed_status")
    unknown_status_count = sum(1 for item in required_outputs if item.get("state") == "unknown_status")
    status = (
        "pass"
        if not stale_count
        and not missing_count
        and not unknown_count
        and not failed_status_count
        and not unknown_status_count
        else "fail"
    )
    return {
        "contract_name": "fleet.proof_orchestration",
        "schema_version": 1,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "source": str(project_config_path),
        "status": status,
        "summary": {
            "job_count": len(materialized_jobs),
            "required_output_count": len(required_outputs),
            "stale_output_count": stale_count,
            "missing_output_count": missing_count,
            "unknown_freshness_output_count": unknown_count,
            "failed_status_output_count": failed_status_count,
            "unknown_status_output_count": unknown_status_count,
        },
        "jobs": materialized_jobs,
    }


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    project_config_path = Path(args.project_config).resolve()
    out_path = Path(args.out).resolve()
    now = _parse_now(args.now)
    project_cfg = _load_yaml(project_config_path)
    payload = build_payload(project_cfg, now=now, project_config_path=project_config_path)
    write_text_atomic(out_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    repo_root = repo_root_for_published_path(out_path)
    if repo_root is not None:
        write_compile_manifest(repo_root)
    print(f"wrote proof orchestration: {out_path}")
    return 1 if payload.get("status") == "fail" and payload.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
