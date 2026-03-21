from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set


SPARK_MODEL = "gpt-5.3-codex-spark"
DEFAULT_LANES: Dict[str, Dict[str, Any]] = {
    "easy": {
        "label": "EA Easy",
        "authority": "run",
        "merge_protected_branches": False,
        "escalation_only": False,
        "worker_profile": "easy",
        "codex_mode": "easy",
        "runtime_model": "ea-gemini-flash",
        "provider_hint_order": ["gemini_vortex"],
        "reviewer_lane": "review_light",
        "budget_bias": "cheap",
        "latency_class": "priority",
    },
    "repair": {
        "label": "EA Repair",
        "authority": "run",
        "merge_protected_branches": False,
        "escalation_only": False,
        "worker_profile": "repair",
        "codex_mode": "easy",
        "runtime_model": "ea-coder-fast",
        "provider_hint_order": ["gemini_vortex", "magixai"],
        "reviewer_lane": "review_light",
        "budget_bias": "cheap",
        "latency_class": "normal",
    },
    "groundwork": {
        "label": "EA Groundwork",
        "authority": "run",
        "merge_protected_branches": False,
        "escalation_only": False,
        "worker_profile": "groundwork",
        "codex_mode": "easy",
        "runtime_model": "ea-groundwork-gemini",
        "provider_hint_order": ["gemini_vortex"],
        "reviewer_lane": "review_light",
        "budget_bias": "cheap",
        "latency_class": "batch",
        "async_only": True,
    },
    "review_light": {
        "label": "EA Review Light",
        "authority": "audit",
        "merge_protected_branches": False,
        "escalation_only": False,
        "worker_profile": "review_light",
        "codex_mode": "jury",
        "runtime_model": "ea-review-light",
        "provider_hint_order": ["gemini_vortex", "chatplayground"],
        "reviewer_lane": "core",
        "budget_bias": "cheap",
        "latency_class": "batch",
        "async_only": True,
    },
    "core": {
        "label": "EA Core",
        "authority": "run",
        "merge_protected_branches": False,
        "escalation_only": False,
        "worker_profile": "core",
        "codex_mode": "core",
        "runtime_model": "ea-coder-hard",
        "provider_hint_order": ["onemin"],
        "reviewer_lane": "core",
        "budget_bias": "standard",
        "latency_class": "normal",
    },
    "jury": {
        "label": "Jury",
        "authority": "approve_merge",
        "merge_protected_branches": True,
        "escalation_only": True,
        "worker_profile": "audit",
        "codex_mode": "jury",
        "runtime_model": "ea-audit-jury",
        "provider_hint_order": ["gemini_vortex", "chatplayground"],
        "reviewer_lane": "core",
        "budget_bias": "premium",
        "latency_class": "batch",
        "async_only": True,
    },
    "survival": {
        "label": "EA Survival",
        "authority": "run",
        "merge_protected_branches": False,
        "escalation_only": True,
        "worker_profile": "survival",
        "codex_mode": "survival",
        "runtime_model": "ea-coder-survival",
        "provider_hint_order": ["gemini_vortex", "chatplayground"],
        "reviewer_lane": "core",
        "budget_bias": "cheap",
        "latency_class": "batch",
        "async_only": True,
    },
}
VALID_TASK_DIFFICULTIES = {"auto", "easy", "medium", "hard"}
VALID_TASK_RISK_LEVELS = {"auto", "low", "medium", "high"}
VALID_BRANCH_POLICIES = {"auto", "feature_branch", "review_branch", "protected_branch", "no_merge"}
VALID_ACCEPTANCE_LEVELS = {"auto", "draft", "verified", "reviewed", "merge_ready"}
VALID_BUDGET_CLASSES = {"auto", "cheap", "standard", "premium"}
VALID_LATENCY_CLASSES = {"auto", "batch", "normal", "priority"}
VALID_DISPATCHABILITY_STATES = {"design_only", "blocked", "dispatchable"}
VALID_WORKFLOW_KINDS = {"default", "groundwork_review_loop"}
BLOCKING_WARNING_KINDS = {
    "unknown_account_alias",
    "spark_policy_impossible",
    "review_mode_drift",
    "unknown_lane",
    "unserved_task_lane",
    "unserved_reviewer_lane",
}


