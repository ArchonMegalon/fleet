from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m125_fleet_signal_cluster_queue.py")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_generated_queue_overlay(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nitems:\n" + yaml.safe_dump([item], sort_keys=False), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _base_registry() -> dict:
    return {
        "milestones": [
            {
                "id": 125,
                "title": "Public signal, visibility, and canon-feedback implementation loop",
                "status": "not_started",
                "dependencies": [106, 111, 120],
                "work_tasks": [
                    {
                        "id": "125.3",
                        "owner": "fleet",
                        "title": "Add signal-cluster-to-queue synthesis for repeated ProductLift, Katteb, ClickRank, support, and public-guide findings.",
                    }
                ],
            }
        ]
    }


def _queue_item() -> dict:
    return {
        "title": "Add signal-cluster-to-queue synthesis for repeated ProductLift, Katteb, ClickRank, support, and public-guide findings.",
        "task": "Add signal-cluster-to-queue synthesis for repeated ProductLift, Katteb, ClickRank, support, and public-guide findings.",
        "package_id": "next90-m125-fleet-add-signal-cluster-to-queue-synthesis-for-repeated-produ",
        "milestone_id": 125,
        "work_task_id": "125.3",
        "frontier_id": 5150581210,
        "status": "not_started",
        "wave": "W17",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["add_signal_cluster_to_queue:fleet"],
    }


def _pipeline_text() -> str:
    return """# Public signal to canon pipeline

## Core rule

ProductLift / Katteb / users

## Decision classes

## Closeout requirements

## Anti-patterns
"""


def _ooda_text() -> str:
    return """# Feedback and signal OODA loop

### Fleet clustering

### Signal packet rule

### Packet-to-action rule

## Forbidden shortcuts
"""


def _productlift_text() -> str:
    return """# ProductLift feedback, roadmap, and changelog bridge

## Weekly digest

## Support misroutes

## Closeout rule

## Status mapping
"""


def _katteb_text() -> str:
    return """# Katteb public guide optimization lane

## Required source packet

## Audit workflow

## Review rule
"""


def _clickrank_text() -> str:
    return """# Public site visibility and search optimization

## Workflow

## Weekly pulse inputs

## Blocked without upstream review
"""


def _weekly_pulse() -> dict:
    return {
        "generated_at": "2026-05-05T12:00:00Z",
        "top_support_or_feedback_clusters": [
            {
                "cluster_id": "install_help_clarity",
                "summary": "Repeated support and guide feedback says download, install, and help copy are unclear.",
                "source_paths": [
                    "products/chummer/PUBLIC_RELEASE_EXPERIENCE.yaml",
                    "products/chummer/FEEDBACK_AND_CRASH_STATUS_MODEL.md",
                ],
            }
        ],
    }


def _support_packets() -> dict:
    return {"generated_at": "2026-05-05T12:00:00Z", "packets": []}


