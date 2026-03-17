#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

ROOT = Path("/docker/fleet")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin.consistency import normalize_lanes_config, normalize_task_queue_item


ROUTING_CONFIG_PATH = ROOT / "config" / "routing.yaml"

DEFAULT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "telemetry_keywords": (
        "current",
        "live",
        "remaining",
        "credits",
        "credit",
        "balance",
        "capacity",
        "quota",
        "available",
        "how much left",
        "remaining percent",
        "remaining %",
        "percent remaining",
        "percent left",
        "eta",
        "runway",
        "sustainable",
        "limit left",
    ),
    "inspect_keywords": (
        "inspect",
        "investigate",
        "triage",
        "understand",
        "look into",
        "read",
        "analyze",
        "status",
        "inventory",
        "explain",
    ),
    "draft_keywords": (
        "draft",
        "summarize",
        "summary",
        "outline",
        "rewrite",
        "document",
        "docs",
        "backlog",
        "plan",
        "proposal",
        "packet",
        "shape",
    ),
    "groundwork_keywords": (
        "architecture",
        "tradeoff",
        "trade-off",
        "deep dive",
        "research",
        "backlog shaping",
        "design review",
        "strategy",
        "second pass",
        "groundwork",
        "approach",
        "direction",
    ),
    "micro_edit_keywords": (
        "rename",
        "typo",
        "comment",
        "small edit",
        "small fix",
        "one-line",
        "single-file",
        "tiny patch",
    ),
    "bounded_fix_keywords": (
        "fix",
        "patch",
        "edit",
        "update",
        "refactor",
        "implement",
        "wire",
        "change",
        "test",
        "failing test",
        "bug",
    ),
    "multi_file_impl_keywords": (
        "multi-file",
        "multi file",
        "integration",
        "workflow",
        "feature",
        "controller",
        "dashboard",
        "backend",
        "frontend",
        "across the repo",
        "cross-service",
    ),
    "cross_repo_contract_keywords": (
        "audit",
        "review",
        "second opinion",
        "critic",
        "escalat",
        "risk",
        "security",
        "migration",
        "public api",
        "contract",
        "auth",
        "payment",
        "billing",
        "release",
        "protected branch",
        "schema migration",
        "breaking change",
        "cross repo",
        "cross-repo",
    ),
}

TASK_KEYS = (
    "difficulty",
    "risk_level",
    "branch_policy",
    "acceptance_level",
    "allowed_lanes",
    "required_reviewer_lane",
    "budget_class",
    "latency_class",
)

TELEMETRY_EXIT_NOT_MATCHED = 10
UNTRUSTED_STATUS_BASES = {"", "unknown_unprobed", "observed_error", "estimated", "no_balance_api"}
TELEMETRY_SIGNAL_TERMS: tuple[str, ...] = (
    "credit",
    "credits",
    "balance",
    "remaining",
    "left",
    "capacity",
    "quota",
    "available",
    "runway",
    "eta",
    "sustainable",
    "burn",
    "percent",
    "%",
)
LANE_NAMES: tuple[str, ...] = ("easy", "repair", "groundwork", "core", "jury", "survival")
PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "browseract": "BrowserAct",
    "chatplayground": "ChatPlayground",
    "gemini_vortex": "Gemini Vortex",
    "magixai": "MagixAI",
    "onemin": "1min",
}
PROVIDER_ALIASES: dict[str, tuple[str, ...]] = {
    "browseract": ("browseract", "browser act"),
    "chatplayground": ("chatplayground", "chat playground"),
    "gemini_vortex": ("gemini_vortex", "gemini vortex", "gemini"),
    "magixai": ("magixai", "magicx", "ai magicx", "aimagicx"),
    "onemin": ("onemin", "1min", "1min.ai", "1minai", "one min", "one-minute", "oneminai"),
}


def _core_guard_enabled() -> bool:
    return str(os.environ.get("CODEXEA_CORE_GUARD_ENABLED", "1")).strip().lower() not in {"0", "false", "off", "no"}


