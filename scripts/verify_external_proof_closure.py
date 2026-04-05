#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


DEFAULT_SUPPORT_PACKETS = Path("/docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json")
DEFAULT_JOURNEY_GATES = Path("/docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json")
DEFAULT_RELEASE_CHANNEL = Path(
    "/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json"
)
DEFAULT_EXTERNAL_PROOF_RUNBOOK = Path("/docker/fleet/.codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md")
DEFAULT_EXTERNAL_PROOF_COMMANDS_DIR = Path("/docker/fleet/.codex-studio/published/external-proof-commands")
DEFAULT_MAX_ARTIFACT_AGE_HOURS = 24


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fail closed when desktop external-proof closure is still incomplete across support packets, "
            "journey gates, or release-channel tuple coverage."
        )
    )
    parser.add_argument("--support-packets", type=Path, default=DEFAULT_SUPPORT_PACKETS)
    parser.add_argument("--journey-gates", type=Path, default=DEFAULT_JOURNEY_GATES)
    parser.add_argument("--release-channel", type=Path, default=DEFAULT_RELEASE_CHANNEL)
    parser.add_argument(
        "--external-proof-runbook",
        type=Path,
        default=None,
        help=(
            "Optional markdown runbook path. When set, fail closed if the generated runbook is missing, "
            "unreadable, stale, or out of sync with support/release timestamps."
        ),
    )
    parser.add_argument(
        "--external-proof-commands-dir",
        type=Path,
        default=None,
        help=(
            "Optional command bundle directory. When set, fail closed if required host scripts are missing or "
            "non-executable while backlog is open."
        ),
    )
    parser.add_argument(
        "--max-artifact-age-hours",
        type=int,
        default=DEFAULT_MAX_ARTIFACT_AGE_HOURS,
        help=(
            "Fail closed when release/support/journey evidence timestamps are older than this many hours. "
            "Set to 0 to disable max-age checks."
        ),
    )
    return parser.parse_args()


def _load_json(path: Path, *, label: str) -> Dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"{label} not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{label} is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{label} root must be a JSON object: {path}")
    return payload


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _dict_field(value: Any, *, field: str, failures: list[str]) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if value not in (None, "", []):
        failures.append(f"{field} has invalid type")
    return {}


def _safe_int(value: Any, *, field: str, failures: list[str]) -> int:
    if isinstance(value, bool):
        failures.append(f"{field} has invalid numeric value")
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    raw = str(value or "").strip()
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        failures.append(f"{field} has invalid numeric value")
        return 0


