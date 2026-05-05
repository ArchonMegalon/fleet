from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m135_fleet_design_queued_coverage.py")

WORK_TASKS = [
    ("135.1", "chummer6-design", "Materialize a canonical design coverage ledger mapping every source family to implemented, queued, future-only, or non-goal posture."),
    ("135.2", "fleet", "Add full-design queued-coverage verification, mirror freshness checks, missing-row detection, and status-plane reporting."),
    ("135.3", "chummer6-core", "Close engine contract-set, package bootstrap, deterministic proof, interop, import/export, and rules-boundary coverage."),
    ("135.4", "chummer6-hub", "Close hosted bounded-context, campaign, account, support, public, community, and orchestration-boundary coverage."),
    ("135.5", "chummer6-hub-registry", "Close registry persistence, release-channel, artifact lineage, publication, entitlement, and compatibility-boundary coverage."),
    ("135.6", "chummer6-ui", "Close desktop workbench, Build Lab, GM Runboard, publication, restore, support, and veteran-familiarity surface coverage."),
    ("135.7", "chummer6-mobile", "Close mobile play shell, reconnect, replay, travel cache, table cards, recap, and offline/degraded-state coverage."),
    ("135.8", "chummer6-ui-kit", "Close shared design-system, accessibility, localization, dense-data, state-badge, and visual-regression package coverage."),
    ("135.9", "chummer6-media-factory", "Close media contracts, render jobs, previews, manifests, archive, provider adapters, and asset lifecycle coverage."),
    ("135.10", "executive-assistant", "Close EA compile, signal, companion, public copy, operator packet, provider digest, and followthrough coverage without canon authority."),
]
REPO_TO_PROJECT = {
    "chummer6-design": "design",
    "fleet": "fleet",
    "chummer6-core": "core",
    "chummer6-hub": "hub",
    "chummer6-hub-registry": "hub-registry",
    "chummer6-ui": "ui",
    "chummer6-mobile": "mobile",
    "chummer6-ui-kit": "ui-kit",
    "chummer6-media-factory": "media-factory",
    "executive-assistant": "ea",
}


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _registry(*, design_status: str) -> dict:
    return {
        "program_wave": "next_90_day_product_advance",
        "milestones": [
            {
                "id": 135,
                "title": "Product backbone, contract sets, ownership matrix, repo hygiene, and final design coverage closeout",
                "wave": "W22",
                "status": "not_started",
                "owners": [owner for _, owner, _ in WORK_TASKS],
                "dependencies": [127, 128, 129, 130, 131, 132, 133, 134],
                "work_tasks": [
                    {
                        "id": task_id,
                        "owner": owner,
                        "title": title,
                        "status": design_status if task_id == "135.1" else "not_started",
                    }
                    for task_id, owner, title in WORK_TASKS
                ],
            }
        ],
    }


def _queue_items() -> list[dict]:
    rows = []
    for task_id, owner, title in WORK_TASKS:
        rows.append(
            {
                "title": title,
                "task": title,
                "package_id": "next90-m135-fleet-add-full-design-queued-coverage-verification-mirror-fres"
                if task_id == "135.2"
                else f"fixture-{task_id}",
                "milestone_id": 135,
                "work_task_id": task_id,
                "frontier_id": 7361549676 if task_id == "135.2" else 1000000000 + int(task_id.replace(".", "")),
                "status": "not_started",
                "wave": "W22",
                "repo": owner,
                "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
                "owned_surfaces": ["add_full_design_queued_coverage:fleet"]
                if task_id == "135.2"
                else [f"{task_id.replace('.', '_')}:fixture"],
            }
        )
    return rows


def _next90_guide() -> str:
    return """## Wave 22 - close backbone, contract, repo-boundary, and final design coverage

### 135. Product backbone, contract sets, ownership matrix, repo hygiene, and final design coverage closeout

Exit: every canonical design source family is implemented, explicitly non-goal/future-only, or represented by a repo-owned executable milestone with queue slice, allowed paths, proof gate, and stop condition.
"""