def _core_min_onemin_credits() -> int:
    try:
        return max(0, int(float(str(os.environ.get("CODEXEA_CORE_MIN_ONEMIN_CREDITS", "100000")))))
    except Exception:
        return 100000


def _ea_status_url() -> str:
    base_url = str(os.environ.get("CODEXEA_STATUS_URL") or "").strip()
    if base_url:
        return base_url
    root = str(os.environ.get("EA_MCP_BASE_URL") or "http://127.0.0.1:8090").rstrip("/")
    return f"{root}/v1/codex/status"


def _ea_profiles_url() -> str:
    base_url = str(os.environ.get("CODEXEA_PROFILES_URL") or "").strip()
    if base_url:
        return base_url
    root = str(os.environ.get("EA_MCP_BASE_URL") or "http://127.0.0.1:8090").rstrip("/")
    return f"{root}/v1/codex/profiles"


def _ea_http_payload(url: str) -> dict[str, Any] | None:
    principal_id = (
        str(os.environ.get("EA_MCP_PRINCIPAL_ID") or "").strip()
        or str(os.environ.get("EA_PRINCIPAL_ID") or "").strip()
        or "codexea-route"
    )
    headers = {"X-EA-Principal-ID": principal_id}
    api_token = str(os.environ.get("EA_MCP_API_TOKEN") or os.environ.get("EA_API_TOKEN") or "").strip()
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _ea_status_payload(*, refresh: bool = False, window: str = "1h") -> dict[str, Any] | None:
    url = f"{_ea_status_url()}?window={window}&refresh={1 if refresh else 0}"
    return _ea_http_payload(url)


def _ea_profiles_payload() -> dict[str, Any] | None:
    return _ea_http_payload(_ea_profiles_url())


def _core_capacity_guard_reason() -> str | None:
    if not _core_guard_enabled():
        return None
    payload = _ea_status_payload(refresh=True)
    if not isinstance(payload, dict):
        return "core_blocked_unknown_capacity"
    providers = payload.get("providers_summary")
    if not isinstance(providers, list):
        return "core_blocked_unknown_capacity"
    trusted_free_credits: list[int] = []
    for row in providers:
        if not isinstance(row, dict):
            continue
        if str(row.get("provider_name") or "").strip().lower() != "1min":
            continue
        state = str(row.get("state") or "").strip().lower()
        basis = str(row.get("basis") or "").strip().lower()
        free = row.get("free_credits")
        if state != "ready":
            continue
        if basis in UNTRUSTED_STATUS_BASES:
            continue
        try:
            trusted_free_credits.append(int(float(str(free))))
        except Exception:
            continue
    if not trusted_free_credits:
        return "core_blocked_unknown_capacity"
    if max(trusted_free_credits) < _core_min_onemin_credits():
        return "core_blocked_low_capacity"
    return None


def _contains_any(haystack: str, terms: tuple[str, ...]) -> bool:
    return any(term in haystack for term in terms)