def _parse_iso(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _load_text(path: Path, *, label: str) -> str:
    if not path.is_file():
        raise SystemExit(f"{label} not found: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"{label} is unreadable: {path}: {exc}") from exc


def _extract_runbook_field(markdown: str, key: str) -> str:
    needle = f"- {key}:"
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith(needle):
            return line[len(needle) :].strip().strip("`")
    return ""


def _is_sha256_hex(value: Any) -> bool:
    raw = str(value or "").strip().lower()
    return bool(raw) and len(raw) == 64 and all(ch in "0123456789abcdef" for ch in raw)


def _normalized_platform(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalized_token(value: Any) -> str:
    return str(value or "").strip()


def _normalize_host_token(value: str) -> str:
    text = "".join(ch if ch.isalnum() else "-" for ch in _normalized_token(value).lower())
    text = text.strip("-")
    return text or "unknown"


def _normalized_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(
        {
            _normalized_token(token).lower()
            for token in value
            if _normalized_token(token)
        }
    )


def _normalized_smoke_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "status_any_of": [],
            "ready_checkpoint": "",
            "head_id": "",
            "platform": "",
            "rid": "",
            "host_class_contains": "",
        }
    return {
        "status_any_of": _normalized_string_list(value.get("status_any_of") or value.get("statusAnyOf")),
        "ready_checkpoint": _normalized_token(value.get("ready_checkpoint") or value.get("readyCheckpoint")).lower(),
        "head_id": _normalized_token(value.get("head_id") or value.get("headId")).lower(),
        "platform": _normalized_platform(value.get("platform")),
        "rid": _normalized_token(value.get("rid")).lower(),
        "host_class_contains": _normalized_token(
            value.get("host_class_contains") or value.get("hostClassContains")
        ).lower(),
    }


def _normalized_command_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        _normalized_token(item)
        for item in value
        if _normalized_token(item)
    ]


def _powershell_wrap(command: str) -> str:
    escaped = _normalized_token(command).replace("'", "''")
    return f"bash -lc '{escaped}'"


def _release_external_request_index(rows: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        return {}
    index: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        tuple_id = _normalized_token(item.get("tupleId") or item.get("tuple_id"))
        if not tuple_id:
            continue
        index[tuple_id] = {
            "tuple_id": tuple_id,
            "required_host": _normalized_platform(item.get("requiredHost") or item.get("required_host")),
            "required_proofs": _normalized_string_list(item.get("requiredProofs") or item.get("required_proofs")),
            "expected_artifact_id": _normalized_token(item.get("expectedArtifactId") or item.get("expected_artifact_id")),
            "expected_installer_file_name": _normalized_token(
                item.get("expectedInstallerFileName") or item.get("expected_installer_file_name")
            ),
            "expected_public_install_route": _normalized_token(
                item.get("expectedPublicInstallRoute") or item.get("expected_public_install_route")
            ),
            "expected_startup_smoke_receipt_path": _normalized_token(
                item.get("expectedStartupSmokeReceiptPath") or item.get("expected_startup_smoke_receipt_path")
            ),
            "expected_installer_sha256": _normalized_token(
                item.get("expectedInstallerSha256") or item.get("expected_installer_sha256")
            ).lower(),
            "proof_capture_commands": _normalized_command_list(
                item.get("proofCaptureCommands") or item.get("proof_capture_commands")
            ),
        }
    return index


def _support_request_row_index(rows: list[tuple[str, int, dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for _, _, item in rows:
        tuple_id = _normalized_token(item.get("tuple_id") or item.get("tupleId"))
        if not tuple_id:
            continue
        index[tuple_id] = {
            "tuple_id": tuple_id,
            "required_host": _normalized_platform(item.get("required_host") or item.get("requiredHost") or item.get("platform")),
            "required_proofs": _normalized_string_list(item.get("required_proofs") or item.get("requiredProofs")),
            "expected_artifact_id": _normalized_token(item.get("expected_artifact_id") or item.get("expectedArtifactId")),
            "expected_installer_file_name": _normalized_token(
                item.get("expected_installer_file_name") or item.get("expectedInstallerFileName")
            ),
            "expected_public_install_route": _normalized_token(
                item.get("expected_public_install_route") or item.get("expectedPublicInstallRoute")
            ),
            "expected_startup_smoke_receipt_path": _normalized_token(
                item.get("expected_startup_smoke_receipt_path") or item.get("expectedStartupSmokeReceiptPath")
            ),
            "expected_installer_sha256": _normalized_token(
                item.get("expected_installer_sha256") or item.get("expectedInstallerSha256")
            ).lower(),
            "proof_capture_commands": _normalized_command_list(
                item.get("proof_capture_commands") or item.get("proofCaptureCommands")
            ),
        }
    return index


def _support_specs_index(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    index: dict[str, dict[str, Any]] = {}
    for raw_tuple_id, raw_spec in value.items():
        tuple_id = _normalized_token(raw_tuple_id)
        if not tuple_id or not isinstance(raw_spec, dict):
            continue
        index[tuple_id] = {
            "tuple_id": tuple_id,
            "required_host": _normalized_platform(raw_spec.get("required_host") or raw_spec.get("requiredHost")),
            "required_proofs": _normalized_string_list(raw_spec.get("required_proofs") or raw_spec.get("requiredProofs")),
            "expected_artifact_id": _normalized_token(raw_spec.get("expected_artifact_id") or raw_spec.get("expectedArtifactId")),
            "expected_installer_file_name": _normalized_token(
                raw_spec.get("expected_installer_file_name") or raw_spec.get("expectedInstallerFileName")
            ),
            "expected_public_install_route": _normalized_token(
                raw_spec.get("expected_public_install_route") or raw_spec.get("expectedPublicInstallRoute")
            ),
            "expected_startup_smoke_receipt_path": _normalized_token(
                raw_spec.get("expected_startup_smoke_receipt_path") or raw_spec.get("expectedStartupSmokeReceiptPath")
            ),
            "expected_installer_sha256": _normalized_token(
                raw_spec.get("expected_installer_sha256") or raw_spec.get("expectedInstallerSha256")
            ).lower(),
            "proof_capture_commands": _normalized_command_list(
                raw_spec.get("proof_capture_commands") or raw_spec.get("proofCaptureCommands")
            ),
        }
    return index


def _age_seconds(ts: datetime, *, now: datetime) -> float:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=now.tzinfo)
    return (now - ts).total_seconds()


def main() -> int:
    args = _parse_args()
    support_packets = _load_json(args.support_packets, label="support packets")
    journey_gates = _load_json(args.journey_gates, label="journey gates")
    release_channel = _load_json(args.release_channel, label="release channel")

    failures: list[str] = []
    raw_support_summary = support_packets.get("summary")
    raw_journey_summary = journey_gates.get("summary")
    raw_tuple_coverage = release_channel.get("desktopTupleCoverage")
    if not isinstance(raw_support_summary, dict):
        failures.append("support packets summary is missing or not an object")
    if not isinstance(raw_journey_summary, dict):
        failures.append("journey gates summary is missing or not an object")
    if not isinstance(raw_tuple_coverage, dict):
        failures.append("release channel desktopTupleCoverage is missing or not an object")

    support_summary = _as_dict(raw_support_summary)
    journey_summary = _as_dict(raw_journey_summary)
    tuple_coverage = _as_dict(raw_tuple_coverage)
    support_plan = _as_dict(support_packets.get("unresolved_external_proof_execution_plan"))
    if not isinstance(support_packets.get("unresolved_external_proof_execution_plan"), dict):
        failures.append("support packets unresolved_external_proof_execution_plan is missing or not an object")

    missing_platforms_raw = tuple_coverage.get("missingRequiredPlatforms")
    missing_head_pairs_raw = tuple_coverage.get("missingRequiredPlatformHeadPairs")
    missing_tuples_raw = tuple_coverage.get("missingRequiredPlatformHeadRidTuples")
    external_proof_requests_raw = tuple_coverage.get("externalProofRequests")
    if "missingRequiredPlatforms" not in tuple_coverage:
        failures.append("release channel desktopTupleCoverage.missingRequiredPlatforms is missing")
    elif not isinstance(missing_platforms_raw, list):
        failures.append("release channel desktopTupleCoverage.missingRequiredPlatforms is not an array")
    if "missingRequiredPlatformHeadPairs" not in tuple_coverage:
        failures.append("release channel desktopTupleCoverage.missingRequiredPlatformHeadPairs is missing")
    elif not isinstance(missing_head_pairs_raw, list):
        failures.append(
            "release channel desktopTupleCoverage.missingRequiredPlatformHeadPairs is not an array"
        )
    if "missingRequiredPlatformHeadRidTuples" not in tuple_coverage:
        failures.append(
            "release channel desktopTupleCoverage.missingRequiredPlatformHeadRidTuples is missing"
        )
    elif not isinstance(missing_tuples_raw, list):
        failures.append(
            "release channel desktopTupleCoverage.missingRequiredPlatformHeadRidTuples is not an array"
        )
    if "externalProofRequests" not in tuple_coverage:
        failures.append("release channel desktopTupleCoverage.externalProofRequests is missing")
    elif not isinstance(external_proof_requests_raw, list):
        failures.append("release channel desktopTupleCoverage.externalProofRequests is not an array")

    support_summary_key_types = {
        "unresolved_external_proof_request_count": (int, float, str),
        "unresolved_external_proof_request_hosts": list,
        "unresolved_external_proof_request_tuples": list,
        "unresolved_external_proof_request_host_counts": dict,
        "unresolved_external_proof_request_tuple_counts": dict,
    }
    for key, expected in support_summary_key_types.items():
        if key not in support_summary:
            failures.append(f"support packets summary.{key} is missing")
            continue
        if not isinstance(support_summary.get(key), expected):
            failures.append(f"support packets summary.{key} has invalid type")
    if "unresolved_external_proof_request_specs" not in support_summary:
        failures.append("support packets summary.unresolved_external_proof_request_specs is missing")
    elif not isinstance(support_summary.get("unresolved_external_proof_request_specs"), (dict, list)):
        failures.append("support packets summary.unresolved_external_proof_request_specs has invalid type")

    journey_summary_key_types = {
        "blocked_external_only_count": (int, float, str),
        "blocked_external_only_hosts": list,
        "blocked_external_only_tuples": list,
        "blocked_external_only_host_counts": dict,
    }
    for key, expected in journey_summary_key_types.items():
        if key not in journey_summary:
            failures.append(f"journey gates summary.{key} is missing")
            continue
        if not isinstance(journey_summary.get(key), expected):
            failures.append(f"journey gates summary.{key} has invalid type")

    support_plan_key_types = {
        "request_count": (int, float, str),
        "hosts": list,
        "host_groups": dict,
    }
    for key, expected in support_plan_key_types.items():
        if key not in support_plan:
            failures.append(f"support packets unresolved_external_proof_execution_plan.{key} is missing")
            continue
        if not isinstance(support_plan.get(key), expected):
            failures.append(
                f"support packets unresolved_external_proof_execution_plan.{key} has invalid type"
            )

    journey_rows = [
        dict(item)
        for item in (journey_gates.get("journeys") or [])
        if isinstance(item, dict)
    ]

    unresolved_count = _safe_int(
        support_summary.get("unresolved_external_proof_request_count"),
        field="support packets summary.unresolved_external_proof_request_count",
        failures=failures,
    )
    blocked_external_only_count = _safe_int(
        journey_summary.get("blocked_external_only_count"),
        field="journey gates summary.blocked_external_only_count",
        failures=failures,
    )
    support_plan_request_count = _safe_int(
        support_plan.get("request_count"),
        field="support packets unresolved_external_proof_execution_plan.request_count",
        failures=failures,
    )
    support_plan_capture_deadline_hours = _safe_int(
        support_plan.get("capture_deadline_hours"),
        field="support packets unresolved_external_proof_execution_plan.capture_deadline_hours",
        failures=failures,
    )
    support_plan_capture_deadline_utc = str(
        support_plan.get("capture_deadline_utc") or support_plan.get("captureDeadlineUtc") or ""
    ).strip()
    support_host_count_map = _dict_field(
        support_summary.get("unresolved_external_proof_request_host_counts"),
        field="support packets summary.unresolved_external_proof_request_host_counts",
        failures=failures,
    )
    support_tuple_count_map = _dict_field(
        support_summary.get("unresolved_external_proof_request_tuple_counts"),
        field="support packets summary.unresolved_external_proof_request_tuple_counts",
        failures=failures,
    )
    journey_host_count_map = _dict_field(
        journey_summary.get("blocked_external_only_host_counts"),
        field="journey gates summary.blocked_external_only_host_counts",
        failures=failures,
    )
    support_plan_hosts = sorted(
        {
            str(item).strip()
            for item in (support_plan.get("hosts") or [])
            if str(item).strip()
        }
    )
    support_plan_host_groups = _dict_field(
        support_plan.get("host_groups"),
        field="support packets unresolved_external_proof_execution_plan.host_groups",
        failures=failures,
    )
    support_plan_hosts_with_backlog = sorted(
        {
            str(raw_host).strip()
            for raw_host, raw_group in support_plan_host_groups.items()
            if str(raw_host).strip()
            and isinstance(raw_group, dict)
            and (
                _safe_int(
                    raw_group.get("request_count"),
                    field=(
                        "support packets unresolved_external_proof_execution_plan.host_groups"
                        f".{str(raw_host).strip()}.request_count"
                    ),
                    failures=failures,
                )
                > 0
                or any(str(item).strip() for item in (raw_group.get("tuples") or []))
                or any(isinstance(item, dict) for item in (raw_group.get("requests") or []))
            )
        }
    )
    support_plan_request_rows: list[tuple[str, int, dict[str, Any]]] = []
    for raw_host, raw_group in support_plan_host_groups.items():
        host = str(raw_host).strip()
        if not host or not isinstance(raw_group, dict):
            continue
        raw_requests = raw_group.get("requests")
        if not isinstance(raw_requests, list):
            continue
        for index, item in enumerate(raw_requests):
            if not isinstance(item, dict):
                continue
            support_plan_request_rows.append((host, index, dict(item)))
    support_plan_request_deadlines = sorted(
        {
            str(item.get("capture_deadline_utc") or item.get("captureDeadlineUtc") or "").strip()
            for raw_group in support_plan_host_groups.values()
            if isinstance(raw_group, dict)
            for item in (raw_group.get("requests") or [])
            if isinstance(item, dict)
            and str(item.get("capture_deadline_utc") or item.get("captureDeadlineUtc") or "").strip()
        }
    )
    support_plan_request_rows_missing_deadline = sorted(
        {
            str(item.get("tuple_id") or item.get("tupleId") or "").strip() or "<unknown>"
            for raw_group in support_plan_host_groups.values()
            if isinstance(raw_group, dict)
            for item in (raw_group.get("requests") or [])
            if isinstance(item, dict)
            and not str(item.get("capture_deadline_utc") or item.get("captureDeadlineUtc") or "").strip()
        }
    )
    support_plan_request_rows_missing_required_proofs = sorted(
        {
            str(item.get("tuple_id") or item.get("tupleId") or "").strip() or "<unknown>"
            for _, _, item in support_plan_request_rows
            if not {
                str(token).strip().lower()
                for token in (
                    item.get("required_proofs")
                    if isinstance(item.get("required_proofs"), list)
                    else item.get("requiredProofs")
                    if isinstance(item.get("requiredProofs"), list)
                    else []
                )
                if str(token).strip()
            }.issuperset({"promoted_installer_artifact", "startup_smoke_receipt"})
        }
    )
    support_plan_request_rows_missing_capture_commands = sorted(
        {
            str(item.get("tuple_id") or item.get("tupleId") or "").strip() or "<unknown>"
            for _, _, item in support_plan_request_rows
            if not [
                str(token).strip()
                for token in (
                    item.get("proof_capture_commands")
                    if isinstance(item.get("proof_capture_commands"), list)
                    else item.get("proofCaptureCommands")
                    if isinstance(item.get("proofCaptureCommands"), list)
                    else []
                )
                if str(token).strip()
            ]
        }
    )
    support_plan_request_rows_missing_expected_fields = sorted(
        {
            f"{(str(item.get('tuple_id') or item.get('tupleId') or '').strip() or '<unknown>')}:{field}"
            for _, _, item in support_plan_request_rows
            for field, value in (
                ("expected_artifact_id", item.get("expected_artifact_id") or item.get("expectedArtifactId")),
                (
                    "expected_installer_file_name",
                    item.get("expected_installer_file_name") or item.get("expectedInstallerFileName"),
                ),
                (
                    "expected_public_install_route",
                    item.get("expected_public_install_route") or item.get("expectedPublicInstallRoute"),
                ),
                (
                    "expected_startup_smoke_receipt_path",
                    item.get("expected_startup_smoke_receipt_path")
                    or item.get("expectedStartupSmokeReceiptPath"),
                ),
            )
            if not str(value or "").strip()
        }
    )
    support_plan_request_rows_invalid_expected_sha256 = sorted(
        {
            str(item.get("tuple_id") or item.get("tupleId") or "").strip() or "<unknown>"
            for _, _, item in support_plan_request_rows
            for value in [
                item.get("expected_installer_sha256")
                if item.get("expected_installer_sha256") is not None
                else item.get("expectedInstallerSha256")
            ]
            if str(value or "").strip() and not _is_sha256_hex(value)
        }
    )
    support_generated_at = str(
        support_packets.get("generated_at") or support_packets.get("generatedAt") or ""
    ).strip()
    support_plan_generated_at = str(
        support_plan.get("generated_at") or support_plan.get("generatedAt") or ""
    ).strip()
    release_generated_at = str(
        release_channel.get("generatedAt") or release_channel.get("generated_at") or ""
    ).strip()
    support_plan_release_generated_at = str(
        support_plan.get("release_channel_generated_at") or support_plan.get("releaseChannelGeneratedAt") or ""
    ).strip()
    journey_support_generated_ats = sorted(
        {
            str((row.get("evidence") or {}).get("support_packets_generated_at") or "").strip()
            for row in journey_rows
            if str((row.get("evidence") or {}).get("support_packets_generated_at") or "").strip()
        }
    )
    journey_rows_missing_support_generated_at = sorted(
        {
            str(row.get("id") or "").strip() or "<unknown>"
            for row in journey_rows
            if not str((row.get("evidence") or {}).get("support_packets_generated_at") or "").strip()
        }
    )
    missing_platforms = [
        str(item).strip()
        for item in (missing_platforms_raw or [])
        if str(item).strip()
    ]
    missing_head_pairs = [
        str(item).strip()
        for item in (missing_head_pairs_raw or [])
        if str(item).strip()
    ]
    missing_tuples = [
        str(item).strip()
        for item in (missing_tuples_raw or [])
        if str(item).strip()
    ]
    external_request_tuples: list[str] = []
    if isinstance(external_proof_requests_raw, list):
        for index, request in enumerate(external_proof_requests_raw):
            if not isinstance(request, dict):
                failures.append(
                    "release channel desktopTupleCoverage.externalProofRequests"
                    f"[{index}] is not an object"
                )
                continue
            tuple_id = str(request.get("tupleId") or request.get("tuple_id") or "").strip()
            if not tuple_id:
                failures.append(
                    "release channel desktopTupleCoverage.externalProofRequests"
                    f"[{index}] is missing tupleId"
                )
                continue
            external_request_tuples.append(tuple_id)
            tuple_parts = tuple_id.split(":")
            if len(tuple_parts) != 3:
                failures.append(
                    "release channel desktopTupleCoverage.externalProofRequests"
                    f"[{index}] tupleId is malformed: {tuple_id}"
                )
            required_host = str(request.get("requiredHost") or request.get("required_host") or "").strip().lower()
            if required_host and required_host not in {"windows", "macos", "linux"}:
                failures.append(
                    "release channel desktopTupleCoverage.externalProofRequests"
                    f"[{index}] requiredHost is invalid: {required_host}"
                )
            if required_host and len(tuple_parts) == 3 and tuple_parts[2].strip().lower() != required_host:
                failures.append(
                    "release channel desktopTupleCoverage.externalProofRequests"
                    f"[{index}] requiredHost ({required_host}) does not match tuple platform ({tuple_parts[2].strip().lower()})"
                )
            required_proofs_raw = request.get("requiredProofs")
            if required_proofs_raw is None:
                required_proofs_raw = request.get("required_proofs")
            if not isinstance(required_proofs_raw, list) or not all(
                isinstance(token, str) for token in required_proofs_raw
            ):
                failures.append(
                    "release channel desktopTupleCoverage.externalProofRequests"
                    f"[{index}] requiredProofs must be a string array"
                )
                continue
            required_proofs = {str(token).strip().lower() for token in required_proofs_raw if str(token).strip()}
            missing_required_proofs = sorted(
                {"promoted_installer_artifact", "startup_smoke_receipt"} - required_proofs
            )
            if missing_required_proofs:
                failures.append(
                    "release channel desktopTupleCoverage.externalProofRequests"
                    f"[{index}] requiredProofs is missing required tokens: {', '.join(missing_required_proofs)}"
                )
            expected_installer_sha256 = (
                request.get("expectedInstallerSha256")
                if request.get("expectedInstallerSha256") is not None
                else request.get("expected_installer_sha256")
            )
            if str(expected_installer_sha256 or "").strip() and not _is_sha256_hex(expected_installer_sha256):
                failures.append(
                    "release channel desktopTupleCoverage.externalProofRequests"
                    f"[{index}] expectedInstallerSha256 must be a 64-character lowercase sha256 hex digest"
                )
    unresolved_tuples = [
        str(item).strip()
        for item in (support_summary.get("unresolved_external_proof_request_tuples") or [])
        if str(item).strip()
    ]
    unresolved_hosts = [
        str(item).strip()
        for item in (support_summary.get("unresolved_external_proof_request_hosts") or [])
        if str(item).strip()
    ]
    unresolved_specs_raw = support_summary.get("unresolved_external_proof_request_specs")
    unresolved_specs = sorted(
        {
            str(item).strip()
            for item in (
                unresolved_specs_raw.keys()
                if isinstance(unresolved_specs_raw, dict)
                else (unresolved_specs_raw or [])
            )
            if str(item).strip()
        }
    )
    unresolved_backlog_raw = support_packets.get("unresolved_external_proof")
    unresolved_entries: list[dict[str, Any]] = []
    unresolved_backlog_count = 0
    unresolved_backlog_hosts: list[str] = []
    unresolved_backlog_tuples: list[str] = []
    unresolved_backlog_host_counts: dict[str, Any] = {}
    unresolved_backlog_tuple_counts: dict[str, Any] = {}
    unresolved_backlog_specs: dict[str, Any] = {}
    if isinstance(unresolved_backlog_raw, list):
        unresolved_entries = [dict(item) for item in unresolved_backlog_raw if isinstance(item, dict)]
        unresolved_backlog_count = len(unresolved_entries)
        unresolved_backlog_hosts = sorted(
            {
                str(item.get("required_host") or item.get("host") or "").strip()
                for item in unresolved_entries
                if str(item.get("required_host") or item.get("host") or "").strip()
            }
        )
        unresolved_backlog_tuples = sorted(
            {
                str(item.get("tuple_id") or item.get("tupleId") or "").strip()
                for item in unresolved_entries
                if str(item.get("tuple_id") or item.get("tupleId") or "").strip()
            }
        )
    elif isinstance(unresolved_backlog_raw, dict):
        unresolved_backlog_count = _safe_int(
            unresolved_backlog_raw.get("count"),
            field="support packets unresolved_external_proof.count",
            failures=failures,
        )
        unresolved_backlog_hosts = sorted(
            {
                str(item).strip()
                for item in (unresolved_backlog_raw.get("hosts") or [])
                if str(item).strip()
            }
        )
        unresolved_backlog_tuples = sorted(
            {
                str(item).strip()
                for item in (unresolved_backlog_raw.get("tuples") or [])
                if str(item).strip()
            }
        )
        unresolved_backlog_host_counts = _dict_field(
            unresolved_backlog_raw.get("host_counts"),
            field="support packets unresolved_external_proof.host_counts",
            failures=failures,
        )
        unresolved_backlog_tuple_counts = _dict_field(
            unresolved_backlog_raw.get("tuple_counts"),
            field="support packets unresolved_external_proof.tuple_counts",
            failures=failures,
        )
        unresolved_backlog_specs = _dict_field(
            unresolved_backlog_raw.get("specs"),
            field="support packets unresolved_external_proof.specs",
            failures=failures,
        )
    elif unresolved_backlog_raw is not None:
        failures.append("support packets unresolved_external_proof has invalid type (expected array or object)")
    blocked_external_only_tuples = [
        str(item).strip()
        for item in (journey_summary.get("blocked_external_only_tuples") or [])
        if str(item).strip()
    ]
    blocked_external_only_hosts = [
        str(item).strip()
        for item in (journey_summary.get("blocked_external_only_hosts") or [])
        if str(item).strip()
    ]
    journey_rows_with_external_requests = sorted(
        {
            str(row.get("id") or "").strip() or "<unknown>"
            for row in journey_rows
            if isinstance(row.get("external_proof_requests"), list) and row.get("external_proof_requests")
        }
    )
    journey_rows_with_malformed_external_requests = sorted(
        {
            str(row.get("id") or "").strip() or "<unknown>"
            for row in journey_rows
            if (
                "external_proof_requests" in row
                and not isinstance(row.get("external_proof_requests"), list)
                and row.get("external_proof_requests") not in (None, "")
            )
        }
    )

    if unresolved_count > 0:
        failures.append(
            f"support packets unresolved_external_proof_request_count={unresolved_count} (expected 0)"
        )
    if support_plan_request_count > 0:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.request_count="
            f"{support_plan_request_count} (expected 0)"
        )
    if blocked_external_only_count > 0:
        failures.append(
            f"journey gates blocked_external_only_count={blocked_external_only_count} (expected 0)"
        )
    if support_host_count_map:
        failures.append(
            "support packets unresolved_external_proof_request_host_counts is not empty: "
            + ", ".join(f"{host}:{count}" for host, count in sorted(support_host_count_map.items()))
        )
    if support_tuple_count_map:
        failures.append(
            "support packets unresolved_external_proof_request_tuple_counts is not empty: "
            + ", ".join(f"{tuple_id}:{count}" for tuple_id, count in sorted(support_tuple_count_map.items()))
        )
    if journey_host_count_map:
        failures.append(
            "journey gates blocked_external_only_host_counts is not empty: "
            + ", ".join(f"{host}:{count}" for host, count in sorted(journey_host_count_map.items()))
        )
    if support_plan_hosts:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.hosts is not empty: "
            + ", ".join(support_plan_hosts)
        )
    if support_plan_hosts_with_backlog:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.host_groups still contain backlog: "
            + ", ".join(support_plan_hosts_with_backlog)
        )
    if support_plan_request_deadlines and support_plan_capture_deadline_utc and support_plan_request_deadlines != [support_plan_capture_deadline_utc]:
        failures.append(
            "support packets unresolved_external_proof_execution_plan request capture_deadline_utc values do not match plan capture_deadline_utc: "
            + ", ".join(support_plan_request_deadlines)
        )
    if support_plan_request_rows_missing_deadline and support_plan_request_count > 0:
        failures.append(
            "support packets unresolved_external_proof_execution_plan request rows are missing capture_deadline_utc for tuples: "
            + ", ".join(support_plan_request_rows_missing_deadline)
        )
    if support_plan_request_rows_missing_required_proofs and support_plan_request_count > 0:
        failures.append(
            "support packets unresolved_external_proof_execution_plan request rows are missing required_proofs tokens "
            "(promoted_installer_artifact,startup_smoke_receipt) for tuples: "
            + ", ".join(support_plan_request_rows_missing_required_proofs)
        )
    if support_plan_request_rows_missing_capture_commands and support_plan_request_count > 0:
        failures.append(
            "support packets unresolved_external_proof_execution_plan request rows are missing proof_capture_commands for tuples: "
            + ", ".join(support_plan_request_rows_missing_capture_commands)
        )
    if support_plan_request_rows_missing_expected_fields and support_plan_request_count > 0:
        failures.append(
            "support packets unresolved_external_proof_execution_plan request rows are missing expected fields: "
            + ", ".join(support_plan_request_rows_missing_expected_fields)
        )
    if support_plan_request_rows_invalid_expected_sha256 and support_plan_request_count > 0:
        failures.append(
            "support packets unresolved_external_proof_execution_plan request rows have invalid expected_installer_sha256 values for tuples: "
            + ", ".join(support_plan_request_rows_invalid_expected_sha256)
        )
    if missing_platforms:
        failures.append(
            "release channel missingRequiredPlatforms is not empty: "
            + ", ".join(missing_platforms)
        )
    if missing_head_pairs:
        failures.append(
            "release channel missingRequiredPlatformHeadPairs is not empty: "
            + ", ".join(missing_head_pairs)
        )
    if missing_tuples:
        failures.append(
            "release channel missingRequiredPlatformHeadRidTuples is not empty: "
            + ", ".join(missing_tuples)
        )
    duplicate_external_request_tuples = sorted(
        {
            tuple_id
            for tuple_id in external_request_tuples
            if external_request_tuples.count(tuple_id) > 1
        }
    )
    if duplicate_external_request_tuples:
        failures.append(
            "release channel desktopTupleCoverage.externalProofRequests contains duplicate tupleId rows: "
            + ", ".join(duplicate_external_request_tuples)
        )
    if missing_tuples and sorted(set(external_request_tuples)) != sorted(set(missing_tuples)):
        failures.append(
            "release channel desktopTupleCoverage.externalProofRequests tupleId set does not match missingRequiredPlatformHeadRidTuples"
        )
    if not missing_tuples and external_request_tuples:
        failures.append(
            "release channel desktopTupleCoverage.externalProofRequests must be empty when missingRequiredPlatformHeadRidTuples is empty"
        )
    release_external_request_index = _release_external_request_index(external_proof_requests_raw)
    support_plan_request_index = _support_request_row_index(support_plan_request_rows)
    support_specs_index = _support_specs_index(unresolved_specs_raw)
    projection_drift_rows = sorted(
        {
            f"{tuple_id}:{field}"
            for tuple_id, expected in release_external_request_index.items()
            for field in (
                "required_host",
                "required_proofs",
                "expected_artifact_id",
                "expected_installer_file_name",
                "expected_public_install_route",
                "expected_startup_smoke_receipt_path",
                "expected_installer_sha256",
            )
            if (
                tuple_id in support_plan_request_index
                and support_plan_request_index[tuple_id].get(field) != expected.get(field)
            )
            or (
                tuple_id in support_specs_index
                and support_specs_index[tuple_id].get(field) != expected.get(field)
            )
        }
    )
    if projection_drift_rows:
        failures.append(
            "support external-proof projections drift from release channel desktopTupleCoverage.externalProofRequests for fields: "
            + ", ".join(projection_drift_rows)
        )
    if unresolved_tuples:
        failures.append(
            "support packets unresolved_external_proof_request_tuples is not empty: "
            + ", ".join(unresolved_tuples)
        )
    if unresolved_hosts:
        failures.append(
            "support packets unresolved_external_proof_request_hosts is not empty: "
            + ", ".join(unresolved_hosts)
        )
    if unresolved_specs:
        failures.append(
            "support packets unresolved_external_proof_request_specs is not empty: "
            + ", ".join(unresolved_specs)
        )
    if unresolved_backlog_count > 0:
        failures.append(
            "support packets unresolved_external_proof.count="
            f"{unresolved_backlog_count} (expected 0)"
        )
    if unresolved_backlog_hosts:
        failures.append(
            "support packets unresolved_external_proof.hosts is not empty: "
            + ", ".join(unresolved_backlog_hosts)
        )
    if unresolved_backlog_tuples:
        failures.append(
            "support packets unresolved_external_proof.tuples is not empty: "
            + ", ".join(unresolved_backlog_tuples)
        )
    if unresolved_backlog_host_counts:
        failures.append(
            "support packets unresolved_external_proof.host_counts is not empty: "
            + ", ".join(f"{host}:{count}" for host, count in sorted(unresolved_backlog_host_counts.items()))
        )
    if unresolved_backlog_tuple_counts:
        failures.append(
            "support packets unresolved_external_proof.tuple_counts is not empty: "
            + ", ".join(f"{tuple_id}:{count}" for tuple_id, count in sorted(unresolved_backlog_tuple_counts.items()))
        )
    if unresolved_backlog_specs:
        failures.append(
            "support packets unresolved_external_proof.specs is not empty: "
            + ", ".join(sorted(unresolved_backlog_specs.keys()))
        )
    if unresolved_entries:
        failures.append(
            "support packets unresolved_external_proof still contains unresolved entries: "
            + ", ".join(sorted({str(item.get("tuple_id") or item.get("tupleId") or "").strip() or "<unknown>" for item in unresolved_entries}))
        )
    if blocked_external_only_tuples:
        failures.append(
            "journey gates blocked_external_only_tuples is not empty: "
            + ", ".join(blocked_external_only_tuples)
        )
    if blocked_external_only_hosts:
        failures.append(
            "journey gates blocked_external_only_hosts is not empty: "
            + ", ".join(blocked_external_only_hosts)
        )
    if journey_rows_with_external_requests:
        failures.append(
            "journey gates still report external_proof_requests in journey rows: "
            + ", ".join(journey_rows_with_external_requests)
        )
    if journey_rows_with_malformed_external_requests:
        failures.append(
            "journey gates have malformed external_proof_requests payload in journey rows: "
            + ", ".join(journey_rows_with_malformed_external_requests)
        )
    if missing_tuples and unresolved_tuples and sorted(set(missing_tuples)) != sorted(set(unresolved_tuples)):
        failures.append(
            "support packets unresolved_external_proof_request_tuples does not match release channel missingRequiredPlatformHeadRidTuples"
        )
    if missing_tuples and blocked_external_only_tuples and sorted(set(missing_tuples)) != sorted(set(blocked_external_only_tuples)):
        failures.append(
            "journey gates blocked_external_only_tuples does not match release channel missingRequiredPlatformHeadRidTuples"
        )
    if not release_generated_at:
        failures.append(
            "release channel generatedAt/generated_at is missing (cannot prove closure freshness)"
        )
    if not support_generated_at:
        failures.append(
            "support packets generated_at/generatedAt is missing (cannot prove closure freshness)"
        )
    if not support_plan_generated_at:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.generated_at/generatedAt is missing"
        )
    if support_plan_generated_at and support_generated_at and support_plan_generated_at != support_generated_at:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.generated_at "
            f"({support_plan_generated_at}) does not match support packets generated_at ({support_generated_at})"
        )
    if not support_plan_release_generated_at:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.release_channel_generated_at is missing"
        )
    if support_plan_release_generated_at and release_generated_at and support_plan_release_generated_at != release_generated_at:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.release_channel_generated_at "
            f"({support_plan_release_generated_at}) does not match release channel generatedAt ({release_generated_at})"
        )
    has_open_backlog_signal = any(
        (
            unresolved_count > 0,
            support_plan_request_count > 0,
            blocked_external_only_count > 0,
            bool(missing_platforms),
            bool(missing_head_pairs),
            bool(missing_tuples),
            bool(external_request_tuples),
            bool(unresolved_tuples),
            bool(unresolved_hosts),
            bool(unresolved_specs),
            unresolved_backlog_count > 0,
            bool(unresolved_backlog_hosts),
            bool(unresolved_backlog_tuples),
            bool(unresolved_backlog_host_counts),
            bool(unresolved_backlog_tuple_counts),
            bool(unresolved_backlog_specs),
            bool(unresolved_entries),
            bool(blocked_external_only_tuples),
            bool(blocked_external_only_hosts),
            bool(support_plan_hosts),
            bool(support_plan_hosts_with_backlog),
            bool(journey_rows_with_external_requests),
        )
    )
    if has_open_backlog_signal and support_plan_capture_deadline_hours <= 0:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.capture_deadline_hours must be a positive integer while external-proof backlog is open"
        )
    if has_open_backlog_signal and not support_plan_capture_deadline_utc:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.capture_deadline_utc is missing while external-proof backlog is open"
        )
    if support_plan_capture_deadline_utc and not _parse_iso(support_plan_capture_deadline_utc):
        failures.append(
            "support packets unresolved_external_proof_execution_plan.capture_deadline_utc is not a valid ISO-8601 timestamp: "
            + support_plan_capture_deadline_utc
        )
    if journey_support_generated_ats and support_generated_at and journey_support_generated_ats != [support_generated_at]:
        failures.append(
            "journey gates evidence.support_packets_generated_at values do not match support packets generated_at: "
            + ", ".join(journey_support_generated_ats)
        )
    if not journey_support_generated_ats:
        failures.append(
            "journey gates evidence.support_packets_generated_at is missing from all journey rows"
        )
    if journey_rows_missing_support_generated_at:
        failures.append(
            "journey gates evidence.support_packets_generated_at is missing in journey rows: "
            + ", ".join(journey_rows_missing_support_generated_at)
        )
    if release_generated_at and not _parse_iso(release_generated_at):
        failures.append(
            "release channel generatedAt/generated_at is not a valid ISO-8601 timestamp: "
            + release_generated_at
        )
    if support_generated_at and not _parse_iso(support_generated_at):
        failures.append(
            "support packets generated_at/generatedAt is not a valid ISO-8601 timestamp: "
            + support_generated_at
        )
    if support_plan_generated_at and not _parse_iso(support_plan_generated_at):
        failures.append(
            "support packets unresolved_external_proof_execution_plan.generated_at/generatedAt is not a valid ISO-8601 timestamp: "
            + support_plan_generated_at
        )
    if support_plan_release_generated_at and not _parse_iso(support_plan_release_generated_at):
        failures.append(
            "support packets unresolved_external_proof_execution_plan.release_channel_generated_at is not a valid ISO-8601 timestamp: "
            + support_plan_release_generated_at
        )
    invalid_journey_support_ts = sorted(
        {
            value
            for value in journey_support_generated_ats
            if value and not _parse_iso(value)
        }
    )
    if invalid_journey_support_ts:
        failures.append(
            "journey gates evidence.support_packets_generated_at includes invalid ISO-8601 timestamps: "
            + ", ".join(invalid_journey_support_ts)
        )
    parsed_release_generated_at = _parse_iso(release_generated_at) if release_generated_at else None
    parsed_support_generated_at = _parse_iso(support_generated_at) if support_generated_at else None
    parsed_capture_deadline_utc = _parse_iso(support_plan_capture_deadline_utc) if support_plan_capture_deadline_utc else None
    parsed_support_plan_generated_at = _parse_iso(support_plan_generated_at) if support_plan_generated_at else None
    parsed_support_plan_release_generated_at = (
        _parse_iso(support_plan_release_generated_at) if support_plan_release_generated_at else None
    )
    parsed_journey_support_generated_ats = [
        parsed
        for parsed in (_parse_iso(value) for value in journey_support_generated_ats)
        if parsed is not None
    ]
    if parsed_release_generated_at and parsed_support_generated_at and parsed_support_generated_at < parsed_release_generated_at:
        failures.append(
            "support packets generated_at/generatedAt is older than release channel generatedAt/generated_at"
        )
    deadline_anchor_name = (
        "support packets unresolved_external_proof_execution_plan.release_channel_generated_at"
        if parsed_support_plan_release_generated_at
        else "support packets generated_at/generatedAt"
    )
    deadline_anchor_ts = parsed_support_plan_release_generated_at or parsed_support_generated_at
    if (
        has_open_backlog_signal
        and parsed_capture_deadline_utc
        and deadline_anchor_ts
        and parsed_capture_deadline_utc < deadline_anchor_ts
    ):
        failures.append(
            "support packets unresolved_external_proof_execution_plan.capture_deadline_utc is earlier than "
            + deadline_anchor_name
        )
    if (
        has_open_backlog_signal
        and deadline_anchor_ts
        and parsed_capture_deadline_utc
        and support_plan_capture_deadline_hours > 0
    ):
        expected_deadline_utc = deadline_anchor_ts.timestamp() + (support_plan_capture_deadline_hours * 3600)
        deadline_delta_seconds = abs(parsed_capture_deadline_utc.timestamp() - expected_deadline_utc)
        if deadline_delta_seconds > 60:
            failures.append(
                "support packets unresolved_external_proof_execution_plan.capture_deadline_utc does not match "
                f"{deadline_anchor_name} plus capture_deadline_hours "
                f"(delta_seconds={int(deadline_delta_seconds)})"
            )

    external_proof_runbook_path = (
        Path(args.external_proof_runbook).resolve() if args.external_proof_runbook is not None else None
    )
    external_proof_commands_dir = (
        Path(args.external_proof_commands_dir).resolve()
        if args.external_proof_commands_dir is not None
        else None
    )
    runbook_generated_at = ""
    parsed_runbook_generated_at: datetime | None = None
    if external_proof_runbook_path is not None:
        runbook_body = _load_text(external_proof_runbook_path, label="external proof runbook")
        runbook_generated_at = _extract_runbook_field(runbook_body, "generated_at")
        runbook_plan_generated_at = _extract_runbook_field(runbook_body, "plan_generated_at")
        runbook_release_generated_at = _extract_runbook_field(runbook_body, "release_channel_generated_at")
        if not runbook_generated_at:
            failures.append("external proof runbook generated_at is missing")
        else:
            parsed_runbook_generated_at = _parse_iso(runbook_generated_at)
            if parsed_runbook_generated_at is None:
                failures.append(
                    "external proof runbook generated_at is not a valid ISO-8601 timestamp: "
                    + runbook_generated_at
                )
        if not runbook_plan_generated_at:
            failures.append("external proof runbook plan_generated_at is missing")
        elif support_generated_at and runbook_plan_generated_at != support_generated_at:
            failures.append(
                "external proof runbook plan_generated_at "
                f"({runbook_plan_generated_at}) does not match support packets generated_at ({support_generated_at})"
            )
        if not runbook_release_generated_at:
            failures.append("external proof runbook release_channel_generated_at is missing")
        elif release_generated_at and runbook_release_generated_at != release_generated_at:
            failures.append(
                "external proof runbook release_channel_generated_at "
                f"({runbook_release_generated_at}) does not match release channel generatedAt ({release_generated_at})"
            )

    if external_proof_commands_dir is not None:
        if not external_proof_commands_dir.is_dir():
            failures.append(
                "external proof commands directory is missing or not a directory: "
                + str(external_proof_commands_dir)
            )
        else:
            post_capture_script = external_proof_commands_dir / "republish-after-host-proof.sh"
            if not post_capture_script.is_file():
                failures.append(
                    "external proof commands directory is missing required script: "
                    + str(post_capture_script)
                )
            elif not os.access(post_capture_script, os.X_OK):
                failures.append(
                    "external proof commands script is not executable: "
                    + str(post_capture_script)
                )
            if has_open_backlog_signal:
                required_hosts = sorted(
                    {
                        _normalized_token(host).lower()
                        for host in (support_plan_hosts + support_plan_hosts_with_backlog)
                        if _normalized_token(host)
                    }
                )
                required_hosts = sorted(
                    set(required_hosts).union(
                        {
                            _normalized_token(
                                request.get("required_host")
                                or (
                                    _normalized_token(tuple_id).split(":")[2]
                                    if _normalized_token(tuple_id).count(":") == 2
                                    else ""
                                )
                            ).lower()
                            for tuple_id, request in release_external_request_index.items()
                            if _normalized_token(
                                request.get("required_host")
                                or (
                                    _normalized_token(tuple_id).split(":")[2]
                                    if _normalized_token(tuple_id).count(":") == 2
                                    else ""
                                )
                            )
                        }
                    )
                )
                for host in required_hosts:
                    host_token = _normalize_host_token(host)
                    capture_script = external_proof_commands_dir / f"capture-{host_token}-proof.sh"
                    validation_script = external_proof_commands_dir / f"validate-{host_token}-proof.sh"
                    capture_script_payload = ""
                    validation_script_payload = ""
                    capture_script_loaded = False
                    validation_script_loaded = False
                    capture_wrapper_script = external_proof_commands_dir / f"capture-{host_token}-proof.ps1"
                    validation_wrapper_script = external_proof_commands_dir / f"validate-{host_token}-proof.ps1"
                    capture_wrapper_payload = ""
                    validation_wrapper_payload = ""
                    capture_wrapper_loaded = False
                    validation_wrapper_loaded = False
                    for script_path in (capture_script, validation_script):
                        if not script_path.is_file():
                            failures.append(
                                "external proof commands directory is missing required host script: "
                                + str(script_path)
                            )
                            continue
                        if not os.access(script_path, os.X_OK):
                            failures.append(
                                "external proof host script is not executable: "
                                + str(script_path)
                            )
                    if capture_script.is_file():
                        try:
                            capture_script_payload = capture_script.read_text(encoding="utf-8")
                            capture_script_loaded = True
                        except OSError as exc:
                            failures.append(
                                "external proof capture script is unreadable: "
                                + f"{capture_script}: {exc}"
                            )
                    if validation_script.is_file():
                        try:
                            validation_script_payload = validation_script.read_text(encoding="utf-8")
                            validation_script_loaded = True
                        except OSError as exc:
                            failures.append(
                                "external proof validation script is unreadable: "
                                + f"{validation_script}: {exc}"
                            )
                    if host == "windows":
                        if capture_wrapper_script.is_file():
                            try:
                                capture_wrapper_payload = capture_wrapper_script.read_text(encoding="utf-8")
                                capture_wrapper_loaded = True
                            except OSError as exc:
                                failures.append(
                                    "external proof windows capture wrapper is unreadable: "
                                    + f"{capture_wrapper_script}: {exc}"
                                )
                        if validation_wrapper_script.is_file():
                            try:
                                validation_wrapper_payload = validation_wrapper_script.read_text(encoding="utf-8")
                                validation_wrapper_loaded = True
                            except OSError as exc:
                                failures.append(
                                    "external proof windows validation wrapper is unreadable: "
                                    + f"{validation_wrapper_script}: {exc}"
                                )
                    if capture_script_loaded or validation_script_loaded:
                        support_host_request_rows = [
                            item
                            for row_host, _, item in support_plan_request_rows
                            if row_host.strip().lower() == host.lower() and isinstance(item, dict)
                        ]
                        release_host_request_rows = [
                            dict(request)
                            for tuple_id, request in release_external_request_index.items()
                            if (
                                _normalized_token(request.get("required_host")).lower() == host.lower()
                                or (
                                    not _normalized_token(request.get("required_host"))
                                    and _normalized_token(tuple_id).count(":") == 2
                                    and _normalized_token(tuple_id).split(":")[2].lower() == host.lower()
                                )
                            )
                        ]
                        host_request_rows = support_host_request_rows or release_host_request_rows
                        for request in host_request_rows:
                            tuple_id = _normalized_token(request.get("tuple_id") or request.get("tupleId")) or "<unknown>"
                            capture_commands = _normalized_command_list(
                                request.get("proof_capture_commands")
                                if request.get("proof_capture_commands") is not None
                                else request.get("proofCaptureCommands")
                            )
                            if capture_commands:
                                for command in capture_commands:
                                    if not capture_script_loaded or command not in capture_script_payload:
                                        failures.append(
                                            "external proof capture script is missing tuple proof_capture_commands entry "
                                            f"for tuple {tuple_id}: {command}"
                                        )
                                    if host == "windows":
                                        wrapped_capture_command = _powershell_wrap(command)
                                        if (
                                            not capture_wrapper_loaded
                                            or wrapped_capture_command not in capture_wrapper_payload
                                        ):
                                            failures.append(
                                                "external proof windows capture wrapper is missing tuple proof_capture_commands entry "
                                                f"for tuple {tuple_id}: {wrapped_capture_command}"
                                            )
                            installer_file_name = _normalized_token(
                                request.get("expected_installer_file_name")
                                or request.get("expectedInstallerFileName")
                            )
                            installer_sha256 = _normalized_token(
                                request.get("expected_installer_sha256")
                                or request.get("expectedInstallerSha256")
                            ).lower()
                            receipt_path = _normalized_token(
                                request.get("expected_startup_smoke_receipt_path")
                                or request.get("expectedStartupSmokeReceiptPath")
                            )
                            if installer_file_name:
                                installer_path = (
                                    f"/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/{installer_file_name}"
                                )
                                if not validation_script_loaded or installer_path not in validation_script_payload:
                                    failures.append(
                                        "external proof validation script does not reference expected installer path "
                                        f"for tuple {tuple_id}: {installer_path}"
                                    )
                                if host == "windows" and (
                                    not validation_wrapper_loaded or installer_path not in validation_wrapper_payload
                                ):
                                    failures.append(
                                        "external proof windows validation wrapper does not reference expected installer path "
                                        f"for tuple {tuple_id}: {installer_path}"
                                    )
                            if installer_sha256:
                                if not validation_script_loaded or "installer-contract-mismatch" not in validation_script_payload:
                                    failures.append(
                                        "external proof validation script is missing installer digest contract checks "
                                        f"for tuple {tuple_id}: expected marker 'installer-contract-mismatch'"
                                    )
                                if not validation_script_loaded or installer_sha256 not in validation_script_payload:
                                    failures.append(
                                        "external proof validation script is missing installer digest contract token "
                                        f"for tuple {tuple_id}: sha256={installer_sha256}"
                                    )
                                if host == "windows":
                                    if (
                                        not validation_wrapper_loaded
                                        or "installer-contract-mismatch" not in validation_wrapper_payload
                                    ):
                                        failures.append(
                                            "external proof windows validation wrapper is missing installer digest contract checks "
                                            f"for tuple {tuple_id}: expected marker 'installer-contract-mismatch'"
                                        )
                                    if (
                                        not validation_wrapper_loaded
                                        or installer_sha256 not in validation_wrapper_payload
                                    ):
                                        failures.append(
                                            "external proof windows validation wrapper is missing installer digest contract token "
                                            f"for tuple {tuple_id}: sha256={installer_sha256}"
                                        )
                            if receipt_path and (
                                not validation_script_loaded or receipt_path not in validation_script_payload
                            ):
                                failures.append(
                                    "external proof validation script does not reference expected startup-smoke receipt path "
                                    f"for tuple {tuple_id}: {receipt_path}"
                                )
                            if host == "windows" and receipt_path and (
                                not validation_wrapper_loaded or receipt_path not in validation_wrapper_payload
                            ):
                                failures.append(
                                    "external proof windows validation wrapper does not reference expected startup-smoke receipt path "
                                    f"for tuple {tuple_id}: {receipt_path}"
                                )
                            smoke_contract = _normalized_smoke_contract(
                                request.get("startup_smoke_receipt_contract")
                                if request.get("startup_smoke_receipt_contract") is not None
                                else request.get("startupSmokeReceiptContract")
                            )
                            if receipt_path and (
                                smoke_contract.get("status_any_of")
                                or smoke_contract.get("ready_checkpoint")
                                or smoke_contract.get("head_id")
                                or smoke_contract.get("platform")
                                or smoke_contract.get("rid")
                                or smoke_contract.get("host_class_contains")
                            ):
                                if (
                                    not validation_script_loaded
                                    or "receipt-contract-mismatch" not in validation_script_payload
                                ):
                                    failures.append(
                                        "external proof validation script is missing startup-smoke receipt contract checks "
                                        f"for tuple {tuple_id}: expected marker 'receipt-contract-mismatch'"
                                    )
                                if host == "windows" and (
                                    not validation_wrapper_loaded
                                    or "receipt-contract-mismatch" not in validation_wrapper_payload
                                ):
                                    failures.append(
                                        "external proof windows validation wrapper is missing startup-smoke receipt contract checks "
                                        f"for tuple {tuple_id}: expected marker 'receipt-contract-mismatch'"
                                    )
                                for key, value in (
                                    ("head_id", smoke_contract.get("head_id")),
                                    ("platform", smoke_contract.get("platform")),
                                    ("rid", smoke_contract.get("rid")),
                                    ("ready_checkpoint", smoke_contract.get("ready_checkpoint")),
                                    ("host_class_contains", smoke_contract.get("host_class_contains")),
                                ):
                                    token = str(value or "").strip().lower()
                                    if not token:
                                        continue
                                    if (
                                        not validation_script_loaded
                                        or f"\"{key}\": \"{token}\"" not in validation_script_payload
                                    ):
                                        failures.append(
                                            "external proof validation script is missing startup-smoke contract token "
                                            f"for tuple {tuple_id}: {key}={token}"
                                        )
                                    if (
                                        host == "windows"
                                        and (
                                            not validation_wrapper_loaded
                                            or f"\"{key}\": \"{token}\"" not in validation_wrapper_payload
                                        )
                                    ):
                                        failures.append(
                                            "external proof windows validation wrapper is missing startup-smoke contract token "
                                            f"for tuple {tuple_id}: {key}={token}"
                                        )
                    if host == "windows":
                        windows_scripts = (
                            capture_wrapper_script,
                            validation_wrapper_script,
                        )
                        for script_path in windows_scripts:
                            if not script_path.is_file():
                                failures.append(
                                    "external proof commands directory is missing required windows wrapper: "
                                    + str(script_path)
                                )

    max_artifact_age_hours = int(args.max_artifact_age_hours or 0)
    if max_artifact_age_hours < 0:
        failures.append("--max-artifact-age-hours must be >= 0")
    if max_artifact_age_hours > 0:
        max_artifact_age_seconds = max_artifact_age_hours * 3600
        now_utc = datetime.now((parsed_support_generated_at or parsed_release_generated_at or datetime.now().astimezone()).tzinfo)
        stale_checks = (
            ("release channel generatedAt/generated_at", parsed_release_generated_at),
            ("support packets generated_at/generatedAt", parsed_support_generated_at),
            ("support packets unresolved_external_proof_execution_plan.generated_at/generatedAt", parsed_support_plan_generated_at),
        )
        if external_proof_runbook_path is not None:
            stale_checks += (("external proof runbook generated_at", parsed_runbook_generated_at),)
        for label, parsed in stale_checks:
            if parsed is None:
                continue
            age_seconds = _age_seconds(parsed, now=now_utc)
            if age_seconds > max_artifact_age_seconds:
                failures.append(
                    f"{label} is stale (age_seconds={int(age_seconds)} > max_artifact_age_seconds={max_artifact_age_seconds})"
                )
            if age_seconds < -300:
                failures.append(
                    f"{label} is in the future beyond tolerance (age_seconds={int(age_seconds)})"
                )
        if parsed_journey_support_generated_ats:
            newest_journey_support_ts = max(parsed_journey_support_generated_ats)
            age_seconds = _age_seconds(newest_journey_support_ts, now=now_utc)
            if age_seconds > max_artifact_age_seconds:
                failures.append(
                    "journey gates evidence.support_packets_generated_at is stale "
                    f"(age_seconds={int(age_seconds)} > max_artifact_age_seconds={max_artifact_age_seconds})"
                )
            if age_seconds < -300:
                failures.append(
                    "journey gates evidence.support_packets_generated_at is in the future beyond tolerance "
                    f"(age_seconds={int(age_seconds)})"
                )

    if failures:
        print("External-proof closure check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("External-proof closure check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
