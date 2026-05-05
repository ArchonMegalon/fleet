from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m128_fleet_trust_plane_monitors.py")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_generated_queue_overlay(path: Path, item: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nitems:\n" + yaml.safe_dump([item], sort_keys=False), encoding="utf-8")


def _registry() -> dict:
    return {
        "program_wave": "next_90_day_product_advance",
        "milestones": [
            {
                "id": 128,
                "title": "Localization, accessibility, telemetry, privacy, support, and crash trust completion",
                "wave": "W18",
                "status": "not_started",
                "owners": ["fleet", "chummer6-ui"],
                "dependencies": [105, 106, 111, 121, 124],
                "work_tasks": [
                    {
                        "id": "128.5",
                        "owner": "fleet",
                        "title": "Add freshness and contradiction monitors for telemetry, privacy, retention, localization, support, and crash proof planes.",
                        "status": "not_started",
                    }
                ],
            }
        ],
    }


def _queue_item() -> dict:
    return {
        "title": "Add freshness and contradiction monitors for telemetry, privacy, retention, localization, support, and crash proof planes.",
        "task": "Add freshness and contradiction monitors for telemetry, privacy, retention, localization, support, and crash proof planes.",
        "package_id": "next90-m128-fleet-add-freshness-and-contradiction-monitors-for-telemetry-p",
        "milestone_id": 128,
        "work_task_id": "128.5",
        "frontier_id": 6911125913,
        "status": "not_started",
        "wave": "W18",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["add_freshness_and_contradiction_monitors:fleet"],
    }


def _guide() -> str:
    return """# Next 90 day product advance guide

## Wave 18 - finish release operations, localization, privacy, and support trust

### 128. Localization, accessibility, telemetry, privacy, support, and crash trust completion

Exit: promoted desktop, mobile, Hub, public, support, and artifact surfaces satisfy localization, accessibility, dense-data, telemetry, privacy, retention, support, and crash-status contracts.

Telemetry and support signals are privacy-bounded, install-aware, user-visible where appropriate, and useful to product-governor decisions without becoming surveillance or support folklore.

Crash, feedback, fix-available, please-test, recovery, reporter followthrough, and public trust surfaces agree on retention clocks and release/support truth.
"""


def _localization() -> str:
    return """# Localization and language system

## Shipping locale set

* `en-US`
* `de-DE`
* `fr-FR`
* `ja-JP`
* `pt-BR`
* `zh-CN`

## Runtime behavior

changing language requires restart

deterministic fallback

## Support-critical scope

The following surfaces are first-class localization scope from day one of the desktop wave:
"""


def _telemetry_model() -> str:
    return """# Product usage telemetry model

Chummer should treat product-improvement telemetry as opt-out, not opt-in.

### Tier 2: pseudonymous hosted product telemetry

after a crash, the crash handler may temporarily arm crash-focused debug uplift for the next launch and recovery flow

### 12. Telemetry trust and control
"""


def _telemetry_schema() -> str:
    return """# Product usage telemetry event schema

The default product-improvement telemetry plane is opt-out.

Every Tier-2 hosted telemetry event must fit this bounded envelope:

### `chummer6-ui` settings

## Delivery safety rules

clear any unsent Tier-2 spool within 24 hours
"""


def _privacy() -> str:
    return """# Privacy and retention boundaries

### Product usage telemetry

raw crash envelopes: retain for 90 days

raw hosted product-improvement event envelopes: retain for 30 days or less, then collapse into bounded daily rollups

install-linked daily usage rollups: retain for 18 months

delete or summarize within 30 days

install-linked telemetry is opt-out by default, pseudonymous by default, and must not be repurposed as a marketing profile
"""


def _crash_reporting() -> str:
    return """# Feedback and crash reporting system

1. crash reporting

chummer6-ui captures the crash locally and sends a redacted crash envelope to a Hub-owned intake endpoint.

fleet may consume the normalized crash work item for clustering, repro, test generation, candidate patch drafting, and PR preparation.

That does not make Fleet the support database, and it does not allow direct client-to-Fleet raw crash transport as the primary seam.

the recovery dialog must offer a remembered opt-out
"""


