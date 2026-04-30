#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
FLEET_ROOT = Path("/docker/fleet")
PRESENTATION_ROOT = Path("/docker/chummercomplete/chummer-presentation")
UI_PARITY_REPORT = PRESENTATION_ROOT / ".codex-studio" / "published" / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json"
UI_PARITY_REPORT_MD = PRESENTATION_ROOT / ".codex-studio" / "published" / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_helper_module() -> Any:
    helper_path = SCRIPT_DIR / "codexea_gap_fix_workflow.py"
    spec = importlib.util.spec_from_file_location("codexea_gap_fix_workflow", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load helper module from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def main() -> int:
    helper = _load_helper_module()
    release_stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    release_version = f"run-{release_stamp}"
    release_published_at = _now_iso()
    deploy_cmd = (
        "CHUMMER_UI_REPO_ROOT=/docker/chummercomplete/chummer6-ui "
        "CHUMMER_DOWNLOADS_DEPLOY_DIR=/docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads "
        "CHUMMER_DESKTOP_APPS=avalonia "
        "CHUMMER_DESKTOP_RIDS=win-x64 "
        "CHUMMER_RELEASE_CHANNEL=preview "
        f"CHUMMER_RELEASE_VERSION={json.dumps(release_version)} "
        f"CHUMMER_RELEASE_PUBLISHED_AT={json.dumps(release_published_at)} "
        "CHUMMER_GITHUB_RELEASE_PUBLISH=off "
        "bash /docker/fleet/scripts/deploy.sh build-chummer-avalonia-windows-downloads"
    )

    steps: list[dict[str, Any]] = []
    steps.append(helper._run_step("build_avalonia_windows_downloads", deploy_cmd, timeout=5400))
    steps.append(
        helper._run_step(
            "publish_built_bundle_to_portal",
            "RELEASE_VERSION="
            + json.dumps(release_version)
            + " RELEASE_CHANNEL=preview RELEASE_PUBLISHED_AT="
            + json.dumps(release_published_at)
            + " bash /docker/chummercomplete/chummer6-ui/scripts/publish-download-bundle.sh"
            + " /tmp/chummer6-ui-desktop-build/bundle"
            + " /docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads",
            timeout=900,
        )
    )
    steps.append(
        helper._run_step(
            "force_sync_bundle_into_portal",
            f"""{sys.executable} - <<'PY'
from pathlib import Path
import shutil

bundle = Path('/tmp/chummer6-ui-desktop-build/bundle')
deploy = Path('/docker/chummercomplete/chummer.run-services/Chummer.Portal/downloads')
if not bundle.is_dir():
    raise SystemExit('missing bundle dir')
for name in ('releases.json', 'RELEASE_CHANNEL.generated.json'):
    src = bundle / name
    if not src.is_file():
        raise SystemExit(f'missing bundle file: {{src}}')
    deploy.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, deploy / name)
bundle_files = bundle / 'files'
if not bundle_files.is_dir():
    raise SystemExit('missing bundle files dir')
deploy_files = deploy / 'files'
deploy_files.mkdir(parents=True, exist_ok=True)
for stale in deploy_files.glob('chummer-*'):
    if stale.is_file():
        stale.unlink()
for src in bundle_files.iterdir():
    if src.is_file():
        shutil.copy2(src, deploy_files / src.name)
bundle_smoke = bundle / 'startup-smoke'
if bundle_smoke.is_dir():
    deploy_smoke = deploy / 'startup-smoke'
    deploy_smoke.mkdir(parents=True, exist_ok=True)
    for src in bundle_smoke.iterdir():
        if src.is_file():
            shutil.copy2(src, deploy_smoke / src.name)
print('ok')
PY""",
            timeout=180,
        )
    )

    sync_result = helper._sync_promoted_release_mirrors()
    sync_result["name"] = "sync_promoted_release_mirrors"
    steps.append(sync_result)

    steps.append(
        helper._run_step(
            "desktop_visual_familiarity_exit_gate",
            "CHUMMER_DESKTOP_VISUAL_SKIP_RELEASE_GATE_LOCK_WAIT=1 bash /docker/chummercomplete/chummer-presentation/scripts/ai/milestones/materialize-desktop-visual-familiarity-exit-gate.sh",
            timeout=600,
        )
    )
    steps.append(
        helper._run_step(
            "desktop_workflow_execution_gate",
            "bash /docker/chummercomplete/chummer-presentation/scripts/ai/milestones/materialize-desktop-workflow-execution-gate.sh",
            timeout=600,
        )
    )
    steps.append(
        helper._run_step(
            "windows_desktop_exit_gate",
            "CHUMMER_WINDOWS_DESKTOP_EXIT_GATE_APP_KEY=avalonia CHUMMER_WINDOWS_DESKTOP_EXIT_GATE_RID=win-x64 bash /docker/chummercomplete/chummer-presentation/scripts/materialize-windows-desktop-exit-gate.sh",
            timeout=300,
        )
    )
    steps.append(
        helper._run_step(
            "desktop_executable_exit_gate",
            "CHUMMER_DESKTOP_EXECUTABLE_SKIP_DEPENDENCY_MATERIALIZE=1 "
            "CHUMMER_DESKTOP_EXECUTABLE_SKIP_RELEASE_GATE_LOCK_WAIT=1 "
            "bash /docker/chummercomplete/chummer-presentation/scripts/ai/milestones/materialize-desktop-executable-exit-gate.sh",
            timeout=600,
        )
    )
    steps.append(
        helper._run_step(
            "ui_verify",
            "cd /docker/chummercomplete/chummer-presentation && bash scripts/ai/verify.sh",
            timeout=1800,
        )
    )
    steps.append(
        helper._run_step(
            "ui_parity_audit",
            f"{sys.executable} /docker/fleet/scripts/codex-shims/codexea_ui_parity_audit_probe.py",
            timeout=180,
        )
    )
    steps.append(
        helper._run_step(
            "flagship_product_readiness",
            f"{sys.executable} /docker/fleet/scripts/materialize_flagship_product_readiness.py",
            timeout=300,
        )
    )
    steps.append(helper._refresh_full_product_frontier())

    statuses = {
        "release_channel": helper._artifact_status(helper.RELEASE_CHANNEL_DST),
        "visual_gate": helper._artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"),
        "workflow_gate": helper._artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"),
        "windows_gate": helper._artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"),
        "desktop_executable_gate": helper._artifact_status(PRESENTATION_ROOT / ".codex-studio" / "published" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"),
        "flagship_readiness": helper._artifact_status(FLEET_ROOT / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"),
    }
    parity_report = _read_json(UI_PARITY_REPORT)
    parity_summary = parity_report.get("summary") if isinstance(parity_report.get("summary"), dict) else {}
    readiness = _read_json(FLEET_ROOT / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json")
    state = _read_json(FLEET_ROOT / "state" / "chummer_design_supervisor" / "state.json")

    applied_steps = [str(step.get("name") or "").strip() for step in steps if str(step.get("status") or "").strip().lower() == "pass"]
    remaining_findings: list[dict[str, str]] = []

    parity_findings = parity_report.get("findings") if isinstance(parity_report.get("findings"), list) else []
    for item in parity_findings[:8]:
        if not isinstance(item, dict):
            continue
        remaining_findings.append(
            {
                "severity": str(item.get("severity") or "medium").strip() or "medium",
                "category": str(item.get("category") or "parity_gap").strip() or "parity_gap",
                "summary": str(item.get("summary") or "").strip(),
                "detail": str(item.get("detail") or "").strip(),
            }
        )

    windows_gate = statuses.get("windows_gate") if isinstance(statuses.get("windows_gate"), dict) else {}
    if str(windows_gate.get("status") or "").strip().lower() not in {"pass", "passed", "ready"}:
        remaining_findings.insert(
            0,
            {
                "severity": "high",
                "category": "workflow_gate_gap",
                "summary": "Windows desktop exit proof is still blocking honest full parity closure.",
                "detail": str(windows_gate.get("reason_0") or "").strip(),
            },
        )

    compact_steps = [helper._compact_step_result(step) for step in steps]
    payload = {
        "probe_kind": "parity_build",
        "generated_at": _now_iso(),
        "release_version": release_version,
        "release_published_at": release_published_at,
        "applied_steps": applied_steps,
        "step_results": compact_steps,
        "status_summary": statuses,
        "parity_report_path": str(UI_PARITY_REPORT),
        "parity_report_markdown_path": str(UI_PARITY_REPORT_MD),
        "parity_summary": parity_summary,
        "remaining_findings": remaining_findings,
        "coverage_gap_keys": list(parity_summary.get("coverage_gap_keys") or []),
        "active_runs_count": int(state.get("active_runs_count") or 0),
        "productive_active_runs_count": int(state.get("productive_active_runs_count") or 0),
        "nonproductive_active_runs_count": int(state.get("nonproductive_active_runs_count") or 0),
        "readiness_status": str(readiness.get("status") or "").strip(),
    }
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
