from __future__ import annotations

from typing import Any, Dict, List, Set


SPARK_MODEL = "gpt-5.3-codex-spark"
BLOCKING_WARNING_KINDS = {"unknown_account_alias", "spark_policy_impossible", "review_mode_drift"}


def _text_list(values: Any) -> List[str]:
    if isinstance(values, (list, tuple)):
        return [str(item).strip() for item in values if str(item).strip()]
    value = str(values or "").strip()
    return [value] if value else []


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
    warnings: List[Dict[str, Any]] = []
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
