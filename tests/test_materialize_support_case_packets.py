from __future__ import annotations

import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/materialize_support_case_packets.py")


def test_materialize_support_case_packets(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_a",
                        "clusterKey": "support:aaaa",
                        "kind": "bug_report",
                        "status": "new",
                        "title": "Desktop crash on save",
                        "summary": "Save explodes in preview.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-alpha",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                    },
                    {
                        "caseId": "support_case_b",
                        "clusterKey": "support:bbbb",
                        "kind": "feedback",
                        "status": "clustered",
                        "title": "Downloads copy is confusing",
                        "summary": "I cannot tell which build to install.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": True,
                        "releaseChannel": "preview",
                    },
                    {
                        "caseId": "support_case_c",
                        "clusterKey": "support:cccc",
                        "kind": "feedback",
                        "status": "deferred",
                        "title": "Already closed",
                        "summary": "This should not remain in the public packet list.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                    },
                ]
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
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["contract_name"] == "fleet.support_case_packets"
    assert payload["summary"]["open_case_count"] == 2
    assert payload["summary"]["design_impact_count"] == 1
    assert payload["summary"]["owner_repo_counts"] == {
        "chummer6-design": 1,
        "chummer6-ui": 1,
    }
    assert payload["summary"]["closure_waiting_on_release_truth"] == 0
    assert payload["summary"]["needs_human_response"] == 2
    assert payload["summary"]["update_required_case_count"] == 0
    assert payload["summary"]["update_required_routed_to_downloads_count"] == 0
    assert payload["summary"]["update_required_misrouted_case_count"] == 0
    assert payload["summary"]["external_proof_required_case_count"] == 0
    assert payload["summary"]["external_proof_required_host_counts"] == {}
    assert payload["summary"]["external_proof_required_tuple_counts"] == {}
    assert payload["summary"]["unresolved_external_proof_request_count"] == 0
    assert payload["summary"]["unresolved_external_proof_request_host_counts"] == {}
    assert payload["summary"]["unresolved_external_proof_request_tuple_counts"] == {}
    assert payload["summary"]["unresolved_external_proof_request_hosts"] == []
    assert payload["summary"]["unresolved_external_proof_request_tuples"] == []
    assert payload["summary"]["unresolved_external_proof_request_specs"] == {}
    assert payload["unresolved_external_proof_execution_plan"] == {
        "request_count": 0,
        "hosts": [],
        "host_groups": {},
    }
    assert payload["source"]["source_kind"] == "local_file"
    assert len(payload["packets"]) == 2
    bug_packet = next(item for item in payload["packets"] if item["kind"] == "bug_report")
    canon_packet = next(item for item in payload["packets"] if item["target_repo"] == "chummer6-design")
    assert bug_packet["primary_lane"] == "code"
    assert bug_packet["target_repo"] == "chummer6-ui"
    assert bug_packet["install_truth_state"] in {
        "registry_unavailable",
        "channel_mismatch",
        "promoted_tuple_match",
        "tuple_not_on_promoted_shelf",
        "insufficient_install_context",
    }
    assert isinstance(bug_packet["install_diagnosis"], dict)
    assert isinstance(bug_packet["fix_confirmation"], dict)
    assert isinstance(bug_packet["recovery_path"], dict)
    assert canon_packet["primary_lane"] == "canon"
    assert "FEEDBACK_AND_SIGNAL_OODA_LOOP.md" in canon_packet["affected_canon_files"]
    assert "reporter_subject_id" not in bug_packet
    assert "case_id" not in bug_packet
    assert "cluster_key" not in bug_packet
    assert "title" not in bug_packet
    assert "summary" not in bug_packet


