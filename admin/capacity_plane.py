from __future__ import annotations

import datetime as dt
import math
import pathlib
from typing import Any, Dict, List, Optional

import yaml


UTC = dt.timezone.utc
DEFAULT_CONTRACT_NAME = "fleet.capacity_plan"
DEFAULT_CONTRACT_VERSION = "2026-03-22"
PROTECTED_OPERATOR_ACCOUNT_CLASS = "protected_operator"
PARTICIPANT_FUNDED_ACCOUNT_CLASS = "participant_funded"
OPERATOR_FUNDED_ACCOUNT_CLASS = "operator_funded"
UNCLASSIFIED_CHATGPT_ACCOUNT_CLASS = "unclassified_chatgpt"
DEFAULT_GLOBAL_ACCOUNT_POLICY = {
    "protected_owner_ids": ["archon.megalon", "the.girscheles", "tibor.girschele"],
    "classes": {
        PROTECTED_OPERATOR_ACCOUNT_CLASS: {
            "drain_policy": "never",
            "allowed_roles": ["studio", "core_authority", "jury", "core_rescue", "emergency_fallback"],
        },
        PARTICIPANT_FUNDED_ACCOUNT_CLASS: {
            "drain_policy": "first",
            "eligible_pools": ["participant_burst"],
            "requires": ["explicit_consent", "valid_token_pool", "work_lease", "scope_lease"],
        },
        OPERATOR_FUNDED_ACCOUNT_CLASS: {
            "drain_policy": "remainder",
            "eligible_pools": ["core_booster", "reserve_rescue"],
            "requires": ["credit_lease", "work_lease", "scope_lease"],
        },
        UNCLASSIFIED_CHATGPT_ACCOUNT_CLASS: {
            "drain_policy": "never",
            "requires": ["explicit_classification"],
        },
    },
}


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


def _safe_int_first(*values: Any, default: int = 0) -> int:
    for value in values:
        if value not in (None, ""):
            return _safe_int(value, default)
    return int(default)


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


def _normalize_global_account_policy(raw: Any) -> Dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    merged = {
        "protected_owner_ids": [
            str(item or "").strip()
            for item in source.get("protected_owner_ids") or DEFAULT_GLOBAL_ACCOUNT_POLICY["protected_owner_ids"]
            if str(item or "").strip()
        ],
        "classes": {},
    }
    raw_classes = source.get("classes") if isinstance(source.get("classes"), dict) else {}
    for class_name, defaults in DEFAULT_GLOBAL_ACCOUNT_POLICY["classes"].items():
        class_cfg = dict(defaults)
        override = raw_classes.get(class_name) if isinstance(raw_classes.get(class_name), dict) else {}
        class_cfg.update(dict(override))
        class_cfg["allowed_roles"] = [
            str(item or "").strip()
            for item in class_cfg.get("allowed_roles") or defaults.get("allowed_roles") or []
            if str(item or "").strip()
        ]
        class_cfg["eligible_pools"] = [
            str(item or "").strip()
            for item in class_cfg.get("eligible_pools") or defaults.get("eligible_pools") or []
            if str(item or "").strip()
        ]
        class_cfg["requires"] = [
            str(item or "").strip()
            for item in class_cfg.get("requires") or defaults.get("requires") or []
            if str(item or "").strip()
        ]
        merged["classes"][class_name] = class_cfg
    return merged


def _account_owner_id(account_cfg: Dict[str, Any], alias: str) -> str:
    explicit = str((account_cfg or {}).get("owner_id") or "").strip()
    if explicit:
        return explicit
    clean_alias = str(alias or "").strip().lower()
    default_owner_map = {
        "acct-chatgpt-archon": "archon.megalon",
        "acct-chatgpt-b": "the.girscheles",
        "acct-chatgpt-core": "tibor.girschele",
    }
    return default_owner_map.get(clean_alias, "")