def _load_config() -> dict[str, Any]:
    loaded = yaml.safe_load(ROUTING_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return loaded if isinstance(loaded, dict) else {}


def _keyword_set(config: dict[str, Any], key: str) -> tuple[str, ...]:
    spider = config.get("spider") if isinstance(config.get("spider"), dict) else {}
    configured = spider.get(key)
    if isinstance(configured, (list, tuple)):
        values = tuple(str(item).strip().lower() for item in configured if str(item).strip())
        if values:
            return values
    return DEFAULT_KEYWORDS[key]


def _normalize_text_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _canonical_provider_name(value: Any) -> str:
    normalized = _normalize_text_token(value)
    if not normalized:
        return ""
    for provider, aliases in PROVIDER_ALIASES.items():
        alias_tokens = {_normalize_text_token(alias) for alias in aliases}
        alias_tokens.add(_normalize_text_token(provider))
        if normalized in alias_tokens:
            return provider
    return ""


def _provider_from_text(text: str) -> str:
    lowered = text.lower()
    for provider, aliases in PROVIDER_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return provider
    return ""


def _lane_from_text(text: str) -> str:
    lowered = text.lower()
    for lane in LANE_NAMES:
        if re.search(rf"\b{re.escape(lane)}\b", lowered):
            return lane
    return ""


def _looks_like_live_telemetry_query(config: dict[str, Any], text: str) -> bool:
    lowered = text.lower()
    if _contains_any(lowered, _keyword_set(config, "telemetry_keywords")):
        return True
    has_target = bool(_provider_from_text(lowered) or _lane_from_text(lowered))
    return has_target and _contains_any(lowered, TELEMETRY_SIGNAL_TERMS)


def _telemetry_target(config: dict[str, Any], text: str) -> dict[str, str]:
    lanes = normalize_lanes_config(config.get("lanes"))
    lane = _lane_from_text(text)
    provider = _provider_from_text(text)
    if not provider and lane:
        provider_hints = (lanes.get(lane) or {}).get("provider_hint_order") or []
        for hint in provider_hints:
            provider = _canonical_provider_name(hint)
            if provider:
                break
    return {"lane": lane, "provider": provider}


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value))
    except Exception:
        return None


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value)))
    except Exception:
        return None


def _remaining_percent_from_row(row: dict[str, Any]) -> float | None:
    remaining = _coerce_float(row.get("remaining_percent"))
    if remaining is not None:
        return max(0.0, min(100.0, remaining))
    remaining = _coerce_float(row.get("remaining_percent_of_max"))
    if remaining is not None:
        return max(0.0, min(100.0, remaining))
    used = _coerce_float(row.get("used_percent"))
    if used is not None:
        return max(0.0, min(100.0, 100.0 - used))
    return None