def _support_status() -> str:
    return """# Support and feedback status model

## Status spine

Notify a reporter that the issue is fixed only when Registry truth says the fix has reached that reporter's channel.

`released_to_reporter_channel`, `user_notified`, and `closed` only count as healthy closure when support packets and registry release truth agree.
"""


def _flagship_readiness(*, runtime_locales: list[str], feedback_status: str, support_generated_at: str, open_packet_count: int) -> dict:
    return {
        "coverage_details": {
            "desktop_client": {
                "evidence": {
                    "ui_localization_release_gate_status": "pass",
                    "ui_localization_release_gate_shipping_locales": runtime_locales,
                    "ui_localization_release_gate_untranslated_locale_count": 0,
                    "ui_localization_release_gate_translation_backlog_finding_count": 0,
                }
            }
        },
        "readiness_planes": {
            "feedback_loop_ready": {
                "status": feedback_status,
                "evidence": {
                    "support_generated_at": support_generated_at,
                    "support_open_packet_count": open_packet_count,
                    "support_open_non_external_packet_count": open_packet_count,
                    "closure_waiting_on_release_truth": 0,
                    "update_required_misrouted_case_count": 0,
                    "non_external_needs_human_response": 0,
                    "non_external_packets_without_named_owner": 0,
                    "non_external_packets_without_lane": 0,
                    "unresolved_external_proof_request_count": 0,
                    "support_source_refresh_mode": "source_mirror_fallback",
                    "thresholds": {"max_support_packet_age_hours": 24},
                },
            }
        },
    }


def _support_packets(*, generated_at: str, refresh_mode: str, refresh_error: str, open_packet_count: int) -> dict:
    return {
        "generated_at": generated_at,
        "summary": {
            "open_case_count": 0,
            "open_packet_count": open_packet_count,
            "open_non_external_packet_count": open_packet_count,
            "closure_waiting_on_release_truth": 0,
            "non_external_needs_human_response": 0,
            "non_external_packets_without_named_owner": 0,
            "non_external_packets_without_lane": 0,
            "unresolved_external_proof_request_count": 0,
            "operator_packet_count": 0,
            "design_impact_count": 0,
            "update_required_misrouted_case_count": 0,
        },
        "source": {
            "refresh_mode": refresh_mode,
            "refresh_error": refresh_error,
            "source_mirror_generated_at": "2026-05-05T10:00:00Z",
        },
    }


def _weekly_pulse(*, open_packet_count: int) -> dict:
    return {
        "supporting_signals": {
            "closure_health": {
                "state": "clear",
                "open_case_count": 0,
                "waiting_closure_count": 0,
                "pending_human_response_count": 0,
                "materialized_packet_count": 0,
                "design_impact_count": 0,
            }
        }
    }


