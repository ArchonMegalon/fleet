#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


UTC = dt.timezone.utc
ROOT = Path("/docker/fleet")
DEFAULT_SUPPORT_PACKETS = ROOT / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
DEFAULT_OUT = ROOT / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"


def _post_capture_republish_commands() -> list[str]:
    return [
        "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
        "cd /docker/fleet && python3 scripts/materialize_support_case_packets.py --out .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json",
        "cd /docker/fleet && python3 scripts/materialize_journey_gates.py --out .codex-studio/published/JOURNEY_GATES.generated.json --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml --progress-report .codex-studio/published/PROGRESS_REPORT.generated.json --progress-history .codex-studio/published/PROGRESS_HISTORY.generated.json --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json",
        "cd /docker/fleet && python3 scripts/materialize_external_proof_runbook.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --out .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md",
        "cd /docker/fleet && python3 scripts/materialize_flagship_product_readiness.py --out .codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json",
        "cd /docker/fleet && python3 scripts/materialize_public_progress_report.py --out .codex-studio/published/PROGRESS_REPORT.generated.json --html-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.html --history-out .codex-studio/published/PROGRESS_HISTORY.generated.json --preview-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.json",
        "cd /docker/chummercomplete/chummer-design && python3 scripts/ai/materialize_weekly_product_pulse_snapshot.py --out products/chummer/WEEKLY_PRODUCT_PULSE.generated.json",
        "cd /docker/fleet && python3 scripts/chummer_design_supervisor.py status >/dev/null",
    ]


def utc_now_iso() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Any) -> dt.datetime | None:
    raw = _normalize_text(value)
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize a host-grouped external-proof execution runbook from "
            "SUPPORT_CASE_PACKETS.generated.json."
        )
    )
    parser.add_argument("--support-packets", type=Path, default=DEFAULT_SUPPORT_PACKETS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
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


def _normalize_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "request_count": 0,
            "hosts": [],
            "host_groups": {},
            "generated_at": "",
            "release_channel_generated_at": "",
            "capture_deadline_hours": 0,
            "capture_deadline_utc": "",
        }

    request_count_raw = value.get("request_count")
    request_count = request_count_raw if isinstance(request_count_raw, int) and not isinstance(request_count_raw, bool) else 0

    raw_hosts = value.get("hosts")
    hosts: list[str] = []
    if isinstance(raw_hosts, list):
        hosts = sorted({_normalize_text(item).lower() for item in raw_hosts if _normalize_text(item)})

    raw_host_groups = value.get("host_groups")
    host_groups: dict[str, Any] = {}
    if isinstance(raw_host_groups, dict):
        for raw_host, raw_group in raw_host_groups.items():
            host = _normalize_text(raw_host).lower()
            if not host or not isinstance(raw_group, dict):
                continue
            raw_requests = raw_group.get("requests")
            requests: list[dict[str, Any]] = []
            if isinstance(raw_requests, list):
                for row in raw_requests:
                    if not isinstance(row, dict):
                        continue
                    commands_raw = row.get("proof_capture_commands")
                    commands = [
                        _normalize_text(token)
                        for token in commands_raw
                        if _normalize_text(token)
                    ] if isinstance(commands_raw, list) else []
                    requests.append(
                        {
                            "tuple_id": _normalize_text(row.get("tuple_id")),
                            "head_id": _normalize_text(row.get("head_id")).lower(),
                            "platform": _normalize_text(row.get("platform")).lower(),
                            "rid": _normalize_text(row.get("rid")).lower(),
                            "expected_artifact_id": _normalize_text(row.get("expected_artifact_id")),
                            "expected_installer_file_name": _normalize_text(row.get("expected_installer_file_name")),
                            "expected_installer_relative_path": _normalize_text(
                                row.get("expected_installer_relative_path")
                            ),
                            "expected_public_install_route": _normalize_text(row.get("expected_public_install_route")),
                            "expected_startup_smoke_receipt_path": _normalize_text(
                                row.get("expected_startup_smoke_receipt_path")
                            ),
                            "capture_deadline_utc": _normalize_text(row.get("capture_deadline_utc")),
                            "required_proofs": sorted(
                                {
                                    _normalize_text(token).lower()
                                    for token in (row.get("required_proofs") or [])
                                    if _normalize_text(token)
                                }
                            ),
                            "proof_capture_commands": commands,
                        }
                    )
            host_groups[host] = {
                "request_count": int(raw_group.get("request_count") or len(requests)),
                "tuples": sorted(
                    {
                        _normalize_text(token)
                        for token in (raw_group.get("tuples") or [])
                        if _normalize_text(token)
                    }
                ),
                "requests": requests,
            }
    if not hosts:
        hosts = sorted(host_groups.keys())
    return {
        "request_count": request_count or sum(
            int(group.get("request_count") or 0)
            for group in host_groups.values()
            if isinstance(group, dict)
        ),
        "hosts": hosts,
        "host_groups": host_groups,
        "generated_at": _normalize_text(value.get("generated_at")),
        "release_channel_generated_at": _normalize_text(value.get("release_channel_generated_at")),
        "capture_deadline_hours": _safe_int(value.get("capture_deadline_hours"), default=0),
        "capture_deadline_utc": _normalize_text(value.get("capture_deadline_utc")),
    }


