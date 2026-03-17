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
REVOKED_KEY_HINTS: tuple[str, ...] = (
    "api key is not active",
    "api key has been deleted",
    "revoked api key",
    "api key disabled",
    "api key expired",
    "invalid api key",
    "incorrect api key provided",
    "api key is invalid or revoked",
)


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


def _format_count_summary(values: list[str]) -> str:
    counts: dict[str, int] = {}
    for raw in values:
        key = str(raw or "").strip() or "unknown"
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return "unknown"
    return ", ".join(
        f"{label} x{counts[label]}" if counts[label] != 1 else label for label in sorted(counts)
    )


def _count_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for raw in values:
        key = str(raw or "").strip() or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _provider_credit_window(payload: dict[str, Any], *, provider: str, window: str) -> float | None:
    credits = (((payload.get("fleet_burn") or {}).get(window) or {}).get("provider_credits") or {})
    aliases = {provider}
    if provider == "onemin":
        aliases.update({"1min", "1min.ai"})
    for key, value in credits.items():
        if _canonical_provider_name(key) in aliases or str(key).strip().lower() in aliases:
            return _coerce_float(value)
    return None


def _bool_or_none(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return None


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _shorten(value: Any, *, limit: int = 120) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)].rstrip() + "..."


def _onemin_slot_revoked_like(slot: dict[str, Any]) -> bool:
    state = str(slot.get("state") or "").strip().lower()
    if state in {"revoked", "deleted", "disabled", "expired"}:
        return True
    haystack = " ".join(
        str(slot.get(key) or "").strip().lower()
        for key in ("detail", "last_error")
        if str(slot.get(key) or "").strip()
    )
    return bool(haystack) and _contains_any(haystack, REVOKED_KEY_HINTS)


def _onemin_slot_label(slot: dict[str, Any], index: int) -> str:
    account_name = str(slot.get("account_name") or "").strip()
    return account_name or f"slot-{index}"