def test_materialize_support_case_packets_refreshes_compile_manifest(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    published = repo_root / ".codex-studio" / "published"
    published.mkdir(parents=True)
    source = tmp_path / "support_cases.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_install",
                        "clusterKey": "support:install",
                        "kind": "install_help",
                        "status": "new",
                        "title": "Need install help",
                        "summary": "Updater is blocked.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                    }
                ]
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
            "--source",
            str(source),
            "--out",
            str(published / "SUPPORT_CASE_PACKETS.generated.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    manifest_payload = json.loads((published / "compile.manifest.json").read_text(encoding="utf-8"))
    assert "SUPPORT_CASE_PACKETS.generated.json" in manifest_payload["artifacts"]


def test_materialize_support_case_packets_reads_authenticated_remote_source(tmp_path: Path) -> None:
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    payload = {
        "items": [
            {
                "caseId": "support_case_remote",
                "clusterKey": "support:remote",
                "kind": "install_help",
                "status": "new",
                "title": "Need install help",
                "summary": "Remote triage feed works.",
                "candidateOwnerRepo": "chummer6-hub",
                "designImpactSuspected": False,
            }
        ]
    }
    token = "remote-token"

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.headers.get("Authorization") != f"Bearer {token}":
                self.send_response(401)
                self.end_headers()
                return
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A003
            return

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    f"http://127.0.0.1:{server.server_address[1]}/api/v1/support/cases/triage",
                    "--bearer-token",
                    token,
                    "--out",
                    str(out_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

    assert result.returncode == 0, result.stderr
    rendered = json.loads(out_path.read_text(encoding="utf-8"))
    assert rendered["source"]["source_kind"] == "remote_url"
    assert rendered["summary"]["open_case_count"] == 1


def test_materialize_support_case_packets_falls_back_from_host_docker_internal(tmp_path: Path) -> None:
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    payload = {
        "items": [
            {
                "caseId": "support_case_host_fallback",
                "clusterKey": "support:host-fallback",
                "kind": "install_help",
                "status": "new",
                "title": "Need install help",
                "summary": "host.docker.internal fallback works.",
                "candidateOwnerRepo": "chummer6-hub",
                "designImpactSuspected": False,
            }
        ]
    }

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.headers.get("X-Forwarded-Proto") != "https":
                self.send_response(307)
                self.send_header("Location", f"https://127.0.0.1{self.path}")
                self.end_headers()
                return
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A003
            return

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    f"http://host.docker.internal:{server.server_address[1]}/api/v1/support/cases/triage",
                    "--out",
                    str(out_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)

    assert result.returncode == 0, result.stderr
    rendered = json.loads(out_path.read_text(encoding="utf-8"))
    assert rendered["source"]["source_kind"] == "remote_url"
    assert rendered["summary"]["open_case_count"] == 1


def test_materialize_support_case_packets_reads_source_from_runtime_env_file(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    env_file = tmp_path / "runtime.env"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_env",
                        "clusterKey": "support:env",
                        "kind": "install_help",
                        "status": "new",
                        "title": "Need install help",
                        "summary": "Runtime env source works.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    env_file.write_text(
        f"FLEET_SUPPORT_CASE_SOURCE={source}\nFLEET_INTERNAL_API_TOKEN=token-from-runtime-env\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": os.environ.get("PATH", ""), "FLEET_RUNTIME_ENV_PATHS": str(env_file)},
    )

    assert result.returncode == 0, result.stderr
    rendered = json.loads(out_path.read_text(encoding="utf-8"))
    assert rendered["source"]["source_kind"] == "local_file"
    assert rendered["summary"]["open_case_count"] == 1


def test_materialize_support_case_packets_enriches_install_truth_from_release_channel(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_release_waiting",
                        "clusterKey": "support:release",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix is staged",
                        "summary": "Reporter still needs to verify.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-release-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    },
                    {
                        "caseId": "support_case_confirmed",
                        "clusterKey": "support:confirmed",
                        "kind": "install_help",
                        "status": "user_notified",
                        "title": "Confirmed fix",
                        "summary": "Reporter confirmed the fix.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                        "installationId": "install-release-2",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                        "reporterVerificationState": "confirmed_fixed",
                    },
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "fixAvailabilitySummary": "Fix is on the preview shelf.",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
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
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["open_case_count"] == 1
    assert payload["summary"]["closure_waiting_on_release_truth"] == 1
    assert payload["summary"]["needs_human_response"] == 0
    assert payload["summary"]["install_truth_state_counts"]["promoted_tuple_match"] == 1
    assert payload["summary"]["update_required_case_count"] == 0
    assert payload["summary"]["update_required_routed_to_downloads_count"] == 0
    assert payload["summary"]["update_required_misrouted_case_count"] == 0
    assert payload["summary"]["external_proof_required_case_count"] == 0
    assert payload["summary"]["external_proof_required_host_counts"] == {}
    assert payload["summary"]["external_proof_required_tuple_counts"] == {}
    assert payload["summary"]["unresolved_external_proof_request_count"] == 0
    assert payload["summary"]["unresolved_external_proof_request_host_counts"] == {}
    assert payload["summary"]["unresolved_external_proof_request_tuple_counts"] == {}
    assert payload["summary"]["unresolved_external_proof_request_hosts"] == []
    assert payload["summary"]["unresolved_external_proof_request_tuples"] == []
    assert payload["summary"]["unresolved_external_proof_request_specs"] == {}
    waiting_packet = next(item for item in payload["packets"] if item["kind"] == "bug_report")
    assert waiting_packet["install_diagnosis"]["registry_channel_id"] == "preview"
    assert waiting_packet["install_diagnosis"]["registry_release_channel_status"] == "published"
    assert waiting_packet["install_diagnosis"]["tuple_present_on_promoted_shelf"] is True
    assert waiting_packet["install_diagnosis"]["registry_release_proof_status"] == "passed"
    assert waiting_packet["install_diagnosis"]["external_proof_required"] is False
    assert waiting_packet["install_diagnosis"]["external_proof_request"] == {
        "tuple_id": "",
        "channel_id": "",
        "tuple_entry_count": 0,
        "tuple_unique": False,
        "required_host": "",
        "required_proofs": [],
        "expected_artifact_id": "",
        "expected_installer_file_name": "",
        "expected_public_install_route": "",
        "expected_startup_smoke_receipt_path": "",
        "startup_smoke_receipt_contract": {},
        "proof_capture_commands": [],
    }
    assert waiting_packet["recovery_path"]["href"] == "/account/support"
    fix_states = sorted(item["fix_confirmation"]["state"] for item in payload["packets"])
    assert fix_states == ["awaiting_reporter_verification"]


def test_materialize_support_case_packets_projects_external_proof_requests_for_missing_tuple(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_windows_tuple_missing",
                        "clusterKey": "support:windows-missing",
                        "kind": "install_help",
                        "status": "accepted",
                        "title": "Windows tuple missing from promoted shelf",
                        "summary": "Support needs host-proof request truth for this install tuple.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                        "installationId": "install-windows-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "windows",
                        "arch": "x64",
                        "installedVersion": "1.2.3",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "coverage_incomplete",
                "supportabilityState": "review_required",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ],
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startupSmokeReceiptContract": {
                                "statusAnyOf": ["pass", "passed", "ready"],
                                "readyCheckpoint": "pre_ui_event_loop",
                                "headId": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "hostClassContains": "windows",
                            },
                        }
                    ],
                },
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
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["install_truth_state_counts"]["tuple_not_on_promoted_shelf"] == 1
    assert payload["summary"]["external_proof_required_case_count"] == 1
    assert payload["summary"]["external_proof_required_host_counts"] == {"windows": 1}
    assert payload["summary"]["external_proof_required_tuple_counts"] == {"avalonia:win-x64:windows": 1}
    assert payload["summary"]["unresolved_external_proof_request_count"] == 1
    assert payload["summary"]["unresolved_external_proof_request_host_counts"] == {"windows": 1}
    assert payload["summary"]["unresolved_external_proof_request_tuple_counts"] == {"avalonia:win-x64:windows": 1}
    assert payload["summary"]["unresolved_external_proof_request_hosts"] == ["windows"]
    assert payload["summary"]["unresolved_external_proof_request_tuples"] == ["avalonia:win-x64:windows"]
    assert payload["summary"]["unresolved_external_proof_request_specs"] == {
        "avalonia:win-x64:windows": {
            "channel_id": "preview",
            "tuple_entry_count": 1,
            "tuple_unique": True,
            "required_host": "windows",
            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
            "expected_artifact_id": "avalonia-win-x64-installer",
            "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
            "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
            "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
            "startup_smoke_receipt_contract": {
                "head_id": "avalonia",
                "host_class_contains": "windows",
                "platform": "windows",
                "ready_checkpoint": "pre_ui_event_loop",
                "rid": "win-x64",
                "status_any_of": ["pass", "passed", "ready"],
            },
            "proof_capture_commands": [
                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
            ],
        }
    }
    packet = payload["packets"][0]
    assert packet["install_truth_state"] == "tuple_not_on_promoted_shelf"
    assert packet["install_diagnosis"]["case_tuple_id"] == "avalonia:win-x64:windows"
    assert packet["install_diagnosis"]["external_proof_required"] is True
    assert packet["install_diagnosis"]["external_proof_request"] == {
        "tuple_id": "avalonia:win-x64:windows",
        "channel_id": "preview",
        "tuple_entry_count": 1,
        "tuple_unique": True,
        "required_host": "windows",
        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
        "expected_artifact_id": "avalonia-win-x64-installer",
        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
        "startup_smoke_receipt_contract": {
            "head_id": "avalonia",
            "host_class_contains": "windows",
            "platform": "windows",
            "ready_checkpoint": "pre_ui_event_loop",
            "rid": "win-x64",
            "status_any_of": ["pass", "passed", "ready"],
        },
        "proof_capture_commands": [
            "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
            "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
        ],
    }
    assert packet["recovery_path"]["action_id"] == "open_downloads"


