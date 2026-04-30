#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PORTAL_DOWNLOADS = Path("/docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads")
PRESENTATION_ROOT = Path("/docker/chummercomplete/chummer-presentation")
UI_ALIAS_ROOT = Path("/docker/chummercomplete/chummer6-ui")
UI_ROOT = UI_ALIAS_ROOT if UI_ALIAS_ROOT.exists() else PRESENTATION_ROOT
HUB_ROOT = Path("/docker/chummercomplete/chummer-hub-registry")
FLEET_ROOT = Path("/docker/fleet")

RELEASE_CHANNEL_SRC = PORTAL_DOWNLOADS / "RELEASE_CHANNEL.generated.json"
RELEASES_JSON_SRC = PORTAL_DOWNLOADS / "releases.json"
RELEASE_CHANNEL_DST = HUB_ROOT / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json"
RELEASES_JSON_DST = HUB_ROOT / ".codex-studio" / "published" / "releases.json"
UI_RELEASE_CHANNEL_DST = UI_ROOT / "Docker" / "Downloads" / "RELEASE_CHANNEL.generated.json"
UI_RELEASES_JSON_DST = UI_ROOT / "Docker" / "Downloads" / "releases.json"
HUB_STARTUP_SMOKE_DST = HUB_ROOT / ".codex-studio" / "published" / "startup-smoke"
UI_STARTUP_SMOKE_DST = UI_ROOT / "Docker" / "Downloads" / "startup-smoke"
UI_FILES_DST = UI_ROOT / "Docker" / "Downloads" / "files"
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _excerpt(value: str, *, max_lines: int = 20, max_chars: int = 2400) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines.append("...")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text