def _onemin_aggregate_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    rows: list[dict[str, Any]] = []
    for row in payload.get("providers_summary") or []:
        if not isinstance(row, dict):
            continue
        provider = _canonical_provider_name(row.get("provider_name") or row.get("provider_key") or row.get("backend"))
        if provider != "onemin":
            continue
        rows.append(
            {
                "account_name": str(row.get("account_name") or "").strip(),
                "max_credits": _coerce_int(row.get("max_credits")),
                "free_credits": _coerce_int(row.get("free_credits")),
                "basis": str(row.get("basis") or "").strip() or "unknown",
                "state": str(row.get("state") or "").strip() or "unknown",
                "detail": str(row.get("detail") or "").strip(),
                "last_error": str(row.get("last_error") or "").strip(),
                "quarantine_until": str(row.get("quarantine_until") or "").strip(),
            }
        )

    precomputed = payload.get("onemin_aggregate")
    use_precomputed_only = not rows and isinstance(precomputed, dict)
    if not rows and not use_precomputed_only:
        return None

    slot_count = len(rows)
    known_balance_count = sum(1 for row in rows if row.get("free_credits") is not None)
    positive_balance_count = sum(1 for row in rows if (row.get("free_credits") or 0) > 0)
    known_max_count = sum(1 for row in rows if row.get("max_credits") is not None)
    sum_free_credits = sum(int(row["free_credits"]) for row in rows if row.get("free_credits") is not None) if rows else None
    sum_max_credits = sum(int(row["max_credits"]) for row in rows if row.get("max_credits") is not None) if rows else None
    basis_counts = _count_values([str(row.get("basis") or "") for row in rows])
    state_counts = _count_values([str(row.get("state") or "") for row in rows])
    unknown_unprobed_count = sum(1 for row in rows if str(row.get("basis") or "").strip().lower() == "unknown_unprobed")
    observed_error_count = sum(1 for row in rows if str(row.get("basis") or "").strip().lower() == "observed_error")
    quarantined_count = sum(1 for row in rows if str(row.get("quarantine_until") or "").strip())
    revoked_count = sum(1 for row in rows if _onemin_slot_revoked_like(row))
    remaining_percent_total = None
    if sum_free_credits is not None and sum_max_credits not in (None, 0):
        remaining_percent_total = max(0.0, min(100.0, (sum_free_credits / float(sum_max_credits)) * 100.0))

    burn_per_hour = _provider_credit_window(payload, provider="onemin", window="1h")
    avg_daily_burn_7d = None
    burn_7d_total = _provider_credit_window(payload, provider="onemin", window="7d")
    if burn_7d_total is not None:
        avg_daily_burn_7d = burn_7d_total / 7.0

    hours_remaining = None
    if sum_free_credits is not None and burn_per_hour not in (None, 0):
        hours_remaining = sum_free_credits / burn_per_hour

    days_remaining_7d = None
    if sum_free_credits is not None and avg_daily_burn_7d not in (None, 0):
        days_remaining_7d = sum_free_credits / avg_daily_burn_7d

    aggregate: dict[str, Any] = {
        "provider": "onemin",
        "provider_label": PROVIDER_DISPLAY_NAMES["onemin"],
        "slot_count": slot_count,
        "slot_count_with_balance": known_balance_count,
        "slot_count_with_known_balance": known_balance_count,
        "slot_count_with_positive_balance": positive_balance_count,
        "slot_count_with_known_max": known_max_count,
        "unknown_balance_slot_count": max(slot_count - known_balance_count, 0),
        "unknown_max_slot_count": max(slot_count - known_max_count, 0),
        "sum_max_credits": sum_max_credits,
        "sum_free_credits": sum_free_credits,
        "remaining_percent_total": remaining_percent_total,
        "current_pace_burn_credits_per_hour": burn_per_hour,
        "hours_remaining_at_current_pace": hours_remaining,
        "avg_daily_burn_credits_7d": avg_daily_burn_7d,
        "days_remaining_at_7d_avg_burn": days_remaining_7d,
        "days_left_at_7d_avg_burn": days_remaining_7d,
        "basis_summary": _format_count_summary([str(row.get("basis") or "") for row in rows]),
        "state_summary": _format_count_summary([str(row.get("state") or "") for row in rows]),
        "basis_counts": basis_counts,
        "state_counts": state_counts,
        "unknown_unprobed_slot_count": unknown_unprobed_count,
        "observed_error_slot_count": observed_error_count,
        "revoked_slot_count": revoked_count,
        "quarantined_slot_count": quarantined_count,
        "slots": [
            {
                "account_name": _onemin_slot_label(row, index + 1),
                "state": str(row.get("state") or "").strip() or "unknown",
                "basis": str(row.get("basis") or "").strip() or "unknown",
                "free_credits": row.get("free_credits"),
                "max_credits": row.get("max_credits"),
                "detail": str(row.get("detail") or "").strip(),
                "last_error": str(row.get("last_error") or "").strip(),
                "quarantine_until": str(row.get("quarantine_until") or "").strip(),
                "revoked_like": _onemin_slot_revoked_like(row),
                "quarantined": bool(str(row.get("quarantine_until") or "").strip()),
            }
            for index, row in enumerate(rows)
        ],
        "probe_note": (
            "unknown_unprobed means no live evidence yet; a single routed smoke request usually only changes the touched slot."
        ),
        "status_basis": str(payload.get("status_basis") or "").strip(),
        "incoming_topups_excluded": True,
        "used_precomputed_aggregate": False,
    }

    if not isinstance(precomputed, dict):
        return aggregate

    mapped_precomputed = {
        "slot_count": _coerce_int(precomputed.get("slot_count")),
        "slot_count_with_known_balance": _coalesce(
            _coerce_int(precomputed.get("slot_count_with_known_balance")),
            _coerce_int(precomputed.get("slot_count_with_balance")),
        ),
        "slot_count_with_positive_balance": _coerce_int(precomputed.get("slot_count_with_positive_balance")),
        "sum_max_credits": _coerce_int(precomputed.get("sum_max_credits")),
        "sum_free_credits": _coerce_int(precomputed.get("sum_free_credits")),
        "remaining_percent_total": _coerce_float(precomputed.get("remaining_percent_total")),
        "current_pace_burn_credits_per_hour": _coerce_float(precomputed.get("current_pace_burn_credits_per_hour")),
        "hours_remaining_at_current_pace": _coalesce(
            _coerce_float(precomputed.get("hours_remaining_at_current_pace")),
            _coerce_float(precomputed.get("hours_left_at_current_pace")),
        ),
        "avg_daily_burn_credits_7d": _coalesce(
            _coerce_float(precomputed.get("avg_daily_burn_credits_7d")),
            _coerce_float(precomputed.get("seven_day_average_daily_burn_credits")),
        ),
        "days_remaining_at_7d_avg_burn": _coalesce(
            _coerce_float(precomputed.get("days_remaining_at_7d_avg_burn")),
            _coerce_float(precomputed.get("days_left_at_7d_avg_burn")),
        ),
        "basis_summary": _coalesce(precomputed.get("basis_summary"), precomputed.get("balance_basis_summary")),
        "state_summary": precomputed.get("state_summary"),
        "basis_counts": precomputed.get("basis_counts") if isinstance(precomputed.get("basis_counts"), dict) else None,
        "state_counts": precomputed.get("state_counts") if isinstance(precomputed.get("state_counts"), dict) else None,
        "unknown_unprobed_slot_count": _coalesce(
            _coerce_int(precomputed.get("unknown_unprobed_slot_count")),
            _coerce_int(((precomputed.get("basis_counts") or {}).get("unknown_unprobed"))),
        ),
        "observed_error_slot_count": _coalesce(
            _coerce_int(precomputed.get("observed_error_slot_count")),
            _coerce_int(((precomputed.get("basis_counts") or {}).get("observed_error"))),
        ),
        "revoked_slot_count": _coerce_int(precomputed.get("revoked_slot_count")),
        "quarantined_slot_count": _coerce_int(precomputed.get("quarantined_slot_count")),
        "slots": precomputed.get("slots") if isinstance(precomputed.get("slots"), list) else None,
        "probe_note": precomputed.get("probe_note"),
        "status_basis": precomputed.get("status_basis"),
        "incoming_topups_excluded": _bool_or_none(precomputed.get("incoming_topups_excluded")),
    }

    for key, value in mapped_precomputed.items():
        if use_precomputed_only:
            aggregate[key] = value
            continue
        if aggregate.get(key) in (None, "") and value not in (None, ""):
            aggregate[key] = value

    aggregate["slot_count"] = _coerce_int(aggregate.get("slot_count")) or 0
    known_balance = _coerce_int(aggregate.get("slot_count_with_known_balance"))
    if known_balance is not None:
        aggregate["slot_count_with_balance"] = known_balance
        aggregate["unknown_balance_slot_count"] = max(int(aggregate["slot_count"]) - known_balance, 0)
    known_max = _coerce_int(aggregate.get("slot_count_with_known_max"))
    if known_max is not None:
        aggregate["unknown_max_slot_count"] = max(int(aggregate["slot_count"]) - known_max, 0)
    if aggregate.get("incoming_topups_excluded") is None:
        aggregate["incoming_topups_excluded"] = True
    aggregate["days_left_at_7d_avg_burn"] = aggregate.get("days_remaining_at_7d_avg_burn")
    aggregate["used_precomputed_aggregate"] = True
    return aggregate


