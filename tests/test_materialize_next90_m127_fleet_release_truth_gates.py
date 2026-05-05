from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m127_fleet_release_truth_gates.py")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_generated_queue_overlay(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nitems:\n" + yaml.safe_dump([item], sort_keys=False), encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _registry() -> dict:
    return {
        "program_wave": "next_90_day_product_advance",
        "milestones": [
            {
                "id": 127,
                "title": "Release pipeline, updater, platform acceptance, and public downloads completion",
                "wave": "W18",
                "status": "not_started",
                "owners": ["fleet", "chummer6-ui"],
                "dependencies": [101, 102, 120],
                "work_tasks": [
                    {
                        "id": "127.4",
                        "owner": "fleet",
                        "title": "Promote platform acceptance, release evidence packs, repo hardening, and external-host proof orchestration into repeatable gates.",
                        "status": "not_started",
                    }
                ],
            }
        ],
    }


def _queue_item() -> dict:
    return {
        "title": "Promote platform acceptance, release evidence packs, repo hardening, and external-host proof orchestration into repeatable gates.",
        "task": "Promote platform acceptance, release evidence packs, repo hardening, and external-host proof orchestration into repeatable gates.",
        "package_id": "next90-m127-fleet-promote-platform-acceptance-release-evidence-packs-repo",
        "milestone_id": 127,
        "work_task_id": "127.4",
        "frontier_id": 6924107419,
        "status": "not_started",
        "wave": "W18",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["promote_platform_acceptance_release_evidence:fleet"],
    }


def _guide() -> str:
    return """# Next 90 day product advance guide

## Wave 18 - finish release operations, localization, privacy, and support trust

### 127. Release pipeline, updater, platform acceptance, and public downloads completion

Exit: release, installer, updater, rollback, revoke, download, proof shelf, platform acceptance, and public channel surfaces compile from one release-truth chain.
"""


def _acceptance_matrix() -> dict:
    return {
        "product": "chummer",
        "platforms": [
            {
                "id": "windows",
                "public_shelf_status": "promoted_preview",
                "primary_package_kind": "installer",
                "startup_smoke_gate": "required",
                "signing_posture": "required_for_promoted_release",
                "updater_mode": "in_app_apply_helper",
                "supportability": "primary",
            },
            {
                "id": "linux",
                "public_shelf_status": "preview_support_directed",
                "primary_package_kind": "deb",
                "startup_smoke_gate": "required",
                "signing_posture": "package_integrity_required",
                "updater_mode": "in_app_or_installer_handoff",
                "supportability": "secondary",
            },
            {
                "id": "macOS",
                "public_shelf_status": "account_gated_setup_script_preview",
                "primary_package_kind": "setup_script",
                "startup_smoke_gate": "required",
                "signing_posture": "codesign_and_notarization_required",
                "updater_mode": "claimed_setup_script_then_dmg_handoff",
                "supportability": "preview",
            },
        ],
    }


def _downloads_policy() -> str:
    return """# Public downloads policy

The downloads surface is a proof shelf first:

`chummer.run` is the only official client download source.

label secondary heads, archives, and manual packages as fallback or recovery paths
"""


def _auto_update_policy() -> str:
    return """# Public auto-update policy

Public copy may promise:

`paused rollout`

Registry owns promoted desktop head and update-feed truth.

The phrase `fixed` is user-safe only when the fix is actually available on that user's channel according to registry truth.
"""


def _repo_hardening_checklist() -> dict:
    return {
        "initiatives": [
            {"id": "RH-001", "title": "Fleet hygiene and secret scrub", "status": "proposed", "owners": ["fleet", "chummer6-design"]},
            {"id": "RH-002", "title": "Signed release-manifest chain", "status": "proposed", "owners": ["fleet", "chummer6-ui"]},
            {"id": "RH-003", "title": "Fleet blast-radius limits", "status": "proposed", "owners": ["fleet", "chummer6-design"]},
            {"id": "RH-005", "title": "Workflow and action hardening", "status": "proposed", "owners": ["fleet", "chummer6-core"]},
            {"id": "RH-006", "title": "Chummer boring-user-loop proof", "status": "proposed", "owners": ["fleet", "chummer6-ui"]},
        ]
    }


def _repo_hygiene_policy() -> str:
    return """# Repo hygiene, release trust, and automation safety

Golden user loops outrank feature sprawl.

### 2. One signed release-manifest chain

### 4. GitHub Actions and workflow hardening

### 7. Fleet blast-radius limits
"""


def _runbook(*, unresolved_request_count: int) -> str:
    return f"""# External Proof Runbook

- generated_at: 2026-05-05T12:00:59Z
- unresolved_request_count: {unresolved_request_count}
- capture_deadline_utc: 2026-05-06T09:59:16Z
- command_bundle_sha256: `abc123`

## Retained Host Lanes

### Host: linux

### Host: macos

### Host: windows

No unresolved external-proof requests are currently queued.
"""


