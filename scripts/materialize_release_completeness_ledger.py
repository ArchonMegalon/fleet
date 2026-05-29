#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

try:
    from scripts.materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest
except ModuleNotFoundError:
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
DEFAULT_OUT = PUBLISHED / "LTT_AND_12_TICKS_RELEASE_COMPLETENESS.generated.json"

READINESS_TITLES = {
    "desktop_client": "Desktop client",
    "rules_engine_and_import": "Rules engine and import",
    "hub_and_registry": "Hub and registry",
    "mobile_play_shell": "Mobile play shell",
    "ui_kit_and_flagship_polish": "UI kit and flagship polish",
    "media_artifacts": "Media artifacts",
    "horizons_and_public_surface": "Horizons and public surface",
    "fleet_and_operator_loop": "Fleet and operator loop",
}


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _status_from_bools(*, implemented: bool, integrated: bool, e2e_tested: bool) -> str:
    if implemented and integrated and e2e_tested:
        return "pass"
    if implemented and integrated:
        return "warning"
    if implemented:
        return "partial"
    return "missing"


def _readiness_inventory(flagship: Dict[str, Any]) -> List[Dict[str, Any]]:
    ready = {str(item).strip() for item in (flagship.get("ready_keys") or []) if str(item).strip()}
    warnings = {str(item).strip() for item in (flagship.get("warning_keys") or []) if str(item).strip()}
    missing = {str(item).strip() for item in (flagship.get("missing_keys") or []) if str(item).strip()}
    keys = list(READINESS_TITLES)
    items: List[Dict[str, Any]] = []
    for key in keys:
        implemented = key in ready or key in warnings
        integrated = key in ready or key in warnings
        e2e_tested = key in ready
        if key in missing:
            implemented = False
            integrated = False
            e2e_tested = False
        items.append(
            {
                "id": key,
                "family": "readiness_plane",
                "title": READINESS_TITLES[key],
                "implemented": implemented,
                "integrated": integrated,
                "end_to_end_tested": e2e_tested,
                "status": _status_from_bools(
                    implemented=implemented,
                    integrated=integrated,
                    e2e_tested=e2e_tested,
                ),
                "evidence": [
                    {
                        "surface": "flagship_product_readiness",
                        "path": str(DEFAULT_OUT.parent / "FLAGSHIP_PRODUCT_READINESS.generated.json"),
                        "status": "ready" if key in ready else ("warning" if key in warnings else "missing"),
                    }
                ],
            }
        )
    return items


