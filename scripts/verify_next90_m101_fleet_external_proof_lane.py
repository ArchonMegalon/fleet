#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote

import yaml


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
PACKAGE_ID = "next90-m101-fleet-external-proof-lane"
FRONTIER_ID = "1324843972"
MILESTONE_ID = 101
MILESTONE_TITLE = "Native-host desktop release train and promotion discipline"
WAVE = "W6"
QUEUE_TITLE = "Keep native-host proof capture and ingest repeatable for release truth"
QUEUE_TASK = (
    "Close the external host proof lane with a generated runbook, retained per-host command bundles, "
    "ingest validation, and readiness-backed repeat prevention."
)
WORK_TASK_ID = "101.1"
WORK_TASK_TITLE = "Turn native-host proof capture and ingest into a repeatable release packet lane."
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]
OWNED_SURFACES = ["desktop_release_train:external_proof_lane", "desktop_release_train:proof_ingest"]
COMPLETION_ACTION = "verify_closed_package_only"
DO_NOT_REOPEN_REASON = (
    "M101 Fleet external proof lane is complete; future shards must verify the external-proof runbook, "
    "command bundle, standalone verifier, registry row, queue row, design queue row, and flagship "
    "readiness receipt instead of reopening native-host proof capture and ingest."
)
DESIGN_QUEUE_STAGING = (
    Path("/docker/chummercomplete/chummer-design/products/chummer")
    / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
)
SUCCESSOR_REGISTRY = (
    Path("/docker/chummercomplete/chummer-design/products/chummer")
    / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
)
SUPPORT_PACKETS = PUBLISHED / "SUPPORT_CASE_PACKETS.generated.json"
JOURNEY_GATES = PUBLISHED / "JOURNEY_GATES.generated.json"
EXTERNAL_PROOF_RUNBOOK = PUBLISHED / "EXTERNAL_PROOF_RUNBOOK.generated.md"
EXTERNAL_PROOF_COMMANDS_DIR = PUBLISHED / "external-proof-commands"
FLAGSHIP_PRODUCT_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
RELEASE_CHANNEL = (
    Path("/docker/chummercomplete/chummer-hub-registry")
    / ".codex-studio"
    / "published"
    / "RELEASE_CHANNEL.generated.json"
)
CLOSEOUT_NOTE = ROOT / "feedback" / "2026-04-19-next90-m101-fleet-external-proof-lane-closeout.md"
EXTERNAL_PROOF_CLOSURE_VERIFIER = ROOT / "scripts" / "verify_external_proof_closure.py"
BOOTSTRAP_GUARD = ROOT / "scripts" / "verify_script_bootstrap_no_pythonpath.py"
BOOTSTRAP_GUARD_TEST = ROOT / "tests" / "test_fleet_script_bootstrap_without_pythonpath.py"
RELEVANT_JOURNEY_IDS = (
    "install_claim_restore_continue",
    "build_explain_publish",
    "report_cluster_release_notify",
)
EXPECTED_EXTERNAL_HOST_REASON = "No unresolved external desktop host-proof requests remain."
DISALLOWED_WORKER_PROOF_MARKERS = (
    "/var/lib/codex-fleet",
    "ACTIVE_RUN_HANDOFF.generated.md",
    "TASK_LOCAL_TELEMETRY.generated.json",
    "frontier ids:",
    "open milestone ids:",
    "successor frontier detail:",
    "active-run telemetry",
    "active-run helper",
    "operator-telemetry",
    "worker-run telemetry",
    "control-plane helper output",
    "run-state helper output",
    "helper output",
    "supervisor status",
    "supervisor eta",
    "mode: successor_wave",
    "active run",
    "run id:",
    "prompt path",
    "recent stderr tail",
    "status: complete; owners:",
    "run_ooda_design_supervisor_until_quiet",
    "ooda_design_supervisor.py",
    "chummer_design_supervisor.py",
    "chummer_design_supervisor.py status",
    "chummer_design_supervisor.py eta",
    "codexea --telemetry",
    "--telemetry-answer",
)
REQUIRED_REGISTRY_EVIDENCE_MARKERS = [
    "/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md",
    "/docker/fleet/.codex-studio/published/external-proof-commands/",
    "/docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json",
    "/docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json",
    "/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json",
    "/docker/fleet/scripts/materialize_external_proof_runbook.py",
    "/docker/fleet/scripts/verify_external_proof_closure.py",
    "/docker/fleet/scripts/verify_next90_m101_fleet_external_proof_lane.py",
    "/docker/fleet/tests/test_materialize_external_proof_runbook.py",
    "/docker/fleet/tests/test_verify_external_proof_closure.py",
    "/docker/fleet/tests/test_verify_next90_m101_fleet_external_proof_lane.py",
    "/docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py",
    "/docker/fleet/tests/test_fleet_script_bootstrap_without_pythonpath.py",
    "/docker/fleet/feedback/2026-04-19-next90-m101-fleet-external-proof-lane-closeout.md",
    "zero external desktop host-proof backlog",
    "retains executable preflight, capture, validate, bundle, ingest, and run entrypoints",
    "external_host_proof.status=pass",
    "bind runbook generation, closure verification, and completed-package repeat prevention",
    "include the standalone M101 verifier in no-PYTHONPATH bootstrap proof",
]
REQUIRED_QUEUE_PROOF_MARKERS = [
    "/docker/fleet/scripts/materialize_external_proof_runbook.py",
    "/docker/fleet/scripts/verify_external_proof_closure.py",
    "/docker/fleet/scripts/verify_next90_m101_fleet_external_proof_lane.py",
    "/docker/fleet/tests/test_materialize_external_proof_runbook.py",
    "/docker/fleet/tests/test_verify_external_proof_closure.py",
    "/docker/fleet/tests/test_verify_next90_m101_fleet_external_proof_lane.py",
    "/docker/fleet/scripts/verify_script_bootstrap_no_pythonpath.py",
    "/docker/fleet/tests/test_fleet_script_bootstrap_without_pythonpath.py",
    "/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md",
    "/docker/fleet/.codex-studio/published/external-proof-commands/",
    "/docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json",
    "/docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json",
    "/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json",
    "/docker/fleet/feedback/2026-04-19-next90-m101-fleet-external-proof-lane-closeout.md",
    "python3 scripts/verify_next90_m101_fleet_external_proof_lane.py exits 0",
    "python3 -m pytest -q tests/test_materialize_external_proof_runbook.py tests/test_verify_external_proof_closure.py tests/test_verify_next90_m101_fleet_external_proof_lane.py tests/test_fleet_script_bootstrap_without_pythonpath.py",
    f"successor frontier {FRONTIER_ID}",
    "support packet external-proof backlog is zero",
    "journey gates external-proof blockers are zero",
    "flagship readiness external_host_proof.status=pass",
    "zero-backlog command bundle retains per-host preflight/capture/validate/bundle/ingest/run scripts",
    "design-owned queue source row matches the Fleet completed queue proof assignment",
    "completed queue action guard requires verify_closed_package_only and package-specific do_not_reopen_reason",
]
REQUIRED_CLOSEOUT_NOTE_MARKERS = [
    f"Package: `{PACKAGE_ID}`",
    f"Frontier: `{FRONTIER_ID}`",
    "Future shards must verify the completed package instead of reopening native-host proof capture and ingest",
    "worker-local telemetry",
    "helper commands",
    "The canonical completed-package frontier for this Fleet proof lane remains pinned in the queue and registry evidence above.",
    "Worker-assignment frontier ids from active successor runs are scheduler-local context only and must never replace the canonical package frontier in closure proof.",
    "support-packet external-proof backlog stays zero",
    "journey gates keep external-only blockers at zero",
    "flagship readiness keeps `external_host_proof.status=pass`",
    "the zero-backlog command bundle still retains per-host preflight, capture, validate, bundle, ingest, and run entrypoints for Linux, macOS, and Windows",
    "the retained command bundle keeps `host-proof-bundles/linux`, `host-proof-bundles/macos`, and `host-proof-bundles/windows` present so ingest can resume without rebuilding the lane",
    "the finalize entrypoint still republishes after the per-host validate and ingest lanes remain available",
    "the standalone verifier and bootstrap no-PYTHONPATH guard stay runnable without ambient worker state",
]
REQUIRED_ANCHOR_PATHS = [
    ROOT / "scripts" / "materialize_external_proof_runbook.py",
    ROOT / "scripts" / "verify_external_proof_closure.py",
    ROOT / "scripts" / "verify_next90_m101_fleet_external_proof_lane.py",
    ROOT / "tests" / "test_materialize_external_proof_runbook.py",
    ROOT / "tests" / "test_verify_external_proof_closure.py",
    ROOT / "tests" / "test_verify_next90_m101_fleet_external_proof_lane.py",
    ROOT / "scripts" / "verify_script_bootstrap_no_pythonpath.py",
    ROOT / "tests" / "test_fleet_script_bootstrap_without_pythonpath.py",
    PUBLISHED / "EXTERNAL_PROOF_RUNBOOK.generated.md",
    PUBLISHED / "external-proof-commands",
    PUBLISHED / "SUPPORT_CASE_PACKETS.generated.json",
    PUBLISHED / "JOURNEY_GATES.generated.json",
    PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json",
    CLOSEOUT_NOTE,
]
REQUIRED_BOOTSTRAP_GUARD_TOKENS = (
    "verify_external_proof_closure.py",
    "materialize_external_proof_runbook.py",
    "verify_next90_m101_fleet_external_proof_lane.py",
    "materialize_proof_orchestration.py",
)
EXPECTED_COMMAND_PATHS = [
    "host-proof-bundles",
    "republish-after-host-proof.sh",
    "finalize-external-host-proof.sh",
    "preflight-linux-proof.sh",
    "capture-linux-proof.sh",
    "validate-linux-proof.sh",
    "bundle-linux-proof.sh",
    "ingest-linux-proof-bundle.sh",
    "run-linux-proof-lane.sh",
    "preflight-macos-proof.sh",
    "capture-macos-proof.sh",
    "validate-macos-proof.sh",
    "bundle-macos-proof.sh",
    "ingest-macos-proof-bundle.sh",
    "run-macos-proof-lane.sh",
    "preflight-windows-proof.sh",
    "capture-windows-proof.sh",
    "validate-windows-proof.sh",
    "bundle-windows-proof.sh",
    "ingest-windows-proof-bundle.sh",
    "run-windows-proof-lane.sh",
    "preflight-windows-proof.ps1",
    "capture-windows-proof.ps1",
    "validate-windows-proof.ps1",
    "bundle-windows-proof.ps1",
    "ingest-windows-proof-bundle.ps1",
    "run-windows-proof-lane.ps1",
]
COMMAND_BUNDLE_SUFFIXES = frozenset({".sh", ".ps1"})
REQUIRED_ZERO_BACKLOG_BUNDLE_TOKENS = (
    'BUNDLE_ARCHIVE="$SCRIPT_DIR/{host}-proof-bundle.tgz"',
    'BUNDLE_ROOT="$SCRIPT_DIR/host-proof-bundles/{host}"',
    'rm -f "$BUNDLE_ARCHIVE"',
    "external-proof-manifest.json",
    '"request_count": 0',
    'tar -czf "$BUNDLE_ARCHIVE" -C "$BUNDLE_ROOT" .',
    'echo "Wrote $BUNDLE_ARCHIVE"',
)
REQUIRED_ZERO_BACKLOG_INGEST_TOKENS = (
    'BUNDLE_ARCHIVE="$SCRIPT_DIR/{host}-proof-bundle.tgz"',
    'BUNDLE_DIR="$SCRIPT_DIR/host-proof-bundles/{host}"',
    "TARGET_ROOT=",
    'Missing host proof bundle: $BUNDLE_ARCHIVE or $BUNDLE_DIR',
    "external-proof-manifest.json",
    "external-proof-bundle-manifest-missing",
    "external-proof-bundle-manifest-mismatch",
    "external-proof-bundle-path-unsafe",
    "assert not bad",
    'tar -xzf "$BUNDLE_ARCHIVE" -C "$TARGET_ROOT"',
    "No expected host proof files were queued for ingest.",
    '"request_count": 0',
)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the checked-in Next90 M101 Fleet external host-proof lane closeout."
    )
    parser.add_argument("--support-packets", default=str(SUPPORT_PACKETS))
    parser.add_argument("--journey-gates", default=str(JOURNEY_GATES))
    parser.add_argument("--release-channel", default=str(RELEASE_CHANNEL))
    parser.add_argument("--external-proof-runbook", default=str(EXTERNAL_PROOF_RUNBOOK))
    parser.add_argument("--external-proof-commands-dir", default=str(EXTERNAL_PROOF_COMMANDS_DIR))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_PRODUCT_READINESS))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--closeout-note", default=str(CLOSEOUT_NOTE))
    parser.add_argument("--json", action="store_true", help="Emit the verification payload as JSON.")
    return parser.parse_args(argv)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _coerce_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    raw = _normalize_text(value)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_iso_utc(value: Any) -> datetime | None:
    raw = _normalize_text(value)
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_json(path: Path, issues: list[str], *, label: str) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(f"{label} is missing or not valid JSON: {path}: {exc}")
        return {}
    if not isinstance(payload, dict):
        issues.append(f"{label} root must be a JSON object: {path}")
        return {}
    return payload


