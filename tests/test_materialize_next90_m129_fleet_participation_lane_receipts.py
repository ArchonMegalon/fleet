from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m129_fleet_participation_lane_receipts.py")

WORK_TASKS = [
    ("129.1", "chummer6-hub", "Build reusable account, profile, group, membership, join-code, boost-code, reward-journal, and entitlement-journal flows."),
    ("129.2", "chummer6-hub-registry", "Publish entitlement-backed desktop channel, install guidance, participation receipt, and reward-publication refs."),
    ("129.3", "chummer6-ui", "Surface account, claim, entitlement, channel, participation, and recovery posture inside desktop without browser-only ritual."),
    ("129.4", "fleet", "Keep participant-lane auth lane-local while emitting signed contribution receipts and sponsor-session execution metadata."),
    ("129.5", "executive-assistant", "Compile contribution, participation, entitlement, channel, and reward followthrough packets from Hub/Fleet receipts only."),
    ("129.6", "chummer6-design", "Close public-auth, identity/channel-linking, participation, account-aware front-door, and community-ledger canon coverage."),
]


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
                "id": 129,
                "title": "Account, identity, channel linking, participation, entitlements, and community ledger completion",
                "wave": "W19",
                "status": "not_started",
                "owners": [owner for _, owner, _ in WORK_TASKS],
                "dependencies": [102, 105, 118, 125],
                "work_tasks": [
                    {
                        "id": task_id,
                        "owner": owner,
                        "title": title,
                        "status": design_status if task_id == "129.6" else "not_started",
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
                "package_id": "next90-m129-fleet-keep-participant-lane-auth-lane-local-while-emitting-sig"
                if task_id == "129.4"
                else f"fixture-{task_id}",
                "milestone_id": 129,
                "work_task_id": task_id,
                "frontier_id": 7997916353 if task_id == "129.4" else 1000000000 + int(task_id.replace(".", "")),
                "status": "not_started",
                "wave": "W19",
                "repo": owner,
                "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
                "owned_surfaces": ["keep_participant_lane_auth_lane:fleet"]
                if task_id == "129.4"
                else [f"{task_id.replace('.', '_')}:fixture"],
            }
        )
    return rows


def _next90_guide() -> str:
    return """## Wave 19 - finish account/community, provider, and public-guide substrate

### 129. Account, identity, channel linking, participation, entitlements, and community ledger completion

Exit: accounts, identities, channels, groups, memberships, sponsorship, rewards, entitlements, participation, and lane-local Fleet receipt semantics form one reusable community substrate.
"""


def _adr() -> str:
    return """`chummer6-hub` owns sponsor intent, consent, user and group truth, sponsor-session records, ledgers, and recognition policy.
`fleet` owns participant-lane provisioning, worker-host device auth, lane-local auth/cache storage, sponsored execution policy, and signed contribution receipts.
Recognition must derive from validated contribution receipts rather than raw time or auth completion.
"""


def _workflow() -> str:
    return """* lane-local auth/cache storage
* signed contribution receipt emission
13. `receipt_projected`
* sponsor-session truth
* raw Codex/OpenAI auth material stays lane-local on Fleet
"""


def _ownership() -> str:
    return """* lane-local auth/cache storage on the execution host
* sponsor-session execution metadata on participant lanes
* signed contribution receipts emitted from meaningful execution events
"""


def _fleet_project() -> str:
    return """* lane-local worker auth/cache state on the execution host
* sponsor-session execution metadata on participant lanes
* signed contribution receipts emitted back to Hub after meaningful work
"""


def _hub_project() -> str:
    return """5. Fleet receipt ingest and sponsor-session projections
Rewards must be derived from validated Fleet contribution receipts, not from merely redeeming a code or completing device auth.
* participation consent and sponsor-session status
"""


def _agent_template() -> str:
    return """those caches must stay lane-local on the execution host.
Fleet may emit signed contribution receipts and hold sponsor-session execution metadata, but Hub remains the source of truth for accounts, groups, rewards, and entitlements.
"""


def _status_plane(*, include_ea: bool) -> dict:
    project_ids = ["hub", "hub-registry", "ui", "fleet", "design"]
    if include_ea:
        project_ids.append("ea")
    return {
        "generated_at": "2026-05-05T12:00:00Z",
        "whole_product_final_claim_status": "pass",
        "projects": [{"id": project_id} for project_id in sorted(project_ids)],
    }