def _journey_ticks(journey_gates: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for row in (journey_gates.get("journeys") or []):
        if not isinstance(row, dict):
            continue
        journey_id = str(row.get("id") or "").strip()
        if not journey_id:
            continue
        state = str(row.get("state") or "").strip().lower()
        implemented = bool(row)
        integrated = state in {"ready", "warning"}
        e2e_tested = state == "ready"
        rows.append(
            {
                "id": journey_id,
                "family": "golden_journey",
                "title": str(row.get("title") or journey_id).strip(),
                "implemented": implemented,
                "integrated": integrated,
                "end_to_end_tested": e2e_tested,
                "status": _status_from_bools(
                    implemented=implemented,
                    integrated=integrated,
                    e2e_tested=e2e_tested,
                ),
                "current_state": state or "missing",
                "evidence": [
                    {
                        "surface": "journey_gates",
                        "path": str(DEFAULT_OUT.parent / "JOURNEY_GATES.generated.json"),
                        "status": state or "missing",
                    }
                ],
            }
        )
    return rows


def _public_route_ticks(progress_report: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for row in (progress_report.get("public_route_cards") or []):
        if not isinstance(row, dict):
            continue
        route_id = str(row.get("id") or "").strip()
        if not route_id:
            continue
        state = str(row.get("proof_state") or "").strip().lower()
        implemented = state in {"implemented", "public-stable", "preview-bounded"}
        integrated = state in {"implemented", "public-stable", "preview-bounded"}
        e2e_tested = state == "public-stable"
        rows.append(
            {
                "id": route_id,
                "family": "public_route",
                "title": str(row.get("title") or route_id).strip(),
                "route": str(row.get("route") or "").strip(),
                "implemented": implemented,
                "integrated": integrated,
                "end_to_end_tested": e2e_tested,
                "status": _status_from_bools(
                    implemented=implemented,
                    integrated=integrated,
                    e2e_tested=e2e_tested,
                ),
                "current_state": state or "missing",
                "evidence": [
                    {
                        "surface": "public_progress_route_card",
                        "path": str(DEFAULT_OUT.parent / "PROGRESS_REPORT.generated.json"),
                        "status": state or "missing",
                    }
                ],
            }
        )
    return rows


def build_payload(
    *,
    flagship: Dict[str, Any],
    journey_gates: Dict[str, Any],
    progress_report: Dict[str, Any],
    completion_frontier: Dict[str, Any],
) -> Dict[str, Any]:
    readiness_inventory = _readiness_inventory(flagship)
    journey_ticks = _journey_ticks(journey_gates)
    public_route_ticks = _public_route_ticks(progress_report)
    ltt_inventory = readiness_inventory + journey_ticks + public_route_ticks
    tick_set = journey_ticks + public_route_ticks

    completion_audit = dict(completion_frontier.get("completion_audit") or {})
    repo_backlog_audit = dict(completion_frontier.get("repo_backlog_audit") or {})
    incomplete_ticks = [row["id"] for row in tick_set if row.get("status") != "pass"]
    blocked_by_repo_backlog = str(repo_backlog_audit.get("status") or "").strip().lower() == "fail"
    absolute_finish_allowed = not incomplete_ticks and not blocked_by_repo_backlog and (
        str(completion_audit.get("status") or "").strip().lower() == "pass"
    )

    return {
        "contract_name": "fleet.ltt_and_12_ticks_release_completeness",
        "schema_version": 1,
        "generated_at": progress_report.get("generated_at"),
        "summary": {
            "ltt_inventory_count": len(ltt_inventory),
            "tick_count": len(tick_set),
            "pass_count": sum(1 for row in tick_set if row.get("status") == "pass"),
            "non_pass_count": sum(1 for row in tick_set if row.get("status") != "pass"),
            "absolute_finish_allowed": absolute_finish_allowed,
        },
        "definition": {
            "ltt_inventory_rule": (
                "LTT is the fleet-wide release-critical inventory built from flagship readiness planes, golden journeys, "
                "and public route proof surfaces."
            ),
            "ticks_rule": (
                "12-ticks is the current executable certification set: six golden journeys plus six public route cards. "
                "This grouping is a fleet synthesis over repo-local proof surfaces rather than a design-registry primitive."
            ),
        },
        "source_artifacts": {
            "flagship_product_readiness": str(DEFAULT_OUT.parent / "FLAGSHIP_PRODUCT_READINESS.generated.json"),
            "journey_gates": str(DEFAULT_OUT.parent / "JOURNEY_GATES.generated.json"),
            "progress_report": str(DEFAULT_OUT.parent / "PROGRESS_REPORT.generated.json"),
            "completion_review_frontier": str(DEFAULT_OUT.parent / "COMPLETION_REVIEW_FRONTIER.generated.yaml"),
        },
        "ltt_inventory": ltt_inventory,
        "ticks": tick_set,
        "release_claim_guard": {
            "status": "pass" if absolute_finish_allowed else "fail",
            "reason": (
                "All twelve executable ticks are pass and the repo-local completion frontier is clean."
                if absolute_finish_allowed
                else "Absolute-finish language remains blocked until every tick passes and repo-local backlog is clear."
            ),
            "incomplete_tick_ids": incomplete_ticks,
            "completion_audit_status": str(completion_audit.get("status") or "").strip().lower() or "missing",
            "completion_audit_reason": str(completion_audit.get("reason") or "").strip(),
            "repo_backlog_status": str(repo_backlog_audit.get("status") or "").strip().lower() or "missing",
            "repo_backlog_reason": str(repo_backlog_audit.get("reason") or "").strip(),
            "repo_backlog_open_item_count": int(repo_backlog_audit.get("open_item_count") or 0),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize Fleet's LTT and 12-ticks release-completeness ledger.")
    parser.add_argument("--flagship-readiness", default=str(PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"))
    parser.add_argument("--journey-gates", default=str(PUBLISHED / "JOURNEY_GATES.generated.json"))
    parser.add_argument("--progress-report", default=str(PUBLISHED / "PROGRESS_REPORT.generated.json"))
    parser.add_argument("--completion-frontier", default=str(PUBLISHED / "COMPLETION_REVIEW_FRONTIER.generated.yaml"))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.out).resolve()
    payload = build_payload(
        flagship=_load_json(Path(args.flagship_readiness).resolve()),
        journey_gates=_load_json(Path(args.journey_gates).resolve()),
        progress_report=_load_json(Path(args.progress_report).resolve()),
        completion_frontier=yaml.safe_load(Path(args.completion_frontier).resolve().read_text(encoding="utf-8")) or {},
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    repo_root = repo_root_for_published_path(out_path)
    if repo_root == ROOT:
        write_compile_manifest(ROOT)
    print(f"wrote release completeness ledger: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
