from __future__ import annotations

from typing import Any, Dict, List, Set


SPARK_MODEL = "gpt-5.3-codex-spark"
DEFAULT_LANES: Dict[str, Dict[str, Any]] = {
    "easy": {
        "label": "EA Easy",
        "authority": "run",
        "merge_protected_branches": False,
        "escalation_only": False,
        "worker_profile": "easy",
        "codex_mode": "easy",
        "runtime_model": "ea-coder-fast",
        "provider_hint_order": ["magixai"],
        "reviewer_lane": "core",
        "budget_bias": "cheap",
        "latency_class": "priority",
    },
    "core": {
        "label": "EA Core",
        "authority": "approve_merge",
        "merge_protected_branches": True,
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
        "authority": "audit",
        "merge_protected_branches": False,
        "escalation_only": True,
        "worker_profile": "audit",
        "codex_mode": "jury",
        "runtime_model": "ea-audit-jury",
        "provider_hint_order": ["chatplayground"],
        "reviewer_lane": "core",
        "budget_bias": "premium",
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
BLOCKING_WARNING_KINDS = {
    "unknown_account_alias",
    "spark_policy_impossible",
    "review_mode_drift",
    "unknown_lane",
    "unserved_task_lane",
}


def _text_list(values: Any) -> List[str]:
    if isinstance(values, (list, tuple)):
        return [str(item).strip() for item in values if str(item).strip()]
    value = str(values or "").strip()
    return [value] if value else []


def normalize_lane_name(value: Any, *, default: str = "core") -> str:
    clean = str(value or "").strip().lower()
    return clean if clean in DEFAULT_LANES else str(default or "core").strip().lower()


def infer_account_lane(account_cfg: Dict[str, Any], *, alias: str = "") -> str:
    explicit = str((account_cfg or {}).get("lane") or "").strip().lower()
    if explicit in DEFAULT_LANES:
        return explicit
    model_aliases = {str(item).strip().lower() for item in _text_list((account_cfg or {}).get("codex_model_aliases"))}
    if "ea-audit-jury" in model_aliases:
        return "jury"
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
    reviewer_lane = normalize_lane_name(item.get("required_reviewer_lane") or item.get("reviewer_lane") or "core")
    raw_allowed = [lane for lane in _text_list(item.get("allowed_lanes")) if lane in lane_names]
    if raw_allowed:
        allowed_lanes = list(dict.fromkeys(raw_allowed))
    elif branch_policy == "protected_branch" or acceptance_level == "merge_ready":
        allowed_lanes = ["core"]
    elif risk_level == "high" or difficulty == "hard":
        allowed_lanes = ["core"]
    elif risk_level == "medium" or difficulty == "medium":
        allowed_lanes = ["easy", "core"]
    else:
        allowed_lanes = ["easy", "core"]
    if branch_policy == "protected_branch" and "core" not in allowed_lanes:
        allowed_lanes = ["core"]
    if branch_policy == "protected_branch":
        allowed_lanes = [lane for lane in allowed_lanes if lane != "easy"] or ["core"]
    if reviewer_lane not in lane_names:
        reviewer_lane = "core"
    return {
        "title": title,
        "difficulty": difficulty,
        "risk_level": risk_level,
        "branch_policy": branch_policy,
        "allowed_lanes": allowed_lanes,
        "required_reviewer_lane": reviewer_lane,
        "acceptance_level": acceptance_level,
        "budget_class": budget_class,
        "latency_class": latency_class,
    }


def project_account_aliases(project: Dict[str, Any]) -> List[str]:
    policy = dict(project.get("account_policy") or {})
    aliases = (
        _text_list(project.get("accounts"))
        + _text_list(policy.get("preferred_accounts"))
        + _text_list(policy.get("burst_accounts"))
        + _text_list(policy.get("reserve_accounts"))
    )
    seen: Set[str] = set()
    ordered: List[str] = []
    for alias in aliases:
        if alias in seen:
            continue
        seen.add(alias)
        ordered.append(alias)
    return ordered


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
        account_lanes = {
            infer_account_lane(accounts.get(alias) or {}, alias=alias)
            for alias in aliases
            if alias in accounts
        }
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
            if allowed_lanes and account_lanes and not any(lane in account_lanes for lane in allowed_lanes):
                warnings.append(
                    {
                        "kind": "unserved_task_lane",
                        "scope_type": "project",
                        "scope_id": project_id,
                        "title": f"{project_id} queue item cannot be served by configured account lanes",
                        "summary": f"item {idx}: {task_meta.get('title') or 'untitled task'}",
                        "detail": (
                            f"Allowed lanes {', '.join(allowed_lanes)} do not overlap project account lanes "
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
        if bool(review.get("enabled", True)) and str(review.get("mode") or "github").strip().lower() != "github":
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
