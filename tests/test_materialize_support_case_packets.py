from __future__ import annotations

import json
import subprocess
import sys
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
    packets = {item["case_id"]: item for item in payload["packets"]}
    assert packets["support_case_a"]["primary_lane"] == "code"
    assert packets["support_case_a"]["target_repo"] == "chummer6-ui"
    assert packets["support_case_b"]["primary_lane"] == "canon"
    assert packets["support_case_b"]["target_repo"] == "chummer6-design"
    assert "FEEDBACK_AND_SIGNAL_OODA_LOOP.md" in packets["support_case_b"]["affected_canon_files"]


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
