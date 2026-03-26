from __future__ import annotations

import http.server
import json
import socketserver
import subprocess
import sys
import threading
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/materialize_support_case_packets.py")


def test_materialize_support_case_packets(tmp_path: Path) -> None:
    source = tmp_path / "support_cases.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
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
                        "releaseChannel": "preview",
                        "headId": "avalonia",
                        "platform": "linux-x64",
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
        "chummer6-hub": 1,
        "chummer6-ui": 1,
    }
    assert payload["source"]["source_kind"] == "local_file"
    assert len(payload["packets"]) == 2
    bug_packet = next(item for item in payload["packets"] if item["kind"] == "bug_report")
    canon_packet = next(item for item in payload["packets"] if item["target_repo"] == "chummer6-design")
    assert bug_packet["primary_lane"] == "code"
    assert bug_packet["target_repo"] == "chummer6-ui"
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