def _load_support_packets(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _commands_for_group(group: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    for row in group.get("requests") or []:
        if not isinstance(row, dict):
            continue
        for command in row.get("proof_capture_commands") or []:
            normalized = _normalize_text(command)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            commands.append(normalized)
    return commands


def _commands_for_request(request: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for command in request.get("proof_capture_commands") or []:
        normalized = _normalize_text(command)
        if normalized:
            commands.append(normalized)
    return commands


def materialize_markdown(plan: dict[str, Any], *, generated_at: str) -> str:
    lines: list[str] = []
    request_count = int(plan.get("request_count") or 0)
    hosts = [str(item) for item in (plan.get("hosts") or []) if str(item)]
    host_groups = plan.get("host_groups") or {}

    lines.append("# External Proof Runbook")
    lines.append("")
    lines.append(f"- generated_at: {generated_at}")
    lines.append(f"- unresolved_request_count: {request_count}")
    lines.append(f"- unresolved_hosts: {', '.join(hosts) if hosts else '(none)'}")
    lines.append(f"- plan_generated_at: {_normalize_text(plan.get('generated_at')) or '(missing)'}")
    lines.append(
        f"- release_channel_generated_at: {_normalize_text(plan.get('release_channel_generated_at')) or '(missing)'}"
    )
    lines.append(f"- capture_deadline_hours: {_safe_int(plan.get('capture_deadline_hours'), default=0)}")
    lines.append(f"- capture_deadline_utc: {_normalize_text(plan.get('capture_deadline_utc')) or '(missing)'}")
    lines.append("")

    if request_count <= 0 or not host_groups:
        lines.append("No unresolved external-proof requests are currently queued.")
        lines.append("")
        return "\n".join(lines)

    for host in hosts:
        group = host_groups.get(host)
        if not isinstance(group, dict):
            continue
        lines.append(f"## Host: {host}")
        lines.append("")
        lines.append(f"- request_count: {int(group.get('request_count') or 0)}")
        tuples = [str(item) for item in (group.get("tuples") or []) if str(item)]
        lines.append(f"- tuples: {', '.join(tuples) if tuples else '(none)'}")
        lines.append("")
        lines.append("### Requested Tuples")
        lines.append("")
        for request in group.get("requests") or []:
            if not isinstance(request, dict):
                continue
            tuple_id = _normalize_text(request.get("tuple_id")) or "unknown"
            required_proofs = ", ".join(request.get("required_proofs") or []) or "(none)"
            artifact_id = _normalize_text(request.get("expected_artifact_id")) or "(missing)"
            installer = _normalize_text(request.get("expected_installer_file_name")) or "(missing)"
            installer_relative_path = _normalize_text(request.get("expected_installer_relative_path")) or "(missing)"
            route = _normalize_text(request.get("expected_public_install_route")) or "(missing)"
            receipt_path = _normalize_text(request.get("expected_startup_smoke_receipt_path")) or "(missing)"
            capture_deadline_utc = _normalize_text(request.get("capture_deadline_utc"))
            deadline_state = "unknown"
            deadline_dt = _parse_iso(capture_deadline_utc)
            if deadline_dt is not None:
                deadline_state = "overdue" if deadline_dt < dt.datetime.now(UTC) else "pending"
            lines.append(f"- `{tuple_id}`")
            lines.append(f"  required_proofs: `{required_proofs}`")
            lines.append(f"  artifact_id: `{artifact_id}`")
            lines.append(f"  installer_file: `{installer}`")
            lines.append(f"  installer_relative_path: `{installer_relative_path}`")
            lines.append(f"  public_route: `{route}`")
            lines.append(f"  startup_smoke_receipt: `{receipt_path}`")
            lines.append(f"  capture_deadline_utc: `{capture_deadline_utc or '(missing)'}`")
            lines.append(f"  capture_deadline_state: `{deadline_state}`")
            tuple_commands = _commands_for_request(request)
            lines.append("  commands:")
            if not tuple_commands:
                lines.append("    - (none)")
            else:
                for command in tuple_commands:
                    lines.append(f"    - `{command}`")
        lines.append("")
        lines.append("### Commands (Host Consolidated)")
        lines.append("")
        commands = _commands_for_group(group)
        if not commands:
            lines.append("No proof-capture commands were provided for this host.")
        else:
            lines.append("```bash")
            for command in commands:
                lines.append(command)
            lines.append("```")
        lines.append("")

    lines.append("## After Host Proof Capture")
    lines.append("")
    lines.append("Run these commands after macOS/Windows proofs land to ingest receipts and republish release truth.")
    lines.append("")
    lines.append("```bash")
    for command in _post_capture_republish_commands():
        lines.append(command)
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    support_packets = _load_support_packets(args.support_packets)
    plan = _normalize_plan(support_packets.get("unresolved_external_proof_execution_plan"))
    markdown = materialize_markdown(plan, generated_at=utc_now_iso())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