def _load_yaml(path: Path, issues: list[str], *, label: str) -> Dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(f"{label} is missing or not valid YAML: {path}: {exc}")
        return {}
    if not isinstance(payload, dict):
        issues.append(f"{label} root must be a mapping: {path}")
        return {}
    return payload


def _load_text(path: Path, issues: list[str], *, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        issues.append(f"{label} is missing or unreadable: {path}: {exc}")
        return ""


def _contains_marker(entries: list[Any], marker: str) -> bool:
    expected = marker.lower()
    return any(expected in _normalize_text(entry).lower() for entry in entries)


def _missing_markers(entries: list[Any], required: list[str]) -> list[str]:
    return [marker for marker in required if not _contains_marker(entries, marker)]


def _disallowed_entries(entries: list[Any]) -> list[str]:
    blocked: list[str] = []
    for entry in entries:
        text = _normalize_text(entry)
        lowered_variants = [variant.lower() for variant in _worker_proof_text_variants(text)]
        if any(
            marker.lower() in lowered_variant
            for marker in DISALLOWED_WORKER_PROOF_MARKERS
            for lowered_variant in lowered_variants
        ):
            blocked.append(text)
    return blocked


def _worker_proof_text_variants(text: str) -> list[str]:
    variants = [text]
    url_decoded = unquote(text)
    if url_decoded != text:
        variants.append(url_decoded)
    html_decoded = html.unescape(text)
    if html_decoded != text:
        variants.append(html_decoded)
    if "\\" in text:
        try:
            escaped = text.encode("utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            escaped = ""
        if escaped and escaped != text:
            variants.append(escaped)
    variants.extend(_decoded_worker_proof_tokens(text))
    deduped: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        if variant not in seen:
            deduped.append(variant)
            seen.add(variant)
    return deduped


def _decoded_worker_proof_tokens(text: str) -> list[str]:
    decoded: list[str] = []
    pending = [text]
    seen = {text}
    for _depth in range(3):
        next_pending: list[str] = []
        for value in pending:
            for token in re.findall(r"\b[0-9A-Fa-f]{24,}\b", value):
                if len(token) % 2:
                    continue
                try:
                    decoded_token = bytes.fromhex(token).decode("utf-8")
                except (UnicodeDecodeError, ValueError):
                    continue
                if decoded_token not in seen:
                    decoded.append(decoded_token)
                    next_pending.append(decoded_token)
                    seen.add(decoded_token)
            for token in re.findall(r"\b[A-Za-z0-9+/_-]{20,}={0,2}\b", value):
                padded = token + ("=" * (-len(token) % 4))
                decoded_token = ""
                try:
                    decoded_token = base64.b64decode(padded, validate=True).decode("utf-8")
                except (binascii.Error, UnicodeDecodeError):
                    try:
                        decoded_token = base64.urlsafe_b64decode(padded).decode("utf-8")
                    except (binascii.Error, UnicodeDecodeError):
                        continue
                if decoded_token not in seen:
                    decoded.append(decoded_token)
                    next_pending.append(decoded_token)
                    seen.add(decoded_token)
        pending = next_pending
        if not pending:
            break
    return decoded


def _disallowed_payload_entries(value: Any) -> list[str]:
    try:
        text = json.dumps(value, sort_keys=True)
    except TypeError:
        text = _normalize_text(value)
    return _disallowed_entries([text])


def _extract_runbook_field(markdown: str, key: str) -> str:
    needle = f"- {key}:"
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith(needle):
            return line[len(needle) :].strip().strip("`")
    return ""


def _command_bundle_fingerprint(commands_dir: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    aggregate = hashlib.sha256()
    if not commands_dir.exists():
        return {"sha256": "", "file_count": 0, "files": files}
    for candidate in sorted(
        path
        for path in commands_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in COMMAND_BUNDLE_SUFFIXES
    ):
        relative_path = candidate.relative_to(commands_dir).as_posix()
        payload = candidate.read_bytes()
        file_sha256 = hashlib.sha256(payload).hexdigest()
        executable = os.access(candidate, os.X_OK)
        aggregate.update(relative_path.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(file_sha256.encode("ascii"))
        aggregate.update(b"\0")
        aggregate.update(b"1" if executable else b"0")
        aggregate.update(b"\n")
        files.append(
            {
                "path": relative_path,
                "sha256": file_sha256,
                "executable": executable,
            }
        )
    return {
        "sha256": aggregate.hexdigest() if files else "",
        "file_count": len(files),
        "files": files,
    }


def _queue_item(queue: Dict[str, Any], package_id: str) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
    matches = [
        dict(item)
        for item in _normalize_list(queue.get("items"))
        if isinstance(item, dict) and _normalize_text(item.get("package_id")) == package_id
    ]
    return matches, (matches[0] if matches else {})


def _registry_milestone(registry: Dict[str, Any]) -> Dict[str, Any]:
    for milestone in _normalize_list(registry.get("milestones")):
        if isinstance(milestone, dict) and _coerce_int(milestone.get("id"), -1) == MILESTONE_ID:
            return dict(milestone)
    return {}


def _registry_work_tasks(milestone: Dict[str, Any]) -> list[Dict[str, Any]]:
    return [
        dict(task)
        for task in _normalize_list(milestone.get("work_tasks"))
        if isinstance(task, dict) and _normalize_text(task.get("id")) == WORK_TASK_ID
    ]


def _run_external_proof_closure(
    *,
    support_packets: Path,
    journey_gates: Path,
    release_channel: Path,
    runbook: Path,
    commands_dir: Path,
) -> list[str]:
    env = dict(os.environ)
    result = subprocess.run(
        [
            sys.executable,
            str(EXTERNAL_PROOF_CLOSURE_VERIFIER),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
            "--quiet",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode == 0:
        return []
    combined = (result.stderr or "").strip()
    if result.stdout:
        combined = f"{combined}\n{result.stdout.strip()}".strip()
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    if not lines:
        lines = [f"verify_external_proof_closure.py exited {result.returncode}"]
    return [f"external proof closure verifier failed: {line}" for line in lines]


def _require(condition: bool, issues: list[str], message: str) -> None:
    if not condition:
        issues.append(message)


def _require_tokens(payload: str, tokens: tuple[str, ...], issues: list[str], *, label: str) -> None:
    for token in tokens:
        if token not in payload:
            issues.append(f"{label} missing required token: {token}")


def _require_file_tokens(path: Path, tokens: tuple[str, ...], issues: list[str], *, label: str) -> None:
    try:
        payload = path.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(f"{label} is missing or unreadable: {path}: {exc}")
        return
    _require_tokens(payload, tokens, issues, label=label)


def _expected_zero_backlog_manifest(host: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "host": host,
        "request_count": 0,
        "requests": [],
    }


def _load_retained_bundle_manifest(bundle_dir: Path, issues: list[str], *, host: str) -> dict[str, Any]:
    manifest_path = bundle_dir / "external-proof-manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        issues.append(f"external proof retained host bundle manifest is missing or invalid for {host}: {manifest_path}: {exc}")
        return {}
    if not isinstance(payload, dict):
        issues.append(f"external proof retained host bundle manifest is not an object for {host}: {manifest_path}")
        return {}
    return payload


def verify(args: argparse.Namespace) -> Dict[str, Any]:
    issues: list[str] = []
    support_packets_path = Path(args.support_packets).resolve()
    journey_gates_path = Path(args.journey_gates).resolve()
    release_channel_path = Path(args.release_channel).resolve()
    runbook_path = Path(args.external_proof_runbook).resolve()
    commands_dir_path = Path(args.external_proof_commands_dir).resolve()
    flagship_readiness_path = Path(args.flagship_readiness).resolve()
    successor_registry_path = Path(args.successor_registry).resolve()
    queue_staging_path = Path(args.queue_staging).resolve()
    design_queue_staging_path = Path(args.design_queue_staging).resolve()
    closeout_note_path = Path(args.closeout_note).resolve()

    support_packets = _load_json(support_packets_path, issues, label="support packets")
    journey_gates = _load_json(journey_gates_path, issues, label="journey gates")
    release_channel = _load_json(release_channel_path, issues, label="release channel")
    flagship_readiness = _load_json(flagship_readiness_path, issues, label="flagship readiness")
    registry = _load_yaml(successor_registry_path, issues, label="successor registry")
    queue = _load_yaml(queue_staging_path, issues, label="queue staging")
    design_queue = _load_yaml(design_queue_staging_path, issues, label="design queue staging")
    runbook_body = _load_text(runbook_path, issues, label="external proof runbook")
    closeout_note_body = _load_text(closeout_note_path, issues, label="closeout note")

    issues.extend(
        _run_external_proof_closure(
            support_packets=support_packets_path,
            journey_gates=journey_gates_path,
            release_channel=release_channel_path,
            runbook=runbook_path,
            commands_dir=commands_dir_path,
        )
    )

    support_generated_at = _normalize_text(support_packets.get("generated_at"))
    support_summary = dict(support_packets.get("summary") or {})
    unresolved_backlog = dict(support_packets.get("unresolved_external_proof") or {})
    execution_plan = dict(support_packets.get("unresolved_external_proof_execution_plan") or {})
    release_generated_at = _normalize_text(
        release_channel.get("generatedAt") or release_channel.get("generated_at")
    )
    raw_release_tuple_coverage = release_channel.get("desktopTupleCoverage")
    release_tuple_coverage = dict(raw_release_tuple_coverage) if isinstance(raw_release_tuple_coverage, dict) else {}
    runbook_generated_at = _extract_runbook_field(runbook_body, "generated_at")
    runbook_plan_generated_at = _extract_runbook_field(runbook_body, "plan_generated_at")
    runbook_release_generated_at = _extract_runbook_field(runbook_body, "release_channel_generated_at")
    runbook_unresolved_request_count = _extract_runbook_field(runbook_body, "unresolved_request_count")
    runbook_unresolved_hosts = _extract_runbook_field(runbook_body, "unresolved_hosts")
    runbook_capture_deadline_hours = _extract_runbook_field(runbook_body, "capture_deadline_hours")
    runbook_command_bundle_sha256 = _extract_runbook_field(runbook_body, "command_bundle_sha256")
    runbook_command_bundle_file_count = _coerce_int(
        _extract_runbook_field(runbook_body, "command_bundle_file_count"),
        -1,
    )
    command_bundle = _command_bundle_fingerprint(commands_dir_path)
    command_bundle_sha256 = _normalize_text(command_bundle.get("sha256"))
    command_bundle_file_count = _coerce_int(command_bundle.get("file_count"), -1)
    readiness_generated_at = _normalize_text(flagship_readiness.get("generated_at"))
    external_host_proof = dict(flagship_readiness.get("external_host_proof") or {})
    fleet_coverage = dict(
        (flagship_readiness.get("coverage_details") or {}).get("fleet_and_operator_loop") or {}
    )
    fleet_evidence = dict(fleet_coverage.get("evidence") or {})
    journey_summary = dict(journey_gates.get("summary") or {})
    journey_rows = {
        _normalize_text(row.get("id")): dict(row)
        for row in _normalize_list(journey_gates.get("journeys"))
        if isinstance(row, dict)
    }

    _require(_parse_iso_utc(support_generated_at) is not None, issues, "support packets generated_at is missing or invalid")
    _require(_parse_iso_utc(release_generated_at) is not None, issues, "release channel generatedAt is missing or invalid")
    _require(_parse_iso_utc(runbook_generated_at) is not None, issues, "external proof runbook generated_at is missing or invalid")
    _require(_parse_iso_utc(readiness_generated_at) is not None, issues, "flagship readiness generated_at is missing or invalid")
    if _parse_iso_utc(runbook_generated_at) and _parse_iso_utc(support_generated_at):
        _require(
            _parse_iso_utc(runbook_generated_at) >= _parse_iso_utc(support_generated_at),
            issues,
            "external proof runbook generated_at predates support packets generated_at",
        )
    if _parse_iso_utc(readiness_generated_at) and _parse_iso_utc(runbook_generated_at):
        _require(
            _parse_iso_utc(readiness_generated_at) >= _parse_iso_utc(runbook_generated_at),
            issues,
            "flagship readiness generated_at predates external proof runbook generated_at",
        )

    _require(
        isinstance(raw_release_tuple_coverage, dict),
        issues,
        "release channel desktopTupleCoverage is missing or not an object",
    )
    _require(
        _normalize_list(release_tuple_coverage.get("missingRequiredPlatforms")) == [],
        issues,
        "release channel desktopTupleCoverage.missingRequiredPlatforms is not empty",
    )
    _require(
        _normalize_list(release_tuple_coverage.get("missingRequiredPlatformHeadPairs")) == [],
        issues,
        "release channel desktopTupleCoverage.missingRequiredPlatformHeadPairs is not empty",
    )
    _require(
        _normalize_list(release_tuple_coverage.get("missingRequiredPlatformHeadRidTuples")) == [],
        issues,
        "release channel desktopTupleCoverage.missingRequiredPlatformHeadRidTuples is not empty",
    )
    _require(
        _normalize_list(release_tuple_coverage.get("externalProofRequests")) == [],
        issues,
        "release channel desktopTupleCoverage.externalProofRequests is not empty",
    )

    _require(
        _coerce_int(support_summary.get("unresolved_external_proof_request_count"), -1) == 0,
        issues,
        "support packets summary unresolved_external_proof_request_count is not zero",
    )
    _require(
        _normalize_list(support_summary.get("unresolved_external_proof_request_hosts")) == [],
        issues,
        "support packets summary unresolved_external_proof_request_hosts is not empty",
    )
    _require(
        _normalize_list(support_summary.get("unresolved_external_proof_request_tuples")) == [],
        issues,
        "support packets summary unresolved_external_proof_request_tuples is not empty",
    )
    _require(
        dict(support_summary.get("unresolved_external_proof_request_specs") or {}) == {},
        issues,
        "support packets summary unresolved_external_proof_request_specs is not empty",
    )
    _require(
        _coerce_int(unresolved_backlog.get("count"), -1) == 0,
        issues,
        "support packets unresolved_external_proof.count is not zero",
    )
    _require(
        _normalize_list(unresolved_backlog.get("hosts")) == [],
        issues,
        "support packets unresolved_external_proof.hosts is not empty",
    )
    _require(
        _normalize_list(unresolved_backlog.get("tuples")) == [],
        issues,
        "support packets unresolved_external_proof.tuples is not empty",
    )
    _require(
        dict(unresolved_backlog.get("specs") or {}) == {},
        issues,
        "support packets unresolved_external_proof.specs is not empty",
    )
    _require(
        _coerce_int(execution_plan.get("request_count"), -1) == 0,
        issues,
        "support packets unresolved_external_proof_execution_plan.request_count is not zero",
    )
    _require(
        _normalize_list(execution_plan.get("hosts")) == [],
        issues,
        "support packets unresolved_external_proof_execution_plan.hosts is not empty",
    )
    _require(
        dict(execution_plan.get("host_groups") or {}) == {},
        issues,
        "support packets unresolved_external_proof_execution_plan.host_groups is not empty",
    )
    _require(
        _coerce_int(execution_plan.get("capture_deadline_hours"), -1) == 24,
        issues,
        "support packets unresolved_external_proof_execution_plan.capture_deadline_hours is not 24",
    )
    _require(
        _normalize_text(execution_plan.get("release_channel_generated_at")) == release_generated_at,
        issues,
        "support packets unresolved_external_proof_execution_plan.release_channel_generated_at drifted from release channel generatedAt",
    )
    _require(
        _normalize_text(runbook_plan_generated_at) == support_generated_at,
        issues,
        "external proof runbook plan_generated_at drifted from support packets generated_at",
    )
    _require(
        _normalize_text(runbook_release_generated_at) == release_generated_at,
        issues,
        "external proof runbook release_channel_generated_at drifted from release channel generatedAt",
    )
    _require(
        runbook_unresolved_request_count == "0",
        issues,
        "external proof runbook unresolved_request_count is not 0",
    )
    _require(
        runbook_unresolved_hosts == "(none)",
        issues,
        "external proof runbook unresolved_hosts is not '(none)'",
    )
    _require(
        runbook_capture_deadline_hours == "24",
        issues,
        "external proof runbook capture_deadline_hours is not 24",
    )
    _require(
        bool(command_bundle_sha256),
        issues,
        "external proof retained command bundle fingerprint is empty",
    )
    _require(
        command_bundle_file_count == len(EXPECTED_COMMAND_PATHS) - 1,
        issues,
        "external proof retained command bundle file count drifted from expected script inventory",
    )
    _require(
        runbook_command_bundle_sha256 == command_bundle_sha256,
        issues,
        "external proof runbook command_bundle_sha256 drifted from retained command bundle",
    )
    _require(
        runbook_command_bundle_file_count == command_bundle_file_count,
        issues,
        "external proof runbook command_bundle_file_count drifted from retained command bundle",
    )
    _require(
        "No unresolved external-proof requests are currently queued." in runbook_body,
        issues,
        "external proof runbook is missing the zero-backlog note",
    )
    _require(
        "## Retained Host Lanes" in runbook_body,
        issues,
        "external proof runbook is missing the retained host lanes section",
    )
    _require(
        runbook_body.count("- request_count: 0") >= 3,
        issues,
        "external proof runbook is missing retained zero-backlog request counts",
    )
    for host in ("linux", "macos", "windows"):
        host_lane_script = commands_dir_path / f"run-{host}-proof-lane.sh"
        retained_bundle_archive_path = commands_dir_path / f"{host}-proof-bundle.tgz"
        retained_bundle_directory_path = commands_dir_path / "host-proof-bundles" / host
        _require(f"### Host: {host}" in runbook_body, issues, f"external proof runbook is missing retained host lane for {host}")
        _require(
            f"- host_lane_script: `{host_lane_script}`" in runbook_body,
            issues,
            f"external proof runbook is missing retained host lane script for {host}",
        )
        _require(
            f"- retained_bundle_archive_path: `{retained_bundle_archive_path}`" in runbook_body,
            issues,
            f"external proof runbook retained bundle archive path drifted for {host}",
        )
        _require(
            f"- retained_bundle_directory_path: `{retained_bundle_directory_path}`" in runbook_body,
            issues,
            f"external proof runbook retained bundle directory path drifted for {host}",
        )
        _require(
            (
                f"- retained_bundle_directory_path: `{retained_bundle_directory_path}`\n"
                "- retained_bundle_directory_present: `true`"
            )
            in runbook_body,
            issues,
            f"external proof runbook does not report retained bundle directory present for {host}",
        )
    _require(
        f"- host_lane_powershell: `{commands_dir_path / 'run-windows-proof-lane.ps1'}`" in runbook_body,
        issues,
        "external proof runbook is missing retained Windows PowerShell lane script",
    )

    _require(
        _normalize_text(journey_summary.get("overall_state")) == "ready",
        issues,
        "journey gates summary overall_state is not ready",
    )
    _require(
        _coerce_int(journey_summary.get("blocked_external_only_count"), -1) == 0,
        issues,
        "journey gates summary blocked_external_only_count is not zero",
    )
    _require(
        _normalize_list(journey_summary.get("blocked_external_only_hosts")) == [],
        issues,
        "journey gates summary blocked_external_only_hosts is not empty",
    )
    _require(
        _normalize_list(journey_summary.get("blocked_external_only_tuples")) == [],
        issues,
        "journey gates summary blocked_external_only_tuples is not empty",
    )
    for journey_id in RELEVANT_JOURNEY_IDS:
        row = journey_rows.get(journey_id, {})
        _require(bool(row), issues, f"journey row {journey_id} is missing")
        if not row:
            continue
        _require(_normalize_text(row.get("state")) == "ready", issues, f"journey row {journey_id} is not ready")
        _require(
            _normalize_list(row.get("external_proof_requests")) == [],
            issues,
            f"journey row {journey_id} still has external_proof_requests",
        )
        _require(
            _normalize_list(row.get("external_blocking_reasons")) == [],
            issues,
            f"journey row {journey_id} still has external_blocking_reasons",
        )
        _require(
            _normalize_list(row.get("blocking_reasons")) == [],
            issues,
            f"journey row {journey_id} still has blocking_reasons",
        )
        _require(
            row.get("blocked_by_external_constraints_only") is False,
            issues,
            f"journey row {journey_id} is still blocked_by_external_constraints_only",
        )

    _require(_normalize_text(flagship_readiness.get("status")) == "pass", issues, "flagship readiness status is not pass")
    _require(
        _normalize_text(external_host_proof.get("status")) == "pass",
        issues,
        "flagship readiness external_host_proof.status is not pass",
    )
    _require(
        _normalize_text(external_host_proof.get("reason")) == EXPECTED_EXTERNAL_HOST_REASON,
        issues,
        "flagship readiness external_host_proof.reason drifted",
    )
    _require(
        _coerce_int(external_host_proof.get("unresolved_request_count"), -1) == 0,
        issues,
        "flagship readiness external_host_proof.unresolved_request_count is not zero",
    )
    _require(
        _normalize_list(external_host_proof.get("unresolved_hosts")) == [],
        issues,
        "flagship readiness external_host_proof.unresolved_hosts is not empty",
    )
    _require(
        _normalize_list(external_host_proof.get("unresolved_tuples")) == [],
        issues,
        "flagship readiness external_host_proof.unresolved_tuples is not empty",
    )
    _require(
        bool(external_host_proof.get("runbook_synced")),
        issues,
        "flagship readiness external_host_proof.runbook_synced is not true",
    )
    _require(
        _normalize_list(external_host_proof.get("runbook_sync_reasons")) == [],
        issues,
        "flagship readiness external_host_proof.runbook_sync_reasons is not empty",
    )
    _require(
        _normalize_text(external_host_proof.get("runbook_path")) == str(runbook_path),
        issues,
        "flagship readiness external_host_proof.runbook_path drifted",
    )
    _require(
        _normalize_text(external_host_proof.get("runbook_generated_at")) == runbook_generated_at,
        issues,
        "flagship readiness external_host_proof.runbook_generated_at drifted",
    )
    _require(
        _normalize_text(external_host_proof.get("runbook_plan_generated_at")) == support_generated_at,
        issues,
        "flagship readiness external_host_proof.runbook_plan_generated_at drifted",
    )
    _require(
        _normalize_text(external_host_proof.get("runbook_release_channel_generated_at")) == release_generated_at,
        issues,
        "flagship readiness external_host_proof.runbook_release_channel_generated_at drifted",
    )
    _require(
        _normalize_text(external_host_proof.get("commands_dir")) == str(commands_dir_path),
        issues,
        "flagship readiness external_host_proof.commands_dir drifted",
    )
    _require(
        _normalize_text(external_host_proof.get("command_bundle_sha256")) == command_bundle_sha256,
        issues,
        "flagship readiness external_host_proof.command_bundle_sha256 drifted from retained command bundle",
    )
    _require(
        _coerce_int(external_host_proof.get("command_bundle_file_count"), -1) == command_bundle_file_count,
        issues,
        "flagship readiness external_host_proof.command_bundle_file_count drifted from retained command bundle",
    )
    _require(
        _normalize_text(external_host_proof.get("runbook_command_bundle_sha256")) == runbook_command_bundle_sha256,
        issues,
        "flagship readiness external_host_proof.runbook_command_bundle_sha256 drifted from runbook",
    )
    _require(
        _coerce_int(external_host_proof.get("runbook_command_bundle_file_count"), -1)
        == runbook_command_bundle_file_count,
        issues,
        "flagship readiness external_host_proof.runbook_command_bundle_file_count drifted from runbook",
    )
    _require(
        _coerce_int(fleet_evidence.get("external_proof_backlog_request_count"), -1) == 0,
        issues,
        "fleet coverage external_proof_backlog_request_count is not zero",
    )
    _require(
        _coerce_int(fleet_evidence.get("external_proof_backlog_request_observation_count"), -1) == 0,
        issues,
        "fleet coverage external_proof_backlog_request_observation_count is not zero",
    )
    _require(
        _coerce_int(fleet_evidence.get("external_proof_backlog_duplicate_observation_count"), -1) == 0,
        issues,
        "fleet coverage external_proof_backlog_duplicate_observation_count is not zero",
    )
    _require(
        bool(fleet_evidence.get("external_proof_runbook_synced")),
        issues,
        "fleet coverage external_proof_runbook_synced is not true",
    )
    _require(
        _coerce_int(fleet_evidence.get("external_proof_runbook_sync_issue_count"), -1) == 0,
        issues,
        "fleet coverage external_proof_runbook_sync_issue_count is not zero",
    )
    _require(
        _normalize_text(fleet_evidence.get("external_proof_runbook_path")) == str(runbook_path),
        issues,
        "fleet coverage external_proof_runbook_path drifted",
    )
    _require(
        _normalize_text(fleet_evidence.get("external_proof_runbook_generated_at")) == runbook_generated_at,
        issues,
        "fleet coverage external_proof_runbook_generated_at drifted",
    )
    _require(
        _normalize_text(fleet_evidence.get("external_proof_runbook_plan_generated_at")) == support_generated_at,
        issues,
        "fleet coverage external_proof_runbook_plan_generated_at drifted",
    )
    _require(
        _normalize_text(fleet_evidence.get("external_proof_runbook_release_channel_generated_at")) == release_generated_at,
        issues,
        "fleet coverage external_proof_runbook_release_channel_generated_at drifted",
    )
    _require(
        _normalize_text(fleet_evidence.get("external_proof_commands_dir")) == str(commands_dir_path),
        issues,
        "fleet coverage external_proof_commands_dir drifted",
    )
    _require(
        _normalize_text(fleet_evidence.get("external_proof_command_bundle_sha256")) == command_bundle_sha256,
        issues,
        "fleet coverage external_proof_command_bundle_sha256 drifted from retained command bundle",
    )
    _require(
        _coerce_int(fleet_evidence.get("external_proof_command_bundle_file_count"), -1) == command_bundle_file_count,
        issues,
        "fleet coverage external_proof_command_bundle_file_count drifted from retained command bundle",
    )
    _require(
        _normalize_text(fleet_evidence.get("external_proof_runbook_command_bundle_sha256")) == runbook_command_bundle_sha256,
        issues,
        "fleet coverage external_proof_runbook_command_bundle_sha256 drifted from runbook",
    )
    _require(
        _coerce_int(fleet_evidence.get("external_proof_runbook_command_bundle_file_count"), -1)
        == runbook_command_bundle_file_count,
        issues,
        "fleet coverage external_proof_runbook_command_bundle_file_count drifted from runbook",
    )
    _require(
        _coerce_int(fleet_evidence.get("journey_effective_blocked_external_only_count"), -1) == 0,
        issues,
        "fleet coverage journey_effective_blocked_external_only_count is not zero",
    )
    _require(
        _normalize_text(fleet_evidence.get("journey_overall_state")) == "ready",
        issues,
        "fleet coverage journey_overall_state is not ready",
    )

    for path in REQUIRED_ANCHOR_PATHS:
        _require(path.exists(), issues, f"required proof anchor is missing on disk: {path}")
    _require_file_tokens(
        BOOTSTRAP_GUARD,
        REQUIRED_BOOTSTRAP_GUARD_TOKENS,
        issues,
        label="pythonpath bootstrap guard script",
    )
    _require_file_tokens(
        BOOTSTRAP_GUARD_TEST,
        REQUIRED_BOOTSTRAP_GUARD_TOKENS,
        issues,
        label="pythonpath bootstrap guard test",
    )

    if not commands_dir_path.is_dir():
        issues.append(f"external proof commands directory is missing: {commands_dir_path}")
    else:
        for relative_name in EXPECTED_COMMAND_PATHS:
            candidate = commands_dir_path / relative_name
            _require(candidate.exists(), issues, f"external proof command artifact is missing: {candidate}")
            if candidate.exists() and candidate.is_file() and candidate.suffix == ".sh":
                _require(os.access(candidate, os.X_OK), issues, f"external proof command is not executable: {candidate}")
            if candidate.exists() and candidate.is_file() and candidate.suffix.lower() in COMMAND_BUNDLE_SUFFIXES:
                command_body = candidate.read_text(encoding="utf-8")
                for entry in _disallowed_entries([command_body]):
                    issues.append(f"external proof command cites active-run telemetry/helper proof: {candidate}: {entry}")
        for host in ("linux", "macos", "windows"):
            lane_path = commands_dir_path / f"run-{host}-proof-lane.sh"
            bundle_path = commands_dir_path / f"bundle-{host}-proof.sh"
            ingest_path = commands_dir_path / f"ingest-{host}-proof-bundle.sh"
            retained_bundle_dir = commands_dir_path / "host-proof-bundles" / host
            _require(
                retained_bundle_dir.is_dir(),
                issues,
                f"external proof retained host bundle directory is missing for {host}: {retained_bundle_dir}",
            )
            retained_manifest = _load_retained_bundle_manifest(retained_bundle_dir, issues, host=host)
            _require(
                retained_manifest == _expected_zero_backlog_manifest(host),
                issues,
                f"external proof retained host bundle manifest is not zero-backlog for {host}",
            )
            if lane_path.is_file():
                lane_body = lane_path.read_text(encoding="utf-8")
                for token in (
                    f"./preflight-{host}-proof.sh",
                    f"./capture-{host}-proof.sh",
                    f"./validate-{host}-proof.sh",
                    f"./bundle-{host}-proof.sh",
                ):
                    _require(
                        token in lane_body,
                        issues,
                        f"external proof host lane script is missing required token for {host}: {token}",
                    )
            if bundle_path.is_file():
                bundle_body = bundle_path.read_text(encoding="utf-8")
                _require_tokens(
                    bundle_body,
                    tuple(token.format(host=host) for token in REQUIRED_ZERO_BACKLOG_BUNDLE_TOKENS),
                    issues,
                    label=f"external proof zero-backlog bundle script for {host}",
                )
            if ingest_path.is_file():
                ingest_body = ingest_path.read_text(encoding="utf-8")
                _require_tokens(
                    ingest_body,
                    tuple(token.format(host=host) for token in REQUIRED_ZERO_BACKLOG_INGEST_TOKENS),
                    issues,
                    label=f"external proof zero-backlog ingest script for {host}",
                )
        finalize_path = commands_dir_path / "finalize-external-host-proof.sh"
        if finalize_path.is_file():
            finalize_body = finalize_path.read_text(encoding="utf-8")
            _require(
                "./republish-after-host-proof.sh" in finalize_body,
                issues,
                "external proof finalize script is missing republish token",
            )
            for host in ("linux", "macos", "windows"):
                for token in (
                    f"./validate-{host}-proof.sh",
                    f"./ingest-{host}-proof-bundle.sh",
                ):
                    _require(
                        token in finalize_body,
                        issues,
                        f"external proof finalize script is missing required token for {host}: {token}",
                    )
                validate_index = finalize_body.find(f"./validate-{host}-proof.sh")
                ingest_index = finalize_body.find(f"./ingest-{host}-proof-bundle.sh")
                republish_index = finalize_body.find("./republish-after-host-proof.sh")
                _require(
                    validate_index >= 0 and ingest_index >= 0 and validate_index < ingest_index,
                    issues,
                    f"external proof finalize script must validate before ingest for {host}",
                )
                _require(
                    ingest_index >= 0 and republish_index >= 0 and ingest_index < republish_index,
                    issues,
                    f"external proof finalize script must ingest {host} before republish",
                )

    queue_item_matches, queue_item = _queue_item(queue, PACKAGE_ID)
    design_item_matches, design_item = _queue_item(design_queue, PACKAGE_ID)
    milestone = _registry_milestone(registry)
    work_task_matches = _registry_work_tasks(milestone)
    work_task = work_task_matches[0] if work_task_matches else {}

    _require(_normalize_text(queue.get("program_wave")) == "next_90_day_product_advance", issues, "queue staging program_wave is not next_90_day_product_advance")
    _require(_normalize_text(queue.get("status")) == "live_parallel_successor", issues, "queue staging status is not live_parallel_successor")
    _require(
        _normalize_text(queue.get("source_registry_path")) == str(successor_registry_path),
        issues,
        "queue staging source_registry_path drifted from successor registry",
    )
    _require(
        _normalize_text(queue.get("source_design_queue_path")) == str(design_queue_staging_path),
        issues,
        "queue staging source_design_queue_path drifted from design queue staging",
    )
    _require(
        _normalize_text(design_queue.get("program_wave")) == "next_90_day_product_advance",
        issues,
        "design queue staging program_wave is not next_90_day_product_advance",
    )
    _require(
        _normalize_text(design_queue.get("source_registry_path")) == str(successor_registry_path),
        issues,
        "design queue staging source_registry_path drifted from successor registry",
    )
    _require(
        _normalize_text(design_queue.get("status")) == "live_parallel_successor",
        issues,
        "design queue staging status is not live_parallel_successor",
    )

    _require(bool(milestone), issues, f"registry milestone {MILESTONE_ID} is missing")
    if milestone:
        _require(_normalize_text(milestone.get("title")) == MILESTONE_TITLE, issues, "registry milestone title drifted")
        _require(_normalize_text(milestone.get("wave")) == WAVE, issues, "registry milestone wave drifted")
        _require(_normalize_text(milestone.get("status")) == "in_progress", issues, "registry milestone status is not in_progress")
        owners = {_normalize_text(item) for item in _normalize_list(milestone.get("owners"))}
        _require("fleet" in owners, issues, "registry milestone owners do not include fleet")

    _require(len(work_task_matches) == 1, issues, f"registry work task {WORK_TASK_ID} is missing or duplicated")
    _require(len(queue_item_matches) == 1, issues, f"queue staging item {PACKAGE_ID} is missing or duplicated")
    _require(len(design_item_matches) == 1, issues, f"design queue staging item {PACKAGE_ID} is missing or duplicated")

    registry_evidence = _normalize_list(work_task.get("evidence"))
    queue_proof = _normalize_list(queue_item.get("proof"))
    design_proof = _normalize_list(design_item.get("proof"))
    missing_registry_markers = _missing_markers(registry_evidence, REQUIRED_REGISTRY_EVIDENCE_MARKERS)
    missing_queue_markers = _missing_markers(queue_proof, REQUIRED_QUEUE_PROOF_MARKERS)
    missing_design_markers = _missing_markers(design_proof, REQUIRED_QUEUE_PROOF_MARKERS)
    for marker in missing_registry_markers:
        issues.append(f"registry evidence missing marker: {marker}")
    for marker in missing_queue_markers:
        issues.append(f"queue proof missing marker: {marker}")
    for marker in missing_design_markers:
        issues.append(f"design queue proof missing marker: {marker}")
    for entry in _disallowed_entries(registry_evidence):
        issues.append(f"registry evidence cites active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_entries(queue_proof):
        issues.append(f"queue proof cites active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_entries(design_proof):
        issues.append(f"design queue proof cites active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_payload_entries(work_task):
        issues.append(f"registry work task cites active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_payload_entries(queue_item):
        issues.append(f"queue item cites active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_payload_entries(design_item):
        issues.append(f"design queue item cites active-run telemetry/helper proof: {entry}")
    for marker in _missing_markers([closeout_note_body], REQUIRED_CLOSEOUT_NOTE_MARKERS):
        issues.append(f"closeout note missing marker: {marker}")
    for entry in _disallowed_entries([runbook_body]):
        issues.append(f"external proof runbook cites active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_entries([json.dumps(support_summary, sort_keys=True)]):
        issues.append(f"support packets summary cites active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_entries([json.dumps(unresolved_backlog, sort_keys=True)]):
        issues.append(f"support packets unresolved_external_proof cites active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_entries([json.dumps(execution_plan, sort_keys=True)]):
        issues.append(f"support packets external-proof execution plan cites active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_entries([json.dumps(journey_summary, sort_keys=True)]):
        issues.append(f"journey gates summary cites active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_entries([json.dumps(journey_rows, sort_keys=True)]):
        issues.append(f"journey gate rows cite active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_entries([json.dumps(release_tuple_coverage, sort_keys=True)]):
        issues.append(f"release channel desktopTupleCoverage cites active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_entries([json.dumps(external_host_proof, sort_keys=True)]):
        issues.append(f"flagship readiness external_host_proof cites active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_entries([json.dumps(fleet_evidence, sort_keys=True)]):
        issues.append(f"fleet coverage evidence cites active-run telemetry/helper proof: {entry}")
    for entry in _disallowed_entries([closeout_note_body]):
        issues.append(f"closeout note cites active-run telemetry/helper proof: {entry}")

    if work_task:
        _require(_normalize_text(work_task.get("owner")) == "fleet", issues, "registry work task owner is not fleet")
        _require(_normalize_text(work_task.get("title")) == WORK_TASK_TITLE, issues, "registry work task title drifted")
        _require(_normalize_text(work_task.get("status")) == "complete", issues, "registry work task status is not complete")
    for prefix, item in (
        ("queue", queue_item),
        ("design queue", design_item),
    ):
        if not item:
            continue
        _require(_normalize_text(item.get("title")) == QUEUE_TITLE, issues, f"{prefix} item title drifted")
        _require(_normalize_text(item.get("task")) == QUEUE_TASK, issues, f"{prefix} item task drifted")
        _require(_normalize_text(item.get("wave")) == WAVE, issues, f"{prefix} item wave drifted")
        _require(_normalize_text(item.get("repo")) == "fleet", issues, f"{prefix} item repo is not fleet")
        _require(_normalize_text(item.get("status")) == "complete", issues, f"{prefix} item status is not complete")
        _require(_normalize_text(item.get("frontier_id")) == FRONTIER_ID, issues, f"{prefix} item frontier_id drifted")
        _require(_coerce_int(item.get("milestone_id"), -1) == MILESTONE_ID, issues, f"{prefix} item milestone_id drifted")
        _require(
            _normalize_list(item.get("allowed_paths")) == ALLOWED_PATHS,
            issues,
            f"{prefix} item allowed_paths drifted",
        )
        _require(
            _normalize_list(item.get("owned_surfaces")) == OWNED_SURFACES,
            issues,
            f"{prefix} item owned_surfaces drifted",
        )
        _require(
            _normalize_text(item.get("completion_action")) == COMPLETION_ACTION,
            issues,
            f"{prefix} item completion_action is not verify_closed_package_only",
        )
        _require(
            _normalize_text(item.get("do_not_reopen_reason")) == DO_NOT_REOPEN_REASON,
            issues,
            f"{prefix} item do_not_reopen_reason drifted",
        )
    if queue_item and design_item:
        for field in (
            "title",
            "task",
            "frontier_id",
            "milestone_id",
            "wave",
            "repo",
            "status",
            "completion_action",
            "do_not_reopen_reason",
            "allowed_paths",
            "owned_surfaces",
        ):
            _require(
                queue_item.get(field) == design_item.get(field),
                issues,
                f"design-owned queue source row does not match Fleet queue field: {field}",
            )
        _require(
            queue_proof == design_proof,
            issues,
            "design-owned queue source proof list does not match Fleet queue proof list",
        )

    payload = {
        "status": "pass" if not issues else "fail",
        "package_id": PACKAGE_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "support_packets": str(support_packets_path),
        "journey_gates": str(journey_gates_path),
        "release_channel": str(release_channel_path),
        "external_proof_runbook": str(runbook_path),
        "external_proof_commands_dir": str(commands_dir_path),
        "flagship_readiness": str(flagship_readiness_path),
        "successor_registry": str(successor_registry_path),
        "queue_staging": str(queue_staging_path),
        "design_queue_staging": str(design_queue_staging_path),
        "closeout_note": str(closeout_note_path),
        "issues": issues,
    }
    return payload


def main(argv: List[str] | None = None) -> int:
    parsed_args = parse_args(argv)
    payload = verify(parsed_args)
    if payload["status"] != "pass":
        if payload.get("issues"):
            for issue in payload["issues"]:
                print(f"{PACKAGE_ID} verifier failed: {issue}", file=sys.stderr)
        else:
            print(f"{PACKAGE_ID} verifier failed", file=sys.stderr)
        if parsed_args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    if parsed_args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"verified {PACKAGE_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