def _fixture_tree(tmp_path: Path, *, design_status: str, include_ea: bool, with_artifact: bool) -> dict[str, Path]:
    registry_path = tmp_path / "registry.yaml"
    queue_path = tmp_path / "queue.yaml"
    design_queue_path = tmp_path / "design_queue.yaml"
    next90_guide_path = tmp_path / "NEXT90_GUIDE.md"
    adr_path = tmp_path / "ADR.md"
    workflow_path = tmp_path / "WORKFLOW.md"
    ownership_path = tmp_path / "OWNERSHIP.md"
    fleet_project_path = tmp_path / "fleet.md"
    hub_project_path = tmp_path / "hub.md"
    agent_template_path = tmp_path / "fleet.AGENTS.template.md"
    status_plane_path = tmp_path / "STATUS_PLANE.generated.yaml"
    fleet_published_root = tmp_path / "fleet-pub"
    hub_published_root = tmp_path / "hub-pub"
    registry_published_root = tmp_path / "registry-pub"

    _write_yaml(registry_path, _registry(design_status=design_status))
    queue_payload = {"items": _queue_items()}
    _write_yaml(queue_path, queue_payload)
    _write_yaml(design_queue_path, queue_payload)
    _write_text(next90_guide_path, _next90_guide())
    _write_text(adr_path, _adr())
    _write_text(workflow_path, _workflow())
    _write_text(ownership_path, _ownership())
    _write_text(fleet_project_path, _fleet_project())
    _write_text(hub_project_path, _hub_project())
    _write_text(agent_template_path, _agent_template())
    _write_yaml(status_plane_path, _status_plane(include_ea=include_ea))
    if with_artifact:
        _write_text(
            hub_published_root / "SPONSOR_SESSION_PROOF.generated.json",
            json.dumps({"status": "pass", "summary": "receipt_projected sponsor-session contribution receipt"}),  # noqa: E501
        )
    return {
        "registry": registry_path,
        "queue": queue_path,
        "design_queue": design_queue_path,
        "next90_guide": next90_guide_path,
        "adr": adr_path,
        "workflow": workflow_path,
        "ownership": ownership_path,
        "fleet_project": fleet_project_path,
        "hub_project": hub_project_path,
        "agent_template": agent_template_path,
        "status_plane": status_plane_path,
        "fleet_published_root": fleet_published_root,
        "hub_published_root": hub_published_root,
        "registry_published_root": registry_published_root,
    }


class MaterializeNext90M129FleetParticipationLaneReceiptsTest(unittest.TestCase):
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
                "--adr",
                str(fixture["adr"]),
                "--workflow",
                str(fixture["workflow"]),
                "--ownership-matrix",
                str(fixture["ownership"]),
                "--fleet-project",
                str(fixture["fleet_project"]),
                "--hub-project",
                str(fixture["hub_project"]),
                "--fleet-agent-template",
                str(fixture["agent_template"]),
                "--status-plane",
                str(fixture["status_plane"]),
                "--fleet-published-root",
                str(fixture["fleet_published_root"]),
                "--hub-published-root",
                str(fixture["hub_published_root"]),
                "--registry-published-root",
                str(fixture["registry_published_root"]),
            ],
            check=True,
        )
        return json.loads(artifact_path.read_text(encoding="utf-8"))

    def test_runtime_blockers_do_not_block_the_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, design_status="not_started", include_ea=True, with_artifact=False)
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["participation_status"], "blocked")
        self.assertTrue(
            any("design canon task 129.6" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )
        self.assertTrue(
            any("No published sponsor-session or contribution-receipt artifact" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )

    def test_missing_canonical_marker_blocks_the_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, design_status="done", include_ea=True, with_artifact=True)
            _write_text(fixture["workflow"], "# missing markers\n")
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(any("workflow" in row for row in payload["package_closeout"]["blockers"]))

    def test_missing_status_plane_owner_is_a_runtime_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, design_status="done", include_ea=False, with_artifact=True)
            artifact = tmp_path / "artifact.json"
            payload = self._run_materializer(fixture, artifact)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["monitor_summary"]["participation_status"], "blocked")
        self.assertTrue(
            any("status plane is missing owner project row(s): ea" in row for row in payload["monitor_summary"]["runtime_blockers"])
        )


if __name__ == "__main__":
    unittest.main()
