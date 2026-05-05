from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m131_fleet_public_guide_gates.py")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write_text(path, json.dumps(payload, indent=2) + "\n")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _registry() -> dict:
    return {
        "program_wave": "next_90_day_product_advance",
        "milestones": [
            {
                "id": 131,
                "title": "Public guide, help, FAQ, content export, media briefs, and search visibility completion",
                "wave": "W19",
                "status": "not_started",
                "owners": ["fleet", "chummer6-design"],
                "dependencies": [107, 111, 120, 125],
                "work_tasks": [
                    {
                        "id": "131.5",
                        "owner": "fleet",
                        "title": "Verify public-guide regeneration, visibility-source freshness, crawl-budget discipline, and unsupported-claim rejection gates.",
                        "status": "not_started",
                    }
                ],
            }
        ],
    }


def _queue_item() -> dict:
    return {
        "title": "Verify public-guide regeneration, visibility-source freshness, crawl-budget discipline, and unsupported-claim rejection gates.",
        "task": "Verify public-guide regeneration, visibility-source freshness, crawl-budget discipline, and unsupported-claim rejection gates.",
        "package_id": "next90-m131-fleet-verify-public-guide-regeneration-visibility-source-fresh",
        "milestone_id": 131,
        "work_task_id": "131.5",
        "frontier_id": 5694544514,
        "status": "not_started",
        "wave": "W19",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["verify_public_guide_regeneration_visibility:fleet"],
    }


def _next90_guide() -> str:
    return """# Next 90 day product advance guide

## Wave 19 - finish account/community, provider, and public-guide substrate

### 131. Public guide, help, FAQ, content export, media briefs, and search visibility completion

Exit: guide, help, FAQ, public parts, media briefs, metadata, schema, sitemap, visibility, and content-export outputs compile from Chummer-owned source truth before public output changes.
"""


def _growth_stack() -> str:
    return """# Public Growth and Visibility Stack

ClickRank audit
  -> Hub or public-guide source patch

None of those tools may own:

- release truth

no public claim outruns Chummer-owned release evidence
"""


def _guide_export_manifest() -> str:
    return """rules:
- The root `products/chummer/HORIZON_REGISTRY.yaml` is the authority for horizon eligibility; derived indexes must not widen it.
- ProductLift-backed `/feedback`, `/roadmap`, and `/changelog` pages are public projections only; they must keep first-party fallback paths and may not become support, release, or roadmap truth.
- accepted suggestions must return to Chummer-owned source before generated guide output changes.
- accepted recommendations must return to Chummer-owned source before generated guide or public site output changes.
"""


def _guide_policy() -> str:
    return """# Public guide policy

`Chummer6` must stay subordinate to `PUBLIC_LANDING_POLICY.md`
`Chummer6` must not invent a public feature map that contradicts `PUBLIC_LANDING_MANIFEST.yaml` or `PUBLIC_FEATURE_REGISTRY.yaml`.
The root `products/chummer/HORIZON_REGISTRY.yaml` is the only source of truth for horizon existence, order, and public-guide eligibility.
accepted changes still land upstream in Chummer-owned source before publication.
"""


def _visibility_policy() -> str:
    return """# Public site visibility and search optimization

Accepted changes must be patched upstream into Chummer-owned source, then regenerated or republished.
Treat the crawled-page capacity as a scarce public-launch budget.
Do not crawl every generated path, archive page, machine output, internal proof page, or low-value duplicate.
public claims that contradict release evidence
"""


def _signal_pipeline() -> str:
    return """# Public signal to canon pipeline

Public signal is input. Canon is decided by Chummer.
upstream canonical source edit
unsupported claims are rejected or removed
generated guide or public page is regenerated from Chummer-owned source
"""


def _katteb_lane() -> str:
    return """# Katteb public guide optimization lane

accepted changes must flow upstream into `chummer6-design` or a Chummer-owned public-guide source registry before the guide is regenerated.
The generated public guide must never be hand-edited to accept Katteb output.
No Katteb output may publish without human review and Product Governor or delegated content-owner approval.
Claims that unshipped features are available.
"""


def _guide_verify_stub(path: Path, *, success: bool) -> None:
    if success:
        text = """#!/usr/bin/env python3
print('guide surface verified: parts=5 horizons=9 updates=4')
"""
    else:
        text = """#!/usr/bin/env python3
import sys
print('RuntimeError: UPDATES/README.md is missing required change-log section: Latest substantial pushes', file=sys.stderr)
raise SystemExit(1)
"""
    _write_text(path, text)


def _flagship_queue_stub(path: Path, *, guide_root: Path, status: str, findings: list[str], burn_allowed: bool) -> None:
    payload = {
        "status": status,
        "findings": findings,
        "queue_task_count": 1 if findings else 0,
        "tasks": ["Refresh the Chummer6 guide from approved source truth."] if findings else [],
        "guide_root": str(guide_root),
        "onemin_total_remaining_credits": 4321,
        "onemin_credit_floor": 150000000,
        "onemin_credit_burn_allowed": burn_allowed,
    }
    text = f"""#!/usr/bin/env python3
print({json.dumps(payload)!r})
"""
    _write_text(path, text)


def _init_git_repo(path: Path, *, committed_at: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _write_text(path / "README.md", "# Guide\n")
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = committed_at
    env["GIT_COMMITTER_DATE"] = committed_at
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True, env=env)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "codex@example.com"], check=True, env=env)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Codex"], check=True, env=env)
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True, env=env)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "init"], check=True, env=env)


