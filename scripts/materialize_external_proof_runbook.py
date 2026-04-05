#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
from pathlib import Path
from typing import Any


UTC = dt.timezone.utc
ROOT = Path("/docker/fleet")
DEFAULT_SUPPORT_PACKETS = ROOT / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
DEFAULT_OUT = ROOT / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"
DEFAULT_EXTERNAL_PROOF_BASE_URL_EXPR = "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}"
UI_REPO_ROOT = Path("/docker/chummercomplete/chummer6-ui")


def _post_capture_republish_commands() -> list[str]:
    return [
        "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
        "cd /docker/chummercomplete/chummer-hub-registry && python3 scripts/materialize_public_release_channel.py --manifest /docker/chummercomplete/chummer6-ui/Docker/Downloads/RELEASE_CHANNEL.generated.json --downloads-dir /docker/chummercomplete/chummer6-ui/Docker/Downloads/files --startup-smoke-dir /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke --proof /docker/chummercomplete/chummer6-ui/Docker/Downloads/release-evidence/public-promotion.json --ui-localization-release-gate /docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCALIZATION_RELEASE_GATE.generated.json --channel docker --version unpublished --published-at \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" --output .codex-studio/published/RELEASE_CHANNEL.generated.json",
        "cd /docker/chummercomplete/chummer-hub-registry && python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json",
        "cd /docker/fleet && python3 scripts/materialize_status_plane.py --out .codex-studio/published/STATUS_PLANE.generated.yaml",
        "cd /docker/fleet && python3 scripts/verify_status_plane_semantics.py --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml",
        "cd /docker/fleet && python3 scripts/materialize_public_progress_report.py --out .codex-studio/published/PROGRESS_REPORT.generated.json --html-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.html --history-out .codex-studio/published/PROGRESS_HISTORY.generated.json --preview-out /docker/chummercomplete/chummer-design/products/chummer/PROGRESS_REPORT.generated.json",
        "cd /docker/fleet && python3 scripts/materialize_support_case_packets.py --out .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json",
        "cd /docker/fleet && python3 scripts/materialize_journey_gates.py --out .codex-studio/published/JOURNEY_GATES.generated.json --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml --progress-report .codex-studio/published/PROGRESS_REPORT.generated.json --progress-history .codex-studio/published/PROGRESS_HISTORY.generated.json --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json",
        "cd /docker/fleet && python3 scripts/materialize_external_proof_runbook.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --out .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md",
        "cd /docker/fleet && python3 scripts/verify_external_proof_closure.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates .codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir .codex-studio/published/external-proof-commands",
        "cd /docker/fleet && python3 scripts/materialize_flagship_product_readiness.py --out .codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json",
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
    parser.add_argument(
        "--commands-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory for generated command scripts. "
            "Defaults to <out-dir>/external-proof-commands."
        ),
    )
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


