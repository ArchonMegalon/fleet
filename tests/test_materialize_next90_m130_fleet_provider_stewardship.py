from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m130_fleet_provider_stewardship.py")


def _load_materializer_module():
    spec = importlib.util.spec_from_file_location("fleet_m130_materializer", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_generated_queue_overlay(path: Path, item: dict) -> None:
    payload = yaml.safe_dump({"items": [item]}, sort_keys=False)
    _write_text(path, "- title: overlay legacy row\nmode: append\n" + payload)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _base_registry() -> dict:
    return {
        "milestones": [
            {
                "id": 130,
                "title": "External tools, LTD provider stewardship, and governed integration adapter completion",
                "status": "not_started",
                "dependencies": [106, 107, 114, 125],
                "work_tasks": [
                    {
                        "id": "130.2",
                        "owner": "fleet",
                        "title": "Add provider-health, credit-runway, kill-switch, fallback, and route-stewardship monitors for all governed external tools.",
                    }
                ],
            }
        ]
    }


def _queue_item() -> dict:
    return {
        "title": "Add provider-health, credit-runway, kill-switch, fallback, and route-stewardship monitors for all governed external tools.",
        "task": "Add provider-health, credit-runway, kill-switch, fallback, and route-stewardship monitors for all governed external tools.",
        "package_id": "next90-m130-fleet-add-provider-health-credit-runway-kill-switch-fallback-a",
        "milestone_id": 130,
        "work_task_id": "130.2",
        "status": "not_started",
        "wave": "W19",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["add_provider_health_credit_runway:fleet"],
    }


def _external_tools_plane_text() -> str:
    return """# External tools plane

## Tool inventory posture

Current known external-tool inventory includes:

* 1min.AI
* BrowserAct
* ClickRank
* ProductLift
* Signitic

## Classification model

### Rule 4 - kill switch required

### Rule 5a - public concierge widget exception

* the widget has a graceful first-party fallback path

## Activation verification rule

* the kill switch exists
* fallback behavior exists

## Release-gate rule
"""


def _ltd_capability_map_text() -> str:
    return """# LTD capability map

## Promoted

* `1min.AI` - low-cost governed reasoning fallback in `chummer6-hub`
* `BrowserAct` - no-API automation fallback, account verification, capture, and ops bridge
* `ClickRank` - public site visibility, crawl-health, technical SEO, schema, metadata, and AI-search audit lane
* `ProductLift` - public feedback, voting, roadmap projection, changelog projection, and voter closeout lane
* `Signitic` - passive outreach and signature-campaign projection lane
* `NextStep` - operator process execution and governed checklist lane

## Bounded

* `FacePop` - bounded public trust / concierge widget and moderated testimonial capture lane

## Research / Parked

* `ChatPlayground AI` - provider comparison and evaluation lab only

## Non-product

* `FastestVPN PRO`

## Bounded owner assignments

* `ProductLift` - `chummer6-hub` for public routes and fallback behavior, `chummer6-design` for taxonomy and truth boundaries, `fleet` for digest and closeout evidence synthesis
* `ClickRank` - `chummer6-hub` for public site crawl and metadata remediation, `chummer6-design` for search-visibility policy and source-truth boundaries, `executive-assistant` for findings normalization, `fleet` for weekly pulse evidence synthesis
* `NextStep` - `fleet` for governed process execution and mirrored operator runbooks
* `Signitic` - `chummer6-hub` for destination shaping, segment routing, UTM naming, and public recruitment/release/world-tick campaign routing; `chummer6-design` for public-safe claim boundaries; `fleet` for bounded measurement review
"""


def _provider_route_stewardship_text() -> str:
    return """# Provider and route stewardship

### 1. Weekly provider scan

### 2. Lane-specific benchmark run

### 3. Canary before default

* rollback target

### 4. Publish the reason

* fallback and rollback hygiene
* No provider or model swap may bypass adapters, receipts, or kill switches.
"""


def _weekly_governor_packet() -> dict:
    return {
        "generated_at": "2026-05-05T10:00:00Z",
        "decision_board": {
            "current_launch_action": "freeze_launch",
            "current_launch_reason": "Hold until provider canary returns green.",
            "canary": {"state": "accumulating", "reason": "Canary evidence is still accumulating"},
            "freeze_launch": {"state": "active", "reason": "Waiting on provider canary"},
            "rollback": {"state": "armed", "reason": "Rollback stays armed from support truth"},
        },
        "decision_gate_ledger": {
            "canary": [
                {
                    "name": "provider_canary",
                    "observed": "Canary evidence is still accumulating",
                    "required": "Canary green on all active lanes",
                    "state": "accumulating",
                }
            ]
        },
    }


def _admin_status() -> dict:
    return {
        "generated_at": "2026-05-05T10:00:00Z",
        "provider_routes": [
            {
                "lane": "review_light",
                "default_route": "browseract",
                "fallback_route": "gemini_vortex",
                "challenger_route": "chatplayground",
                "posture": "safe_today",
                "state": "ready",
                "configured_slots": 1,
                "ready_slots": 1,
                "runway": "91% allowance",
                "remaining_text": "91%",
                "review_required": False,
                "merge_review_required": False,
            },
            {
                "lane": "core",
                "default_route": "onemin",
                "fallback_route": "gemini_vortex",
                "challenger_route": "chatplayground",
                "posture": "safe_today",
                "state": "ready",
                "configured_slots": 6,
                "ready_slots": 2,
                "runway": "8h",
                "remaining_text": "5%",
                "review_required": True,
                "merge_review_required": True,
            },
        ],
        "runtime_healing": {
            "generated_at": "2026-05-05T09:59:00Z",
            "services": [
                {"service": "fleet-design-supervisor", "current_state": "healthy"},
                {"service": "fleet-controller", "current_state": "healthy"},
            ],
        },
    }


def _provider_credit() -> dict:
    return {
        "provider": "1min",
        "free_credits": 4255218,
        "max_credits": 84550000,
        "remaining_percent_total": 5.03,
        "active_lease_count": 2,
        "next_topup_at": "2026-05-05T11:36:06Z",
        "topup_amount": 15000,
        "topup_eta_source": "billing_cycle",
        "hours_until_next_topup": 0.64,
        "hours_remaining_at_current_pace_no_topup": 1.2,
        "hours_remaining_including_next_topup_at_current_pace": 1.6,
        "days_remaining_including_next_topup_at_7d_avg": 0.25,
        "depletes_before_next_topup": True,
        "basis_quality": "actual",
        "basis_summary": "actual_billing_usage_page x13",
    }


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    registry = tmp_path / "registry.yaml"
    queue = tmp_path / "queue.yaml"
    design_queue = tmp_path / "design_queue.yaml"
    external_tools = tmp_path / "EXTERNAL_TOOLS_PLANE.md"
    ltd_map = tmp_path / "LTD_CAPABILITY_MAP.md"
    stewardship = tmp_path / "PROVIDER_AND_ROUTE_STEWARDSHIP.md"
    weekly = tmp_path / "WEEKLY_GOVERNOR_PACKET.generated.json"
    admin_status = tmp_path / "admin_status.json"
    provider_credit = tmp_path / "provider_credit.json"
    artifact = tmp_path / "NEXT90_M130_FLEET_PROVIDER_STEWARDSHIP.generated.json"
    markdown = tmp_path / "NEXT90_M130_FLEET_PROVIDER_STEWARDSHIP.generated.md"

    _write_yaml(registry, _base_registry())
    _write_yaml(queue, {"items": [_queue_item()]})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(external_tools, _external_tools_plane_text())
    _write_text(ltd_map, _ltd_capability_map_text())
    _write_text(stewardship, _provider_route_stewardship_text())
    _write_json(weekly, _weekly_governor_packet())
    _write_json(admin_status, _admin_status())
    _write_json(provider_credit, _provider_credit())

    return {
        "registry": registry,
        "queue": queue,
        "design_queue": design_queue,
        "external_tools": external_tools,
        "ltd_map": ltd_map,
        "stewardship": stewardship,
        "weekly": weekly,
        "admin_status": admin_status,
        "provider_credit": provider_credit,
        "artifact": artifact,
        "markdown": markdown,
    }


def _materialize(paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
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
            "--external-tools-plane",
            str(paths["external_tools"]),
            "--ltd-capability-map",
            str(paths["ltd_map"]),
            "--provider-route-stewardship",
            str(paths["stewardship"]),
            "--weekly-governor-packet",
            str(paths["weekly"]),
            "--admin-status",
            str(paths["admin_status"]),
            "--provider-credit",
            str(paths["provider_credit"]),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class MaterializeNext90M130FleetProviderStewardshipTests(unittest.TestCase):
    def test_materialize_generates_monitor_packet(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m130-materialize-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["canonical_alignment"]["state"], "pass")
            self.assertEqual(payload["runtime_monitors"]["provider_routes"]["governed_route_count"], 2)
            self.assertEqual(
                payload["canonical_monitors"]["governed_tool_inventory"]["fleet_assigned_tools"],
                ["ClickRank", "NextStep", "ProductLift", "Signitic"],
            )
            markdown = paths["markdown"].read_text(encoding="utf-8")
            self.assertIn("Fleet M130 provider stewardship monitor", markdown)

    def test_materialize_blocks_when_provider_canary_gate_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m130-materialize-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            weekly_payload = json.loads(paths["weekly"].read_text(encoding="utf-8"))
            weekly_payload["decision_gate_ledger"]["canary"] = []
            _write_json(paths["weekly"], weekly_payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "blocked")
            blockers = payload["package_closeout"]["blockers"]
            self.assertTrue(any("provider_canary gate" in blocker for blocker in blockers))

    def test_live_loader_falls_back_to_container_cache_mode(self) -> None:
        module = _load_materializer_module()
        expected_admin_status = {"generated_at": "2026-05-05T12:00:00Z", "provider_routes": [{"lane": "core"}]}
        expected_provider_credit = {"provider": "1min", "basis_quality": "estimated"}
        completed = subprocess.CompletedProcess(
            args=["docker", "exec"],
            returncode=0,
            stdout=json.dumps(
                {
                    "admin_status": expected_admin_status,
                    "provider_credit": expected_provider_credit,
                }
            ),
            stderr="",
        )

        with mock.patch.object(module, "_load_admin_module", side_effect=RuntimeError("db unavailable")):
            with mock.patch.object(module.subprocess, "run", return_value=completed) as run_mock:
                admin_status, provider_credit = module._load_live_admin_inputs()

        self.assertEqual(admin_status, expected_admin_status)
        self.assertEqual(provider_credit, expected_provider_credit)
        run_mock.assert_called_once()

    def test_materialize_reads_generated_queue_overlay_shape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m130-materialize-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            _write_generated_queue_overlay(paths["queue"], _queue_item())
            _write_generated_queue_overlay(paths["design_queue"], _queue_item())

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["canonical_alignment"]["state"], "pass")
            self.assertFalse(any("Fleet queue row is missing." in blocker for blocker in payload["package_closeout"]["blockers"]))
            self.assertFalse(any("Design queue row is missing." in blocker for blocker in payload["package_closeout"]["blockers"]))


if __name__ == "__main__":
    unittest.main()
