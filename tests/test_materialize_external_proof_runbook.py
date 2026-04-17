from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/materialize_external_proof_runbook.py")


def _load_runbook_module():
    previous_sys_path = list(sys.path)
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("materialize_external_proof_runbook", SCRIPT)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = previous_sys_path


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_bundle_archive(
    *,
    archive_path: Path,
    manifest_payload: dict,
    installer_relative_path: str,
    installer_bytes: bytes,
    receipt_relative_path: str,
    receipt_payload: dict,
) -> None:
    bundle_root = archive_path.parent / "bundle-fixture"
    if bundle_root.exists():
        subprocess.run(["rm", "-rf", str(bundle_root)], check=True)
    (bundle_root / Path(installer_relative_path).parent).mkdir(parents=True, exist_ok=True)
    (bundle_root / Path(receipt_relative_path).parent).mkdir(parents=True, exist_ok=True)
    (bundle_root / "external-proof-manifest.json").write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (bundle_root / installer_relative_path).write_bytes(installer_bytes)
    (bundle_root / receipt_relative_path).write_text(
        json.dumps(receipt_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(bundle_root, arcname=".")
    subprocess.run(["rm", "-rf", str(bundle_root)], check=True)


def test_sanitize_proof_capture_command_preserves_version_hint_and_canonical_os_hint() -> None:
    module = _load_runbook_module()

    normalized = module._sanitize_proof_capture_command(
        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke run-20260414-1836"
        ,
        required_host="macos",
        platform="macos",
    )

    assert normalized == (
        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host "
        "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS "
        "./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/"
        "chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia "
        "/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke run-20260414-1836"
    )


def test_commands_for_request_preserves_shell_quoted_capture_commands_without_duplicate_preflight() -> None:
    module = _load_runbook_module()
    request = {
        "expected_public_install_route": "/downloads/install/avalonia-osx-arm64-installer",
        "expected_installer_relative_path": "files/chummer-avalonia-osx-arm64-installer.dmg",
        "expected_installer_file_name": "chummer-avalonia-osx-arm64-installer.dmg",
        "expected_installer_sha256": "424b3216afedf86347494eea985cc1e7ceca7cb8cbf7aff04a475456a15973f4",
    }
    provided_preflight = module._installer_fetch_preflight_command(request)

    commands = module._commands_for_request(
        {
            **request,
            "proof_capture_commands": [
                provided_preflight,
                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke unpublished",
            ],
        }
    )

    assert commands[0] == provided_preflight
    assert commands.count(provided_preflight) == 1
    assert len(commands) == 2


def test_proof_capture_command_dedupe_key_ignores_optional_version_hint() -> None:
    module = _load_runbook_module()

    dedupe_key = module._proof_capture_command_dedupe_key(
        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=macOS ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke run-20260414-1836"
    )

    assert dedupe_key == (
        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host "
        "./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/"
        "chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia "
        "/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke"
    )


def test_materialize_external_proof_runbook_groups_requests_by_host(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 2,
                    "hosts": ["macos", "windows"],
                    "generated_at": "2026-04-05T00:00:00Z",
                    "release_channel_generated_at": "2026-04-05T00:00:00Z",
                    "capture_deadline_hours": 24,
                    "capture_deadline_utc": "2026-04-06T00:00:00Z",
                    "host_groups": {
                        "windows": {
                            "request_count": 1,
                            "tuples": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_installer_sha256": "a" * 64,
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "startup_smoke_receipt_contract": {
                                        "ready_checkpoint": "pre_ui_event_loop",
                                        "head_id": "avalonia",
                                        "platform": "windows",
                                        "rid": "win-x64",
                                        "host_class_contains": "windows",
                                        "status_any_of": ["pass", "ready"],
                                    },
                                    "capture_deadline_utc": "2026-04-06T00:00:00Z",
                                    "proof_capture_commands": [
                                        "echo windows-proof",
                                        "echo refresh-manifest",
                                    ],
                                }
                            ],
                        },
                        "macos": {
                            "request_count": 1,
                            "tuples": ["blazor-desktop:osx-arm64:macos"],
                            "requests": [
                                {
                                    "tuple_id": "blazor-desktop:osx-arm64:macos",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "blazor-desktop-osx-arm64-installer",
                                    "expected_installer_file_name": "chummer-blazor-desktop-osx-arm64-installer.dmg",
                                    "expected_public_install_route": "/downloads/install/blazor-desktop-osx-arm64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json",
                                    "startup_smoke_receipt_contract": {
                                        "ready_checkpoint": "pre_ui_event_loop",
                                        "head_id": "blazor-desktop",
                                        "platform": "macos",
                                        "rid": "osx-arm64",
                                        "host_class_contains": "macos",
                                        "status_any_of": ["pass", "ready"],
                                    },
                                    "capture_deadline_utc": "2026-04-06T00:00:00Z",
                                    "proof_capture_commands": [
                                        "echo macos-proof",
                                        "echo refresh-manifest",
                                    ],
                                }
                            ],
                        },
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    journey_gates.write_text(json.dumps({"journeys": []}, indent=2) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    module = _load_runbook_module()
    payload = out.read_text(encoding="utf-8")
    commands_dir = out.parent / "external-proof-commands"
    windows_capture = commands_dir / "capture-windows-proof.sh"
    windows_validate = commands_dir / "validate-windows-proof.sh"
    windows_preflight = commands_dir / "preflight-windows-proof.sh"
    windows_bundle = commands_dir / "bundle-windows-proof.sh"
    windows_ingest = commands_dir / "ingest-windows-proof-bundle.sh"
    windows_preflight_ps1 = commands_dir / "preflight-windows-proof.ps1"
    windows_capture_ps1 = commands_dir / "capture-windows-proof.ps1"
    windows_validate_ps1 = commands_dir / "validate-windows-proof.ps1"
    windows_bundle_ps1 = commands_dir / "bundle-windows-proof.ps1"
    windows_ingest_ps1 = commands_dir / "ingest-windows-proof-bundle.ps1"
    macos_preflight = commands_dir / "preflight-macos-proof.sh"
    macos_capture = commands_dir / "capture-macos-proof.sh"
    macos_validate = commands_dir / "validate-macos-proof.sh"
    macos_bundle = commands_dir / "bundle-macos-proof.sh"
    macos_ingest = commands_dir / "ingest-macos-proof-bundle.sh"
    post_capture = commands_dir / "republish-after-host-proof.sh"
    finalize = commands_dir / "finalize-external-host-proof.sh"

    assert "# External Proof Runbook" in payload
    assert "## Generated Command Files" in payload
    assert f"commands_dir: `{commands_dir}`" in payload
    assert "## Host: windows" in payload
    assert "## Host: macos" in payload
    assert "shell_hint: Run canonical commands in Git Bash (or WSL bash)." in payload
    assert "shell_hint: Run commands in a POSIX shell (bash/zsh) on the required host." in payload
    assert "plan_generated_at: 2026-04-05T00:00:00Z" in payload
    assert "capture_deadline_hours: 24" in payload
    assert "capture_deadline_utc: 2026-04-06T00:00:00Z" in payload
    assert "`avalonia:win-x64:windows`" in payload
    assert "`blazor-desktop:osx-arm64:macos`" in payload
    assert "capture_deadline_state: `pending`" in payload or "capture_deadline_state: `overdue`" in payload
    assert "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-win-x64-installer" in payload
    assert "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/blazor-desktop-osx-arm64-installer" in payload
    assert "echo windows-proof" in payload
    assert "echo macos-proof" in payload
    assert payload.count("`echo refresh-manifest`") == 2
    assert payload.count("\necho refresh-manifest\n") == 2
    assert "### Commands (Host Consolidated)" in payload
    assert "### Commands (Host Preflight)" in payload
    assert "### Commands (Host Validation)" in payload
    assert "### Commands (Host Bundle)" in payload
    assert "### Commands (Host Ingest)" in payload
    assert "### Commands (PowerShell Preflight Wrappers)" in payload
    assert "### Commands (PowerShell Wrappers)" in payload
    assert "### Commands (PowerShell Validation Wrappers)" in payload
    assert "### Commands (PowerShell Bundle Wrappers)" in payload
    assert "### Commands (PowerShell Ingest Wrappers)" in payload
    assert "```powershell" in payload
    assert "bash -lc 'echo windows-proof'" in payload
    assert "installer-preflight-sha256-mismatch" in payload
    assert "installer-download-html-response" in payload
    assert "installer-download-signature-mismatch" in payload
    assert "installer-postdownload-sha256-mismatch" in payload
    assert "external-proof-auth-missing" in payload
    assert "CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD" in payload
    assert "signed-in-download-route-required-or-bytes-drift" in payload
    assert "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe" in payload
    assert "hashlib.sha256" in payload
    assert "installer-contract-mismatch" in payload
    assert "release-channel-contract-mismatch" in payload
    assert "expected_artifact=" in payload
    assert "expected_route=" in payload
    assert "avalonia-win-x64-installer" in payload
    assert "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in payload
    assert "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json" in payload
    assert "receipt-contract-mismatch" in payload
    assert "startup-smoke-receipt-stale" in payload
    assert "max_age_seconds=86400" in payload
    assert "readyCheckpoint" in payload
    assert "hostClass" in payload
    assert "\"head_id\": \"avalonia\"" in payload
    assert "bash -lc 'cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'" in payload
    assert "  commands:" in payload
    assert "## After Host Proof Capture" in payload
    assert "python3 scripts/materialize_support_case_packets.py" in payload
    assert "python3 scripts/materialize_status_plane.py" in payload
    assert "python3 scripts/verify_status_plane_semantics.py" in payload
    assert "python3 scripts/materialize_public_release_channel.py" in payload
    assert "--proof /docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCAL_RELEASE_PROOF.generated.json" in payload
    assert "--ui-localization-release-gate /docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCALIZATION_RELEASE_GATE.generated.json" in payload
    assert "python3 scripts/verify_public_release_channel.py" in payload
    assert f"--release-channel {module.REGISTRY_RELEASE_CHANNEL_PATH}" in payload
    assert payload.index("python3 scripts/materialize_status_plane.py") < payload.index(
        "python3 scripts/materialize_journey_gates.py"
    )
    assert payload.index("python3 scripts/materialize_public_progress_report.py") < payload.index(
        "python3 scripts/materialize_journey_gates.py"
    )
    assert "python3 scripts/materialize_journey_gates.py" in payload
    assert "--journey-gates /docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json" in payload
    assert "python3 scripts/verify_external_proof_closure.py" in payload
    assert "--external-proof-runbook .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md" in payload
    assert "--external-proof-commands-dir .codex-studio/published/external-proof-commands" in payload
    assert (
        "python3 scripts/materialize_flagship_product_readiness.py --out "
        ".codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json --mirror-out "
        "/docker/fleet/.codex-design/product/FLAGSHIP_PRODUCT_READINESS.generated.json"
    ) in payload
    assert "python3 scripts/ai/materialize_weekly_product_pulse_snapshot.py" in payload
    assert windows_preflight.is_file()
    assert windows_capture.is_file()
    assert windows_validate.is_file()
    assert windows_bundle.is_file()
    assert windows_ingest.is_file()
    assert windows_preflight_ps1.is_file()
    assert windows_capture_ps1.is_file()
    assert windows_validate_ps1.is_file()
    assert windows_bundle_ps1.is_file()
    assert windows_ingest_ps1.is_file()
    assert macos_preflight.is_file()
    assert macos_capture.is_file()
    assert macos_validate.is_file()
    assert macos_bundle.is_file()
    assert macos_ingest.is_file()
    assert post_capture.is_file()
    assert finalize.is_file()
    assert os.access(windows_preflight, os.X_OK)
    assert os.access(windows_capture, os.X_OK)
    assert os.access(windows_bundle, os.X_OK)
    assert os.access(windows_ingest, os.X_OK)
    assert os.access(macos_preflight, os.X_OK)
    assert os.access(macos_capture, os.X_OK)
    assert os.access(macos_bundle, os.X_OK)
    assert os.access(macos_ingest, os.X_OK)
    assert os.access(post_capture, os.X_OK)
    assert os.access(finalize, os.X_OK)
    assert "command -v python3 >/dev/null 2>&1" in windows_preflight.read_text(encoding="utf-8")
    assert "external-proof-powershell-missing" in windows_preflight.read_text(encoding="utf-8")
    assert "command -v hdiutil >/dev/null 2>&1" in macos_preflight.read_text(encoding="utf-8")
    assert "bash -lc 'if ! command -v python3 >/dev/null 2>&1; then echo ''external-proof-python3-missing'' >&2; exit 1; fi'" in windows_preflight_ps1.read_text(encoding="utf-8")
    assert "echo windows-proof" in windows_capture.read_text(encoding="utf-8")
    assert "echo macos-proof" in macos_capture.read_text(encoding="utf-8")
    assert "external-proof-auth-missing" in windows_capture.read_text(encoding="utf-8")
    assert "CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD" in windows_capture.read_text(encoding="utf-8")
    assert "installer-download-html-response" in windows_capture.read_text(encoding="utf-8")
    assert "installer-download-signature-mismatch" in windows_capture.read_text(encoding="utf-8")
    assert "external-proof-auth-missing" in macos_capture.read_text(encoding="utf-8")
    assert "CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD" in macos_capture.read_text(encoding="utf-8")
    assert "installer-download-html-response" in macos_capture.read_text(encoding="utf-8")
    assert "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe" in windows_validate.read_text(
        encoding="utf-8"
    )
    assert "installer-contract-mismatch" in windows_validate.read_text(encoding="utf-8")
    assert "release-channel-contract-mismatch" in windows_validate.read_text(encoding="utf-8")
    assert "receipt-contract-mismatch" in windows_validate.read_text(encoding="utf-8")
    assert "startup-smoke-receipt-stale" in windows_validate.read_text(encoding="utf-8")
    assert "max_age_seconds=86400" in windows_validate.read_text(encoding="utf-8")
    assert "startup-smoke-receipt-stale" in macos_validate.read_text(encoding="utf-8")
    assert "max_age_seconds=86400" in macos_validate.read_text(encoding="utf-8")
    assert "startup-smoke-receipt-stale" in windows_ingest.read_text(encoding="utf-8")
    assert "max_age_seconds=86400" in windows_ingest.read_text(encoding="utf-8")
    assert "startup-smoke-receipt-stale" in macos_ingest.read_text(encoding="utf-8")
    assert "max_age_seconds=86400" in macos_ingest.read_text(encoding="utf-8")


def test_materialize_external_proof_runbook_recovers_requests_from_journey_gates_when_support_plan_is_empty(
    tmp_path: Path,
) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-14T21:17:39Z",
                "unresolved_external_proof_execution_plan": {
                    "request_count": 0,
                    "hosts": [],
                    "host_groups": {},
                    "generated_at": "2026-04-14T21:17:39Z",
                    "release_channel_generated_at": "2026-04-14T20:59:34Z",
                    "capture_deadline_hours": 24,
                    "capture_deadline_utc": "2026-04-15T20:59:34Z",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    journey_gates.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-14T21:17:18Z",
                "journeys": [
                    {
                        "id": "install_claim_restore_continue",
                        "external_proof_requests": [
                            {
                                "tuple_id": "avalonia:osx-arm64:macos",
                                "required_host": "macos",
                                "required_proofs": [
                                    "promoted_installer_artifact",
                                    "startup_smoke_receipt",
                                ],
                                "head_id": "avalonia",
                                "platform": "macos",
                                "rid": "osx-arm64",
                                "expected_artifact_id": "avalonia-osx-arm64-installer",
                                "expected_installer_file_name": "chummer-avalonia-osx-arm64-installer.dmg",
                                "expected_installer_relative_path": "files/chummer-avalonia-osx-arm64-installer.dmg",
                                "expected_installer_sha256": "a" * 64,
                                "expected_public_install_route": "/downloads/install/avalonia-osx-arm64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                                "startup_smoke_receipt_contract": {
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "macos",
                                    "rid": "osx-arm64",
                                    "host_class_contains": "macos",
                                    "status_any_of": ["pass", "passed", "ready"],
                                },
                                "proof_capture_commands": [
                                    "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                    "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                                ],
                            }
                        ],
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = out.read_text(encoding="utf-8")
    assert "- unresolved_request_count: 1" in payload
    assert "- unresolved_hosts: macos" in payload
    assert "- plan_generated_at: 2026-04-14T21:17:39Z" in payload
    assert "`avalonia:osx-arm64:macos`" in payload
    assert "No unresolved external-proof requests are currently queued." not in payload
    commands_dir = out.parent / "external-proof-commands"
    macos_capture = commands_dir / "capture-macos-proof.sh"
    macos_bundle = commands_dir / "bundle-macos-proof.sh"
    macos_ingest = commands_dir / "ingest-macos-proof-bundle.sh"
    post_capture = commands_dir / "republish-after-host-proof.sh"
    finalize = commands_dir / "finalize-external-host-proof.sh"
    assert "run-desktop-startup-smoke.sh" in macos_capture.read_text(encoding="utf-8")
    assert 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' in macos_bundle.read_text(encoding="utf-8")
    assert "tar -czf \"$SCRIPT_DIR/macos-proof-bundle.tgz\" -C \"$BUNDLE_ROOT\" ." in macos_bundle.read_text(
        encoding="utf-8"
    )
    assert "cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg" in macos_bundle.read_text(
        encoding="utf-8"
    )
    assert "cp -f /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json" in macos_bundle.read_text(
        encoding="utf-8"
    )
    ingest_payload = macos_ingest.read_text(encoding="utf-8")
    assert "BUNDLE_ARCHIVE=\"$SCRIPT_DIR/macos-proof-bundle.tgz\"" in ingest_payload
    assert "BUNDLE_DIR=\"$SCRIPT_DIR/host-proof-bundles/macos\"" in ingest_payload
    assert "if [ ! -s \"$BUNDLE_ARCHIVE\" ]; then" in ingest_payload
    assert "external-proof-bundle-path-unsafe" in ingest_payload
    assert "import os, pathlib, shutil" in ingest_payload
    assert "shutil.copy2(source, destination)" in ingest_payload
    assert "source.is_absolute()" not in ingest_payload
    assert "tar -xzf \"$BUNDLE_ARCHIVE\" -C \"$TARGET_ROOT\"" in ingest_payload
    assert "if [ ! -d \"$BUNDLE_DIR\" ]; then" in ingest_payload
    assert "external-proof-bundle-empty" in ingest_payload
    assert "test -s \"$TARGET_ROOT/files/chummer-avalonia-osx-arm64-installer.dmg\"" in ingest_payload
    assert "test -s \"$TARGET_ROOT/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json\"" in ingest_payload
    assert "installer-contract-mismatch" in ingest_payload
    assert "receipt-contract-mismatch" in ingest_payload
    assert "external-proof-bundle-installer-missing" in ingest_payload
    assert "external-proof-bundle-receipt-missing" in ingest_payload
    assert 'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"' in macos_ingest.read_text(encoding="utf-8")
    assert "python3 scripts/materialize_support_case_packets.py" in post_capture.read_text(encoding="utf-8")
    assert "--proof /docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCAL_RELEASE_PROOF.generated.json" in post_capture.read_text(encoding="utf-8")
    assert "--ui-localization-release-gate /docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCALIZATION_RELEASE_GATE.generated.json" in post_capture.read_text(encoding="utf-8")
    assert "python3 scripts/chummer_design_supervisor.py status" not in post_capture.read_text(encoding="utf-8")
    finalize_payload = finalize.read_text(encoding="utf-8")
    assert "./validate-macos-proof.sh" in finalize_payload
    assert "./ingest-macos-proof-bundle.sh" in finalize_payload
    assert "./republish-after-host-proof.sh" in finalize_payload
    assert finalize_payload.index("./ingest-macos-proof-bundle.sh") < finalize_payload.index(
        "./validate-macos-proof.sh"
    )


def test_materialize_external_proof_runbook_accepts_release_channel_override(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-14T21:17:39Z",
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["windows"],
                    "generated_at": "2026-04-14T21:17:39Z",
                    "release_channel_generated_at": "2026-04-14T20:59:34Z",
                    "capture_deadline_hours": 24,
                    "capture_deadline_utc": "2026-04-15T20:59:34Z",
                    "host_groups": {
                        "windows": {
                            "request_count": 1,
                            "tuples": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_installer_relative_path": "files/chummer-avalonia-win-x64-installer.exe",
                                    "expected_installer_sha256": "a" * 64,
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "startup_smoke_receipt_contract": {
                                        "ready_checkpoint": "pre_ui_event_loop",
                                        "head_id": "avalonia",
                                        "platform": "windows",
                                        "rid": "win-x64",
                                        "host_class_contains": "windows",
                                        "status_any_of": ["pass", "ready"],
                                    },
                                    "proof_capture_commands": ["echo windows-proof"],
                                }
                            ],
                        }
                    },
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    journey_gates.write_text(json.dumps({"journeys": []}, indent=2) + "\n", encoding="utf-8")
    release_channel.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-14T20:59:34Z",
                "channel": {"artifacts": []},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = out.read_text(encoding="utf-8")
    assert "## After Host Proof Capture" in payload
    republish_payload = (out.parent / "external-proof-commands" / "republish-after-host-proof.sh").read_text(
        encoding="utf-8"
    )
    assert f"--release-channel {release_channel}" in republish_payload


def test_materialize_external_proof_runbook_removes_stale_existing_bundle_archive(tmp_path: Path) -> None:
    module = _load_runbook_module()
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"
    installer_bytes = bytes.fromhex("44" * 32)
    installer_sha256 = hashlib.sha256(installer_bytes).hexdigest()
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["macos"],
                    "host_groups": {
                        "macos": {
                            "request_count": 1,
                            "tuples": ["avalonia:osx-arm64:macos"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:osx-arm64:macos",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-osx-arm64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-osx-arm64-installer.dmg",
                                    "expected_installer_relative_path": "files/chummer-avalonia-osx-arm64-installer.dmg",
                                    "expected_installer_sha256": "424b3216afedf86347494eea985cc1e7ceca7cb8cbf7aff04a475456a15973f4",
                                    "expected_public_install_route": "/downloads/install/avalonia-osx-arm64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                                    "startup_smoke_receipt_contract": {
                                        "ready_checkpoint": "pre_ui_event_loop",
                                        "head_id": "avalonia",
                                        "platform": "macos",
                                        "rid": "osx-arm64",
                                        "host_class_contains": "macos",
                                        "status_any_of": ["pass", "passed", "ready"],
                                    },
                                    "proof_capture_commands": [
                                        "echo macos-proof",
                                    ],
                                }
                            ],
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    journey_gates.write_text(json.dumps({"journeys": []}, indent=2) + "\n", encoding="utf-8")
    commands_dir.mkdir(parents=True, exist_ok=True)

    group = json.loads(support_packets.read_text(encoding="utf-8"))["unresolved_external_proof_execution_plan"][
        "host_groups"
    ]["macos"]
    expected_manifest = module._bundle_manifest_payload_for_group(group, host="macos")
    bundle_archive = commands_dir / "macos-proof-bundle.tgz"
    installer_bytes = b"fixture-installer-bytes"
    expected_manifest["requests"][0]["expected_installer_sha256"] = hashlib.sha256(installer_bytes).hexdigest()
    stale_receipt = {
        "headId": "avalonia",
        "platform": "macos",
        "rid": "osx-arm64",
        "hostClass": "macos-host",
        "readyCheckpoint": "pre_ui_event_loop",
        "status": "pass",
        "recordedAtUtc": _iso_z(datetime.now(timezone.utc) - timedelta(days=3)),
    }
    _write_bundle_archive(
        archive_path=bundle_archive,
        manifest_payload=expected_manifest,
        installer_relative_path="files/chummer-avalonia-osx-arm64-installer.dmg",
        installer_bytes=installer_bytes,
        receipt_relative_path="startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
        receipt_payload=stale_receipt,
    )
    assert bundle_archive.is_file()
    assert module._bundle_archive_is_reusable(bundle_archive, expected_manifest=expected_manifest) is False

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--commands-dir",
            str(commands_dir),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert not bundle_archive.exists()


def test_materialize_external_proof_runbook_preserves_per_tuple_command_sequences(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 2,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 2,
                            "tuples": [
                                "avalonia:win-x64:windows",
                                "blazor-desktop:win-x64:windows",
                            ],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "proof_capture_commands": [
                                        "echo tuple-1-proof",
                                        "echo refresh-manifest",
                                    ],
                                },
                                {
                                    "tuple_id": "blazor-desktop:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "blazor-desktop-win-x64-installer",
                                    "expected_installer_file_name": "chummer-blazor-desktop-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/blazor-desktop-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json",
                                    "proof_capture_commands": [
                                        "echo tuple-2-proof",
                                        "echo refresh-manifest",
                                    ],
                                },
                            ],
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = out.read_text(encoding="utf-8")
    assert payload.count("`echo refresh-manifest`") == 2
    assert payload.count("\necho refresh-manifest\n") == 1
    assert payload.count("${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/") >= 4
    assert payload.count("\nbash -lc '") >= 5
    assert "    - `echo tuple-1-proof`" in payload
    assert "    - `echo tuple-2-proof`" in payload
    assert payload.count("\ncd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh\n") == 1
    assert "### Commands (Host Validation)" in payload
    assert payload.count("\ncd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-") == 2


def test_materialize_external_proof_runbook_normalizes_legacy_capture_command_tokens(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 1,
                            "tuple_ids": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tupleId": "avalonia:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "proofCaptureCommands": [
                                        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=linux CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh "
                                        "/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                        "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                                    ],
                                }
                            ],
                        },
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = out.read_text(encoding="utf-8")
    commands_dir = out.parent / "external-proof-commands"
    capture_script = commands_dir / "capture-windows-proof.sh"
    script_payload = capture_script.read_text(encoding="utf-8")
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=linux" not in payload
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=linux" not in script_payload
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows" in script_payload
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=Windows" in script_payload
    assert "CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host" in script_payload


def test_materialize_external_proof_runbook_uses_expected_installer_relative_path_in_validation_scripts(
    tmp_path: Path,
) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 1,
                            "tuples": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_installer_relative_path": "quarantine/chummer-avalonia-win-x64-installer.exe",
                                    "expected_installer_sha256": "a" * 64,
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "capture_deadline_utc": "2026-04-06T00:00:00Z",
                                    "proof_capture_commands": ["echo capture-proof"],
                                }
                            ],
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    windows_capture = out.parent / "external-proof-commands" / "capture-windows-proof.sh"
    windows_validate = out.parent / "external-proof-commands" / "validate-windows-proof.sh"
    capture_payload = windows_capture.read_text(encoding="utf-8")
    validate_payload = windows_validate.read_text(encoding="utf-8")
    assert (
        "/docker/chummercomplete/chummer6-ui/Docker/Downloads/quarantine/chummer-avalonia-win-x64-installer.exe"
        in capture_payload
    )
    assert "/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe" not in capture_payload
    assert "installer-preflight-sha256-mismatch" in capture_payload
    assert "installer-postdownload-sha256-mismatch" in capture_payload
    assert (
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/quarantine/chummer-avalonia-win-x64-installer.exe"
        in validate_payload
    )
    assert "/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe" not in validate_payload