def _account_classification(
    account_cfg: Dict[str, Any],
    *,
    alias: str,
    policy: Dict[str, Any],
    participant_lane_aliases: set[str],
) -> str:
    explicit = str((account_cfg or {}).get("account_class") or "").strip().lower()
    if explicit:
        return explicit
    owner_category = str((account_cfg or {}).get("owner_category") or "").strip().lower()
    if alias in participant_lane_aliases or owner_category == "participant" or bool((account_cfg or {}).get("participant_burst_lane")):
        return PARTICIPANT_FUNDED_ACCOUNT_CLASS
    owner_id = _account_owner_id(account_cfg, alias)
    protected = {
        str(item or "").strip()
        for item in policy.get("protected_owner_ids") or []
        if str(item or "").strip()
    }
    if owner_id and owner_id in protected:
        return PROTECTED_OPERATOR_ACCOUNT_CLASS
    funding_class = str((account_cfg or {}).get("funding_class") or "").strip().lower()
    if funding_class:
        return funding_class
    auth_kind = str((account_cfg or {}).get("auth_kind") or "").strip().lower()
    if auth_kind == "ea":
        return OPERATOR_FUNDED_ACCOUNT_CLASS
    if auth_kind in {"chatgpt_auth_json", "auth_json"}:
        return UNCLASSIFIED_CHATGPT_ACCOUNT_CLASS
    return "operator"


def _account_has_explicit_consent(account_cfg: Dict[str, Any], *, alias: str, participant_lane_aliases: set[str]) -> bool:
    if "explicit_consent" in (account_cfg or {}):
        return bool((account_cfg or {}).get("explicit_consent"))
    return alias in participant_lane_aliases or bool((account_cfg or {}).get("participant_burst_lane"))


def _account_token_pool_state(account_cfg: Dict[str, Any], pool_row: Dict[str, Any], *, alias: str, participant_lane_aliases: set[str]) -> str:
    explicit = str((account_cfg or {}).get("token_pool_state") or "").strip().lower()
    if explicit:
        return explicit
    if alias not in participant_lane_aliases and not bool((account_cfg or {}).get("participant_burst_lane")):
        return "n/a"
    pool_state = str((pool_row or {}).get("pool_state") or "").strip().lower()
    return "valid" if pool_state == "ready" else "invalid"