def test_materialize_support_case_packets_matches_external_proof_request_when_case_uses_legacy_tuple_order(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_windows_tuple_legacy_order",
                        "clusterKey": "support:windows-legacy-order",
                        "kind": "install_help",
                        "status": "accepted",
                        "title": "Windows tuple captured in legacy tuple order",
                        "summary": "Case payload provides head:platform:rid without arch metadata.",
                        "candidateOwnerRepo": "chummer6-hub",
                        "designImpactSuspected": False,
                        "installationId": "install-windows-legacy-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "windows",
                        "tupleId": "avalonia:windows:win-x64",
                        "installedVersion": "1.2.3",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "coverage_incomplete",
                "supportabilityState": "review_required",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ],
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        }
                    ],
                },
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
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["external_proof_required_case_count"] == 1
    assert payload["summary"]["external_proof_required_tuple_counts"] == {"avalonia:win-x64:windows": 1}
    packet = payload["packets"][0]
    assert packet["install_diagnosis"]["case_tuple_id"] == "avalonia:win-x64:windows"
    assert packet["install_diagnosis"]["external_proof_required"] is True
    assert packet["install_diagnosis"]["external_proof_request"]["tuple_id"] == "avalonia:win-x64:windows"


def test_materialize_support_case_packets_reports_release_channel_external_proof_backlog_without_open_cases(
    tmp_path: Path,
) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(json.dumps({"items": []}, indent=2) + "\n", encoding="utf-8")
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        },
                        {
                            "tupleId": "blazor-desktop:osx-arm64:macos",
                            "head": "blazor-desktop",
                            "platform": "macos",
                            "rid": "osx-arm64",
                            "requiredHost": "macos",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        },
                    ]
                },
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
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["open_case_count"] == 0
    assert payload["summary"]["external_proof_required_case_count"] == 0
    assert payload["summary"]["unresolved_external_proof_request_count"] == 2
    assert payload["summary"]["unresolved_external_proof_request_host_counts"] == {"macos": 1, "windows": 1}
    assert payload["summary"]["unresolved_external_proof_request_tuple_counts"] == {
        "avalonia:win-x64:windows": 1,
        "blazor-desktop:osx-arm64:macos": 1,
    }
    assert payload["summary"]["unresolved_external_proof_request_hosts"] == ["macos", "windows"]
    assert payload["summary"]["unresolved_external_proof_request_tuples"] == [
        "avalonia:win-x64:windows",
        "blazor-desktop:osx-arm64:macos",
    ]
    assert payload["summary"]["unresolved_external_proof_request_specs"] == {
        "avalonia:win-x64:windows": {
            "channel_id": "preview",
            "tuple_entry_count": 1,
            "tuple_unique": True,
            "required_host": "windows",
            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
            "expected_artifact_id": "",
            "expected_installer_file_name": "",
            "expected_public_install_route": "",
            "expected_startup_smoke_receipt_path": "",
            "startup_smoke_receipt_contract": {
                "head_id": "avalonia",
                "host_class_contains": "windows",
                "platform": "windows",
                "ready_checkpoint": "pre_ui_event_loop",
                "rid": "win-x64",
                "status_any_of": ["pass", "passed", "ready"],
            },
            "proof_capture_commands": [
                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
            ],
        },
        "blazor-desktop:osx-arm64:macos": {
            "channel_id": "preview",
            "tuple_entry_count": 1,
            "tuple_unique": True,
            "required_host": "macos",
            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
            "expected_artifact_id": "",
            "expected_installer_file_name": "",
            "expected_public_install_route": "",
            "expected_startup_smoke_receipt_path": "",
            "startup_smoke_receipt_contract": {
                "head_id": "blazor-desktop",
                "host_class_contains": "macos",
                "platform": "macos",
                "ready_checkpoint": "pre_ui_event_loop",
                "rid": "osx-arm64",
                "status_any_of": ["pass", "passed", "ready"],
            },
            "proof_capture_commands": [
                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg blazor-desktop osx-arm64 Chummer.Blazor.Desktop /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
            ],
        },
    }
    assert payload["unresolved_external_proof_execution_plan"] == {
        "request_count": 2,
        "hosts": ["macos", "windows"],
        "host_groups": {
            "macos": {
                "request_count": 1,
                "tuples": ["blazor-desktop:osx-arm64:macos"],
                "requests": [
                    {
                        "tuple_id": "blazor-desktop:osx-arm64:macos",
                        "head_id": "blazor-desktop",
                        "platform": "macos",
                        "rid": "osx-arm64",
                        "expected_artifact_id": "",
                        "expected_installer_file_name": "",
                        "expected_public_install_route": "",
                        "expected_startup_smoke_receipt_path": "",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "startup_smoke_receipt_contract": {
                            "head_id": "blazor-desktop",
                            "host_class_contains": "macos",
                            "platform": "macos",
                            "ready_checkpoint": "pre_ui_event_loop",
                            "rid": "osx-arm64",
                            "status_any_of": ["pass", "passed", "ready"],
                        },
                        "proof_capture_commands": [
                            "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg blazor-desktop osx-arm64 Chummer.Blazor.Desktop /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                            "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                        ],
                    }
                ],
            },
            "windows": {
                "request_count": 1,
                "tuples": ["avalonia:win-x64:windows"],
                "requests": [
                    {
                        "tuple_id": "avalonia:win-x64:windows",
                        "head_id": "avalonia",
                        "platform": "windows",
                        "rid": "win-x64",
                        "expected_artifact_id": "",
                        "expected_installer_file_name": "",
                        "expected_public_install_route": "",
                        "expected_startup_smoke_receipt_path": "",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "startup_smoke_receipt_contract": {
                            "head_id": "avalonia",
                            "host_class_contains": "windows",
                            "platform": "windows",
                            "ready_checkpoint": "pre_ui_event_loop",
                            "rid": "win-x64",
                            "status_any_of": ["pass", "passed", "ready"],
                        },
                        "proof_capture_commands": [
                            "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                            "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                        ],
                    }
                ],
            },
        },
    }