def _sync_manifest() -> dict:
    return {
        "canonical_source_repo": "chummer6-design",
        "repo_root_aliases": {owner: [owner] for _, owner, _ in WORK_TASKS[1:]},
        "product_source_groups": {
            "base_governance": ["products/chummer/PROGRAM_MILESTONES.yaml"],
            "horizons": ["products/chummer/HORIZON_REGISTRY.yaml"],
            "public_surface": ["products/chummer/PUBLIC_LANDING_POLICY.md"],
            "release": ["products/chummer/RELEASE_PIPELINE.md"],
            "support_plane": ["products/chummer/FEEDBACK_AND_SIGNAL_OODA_LOOP.md"],
            "external_tools": ["products/chummer/EXTERNAL_TOOLS_PLANE.md"],
        },
    }


def _backlog_text(*, include_all_repos: bool) -> str:
    repos = [owner for _, owner, _ in WORK_TASKS if owner != "chummer6-design"]
    if not include_all_repos:
        repos = [repo for repo in repos if repo != "executive-assistant"]
    lines = [
        "# Local Mirror Publish Backlog",
        "",
        "| Backlog ID | Status | Target Repo | Source of Truth | Mirror Targets (code repo) | Publish Evidence |",
        "|---|---|---|---|---|---|",
    ]
    for idx, repo in enumerate(repos, start=1):
        lines.append(
            f"| WL-D008-{idx:02d} | done | {repo} | manifest | .codex-design/product | evidence |"
        )
    lines.extend(
        [
            "",
            "| Backlog ID | Status | Scope | Action |",
            "|---|---|---|---|",
            "| WL-D018-01 | queued | cycle startup | startup |",
            "| WL-D018-02 | queued | parity audit | audit |",
            "| WL-D018-03 | queued | drift republish | republish |",
            "| WL-D018-04 | queued | no-change closeout | closeout |",
            "| WL-D018-05 | queued | queue reflection | reflect |",
        ]
    )
    return "\n".join(lines) + "\n"


def _evidence_text(*, repos: list[str], source_sha: str, latest_at: str) -> str:
    lines = [
        "# Local Mirror Publish Evidence",
        "",
        f"## WL-D018 Cycle 2026-04-22A (operator: codex, final release closeout)",
        f"- WL-D018-04 `done` at `{latest_at}`: closed the cycle with explicit parity evidence.",
        "",
        "| Backlog ID | Target Repo | publish_ref | program_milestones_source_sha256 | program_milestones_target_sha256 | result |",
        "|---|---|---|---|---|---|",
    ]
    for idx, repo in enumerate(repos, start=1):
        lines.append(
            f"| WL-D008-{idx:02d} | {repo} | `ref{idx:02d}` | `{source_sha}` | `{source_sha}` | done |"
        )
    return "\n".join(lines) + "\n"


def _program_milestones(*, last_reviewed: str) -> dict:
    return {"product": "chummer", "last_reviewed": last_reviewed}


def _status_plane(*, include_ea: bool, generated_at: str) -> dict:
    project_ids = [REPO_TO_PROJECT[owner] for _, owner, _ in WORK_TASKS]
    if not include_ea:
        project_ids = [project_id for project_id in project_ids if project_id != "ea"]
    return {
        "generated_at": generated_at,
        "whole_product_final_claim_status": "pass",
        "whole_product_final_claim_ready": 1,
        "projects": [{"id": project_id} for project_id in sorted(set(project_ids))],
    }