def _fixture_tree(
    tmp_path: Path,
    *,
    runtime_locales: list[str],
    feedback_status: str,
    refresh_mode: str,
    refresh_error: str,
    open_packet_count: int,
) -> dict[str, Path]:
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    guide = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
    localization = tmp_path / "LOCALIZATION_AND_LANGUAGE_SYSTEM.md"
    telemetry_model = tmp_path / "PRODUCT_USAGE_TELEMETRY_MODEL.md"
    telemetry_schema = tmp_path / "PRODUCT_USAGE_TELEMETRY_EVENT_SCHEMA.md"
    privacy = tmp_path / "PRIVACY_AND_RETENTION_BOUNDARIES.md"
    crash_reporting = tmp_path / "FEEDBACK_AND_CRASH_REPORTING_SYSTEM.md"
    support_status = tmp_path / "FEEDBACK_AND_CRASH_STATUS_MODEL.md"
    flagship = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    weekly_pulse = tmp_path / "WEEKLY_PRODUCT_PULSE.generated.json"
    artifact = tmp_path / "NEXT90_M128_FLEET_TRUST_PLANE_MONITORS.generated.json"
    markdown = tmp_path / "NEXT90_M128_FLEET_TRUST_PLANE_MONITORS.generated.md"

    _write_yaml(registry, _registry())
    _write_yaml(queue, {"items": [_queue_item()]})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(guide, _guide())
    _write_text(localization, _localization())
    _write_text(telemetry_model, _telemetry_model())
    _write_text(telemetry_schema, _telemetry_schema())
    _write_text(privacy, _privacy())
    _write_text(crash_reporting, _crash_reporting())
    _write_text(support_status, _support_status())
    _write_json(
        flagship,
        _flagship_readiness(
            runtime_locales=runtime_locales,
            feedback_status=feedback_status,
            support_generated_at="2026-05-05T12:00:00Z",
            open_packet_count=open_packet_count,
        ),
    )
    _write_json(
        support_packets,
        _support_packets(
            generated_at="2026-05-05T12:00:00Z",
            refresh_mode=refresh_mode,
            refresh_error=refresh_error,
            open_packet_count=open_packet_count,
        ),
    )
    _write_json(weekly_pulse, _weekly_pulse(open_packet_count=open_packet_count))

    return {
        "registry": registry,
        "queue": queue,
        "design_queue": design_queue,
        "guide": guide,
        "localization": localization,
        "telemetry_model": telemetry_model,
        "telemetry_schema": telemetry_schema,
        "privacy": privacy,
        "crash_reporting": crash_reporting,
        "support_status": support_status,
        "flagship": flagship,
        "support_packets": support_packets,
        "weekly_pulse": weekly_pulse,
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
            "--localization-system",
            str(paths["localization"]),
            "--telemetry-model",
            str(paths["telemetry_model"]),
            "--telemetry-schema",
            str(paths["telemetry_schema"]),
            "--privacy-boundaries",
            str(paths["privacy"]),
            "--crash-reporting",
            str(paths["crash_reporting"]),
            "--support-status",
            str(paths["support_status"]),
            "--flagship-readiness",
            str(paths["flagship"]),
            "--support-packets",
            str(paths["support_packets"]),
            "--weekly-product-pulse",
            str(paths["weekly_pulse"]),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class MaterializeNext90M128FleetTrustPlaneMonitorsTests(unittest.TestCase):
    def test_materialize_passes_with_warning_when_support_source_is_mirror_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m128-materialize-") as temp_dir:
            paths = _fixture_tree(
                Path(temp_dir),
                runtime_locales=["en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn"],
                feedback_status="ready",
                refresh_mode="source_mirror_fallback",
                refresh_error="source unreachable",
                open_packet_count=0,
            )
            result = _run_materializer(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["monitor_summary"]["trust_plane_status"], "warning")
            self.assertEqual(payload["monitor_summary"]["runtime_blocker_count"], 0)
            self.assertTrue(payload["package_closeout"]["warnings"])

    def test_materialize_flags_runtime_blockers_when_locales_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m128-materialize-") as temp_dir:
            paths = _fixture_tree(
                Path(temp_dir),
                runtime_locales=["en-us", "de-de", "fr-fr"],
                feedback_status="ready",
                refresh_mode="remote_live",
                refresh_error="",
                open_packet_count=0,
            )
            result = _run_materializer(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["monitor_summary"]["trust_plane_status"], "blocked")
            self.assertIn("shipping locale set drifted", "\n".join(payload["monitor_summary"]["runtime_blockers"]))

    def test_materialize_accepts_generated_queue_overlay_shape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m128-materialize-") as temp_dir:
            paths = _fixture_tree(
                Path(temp_dir),
                runtime_locales=["en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn"],
                feedback_status="ready",
                refresh_mode="remote_live",
                refresh_error="",
                open_packet_count=0,
            )
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