def _flagship_readiness(*, external_status: str, unresolved_request_count: int) -> dict:
    return {
        "generated_at": "2026-05-05T12:45:03Z",
        "status": "pass" if external_status == "pass" and unresolved_request_count == 0 else "blocked",
        "scoped_status": "pass" if external_status == "pass" and unresolved_request_count == 0 else "blocked",
        "warning_keys": [],
        "external_host_proof": {
            "status": external_status,
            "unresolved_request_count": unresolved_request_count,
            "runbook_generated_at": "2026-05-05T12:00:59Z",
            "command_bundle_sha256": "abc123",
            "runbook_synced": True,
        },
    }


def _fixture_tree(tmp_path: Path, *, unresolved_request_count: int, external_status: str) -> dict[str, Path]:
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    guide = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
    acceptance = tmp_path / "DESKTOP_PLATFORM_ACCEPTANCE_MATRIX.yaml"
    downloads = tmp_path / "PUBLIC_DOWNLOADS_POLICY.md"
    auto_update = tmp_path / "PUBLIC_AUTO_UPDATE_POLICY.md"
    hardening = tmp_path / "REPO_HARDENING_CHECKLIST.yaml"
    hygiene = tmp_path / "REPO_HYGIENE_RELEASE_TRUST_AND_AUTOMATION_SAFETY.md"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    readiness = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    artifact = tmp_path / "NEXT90_M127_FLEET_RELEASE_TRUTH_GATES.generated.json"
    markdown = tmp_path / "NEXT90_M127_FLEET_RELEASE_TRUTH_GATES.generated.md"

    _write_yaml(registry, _registry())
    _write_yaml(queue, {"items": [_queue_item()]})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(guide, _guide())
    _write_yaml(acceptance, _acceptance_matrix())
    _write_text(downloads, _downloads_policy())
    _write_text(auto_update, _auto_update_policy())
    _write_yaml(hardening, _repo_hardening_checklist())
    _write_text(hygiene, _repo_hygiene_policy())
    _write_text(runbook, _runbook(unresolved_request_count=unresolved_request_count))
    _write_json(readiness, _flagship_readiness(external_status=external_status, unresolved_request_count=unresolved_request_count))

    return {
        "registry": registry,
        "queue": queue,
        "design_queue": design_queue,
        "guide": guide,
        "acceptance": acceptance,
        "downloads": downloads,
        "auto_update": auto_update,
        "hardening": hardening,
        "hygiene": hygiene,
        "runbook": runbook,
        "readiness": readiness,
        "artifact": artifact,
        "markdown": markdown,
    }


def _run_materializer(paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output",
            str(paths["artifact"]),
            "--markdown-output",
            str(paths["markdown"]),
            "--successor-registry",
            str(paths["registry"]),
            "--queue-staging",
            str(paths["queue"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--next90-guide",
            str(paths["guide"]),
            "--acceptance-matrix",
            str(paths["acceptance"]),
            "--public-downloads-policy",
            str(paths["downloads"]),
            "--public-auto-update-policy",
            str(paths["auto_update"]),
            "--repo-hardening-checklist",
            str(paths["hardening"]),
            "--repo-hygiene-policy",
            str(paths["hygiene"]),
            "--external-proof-runbook",
            str(paths["runbook"]),
            "--flagship-product-readiness",
            str(paths["readiness"]),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class MaterializeNext90M127FleetReleaseTruthGatesTests(unittest.TestCase):
    def test_materialize_passes_with_warning_only_release_posture(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m127-materialize-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), unresolved_request_count=0, external_status="pass")
            result = _run_materializer(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["runtime_monitors"]["external_proof_runbook"]["unresolved_request_count"], 0)
            self.assertTrue(payload["package_closeout"]["warnings"])
            self.assertEqual(payload["canonical_monitors"]["acceptance_matrix"]["state"], "pass")
            self.assertIn("linux", payload["gate_summary"]["platforms"])
            self.assertEqual(payload["gate_summary"]["release_gate_status"], "pass")

    def test_materialize_blocks_when_external_proof_or_readiness_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m127-materialize-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), unresolved_request_count=1, external_status="blocked")
            result = _run_materializer(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["gate_summary"]["release_gate_status"], "blocked")
            warnings = "\n".join(payload["package_closeout"]["warnings"])
            self.assertIn("External proof runbook unresolved_request_count is not zero.", warnings)
            self.assertIn("Flagship readiness external_host_proof.status is blocked", warnings)

    def test_materialize_accepts_generated_queue_overlay_shape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m127-materialize-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), unresolved_request_count=0, external_status="pass")
            queue_item = _queue_item()
            _write_generated_queue_overlay(paths["queue"], queue_item)
            _write_generated_queue_overlay(paths["design_queue"], queue_item)
            result = _run_materializer(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["canonical_alignment"]["state"], "pass")
            self.assertFalse(payload["package_closeout"]["blockers"])


if __name__ == "__main__":
    unittest.main()
