#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    repo = Path("/docker/chummercomplete/chummer-presentation")
    published_trace = repo / ".codex-studio/published/USER_JOURNEY_TESTER_TRACE.generated.json"
    published_audit = repo / ".codex-studio/published/USER_JOURNEY_TESTER_AUDIT.generated.json"
    published_screenshot_dir = repo / ".codex-studio/published/user-journey-tester-screenshots"

    published_payload: dict[str, object] = {}
    try:
        if published_audit.is_file():
            loaded = json.loads(published_audit.read_text(encoding="utf-8", errors="replace"))
            if isinstance(loaded, dict):
                published_payload = loaded
    except Exception:
        published_payload = {}

    candidates: list[tuple[float, Path, Path, Path, Path, dict[str, object], dict[str, object]]] = []
    tmp_root = repo / ".tmp"
    if tmp_root.is_dir():
        for candidate in tmp_root.glob("user-journey-*"):
            trace_path = candidate / "trace.json"
            audit_path = candidate / "audit.json"
            screenshot_dir = candidate / "screens"
            if not trace_path.is_file() or not audit_path.is_file():
                continue
            try:
                audit_payload = json.loads(audit_path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            if not isinstance(audit_payload, dict):
                continue
            try:
                trace_payload = json.loads(trace_path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                trace_payload = {}
            if not isinstance(trace_payload, dict):
                trace_payload = {}
            candidates.append(
                (
                    float(audit_path.stat().st_mtime),
                    candidate,
                    trace_path,
                    audit_path,
                    screenshot_dir,
                    trace_payload,
                    audit_payload,
                )
            )

    best = max(candidates, key=lambda item: item[0]) if candidates else None
    workflow_ids: list[str] = []
    tmp_screenshot_count = 0
    tmp_tester_shard_id = ""
    tmp_fix_shard_id = ""
    tmp_linux_binary_under_test: object = None
    tmp_used_internal_apis: object = None
    tmp_trace_status = ""
    tmp_audit_status = ""
    tmp_bundle_dir = ""
    tmp_trace_path = ""
    tmp_audit_path = ""
    tmp_screenshot_dir = ""
    if best is not None:
        _, bundle_dir, trace_path, audit_path, screenshot_dir, trace_payload, audit_payload = best
        evidence = audit_payload.get("evidence") if isinstance(audit_payload.get("evidence"), dict) else {}
        workflow_rows = []
        if isinstance(trace_payload.get("workflows"), list):
            workflow_rows = [row for row in trace_payload.get("workflows") if isinstance(row, dict)]
        workflow_ids = [str(row.get("id") or "").strip() for row in workflow_rows if str(row.get("id") or "").strip()]
        tmp_bundle_dir = str(bundle_dir)
        tmp_trace_path = str(trace_path)
        tmp_audit_path = str(audit_path)
        tmp_screenshot_dir = str(screenshot_dir)
        tmp_screenshot_count = len(list(screenshot_dir.glob("*.png"))) if screenshot_dir.is_dir() else 0
        tmp_tester_shard_id = str(evidence.get("tester_shard_id") or trace_payload.get("tester_shard_id") or "").strip()
        tmp_fix_shard_id = str(evidence.get("fix_shard_id") or trace_payload.get("fix_shard_id") or "").strip()
        tmp_linux_binary_under_test = evidence.get("linux_binary_under_test")
        if tmp_linux_binary_under_test is None:
            tmp_linux_binary_under_test = trace_payload.get("linux_binary_under_test")
        tmp_used_internal_apis = evidence.get("used_internal_apis")
        if tmp_used_internal_apis is None:
            tmp_used_internal_apis = trace_payload.get("used_internal_apis")
        tmp_trace_status = str(trace_payload.get("status") or "").strip()
        tmp_audit_status = str(audit_payload.get("status") or "").strip()

    payload = {
        "published_trace_exists": published_trace.is_file(),
        "published_trace_path": str(published_trace),
        "published_audit_path": str(published_audit),
        "published_audit_status": str(published_payload.get("status") or "").strip(),
        "published_audit_reasons": list(published_payload.get("reasons") or [])[:6],
        "published_screenshot_dir": str(published_screenshot_dir),
        "published_screenshot_count": len(list(published_screenshot_dir.glob("*.png"))) if published_screenshot_dir.is_dir() else 0,
        "tmp_bundle_dir": tmp_bundle_dir,
        "tmp_trace_path": tmp_trace_path,
        "tmp_trace_status": tmp_trace_status,
        "tmp_audit_path": tmp_audit_path,
        "tmp_audit_status": tmp_audit_status,
        "tmp_screenshot_dir": tmp_screenshot_dir,
        "tmp_screenshot_count": tmp_screenshot_count,
        "tmp_tester_shard_id": tmp_tester_shard_id,
        "tmp_fix_shard_id": tmp_fix_shard_id,
        "tmp_linux_binary_under_test": tmp_linux_binary_under_test,
        "tmp_used_internal_apis": tmp_used_internal_apis,
        "tmp_workflow_ids": workflow_ids,
    }
    payload["materialize_ready"] = bool(
        payload["tmp_bundle_dir"]
        and payload["tmp_trace_status"].lower() in {"pass", "passed", "ready"}
        and payload["tmp_audit_status"].lower() in {"pass", "passed", "ready"}
        and not payload["published_trace_exists"]
    )
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