def _signal_source() -> dict:
    return {
        "generated_at": "2026-05-05T12:01:00Z",
        "items": [
            {
                "packet_id": "pl-1",
                "source": "ProductLift",
                "source_families": ["ProductLift"],
                "signal_family": "lightweight feedback",
                "audience": "public",
                "claim_sensitivity": "public_signal",
                "owner": "fleet",
                "decision": "triage",
                "closeout_posture": "open",
                "decision_class": "docs/help fix",
                "cluster_key": "install_help_clarity",
                "summary": "Users keep asking for clearer install help and release guidance.",
                "source_refs": ["/feedback/install-help"],
                "candidate_owner_repo": "chummer6-design",
            },
            {
                "packet_id": "kat-1",
                "source": "Katteb",
                "source_families": ["Katteb", "public-guide"],
                "signal_family": "lightweight feedback",
                "audience": "public",
                "claim_sensitivity": "public_copy",
                "owner": "executive-assistant",
                "decision": "draft_patch",
                "closeout_posture": "open",
                "decision_class": "docs/help fix",
                "cluster_key": "install_help_clarity",
                "summary": "Guide intro needs clearer install and update copy.",
                "source_refs": ["guide/download-and-install"],
                "candidate_owner_repo": "chummer6-design",
            },
            {
                "packet_id": "clk-1",
                "source": "ClickRank",
                "source_families": ["ClickRank"],
                "signal_family": "public-promise drift",
                "audience": "public",
                "claim_sensitivity": "public_promise_drift",
                "owner": "executive-assistant",
                "decision": "audit",
                "closeout_posture": "open",
                "decision_class": "docs/help fix",
                "cluster_key": "install_help_clarity",
                "summary": "Search snippets overpromise install readiness and recovery coverage.",
                "source_refs": ["/downloads"],
                "candidate_owner_repo": "chummer6-design",
            },
            {
                "packet_id": "sup-1",
                "source": "support",
                "source_families": ["support"],
                "signal_family": "public issue",
                "audience": "support_reporter",
                "claim_sensitivity": "private_support",
                "owner": "chummer6-hub",
                "decision": "triage",
                "closeout_posture": "open",
                "decision_class": "support knowledge or closure fix",
                "cluster_key": "install_help_clarity",
                "summary": "Support cases repeat the same install and update confusion.",
                "source_refs": ["case-14"],
                "candidate_owner_repo": "chummer6-hub",
            },
            {
                "packet_id": "pg-1",
                "source": "public-guide",
                "source_families": ["public-guide"],
                "signal_family": "lightweight feedback",
                "audience": "public",
                "claim_sensitivity": "public_copy",
                "owner": "chummer6-design",
                "decision": "source_patch_needed",
                "closeout_posture": "open",
                "decision_class": "docs/help fix",
                "cluster_key": "install_help_clarity",
                "summary": "Public guide page still buries the recovery path.",
                "source_refs": ["guide/download-and-install"],
                "candidate_owner_repo": "chummer6-design",
            },
        ],
    }


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    registry = tmp_path / "registry.yaml"
    queue = tmp_path / "queue.yaml"
    design_queue = tmp_path / "design_queue.yaml"
    pipeline = tmp_path / "PUBLIC_SIGNAL_TO_CANON_PIPELINE.md"
    ooda = tmp_path / "FEEDBACK_AND_SIGNAL_OODA_LOOP.md"
    productlift = tmp_path / "PRODUCTLIFT_FEEDBACK_ROADMAP_BRIDGE.md"
    katteb = tmp_path / "KATTEB_PUBLIC_GUIDE_OPTIMIZATION_LANE.md"
    clickrank = tmp_path / "PUBLIC_SITE_VISIBILITY_AND_SEARCH_OPTIMIZATION.md"
    weekly = tmp_path / "WEEKLY_PRODUCT_PULSE.generated.json"
    support = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    signal_source = tmp_path / "signal_source.json"
    live_signal_source = tmp_path / "live_signal_source.generated.json"
    artifact = tmp_path / "NEXT90_M125_FLEET_SIGNAL_CLUSTER_QUEUE.generated.json"
    markdown = tmp_path / "NEXT90_M125_FLEET_SIGNAL_CLUSTER_QUEUE.generated.md"

    _write_yaml(registry, _base_registry())
    _write_yaml(queue, {"items": [_queue_item()]})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(pipeline, _pipeline_text())
    _write_text(ooda, _ooda_text())
    _write_text(productlift, _productlift_text())
    _write_text(katteb, _katteb_text())
    _write_text(clickrank, _clickrank_text())
    _write_json(weekly, _weekly_pulse())
    _write_json(support, _support_packets())
    _write_json(signal_source, _signal_source())

    return {
        "registry": registry,
        "queue": queue,
        "design_queue": design_queue,
        "pipeline": pipeline,
        "ooda": ooda,
        "productlift": productlift,
        "katteb": katteb,
        "clickrank": clickrank,
        "weekly": weekly,
        "support": support,
        "signal_source": signal_source,
        "live_signal_source": live_signal_source,
        "artifact": artifact,
        "markdown": markdown,
    }


def _materialize(paths: dict[str, Path], *, include_signal_source: bool = True) -> subprocess.CompletedProcess[str]:
    args = [
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
        "--public-signal-pipeline",
        str(paths["pipeline"]),
        "--feedback-ooda-loop",
        str(paths["ooda"]),
        "--productlift-bridge",
        str(paths["productlift"]),
        "--katteb-lane",
        str(paths["katteb"]),
        "--clickrank-lane",
        str(paths["clickrank"]),
        "--weekly-product-pulse",
        str(paths["weekly"]),
        "--support-case-packets",
        str(paths["support"]),
        "--live-signal-source-output",
        str(paths["live_signal_source"]),
    ]
    if include_signal_source:
        args.extend(["--signal-source", str(paths["signal_source"])])
    return subprocess.run(args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


class MaterializeNext90M125FleetSignalClusterQueueTests(unittest.TestCase):
    def test_materialize_generates_queue_candidate_from_clustered_signal_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m125-materialize-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["queue_synthesis"]["queue_candidate_count"], 1)
            self.assertEqual(payload["queue_synthesis"]["missing_source_families"], [])
            candidate = payload["queue_synthesis"]["queue_candidates"][0]
            self.assertEqual(candidate["proposal_state"], "proposal_only")
            self.assertEqual(candidate["repeated_signal_count"], 5)
            self.assertEqual(len(candidate["source_items"]), 5)

    def test_materialize_blocks_when_signal_packet_is_missing_required_classification(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m125-materialize-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            payload = json.loads(paths["signal_source"].read_text(encoding="utf-8"))
            payload["items"][0].pop("claim_sensitivity")
            _write_json(paths["signal_source"], payload)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            artifact = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(artifact["status"], "blocked")
            blockers = artifact["package_closeout"]["blockers"]
            self.assertTrue(any("missing required fields" in blocker for blocker in blockers))

    def test_materialize_derives_live_signal_source_snapshot_when_explicit_source_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m125-materialize-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            result = _materialize(paths, include_signal_source=False)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["queue_synthesis"]["queue_candidate_count"], 1)
            self.assertTrue(paths["live_signal_source"].exists())
            snapshot = json.loads(paths["live_signal_source"].read_text(encoding="utf-8"))
            self.assertEqual(snapshot["count"], 1)
            self.assertEqual(snapshot["items"][0]["source"], "weekly_product_pulse")

    def test_materialize_accepts_generated_queue_overlay_shape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m125-materialize-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            queue_item = _queue_item()
            _write_generated_queue_overlay(paths["queue"], queue_item)
            _write_generated_queue_overlay(paths["design_queue"], queue_item)

            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["canonical_alignment"]["state"], "pass")
            self.assertFalse(payload["package_closeout"]["blockers"])


if __name__ == "__main__":
    unittest.main()