def test_materialize_external_proof_runbook_reports_no_backlog(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 0,
                    "hosts": [],
                    "host_groups": {},
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = out.read_text(encoding="utf-8")
    commands_dir = out.parent / "external-proof-commands"
    assert "unresolved_request_count: 0" in payload
    assert "## Generated Command Files" in payload
    assert f"commands_dir: `{commands_dir}`" in payload
    assert "No unresolved external-proof requests are currently queued." in payload
    assert (commands_dir / "republish-after-host-proof.sh").is_file()


def test_materialize_external_proof_runbook_accepts_camel_case_plan_fields(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "requestCount": 1,
                    "hosts": ["windows"],
                    "generatedAt": "2026-04-05T00:00:00Z",
                    "releaseChannelGeneratedAt": "2026-04-05T00:00:00Z",
                    "captureDeadlineHours": 24,
                    "captureDeadlineUtc": "2026-04-06T00:00:00Z",
                    "hostGroups": {
                        "windows": {
                            "requestCount": 1,
                            "tupleIds": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tupleId": "avalonia:win-x64:windows",
                                    "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expectedArtifactId": "avalonia-win-x64-installer",
                                    "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                                    "expectedInstallerSha256": "a" * 64,
                                    "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                                    "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "startupSmokeReceiptContract": {
                                        "readyCheckpoint": "pre_ui_event_loop",
                                        "headId": "avalonia",
                                        "platform": "windows",
                                        "rid": "win-x64",
                                        "hostClassContains": "windows",
                                        "statusAnyOf": ["pass", "ready"],
                                    },
                                    "captureDeadlineUtc": "2026-04-06T00:00:00Z",
                                    "proofCaptureCommands": [
                                        "echo windows-proof",
                                        "echo refresh-manifest",
                                    ],
                                }
                            ],
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = out.read_text(encoding="utf-8")
    commands_dir = out.parent / "external-proof-commands"
    windows_capture = commands_dir / "capture-windows-proof.sh"
    windows_validate = commands_dir / "validate-windows-proof.sh"
    windows_capture_ps1 = commands_dir / "capture-windows-proof.ps1"
    windows_validate_ps1 = commands_dir / "validate-windows-proof.ps1"

    assert "plan_generated_at: 2026-04-05T00:00:00Z" in payload
    assert "release_channel_generated_at: 2026-04-05T00:00:00Z" in payload
    assert "capture_deadline_hours: 24" in payload
    assert "capture_deadline_utc: 2026-04-06T00:00:00Z" in payload
    assert "`avalonia:win-x64:windows`" in payload
    assert "echo windows-proof" in windows_capture.read_text(encoding="utf-8")
    assert "installer-contract-mismatch" in windows_validate.read_text(encoding="utf-8")
    assert "release-channel-contract-mismatch" in windows_validate.read_text(encoding="utf-8")
    assert "receipt-contract-mismatch" in windows_validate.read_text(encoding="utf-8")
    capture_ps1_payload = windows_capture_ps1.read_text(encoding="utf-8")
    validate_ps1_payload = windows_validate_ps1.read_text(encoding="utf-8")
    assert "$ErrorActionPreference = 'Stop'" in capture_ps1_payload
    assert "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }" in capture_ps1_payload
    assert "bash -lc 'echo windows-proof'" in capture_ps1_payload
    assert "$ErrorActionPreference = 'Stop'" in validate_ps1_payload
    assert "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }" in validate_ps1_payload
    assert "bash -lc 'cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'" in validate_ps1_payload


def test_materialize_external_proof_runbook_fails_with_absolute_expected_installer_relative_path(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 1,
                            "tuples": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_installer_relative_path": "/tmp/quarantine/chummer-avalonia-win-x64-installer.exe",
                                    "expected_installer_sha256": "a" * 64,
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "proof_capture_commands": ["echo capture-proof"],
                                }
                            ],
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external-proof materialize failed: malformed relative paths" in result.stderr
    assert "must be relative" in result.stderr


def test_materialize_external_proof_runbook_fails_with_parent_traversal_startup_smoke_relative_path(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 1,
                            "tuples": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_installer_relative_path": "files/chummer-avalonia-win-x64-installer.exe",
                                    "expected_installer_sha256": "a" * 64,
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "../startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "proof_capture_commands": ["echo capture-proof"],
                                }
                            ],
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external-proof materialize failed: malformed relative paths" in result.stderr
    assert "must not contain '..' segments" in result.stderr