def _fixture_tree(
    tmp_path: Path,
    *,
    guide_verify_success: bool,
    flagship_status: str,
    flagship_findings: list[str],
    burn_allowed: bool,
) -> dict[str, Path]:
    registry_path = tmp_path / "registry.yaml"
    queue_path = tmp_path / "queue.yaml"
    design_queue_path = tmp_path / "design_queue.yaml"
    next90_guide_path = tmp_path / "NEXT90_GUIDE.md"
    growth_stack_path = tmp_path / "PUBLIC_GROWTH.md"
    export_manifest_path = tmp_path / "PUBLIC_GUIDE_EXPORT_MANIFEST.yaml"
    guide_policy_path = tmp_path / "PUBLIC_GUIDE_POLICY.md"
    visibility_policy_path = tmp_path / "PUBLIC_VISIBILITY_POLICY.md"
    signal_pipeline_path = tmp_path / "PUBLIC_SIGNAL_PIPELINE.md"
    katteb_lane_path = tmp_path / "KATTEB_LANE.md"
    guide_verify_script = tmp_path / "verify_guide_stub.py"
    flagship_queue_script = tmp_path / "flagship_queue_stub.py"
    guide_repo_root = tmp_path / "Chummer6"

    _write_yaml(registry_path, _registry())
    _write_yaml(queue_path, {"items": [_queue_item()]})
    _write_yaml(design_queue_path, {"items": [_queue_item()]})
    _write_text(next90_guide_path, _next90_guide())
    _write_text(growth_stack_path, _growth_stack())
    _write_text(export_manifest_path, _guide_export_manifest())
    _write_text(guide_policy_path, _guide_policy())
    _write_text(visibility_policy_path, _visibility_policy())
    _write_text(signal_pipeline_path, _signal_pipeline())
    _write_text(katteb_lane_path, _katteb_lane())
    _guide_verify_stub(guide_verify_script, success=guide_verify_success)
    _init_git_repo(guide_repo_root, committed_at="2026-05-05T10:00:00+00:00")
    _flagship_queue_stub(
        flagship_queue_script,
        guide_root=guide_repo_root,
        status=flagship_status,
        findings=flagship_findings,
        burn_allowed=burn_allowed,
    )
    return {
        "registry": registry_path,
        "queue": queue_path,
        "design_queue": design_queue_path,
        "next90_guide": next90_guide_path,
        "growth_stack": growth_stack_path,
        "export_manifest": export_manifest_path,
        "guide_policy": guide_policy_path,
        "visibility_policy": visibility_policy_path,
        "signal_pipeline": signal_pipeline_path,
        "katteb_lane": katteb_lane_path,
        "guide_verify_script": guide_verify_script,
        "flagship_queue_script": flagship_queue_script,
        "guide_repo_root": guide_repo_root,
    }


class MaterializeNext90M131FleetPublicGuideGatesTest(unittest.TestCase):
    def _run_materializer(self, fixture: dict[str, Path], artifact_path: Path) -> dict:
        markdown_path = artifact_path.with_suffix(".md")
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--output",
                str(artifact_path),
                "--markdown-output",
                str(markdown_path),
                "--successor-registry",
                str(fixture["registry"]),
                "--queue-staging",
                str(fixture["queue"]),
                "--design-queue-staging",
                str(fixture["design_queue"]),
                "--next90-guide",
                str(fixture["next90_guide"]),
                "--growth-stack",
                str(fixture["growth_stack"]),
                "--guide-export-manifest",
                str(fixture["export_manifest"]),
                "--guide-policy",
                str(fixture["guide_policy"]),
                "--visibility-policy",
                str(fixture["visibility_policy"]),
                "--signal-pipeline",
                str(fixture["signal_pipeline"]),
                "--katteb-lane",
                str(fixture["katteb_lane"]),
                "--guide-verify-script",
                str(fixture["guide_verify_script"]),
                "--flagship-queue-script",
                str(fixture["flagship_queue_script"]),
                "--guide-repo-root",
                str(fixture["guide_repo_root"]),
            ],
            check=True,
        )
        return json.loads(artifact_path.read_text(encoding="utf-8"))

    def test_runtime_gate_failures_do_not_block_the_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                guide_verify_success=False,
                flagship_status="fail",
                flagship_findings=["story_cast_signature:assets/hero/chummer6-hero.png:solo"],
                burn_allowed=False,
            )
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["public_guide_gate_status"], "blocked")
        self.assertEqual(payload["runtime_monitors"]["guide_surface_gate"]["gate_status"], "blocked")
        self.assertEqual(payload["runtime_monitors"]["flagship_queue_gate"]["flagship_queue_status"], "fail")
        self.assertEqual(payload["runtime_monitors"]["guide_repo_freshness"]["gate_status"], "pass")
        self.assertTrue(
            any("story_cast_signature" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )
        self.assertTrue(
            any("cannot burn 1min credits" in row for row in payload["package_closeout"]["warnings"])
        )

    def test_missing_canonical_marker_blocks_the_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                guide_verify_success=True,
                flagship_status="pass",
                flagship_findings=[],
                burn_allowed=True,
            )
            _write_text(fixture["visibility_policy"], "# missing marker\n")
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(
            any("visibility_policy" in row for row in payload["package_closeout"]["blockers"])
        )


if __name__ == "__main__":
    unittest.main()