def _text_list(values: Any) -> List[str]:
    if isinstance(values, (list, tuple)):
        return [str(item).strip() for item in values if str(item).strip()]
    value = str(values or "").strip()
    return [value] if value else []


def _bool_flag(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    clean = str(value).strip().lower()
    if not clean:
        return default
    if clean in {"1", "true", "yes", "y", "on", "required"}:
        return True
    if clean in {"0", "false", "no", "n", "off"}:
        return False
    return bool(value)


def _normalize_requirement_name(value: Any) -> str:
    clean = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return clean


def _normalized_requirement_list(values: Any) -> List[str]:
    requirements: List[str] = []
    for value in _text_list(values):
        clean = _normalize_requirement_name(value)
        if clean and clean not in requirements:
            requirements.append(clean)
    return requirements


def normalize_lane_name(value: Any, *, default: str = "core") -> str:
    clean = str(value or "").strip().lower()
    return clean if clean in DEFAULT_LANES else str(default or "core").strip().lower()


def project_account_policy(project_cfg: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(project_cfg.get("account_policy") or {})
    raw.setdefault("preferred_accounts", list(project_cfg.get("accounts") or []))
    raw.setdefault("burst_accounts", [])
    raw.setdefault("reserve_accounts", [])
    raw.setdefault("emergency_chatgpt_fallback_accounts", [])
    raw.setdefault("allow_chatgpt_accounts", True)
    raw.setdefault("allow_api_accounts", True)
    raw.setdefault("pin_special_accounts", False)
    return raw


def ordered_project_aliases(project_cfg: Dict[str, Any]) -> List[str]:
    policy = project_account_policy(project_cfg)
    aliases = (
        _text_list(policy.get("preferred_accounts"))
        + _text_list(policy.get("burst_accounts"))
        + _text_list(policy.get("reserve_accounts"))
        + _text_list(project_cfg.get("accounts"))
    )
    seen: Set[str] = set()
    ordered: List[str] = []
    for alias in aliases:
        if alias in seen:
            continue
        seen.add(alias)
        ordered.append(alias)
    return ordered


def expand_serviceable_lanes(
    allowed_lanes: Any,
    *,
    task_meta: Optional[Dict[str, Any]] = None,
    lanes: Any = None,
) -> List[str]:
    lane_cfg = normalize_lanes_config(lanes)
    lane_names = set(lane_cfg)
    normalized: List[str] = []
    for lane in _text_list(allowed_lanes):
        clean = str(lane or "").strip().lower()
        if clean in lane_names and clean not in normalized:
            normalized.append(clean)
    meta = task_meta if isinstance(task_meta, dict) else {}
    if _bool_flag(meta.get("protected_runtime")):
        return ["core"] if "core" in lane_names else [lane for lane in normalized if lane == "core"]
    if "easy" in normalized and "groundwork" in lane_names and "groundwork" not in normalized:
        insert_at = normalized.index("easy") + 1
        normalized = [*normalized[:insert_at], "groundwork", *normalized[insert_at:]]
    return normalized


def infer_account_lane(account_cfg: Dict[str, Any], *, alias: str = "") -> str:
    explicit = str((account_cfg or {}).get("lane") or "").strip().lower()
    if explicit in DEFAULT_LANES:
        return explicit
    model_aliases = {str(item).strip().lower() for item in _text_list((account_cfg or {}).get("codex_model_aliases"))}
    if "ea-review-light" in model_aliases:
        return "review_light"
    if "ea-groundwork" in model_aliases or "ea-groundwork-gemini" in model_aliases:
        return "groundwork"
    if "ea-audit-jury" in model_aliases:
        return "jury"
    if "ea-coder-survival" in model_aliases:
        return "survival"
    if "ea-coder-fast" in model_aliases and "ea-coder-hard" not in model_aliases and "ea-coder-best" not in model_aliases:
        return "repair"
    if alias.startswith("acct-ea-") and ("ea-coder-hard" in model_aliases or "ea-coder-best" in model_aliases):
        return "core"
    if alias.startswith("acct-ea-"):
        return "easy"
    return "core"


def normalize_lanes_config(raw_lanes: Any) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    raw = raw_lanes if isinstance(raw_lanes, dict) else {}
    for lane_name, defaults in DEFAULT_LANES.items():
        lane_cfg = dict(defaults)
        lane_cfg.update(dict(raw.get(lane_name) or {}))
        lane_cfg["id"] = lane_name
        lane_cfg["label"] = str(lane_cfg.get("label") or defaults.get("label") or lane_name.title()).strip()
        lane_cfg["authority"] = str(lane_cfg.get("authority") or defaults.get("authority") or "run").strip().lower()
        lane_cfg["merge_protected_branches"] = bool(
            lane_cfg.get("merge_protected_branches", defaults.get("merge_protected_branches", False))
        )
        lane_cfg["escalation_only"] = bool(lane_cfg.get("escalation_only", defaults.get("escalation_only", False)))
        lane_cfg["worker_profile"] = str(lane_cfg.get("worker_profile") or defaults.get("worker_profile") or lane_name).strip()
        lane_cfg["codex_mode"] = str(lane_cfg.get("codex_mode") or defaults.get("codex_mode") or lane_name).strip()
        lane_cfg["runtime_model"] = str(lane_cfg.get("runtime_model") or defaults.get("runtime_model") or "").strip()
        lane_cfg["provider_hint_order"] = _text_list(
            lane_cfg.get("provider_hint_order") or defaults.get("provider_hint_order") or []
        )
        lane_cfg["reviewer_lane"] = normalize_lane_name(
            lane_cfg.get("reviewer_lane") or defaults.get("reviewer_lane") or "core",
            default="core",
        )
        lane_cfg["budget_bias"] = str(lane_cfg.get("budget_bias") or defaults.get("budget_bias") or "standard").strip().lower()
        lane_cfg["latency_class"] = str(
            lane_cfg.get("latency_class") or defaults.get("latency_class") or "normal"
        ).strip().lower()
        lane_cfg["async_only"] = bool(lane_cfg.get("async_only", defaults.get("async_only", False)))
        normalized[lane_name] = lane_cfg
    return normalized


def task_slice_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("title", "text", "slice", "task", "name", "summary"):
            text = str(value.get(key) or "").strip()
            if text:
                return text
    text = str(value or "").strip()
    return text


def normalize_task_queue_item(value: Any, *, lanes: Any = None) -> Dict[str, Any]:
    lane_cfg = normalize_lanes_config(lanes)
    lane_names = set(lane_cfg)
    if isinstance(value, dict):
        item = dict(value)
    else:
        item = {"title": task_slice_text(value)}
    title = task_slice_text(item)
    difficulty = str(item.get("difficulty") or "auto").strip().lower()
    if difficulty not in VALID_TASK_DIFFICULTIES:
        difficulty = "auto"
    risk_level = str(item.get("risk_level") or item.get("risk") or "auto").strip().lower()
    if risk_level not in VALID_TASK_RISK_LEVELS:
        risk_level = "auto"
    branch_policy = str(item.get("branch_policy") or "auto").strip().lower()
    if branch_policy not in VALID_BRANCH_POLICIES:
        branch_policy = "auto"
    acceptance_level = str(item.get("acceptance_level") or "auto").strip().lower()
    if acceptance_level not in VALID_ACCEPTANCE_LEVELS:
        acceptance_level = "auto"
    budget_class = str(item.get("budget_class") or "auto").strip().lower()
    if budget_class not in VALID_BUDGET_CLASSES:
        budget_class = "auto"
    latency_class = str(item.get("latency_class") or "auto").strip().lower()
    if latency_class not in VALID_LATENCY_CLASSES:
        latency_class = "auto"
    design_owner = str(item.get("design_owner") or "").strip()
    design_sensitive = _bool_flag(item.get("design_sensitive"))
    architecture_sensitive = _bool_flag(item.get("architecture_sensitive"))
    dispatchability_state = str(item.get("dispatchability_state") or "").strip().lower()
    if dispatchability_state not in VALID_DISPATCHABILITY_STATES:
        if _bool_flag(item.get("design_only")):
            dispatchability_state = "design_only"
        elif _bool_flag(item.get("blocked")):
            dispatchability_state = "blocked"
        else:
            dispatchability_state = "dispatchable"
    groundwork_required = _bool_flag(item.get("groundwork_required"))
    jury_required = _bool_flag(item.get("jury_required"))
    workflow_kind = str(item.get("workflow_kind") or "default").strip().lower()
    if workflow_kind not in VALID_WORKFLOW_KINDS:
        workflow_kind = "default"
    final_reviewer_lane = str(item.get("final_reviewer_lane") or "").strip().lower()
    if final_reviewer_lane not in DEFAULT_LANES:
        final_reviewer_lane = ""
    landing_lane = str(item.get("landing_lane") or "").strip().lower()
    if landing_lane not in DEFAULT_LANES:
        landing_lane = ""
    raw_allowed = [lane for lane in _text_list(item.get("allowed_lanes")) if lane in lane_names]
    try:
        max_review_rounds = int(item.get("max_review_rounds") or 0)
    except Exception:
        max_review_rounds = 0
    first_review_required = _bool_flag(item.get("first_review_required"))
    jury_acceptance_required = _bool_flag(item.get("jury_acceptance_required"))
    allow_credit_burn = _bool_flag(item.get("allow_credit_burn"), default="core" in raw_allowed)
    allow_paid_fast_lane = _bool_flag(item.get("allow_paid_fast_lane"), default="repair" in raw_allowed)
    allow_core_rescue = _bool_flag(item.get("allow_core_rescue"), default=False)
    try:
        core_rescue_after_round = int(item.get("core_rescue_after_round") or 0)
    except Exception:
        core_rescue_after_round = 0
    try:
        review_round = int(item.get("review_round") or 0)
    except Exception:
        review_round = 0
    if review_round < 0:
        review_round = 0
    first_review_complete = _bool_flag(item.get("first_review_complete"))
    accepted_on_round = str(item.get("accepted_on_round") or "").strip().lower()
    needs_core_rescue = _bool_flag(item.get("needs_core_rescue"))
    core_rescue_reason = str(item.get("core_rescue_reason") or "").strip()
    raw_jury_feedback_history = item.get("jury_feedback_history")
    jury_feedback_history = list(raw_jury_feedback_history) if isinstance(raw_jury_feedback_history, list) else []
    issue_fingerprints = list(dict.fromkeys(_text_list(item.get("issue_fingerprints"))))
    protected_runtime = _bool_flag(item.get("protected_runtime"))
    premium_required = _bool_flag(item.get("premium_required"))
    premium_beneficial = _bool_flag(item.get("premium_beneficial"))
    participant_eligible = _bool_flag(
        item.get("participant_eligible"),
        default=premium_required or premium_beneficial,
    )
    operator_override_required = _bool_flag(
        item.get("operator_override_required"),
        default=protected_runtime,
    )
    if workflow_kind == "groundwork_review_loop":
        groundwork_required = True
        jury_required = True
        first_review_required = True if "first_review_required" not in item else first_review_required
        jury_acceptance_required = True if "jury_acceptance_required" not in item else jury_acceptance_required
        allow_credit_burn = False if "allow_credit_burn" not in item else allow_credit_burn
        allow_paid_fast_lane = False if "allow_paid_fast_lane" not in item else allow_paid_fast_lane
        allow_core_rescue = False if "allow_core_rescue" not in item else allow_core_rescue
        if not landing_lane and "jury" in lane_names:
            landing_lane = "jury"
        max_review_rounds = max(1, max_review_rounds or 3)
        core_rescue_after_round = max(1, core_rescue_after_round or max_review_rounds) if allow_core_rescue else 0
        if review_round > max_review_rounds:
            review_round = max_review_rounds
        if review_round > 0 and "first_review_complete" not in item:
            first_review_complete = True
        if needs_core_rescue and core_rescue_after_round > 0 and review_round == 0:
            review_round = min(core_rescue_after_round, max_review_rounds) if max_review_rounds > 0 else core_rescue_after_round
        if needs_core_rescue and not core_rescue_reason:
            core_rescue_reason = (
                "workflow escalation requested"
                if allow_core_rescue
                else "workflow escalation requested, but credit burn is disabled"
            )
    else:
        if accepted_on_round == "core" and not needs_core_rescue:
            needs_core_rescue = False
    signoff_requirements = _normalized_requirement_list(item.get("signoff_requirements"))
    publish_truth_sources = list(dict.fromkeys(_text_list(item.get("publish_truth_sources"))))
    reviewer_lane = normalize_lane_name(item.get("required_reviewer_lane") or item.get("reviewer_lane") or "core")
    if raw_allowed:
        allowed_lanes = list(dict.fromkeys(raw_allowed))
    elif protected_runtime or branch_policy == "protected_branch" or acceptance_level == "merge_ready":
        allowed_lanes = ["core"]
    elif groundwork_required and "groundwork" in lane_names:
        allowed_lanes = ["groundwork", "easy"]
    elif risk_level == "high" or difficulty == "hard":
        allowed_lanes = ["groundwork", "easy"] if "groundwork" in lane_names else ["easy"]
    elif risk_level == "medium" or difficulty == "medium":
        allowed_lanes = ["easy", "groundwork"] if "groundwork" in lane_names else ["easy"]
    else:
        allowed_lanes = ["easy"]
    if not allow_paid_fast_lane:
        allowed_lanes = [lane for lane in allowed_lanes if lane != "repair"]
    elif "repair" in lane_names and "repair" not in allowed_lanes:
        allowed_lanes.append("repair")
    if not allow_credit_burn and not protected_runtime and branch_policy != "protected_branch" and acceptance_level != "merge_ready":
        allowed_lanes = [lane for lane in allowed_lanes if lane != "core"]
    elif "core" in lane_names and "core" not in allowed_lanes:
        allowed_lanes.append("core")
    if participant_eligible and "core" in lane_names and "core" not in allowed_lanes:
        allowed_lanes.append("core")
    if protected_runtime and "core" not in allowed_lanes:
        allowed_lanes = ["core"]
    if branch_policy == "protected_branch" and "core" not in allowed_lanes:
        allowed_lanes = ["core"]
    if acceptance_level == "merge_ready" and "core" not in allowed_lanes:
        allowed_lanes = ["core"]
    if protected_runtime:
        allowed_lanes = [lane for lane in allowed_lanes if lane == "core"] or ["core"]
    if branch_policy == "protected_branch":
        allowed_lanes = [lane for lane in allowed_lanes if lane not in {"easy", "repair"}] or ["core"]
    if not allowed_lanes:
        fallback_lanes: List[str] = []
        if groundwork_required and "groundwork" in lane_names:
            fallback_lanes.append("groundwork")
        if "easy" in lane_names:
            fallback_lanes.append("easy")
        if allow_paid_fast_lane and "repair" in lane_names:
            fallback_lanes.append("repair")
        if allow_credit_burn and "core" in lane_names:
            fallback_lanes.append("core")
        if "easy" in lane_names and "easy" not in fallback_lanes:
            fallback_lanes.append("easy")
        allowed_lanes = fallback_lanes or (["easy"] if "easy" in lane_names else ["core"])
    if groundwork_required and "groundwork" in lane_names:
        allowed_lanes = ["groundwork", *[lane for lane in allowed_lanes if lane != "groundwork"]]
    if workflow_kind == "groundwork_review_loop":
        if "required_reviewer_lane" not in item and "jury" in lane_names:
            reviewer_lane = "jury"
        if "final_reviewer_lane" not in item and "jury" in lane_names:
            final_reviewer_lane = "jury"
    elif jury_required and "jury" in lane_names:
        reviewer_lane = "jury"
        final_reviewer_lane = "jury"
    if reviewer_lane not in lane_names:
        reviewer_lane = "core"
    if not final_reviewer_lane:
        final_reviewer_lane = landing_lane
    if not final_reviewer_lane:
        final_reviewer_lane = reviewer_lane
    if final_reviewer_lane not in lane_names:
        final_reviewer_lane = "jury" if "jury" in lane_names else reviewer_lane
    if not landing_lane:
        landing_lane = final_reviewer_lane
    if landing_lane not in lane_names:
        landing_lane = final_reviewer_lane
    if workflow_kind == "groundwork_review_loop" and jury_acceptance_required:
        jury_required = True
        if "jury" in lane_names:
            final_reviewer_lane = "jury"
            landing_lane = "jury"
    if design_sensitive and "design_review" not in signoff_requirements:
        signoff_requirements.append("design_review")
    if architecture_sensitive and "architecture_review" not in signoff_requirements:
        signoff_requirements.append("architecture_review")
    if (jury_required or final_reviewer_lane == "jury") and "jury" not in signoff_requirements:
        signoff_requirements.append("jury")
    if operator_override_required and "operator_signoff" not in signoff_requirements:
        signoff_requirements.append("operator_signoff")
    return {
        "title": title,
        "difficulty": difficulty,
        "risk_level": risk_level,
        "branch_policy": branch_policy,
        "allowed_lanes": allowed_lanes,
        "required_reviewer_lane": reviewer_lane,
        "final_reviewer_lane": final_reviewer_lane,
        "landing_lane": landing_lane,
        "acceptance_level": acceptance_level,
        "budget_class": budget_class,
        "latency_class": latency_class,
        "design_owner": design_owner,
        "design_sensitive": design_sensitive,
        "architecture_sensitive": architecture_sensitive,
        "dispatchability_state": dispatchability_state,
        "workflow_kind": workflow_kind,
        "review_round": review_round,
        "max_review_rounds": max_review_rounds,
        "first_review_required": first_review_required,
        "jury_acceptance_required": jury_acceptance_required,
        "allow_credit_burn": allow_credit_burn,
        "allow_paid_fast_lane": allow_paid_fast_lane,
        "allow_core_rescue": allow_core_rescue,
        "core_rescue_after_round": core_rescue_after_round,
        "first_review_complete": first_review_complete,
        "accepted_on_round": accepted_on_round,
        "needs_core_rescue": needs_core_rescue,
        "core_rescue_reason": core_rescue_reason,
        "jury_feedback_history": jury_feedback_history,
        "issue_fingerprints": issue_fingerprints,
        "groundwork_required": groundwork_required,
        "jury_required": jury_required,
        "operator_override_required": operator_override_required,
        "protected_runtime": protected_runtime,
        "premium_required": premium_required,
        "premium_beneficial": premium_beneficial,
        "participant_eligible": participant_eligible,
        "signoff_requirements": signoff_requirements,
        "publish_truth_sources": publish_truth_sources,
    }


def project_account_aliases(project: Dict[str, Any]) -> List[str]:
    return ordered_project_aliases(project)


def shared_lane_fallback_aliases(
    config: Dict[str, Any],
    project_cfg: Dict[str, Any],
    *,
    target_lanes: Optional[List[str]] = None,
) -> List[str]:
    policy = project_account_policy(project_cfg)
    if bool(policy.get("pin_special_accounts", False)):
        return []
    existing_aliases = set(ordered_project_aliases(project_cfg))
    desired_lanes = expand_serviceable_lanes(target_lanes or [], lanes=config.get("lanes"))
    accounts_cfg = config.get("accounts") or {}
    candidates: List[str] = []
    for alias, account_cfg in accounts_cfg.items():
        clean_alias = str(alias or "").strip()
        if not clean_alias or clean_alias in existing_aliases:
            continue
        if not clean_alias.startswith("acct-ea-"):
            continue
        configured_lane = infer_account_lane(account_cfg, alias=clean_alias)
        if desired_lanes and configured_lane not in desired_lanes:
            continue
        auth_kind = str((account_cfg or {}).get("auth_kind") or "api_key").strip()
        if auth_kind in {"chatgpt_auth_json", "auth_json"} and not bool(policy.get("allow_chatgpt_accounts", True)):
            continue
        if auth_kind == "api_key" and not bool(policy.get("allow_api_accounts", True)):
            continue
        candidates.append(clean_alias)
    lane_rank = {lane: index for index, lane in enumerate(desired_lanes)}
    candidates.sort(key=lambda alias: (lane_rank.get(infer_account_lane(accounts_cfg.get(alias) or {}, alias=alias), len(lane_rank)), alias))
    return candidates


def account_supports_spark(account_cfg: Dict[str, Any]) -> bool:
    allowed_models = _text_list(account_cfg.get("allowed_models"))
    spark_enabled = bool(account_cfg.get("spark_enabled", SPARK_MODEL in allowed_models))
    return spark_enabled and ((not allowed_models) or (SPARK_MODEL in allowed_models))


def config_consistency_warnings(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    accounts = dict(config.get("accounts") or {})
    lanes = normalize_lanes_config(config.get("lanes"))
    warnings: List[Dict[str, Any]] = []
    for alias, account_cfg in accounts.items():
        explicit_lane = str((account_cfg or {}).get("lane") or "").strip().lower()
        if explicit_lane and explicit_lane not in lanes:
            warnings.append(
                {
                    "kind": "unknown_lane",
                    "scope_type": "account",
                    "scope_id": str(alias or "unknown").strip() or "unknown",
                    "title": f"{alias} references an undefined lane",
                    "summary": explicit_lane,
                    "detail": f"Define lane `{explicit_lane}` in routing.yaml or change the account lane assignment.",
                }
            )
    for project in config.get("projects") or []:
        project_id = str(project.get("id") or "").strip() or "unknown"
        aliases = project_account_aliases(project)
        missing = [alias for alias in aliases if alias not in accounts]
        if missing:
            warnings.append(
                {
                    "kind": "unknown_account_alias",
                    "scope_type": "project",
                    "scope_id": project_id,
                    "title": f"{project_id} references undefined account aliases",
                    "summary": ", ".join(missing),
                    "detail": f"Define {', '.join(missing)} in accounts.yaml or stop referencing them in project policy.",
                }
            )
        for idx, item in enumerate(project.get("queue") or [], start=1):
            task_meta = normalize_task_queue_item(item, lanes=lanes)
            allowed_lanes = list(task_meta.get("allowed_lanes") or [])
            serviceable_lanes = expand_serviceable_lanes(allowed_lanes, task_meta=task_meta, lanes=lanes)
            task_aliases = list(aliases)
            task_aliases.extend(
                alias
                for alias in shared_lane_fallback_aliases(config, project, target_lanes=serviceable_lanes)
                if alias not in task_aliases
            )
            account_lanes = {
                infer_account_lane(accounts.get(alias) or {}, alias=alias)
                for alias in task_aliases
                if alias in accounts
            }
            if serviceable_lanes and account_lanes and not any(lane in account_lanes for lane in serviceable_lanes):
                warnings.append(
                    {
                        "kind": "unserved_task_lane",
                        "scope_type": "project",
                        "scope_id": project_id,
                        "title": f"{project_id} queue item cannot be served by configured account lanes",
                        "summary": f"item {idx}: {task_meta.get('title') or 'untitled task'}",
                        "detail": (
                            f"Allowed lanes {', '.join(serviceable_lanes)} do not overlap project account lanes "
                            f"{', '.join(sorted(account_lanes)) or 'none'}."
                        ),
                    }
                )
        policy = dict(project.get("account_policy") or {})
        if bool(policy.get("spark_enabled", True)):
            spark_aliases = [alias for alias in aliases if account_supports_spark(accounts.get(alias) or {})]
            if not spark_aliases:
                warnings.append(
                    {
                        "kind": "spark_policy_impossible",
                        "scope_type": "project",
                        "scope_id": project_id,
                        "title": f"{project_id} asks for Spark but no eligible Spark lane exists",
                        "summary": "spark_enabled=true but no referenced account can run gpt-5.3-codex-spark",
                        "detail": "Add a Spark-capable ChatGPT-auth alias or disable Spark for this project policy.",
                    }
                )
        review = dict(project.get("review") or {})
        review_mode = str(review.get("mode") or "github").strip().lower()
        if review_mode == "local":
            review_aliases = list(aliases)
            review_aliases.extend(
                alias
                for alias in _text_list(review.get("preferred_accounts"))
                if alias not in review_aliases
            )
            review_account_lanes = {
                infer_account_lane(accounts.get(alias) or {}, alias=alias)
                for alias in review_aliases
                if alias in accounts
            }
            reviewer_lanes: List[str] = []
            for item in project.get("queue") or []:
                task_meta = normalize_task_queue_item(item, lanes=lanes)
                for lane_name in (
                    str(task_meta.get("required_reviewer_lane") or "").strip().lower(),
                    str(task_meta.get("final_reviewer_lane") or "").strip().lower(),
                ):
                    if lane_name and lane_name not in reviewer_lanes:
                        reviewer_lanes.append(lane_name)
            missing_reviewer_lanes = [lane_name for lane_name in reviewer_lanes if lane_name not in review_account_lanes]
            if missing_reviewer_lanes:
                warnings.append(
                    {
                        "kind": "unserved_reviewer_lane",
                        "scope_type": "project",
                        "scope_id": project_id,
                        "title": f"{project_id} local review lanes are not backed by configured accounts",
                        "summary": ", ".join(missing_reviewer_lanes),
                        "detail": (
                            f"Local review needs reviewer lanes {', '.join(missing_reviewer_lanes)}, but project account lanes are "
                            f"{', '.join(sorted(review_account_lanes)) or 'none'}."
                        ),
                    }
                )
        local_review_allowed = (
            project_id == "fleet"
            and review_mode == "local"
            and bool(review.get("required_before_queue_advance", True))
        )
        if bool(review.get("enabled", True)) and review_mode != "github" and not local_review_allowed:
            warnings.append(
                {
                    "kind": "review_mode_drift",
                    "scope_type": "project",
                    "scope_id": project_id,
                    "title": f"{project_id} is not on the documented GitHub-first review lane",
                    "summary": f"review.mode={str(review.get('mode') or '').strip() or 'local'}",
                    "detail": "Either keep the project on github review mode or update the docs/spec to describe a different default posture.",
                }
            )
    return warnings


def blocking_config_consistency_warnings(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [warning for warning in config_consistency_warnings(config) if str(warning.get("kind") or "") in BLOCKING_WARNING_KINDS]


def raise_for_config_consistency(config: Dict[str, Any]) -> None:
    blocking = blocking_config_consistency_warnings(config)
    if not blocking:
        return
    parts = []
    for warning in blocking:
        scope_id = str(warning.get("scope_id") or "unknown").strip() or "unknown"
        kind = str(warning.get("kind") or "unknown").strip() or "unknown"
        summary = str(warning.get("summary") or "").strip() or "no summary"
        parts.append(f"{scope_id}:{kind}:{summary}")
    raise RuntimeError("config_consistency_errors:" + " | ".join(parts))