def _fixture_tree(
    tmp_path: Path,
    *,
    design_status: str,
    include_ea_in_backlog: bool,
    include_ea_in_status_plane: bool,
    mirror_latest_at: str,
    last_reviewed: str,
    evidence_source_sha: str,
) -> dict[str, Path]:
    registry_path = tmp_path / "registry.yaml"
    queue_path = tmp_path / "queue.yaml"
    design_queue_path = tmp_path / "design_queue.yaml"
    next90_guide_path = tmp_path / "NEXT90_GUIDE.md"
    sync_manifest_path = tmp_path / "sync-manifest.yaml"
    mirror_backlog_path = tmp_path / "LOCAL_MIRROR_PUBLISH_BACKLOG.md"
    mirror_evidence_path = tmp_path / "LOCAL_MIRROR_PUBLISH_EVIDENCE.md"
    program_milestones_path = tmp_path / "PROGRAM_MILESTONES.yaml"
    status_plane_path = tmp_path / "STATUS_PLANE.generated.yaml"

    _write_yaml(registry_path, _registry(design_status=design_status))
    queue_payload = {"items": _queue_items()}
    _write_yaml(queue_path, queue_payload)
    _write_yaml(design_queue_path, queue_payload)
    _write_text(next90_guide_path, _next90_guide())
    _write_yaml(sync_manifest_path, _sync_manifest())
    _write_text(mirror_backlog_path, _backlog_text(include_all_repos=include_ea_in_backlog))
    evidence_repos = [owner for _, owner, _ in WORK_TASKS if owner != "chummer6-design"]
    if not include_ea_in_backlog:
        evidence_repos = [repo for repo in evidence_repos if repo != "executive-assistant"]
    _write_text(
        mirror_evidence_path,
        _evidence_text(repos=evidence_repos, source_sha=evidence_source_sha, latest_at=mirror_latest_at),
    )
    _write_yaml(program_milestones_path, _program_milestones(last_reviewed=last_reviewed))
    _write_yaml(status_plane_path, _status_plane(include_ea=include_ea_in_status_plane, generated_at=mirror_latest_at))
    return {
        "registry": registry_path,
        "queue": queue_path,
        "design_queue": design_queue_path,
        "next90_guide": next90_guide_path,
        "sync_manifest": sync_manifest_path,
        "mirror_backlog": mirror_backlog_path,
        "mirror_evidence": mirror_evidence_path,
        "program_milestones": program_milestones_path,
        "status_plane": status_plane_path,
    }


class MaterializeNext90M135FleetDesignQueuedCoverageTest(unittest.TestCase):
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
                "--sync-manifest",
                str(fixture["sync_manifest"]),
                "--mirror-backlog",
                str(fixture["mirror_backlog"]),
                "--mirror-evidence",
                str(fixture["mirror_evidence"]),
                "--program-milestones",
                str(fixture["program_milestones"]),
                "--status-plane",
                str(fixture["status_plane"]),
            ],
            check=True,
        )
        return json.loads(artifact_path.read_text(encoding="utf-8"))

    def test_runtime_blockers_do_not_block_the_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                design_status="not_started",
                include_ea_in_backlog=True,
                include_ea_in_status_plane=True,
                mirror_latest_at="2026-04-22T10:00:00Z",
                last_reviewed="2026-04-22",
                evidence_source_sha=yaml.safe_dump(_program_milestones(last_reviewed="2026-04-22")),
            )
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["design_coverage_status"], "blocked")
        self.assertTrue(
            any("design coverage ledger task 135.1" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )

    def test_missing_guide_marker_blocks_the_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                design_status="done",
                include_ea_in_backlog=True,
                include_ea_in_status_plane=True,
                mirror_latest_at="2026-04-22T10:00:00Z",
                last_reviewed="2026-04-22",
                evidence_source_sha="fixture-sha",
            )
            _write_text(fixture["next90_guide"], "# missing markers\n")
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(any("next90_guide" in row for row in payload["package_closeout"]["blockers"]))

    def test_stale_mirror_evidence_and_missing_status_plane_owner_are_runtime_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            current_program = _program_milestones(last_reviewed="2026-04-22")
            fixture = _fixture_tree(
                tmp_path,
                design_status="done",
                include_ea_in_backlog=False,
                include_ea_in_status_plane=False,
                mirror_latest_at="2026-03-19T10:59:51Z",
                last_reviewed="2026-04-22",
                evidence_source_sha="stale-sha",
            )
            _write_yaml(fixture["program_milestones"], current_program)
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["design_coverage_status"], "blocked")
        self.assertTrue(
            any("mirror backlog is missing repo row(s): executive-assistant" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )
        self.assertTrue(
            any("status plane is missing owner project row(s): ea" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )
        self.assertTrue(
            any("current PROGRAM_MILESTONES checksum" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )


if __name__ == "__main__":
    unittest.main()