def _textify(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _sync_promoted_release_mirrors() -> dict[str, Any]:
    release_channel = _read_json(RELEASE_CHANNEL_SRC)
    copied_files: list[str] = []
    copied_startup_smoke: list[str] = []

    _copy_file(RELEASE_CHANNEL_SRC, RELEASE_CHANNEL_DST)
    _copy_file(RELEASES_JSON_SRC, RELEASES_JSON_DST)
    _copy_file(RELEASE_CHANNEL_SRC, UI_RELEASE_CHANNEL_DST)
    _copy_file(RELEASES_JSON_SRC, UI_RELEASES_JSON_DST)

    for root in (HUB_STARTUP_SMOKE_DST, UI_STARTUP_SMOKE_DST):
        root.mkdir(parents=True, exist_ok=True)
    for src in sorted((PORTAL_DOWNLOADS / "startup-smoke").glob("*")):
        if not src.is_file():
            continue
        for dst_root in (HUB_STARTUP_SMOKE_DST, UI_STARTUP_SMOKE_DST):
            dst = dst_root / src.name
            _copy_file(src, dst)
        copied_startup_smoke.append(src.name)

    artifacts = release_channel.get("artifacts")
    if isinstance(artifacts, list):
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            download_url = str(item.get("downloadUrl") or "").strip()
            if not download_url.startswith("/downloads/files/"):
                continue
            rel = download_url.removeprefix("/downloads/").lstrip("/")
            src = PORTAL_DOWNLOADS / rel
            if not src.is_file():
                continue
            dst = UI_ROOT / "Docker" / "Downloads" / rel
            _copy_file(src, dst)
            copied_files.append(rel)

    return {
        "status": "pass",
        "portal_release_channel_version": str(release_channel.get("version") or "").strip(),
        "release_channel_target_count": 4,
        "artifact_file_count": len(copied_files),
        "startup_smoke_file_count": len(copied_startup_smoke),
    }


def _run_step(name: str, cmd: str, *, timeout: int = 300, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    merged_env = dict(env or {})
    process = subprocess.Popen(
        ["/bin/bash", "-lc", cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, **merged_env},
        start_new_session=True,
    )
    try:
        stdout_text, stderr_text = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            stdout_text, stderr_text = process.communicate(timeout=5)
        except Exception:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except Exception:
                pass
            stdout_text, stderr_text = process.communicate()
        return {
            "name": name,
            "status": "timeout",
            "timeout_seconds": timeout,
            "duration_seconds": round(time.monotonic() - started, 2),
            "cmd": cmd,
            "stdout_excerpt": _excerpt(_textify(exc.stdout) + _textify(stdout_text)),
            "stderr_excerpt": _excerpt(_textify(exc.stderr) + _textify(stderr_text)),
        }
    return {
        "name": name,
        "status": "pass" if process.returncode == 0 else "fail",
        "returncode": int(process.returncode or 0),
        "duration_seconds": round(time.monotonic() - started, 2),
        "cmd": cmd,
        "stdout_excerpt": _excerpt(stdout_text),
        "stderr_excerpt": _excerpt(stderr_text),
    }


def _artifact_status(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    reasons = payload.get("reasons") or payload.get("blockingFindings") or payload.get("blocking_findings") or []
    rows = [str(item).strip() for item in reasons if str(item).strip()]
    return {
        "path": str(path),
        "status": str(payload.get("status") or "").strip(),
        "generated_at": str(payload.get("generated_at") or payload.get("generatedAt") or "").strip(),
        "reason_0": rows[0] if rows else "",
        "reason_count": len(rows),
    }


def _refresh_full_product_frontier() -> dict[str, Any]:
    script_root = str(FLEET_ROOT / "scripts")
    python_script = (
        "import json, sys; "
        f"sys.path.insert(0, {script_root!r}); "
        "from pathlib import Path; "
        "import chummer_design_supervisor as m; "
        "state_root = Path('/docker/fleet/state/chummer_design_supervisor').resolve(); "
        "args = m._runtime_snapshot_args_for_state_root(state_root); "
        "base = m.derive_context(args); "
        "ctx = m.derive_flagship_product_context(args, state_root, base_context=base); "
        "print(json.dumps({'frontier_ids': ctx.get('frontier_ids') or []}, ensure_ascii=True, separators=(',', ':')))"
    )
    result = _run_step(
        "refresh_full_product_frontier",
        f"{sys.executable} -c {json.dumps(python_script)}",
        timeout=180,
    )
    if str(result.get("status") or "").strip().lower() == "pass":
        payload = _read_yaml(FLEET_ROOT / ".codex-studio" / "published" / "FULL_PRODUCT_FRONTIER.generated.yaml")
        if isinstance(payload, dict):
            frontier = payload.get("frontier")
            if isinstance(frontier, list):
                result["frontier_count"] = len(frontier)
    return result


def _compact_step_result(step: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "name": str(step.get("name") or "").strip(),
        "status": str(step.get("status") or "").strip(),
    }
    for key in ("duration_seconds", "returncode", "timeout_seconds", "portal_release_channel_version"):
        if key in step:
            compact[key] = step.get(key)
    if "artifact_file_count" in step:
        compact["artifact_file_count"] = step.get("artifact_file_count")
    if "startup_smoke_file_count" in step:
        compact["startup_smoke_file_count"] = step.get("startup_smoke_file_count")
    if "release_channel_target_count" in step:
        compact["release_channel_target_count"] = step.get("release_channel_target_count")
    status = str(step.get("status") or "").strip().lower()
    if status in {"fail", "timeout"}:
        stdout_excerpt = str(step.get("stdout_excerpt") or "").strip()
        stderr_excerpt = str(step.get("stderr_excerpt") or "").strip()
        if stdout_excerpt:
            compact["stdout_excerpt"] = stdout_excerpt
        if stderr_excerpt:
            compact["stderr_excerpt"] = stderr_excerpt
    return compact


def main() -> int:
    steps: list[dict[str, Any]] = []
    sync_result = _sync_promoted_release_mirrors()
    sync_result["name"] = "sync_promoted_release_mirrors"
    steps.append(sync_result)

    steps.append(
        _run_step(
            "chummer5a_desktop_workflow_parity",
            "bash /docker/chummercomplete/chummer-presentation/scripts/ai/milestones/chummer5a-desktop-workflow-parity-check.sh",
            timeout=300,
        )
    )
    steps.append(
        _run_step(
            "sr4_desktop_workflow_parity",
            "bash /docker/chummercomplete/chummer-presentation/scripts/ai/milestones/sr4-desktop-workflow-parity-check.sh",
            timeout=300,
        )
    )
    steps.append(
        _run_step(
            "sr6_desktop_workflow_parity",
            "bash /docker/chummercomplete/chummer-presentation/scripts/ai/milestones/sr6-desktop-workflow-parity-check.sh",
            timeout=300,
        )
    )
    steps.append(
        _run_step(
            "desktop_visual_familiarity_exit_gate",
            "CHUMMER_DESKTOP_VISUAL_SKIP_RELEASE_GATE_LOCK_WAIT=1 bash /docker/chummercomplete/chummer-presentation/scripts/ai/milestones/materialize-desktop-visual-familiarity-exit-gate.sh",
            timeout=300,
        )
    )
    steps.append(
        _run_step(
            "desktop_workflow_execution_gate",
            "bash /docker/chummercomplete/chummer-presentation/scripts/ai/milestones/materialize-desktop-workflow-execution-gate.sh",
            timeout=300,
        )
    )
    steps.append(
        _run_step(
            "windows_desktop_exit_gate",
            "CHUMMER_WINDOWS_DESKTOP_EXIT_GATE_APP_KEY=avalonia CHUMMER_WINDOWS_DESKTOP_EXIT_GATE_RID=win-x64 bash /docker/chummercomplete/chummer-presentation/scripts/materialize-windows-desktop-exit-gate.sh",
            timeout=120,
        )
    )
    steps.append(
        _run_step(
            "flagship_product_readiness",
            f"{sys.executable} /docker/fleet/scripts/materialize_flagship_product_readiness.py",
            timeout=180,
        )
    )
    steps.append(_refresh_full_product_frontier())

    statuses = {
        "release_channel": _artifact_status(RELEASE_CHANNEL_DST),
        "chummer5a_workflow_parity": _artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"),
        "sr4_workflow_parity": _artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"),
        "sr6_workflow_parity": _artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"),
        "sr4_sr6_frontier": _artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"),
        "visual_gate": _artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"),
        "workflow_gate": _artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"),
        "windows_gate": _artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"),
        "linux_gate": _artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"),
        "macos_gate": _artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "UI_MACOS_AVALONIA_OSX_ARM64_DESKTOP_EXIT_GATE.generated.json"),
        "desktop_executable_gate": _artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"),
        "flagship_readiness": _artifact_status(FLEET_ROOT / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"),
    }
    readiness = _read_json(FLEET_ROOT / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json")
    state = _read_json(FLEET_ROOT / "state" / "chummer_design_supervisor" / "state.json")

    applied_steps = [str(step.get("name") or "").strip() for step in steps if str(step.get("status") or "").strip() == "pass"]
    remaining_findings: list[dict[str, str]] = []
    windows_gate = statuses.get("windows_gate") if isinstance(statuses.get("windows_gate"), dict) else {}
    if str(windows_gate.get("status") or "").strip().lower() not in {"pass", "passed", "ready"}:
        remaining_findings.append(
            {
                "severity": "high",
                "category": "workflow_gate_gap",
                "summary": "Windows desktop proof is still blocked by startup-smoke freshness or installer-byte mismatch.",
                "detail": str(windows_gate.get("reason_0") or "").strip(),
            }
        )
    desktop_gate = statuses.get("desktop_executable_gate") if isinstance(statuses.get("desktop_executable_gate"), dict) else {}
    if str(desktop_gate.get("status") or "").strip().lower() not in {"pass", "passed", "ready"}:
        remaining_findings.append(
            {
                "severity": "high",
                "category": "workflow_gate_gap",
                "summary": "The top-level desktop executable gate is still failing on platform proof closure.",
                "detail": str(desktop_gate.get("reason_0") or "").strip(),
            }
        )
    coverage = readiness.get("coverage") if isinstance(readiness.get("coverage"), dict) else {}
    warning_keys = [key for key, value in coverage.items() if str(value or "").strip().lower() in {"warning", "missing"}]
    if warning_keys:
        remaining_findings.append(
            {
                "severity": "medium",
                "category": "design_gap",
                "summary": "Remaining flagship coverage keys are still open after the proof refresh pass.",
                "detail": ", ".join(warning_keys),
            }
        )
    productive = int(state.get("productive_active_runs_count") or 0)
    nonproductive = int(state.get("nonproductive_active_runs_count") or 0)
    if nonproductive > 0:
        remaining_findings.append(
            {
                "severity": "medium",
                "category": "shard_gap",
                "summary": "Some live shard runs are still nonproductive after the proof refresh pass.",
                "detail": f"productive={productive}, nonproductive={nonproductive}",
            }
        )
    notes = [
        "The control-plane fix path refreshed the canonical release channel, mirrored promoted shelf bytes, and re-materialized the fast parity and visual/workflow proof receipts.",
        "No missing flagship milestone materialization was targeted here; this pass focuses on proof and gate closure rather than backlog expansion.",
    ]

    payload = {
        "probe_kind": "gap_fix",
        "generated_at": _now_iso(),
        "applied_steps": applied_steps,
        "step_results": [_compact_step_result(step) for step in steps],
        "status_summary": statuses,
        "readiness_coverage": readiness.get("coverage") if isinstance(readiness.get("coverage"), dict) else {},
        "active_runs_count": int(state.get("active_runs_count") or 0),
        "productive_active_runs_count": int(state.get("productive_active_runs_count") or 0),
        "nonproductive_active_runs_count": int(state.get("nonproductive_active_runs_count") or 0),
        "remaining_findings": remaining_findings,
        "notes": notes,
    }
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