def _normalized_smoke_contract_map(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    status_tokens = source.get("status_any_of") or source.get("statusAnyOf") or []
    status_any_of = sorted(
        {
            _normalize_text(token).lower()
            for token in status_tokens
            if _normalize_text(token)
        }
    ) if isinstance(status_tokens, list) else []
    return {
        "status_any_of": status_any_of,
        "ready_checkpoint": _normalize_text(
            source.get("ready_checkpoint") or source.get("readyCheckpoint")
        ).lower(),
        "head_id": _normalize_text(source.get("head_id") or source.get("headId")).lower(),
        "platform": _normalize_text(source.get("platform")).lower(),
        "rid": _normalize_text(source.get("rid")).lower(),
        "host_class_contains": _normalize_text(
            source.get("host_class_contains") or source.get("hostClassContains")
        ).lower(),
    }


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
                            "expected_installer_sha256": _normalize_text(
                                row.get("expected_installer_sha256")
                            ).lower(),
                            "expected_public_install_route": _normalize_text(row.get("expected_public_install_route")),
                            "expected_startup_smoke_receipt_path": _normalize_text(
                                row.get("expected_startup_smoke_receipt_path")
                            ),
                            "startup_smoke_receipt_contract": _normalized_smoke_contract_map(
                                row.get("startup_smoke_receipt_contract")
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
        for command in _commands_for_request(row):
            normalized = _normalize_text(command)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            commands.append(normalized)
    return commands


def _validation_commands_for_request(request: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    installer_file_name = _normalize_text(request.get("expected_installer_file_name"))
    installer_sha256 = _normalize_text(request.get("expected_installer_sha256")).lower()
    receipt_relative_path = _normalize_text(request.get("expected_startup_smoke_receipt_path"))
    if installer_file_name:
        installer_path = UI_REPO_ROOT / "Docker" / "Downloads" / "files" / installer_file_name
        commands.append(
            f"cd {shlex.quote(str(UI_REPO_ROOT))} && test -s {shlex.quote(str(installer_path))}"
        )
        if installer_sha256:
            commands.append(
                f"cd {shlex.quote(str(UI_REPO_ROOT))} && "
                "python3 -c "
                + shlex.quote(
                    "import hashlib, pathlib, sys; "
                    f"p=pathlib.Path({str(installer_path)!r}); "
                    f"expected={installer_sha256!r}; "
                    "digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); "
                    "sys.exit(0) if digest==expected else sys.exit("
                    "f'mismatch:{p}:{digest}:expected:{expected}')"
                )
            )
    if receipt_relative_path:
        receipt_path = UI_REPO_ROOT / "Docker" / "Downloads" / receipt_relative_path
        commands.append(
            f"cd {shlex.quote(str(UI_REPO_ROOT))} && test -s {shlex.quote(str(receipt_path))}"
        )
        receipt_contract = _normalized_smoke_contract_map(request.get("startup_smoke_receipt_contract"))
        contract_payload = json.dumps(receipt_contract, sort_keys=True)
        commands.append(
            f"cd {shlex.quote(str(UI_REPO_ROOT))} && "
            "python3 -c "
            + shlex.quote(
                "import json, pathlib, sys; "
                f"p=pathlib.Path({str(receipt_path)!r}); "
                f"contract=json.loads({contract_payload!r}); "
                "payload=json.loads(p.read_text(encoding='utf-8')); "
                "payload=payload if isinstance(payload, dict) else {}; "
                "status=str(payload.get('status') or '').strip().lower(); "
                "expected_statuses=[str(token).strip().lower() for token in (contract.get('status_any_of') or []) if str(token).strip()]; "
                "head_id=str(payload.get('headId') or '').strip().lower(); "
                "platform=str(payload.get('platform') or '').strip().lower(); "
                "rid=str(payload.get('rid') or '').strip().lower(); "
                "ready_checkpoint=str(payload.get('readyCheckpoint') or '').strip().lower(); "
                "host_class=str(payload.get('hostClass') or '').strip().lower(); "
                "expected_head=str(contract.get('head_id') or '').strip().lower(); "
                "expected_platform=str(contract.get('platform') or '').strip().lower(); "
                "expected_rid=str(contract.get('rid') or '').strip().lower(); "
                "expected_ready=str(contract.get('ready_checkpoint') or '').strip().lower(); "
                "expected_host_contains=str(contract.get('host_class_contains') or '').strip().lower(); "
                "sys.exit(0) if ("
                "(not expected_statuses or status in expected_statuses) and "
                "(not expected_head or head_id == expected_head) and "
                "(not expected_platform or platform == expected_platform) and "
                "(not expected_rid or rid == expected_rid) and "
                "(not expected_ready or ready_checkpoint == expected_ready) and "
                "(not expected_host_contains or expected_host_contains in host_class)"
                ") else sys.exit("
                "f'receipt-contract-mismatch:{p}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}')"
            )
        )
    return commands


def _validation_commands_for_group(group: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    for row in group.get("requests") or []:
        if not isinstance(row, dict):
            continue
        for command in _validation_commands_for_request(row):
            normalized = _normalize_text(command)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            commands.append(normalized)
    return commands


def _shell_hint_for_host(host: str) -> str:
    normalized = _normalize_text(host).lower()
    if normalized == "windows":
        return (
            "Run canonical commands in Git Bash (or WSL bash). "
            "PowerShell wrappers are provided below when you need to stay in PowerShell."
        )
    return "Run commands in a POSIX shell (bash/zsh) on the required host."


def _powershell_wrappers(commands: list[str]) -> list[str]:
    wrapped: list[str] = []
    for command in commands:
        normalized = _normalize_text(command)
        if not normalized:
            continue
        escaped = normalized.replace("'", "''")
        wrapped.append(f"bash -lc '{escaped}'")
    return wrapped


def _installer_fetch_preflight_command(request: dict[str, Any]) -> str:
    expected_route = _normalize_text(request.get("expected_public_install_route"))
    installer_file_name = _normalize_text(request.get("expected_installer_file_name"))
    if not expected_route or not installer_file_name:
        return ""
    if not expected_route.startswith("/"):
        expected_route = "/" + expected_route
    installer_path = UI_REPO_ROOT / "Docker" / "Downloads" / "files" / installer_file_name
    return (
        f"cd {shlex.quote(str(UI_REPO_ROOT))} && "
        f"mkdir -p {shlex.quote(str(installer_path.parent))} && "
        f"if [ ! -s {shlex.quote(str(installer_path))} ]; then "
        f"curl -fL --retry 3 --retry-delay 2 "
        f"\"{DEFAULT_EXTERNAL_PROOF_BASE_URL_EXPR}{expected_route}\" "
        f"-o {shlex.quote(str(installer_path))}; "
        f"fi"
    )


def _commands_for_request(request: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    preflight = _installer_fetch_preflight_command(request)
    if preflight:
        commands.append(preflight)
    for command in request.get("proof_capture_commands") or []:
        normalized = _normalize_text(command)
        if normalized and normalized not in commands:
            commands.append(normalized)
    return commands


def _normalize_host_token(value: str) -> str:
    text = "".join(ch if ch.isalnum() else "-" for ch in _normalize_text(value).lower())
    text = text.strip("-")
    return text or "unknown"


def _render_bash_script(commands: list[str], *, no_op_message: str) -> str:
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    if commands:
        lines.extend(commands)
    else:
        lines.append(f"echo {shlex.quote(no_op_message)}")
    lines.append("")
    return "\n".join(lines)


def _write_file(path: Path, content: str, *, executable: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    mode = 0o755 if executable else 0o644
    os.chmod(path, mode)


def _materialize_command_files(plan: dict[str, Any], *, commands_dir: Path) -> dict[str, Any]:
    hosts = [str(item) for item in (plan.get("hosts") or []) if str(item)]
    host_groups = plan.get("host_groups") or {}
    host_files: list[dict[str, str]] = []
    commands_dir.mkdir(parents=True, exist_ok=True)

    for host in hosts:
        group = host_groups.get(host)
        if not isinstance(group, dict):
            continue
        host_token = _normalize_host_token(host)
        capture_commands = _commands_for_group(group)
        validation_commands = _validation_commands_for_group(group)
        capture_script = commands_dir / f"capture-{host_token}-proof.sh"
        validation_script = commands_dir / f"validate-{host_token}-proof.sh"
        _write_file(
            capture_script,
            _render_bash_script(
                capture_commands,
                no_op_message=f"No unresolved external-proof commands for host '{host}'.",
            ),
            executable=True,
        )
        _write_file(
            validation_script,
            _render_bash_script(
                validation_commands,
                no_op_message=f"No external-proof validation commands for host '{host}'.",
            ),
            executable=True,
        )
        host_file_row: dict[str, str] = {
            "host": host,
            "capture_script": str(capture_script),
            "validation_script": str(validation_script),
        }
        if host.lower() == "windows":
            capture_wrappers = _powershell_wrappers(capture_commands)
            validation_wrappers = _powershell_wrappers(validation_commands)
            capture_ps1 = commands_dir / f"capture-{host_token}-proof.ps1"
            validation_ps1 = commands_dir / f"validate-{host_token}-proof.ps1"
            _write_file(
                capture_ps1,
                "\n".join(capture_wrappers + [""]) if capture_wrappers else "# No windows capture wrappers generated.\n",
                executable=False,
            )
            _write_file(
                validation_ps1,
                "\n".join(validation_wrappers + [""])
                if validation_wrappers
                else "# No windows validation wrappers generated.\n",
                executable=False,
            )
            host_file_row["capture_powershell"] = str(capture_ps1)
            host_file_row["validation_powershell"] = str(validation_ps1)
        host_files.append(host_file_row)

    post_capture_script = commands_dir / "republish-after-host-proof.sh"
    _write_file(
        post_capture_script,
        _render_bash_script(
            _post_capture_republish_commands(),
            no_op_message="No post-capture republish commands were generated.",
        ),
        executable=True,
    )
    return {
        "commands_dir": str(commands_dir),
        "hosts": host_files,
        "post_capture_script": str(post_capture_script),
    }


def materialize_markdown(
    plan: dict[str, Any], *, generated_at: str, command_files: dict[str, Any] | None = None
) -> str:
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
    if isinstance(command_files, dict) and _normalize_text(command_files.get("commands_dir")):
        lines.append("## Generated Command Files")
        lines.append("")
        lines.append(f"- commands_dir: `{_normalize_text(command_files.get('commands_dir'))}`")
        for host_row in command_files.get("hosts") or []:
            if not isinstance(host_row, dict):
                continue
            host = _normalize_text(host_row.get("host")) or "unknown"
            capture_script = _normalize_text(host_row.get("capture_script"))
            validation_script = _normalize_text(host_row.get("validation_script"))
            capture_powershell = _normalize_text(host_row.get("capture_powershell"))
            validation_powershell = _normalize_text(host_row.get("validation_powershell"))
            lines.append(f"- host `{host}`")
            if capture_script:
                lines.append(f"  capture_script: `{capture_script}`")
            if validation_script:
                lines.append(f"  validation_script: `{validation_script}`")
            if capture_powershell:
                lines.append(f"  capture_powershell: `{capture_powershell}`")
            if validation_powershell:
                lines.append(f"  validation_powershell: `{validation_powershell}`")
        post_capture_script = _normalize_text(command_files.get("post_capture_script"))
        if post_capture_script:
            lines.append(f"- post_capture_script: `{post_capture_script}`")
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
        lines.append(f"- shell_hint: {_shell_hint_for_host(host)}")
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
            installer_sha256 = _normalize_text(request.get("expected_installer_sha256")) or "(missing)"
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
            lines.append(f"  installer_sha256: `{installer_sha256}`")
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
        validation_commands = _validation_commands_for_group(group)
        lines.append("")
        lines.append("### Commands (Host Validation)")
        lines.append("")
        if not validation_commands:
            lines.append("No host validation commands were generated for this host.")
        else:
            lines.append("```bash")
            for command in validation_commands:
                lines.append(command)
            lines.append("```")
        if host.lower() == "windows":
            wrappers = _powershell_wrappers(commands)
            validation_wrappers = _powershell_wrappers(validation_commands)
            lines.append("")
            lines.append("### Commands (PowerShell Wrappers)")
            lines.append("")
            if not wrappers:
                lines.append("No PowerShell wrappers were generated for this host.")
            else:
                lines.append("```powershell")
                for command in wrappers:
                    lines.append(command)
                lines.append("```")
            lines.append("")
            lines.append("### Commands (PowerShell Validation Wrappers)")
            lines.append("")
            if not validation_wrappers:
                lines.append("No PowerShell validation wrappers were generated for this host.")
            else:
                lines.append("```powershell")
                for command in validation_wrappers:
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
    commands_dir = (
        Path(args.commands_dir).resolve()
        if args.commands_dir is not None
        else (args.out.parent / "external-proof-commands").resolve()
    )
    command_files = _materialize_command_files(plan, commands_dir=commands_dir)
    markdown = materialize_markdown(plan, generated_at=utc_now_iso(), command_files=command_files)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
