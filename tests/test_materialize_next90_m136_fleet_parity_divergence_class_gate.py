from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m136_fleet_parity_divergence_class_gate.py")
PACKAGE_ID = "next90-m136-fleet-fail-parity-closeout-when-remaining-deltas-are-not-classified-as-must"
QUEUE_TITLE = "Fail parity closeout when remaining deltas are not classified as must-match, may-improve, or may-remove-if-non-degrading in the audit artifacts."


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
    return {"milestones": [{"id": 136, "work_tasks": [{"id": "136.16", "owner": "fleet", "title": QUEUE_TITLE}]}]}


def _queue_item() -> dict:
    return {
        "title": QUEUE_TITLE,
        "task": QUEUE_TITLE,
        "package_id": PACKAGE_ID,
        "work_task_id": "136.16",
        "frontier_id": 2977536653,
        "milestone_id": 136,
        "status": "not_started",
        "wave": "W23",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["fail_parity_closeout_when_remaining_deltas_are_not_class:fleet"],
    }


def _guide() -> str:
    return """## Wave 23 - close calm-under-pressure payoff and veteran continuity

### 136. Calm-under-pressure payoff, veteran-depth parity, and campaign continuity closure
"""


def _bar() -> str:
    return """Release proof must also classify intentional divergence explicitly:

* `must_match`
* `may_improve`
* `may_remove_if_non_degrading`
"""


def _spec() -> str:
    return """Allowed modernization maps to the divergence class `may_improve`.
If a surface trips any of these conditions, it is a `must_match` failure until the replacement route proves equal or better directness, speed, and trust.
This is the divergence class `may_remove_if_non_degrading`.
"""


def _planes(*, include_divergence_classes: bool = True) -> dict:
    policy = {}
    if include_divergence_classes:
        policy["divergence_classes"] = [
            {"id": "must_match", "meaning": "default"},
            {"id": "may_improve", "meaning": "modernization"},
            {"id": "may_remove_if_non_degrading", "meaning": "extra"},
        ]
    return {"policy": policy}


def _release_acceptance(*, include_rule: bool = True) -> dict:
    rules = []
    if include_rule:
        rules.append(
            "Parity doctrine must classify remaining differences as `must_match`, `may_improve`, or `may_remove_if_non_degrading`; unclassified drift does not count as flagship-ready modernization."
        )
    return {"whole_product_release_rules": rules}


def _parity_audit(*, classified: bool) -> dict:
    delta_row = {
        "id": "family:legacy_and_adjacent_import_oracles",
        "visual_parity": "no",
        "behavioral_parity": "no",
        "present_in_chummer5a": "yes",
        "removable_without_workflow_degradation": "no",
    }
    if classified:
        delta_row["divergence_class"] = "must_match"
    return {
        "generated_at": "2026-05-05T16:20:00Z",
        "elements": [
            {
                "id": "baseline:roster",
                "visual_parity": "yes",
                "behavioral_parity": "yes",
                "present_in_chummer5a": "yes",
                "removable_without_workflow_degradation": "no",
            },
            delta_row,
        ],
    }


def _fixture_tree(
    tmp_path: Path,
    *,
    include_divergence_classes: bool = True,
    include_release_rule: bool = True,
    classified: bool = True,
    include_fleet_queue_row: bool = True,
) -> dict[str, Path]:
    registry = tmp_path / "registry.yaml"
    fleet_queue = tmp_path / "fleet-queue.yaml"
    design_queue = tmp_path / "design-queue.yaml"
    guide = tmp_path / "guide.md"
    planes = tmp_path / "planes.yaml"
    bar = tmp_path / "bar.md"
    acceptance = tmp_path / "acceptance.yaml"
    spec = tmp_path / "spec.md"
    audit = tmp_path / "audit.json"
    _write_yaml(registry, _registry())
    _write_yaml(fleet_queue, {"items": [_queue_item()]} if include_fleet_queue_row else {"items": []})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(guide, _guide())
    _write_yaml(planes, _planes(include_divergence_classes=include_divergence_classes))
    _write_text(bar, _bar())
    _write_yaml(acceptance, _release_acceptance(include_rule=include_release_rule))
    _write_text(spec, _spec())
    _write_json(audit, _parity_audit(classified=classified))
    return {
        "registry": registry,
        "fleet_queue": fleet_queue,
        "design_queue": design_queue,
        "guide": guide,
        "planes": planes,
        "bar": bar,
        "acceptance": acceptance,
        "spec": spec,
        "audit": audit,
    }


class MaterializeNext90M136FleetParityDivergenceClassGateTest(unittest.TestCase):
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
                "--flagship-release-acceptance",
                str(fixture["acceptance"]),
                "--parity-spec",
                str(fixture["spec"]),
                "--parity-audit",
                str(fixture["audit"]),
            ],
            check=True,
        )
        return json.loads(artifact.read_text(encoding="utf-8"))

    def test_materializer_passes_with_classified_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, classified=True)
            payload = self._run_materializer(fixture, tmp_path / "artifact.json", tmp_path / "artifact.md")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["divergence_status"], "pass")
        self.assertEqual(payload["monitor_summary"]["unclassified_delta_count"], 0)

    def test_materializer_blocks_unclassified_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, classified=False)
            payload = self._run_materializer(fixture, tmp_path / "artifact.json", tmp_path / "artifact.md")
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["divergence_status"], "blocked")
        self.assertEqual(payload["monitor_summary"]["unclassified_delta_count"], 1)
        self.assertTrue(any("missing a machine-readable divergence class" in issue for issue in payload["monitor_summary"]["runtime_blockers"]))

    def test_materializer_blocks_missing_divergence_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, include_divergence_classes=False)
            payload = self._run_materializer(fixture, tmp_path / "artifact.json", tmp_path / "artifact.md")
        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(any("divergence_classes drifted" in issue for issue in payload["canonical_monitors"]["divergence_contract"]["issues"]))