def test_materialize_external_proof_runbook_fails_with_malformed_tuple_id(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 1,
                            "tuples": ["avalonia:win-x64"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "expected_installer_sha256": "a" * 64,
                                    "proof_capture_commands": ["echo capture-proof"],
                                }
                            ],
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external-proof materialize failed: malformed relative paths" in result.stderr
    assert "tuple_id is invalid" in result.stderr


def test_materialize_external_proof_runbook_fails_when_tuple_id_is_missing(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 1,
                            "tuples": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "expected_installer_sha256": "a" * 64,
                                    "proof_capture_commands": ["echo capture-proof"],
                                }
                            ],
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external-proof materialize failed: malformed relative paths" in result.stderr
    assert ".requests[0].tuple_id is missing" in result.stderr


def test_materialize_external_proof_runbook_preserves_host_and_tuple_order(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 3,
                    "hosts": ["windows", "macos", "windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 2,
                            "tuples": [
                                "zeta:win-x64:windows",
                                "alpha:win-x64:windows",
                                "zeta:win-x64:windows",
                            ],
                            "requests": [
                                {
                                    "tuple_id": "zeta:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "zeta-win-x64-installer",
                                    "expected_installer_file_name": "chummer-zeta-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/zeta-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-zeta-win-x64.receipt.json",
                                    "proof_capture_commands": ["echo zeta-win"],
                                },
                                {
                                    "tuple_id": "alpha:win-x64:windows",
                                    "required_proofs": ["startup_smoke_receipt", "promoted_installer_artifact"],
                                    "expected_artifact_id": "alpha-win-x64-installer",
                                    "expected_installer_file_name": "chummer-alpha-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/alpha-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-alpha-win-x64.receipt.json",
                                    "proof_capture_commands": ["echo alpha-win"],
                                },
                            ],
                        },
                        "macos": {
                            "request_count": 1,
                            "tuples": ["gamma:osx-arm64:macos"],
                            "requests": [
                                {
                                    "tuple_id": "gamma:osx-arm64:macos",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "gamma-osx-arm64-installer",
                                    "expected_installer_file_name": "chummer-gamma-osx-arm64-installer.dmg",
                                    "expected_public_install_route": "/downloads/install/gamma-osx-arm64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-gamma-osx-arm64.receipt.json",
                                    "proof_capture_commands": ["echo gamma-osx"],
                                }
                            ],
                        },
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = out.read_text(encoding="utf-8")
    assert payload.index("## Host: windows") < payload.index("## Host: macos")
    windows_start = payload.index("## Host: windows")
    host_commands_start = payload.index("### Requested Tuples", windows_start)
    host_commands_end = payload.index("### Commands (Host Consolidated)", host_commands_start)
    windows_tuples_block = payload[host_commands_start:host_commands_end]
    assert "`zeta:win-x64:windows`" in windows_tuples_block
    assert "`alpha:win-x64:windows`" in windows_tuples_block
    assert windows_tuples_block.index("`zeta:win-x64:windows`") < windows_tuples_block.index(
        "`alpha:win-x64:windows`"
    )


def test_materialize_external_proof_runbook_fails_for_duplicate_tuple_ids_in_host_group(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 1,
                            "tuples": [
                                "avalonia:win-x64:windows",
                                "avalonia:win-x64:windows",
                            ],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "proof_capture_commands": ["echo capture-proof"],
                                }
                            ],
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "unresolved_external_proof_execution_plan.host_groups.windows.tuples[1] duplicate tuple_id" in result.stderr


