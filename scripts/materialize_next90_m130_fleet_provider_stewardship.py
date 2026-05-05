#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
PRODUCT_MIRROR = Path("/docker/chummercomplete/chummer-design/products/chummer")

PACKAGE_ID = "next90-m130-fleet-add-provider-health-credit-runway-kill-switch-fallback-a"
FRONTIER_ID = 7382989835
MILESTONE_ID = 130
WORK_TASK_ID = "130.2"
WAVE_ID = "W19"
QUEUE_TITLE = "Add provider-health, credit-runway, kill-switch, fallback, and route-stewardship monitors for all governed external tools."
QUEUE_TASK = "Add provider-health, credit-runway, kill-switch, fallback, and route-stewardship monitors for all governed external tools."
WORK_TASK_TITLE = "Add provider-health, credit-runway, kill-switch, fallback, and route-stewardship monitors for all governed external tools."
WORK_TASK_DEPENDENCIES = [106, 107, 114, 125]
OWNED_SURFACES = ["add_provider_health_credit_runway:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M130_FLEET_PROVIDER_STEWARDSHIP.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M130_FLEET_PROVIDER_STEWARDSHIP.generated.md"
DEFAULT_LIVE_ADMIN_STATUS_OUTPUT = PUBLISHED / "NEXT90_M130_FLEET_PROVIDER_STEWARDSHIP.admin_status.generated.json"
DEFAULT_LIVE_PROVIDER_CREDIT_OUTPUT = PUBLISHED / "NEXT90_M130_FLEET_PROVIDER_STEWARDSHIP.provider_credit.generated.json"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
EXTERNAL_TOOLS_PLANE = PRODUCT_MIRROR / "EXTERNAL_TOOLS_PLANE.md"
LTD_CAPABILITY_MAP = PRODUCT_MIRROR / "LTD_CAPABILITY_MAP.md"
PROVIDER_ROUTE_STEWARDSHIP = PRODUCT_MIRROR / "PROVIDER_AND_ROUTE_STEWARDSHIP.md"
WEEKLY_GOVERNOR_PACKET = PUBLISHED / "WEEKLY_GOVERNOR_PACKET.generated.json"
ADMIN_MODULE_PATH = ROOT / "admin" / "app.py"
ADMIN_CONTAINER_NAME = "fleet-admin"

REQUIRED_STEWARDSHIP_MARKERS = {
    "weekly_provider_scan": "### 1. Weekly provider scan",
    "lane_specific_benchmark": "### 2. Lane-specific benchmark run",
    "canary_before_default": "### 3. Canary before default",
    "publish_the_reason": "### 4. Publish the reason",
    "fallback_hygiene": "* fallback and rollback hygiene",
    "rollback_target": "* rollback target",
    "kill_switch_rule": "* No provider or model swap may bypass adapters, receipts, or kill switches.",
}
REQUIRED_EXTERNAL_TOOLS_MARKERS = {
    "kill_switch_rule": "### Rule 4 - kill switch required",
    "public_widget_fallback": "* the widget has a graceful first-party fallback path",
    "activation_verification": "## Activation verification rule",
    "kill_switch_exists": "* the kill switch exists",
    "fallback_behavior_exists": "* fallback behavior exists",
    "release_gate_rule": "## Release-gate rule",
}
TOOL_BULLET_RE = re.compile(r"^\* `([^`]+)` - (.+)$", re.MULTILINE)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the Fleet M130 provider stewardship monitor packet."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--external-tools-plane", default=str(EXTERNAL_TOOLS_PLANE))
    parser.add_argument("--ltd-capability-map", default=str(LTD_CAPABILITY_MAP))
    parser.add_argument("--provider-route-stewardship", default=str(PROVIDER_ROUTE_STEWARDSHIP))
    parser.add_argument("--weekly-governor-packet", default=str(WEEKLY_GOVERNOR_PACKET))
    parser.add_argument("--admin-status", default="")
    parser.add_argument("--provider-credit", default="")
    parser.add_argument("--live-admin-status-output", default=str(DEFAULT_LIVE_ADMIN_STATUS_OUTPUT))
    parser.add_argument("--live-provider-credit-output", default=str(DEFAULT_LIVE_PROVIDER_CREDIT_OUTPUT))
    return parser.parse_args(argv)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [_normalize_text(value) for value in values if _normalize_text(value)]


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> Dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _parse_iso_utc(value: Any) -> dt.datetime | None:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except ValueError:
        return None


