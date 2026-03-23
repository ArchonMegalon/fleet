from __future__ import annotations

import datetime as dt
import math
import pathlib
from typing import Any, Dict, List, Optional

import yaml


UTC = dt.timezone.utc
DEFAULT_CONTRACT_NAME = "fleet.capacity_plan"
DEFAULT_CONTRACT_VERSION = "2026-03-22"


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso(value: Optional[dt.datetime]) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: Any) -> Optional[dt.datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(raw).astimezone(UTC)
    except ValueError:
        return None


def load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_capacity_plane_configs(config_root: pathlib.Path) -> Dict[str, Any]:
    root = config_root if config_root.is_dir() else config_root.parent
    return {
        "quartermaster": dict((load_yaml(root / "quartermaster.yaml").get("quartermaster")) or {}),
        "booster_pools": dict((load_yaml(root / "booster_pools.yaml").get("booster_pools")) or {}),
        "review_fabric": dict((load_yaml(root / "review_fabric.yaml").get("review_fabric")) or {}),
        "audit_fabric": dict((load_yaml(root / "audit_fabric.yaml").get("audit_fabric")) or {}),
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _effective_project_safety_cap(contract: Dict[str, Any]) -> int:
    merged = dict(contract or {})
    safety = dict(merged.get("safety") or {})
    explicit_cap = _safe_int(merged.get("project_safety_cap"))
    default_cap = _safe_int(merged.get("default_project_cap"), _safe_int(safety.get("default_project_cap")))
    hard_cap = _safe_int(merged.get("hard_project_cap"), _safe_int(safety.get("hard_project_cap")))
    if explicit_cap > 0:
        return min(explicit_cap, hard_cap) if hard_cap > 0 else explicit_cap
    if default_cap > 0:
        return min(default_cap, hard_cap) if hard_cap > 0 else default_cap
    return 0


def _merged_project_pool_contract(contract: Dict[str, Any], booster_pools: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(contract or {})
    pool_name = str(merged.get("pool") or "").strip()
    pool = dict((booster_pools or {}).get(pool_name) or {}) if pool_name else {}
    if not pool:
        return merged
    result = dict(pool)
    result.update(merged)
    pool_safety = dict(pool.get("safety") or {})
    contract_safety = dict(merged.get("safety") or {})
    merged_safety = dict(pool_safety)
    merged_safety.update(contract_safety)
    if merged_safety:
        result["safety"] = merged_safety
    if "default_project_cap" not in result and merged_safety.get("default_project_cap") not in (None, ""):
        result["default_project_cap"] = merged_safety.get("default_project_cap")
    if "hard_project_cap" not in result and merged_safety.get("hard_project_cap") not in (None, ""):
        result["hard_project_cap"] = merged_safety.get("hard_project_cap")
    result["pool"] = pool_name or str(result.get("pool") or "")
    return result


def _month_end(now: dt.datetime) -> dt.datetime:
    if now.month == 12:
        return dt.datetime(now.year + 1, 1, 1, tzinfo=UTC)
    return dt.datetime(now.year, now.month + 1, 1, tzinfo=UTC)


def _unique_preserve(values: List[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        clean = str(value or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        ordered.append(clean)
    return ordered


def _lane_map(capacity_forecast: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(item.get("lane") or "").strip(): dict(item)
        for item in (capacity_forecast.get("lanes") or [])
        if str(item.get("lane") or "").strip()
    }


def _credit_slot_cap(
    *,
    current_slots: int,
    hours_remaining_no_topup: Optional[float],
    hours_until_next_topup: Optional[float],
    reserve_buffer_hours: float,
) -> Optional[int]:
    if current_slots <= 0 or hours_remaining_no_topup is None:
        return None
    target_hours = max(0.0, float(hours_until_next_topup or 0.0)) + max(0.0, reserve_buffer_hours)
    if target_hours <= 0:
        return current_slots
    ratio = float(hours_remaining_no_topup) / target_hours
    return max(0, int(math.floor(ratio * current_slots)))


def _cycle_slot_cap(
    *,
    current_slots: int,
    days_remaining_with_topup_7d_avg: Optional[float],
    cycle_days_remaining: float,
    cycle_reserve_percent: float,
) -> Optional[int]:
    if current_slots <= 0 or days_remaining_with_topup_7d_avg is None or cycle_days_remaining <= 0:
        return None
    effective_target_days = cycle_days_remaining * (1.0 + max(0.0, cycle_reserve_percent) / 100.0)
    ratio = float(days_remaining_with_topup_7d_avg) / effective_target_days
    return max(0, int(math.floor(ratio * current_slots)))


def _eligible_project_count(projects: List[Dict[str, Any]], booster_worker_lanes: List[str]) -> int:
    booster_set = set(booster_worker_lanes)
    count = 0
    for project in projects:
        allowed_lanes = {
            str(item).strip()
            for item in (project.get("allowed_lanes") or [])
            if str(item).strip()
        }
        task_allow_credit_burn = bool(project.get("task_allow_credit_burn", True))
        runtime_status = str(project.get("runtime_status") or "").strip().lower()
        if runtime_status in {"completed", "completed_signed_off", "signoff_only"}:
            continue
        if not task_allow_credit_burn:
            continue
        if allowed_lanes & booster_set:
            count += 1
    return count


def _typed_finding(
    finding_type: str,
    severity: str,
    summary: str,
    *,
    cap_name: str = "",
    observed_value: Any = None,
) -> Dict[str, Any]:
    return {
        "type": str(finding_type or "").strip(),
        "severity": str(severity or "info").strip(),
        "summary": str(summary or "").strip(),
        "cap_name": str(cap_name or "").strip(),
        "observed_value": observed_value,
    }


def build_capacity_plan_payload(
    status: Dict[str, Any],
    *,
    capacity_configs: Dict[str, Any],
    now: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    current_now = now or utc_now()
    cockpit = dict((status.get("cockpit")) or status or {})
    summary = dict(cockpit.get("summary") or {})
    mission_board = dict(cockpit.get("mission_board") or {})
    capacity_forecast = dict(cockpit.get("capacity_forecast") or {})
    runway = dict(cockpit.get("runway") or {})
    jury_telemetry = dict(cockpit.get("jury_telemetry") or mission_board.get("jury_telemetry") or {})
    booster_runtime = dict(mission_board.get("booster_runtime_card") or {})
    provider_credit = dict(mission_board.get("provider_credit_card") or {})
    projects = list(status.get("projects") or cockpit.get("projects") or [])
    work_packages = dict(status.get("work_packages") or cockpit.get("work_packages") or {})
    config_projects = {
        str(item.get("id") or "").strip(): dict(item)
        for item in ((status.get("config") or {}).get("projects") or [])
        if str(item.get("id") or "").strip()
    }
    quartermaster = dict(capacity_configs.get("quartermaster") or {})
    booster_pools = dict(capacity_configs.get("booster_pools") or {})
    review_fabric = dict((capacity_configs.get("review_fabric") or {}).get("default") or {})
    audit_fabric = dict((capacity_configs.get("audit_fabric") or {}).get("default") or {})

    incidents_cfg = dict(quartermaster.get("incidents") or {})
    telemetry_cfg = dict(quartermaster.get("telemetry") or {})
    credit_cfg = dict(quartermaster.get("credit") or {})
    policy_cfg = dict(((status.get("config") or {}).get("policies") or {}).get("capacity_plane") or {})
    plane_caps = dict(policy_cfg.get("plane_caps") or {})
    backpressure = dict(policy_cfg.get("backpressure") or {})
    review_shards = dict(review_fabric.get("shards") or {})
    audit_debt = dict(audit_fabric.get("debt_backpressure") or {})
    driver = str(quartermaster.get("driver") or "service_poll").strip().lower() or "service_poll"
    baseline_tick_seconds = max(0, _safe_int(quartermaster.get("baseline_tick_seconds"), _safe_int(quartermaster.get("refresh_seconds"), 30)))
    event_tick_min_seconds = max(0, _safe_int(quartermaster.get("event_tick_min_seconds"), max(30, min(120, baseline_tick_seconds or 90))))
    plan_ttl_seconds = max(event_tick_min_seconds or 0, _safe_int(quartermaster.get("plan_ttl_seconds"), max(baseline_tick_seconds, 900)))
    max_scale_up_per_tick = max(0, _safe_int(quartermaster.get("max_scale_up_per_tick"), 1))
    max_scale_down_per_tick = max(0, _safe_int(quartermaster.get("max_scale_down_per_tick"), 1))
    min_worker_dwell_seconds = max(0, _safe_int(quartermaster.get("min_worker_dwell_seconds"), 0))
    idle_drain_seconds = max(0, _safe_int(quartermaster.get("idle_drain_seconds"), 0))
    trigger_ids = _unique_preserve(
        [
            str(item or "").strip()
            for item in incidents_cfg.get("triggers") or []
            if str(item or "").strip()
        ]
    )
    if not trigger_ids:
        trigger_ids = ["review_backpressure", "audit_debt", "booster_idle", "slot_probe_stale"]
    telemetry_provider = str(telemetry_cfg.get("provider") or "ea_onemin_manager").strip() or "ea_onemin_manager"
    onemin_manager = str(telemetry_cfg.get("onemin_manager") or "ea").strip() or "ea"
    onemin_query_mode = str(telemetry_cfg.get("onemin_query_mode") or "manager").strip() or "manager"

    capacity_by_lane = _lane_map(capacity_forecast)
    booster_worker_lanes = _unique_preserve(
        [
            str(pool.get("worker_lane") or "").strip()
            for pool in booster_pools.values()
            if isinstance(pool, dict)
        ]
        or ["core_booster", "core"]
    )
    booster_lane_rows = [capacity_by_lane.get(lane) or {} for lane in booster_worker_lanes]
    ready_slots = sum(max(0, _safe_int(item.get("ready_slots"))) for item in booster_lane_rows)
    configured_slots = sum(max(0, _safe_int(item.get("configured_slots"))) for item in booster_lane_rows)
    degraded_slots = sum(max(0, _safe_int(item.get("degraded_slots"))) for item in booster_lane_rows)
    slot_cap = max(0, ready_slots or configured_slots or _safe_int(booster_runtime.get("active_onemin_codexers")) or _safe_int(booster_runtime.get("active_boosters")))

    active_boosters = max(
        _safe_int(booster_runtime.get("active_onemin_codexers")),
        _safe_int(booster_runtime.get("active_boosters")),
    )
    current_credit_slots = max(
        active_boosters,
        _safe_int(provider_credit.get("slot_count_with_billing_snapshot")),
        _safe_int(provider_credit.get("slot_count_with_member_reconciliation")),
        slot_cap,
    )

    reserve_buffer_hours = max(
        _safe_float(credit_cfg.get("reserve_buffer_hours")) or 0.0,
        _safe_float(credit_cfg.get("minimum_headroom_hours")) or 0.0,
    )
    cycle_reserve_percent = max(0.0, _safe_float(credit_cfg.get("cycle_reserve_percent")) or 0.0)

    hours_remaining_no_topup = _safe_float(provider_credit.get("hours_remaining_at_current_pace_no_topup"))
    hours_until_next_topup = _safe_float(provider_credit.get("hours_until_next_topup"))
    days_remaining_7d_avg = _safe_float(provider_credit.get("days_remaining_including_next_topup_at_7d_avg"))
    cycle_days_remaining = max(0.0, (_month_end(current_now) - current_now).total_seconds() / 86400.0)

    credit_cap_until_next_topup = _credit_slot_cap(
        current_slots=current_credit_slots,
        hours_remaining_no_topup=hours_remaining_no_topup,
        hours_until_next_topup=hours_until_next_topup,
        reserve_buffer_hours=reserve_buffer_hours,
    )
    credit_cap_until_cycle_end = _cycle_slot_cap(
        current_slots=current_credit_slots,
        days_remaining_with_topup_7d_avg=days_remaining_7d_avg,
        cycle_days_remaining=cycle_days_remaining,
        cycle_reserve_percent=cycle_reserve_percent,
    )

    premium_queue_depth = _safe_int(((jury_telemetry.get("participant_burst") or {}).get("premium_queue_depth")))
    ready_work_packages = max(
        _safe_int(work_packages.get("ready_packages")),
        _safe_int(work_packages.get("ready_scope_cap")),
    )
    useful_work_cap = max(
        premium_queue_depth,
        ready_work_packages,
        _eligible_project_count(projects, booster_worker_lanes),
    )
    scope_cap = _safe_int(work_packages.get("scope_cap"))
    if scope_cap <= 0:
        scope_cap = 0 if work_packages else None

    review_lane_name = str(review_shards.get("lane") or "review_shard").strip() or "review_shard"
    review_lane_row = capacity_by_lane.get(review_lane_name) or {}
    review_ready_slots = max(0, _safe_int(review_lane_row.get("ready_slots")))
    active_review_workers = max(
        _safe_int(summary.get("active_review_workers")),
        review_ready_slots,
    )
    queue_per_reviewer = max(
        1,
        _safe_int(review_shards.get("max_queue_depth_per_active_reviewer"))
        or _safe_int(backpressure.get("review_queue_depth_per_active_reviewer"))
        or 2,
    )
    review_capacity_budget = active_review_workers * queue_per_reviewer
    queued_jury_jobs = max(
        _safe_int(summary.get("queued_jury_jobs")),
        _safe_int(jury_telemetry.get("queued_jury_jobs")),
    )
    blocked_on_jury = max(
        _safe_int(summary.get("blocked_on_jury_workers")),
        _safe_int(jury_telemetry.get("blocked_total_workers")),
    )
    review_cap = max(0, review_capacity_budget - max(0, queued_jury_jobs + blocked_on_jury - review_capacity_budget))
    review_cap = min(review_cap or review_capacity_budget, _safe_int(plane_caps.get("review_shard_cap"), review_capacity_budget or 1))

    audit_lane_name = str(audit_fabric.get("lane") or "audit_shard").strip() or "audit_shard"
    audit_lane_row = capacity_by_lane.get(audit_lane_name) or {}
    audit_lane_observed = bool(audit_lane_row)
    audit_ready_slots = max(0, _safe_int(audit_lane_row.get("ready_slots")))
    active_audit_workers = max(
        _safe_int(summary.get("active_audit_workers")),
        audit_ready_slots,
    )
    audit_parallelism = max(_safe_int(audit_fabric.get("target_parallelism"), 1), _safe_int(audit_fabric.get("service_floor"), 1))
    if active_audit_workers <= 0 and not audit_lane_observed:
        active_audit_workers = audit_parallelism
    audit_plane_cap = max(0, _safe_int(plane_caps.get("audit_shard_cap"), audit_parallelism))
    open_incidents = _safe_int(summary.get("open_incidents"))
    yellow_threshold = max(1, _safe_int(audit_debt.get("open_incidents_yellow"), 8))
    red_threshold = max(yellow_threshold, _safe_int(audit_debt.get("open_incidents_red"), 16))
    if active_audit_workers <= 0 or audit_plane_cap <= 0:
        audit_cap = 0
    elif open_incidents >= red_threshold:
        audit_cap = min(
            active_audit_workers,
            audit_plane_cap,
            max(1, _safe_int(audit_fabric.get("service_floor"), 1)),
        )
    elif open_incidents >= yellow_threshold:
        audit_cap = min(
            active_audit_workers,
            audit_plane_cap,
            max(1, audit_parallelism),
        )
    else:
        audit_cap = min(active_audit_workers, audit_plane_cap)

    project_safety_cap = 0
    active_pool_contracts: List[Dict[str, Any]] = []
    for project in projects:
        project_id = str(project.get("id") or "").strip()
        config_project = config_projects.get(project_id, {})
        raw_contract = dict(project.get("booster_pool_contract") or config_project.get("booster_pool_contract") or {})
        contract = _merged_project_pool_contract(raw_contract, booster_pools)
        if not contract:
            continue
        cap = max(0, _effective_project_safety_cap(contract))
        project_safety_cap += cap
        active_pool_contracts.append(
            {
                "project_id": project_id,
                "pool": str(contract.get("pool") or "").strip(),
                "authority_lane": str(contract.get("authority_lane") or "").strip(),
                "booster_lane": str(contract.get("booster_lane") or "").strip(),
                "rescue_lane": str(contract.get("rescue_lane") or "").strip(),
                "project_safety_cap": cap,
            }
        )
    if project_safety_cap <= 0:
        project_safety_cap = max(1, _safe_int(plane_caps.get("global_booster_cap"), 1))

    finite_caps = [
        item
        for item in [
            credit_cap_until_next_topup,
            credit_cap_until_cycle_end,
            slot_cap,
            useful_work_cap,
            scope_cap,
            review_cap,
            audit_cap,
            project_safety_cap,
            _safe_int(plane_caps.get("global_booster_cap"), 0) or None,
        ]
        if item is not None
    ]
    effective_booster_cap = max(0, min(finite_caps)) if finite_caps else 0

    typed_findings: List[Dict[str, Any]] = []
    if credit_cap_until_next_topup is not None and credit_cap_until_next_topup < max(1, slot_cap):
        typed_findings.append(
            _typed_finding(
                "credit_runway_risk",
                "high" if credit_cap_until_next_topup <= 0 else "medium",
                "Credit runway is tighter than the available booster slots before the next top-up window.",
                cap_name="credit_cap_until_next_topup",
                observed_value=credit_cap_until_next_topup,
            )
        )
    if useful_work_cap <= 0 and active_boosters > 0:
        typed_findings.append(
            _typed_finding(
                "booster_idle",
                "medium",
                "Booster capacity is active without dispatchable premium work depth.",
                cap_name="useful_work_cap",
                observed_value=useful_work_cap,
            )
        )
    if scope_cap is not None and scope_cap < useful_work_cap:
        typed_findings.append(
            _typed_finding(
                "scope_contention",
                "medium" if scope_cap > 0 else "high",
                "Conflict-free package scope is tighter than raw useful work depth.",
                cap_name="scope_cap",
                observed_value=scope_cap,
            )
        )
    if review_cap < max(1, slot_cap):
        typed_findings.append(
            _typed_finding(
                "review_backpressure",
                "medium" if review_cap > 0 else "high",
                "Review fabric is the tighter constraint than raw booster slot availability.",
                cap_name="review_cap",
                observed_value=review_cap,
            )
        )
    if open_incidents >= yellow_threshold:
        typed_findings.append(
            _typed_finding(
                "audit_debt",
                "high" if open_incidents >= red_threshold else "medium",
                "Open incident debt is high enough to constrain writer scaling.",
                cap_name="audit_cap",
                observed_value=open_incidents,
            )
        )
    if degraded_slots > 0:
        typed_findings.append(
            _typed_finding(
                "slot_probe_stale",
                "medium",
                "One or more booster-lane slots are degraded or cooling down.",
                cap_name="slot_cap",
                observed_value=degraded_slots,
            )
        )
    if _safe_int(summary.get("blocked_unresolved_incidents")) > 0 or _safe_int(summary.get("coverage_pressure_projects")) > 0:
        typed_findings.append(
            _typed_finding(
                "contract_drift",
                "medium",
                "Runtime blockers or coverage pressure indicate drift between contracts and dispatchable truth.",
                cap_name="project_safety_cap",
                observed_value=_safe_int(summary.get("blocked_unresolved_incidents")) + _safe_int(summary.get("coverage_pressure_projects")),
            )
        )

    caps = {
        "credit_cap_until_next_topup": {
            "value": credit_cap_until_next_topup,
            "basis": "hours_remaining_at_current_pace_no_topup vs hours_until_next_topup + reserve_buffer",
        },
        "credit_cap_until_cycle_end": {
            "value": credit_cap_until_cycle_end,
            "basis": "days_remaining_including_next_topup_at_7d_avg vs cycle_end_horizon",
        },
        "slot_cap": {
            "value": slot_cap,
            "basis": "ready booster-lane slots",
        },
        "useful_work_cap": {
            "value": useful_work_cap,
            "basis": "premium queue depth plus eligible paid-lane project count and ready work packages",
        },
        "scope_cap": {
            "value": scope_cap,
            "basis": "simultaneously dispatchable non-overlapping work packages",
        },
        "review_cap": {
            "value": review_cap,
            "basis": "observed review shard supply vs queued jury debt",
        },
        "audit_cap": {
            "value": audit_cap,
            "basis": "observed audit shard supply vs open incidents",
        },
        "project_safety_cap": {
            "value": project_safety_cap,
            "basis": "sum of active project booster-pool contracts",
        },
    }
    limiting_cap_name = next(
        (
            name
            for name, item in caps.items()
            if item.get("value") is not None and int(item.get("value") or 0) == effective_booster_cap
        ),
        "unknown",
    )

    return {
        "contract_name": str(quartermaster.get("contract_name") or DEFAULT_CONTRACT_NAME),
        "contract_version": str(quartermaster.get("contract_version") or DEFAULT_CONTRACT_VERSION),
        "generated_at": iso(current_now),
        "mode": str(quartermaster.get("mode") or "observe_only"),
        "runtime_authority": {
            "dispatcher": "fleet-controller",
            "capacity_compiler": "fleet-quartermaster",
            "driver": driver,
            "routing_contract": "static_lane_families",
            "dynamic_instances": "fleet_reconcile",
        },
        "controller_tick": {
            "driver": driver,
            "baseline_tick_seconds": baseline_tick_seconds,
            "event_tick_min_seconds": event_tick_min_seconds,
            "plan_ttl_seconds": plan_ttl_seconds,
            "max_scale_up_per_tick": max_scale_up_per_tick,
            "max_scale_down_per_tick": max_scale_down_per_tick,
            "min_worker_dwell_seconds": min_worker_dwell_seconds,
            "idle_drain_seconds": idle_drain_seconds,
            "triggers": trigger_ids,
        },
        "telemetry_sources": {
            "provider_credit": {
                "provider": telemetry_provider,
                "onemin_manager": onemin_manager,
                "query_mode": onemin_query_mode,
            }
        },
        "objectives": {
            "hard_constraint": "survive_until_next_topup",
            "soft_objective": "consume_efficiently_until_cycle_end",
        },
        "caps": caps,
        "effective_booster_cap": effective_booster_cap,
        "limiting_cap": limiting_cap_name,
        "lane_targets": {
            "core_authority": min(_safe_int(plane_caps.get("core_authority_cap"), 1), max(1, effective_booster_cap or 1)),
            "core_booster": effective_booster_cap,
            "core_rescue": min(_safe_int(plane_caps.get("core_rescue_cap"), 1), max(1, project_safety_cap)),
            "review_shard": max(0, min(_safe_int(plane_caps.get("review_shard_cap"), review_cap), max(0, review_cap))),
            "audit_shard": max(0, min(_safe_int(plane_caps.get("audit_shard_cap"), audit_cap), max(0, audit_cap))),
        },
        "runway": {
            "hours_until_next_topup": hours_until_next_topup,
            "hours_remaining_no_topup": hours_remaining_no_topup,
            "days_remaining_7d_avg": days_remaining_7d_avg,
            "cycle_days_remaining": round(cycle_days_remaining, 2),
            "reserve_buffer_hours": reserve_buffer_hours,
            "cycle_reserve_percent": cycle_reserve_percent,
        },
        "booster_pools": [
            {
                "pool": pool_name,
                "funding": str(pool.get("funding") or "").strip(),
                "worker_lane": str(pool.get("worker_lane") or "").strip(),
                "authority_lane": str(pool.get("authority_lane") or "").strip(),
                "rescue_lane": str(pool.get("rescue_lane") or "").strip(),
                "dispatch_classes": list(pool.get("dispatch_classes") or []),
                "lease": {
                    "require_credit_lease": bool(((pool.get("lease") or {}).get("require_credit_lease"))),
                    "require_work_lease": bool(((pool.get("lease") or {}).get("require_work_lease"))),
                    "require_scope_lease": bool(((pool.get("lease") or {}).get("require_scope_lease"))),
                },
            }
            for pool_name, pool in booster_pools.items()
            if isinstance(pool, dict)
        ],
        "active_project_contracts": active_pool_contracts,
        "typed_findings": typed_findings,
        "inputs": {
            "active_boosters": active_boosters,
            "premium_queue_depth": premium_queue_depth,
            "ready_work_packages": ready_work_packages,
            "scope_cap": scope_cap,
            "queued_jury_jobs": queued_jury_jobs,
            "blocked_on_jury_workers": blocked_on_jury,
            "open_incidents": open_incidents,
            "ready_slots": ready_slots,
            "configured_slots": configured_slots,
            "degraded_slots": degraded_slots,
        },
        "notes": [
            (
                "Deterministic enforced capacity plan. Quartermaster compiles desired capacity while fleet-controller remains the sole runtime dispatcher and reconciler."
                if str(quartermaster.get("mode") or "observe_only").strip().lower() != "observe_only"
                else "Deterministic observe-only capacity plan. Quartermaster stays a capacity compiler and does not own runtime spawning."
            ),
            f"Controller tick driver is {driver}; lane families stay static while Fleet reconciles dynamic worker and lease instances.",
            f"1min telemetry is expected from {telemetry_provider} via the {onemin_manager} manager ({onemin_query_mode}), not direct BrowserAct runtime orchestration.",
            "Booster admission requires capacity, useful work, and non-conflicting package scope; scope leases are treated as a first-class cap.",
            "Studio remains intentionally serial; this plan governs booster, review, and audit pools below the design plane.",
        ],
    }