def _render_onemin_slots(slots: list[dict[str, Any]]) -> list[str]:
    lines = ["Slot details:"]
    for index, slot in enumerate(slots, start=1):
        label = _onemin_slot_label(slot, index)
        bits = [
            str(slot.get("state") or "unknown").strip() or "unknown",
            str(slot.get("basis") or "unknown").strip() or "unknown",
        ]
        free_credits = _coerce_int(slot.get("free_credits"))
        max_credits = _coerce_int(slot.get("max_credits"))
        if free_credits is not None or max_credits is not None:
            bits.append(f"{_format_int(free_credits)} free / {_format_int(max_credits)} max")
        if slot.get("revoked_like"):
            bits.append("revoked-like")
        quarantine_until = str(slot.get("quarantine_until") or "").strip()
        if quarantine_until:
            bits.append(f"quarantine {quarantine_until}")
        detail = _shorten(_coalesce(slot.get("detail"), slot.get("last_error")) or "", limit=120)
        if detail:
            bits.append(detail)
        lines.append(f"- {label}: " + " | ".join(bit for bit in bits if bit))
    return lines


def _render_onemin_aggregate(aggregate: dict[str, Any], *, include_slots: bool = False) -> str:
    slot_count = _coerce_int(aggregate.get("slot_count")) or 0
    known_balance = _coerce_int(aggregate.get("slot_count_with_known_balance"))
    unknown_balance = _coerce_int(aggregate.get("unknown_balance_slot_count"))
    slot_bits = [f"{slot_count} total"]
    if known_balance is not None:
        slot_bits.append(f"{known_balance} with reported balance")
    if unknown_balance not in (None, 0):
        slot_bits.append(f"{unknown_balance} balance unknown")

    credits_bits = [f"{_format_int(_coerce_int(aggregate.get('sum_free_credits')))} free"]
    credits_bits.append(f"{_format_int(_coerce_int(aggregate.get('sum_max_credits')))} max")
    remaining = _coerce_float(aggregate.get("remaining_percent_total"))
    if remaining is not None:
        credits_bits.append(f"{_format_decimal(remaining, suffix='%')} left")

    current_pace_bits = [f"{_format_decimal(_coerce_float(aggregate.get('current_pace_burn_credits_per_hour')), precision=1)} cr/h"]
    hours_remaining = _coerce_float(aggregate.get("hours_remaining_at_current_pace"))
    if hours_remaining is not None:
        current_pace_bits.append(
            f"ETA {_format_decimal(hours_remaining, suffix='h')} ({_format_decimal(hours_remaining / 24.0, suffix='d')})"
        )

    avg_daily_burn = _coerce_float(aggregate.get("avg_daily_burn_credits_7d"))
    seven_day_bits = [f"{_format_decimal(avg_daily_burn, precision=1)} cr/day"]
    days_remaining = _coerce_float(aggregate.get("days_remaining_at_7d_avg_burn"))
    if days_remaining is not None:
        seven_day_bits.append(f"{_format_decimal(days_remaining, suffix='d')} left")

    lines = [
        "1min aggregate",
        "Slots: " + " | ".join(slot_bits),
        "Credits: " + " / ".join(credits_bits[:2]) + (f" ({credits_bits[2]})" if len(credits_bits) > 2 else ""),
        "Current pace: " + " | ".join(current_pace_bits),
        "7d average burn: " + " | ".join(seven_day_bits),
        f"Basis: {str(aggregate.get('basis_summary') or 'unknown')}",
        f"State: {str(aggregate.get('state_summary') or 'unknown')}",
    ]
    observed_bits: list[str] = []
    unknown_unprobed = _coerce_int(aggregate.get("unknown_unprobed_slot_count"))
    if unknown_unprobed not in (None, 0):
        observed_bits.append(f"unknown/unprobed {unknown_unprobed}")
    observed_error = _coerce_int(aggregate.get("observed_error_slot_count"))
    if observed_error not in (None, 0):
        observed_bits.append(f"observed_error {observed_error}")
    revoked_count = _coerce_int(aggregate.get("revoked_slot_count"))
    if revoked_count not in (None, 0):
        observed_bits.append(f"revoked-like {revoked_count}")
    quarantined_count = _coerce_int(aggregate.get("quarantined_slot_count"))
    if quarantined_count not in (None, 0):
        observed_bits.append(f"quarantined {quarantined_count}")
    if observed_bits:
        lines.append("Observed slot flags: " + " | ".join(observed_bits))
    status_basis = str(aggregate.get("status_basis") or "").strip()
    if status_basis:
        lines.append(f"Status basis: {status_basis}")
    incoming_topups_excluded = _bool_or_none(aggregate.get("incoming_topups_excluded"))
    lines.append(f"Top-ups excluded: {'yes' if incoming_topups_excluded is not False else 'no'}")
    probe_note = str(aggregate.get("probe_note") or "").strip()
    if probe_note:
        lines.append(f"Probe note: {probe_note}")
    if include_slots:
        slots = aggregate.get("slots")
        if isinstance(slots, list) and slots:
            lines.extend(_render_onemin_slots([slot for slot in slots if isinstance(slot, dict)]))
    return "\n".join(lines)