def test_materialize_support_case_packets_dedupes_duplicate_external_proof_tuples(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(json.dumps({"items": []}, indent=2) + "\n", encoding="utf-8")
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        },
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact"],
                        },
                    ]
                },
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
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["operator_packet_count"] == 1
    assert payload["summary"]["unresolved_external_proof_request_count"] == 1
    assert payload["summary"]["unresolved_external_proof_request_tuple_counts"] == {
        "avalonia:win-x64:windows": 1
    }
    assert payload["summary"]["unresolved_external_proof_request_specs"] == {
        "avalonia:win-x64:windows": {
            "channel_id": "preview",
            "tuple_entry_count": 2,
            "tuple_unique": False,
            "required_host": "windows",
            "required_proofs": ["promoted_installer_artifact"],
            "expected_artifact_id": "",
            "expected_installer_file_name": "",
            "expected_public_install_route": "",
            "expected_startup_smoke_receipt_path": "",
            "startup_smoke_receipt_contract": {
                "head_id": "avalonia",
                "host_class_contains": "windows",
                "platform": "windows",
                "ready_checkpoint": "pre_ui_event_loop",
                "rid": "win-x64",
                "status_any_of": ["pass", "passed", "ready"],
            },
            "proof_capture_commands": [
                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
            ],
        }
    }
    packet = payload["packets"][0]
    assert packet["packet_kind"] == "external_proof_request"
    assert packet["install_diagnosis"]["external_proof_request"]["tuple_entry_count"] == 2
    assert packet["install_diagnosis"]["external_proof_request"]["tuple_unique"] is False