def _age_seconds(value: Any, *, generated_at: str) -> int | None:
    source_dt = _parse_iso_utc(value)
    generated_dt = _parse_iso_utc(generated_at)
    if source_dt is None or generated_dt is None:
        return None
    return max(0, int((generated_dt - source_dt).total_seconds()))


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _find_queue_item(queue: Dict[str, Any], package_id: str) -> Dict[str, Any]:
    for row in queue.get("items") or []:
        if isinstance(row, dict) and _normalize_text(row.get("package_id")) == package_id:
            return dict(row)
    return {}


def _find_milestone(registry: Dict[str, Any], milestone_id: int) -> Dict[str, Any]:
    for row in registry.get("milestones") or []:
        if isinstance(row, dict) and int(row.get("id") or 0) == milestone_id:
            return dict(row)
    return {}


def _find_work_task(milestone: Dict[str, Any], work_task_id: str) -> Dict[str, Any]:
    for row in milestone.get("work_tasks") or []:
        if isinstance(row, dict) and _normalize_text(row.get("id")) == work_task_id:
            return dict(row)
    return {}


def _queue_alignment(
    queue_item: Dict[str, Any],
    design_queue_item: Dict[str, Any],
    work_task: Dict[str, Any],
    milestone: Dict[str, Any],
) -> Dict[str, Any]:
    issues: List[str] = []
    if not queue_item:
        issues.append("Fleet queue row is missing.")
    if not design_queue_item:
        issues.append("Design queue row is missing.")
    if not work_task:
        issues.append("Canonical registry work task is missing.")
    expected = {
        "title": QUEUE_TITLE,
        "task": QUEUE_TASK,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "repo": "fleet",
        "wave": WAVE_ID,
    }
    for field, expected_value in expected.items():
        expected_text = _normalize_text(expected_value)
        if queue_item and _normalize_text(queue_item.get(field)) != expected_text:
            issues.append(f"Fleet queue {field} drifted.")
        if design_queue_item and _normalize_text(design_queue_item.get(field)) != expected_text:
            issues.append(f"Design queue {field} drifted.")
    if queue_item and _normalize_list(queue_item.get("allowed_paths")) != ALLOWED_PATHS:
        issues.append("Fleet queue allowed_paths drifted.")
    if design_queue_item and _normalize_list(design_queue_item.get("allowed_paths")) != ALLOWED_PATHS:
        issues.append("Design queue allowed_paths drifted.")
    if queue_item and _normalize_list(queue_item.get("owned_surfaces")) != OWNED_SURFACES:
        issues.append("Fleet queue owned_surfaces drifted.")
    if design_queue_item and _normalize_list(design_queue_item.get("owned_surfaces")) != OWNED_SURFACES:
        issues.append("Design queue owned_surfaces drifted.")
    if work_task:
        if _normalize_text(work_task.get("owner")) != "fleet":
            issues.append("Canonical registry work task owner drifted.")
        if _normalize_text(work_task.get("title")) != WORK_TASK_TITLE:
            issues.append("Canonical registry work task title drifted.")
    if milestone and [int(value) for value in milestone.get("dependencies") or []] != WORK_TASK_DEPENDENCIES:
        issues.append("Canonical registry milestone dependencies drifted from M130 requirement set.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "fleet_queue_status": _normalize_text(queue_item.get("status")),
        "design_queue_status": _normalize_text(design_queue_item.get("status")),
        "registry_status": _normalize_text(milestone.get("status")),
        "work_task_status": _normalize_text(work_task.get("status")),
        "work_task_title": _normalize_text(work_task.get("title")),
    }


