#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
PRODUCT_MIRROR = Path("/docker/chummercomplete/chummer-design/products/chummer")
UI_PUBLISHED = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published")
HUB_REGISTRY_PUBLISHED = Path("/docker/chummercomplete/chummer-hub-registry/.codex-studio/published")

PACKAGE_ID = "next90-m144-fleet-fail-closeout-when-desktop-client-readiness-is-green-without-matching"
FRONTIER_ID = 4185937434
MILESTONE_ID = 144
WORK_TASK_ID = "144.4"
WAVE_ID = "W22P"
QUEUE_TITLE = "Fail closeout when desktop-client readiness is green without matching executable-gate, startup-smoke, and release-channel tuple proof."
OWNED_SURFACES = ["fail_closeout_when_desktop_client_readiness_is_green_wit:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M144_FLEET_DESKTOP_PROOF_INTEGRITY_CLOSEOUT_GATES.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M144_FLEET_DESKTOP_PROOF_INTEGRITY_CLOSEOUT_GATES.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
FLEET_QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
FLAGSHIP_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"
UI_WINDOWS_EXIT_GATE = UI_PUBLISHED / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
DESKTOP_EXECUTABLE_EXIT_GATE = UI_PUBLISHED / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
RELEASE_CHANNEL = HUB_REGISTRY_PUBLISHED / "RELEASE_CHANNEL.generated.json"

GUIDE_MARKERS = {
    "wave_22p": "## Wave 22P - close human-tested parity proof and desktop executable trust before successor breadth",
    "milestone_144": "### 144. Desktop executable proof integrity and publishable flagship-route closure",
    "exit_contract": "Exit: Windows, Linux, and macOS promoted desktop tuples have matching startup-smoke receipts, executable-gate proof, release-channel tuple truth, and `desktop_client` readiness with no stale or inherited trust.",
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M144 desktop proof integrity closeout gate packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--fleet-queue-staging", default=str(FLEET_QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
    parser.add_argument("--ui-windows-exit-gate", default=str(UI_WINDOWS_EXIT_GATE))
    parser.add_argument("--desktop-executable-exit-gate", default=str(DESKTOP_EXECUTABLE_EXIT_GATE))
    parser.add_argument("--release-channel", default=str(RELEASE_CHANNEL))
    parser.add_argument("--startup-smoke-receipt", default="")
    return parser.parse_args(argv)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [_normalize_text(value) for value in values if _normalize_text(value)]


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        payload = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        marker = "\nitems:\n"
        if marker not in raw:
            return {}
        try:
            payload = yaml.safe_load("items:\n" + raw.split(marker, 1)[1]) or {}
        except yaml.YAMLError:
            return {}
    return payload if isinstance(payload, dict) else {}


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _parse_generated_at(path: Path, payload: Dict[str, Any]) -> tuple[str, str]:
    generated_at = _normalize_text(payload.get("generated_at") or payload.get("generatedAt"))
    if generated_at:
        return generated_at, "payload"
    try:
        fallback = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
    except OSError:
        return "", ""
    return fallback, "file_mtime"


def _parse_iso_utc(value: str) -> Optional[dt.datetime]:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except ValueError:
        return None


def _source_link(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    generated_at, generated_at_source = _parse_generated_at(path, payload)
    return {
        "path": _display_path(path),
        "sha256": _sha256_file(path),
        "generated_at": generated_at,
        "generated_at_source": generated_at_source,
    }


def _write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _find_milestone(registry: Dict[str, Any], milestone_id: int) -> Dict[str, Any]:
    for row in registry.get("milestones") or []:
        if isinstance(row, dict) and int(row.get("id") or 0) == milestone_id:
            return dict(row)
    return {}


def _find_work_task(milestone: Dict[str, Any], work_task_id: str) -> Dict[str, Any]:
    for row in milestone.get("work_tasks") or []:
        if isinstance(row, dict) and _normalize_text(row.get("id")) == work_task_id:
            return dict(row)
    return {}


def _find_queue_item(queue: Dict[str, Any], work_task_id: str) -> Dict[str, Any]:
    for row in queue.get("items") or []:
        if isinstance(row, dict) and _normalize_text(row.get("work_task_id")) == work_task_id:
            return dict(row)
    return {}


def _marker_monitor(text: str, markers: Dict[str, str], *, label: str) -> Dict[str, Any]:
    checks = {name: marker in text for name, marker in markers.items()}
    issues = [f"{label} missing required marker: {name}" for name, present in checks.items() if not present]
    return {"state": "pass" if not issues else "fail", "checks": checks, "issues": issues}


def _queue_alignment(*, work_task: Dict[str, Any], fleet_queue_item: Dict[str, Any], design_queue_item: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    if not work_task:
        issues.append("Canonical registry work task is missing.")
    if not design_queue_item:
        issues.append("Design queue row is missing.")
    if not fleet_queue_item:
        warnings.append("Fleet queue mirror row is still missing for work task 144.4.")
    expected = {
        "title": QUEUE_TITLE,
        "task": QUEUE_TITLE,
        "package_id": PACKAGE_ID,
        "work_task_id": WORK_TASK_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "wave": WAVE_ID,
        "repo": "fleet",
    }
    if work_task and _normalize_text(work_task.get("owner")) != "fleet":
        issues.append("Canonical registry work task owner drifted from fleet.")
    for label, row in (("design", design_queue_item), ("fleet", fleet_queue_item)):
        if not row:
            continue
        for field, expected_value in expected.items():
            if _normalize_text(row.get(field)) != _normalize_text(expected_value):
                message = f"{label.title()} queue {field} drifted."
                if label == "design":
                    issues.append(message)
                else:
                    warnings.append(message)
        if _normalize_list(row.get("allowed_paths")) != ALLOWED_PATHS:
            message = f"{label.title()} queue allowed_paths drifted."
            if label == "design":
                issues.append(message)
            else:
                warnings.append(message)
        if _normalize_list(row.get("owned_surfaces")) != OWNED_SURFACES:
            message = f"{label.title()} queue owned_surfaces drifted."
            if label == "design":
                issues.append(message)
            else:
                warnings.append(message)
    return {"state": "pass" if not issues else "fail", "issues": issues, "warnings": warnings}


def _normalize_status(value: Any) -> str:
    return _normalize_text(value).lower()


def _artifact_status_ok(value: Any) -> bool:
    return _normalize_status(value) in {"pass", "passed", "published", "ready"}


def _flagship_monitor(flagship_readiness: Dict[str, Any]) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    coverage = dict(flagship_readiness.get("coverage") or {})
    details = dict((flagship_readiness.get("coverage_details") or {}).get("desktop_client") or {})
    evidence = dict(details.get("evidence") or {})
    status = _normalize_status(flagship_readiness.get("status"))
    desktop_status = _normalize_status(coverage.get("desktop_client"))
    if status != "pass":
        runtime_blockers.append("FLAGSHIP_PRODUCT_READINESS status is not `pass`.")
    if desktop_status != "ready":
        runtime_blockers.append("FLAGSHIP_PRODUCT_READINESS coverage.desktop_client is not `ready`.")
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "flagship_status": status,
        "desktop_client_status": desktop_status,
        "desktop_evidence": evidence,
    }


def _find_windows_release_artifact(release_channel: Dict[str, Any]) -> Dict[str, Any]:
    promoted = [
        dict(row)
        for row in (dict(release_channel.get("desktopTupleCoverage") or {}).get("promotedInstallerTuples") or [])
        if isinstance(row, dict) and _normalize_status(row.get("platform")) == "windows"
    ]
    artifact_id = _normalize_text(promoted[0].get("artifactId")) if promoted else ""
    for row in release_channel.get("artifacts") or []:
        if isinstance(row, dict) and (
            _normalize_text(row.get("artifactId")) == artifact_id
            or (
                _normalize_status(row.get("platform")) == "windows"
                and _normalize_status(row.get("kind")) == "installer"
                and _normalize_status(row.get("head")) == "avalonia"
            )
        ):
            return dict(row)
    return {}


def _release_channel_monitor(release_channel: Dict[str, Any]) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    coverage = dict(release_channel.get("desktopTupleCoverage") or {})
    if _normalize_status(release_channel.get("status")) != "published":
        runtime_blockers.append("RELEASE_CHANNEL status is not `published`.")
    for key in ("missingRequiredPlatforms", "missingRequiredPlatformHeadPairs", "missingRequiredPlatformHeadRidTuples"):
        if coverage.get(key):
            runtime_blockers.append(f"RELEASE_CHANNEL desktopTupleCoverage.{key} is not empty.")
    if coverage.get("complete") is False:
        runtime_blockers.append("RELEASE_CHANNEL desktopTupleCoverage.complete is false.")
    windows_artifact = _find_windows_release_artifact(release_channel)
    if not windows_artifact:
        runtime_blockers.append("RELEASE_CHANNEL is missing the promoted Windows installer tuple artifact.")
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "windows_artifact": windows_artifact,
        "release_channel_version": _normalize_text(release_channel.get("version")),
        "release_channel_generated_at": _normalize_text(release_channel.get("generated_at") or release_channel.get("generatedAt")),
    }


def _windows_gate_monitor(
    windows_gate: Dict[str, Any],
    *,
    startup_smoke_receipt: Dict[str, Any],
    windows_artifact: Dict[str, Any],
    release_channel_version: str,
) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    checks = dict(windows_gate.get("checks") or {})
    if not _artifact_status_ok(windows_gate.get("status")):
        runtime_blockers.append("UI_WINDOWS_DESKTOP_EXIT_GATE status is not passing.")
    if not bool(checks.get("installer_exists")):
        runtime_blockers.append("UI_WINDOWS_DESKTOP_EXIT_GATE no longer resolves a current promoted Windows installer.")
    if not bool(checks.get("startup_smoke_receipt_found")):
        runtime_blockers.append("UI_WINDOWS_DESKTOP_EXIT_GATE cannot find the Windows startup-smoke receipt.")
    if _normalize_status(checks.get("startup_smoke_status")) != "pass":
        runtime_blockers.append("Windows startup-smoke receipt status is not `pass`.")
    expected_digest = _normalize_text(checks.get("expected_startup_smoke_artifact_digest"))
    startup_digest = _normalize_text(checks.get("startup_smoke_artifact_digest"))
    installer_sha = _normalize_text(checks.get("installer_sha256"))
    release_sha = _normalize_text(windows_artifact.get("sha256"))
    if expected_digest and startup_digest and startup_digest != expected_digest:
        runtime_blockers.append("Windows startup-smoke artifact digest no longer matches the expected promoted digest.")
    if release_sha and installer_sha and installer_sha != release_sha:
        runtime_blockers.append("Windows installer sha256 no longer matches the promoted release-channel artifact.")
    if startup_digest and release_sha and startup_digest != f"sha256:{release_sha}":
        runtime_blockers.append("Windows startup-smoke receipt digest no longer matches the promoted release-channel artifact.")
    release_size = windows_artifact.get("sizeBytes")
    installer_size = checks.get("installer_size_bytes")
    if isinstance(release_size, int) and isinstance(installer_size, int) and release_size != installer_size:
        runtime_blockers.append("Windows installer byte count no longer matches the promoted release-channel artifact.")
    startup_version = _normalize_text(checks.get("startup_smoke_version") or startup_smoke_receipt.get("version"))
    receipt_version = _normalize_text(startup_smoke_receipt.get("version") or startup_smoke_receipt.get("releaseVersion"))
    artifact_version = _normalize_text(windows_artifact.get("releaseVersion") or windows_artifact.get("version"))
    checks_version = _normalize_text(checks.get("release_channel_version"))
    if release_channel_version and checks_version and checks_version != release_channel_version:
        runtime_blockers.append(
            f"UI_WINDOWS_DESKTOP_EXIT_GATE still cites release channel version `{checks_version}` while live RELEASE_CHANNEL is `{release_channel_version}`."
        )
    if release_channel_version and startup_version and startup_version != release_channel_version:
        runtime_blockers.append(
            f"Windows startup-smoke receipt version `{startup_version}` no longer matches live RELEASE_CHANNEL version `{release_channel_version}`."
        )
    if artifact_version and startup_version and artifact_version != startup_version:
        runtime_blockers.append(
            f"Windows startup-smoke receipt version `{startup_version}` does not match the promoted Windows artifact version `{artifact_version}`."
        )
    ready_checkpoint = _normalize_text(checks.get("startup_smoke_ready_checkpoint") or startup_smoke_receipt.get("readyCheckpoint"))
    if not ready_checkpoint:
        runtime_blockers.append("Windows startup-smoke receipt readyCheckpoint is missing.")
    age_seconds = checks.get("startup_smoke_age_seconds")
    max_age_seconds = checks.get("startup_smoke_max_age_seconds")
    if isinstance(age_seconds, (int, float)) and isinstance(max_age_seconds, (int, float)) and age_seconds > max_age_seconds:
        runtime_blockers.append(
            f"Windows startup-smoke receipt is stale at {int(age_seconds)}s, exceeding the {int(max_age_seconds)}s budget."
        )
    if receipt_version and startup_version and receipt_version != startup_version:
        runtime_blockers.append("Windows startup-smoke receipt version drifted from the Windows exit gate checks.")
    if startup_digest and _normalize_text(startup_smoke_receipt.get("artifactDigest")) and _normalize_text(startup_smoke_receipt.get("artifactDigest")) != startup_digest:
        runtime_blockers.append("Windows startup-smoke receipt digest drifted from the Windows exit gate checks.")
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "checks": checks,
    }


def _executable_gate_monitor(
    executable_gate: Dict[str, Any],
    *,
    release_channel_version: str,
) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    evidence = dict(executable_gate.get("evidence") or {})
    if _normalize_status(executable_gate.get("status")) != "pass":
        runtime_blockers.append("DESKTOP_EXECUTABLE_EXIT_GATE status is not `pass`.")
    local_blocking_findings_count = executable_gate.get("local_blocking_findings_count")
    if not isinstance(local_blocking_findings_count, int):
        local_blocking_findings_count = executable_gate.get("localBlockingFindingsCount")
    if isinstance(local_blocking_findings_count, int) and local_blocking_findings_count != 0:
        runtime_blockers.append(
            f"DESKTOP_EXECUTABLE_EXIT_GATE local_blocking_findings_count is `{local_blocking_findings_count}` instead of `0`."
        )
    gate_release_channel_version = _normalize_text(evidence.get("release_channel_version"))
    if release_channel_version and gate_release_channel_version and gate_release_channel_version != release_channel_version:
        runtime_blockers.append(
            f"DESKTOP_EXECUTABLE_EXIT_GATE still cites release channel version `{gate_release_channel_version}` while live RELEASE_CHANNEL is `{release_channel_version}`."
        )
    if evidence.get("desktopTupleCoverage.missingRequiredPlatforms_normalized"):
        runtime_blockers.append("DESKTOP_EXECUTABLE_EXIT_GATE still reports missing required desktop platforms.")
    if evidence.get("desktopTupleCoverage.missingRequiredPlatformHeadPairs_normalized"):
        runtime_blockers.append("DESKTOP_EXECUTABLE_EXIT_GATE still reports missing required platform/head pairs.")
    if evidence.get("desktopTupleCoverage.missingRequiredPlatformHeadRidTuples_normalized"):
        runtime_blockers.append("DESKTOP_EXECUTABLE_EXIT_GATE still reports missing required platform/head/rid tuples.")
    return {
        "state": "pass",
        "issues": [],
        "runtime_blockers": runtime_blockers,
        "evidence": evidence,
        "local_blocking_findings_count": int(local_blocking_findings_count or 0),
    }


def _consistency_monitor(
    flagship_monitor: Dict[str, Any],
    *,
    windows_gate: Dict[str, Any],
    executable_gate: Dict[str, Any],
    release_channel: Dict[str, Any],
    windows_artifact: Dict[str, Any],
) -> Dict[str, Any]:
    runtime_blockers: List[str] = []
    desktop_evidence = dict(flagship_monitor.get("desktop_evidence") or {})
    release_channel_version = _normalize_text(release_channel.get("version"))
    flagship_release_channel_version = _normalize_text(desktop_evidence.get("release_channel_version"))
    if release_channel_version and flagship_release_channel_version and flagship_release_channel_version != release_channel_version:
        runtime_blockers.append(
            f"FLAGSHIP_PRODUCT_READINESS still cites release channel version `{flagship_release_channel_version}` while live RELEASE_CHANNEL is `{release_channel_version}`."
        )
    if _normalize_text(desktop_evidence.get("ui_windows_exit_gate_status")).lower() not in {"", _normalize_status(windows_gate.get("status"))}:
        runtime_blockers.append("FLAGSHIP_PRODUCT_READINESS desktop_client evidence disagrees with the live Windows exit gate status.")
    if _normalize_text(desktop_evidence.get("ui_executable_exit_gate_status")).lower() not in {"", _normalize_status(executable_gate.get("status"))}:
        runtime_blockers.append("FLAGSHIP_PRODUCT_READINESS desktop_client evidence disagrees with the live desktop executable gate status.")
    recorded_local_blockers = desktop_evidence.get("ui_executable_exit_gate_local_blocking_findings_count")
    live_local_blockers = executable_gate.get("local_blocking_findings_count")
    if isinstance(recorded_local_blockers, int) and isinstance(live_local_blockers, int) and recorded_local_blockers != live_local_blockers:
        runtime_blockers.append("FLAGSHIP_PRODUCT_READINESS desktop_client evidence still carries a stale executable local blocking count.")
    release_generated = _parse_iso_utc(_normalize_text(release_channel.get("generated_at") or release_channel.get("generatedAt")))
    windows_generated = _parse_iso_utc(_normalize_text(windows_gate.get("generated_at") or windows_gate.get("generatedAt")))
    if release_generated and windows_generated and release_generated > windows_generated:
        live_version = _normalize_text(windows_artifact.get("releaseVersion") or windows_artifact.get("version"))
        gate_version = _normalize_text(dict(windows_gate.get("checks") or {}).get("release_channel_version"))
        if live_version and gate_version and live_version != gate_version:
            runtime_blockers.append("Windows tuple proof is older than the live release-channel publish and is still carrying forward stale promoted-version truth.")
    return {"state": "pass", "issues": [], "runtime_blockers": runtime_blockers}


def build_payload(
    *,
    registry_path: Path,
    fleet_queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    flagship_readiness_path: Path,
    ui_windows_exit_gate_path: Path,
    desktop_executable_exit_gate_path: Path,
    release_channel_path: Path,
    startup_smoke_receipt_path: Optional[Path] = None,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    registry = _load_yaml(registry_path)
    fleet_queue = _load_yaml(fleet_queue_path)
    design_queue = _load_yaml(design_queue_path)
    next90_guide = next90_guide_path.read_text(encoding="utf-8") if next90_guide_path.is_file() else ""
    flagship_readiness = _load_json(flagship_readiness_path)
    ui_windows_exit_gate = _load_json(ui_windows_exit_gate_path)
    desktop_executable_exit_gate = _load_json(desktop_executable_exit_gate_path)
    release_channel = _load_json(release_channel_path)

    checks = dict(ui_windows_exit_gate.get("checks") or {})
    effective_startup_smoke_receipt_path = startup_smoke_receipt_path or Path(
        _normalize_text(checks.get("startup_smoke_receipt_path"))
    )
    startup_smoke_receipt = (
        _load_json(effective_startup_smoke_receipt_path)
        if effective_startup_smoke_receipt_path and str(effective_startup_smoke_receipt_path).strip()
        else {}
    )

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    fleet_queue_item = _find_queue_item(fleet_queue, WORK_TASK_ID)
    design_queue_item = _find_queue_item(design_queue, WORK_TASK_ID)

    canonical_monitors = {
        "guide_markers": _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon"),
        "queue_alignment": _queue_alignment(
            work_task=work_task,
            fleet_queue_item=fleet_queue_item,
            design_queue_item=design_queue_item,
        ),
    }

    release_channel_monitor = _release_channel_monitor(release_channel)
    flagship_monitor = _flagship_monitor(flagship_readiness)
    windows_monitor = _windows_gate_monitor(
        ui_windows_exit_gate,
        startup_smoke_receipt=startup_smoke_receipt,
        windows_artifact=dict(release_channel_monitor.get("windows_artifact") or {}),
        release_channel_version=str(release_channel_monitor.get("release_channel_version") or ""),
    )
    executable_monitor = _executable_gate_monitor(
        desktop_executable_exit_gate,
        release_channel_version=str(release_channel_monitor.get("release_channel_version") or ""),
    )
    consistency_monitor = _consistency_monitor(
        flagship_monitor,
        windows_gate=ui_windows_exit_gate,
        executable_gate=desktop_executable_exit_gate,
        release_channel=release_channel,
        windows_artifact=dict(release_channel_monitor.get("windows_artifact") or {}),
    )

    runtime_monitors = {
        "flagship_desktop_readiness": flagship_monitor,
        "release_channel_tuple_truth": release_channel_monitor,
        "windows_startup_smoke_truth": windows_monitor,
        "desktop_executable_gate": executable_monitor,
        "proof_consistency": consistency_monitor,
    }

    canonical_issues = [
        issue
        for monitor in canonical_monitors.values()
        for issue in monitor.get("issues") or []
        if _normalize_text(issue)
    ]
    warnings = [
        warning
        for monitor in list(canonical_monitors.values()) + list(runtime_monitors.values())
        for warning in monitor.get("warnings") or []
        if _normalize_text(warning)
    ]
    runtime_blockers = [
        blocker
        for monitor in runtime_monitors.values()
        for blocker in monitor.get("runtime_blockers") or []
        if _normalize_text(blocker)
    ]

    desktop_proof_integrity_closeout_status = "blocked" if runtime_blockers else ("warning" if warnings else "pass")
    package_status = "pass" if not canonical_issues else "fail"
    package_closeout = {
        "ready": package_status == "pass" and not runtime_blockers,
        "status": desktop_proof_integrity_closeout_status if package_status == "pass" else "blocked",
        "reasons": canonical_issues + runtime_blockers,
        "warnings": warnings,
    }

    source_inputs = {
        "successor_registry": _source_link(registry_path, {}),
        "fleet_queue_staging": _source_link(fleet_queue_path, {}),
        "design_queue_staging": _source_link(design_queue_path, {}),
        "next90_guide": _source_link(next90_guide_path, {}),
        "flagship_readiness": _source_link(flagship_readiness_path, flagship_readiness),
        "ui_windows_exit_gate": _source_link(ui_windows_exit_gate_path, ui_windows_exit_gate),
        "desktop_executable_exit_gate": _source_link(desktop_executable_exit_gate_path, desktop_executable_exit_gate),
        "release_channel": _source_link(release_channel_path, release_channel),
    }
    if effective_startup_smoke_receipt_path and str(effective_startup_smoke_receipt_path).strip():
        source_inputs["startup_smoke_receipt"] = _source_link(effective_startup_smoke_receipt_path, startup_smoke_receipt)

    return {
        "generated_at": generated_at,
        "contract_name": "fleet.next90_m144_desktop_proof_integrity_closeout_gates",
        "package_id": PACKAGE_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "wave": WAVE_ID,
        "status": package_status,
        "queue_title": QUEUE_TITLE,
        "monitor_summary": {
            "desktop_proof_integrity_closeout_status": desktop_proof_integrity_closeout_status,
            "canonical_issue_count": len(canonical_issues),
            "runtime_blocker_count": len(runtime_blockers),
            "warning_count": len(warnings),
            "runtime_blockers": runtime_blockers,
            "warnings": warnings,
        },
        "canonical_monitors": canonical_monitors,
        "runtime_monitors": runtime_monitors,
        "package_closeout": package_closeout,
        "source_inputs": source_inputs,
    }


def _render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    package_closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Next90 M144 Fleet Desktop Proof Integrity Closeout Gates",
        "",
        f"- status: `{payload.get('status', '')}`",
        f"- desktop_proof_integrity_closeout_status: `{summary.get('desktop_proof_integrity_closeout_status', '')}`",
        f"- ready: `{package_closeout.get('ready', False)}`",
        "",
        "## Runtime blockers",
    ]
    runtime_blockers = list(summary.get("runtime_blockers") or [])
    if runtime_blockers:
        for item in runtime_blockers:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings"])
    warnings = list(summary.get("warnings") or [])
    if warnings:
        for item in warnings:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    startup_smoke_receipt_path = Path(args.startup_smoke_receipt).resolve() if str(args.startup_smoke_receipt or "").strip() else None
    payload = build_payload(
        registry_path=Path(args.successor_registry).resolve(),
        fleet_queue_path=Path(args.fleet_queue_staging).resolve(),
        design_queue_path=Path(args.design_queue_staging).resolve(),
        next90_guide_path=Path(args.next90_guide).resolve(),
        flagship_readiness_path=Path(args.flagship_readiness).resolve(),
        ui_windows_exit_gate_path=Path(args.ui_windows_exit_gate).resolve(),
        desktop_executable_exit_gate_path=Path(args.desktop_executable_exit_gate).resolve(),
        release_channel_path=Path(args.release_channel).resolve(),
        startup_smoke_receipt_path=startup_smoke_receipt_path,
    )
    output_path = Path(args.output).resolve()
    markdown_path = Path(args.markdown_output).resolve()
    _write_json_file(output_path, payload)
    _write_markdown_file(markdown_path, _render_markdown(payload))
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