def _provider_rows_from_payload(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    providers_summary = payload.get("providers_summary")
    if isinstance(providers_summary, list):
        for row in providers_summary:
            if not isinstance(row, dict):
                continue
            provider = _canonical_provider_name(row.get("provider_name") or row.get("provider_key") or row.get("backend"))
            rows.append(
                {
                    "provider": provider,
                    "provider_label": str(row.get("provider_name") or PROVIDER_DISPLAY_NAMES.get(provider) or "provider").strip(),
                    "account_name": str(row.get("account_name") or "").strip(),
                    "remaining_percent": _remaining_percent_from_row(row),
                    "free_credits": _coerce_int(row.get("free_credits")),
                    "hours_remaining": _coerce_float(row.get("hours_remaining_at_current_pace")),
                    "basis": str(row.get("basis") or "").strip(),
                    "state": str(row.get("state") or "").strip(),
                    "trustworthy_percent": _remaining_percent_from_row(row) is not None
                    and str(row.get("basis") or "").strip().lower() not in UNTRUSTED_STATUS_BASES,
                }
            )
        return "status", rows

    providers = ((payload.get("provider_health") or {}).get("providers") or {})
    if isinstance(providers, dict):
        for key, row in providers.items():
            if not isinstance(row, dict):
                continue
            provider = _canonical_provider_name(key) or _canonical_provider_name(row.get("provider_key") or row.get("backend"))
            rows.append(
                {
                    "provider": provider or str(key).strip().lower(),
                    "provider_label": str(row.get("provider_name") or PROVIDER_DISPLAY_NAMES.get(provider or "", key) or key).strip(),
                    "account_name": "",
                    "remaining_percent": _remaining_percent_from_row(row),
                    "free_credits": _coerce_int(row.get("free_credits")),
                    "hours_remaining": _coerce_float(row.get("estimated_hours_remaining_at_current_pace")),
                    "basis": str(row.get("basis") or payload.get("status_basis") or "profiles_fallback").strip(),
                    "state": str(row.get("state") or "").strip(),
                    "trustworthy_percent": _remaining_percent_from_row(row) is not None,
                }
            )
        return "profiles_fallback", rows
    return "unavailable", rows


def _provider_label(row: dict[str, Any]) -> str:
    provider = str(row.get("provider") or "").strip().lower()
    label = str(row.get("provider_label") or PROVIDER_DISPLAY_NAMES.get(provider) or provider or "provider").strip()
    account_name = str(row.get("account_name") or "").strip()
    if account_name and account_name.lower() not in {label.lower(), provider}:
        return f"{label}/{account_name}"
    return label


def _scope_label(target: dict[str, str]) -> str:
    lane = str(target.get("lane") or "").strip()
    provider = str(target.get("provider") or "").strip().lower()
    provider_label = PROVIDER_DISPLAY_NAMES.get(provider, provider)
    if lane and provider_label:
        return f"{lane}/{provider_label}"
    if provider_label:
        return provider_label
    return lane


def _format_decimal(value: float | None, *, suffix: str = "", precision: int = 1) -> str:
    if value is None:
        return "unknown"
    return f"{value:.{precision}f}{suffix}"


def _format_int(value: int | None) -> str:
    if value is None:
        return "unknown"
    return f"{value:,}"


def _format_telemetry_row(row: dict[str, Any], *, strict_unknown: bool) -> str:
    label = _provider_label(row)
    remaining = row.get("remaining_percent")
    state = str(row.get("state") or "unknown").strip()
    basis = str(row.get("basis") or "").strip()
    if strict_unknown and not bool(row.get("trustworthy_percent")):
        bits = ["remaining percent is unknown right now"]
        if basis:
            bits.append(f"basis {basis}")
        bits.append(f"state {state}")
        return f"{label}: " + ", ".join(bits)

    bits = [f"{_format_decimal(remaining, suffix='%')} remaining" if remaining is not None else "remaining percent unknown"]
    free_credits = _coerce_int(row.get("free_credits"))
    if free_credits is not None:
        bits.append(f"{_format_int(free_credits)} free credits")
    hours_remaining = _coerce_float(row.get("hours_remaining"))
    if hours_remaining is not None:
        bits.append(f"ETA {_format_decimal(hours_remaining, suffix='h')}")
    if basis:
        bits.append(f"basis {basis}")
    bits.append(f"state {state}")
    return f"{label}: " + ", ".join(bits)


def _telemetry_response(text: str) -> dict[str, Any]:
    config = _load_config()
    if not _looks_like_live_telemetry_query(config, text):
        return {"matched": False, "ok": False, "exit_code": TELEMETRY_EXIT_NOT_MATCHED, "message": ""}

    target = _telemetry_target(config, text)
    payload = _ea_status_payload(refresh=True)
    payload_source = "status"
    if not isinstance(payload, dict):
        payload = _ea_profiles_payload()
        payload_source = "profiles_fallback"
    if not isinstance(payload, dict):
        return {
            "matched": True,
            "ok": False,
            "exit_code": 1,
            "message": "Live CodexEA status is unavailable right now; `/v1/codex/status?refresh=1` did not return data.",
        }

    row_source, rows = _provider_rows_from_payload(payload)
    if not rows:
        return {
            "matched": True,
            "ok": False,
            "exit_code": 1,
            "message": "Live CodexEA status refreshed, but no provider telemetry rows were returned.",
        }

    selected_rows = rows
    if target.get("provider"):
        selected_rows = [row for row in rows if str(row.get("provider") or "").strip().lower() == target["provider"]]
        if not selected_rows:
            target_label = _scope_label(target)
            return {
                "matched": True,
                "ok": True,
                "exit_code": 0,
                "message": f"Live {target_label} status refreshed, but no matching provider row was returned.",
            }

    strict_unknown = row_source == "status"
    scope_label = _scope_label(target)
    prefix = "Live CodexEA provider status"
    if scope_label:
        prefix = f"Live {scope_label} status"
    if payload_source == "profiles_fallback":
        prefix += " (profiles fallback)"
    rendered_rows = [_format_telemetry_row(row, strict_unknown=strict_unknown) for row in selected_rows]
    return {
        "matched": True,
        "ok": True,
        "exit_code": 0,
        "message": prefix + ": " + " | ".join(rendered_rows),
    }


def _task_meta_from_text(config: dict[str, Any], text: str) -> dict[str, Any]:
    lowered = text.lower()
    item: dict[str, Any] = {"title": text}
    patch_like = _contains_any(
        lowered,
        _keyword_set(config, "bounded_fix_keywords") + _keyword_set(config, "micro_edit_keywords"),
    )
    groundwork_like = _contains_any(lowered, _keyword_set(config, "groundwork_keywords"))

    if _contains_any(lowered, ("protected branch", "merge-ready", "merge ready")):
        item["branch_policy"] = "protected_branch"
        item["acceptance_level"] = "merge_ready"
    elif _contains_any(lowered, ("no merge", "docs only", "documentation only")):
        item["branch_policy"] = "no_merge"

    if _contains_any(lowered, ("high risk", "security", "migration", "billing", "auth", "payment")):
        item["risk_level"] = "high"
    elif _contains_any(lowered, ("medium risk", "coordination", "cross-service")):
        item["risk_level"] = "medium"
    else:
        item["risk_level"] = "low"

    if _contains_any(lowered, ("audit", "review", "jury", "second opinion")) and not patch_like and not groundwork_like:
        item["allowed_lanes"] = ["jury"]
        item["required_reviewer_lane"] = "jury"
    elif _contains_any(lowered, ("fix", "patch", "bug", "refactor", "implement", "wire", "test")):
        item["allowed_lanes"] = ["easy", "repair", "core"]
    else:
        item["allowed_lanes"] = ["easy", "repair", "core"]
    return item


def _classify_tier(config: dict[str, Any], text: str) -> str:
    lowered = text.lower()
    patch_like = _contains_any(lowered, _keyword_set(config, "bounded_fix_keywords"))
    if _looks_like_live_telemetry_query(config, lowered):
        return "telemetry"
    if _contains_any(lowered, _keyword_set(config, "groundwork_keywords")) and not patch_like:
        return "groundwork"
    if _contains_any(lowered, _keyword_set(config, "cross_repo_contract_keywords")) and not patch_like:
        return "cross_repo_contract"
    if _contains_any(lowered, _keyword_set(config, "inspect_keywords")) and not _contains_any(
        lowered, _keyword_set(config, "bounded_fix_keywords")
    ):
        return "inspect"
    if _contains_any(lowered, _keyword_set(config, "draft_keywords")) and not _contains_any(
        lowered, _keyword_set(config, "bounded_fix_keywords")
    ):
        return "draft"
    if _contains_any(lowered, _keyword_set(config, "micro_edit_keywords")):
        return "micro_edit"
    if _contains_any(lowered, _keyword_set(config, "bounded_fix_keywords")):
        return "bounded_fix"
    if _contains_any(lowered, _keyword_set(config, "multi_file_impl_keywords")):
        return "multi_file_impl"
    return "inspect"


def _route(argv: list[str]) -> dict[str, str]:
    config = _load_config()
    lanes = normalize_lanes_config(config.get("lanes"))
    spider = config.get("spider") if isinstance(config.get("spider"), dict) else {}
    default_lane = "easy"

    if not argv:
        lane_cfg = lanes.get(default_lane) or {}
        return {
            "lane": default_lane,
            "submode": "mcp",
            "reasoning_effort": "low",
            "reason": "interactive_or_first_pass",
            "task_class": "inspect",
            "runtime_model": str(lane_cfg.get("runtime_model") or ""),
            "provider_hint_order": ",".join(lane_cfg.get("provider_hint_order") or []),
        }

    text = " ".join(argv).strip()
    task_meta = normalize_task_queue_item(_task_meta_from_text(config, text), lanes=lanes)
    tier = _classify_tier(config, text)
    allowed_lanes = list(task_meta.get("allowed_lanes") or ["easy", "repair", "core"])
    difficulty = str(task_meta.get("difficulty") or "auto")
    risk_level = str(task_meta.get("risk_level") or "auto")
    branch_policy = str(task_meta.get("branch_policy") or "auto")
    acceptance_level = str(task_meta.get("acceptance_level") or "auto")
    requires_contract_authority = tier == "cross_repo_contract" or branch_policy == "protected_branch" or acceptance_level == "merge_ready"

    preferred_lane = allowed_lanes[0] if allowed_lanes else default_lane
    submode = "mcp"
    reason = "cheap_first_default"
    reasoning_effort = "low"

    if preferred_lane == "jury":
        submode = "responses_audit"
        reason = "audit_or_risk_signal"
        reasoning_effort = "medium"
    elif tier == "telemetry":
        preferred_lane = "easy"
        submode = "mcp"
        reason = "telemetry_live_status"
        reasoning_effort = "low"
    elif tier == "groundwork" and "groundwork" in lanes and "groundwork" in allowed_lanes + ["groundwork"]:
        preferred_lane = "groundwork"
        submode = "responses_groundwork"
        reason = "complex_nonurgent_analysis"
        reasoning_effort = "medium"
    elif preferred_lane == "easy" and tier in {"bounded_fix", "micro_edit"} and "repair" in allowed_lanes:
        preferred_lane = "repair"
        submode = "responses_fast"
        reason = "bounded_patch_generation"
    if preferred_lane in {"easy", "repair"} and (
        tier in {"multi_file_impl", "cross_repo_contract"} or risk_level in {"medium", "high"} or requires_contract_authority
    ) and "core" in allowed_lanes:
        preferred_lane = "core"
        submode = "responses_hard"
        reason = "high_risk_scope"
        reasoning_effort = "high"
    elif preferred_lane == "easy" and tier != "telemetry":
        if tier in {"inspect", "draft"}:
            submode = "mcp"
            reason = "lightweight_exploration" if tier == "draft" else "interactive_or_first_pass"
            reasoning_effort = str(((spider.get("tier_preferences") or {}).get(tier) or {}).get("reasoning_effort") or "low")
        else:
            submode = "mcp"
            reason = "cheap_first_default"
    elif preferred_lane == "repair":
        submode = "responses_fast"
        reason = "bounded_patch_generation"
    elif preferred_lane == "core":
        submode = "responses_hard"
        reason = "high_risk_scope"
        reasoning_effort = "high"

    if preferred_lane == "core":
        capacity_reason = _core_capacity_guard_reason()
        if capacity_reason:
            if "repair" in allowed_lanes:
                preferred_lane = "repair"
                submode = "responses_fast"
                reason = capacity_reason
                reasoning_effort = "low"
            else:
                preferred_lane = "easy"
                submode = "mcp"
                reason = capacity_reason
                reasoning_effort = "low"

    lane_cfg = lanes.get(preferred_lane) or {}
    return {
        "lane": preferred_lane,
        "submode": submode,
        "reasoning_effort": reasoning_effort,
        "reason": reason,
        "task_class": tier,
        "runtime_model": str(lane_cfg.get("runtime_model") or ""),
        "provider_hint_order": ",".join(lane_cfg.get("provider_hint_order") or []),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shell", action="store_true")
    parser.add_argument("--telemetry-answer", action="store_true")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args(argv)
    if ns.telemetry_answer:
        response = _telemetry_response(" ".join(ns.args).strip())
        message = str(response.get("message") or "").strip()
        if message:
            stream = sys.stdout if int(response.get("exit_code") or 0) == 0 else sys.stderr
            print(message, file=stream)
        return int(response.get("exit_code") or 0)
    routed = _route(ns.args)
    if ns.shell:
        for key, value in routed.items():
            print(f"CODEXEA_ROUTE_{key.upper()}={shlex.quote(value)}")
        return 0
    for key, value in routed.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