def _extract_markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}\n"
    start = text.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    remainder = text[start:]
    next_heading = remainder.find("\n## ")
    return remainder[:next_heading] if next_heading >= 0 else remainder


def _parse_tool_bullets(section_text: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for tool_name, description in TOOL_BULLET_RE.findall(section_text):
        rows.append({"tool": _normalize_text(tool_name), "description": _normalize_text(description)})
    return rows


def _canonical_marker_monitor(text: str, markers: Dict[str, str], *, label: str) -> Dict[str, Any]:
    checks = {name: marker in text for name, marker in markers.items()}
    issues = [f"{label} missing required marker: {name}" for name, present in checks.items() if not present]
    return {
        "state": "pass" if not issues else "fail",
        "checks": checks,
        "issues": issues,
    }


def _governed_tool_inventory_monitor(
    *,
    external_tools_text: str,
    ltd_capability_text: str,
) -> Dict[str, Any]:
    plane_section = _extract_markdown_section(external_tools_text, "Tool inventory posture")
    plane_inventory = [line.strip("* ").strip() for line in plane_section.splitlines() if line.strip().startswith("* ")]
    promoted = _parse_tool_bullets(_extract_markdown_section(ltd_capability_text, "Promoted"))
    bounded = _parse_tool_bullets(_extract_markdown_section(ltd_capability_text, "Bounded"))
    research = _parse_tool_bullets(_extract_markdown_section(ltd_capability_text, "Research / Parked"))
    non_product = _parse_tool_bullets(_extract_markdown_section(ltd_capability_text, "Non-product"))
    owner_assignments = _parse_tool_bullets(_extract_markdown_section(ltd_capability_text, "Bounded owner assignments"))
    promoted_and_bounded = {row["tool"] for row in [*promoted, *bounded]}
    fleet_assignments = []
    for row in owner_assignments:
        description = row.get("description", "")
        if "`fleet`" in description or "fleet" in description.lower():
            fleet_assignments.append(row["tool"])
    issues: List[str] = []
    if not plane_inventory:
        issues.append("External tools plane inventory is empty.")
    if not promoted:
        issues.append("LTD capability map promoted section is empty.")
    if not fleet_assignments:
        issues.append("No Fleet-owned governed external-tool assignments were found.")
    for tool in fleet_assignments:
        if tool not in promoted_and_bounded:
            issues.append(f"Fleet assignment for `{tool}` is missing from promoted/bounded inventory.")
    return {
        "state": "pass" if not issues else "fail",
        "external_tools_plane_inventory_count": len(plane_inventory),
        "promoted_tool_count": len(promoted),
        "bounded_tool_count": len(bounded),
        "research_tool_count": len(research),
        "non_product_tool_count": len(non_product),
        "fleet_assigned_tools": sorted(fleet_assignments),
        "issues": issues,
    }


def _provider_routes_monitor(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    issues: List[str] = []
    fallback_thin_lanes: List[str] = []
    review_due_lanes: List[str] = []
    revert_now_lanes: List[str] = []
    summarized_rows: List[Dict[str, Any]] = []
    for row in rows:
        lane = _normalize_text(row.get("lane"))
        default_route = _normalize_text(row.get("default_route"))
        if not lane:
            issues.append("A provider route row is missing lane.")
            continue
        if not default_route:
            issues.append(f"Provider route row `{lane}` is missing default_route.")
        fallback_route = _normalize_text(row.get("fallback_route"))
        posture = _normalize_text(row.get("posture")) or "unknown"
        state = _normalize_text(row.get("state")) or "unknown"
        if posture == "fallback_thin" or not fallback_route:
            fallback_thin_lanes.append(lane)
        if bool(row.get("review_required")):
            review_due_lanes.append(lane)
        if posture == "revert_now" or state in {"blocked", "critical", "red"}:
            revert_now_lanes.append(lane)
        summarized_rows.append(
            {
                "lane": lane,
                "default_route": default_route,
                "fallback_route": fallback_route,
                "challenger_route": _normalize_text(row.get("challenger_route")),
                "state": state,
                "posture": posture,
                "configured_slots": int(row.get("configured_slots") or 0),
                "ready_slots": int(row.get("ready_slots") or 0),
                "runway": _normalize_text(row.get("runway")),
                "remaining_text": _normalize_text(row.get("remaining_text")),
                "review_required": bool(row.get("review_required")),
                "merge_review_required": bool(row.get("merge_review_required")),
            }
        )
    warnings: List[str] = []
    if fallback_thin_lanes:
        warnings.append(f"Fallback coverage is thin for {', '.join(sorted(fallback_thin_lanes))}.")
    if review_due_lanes:
        warnings.append(f"Route stewardship review is due for {', '.join(sorted(review_due_lanes))}.")
    if revert_now_lanes:
        warnings.append(f"Route posture is critical for {', '.join(sorted(revert_now_lanes))}.")
    return {
        "state": "pass" if not issues else "fail",
        "governed_route_count": len(summarized_rows),
        "fallback_thin_count": len(set(fallback_thin_lanes)),
        "review_due_count": len(set(review_due_lanes)),
        "revert_now_count": len(set(revert_now_lanes)),
        "fallback_thin_lanes": sorted(set(fallback_thin_lanes)),
        "review_due_lanes": sorted(set(review_due_lanes)),
        "revert_now_lanes": sorted(set(revert_now_lanes)),
        "warnings": warnings,
        "issues": issues,
        "routes": summarized_rows,
    }


def _credit_runway_monitor(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload:
        return {"state": "fail", "issues": ["Provider credit summary is missing."], "warnings": []}
    warnings: List[str] = []
    remaining_percent = payload.get("remaining_percent_total")
    if payload.get("depletes_before_next_topup") is True:
        warnings.append("Current burn depletes before the next known top-up.")
    try:
        if remaining_percent is not None and float(remaining_percent) <= 10.0:
            warnings.append("Aggregate remaining credits are at or below ten percent.")
    except (TypeError, ValueError):
        pass
    return {
        "state": "pass",
        "provider": _normalize_text(payload.get("provider")) or "unknown",
        "free_credits": payload.get("free_credits"),
        "max_credits": payload.get("max_credits"),
        "remaining_percent_total": remaining_percent,
        "active_lease_count": int(payload.get("active_lease_count") or 0),
        "next_topup_at": _normalize_text(payload.get("next_topup_at")),
        "topup_amount": payload.get("topup_amount"),
        "topup_eta_source": _normalize_text(payload.get("topup_eta_source")),
        "hours_until_next_topup": payload.get("hours_until_next_topup"),
        "hours_remaining_at_current_pace_no_topup": payload.get("hours_remaining_at_current_pace_no_topup"),
        "hours_remaining_including_next_topup_at_current_pace": payload.get(
            "hours_remaining_including_next_topup_at_current_pace"
        ),
        "days_remaining_including_next_topup_at_7d_avg": payload.get("days_remaining_including_next_topup_at_7d_avg"),
        "depletes_before_next_topup": payload.get("depletes_before_next_topup"),
        "basis_quality": _normalize_text(payload.get("basis_quality")),
        "basis_summary": _normalize_text(payload.get("basis_summary")),
        "warnings": warnings,
        "issues": [],
    }


def _governor_monitor(packet: Dict[str, Any]) -> Dict[str, Any]:
    if not packet:
        return {"state": "fail", "issues": ["Weekly governor packet is missing."], "warnings": []}
    board = dict(packet.get("decision_board") or {})
    ledger = dict(packet.get("decision_gate_ledger") or {})
    canary_gate = next(
        (
            dict(row)
            for lane in ("canary", "launch_expand")
            for row in (ledger.get(lane) or [])
            if isinstance(row, dict) and _normalize_text(row.get("name")) == "provider_canary"
        ),
        {},
    )
    issues: List[str] = []
    if not board.get("canary"):
        issues.append("Weekly governor packet is missing canary decision_board truth.")
    if not board.get("rollback"):
        issues.append("Weekly governor packet is missing rollback decision_board truth.")
    if not board.get("freeze_launch"):
        issues.append("Weekly governor packet is missing freeze-launch decision_board truth.")
    if not canary_gate:
        issues.append("Weekly governor packet is missing the provider_canary gate.")
    warnings: List[str] = []
    canary_state = _normalize_text((board.get("canary") or {}).get("state"))
    rollback_state = _normalize_text((board.get("rollback") or {}).get("state"))
    current_launch_action = _normalize_text(board.get("current_launch_action"))
    if canary_state and canary_state != "ready":
        warnings.append(f"Provider canary remains {canary_state or 'unknown'}.")
    if rollback_state in {"armed", "active", "watch"}:
        warnings.append(f"Rollback posture remains {rollback_state}.")
    if current_launch_action and current_launch_action != "launch_expand":
        warnings.append(f"Current launch action is {current_launch_action}.")
    return {
        "state": "pass" if not issues else "fail",
        "current_launch_action": current_launch_action,
        "current_launch_reason": _normalize_text(board.get("current_launch_reason")),
        "canary_state": canary_state,
        "canary_reason": _normalize_text((board.get("canary") or {}).get("reason")),
        "rollback_state": rollback_state,
        "rollback_reason": _normalize_text((board.get("rollback") or {}).get("reason")),
        "freeze_launch_state": _normalize_text((board.get("freeze_launch") or {}).get("state")),
        "provider_canary_gate": {
            "state": _normalize_text(canary_gate.get("state")),
            "observed": _normalize_text(canary_gate.get("observed")),
            "required": _normalize_text(canary_gate.get("required")),
        },
        "warnings": warnings,
        "issues": issues,
    }


def _source_link(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "path": _display_path(path),
        "sha256": _sha256_file(path),
        "generated_at": _normalize_text(payload.get("generated_at")),
    }


def _live_source_link(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "path": f"live:{name}",
        "sha256": _sha256_text(json.dumps(payload, sort_keys=True)),
        "generated_at": _normalize_text(payload.get("generated_at")),
    }


def _write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _install_fastapi_stubs(*, force: bool = False) -> None:
    if not force and "fastapi" in sys.modules and "fastapi.responses" in sys.modules:
        return
    if force:
        sys.modules.pop("fastapi", None)
        sys.modules.pop("fastapi.responses", None)
    fastapi = types.ModuleType("fastapi")
    responses = types.ModuleType("fastapi.responses")

    class DummyFastAPI:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __getattr__(self, _name: str):
            def decorator(*args: Any, **kwargs: Any):
                def wrapper(func):
                    return func

                return wrapper

            return decorator

    class DummyHTTPException(Exception):
        pass

    class DummyRequest:
        pass

    class DummyResponse:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    def dummy_form(*args: Any, **kwargs: Any) -> None:
        return None

    fastapi.FastAPI = DummyFastAPI
    fastapi.Form = dummy_form
    fastapi.HTTPException = DummyHTTPException
    fastapi.Request = DummyRequest
    responses.HTMLResponse = DummyResponse
    responses.JSONResponse = DummyResponse
    responses.PlainTextResponse = DummyResponse
    responses.RedirectResponse = DummyResponse
    responses.Response = DummyResponse
    sys.modules["fastapi"] = fastapi
    sys.modules["fastapi.responses"] = responses


def _load_admin_module():
    try:
        spec = importlib.util.spec_from_file_location("fleet_admin_app", ADMIN_MODULE_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"unable to load module from {ADMIN_MODULE_PATH}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        _install_fastapi_stubs(force=True)
        spec = importlib.util.spec_from_file_location("fleet_admin_app", ADMIN_MODULE_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"unable to load module from {ADMIN_MODULE_PATH}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def _load_live_admin_inputs() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    try:
        module = _load_admin_module()
        admin_status = dict(module.api_cockpit_status() or {})
        provider_credit = dict(module.provider_credit_card_payload(cache_only=False) or {})
        return admin_status, provider_credit
    except Exception:
        return _load_container_cache_only_admin_inputs()


def _load_container_cache_only_admin_inputs() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    script = """
import importlib.util
import json

spec = importlib.util.spec_from_file_location("fleet_admin_app", "/app/app.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
status = dict(module.admin_status_payload(public_mode=True) or {})
status["provider_routes"] = list(module.provider_route_summary_payload(status, cache_only=True) or [])
provider_credit = dict(module.provider_credit_card_payload(cache_only=True) or {})
print(json.dumps({"admin_status": status, "provider_credit": provider_credit}))
""".strip()
    result = subprocess.run(
        ["docker", "exec", "-i", ADMIN_CONTAINER_NAME, "python", "-"],
        input=script,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "container admin fallback failed")
    payload = json.loads(result.stdout or "{}")
    admin_status = dict(payload.get("admin_status") or {})
    provider_credit = dict(payload.get("provider_credit") or {})
    if not admin_status or not provider_credit:
        raise RuntimeError("container admin fallback returned incomplete data")
    return admin_status, provider_credit


def build_payload(
    *,
    registry_path: Path,
    queue_path: Path,
    design_queue_path: Path,
    external_tools_plane_path: Path,
    ltd_capability_map_path: Path,
    provider_route_stewardship_path: Path,
    weekly_governor_packet_path: Path,
    admin_status: Dict[str, Any],
    provider_credit: Dict[str, Any],
    admin_status_source: str,
    provider_credit_source: str,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    registry = _read_yaml(registry_path)
    queue = _read_yaml(queue_path)
    design_queue = _read_yaml(design_queue_path)
    weekly_governor_packet = _read_json(weekly_governor_packet_path)
    external_tools_text = _read_text(external_tools_plane_path)
    ltd_capability_text = _read_text(ltd_capability_map_path)
    provider_route_stewardship_text = _read_text(provider_route_stewardship_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    queue_item = _find_queue_item(queue, PACKAGE_ID)
    design_queue_item = _find_queue_item(design_queue, PACKAGE_ID)

    canonical_alignment = _queue_alignment(queue_item, design_queue_item, work_task, milestone)
    route_stewardship_monitor = _canonical_marker_monitor(
        provider_route_stewardship_text,
        REQUIRED_STEWARDSHIP_MARKERS,
        label="Provider-route stewardship canon",
    )
    external_tools_monitor = _canonical_marker_monitor(
        external_tools_text,
        REQUIRED_EXTERNAL_TOOLS_MARKERS,
        label="External-tools plane canon",
    )
    inventory_monitor = _governed_tool_inventory_monitor(
        external_tools_text=external_tools_text,
        ltd_capability_text=ltd_capability_text,
    )
    provider_routes_monitor = _provider_routes_monitor(
        [dict(row) for row in admin_status.get("provider_routes") or [] if isinstance(row, dict)]
    )
    credit_runway_monitor = _credit_runway_monitor(provider_credit)
    governor_monitor = _governor_monitor(weekly_governor_packet)

    blockers: List[str] = []
    for section_name, section in (
        ("canonical_alignment", canonical_alignment),
        ("route_stewardship_monitor", route_stewardship_monitor),
        ("external_tools_monitor", external_tools_monitor),
        ("inventory_monitor", inventory_monitor),
        ("provider_routes_monitor", provider_routes_monitor),
        ("credit_runway_monitor", credit_runway_monitor),
        ("governor_monitor", governor_monitor),
    ):
        for issue in section.get("issues") or []:
            blockers.append(f"{section_name}: {issue}")

    warnings: List[str] = []
    warnings.extend(provider_routes_monitor.get("warnings") or [])
    warnings.extend(credit_runway_monitor.get("warnings") or [])
    warnings.extend(governor_monitor.get("warnings") or [])

    source_inputs = {
        "successor_registry": _source_link(registry_path, registry),
        "queue_staging": _source_link(queue_path, queue),
        "design_queue_staging": _source_link(design_queue_path, design_queue),
        "external_tools_plane": {
            "path": _display_path(external_tools_plane_path),
            "sha256": _sha256_file(external_tools_plane_path),
            "generated_at": "",
        },
        "ltd_capability_map": {
            "path": _display_path(ltd_capability_map_path),
            "sha256": _sha256_file(ltd_capability_map_path),
            "generated_at": "",
        },
        "provider_route_stewardship": {
            "path": _display_path(provider_route_stewardship_path),
            "sha256": _sha256_file(provider_route_stewardship_path),
            "generated_at": "",
        },
        "weekly_governor_packet": _source_link(weekly_governor_packet_path, weekly_governor_packet),
        "admin_status": (
            _source_link(Path(admin_status_source), admin_status)
            if admin_status_source and admin_status_source != "live"
            else _live_source_link("admin_status", admin_status)
        ),
        "provider_credit": (
            _source_link(Path(provider_credit_source), provider_credit)
            if provider_credit_source and provider_credit_source != "live"
            else _live_source_link("provider_credit", provider_credit)
        ),
    }

    return {
        "contract_name": "fleet.next90_m130_provider_stewardship_monitor",
        "generated_at": generated_at,
        "status": "pass" if not blockers else "blocked",
        "package_id": PACKAGE_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "wave": WAVE_ID,
        "queue_title": QUEUE_TITLE,
        "queue_task": QUEUE_TASK,
        "owned_surfaces": OWNED_SURFACES,
        "allowed_paths": ALLOWED_PATHS,
        "canonical_alignment": canonical_alignment,
        "canonical_monitors": {
            "provider_route_stewardship": route_stewardship_monitor,
            "external_tools_plane": external_tools_monitor,
            "governed_tool_inventory": inventory_monitor,
        },
        "runtime_monitors": {
            "provider_routes": provider_routes_monitor,
            "credit_runway": credit_runway_monitor,
            "runtime_healing_summary": {
                "service_count": len((admin_status.get("runtime_healing") or {}).get("services") or []),
                "generated_at": _normalize_text((admin_status.get("runtime_healing") or {}).get("generated_at")),
                "source_age_seconds": _age_seconds(
                    (admin_status.get("runtime_healing") or {}).get("generated_at"),
                    generated_at=generated_at,
                ),
            },
        },
        "governor_monitors": governor_monitor,
        "package_closeout": {
            "state": "pass" if not blockers else "blocked",
            "blockers": blockers,
            "warnings": warnings,
        },
        "source_inputs": source_inputs,
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    provider_routes = dict(((payload.get("runtime_monitors") or {}).get("provider_routes") or {}))
    credit_runway = dict(((payload.get("runtime_monitors") or {}).get("credit_runway") or {}))
    governor = dict(payload.get("governor_monitors") or {})
    inventory = dict(((payload.get("canonical_monitors") or {}).get("governed_tool_inventory") or {}))
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        f"# Fleet M130 provider stewardship monitor",
        "",
        f"- status: {payload.get('status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Runtime posture",
        f"- governed routes: {provider_routes.get('governed_route_count', 0)}",
        f"- fallback-thin lanes: {provider_routes.get('fallback_thin_count', 0)}",
        f"- review-due lanes: {provider_routes.get('review_due_count', 0)}",
        f"- revert-now lanes: {provider_routes.get('revert_now_count', 0)}",
        f"- credit provider: {credit_runway.get('provider', 'unknown')}",
        f"- free credits: {credit_runway.get('free_credits')}",
        f"- next top-up: {credit_runway.get('next_topup_at') or 'unknown'}",
        "",
        "## Governor posture",
        f"- launch action: {governor.get('current_launch_action') or 'unknown'}",
        f"- canary state: {governor.get('canary_state') or 'unknown'}",
        f"- rollback state: {governor.get('rollback_state') or 'unknown'}",
        "",
        "## Canon posture",
        f"- external-tool inventory count: {inventory.get('external_tools_plane_inventory_count', 0)}",
        f"- promoted tools: {inventory.get('promoted_tool_count', 0)}",
        f"- bounded tools: {inventory.get('bounded_tool_count', 0)}",
        f"- Fleet-assigned tools: {', '.join(inventory.get('fleet_assigned_tools') or []) or 'none'}",
        "",
        "## Package closeout",
        f"- state: {closeout.get('state') or 'blocked'}",
    ]
    blockers = list(closeout.get("blockers") or [])
    warnings = list(closeout.get("warnings") or [])
    if blockers:
        lines.append("- blockers:")
        lines.extend([f"  - {item}" for item in blockers])
    if warnings:
        lines.append("- warnings:")
        lines.extend([f"  - {item}" for item in warnings])
    return "\n".join(lines) + "\n"


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    admin_status_path = Path(args.admin_status).resolve() if _normalize_text(args.admin_status) else None
    provider_credit_path = Path(args.provider_credit).resolve() if _normalize_text(args.provider_credit) else None
    if admin_status_path is not None:
        admin_status = _read_json(admin_status_path)
        admin_status_source = str(admin_status_path)
    else:
        admin_status = {}
        admin_status_source = "live"
    if provider_credit_path is not None:
        provider_credit = _read_json(provider_credit_path)
        provider_credit_source = str(provider_credit_path)
    else:
        provider_credit = {}
        provider_credit_source = "live"
    loaded_live_inputs = False
    if not admin_status or not provider_credit:
        live_admin_status, live_provider_credit = _load_live_admin_inputs()
        if not admin_status:
            admin_status = live_admin_status
            loaded_live_inputs = True
        if not provider_credit:
            provider_credit = live_provider_credit
            loaded_live_inputs = True
    if loaded_live_inputs:
        capture_time = _utc_now()
        if admin_status and not _normalize_text(admin_status.get("generated_at")):
            admin_status = {"generated_at": capture_time, **admin_status}
        if provider_credit and not _normalize_text(provider_credit.get("generated_at")):
            provider_credit = {"generated_at": capture_time, **provider_credit}
        if admin_status_path is None:
            admin_status_path = Path(args.live_admin_status_output).resolve()
            _write_json_file(admin_status_path, admin_status)
            admin_status_source = str(admin_status_path)
        if provider_credit_path is None:
            provider_credit_path = Path(args.live_provider_credit_output).resolve()
            _write_json_file(provider_credit_path, provider_credit)
            provider_credit_source = str(provider_credit_path)
    payload = build_payload(
        registry_path=Path(args.successor_registry).resolve(),
        queue_path=Path(args.queue_staging).resolve(),
        design_queue_path=Path(args.design_queue_staging).resolve(),
        external_tools_plane_path=Path(args.external_tools_plane).resolve(),
        ltd_capability_map_path=Path(args.ltd_capability_map).resolve(),
        provider_route_stewardship_path=Path(args.provider_route_stewardship).resolve(),
        weekly_governor_packet_path=Path(args.weekly_governor_packet).resolve(),
        admin_status=admin_status,
        provider_credit=provider_credit,
        admin_status_source=admin_status_source,
        provider_credit_source=provider_credit_source,
    )
    output_path = Path(args.output).resolve()
    markdown_path = Path(args.markdown_output).resolve()
    _write_json_file(output_path, payload)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