def test_materialize_external_proof_runbook_fails_for_duplicate_request_tuple_ids(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 2,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 2,
                            "tuples": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "proof_capture_commands": ["echo capture-proof"],
                                },
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "proof_capture_commands": ["echo capture-proof"],
                                },
                            ],
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "requests duplicate tuple_id: avalonia:win-x64:windows" in result.stderr


def test_materialize_external_proof_runbook_fails_for_required_host_mismatch(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 1,
                            "tuples": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "required_host": "macos",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "proof_capture_commands": ["echo capture-proof"],
                                }
                            ],
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "requiredHost (macos) does not match group host (windows)" in result.stderr


def test_materialize_external_proof_runbook_fails_when_request_required_proofs_are_incomplete(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 1,
                            "tuples": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "proof_capture_commands": ["echo capture-proof"],
                                }
                            ],
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "required_proofs is missing required tokens: startup_smoke_receipt" in result.stderr


def test_materialize_external_proof_runbook_reports_stale_directory_bundle_state(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"
    installer_bytes = bytes.fromhex("44" * 32)
    installer_sha256 = hashlib.sha256(installer_bytes).hexdigest()
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["macos"],
                    "generated_at": "2026-04-14T23:19:34Z",
                    "release_channel_generated_at": "2026-04-14T22:45:00Z",
                    "capture_deadline_hours": 24,
                    "capture_deadline_utc": "2026-04-15T22:45:00Z",
                    "host_groups": {
                        "macos": {
                            "request_count": 1,
                            "tuples": ["avalonia:osx-arm64:macos"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:osx-arm64:macos",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-osx-arm64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-osx-arm64-installer.dmg",
                                    "expected_installer_relative_path": "files/chummer-avalonia-osx-arm64-installer.dmg",
                                        "expected_installer_sha256": installer_sha256,
                                    "expected_public_install_route": "/downloads/install/avalonia-osx-arm64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                                    "startup_smoke_receipt_contract": {
                                        "ready_checkpoint": "pre_ui_event_loop",
                                        "head_id": "avalonia",
                                        "platform": "macos",
                                        "rid": "osx-arm64",
                                        "host_class_contains": "macos",
                                        "status_any_of": ["pass", "passed", "ready"],
                                    },
                                    "proof_capture_commands": ["echo macos-proof"],
                                    "local_evidence": {
                                        "installer_artifact": {
                                            "path": "/docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg",
                                            "present": True,
                                            "state": "present_sha256_match",
                                        },
                                        "startup_smoke_receipt": {
                                            "path": "/docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                                            "present": True,
                                            "state": "stale",
                                            "recorded_at_utc": "2026-04-11T20:19:47.089302+00:00",
                                            "age_seconds": 270101,
                                        },
                                    },
                                }
                            ],
                        }
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    journey_gates.write_text(json.dumps({"journeys": []}, indent=2) + "\n", encoding="utf-8")

    bundle_dir = commands_dir / "host-proof-bundles" / "macos"
    (bundle_dir / "files").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "startup-smoke").mkdir(parents=True, exist_ok=True)
    (bundle_dir / "external-proof-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "host": "macos",
                "request_count": 1,
                "requests": [
                        {
                            "tuple_id": "avalonia:osx-arm64:macos",
                            "expected_installer_bundle_relative_path": "files/chummer-avalonia-osx-arm64-installer.dmg",
                            "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                            "expected_installer_sha256": installer_sha256,
                        }
                    ],
                },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (bundle_dir / "files" / "chummer-avalonia-osx-arm64-installer.dmg").write_bytes(installer_bytes)
    (bundle_dir / "startup-smoke" / "startup-smoke-avalonia-osx-arm64.receipt.json").write_text(
        json.dumps(
            {
                "headId": "avalonia",
                "platform": "macos",
                "rid": "osx-arm64",
                "hostClass": "macos-host",
                "readyCheckpoint": "pre_ui_event_loop",
                "status": "pass",
                "recordedAtUtc": _iso_z(datetime.now(timezone.utc) - timedelta(days=3)),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--commands-dir",
            str(commands_dir),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = out.read_text(encoding="utf-8")
    assert "cached_bundle_status: `stale_directory`" in payload
    assert "cached_bundle_detail: `receipt_stale:recorded_at=" in payload
    assert "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json`" in payload
    assert f"cached_bundle_directory_path: `{bundle_dir}`" in payload
    assert "local_startup_smoke_receipt_state: `stale`" in payload
    assert "local_startup_smoke_receipt_recorded_at: `2026-04-11T20:19:47.089302+00:00`" in payload
    assert "local_startup_smoke_receipt_age_seconds: `270101`" in payload