def _participant_pool_snapshot(
    *,
    accounts_cfg: Dict[str, Any],
    account_policy: Dict[str, Any],
    account_pools: List[Dict[str, Any]],
    participant_lanes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    pool_by_alias = {
        str(item.get("alias") or "").strip(): dict(item)
        for item in account_pools
        if str(item.get("alias") or "").strip()
    }
    participant_lane_aliases = {
        str(item.get("account_alias") or "").strip()
        for item in participant_lanes
        if str(item.get("account_alias") or "").strip()
    }
    aliases: set[str] = set(participant_lane_aliases)
    for alias, account_cfg in accounts_cfg.items():
        clean_alias = str(alias or "").strip()
        if not clean_alias:
            continue
        if _account_classification(dict(account_cfg or {}), alias=clean_alias, policy=account_policy, participant_lane_aliases=participant_lane_aliases) == PARTICIPANT_FUNDED_ACCOUNT_CLASS:
            aliases.add(clean_alias)
    ready_aliases: List[str] = []
    invalid_aliases: List[str] = []
    missing_consent_aliases: List[str] = []
    for alias in sorted(aliases):
        account_cfg = dict(accounts_cfg.get(alias) or {})
        pool_row = dict(pool_by_alias.get(alias) or {})
        consent_ok = _account_has_explicit_consent(account_cfg, alias=alias, participant_lane_aliases=participant_lane_aliases)
        token_pool_state = _account_token_pool_state(account_cfg, pool_row, alias=alias, participant_lane_aliases=participant_lane_aliases)
        pool_state = str(pool_row.get("pool_state") or "").strip().lower()
        if not consent_ok:
            missing_consent_aliases.append(alias)
        if token_pool_state not in {"valid", "ready"}:
            invalid_aliases.append(alias)
        if consent_ok and token_pool_state in {"valid", "ready"} and pool_state == "ready":
            ready_aliases.append(alias)
    return {
        "participant_account_count": len(aliases),
        "ready_accounts": ready_aliases,
        "invalid_accounts": invalid_aliases,
        "missing_consent_accounts": missing_consent_aliases,
        "drainable": bool(ready_aliases),
        "starved": bool(aliases) and not bool(ready_aliases),
    }


def _account_order_recommendations(
    *,
    account_policy: Dict[str, Any],
    participant_pool: Dict[str, Any],
    credit_waste_risk: bool,
) -> Dict[str, Dict[str, Any]]:
    protected_owner_ids = list(account_policy.get("protected_owner_ids") or [])
    core_booster_preferred = (
        [OPERATOR_FUNDED_ACCOUNT_CLASS, PARTICIPANT_FUNDED_ACCOUNT_CLASS]
        if credit_waste_risk
        else [PARTICIPANT_FUNDED_ACCOUNT_CLASS, OPERATOR_FUNDED_ACCOUNT_CLASS]
    )
    if not participant_pool.get("drainable"):
        core_booster_preferred = [OPERATOR_FUNDED_ACCOUNT_CLASS]
    return {
        "core_booster": {
            "preferred_account_classes": core_booster_preferred,
            "blocked_account_classes": [PROTECTED_OPERATOR_ACCOUNT_CLASS, UNCLASSIFIED_CHATGPT_ACCOUNT_CLASS],
            "credit_waste_override_active": bool(credit_waste_risk),
            "protected_owner_ids": protected_owner_ids,
        },
        "core_authority": {
            "preferred_account_classes": [PROTECTED_OPERATOR_ACCOUNT_CLASS, OPERATOR_FUNDED_ACCOUNT_CLASS],
            "blocked_account_classes": [PARTICIPANT_FUNDED_ACCOUNT_CLASS, UNCLASSIFIED_CHATGPT_ACCOUNT_CLASS],
            "credit_waste_override_active": False,
            "protected_owner_ids": protected_owner_ids,
        },
        "core_rescue": {
            "preferred_account_classes": [PROTECTED_OPERATOR_ACCOUNT_CLASS, OPERATOR_FUNDED_ACCOUNT_CLASS],
            "blocked_account_classes": [PARTICIPANT_FUNDED_ACCOUNT_CLASS, UNCLASSIFIED_CHATGPT_ACCOUNT_CLASS],
            "credit_waste_override_active": False,
            "protected_owner_ids": protected_owner_ids,
        },
        "jury": {
            "preferred_account_classes": [PROTECTED_OPERATOR_ACCOUNT_CLASS, OPERATOR_FUNDED_ACCOUNT_CLASS],
            "blocked_account_classes": [PARTICIPANT_FUNDED_ACCOUNT_CLASS, UNCLASSIFIED_CHATGPT_ACCOUNT_CLASS],
            "credit_waste_override_active": False,
            "protected_owner_ids": protected_owner_ids,
        },
    }


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
    account_pools = list(status.get("account_pools") or cockpit.get("account_pools") or [])
    participant_lanes = list(status.get("participant_lanes") or cockpit.get("participant_lanes") or [])
    config_root = dict(status.get("config") or {})
    accounts_cfg = dict(config_root.get("accounts") or {})
    account_policy = _normalize_global_account_policy(config_root.get("account_policy") or {})
    config_projects = {
        str(item.get("id") or "").strip(): dict(item)
        for item in (config_root.get("projects") or [])
        if str(item.get("id") or "").strip()
    }
    quartermaster = dict(capacity_configs.get("quartermaster") or {})
    booster_pools = dict(capacity_configs.get("booster_pools") or {})
    review_fabric = dict((capacity_configs.get("review_fabric") or {}).get("default") or {})
    audit_fabric = dict((capacity_configs.get("audit_fabric") or {}).get("default") or {})

    incidents_cfg = dict(quartermaster.get("incidents") or {})
    telemetry_cfg = dict(quartermaster.get("telemetry") or {})
    credit_cfg = dict(quartermaster.get("credit") or {})
    useful_work_cfg = dict(quartermaster.get("useful_work") or {})
    service_floor_cfg = dict(quartermaster.get("service_floor") or {})
    ramp_cfg = dict(quartermaster.get("ramp") or {})
    policy_cfg = dict((config_root.get("policies") or {}).get("capacity_plane") or {})
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
    participant_pool = _participant_pool_snapshot(
        accounts_cfg=accounts_cfg,
        account_policy=account_policy,
        account_pools=account_pools,
        participant_lanes=participant_lanes,
    )

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
    ready_package_count = max(0, _safe_int_first(work_packages.get("ready_booster_packages"), work_packages.get("ready_packages")))
    ready_dispatchable_packages = max(
        0,
        _safe_int_first(work_packages.get("ready_booster_scope_cap"), work_packages.get("ready_scope_cap"), ready_package_count),
    )
    active_package_count = max(0, _safe_int_first(work_packages.get("active_booster_packages"), work_packages.get("active_packages")))
    waiting_dependency_packages = max(
        0,
        _safe_int_first(work_packages.get("waiting_dependency_booster_packages"), work_packages.get("waiting_dependency_packages")),
    )
    blocked_packages = max(0, _safe_int_first(work_packages.get("blocked_booster_packages"), work_packages.get("blocked_packages")))
    eligible_booster_projects = _eligible_project_count(projects, booster_worker_lanes)
    ready_work_packages = max(
        ready_package_count,
        ready_dispatchable_packages,
    )
    useful_work_cap = max(
        premium_queue_depth,
        ready_work_packages,
        eligible_booster_projects,
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

    sustainable_caps = [
        item
        for item in [
            credit_cap_until_next_topup,
            credit_cap_until_cycle_end,
            slot_cap,
            review_cap,
            audit_cap,
            project_safety_cap,
            _safe_int(plane_caps.get("global_booster_cap"), 0) or None,
        ]
        if item is not None
    ]
    sustainable_booster_cap = max(0, min(sustainable_caps)) if sustainable_caps else 0
    credit_waste_risk = bool(
        participant_pool.get("drainable")
        and days_remaining_7d_avg is not None
        and cycle_days_remaining > 0
        and days_remaining_7d_avg > (cycle_days_remaining * (1.0 + max(10.0, cycle_reserve_percent) / 100.0))
    )
    account_order_recommendations = _account_order_recommendations(
        account_policy=account_policy,
        participant_pool=participant_pool,
        credit_waste_risk=credit_waste_risk,
    )
    ready_reserve_multiplier = max(1, _safe_int(useful_work_cfg.get("ready_reserve_multiplier"), 2))
    minimum_ready_packages = max(0, _safe_int(useful_work_cfg.get("minimum_ready_packages"), 2))
    packages_per_authority_worker = max(1, _safe_int(useful_work_cfg.get("packages_per_authority_worker"), 4))
    ready_reserve_step_divisor = max(1, _safe_int(ramp_cfg.get("ready_reserve_step_divisor"), ready_reserve_multiplier))
    minimum_scale_up_step = max(1, _safe_int(ramp_cfg.get("minimum_scale_up_step"), 1))
    booster_work_present = bool(
        ready_dispatchable_packages > 0
        or active_package_count > 0
        or waiting_dependency_packages > 0
        or blocked_packages > 0
        or eligible_booster_projects > 0
    )
    ready_work_reserve_target = 0
    if sustainable_booster_cap > 0 and booster_work_present:
        ready_work_reserve_target = max(
            minimum_ready_packages,
            sustainable_booster_cap * ready_reserve_multiplier,
        )
    ready_work_reserve_shortfall = max(0, ready_work_reserve_target - ready_dispatchable_packages)
    authority_service_floor = max(1, _safe_int(service_floor_cfg.get("core_authority"), 1))
    authority_cap = max(authority_service_floor, _safe_int(plane_caps.get("core_authority_cap"), authority_service_floor))
    authority_target = authority_service_floor
    if ready_work_reserve_shortfall > 0:
        authority_target = min(
            authority_cap,
            max(
                authority_service_floor,
                int(math.ceil(float(ready_work_reserve_shortfall) / float(packages_per_authority_worker))),
            ),
        )

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
    desired_booster_target = effective_booster_cap
    ready_scale_up_budget = max(
        0,
        int(
            math.ceil(
                float(max(0, ready_dispatchable_packages - active_boosters))
                / float(ready_reserve_step_divisor)
            )
        ),
    )
    review_spare_budget = max(0, review_cap - active_boosters)
    audit_spare_budget = max(0, audit_cap - active_boosters)
    booster_scale_up_budget = 0
    if desired_booster_target > active_boosters:
        ramp_limits = [
            max(0, max_scale_up_per_tick),
            max(0, ready_scale_up_budget),
            max(0, max(minimum_scale_up_step, review_spare_budget)) if review_spare_budget > 0 else 0,
            max(0, max(minimum_scale_up_step, audit_spare_budget)) if audit_spare_budget > 0 else 0,
        ]
        booster_scale_up_budget = min(ramp_limits) if ramp_limits else 0
        effective_booster_cap = min(desired_booster_target, active_boosters + booster_scale_up_budget)
    elif desired_booster_target < active_boosters:
        effective_booster_cap = max(desired_booster_target, active_boosters - max_scale_down_per_tick)

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
    if ready_work_reserve_shortfall > 0 and booster_work_present:
        typed_findings.append(
            _typed_finding(
                "booster_supply_starved",
                "high" if ready_dispatchable_packages <= 0 else "medium",
                "Ready booster-safe package supply is below the reserve target, so authority/package feeder work should replenish dispatchable tasks.",
                cap_name="ready_work_reserve_target",
                observed_value=ready_work_reserve_shortfall,
            )
        )
    if participant_pool.get("drainable"):
        typed_findings.append(
            _typed_finding(
                "participant_pool_drainable",
                "info",
                "Participant-funded accounts are healthy and can drain eligible bounded burst work before operator-funded booster lanes.",
                cap_name="ready_participant_accounts",
                observed_value=len(participant_pool.get("ready_accounts") or []),
            )
        )
    if participant_pool.get("starved"):
        typed_findings.append(
            _typed_finding(
                "participant_pool_starved",
                "medium",
                "Participant-funded accounts exist but none are currently drainable for bounded burst work.",
                cap_name="participant_account_count",
                observed_value=participant_pool.get("participant_account_count"),
            )
        )
    if participant_pool.get("invalid_accounts"):
        typed_findings.append(
            _typed_finding(
                "participant_token_pool_invalid",
                "medium",
                "One or more participant-funded accounts are missing a healthy token pool or ready auth posture.",
                cap_name="participant_invalid_accounts",
                observed_value=len(participant_pool.get("invalid_accounts") or []),
            )
        )
    if participant_pool.get("missing_consent_accounts"):
        typed_findings.append(
            _typed_finding(
                "participant_consent_missing",
                "high",
                "One or more participant-funded accounts are missing explicit consent and must stay out of burst dispatch.",
                cap_name="participant_missing_consent_accounts",
                observed_value=len(participant_pool.get("missing_consent_accounts") or []),
            )
        )
    if credit_waste_risk:
        typed_findings.append(
            _typed_finding(
                "onemin_credit_waste_risk",
                "medium",
                "Operator-funded 1min credits appear likely to outlast the current cycle, so quartermaster should prefer burning that pool before it expires.",
                cap_name="credit_cap_until_cycle_end",
                observed_value=credit_cap_until_cycle_end,
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
        "ready_work_reserve_target": {
            "value": ready_work_reserve_target,
            "basis": "sustainable booster target multiplied by the configured ready package reserve",
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
        "ramp_damping": {
            "ready_reserve_step_divisor": ready_reserve_step_divisor,
            "minimum_scale_up_step": minimum_scale_up_step,
            "desired_core_booster_target": desired_booster_target,
            "ramped_core_booster_target": effective_booster_cap,
            "booster_scale_up_budget": booster_scale_up_budget,
            "review_spare_budget": review_spare_budget,
            "audit_spare_budget": audit_spare_budget,
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
            "core_authority": authority_target,
            "core_booster": effective_booster_cap,
            "core_rescue": min(_safe_int(plane_caps.get("core_rescue_cap"), 1), max(1, project_safety_cap)),
            "review_shard": max(0, min(_safe_int(plane_caps.get("review_shard_cap"), review_cap), max(0, review_cap))),
            "audit_shard": max(0, min(_safe_int(plane_caps.get("audit_shard_cap"), audit_cap), max(0, audit_cap))),
        },
        "account_order_recommendations": account_order_recommendations,
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
            "ready_package_count": ready_package_count,
            "ready_work_packages": ready_work_packages,
            "ready_dispatchable_packages": ready_dispatchable_packages,
            "active_packages": active_package_count,
            "waiting_dependency_packages": waiting_dependency_packages,
            "blocked_packages": blocked_packages,
            "eligible_booster_projects": eligible_booster_projects,
            "participant_account_count": participant_pool.get("participant_account_count"),
            "ready_participant_accounts": len(participant_pool.get("ready_accounts") or []),
            "participant_invalid_accounts": len(participant_pool.get("invalid_accounts") or []),
            "participant_missing_consent_accounts": len(participant_pool.get("missing_consent_accounts") or []),
            "credit_waste_risk": credit_waste_risk,
            "scope_cap": scope_cap,
            "queued_jury_jobs": queued_jury_jobs,
            "blocked_on_jury_workers": blocked_on_jury,
            "open_incidents": open_incidents,
            "ready_slots": ready_slots,
            "configured_slots": configured_slots,
            "degraded_slots": degraded_slots,
            "sustainable_booster_cap": sustainable_booster_cap,
            "ready_work_reserve_target": ready_work_reserve_target,
            "ready_work_reserve_shortfall": ready_work_reserve_shortfall,
            "packages_per_authority_worker": packages_per_authority_worker,
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