def _onemin_aggregate_response(*, refresh: bool = True, window: str = "7d", include_slots: bool = False) -> dict[str, Any]:
    payload = _ea_status_payload(refresh=refresh, window=window)
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "exit_code": 1,
            "message": "Live CodexEA status is unavailable right now; `codexea credits` requires `/v1/codex/status`.",
        }
    aggregate = _onemin_aggregate_payload(payload)
    if not isinstance(aggregate, dict):
        return {
            "ok": False,
            "exit_code": 1,
            "message": "Live CodexEA status refreshed, but no 1min aggregate data was returned.",
        }
    return {
        "ok": True,
        "exit_code": 0,
        "message": _render_onemin_aggregate(aggregate, include_slots=include_slots),
        "data": aggregate,
    }


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
    parser.add_argument("--onemin-aggregate", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--slots", action="store_true")
    parser.add_argument("--window", default="7d")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args(argv)
    if ns.telemetry_answer:
        response = _telemetry_response(" ".join(ns.args).strip())
        message = str(response.get("message") or "").strip()
        if message:
            stream = sys.stdout if int(response.get("exit_code") or 0) == 0 else sys.stderr
            print(message, file=stream)
        return int(response.get("exit_code") or 0)
    if ns.onemin_aggregate:
        response = _onemin_aggregate_response(
            refresh=True if ns.refresh or ns.onemin_aggregate else ns.refresh,
            window=ns.window,
            include_slots=ns.slots,
        )
        if ns.json:
            payload = {"ok": True, **dict(response.get("data") or {})} if response.get("ok") else {"ok": False, "error": str(response.get("message") or "").strip()}
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
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
