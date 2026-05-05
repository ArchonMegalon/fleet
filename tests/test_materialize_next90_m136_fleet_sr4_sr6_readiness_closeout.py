from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m136_fleet_sr4_sr6_readiness_closeout.py")
PACKAGE_ID = "next90-m136-fleet-publish-explicit-sr4-and-sr6-readiness-plane-closeout-from-direct-proo"
QUEUE_TITLE = "Publish explicit SR4 and SR6 readiness-plane closeout from direct proofs instead of letting adjacent coverage inherit from broad desktop readiness."


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _registry() -> dict:
    return {"milestones": [{"id": 136, "work_tasks": [{"id": "136.19", "owner": "fleet", "title": QUEUE_TITLE}]}]}


def _queue_item() -> dict:
    return {
        "title": QUEUE_TITLE,
        "task": QUEUE_TITLE,
        "package_id": PACKAGE_ID,
        "work_task_id": "136.19",
        "frontier_id": 7496747405,
        "milestone_id": 136,
        "status": "not_started",
        "wave": "W23",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["publish_explicit_sr4_and_sr6_readiness_plane_closeout_fr:fleet"],
    }


def _guide() -> str:
    return """## Wave 23 - close calm-under-pressure payoff and veteran continuity

### 136. Calm-under-pressure payoff, veteran-depth parity, and campaign continuity closure
"""


def _bar() -> str:
    return """### 3. SR4, SR5, and SR6 must feel authored, not flattened
* deterministic parity in engine truth
* ruleset-specific interaction affordances where a shared generic workflow would feel confusing or lossy
"""


def _planes() -> dict:
    return {
        "planes": [
            {
                "id": "sr4_parity_ready",
                "owner_repos": ["fleet", "chummer6-ui"],
                "proving_artifacts": [
                    "/docker/chummercomplete/chummer-presentation/.codex-studio/published/SR4_DESKTOP_WORKFLOW_PARITY.generated.json",
                    "/docker/chummercomplete/chummer-presentation/.codex-studio/published/SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json",
                ],
                "fail_when": [
                    "SR4 explicit parity proofs stay absent, external-only, or below bounded replacement quality",
                ],
            },
            {
                "id": "sr6_parity_ready",
                "owner_repos": ["fleet", "chummer6-ui"],
                "proving_artifacts": [
                    "/docker/chummercomplete/chummer-presentation/.codex-studio/published/SR6_DESKTOP_WORKFLOW_PARITY.generated.json",
                    "/docker/chummercomplete/chummer-presentation/.codex-studio/published/SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json",
                ],
                "fail_when": [
                    "SR6 explicit parity proofs stay absent, external-only, or below bounded replacement quality",
                ],
            },
        ]
    }


def _flagship_payload(*, sr4_status: str = "ready", sr6_status: str = "ready", frontier_linked: bool = True) -> dict:
    return {
        "readiness_planes": {
            "sr4_parity_ready": {
                "status": sr4_status,
                "summary": "SR4 parity proof is explicit and current.",
                "reasons": [] if sr4_status == "ready" else ["SR4 parity proof is still incomplete."],
                "evidence": {
                    "sr4_workflow_parity_status": "pass" if sr4_status == "ready" else "fail",
                    "sr4_workflow_parity_external_only_missing_api_surface_contract": False,
                    "sr4_sr6_frontier_receipt_status": "pass" if frontier_linked else "fail",
                },
            },
            "sr6_parity_ready": {
                "status": sr6_status,
                "summary": "SR6 parity proof is explicit and current.",
                "reasons": [] if sr6_status == "ready" else ["SR6 parity proof is still incomplete."],
                "evidence": {
                    "sr6_workflow_parity_status": "pass" if sr6_status == "ready" else "fail",
                    "sr6_workflow_parity_external_only_missing_api_surface_contract": False,
                    "sr4_sr6_frontier_receipt_status": "pass" if frontier_linked else "fail",
                    "ui_element_parity_audit_gap_ids": [],
                },
            },
            "flagship_ready": {
                "status": "ready",
                "summary": "Flagship replacement truth is fully green.",
                "reasons": [],
                "evidence": {
                    "sr4_parity_ready": sr4_status == "ready",
                    "sr6_parity_ready": sr6_status == "ready",
                },
            },
        }
    }


def _sr4_payload(*, passing: bool = True, external_only: bool = False) -> dict:
    return {
        "status": "pass" if passing else "fail",
        "evidence": {
            "failingParityReceiptsExternalOnly": external_only,
            "missingFamilyIds": [],
            "nonReadyFamilyIds": [] if passing else ["family:a"],
        },
    }