def test_materialize_support_case_packets_normalizes_external_proof_required_proofs_tokens(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(json.dumps({"items": []}, indent=2) + "\n", encoding="utf-8")
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": [
                                "STARTUP_SMOKE_RECEIPT",
                                "promoted_installer_artifact",
                                "startup_smoke_receipt",
                            ],
                        },
                    ]
                },
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
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["unresolved_external_proof_request_specs"] == {
        "avalonia:win-x64:windows": {
            "channel_id": "preview",
            "tuple_entry_count": 1,
            "tuple_unique": True,
            "required_host": "windows",
            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
            "expected_artifact_id": "",
            "expected_installer_file_name": "",
            "expected_public_install_route": "",
            "expected_startup_smoke_receipt_path": "",
            "startup_smoke_receipt_contract": {
                "head_id": "avalonia",
                "host_class_contains": "windows",
                "platform": "windows",
                "ready_checkpoint": "pre_ui_event_loop",
                "rid": "win-x64",
                "status_any_of": ["pass", "passed", "ready"],
            },
            "proof_capture_commands": [
                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
            ],
        },
    }


def test_materialize_support_case_packets_marks_update_required_when_fixed_version_differs_from_installed_version(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "caseId": "support_case_update_required",
                        "clusterKey": "support:update-required",
                        "kind": "bug_report",
                        "status": "fixed",
                        "title": "Fix published but user still on old build",
                        "summary": "User install version is behind the fixed version.",
                        "candidateOwnerRepo": "chummer6-ui",
                        "designImpactSuspected": False,
                        "installationId": "install-update-1",
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux",
                        "arch": "x64",
                        "installedVersion": "1.2.2",
                        "fixedVersion": "1.2.3",
                        "fixedChannel": "preview",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "version": "1.2.3",
                "releaseProof": {"status": "passed"},
                "rolloutState": "published",
                "supportabilityState": "supported",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [
                        {
                            "tupleId": "avalonia:linux:linux-x64",
                            "head": "avalonia",
                            "platform": "linux",
                            "rid": "linux-x64",
                            "artifactId": "avalonia-linux-x64-installer",
                        }
                    ]
                },
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
            "--source",
            str(source),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["open_case_count"] == 1
    assert payload["summary"]["update_required_case_count"] == 1
    assert payload["summary"]["update_required_routed_to_downloads_count"] == 1
    assert payload["summary"]["update_required_misrouted_case_count"] == 0
    packet = payload["packets"][0]
    assert packet["install_diagnosis"]["case_installed_version"] == "1.2.2"
    assert packet["install_diagnosis"]["registry_release_channel_status"] == "published"
    assert packet["install_diagnosis"]["registry_release_proof_status"] == "passed"
    assert packet["install_diagnosis"]["case_version_matches_registry_release"] is False
    assert packet["install_diagnosis"]["case_fixed_version_matches_registry_release"] is True
    assert packet["fix_confirmation"]["update_required"] is True
    assert packet["recovery_path"]["action_id"] == "open_downloads"
    assert packet["recovery_path"]["href"] == "/downloads"