def _sr6_payload(*, passing: bool = True, external_only: bool = False) -> dict:
    return {
        "status": "pass" if passing else "fail",
        "evidence": {
            "failingParityReceiptsExternalOnly": external_only,
            "missingFamilyIds": [],
            "nonReadyFamilyIds": [] if passing else ["family:b"],
        },
    }


def _frontier_payload(*, sr4: str = "pass", sr6: str = "pass") -> dict:
    return {"status": "pass", "evidence": {"sr4Status": sr4, "sr6Status": sr6}}


def _fixture_tree(
    tmp_path: Path,
    *,
    sr4_plane_status: str = "ready",
    sr6_plane_status: str = "ready",
    sr4_direct_pass: bool = True,
    sr6_direct_pass: bool = True,
    include_sr6_plane_contract: bool = True,
) -> dict[str, Path]:
    registry = tmp_path / "registry.yaml"
    fleet_queue = tmp_path / "fleet-queue.yaml"
    design_queue = tmp_path / "design-queue.yaml"
    guide = tmp_path / "guide.md"
    planes = tmp_path / "planes.yaml"
    bar = tmp_path / "bar.md"
    flagship = tmp_path / "flagship.json"
    sr4 = tmp_path / "sr4.json"
    sr6 = tmp_path / "sr6.json"
    frontier = tmp_path / "frontier.json"
    _write_yaml(registry, _registry())
    _write_yaml(fleet_queue, {"items": [_queue_item()]})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(guide, _guide())
    planes_payload = _planes()
    if not include_sr6_plane_contract:
        planes_payload["planes"] = [row for row in planes_payload["planes"] if row.get("id") != "sr6_parity_ready"]
    _write_yaml(planes, planes_payload)
    _write_text(bar, _bar())
    _write_json(flagship, _flagship_payload(sr4_status=sr4_plane_status, sr6_status=sr6_plane_status))
    _write_json(sr4, _sr4_payload(passing=sr4_direct_pass))
    _write_json(sr6, _sr6_payload(passing=sr6_direct_pass))
    _write_json(frontier, _frontier_payload(sr4="pass" if sr4_direct_pass else "fail", sr6="pass" if sr6_direct_pass else "fail"))
    return {
        "registry": registry,
        "fleet_queue": fleet_queue,
        "design_queue": design_queue,
        "guide": guide,
        "planes": planes,
        "bar": bar,
        "flagship": flagship,
        "sr4": sr4,
        "sr6": sr6,
        "frontier": frontier,
    }


class MaterializeNext90M136FleetSr4Sr6ReadinessCloseoutTest(unittest.TestCase):
    def _run_materializer(self, fixture: dict[str, Path], artifact: Path, markdown: Path) -> dict:
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--output",
                str(artifact),
                "--markdown-output",
                str(markdown),
                "--successor-registry",
                str(fixture["registry"]),
                "--fleet-queue-staging",
                str(fixture["fleet_queue"]),
                "--design-queue-staging",
                str(fixture["design_queue"]),
                "--next90-guide",
                str(fixture["guide"]),
                "--flagship-readiness-planes",
                str(fixture["planes"]),
                "--flagship-product-bar",
                str(fixture["bar"]),
                "--flagship-product-readiness",
                str(fixture["flagship"]),
                "--sr4-workflow-parity",
                str(fixture["sr4"]),
                "--sr6-workflow-parity",
                str(fixture["sr6"]),
                "--sr4-sr6-frontier",
                str(fixture["frontier"]),
            ],
            check=True,
        )
        return json.loads(artifact.read_text(encoding="utf-8"))

    def test_materializer_passes_with_explicit_direct_proofs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            payload = self._run_materializer(fixture, tmp_path / "artifact.json", tmp_path / "artifact.md")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["closeout_status"], "pass")
        self.assertTrue(payload["monitor_summary"]["sr4_ready"])
        self.assertTrue(payload["monitor_summary"]["sr6_ready"])

    def test_materializer_blocks_when_plane_inherits_without_direct_sr6_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, sr6_plane_status="ready", sr6_direct_pass=False)
            payload = self._run_materializer(fixture, tmp_path / "artifact.json", tmp_path / "artifact.md")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["closeout_status"], "blocked")
        self.assertTrue(any("sr6_parity_ready ready-state drifted" in issue for issue in payload["monitor_summary"]["runtime_blockers"]))

    def test_materializer_blocks_missing_sr6_contract_plane(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, include_sr6_plane_contract=False)
            payload = self._run_materializer(fixture, tmp_path / "artifact.json", tmp_path / "artifact.md")
        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(any("sr6_parity_ready" in issue for issue in payload["canonical_monitors"]["flagship_readiness_planes"]["issues"]))
