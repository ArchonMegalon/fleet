#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
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
TELEMETRY_SHORTCUT_TERMS: tuple[str, ...] = (
    "credit",
    "credits",
    "balance",
    "capacity",
    "quota",
    "burn",
    "remaining percent",
    "remaining %",
    "percent remaining",
    "percent left",
    "free credits",
)
FLEET_RUNTIME_QUERY_PREFIXES: tuple[str, ...] = (
    "how many",
    "what",
    "is",
    "are",
    "show",
    "list",
    "count",
    "status",
    "check",
    "tell me",
)
FLEET_RUNTIME_TARGET_TERMS: tuple[str, ...] = (
    "fleet",
    "fleet loop",
    "shard",
    "shards",
    "worker",
    "workers",
    "loop",
    "runtime",
    "supervisor",
)
FLEET_RUNTIME_SIGNAL_TERMS: tuple[str, ...] = (
    "running",
    "active",
    "alive",
    "busy",
    "idle",
    "status",
    "count",
    "currently",
    "right now",
    "now",
)
LANE_NAMES: tuple[str, ...] = ("easy", "repair", "groundwork", "review_light", "core", "jury", "survival")
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
_LAST_EA_HTTP_ERROR = ""
_LAST_EA_STATUS_SOURCE = ""
_LAST_EA_STATUS_FETCHED_AT = ""
_LAST_EA_PROFILES_SOURCE = ""
_LAST_EA_PROFILES_FETCHED_AT = ""

RUNTIME_CACHE_KEY_EA_CODEX_STATUS = "ea_codex_status"
RUNTIME_CACHE_KEY_EA_CODEX_PROFILES = "ea_codex_profiles"
FLEET_RUNTIME_STATUS_STALE_SECONDS = 600


def _runtime_env_candidates() -> tuple[Path, ...]:
    explicit_overrides = [
        Path(raw)
        for raw in (
            str(os.environ.get("CODEXEA_RUNTIME_EA_ENV_PATH") or "").strip(),
            str(os.environ.get("FLEET_RUNTIME_EA_ENV_PATH") or "").strip(),
        )
        if raw
    ]
    if explicit_overrides:
        ordered_overrides: list[Path] = []
        for path in explicit_overrides:
            if path not in ordered_overrides:
                ordered_overrides.append(path)
        return tuple(ordered_overrides)
    ordered: list[Path] = []
    for raw in (
        str(ROOT / "runtime.ea.env"),
        str(ROOT / "runtime.env"),
        "/docker/EA/.env.local",
        "/docker/EA/.env",
    ):
        if not raw:
            continue
        path = Path(raw)
        if path not in ordered:
            ordered.append(path)
    return tuple(ordered)


def _strip_wrapping_quotes(value: str) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _runtime_env_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for env_path in _runtime_env_candidates():
        if not env_path.exists():
            continue
        try:
            lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export ") :].lstrip()
            key, value = line.split("=", 1)
            key = key.strip()
            value = _strip_wrapping_quotes(value)
            if not key or not value or key in values:
                continue
            values[key] = value
    return values


def _env_value(name: str, default: str = "") -> str:
    direct = str(os.environ.get(name) or "").strip()
    if direct:
        return direct
    return str(_runtime_env_values().get(name) or default).strip()


def _env_flag(name: str, default: bool = False) -> bool:
    value = _env_value(name)
    if not value:
        return bool(default)
    return value.strip().lower() not in {"0", "false", "off", "no"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env_value(name) or default)
    except Exception:
        return float(default)


def _utc_now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _parse_utc_datetime(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.fromtimestamp(float(value), tz=dt.timezone.utc)
        except Exception:
            return None
    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00", 1) if raw.endswith("Z") else raw
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except Exception:
        try:
            parsed = dt.datetime.fromtimestamp(float(raw), tz=dt.timezone.utc)
        except Exception:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _humanize_age(timestamp: dt.datetime, *, now: dt.datetime) -> str:
    delta = now - timestamp
    if delta.total_seconds() <= 0:
        return "just now"
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _prefer_runtime_auth_values() -> bool:
    raw = str(os.environ.get("CODEXEA_PREFER_RUNTIME_AUTH", "1") or "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def _auth_env_value(name: str, default: str = "") -> str:
    direct = str(os.environ.get(name) or "").strip()
    runtime = str(_runtime_env_values().get(name) or "").strip()
    if _prefer_runtime_auth_values() and runtime:
        return runtime
    return direct or default


def _ea_api_token() -> str:
    return _auth_env_value("EA_MCP_API_TOKEN") or _auth_env_value("EA_API_TOKEN")


def _ea_http_error_detail(value: str) -> str:
    detail = str(value or "").strip()
    if detail == "missing_api_token":
        return "EA API token is not configured"
    return detail or "unavailable"


def _normalize_ea_base_url(value: str) -> str:
    base_url = str(value or "").strip().rstrip("/")
    if not base_url:
        return ""
    parsed = urllib.parse.urlsplit(base_url)
    hostname = str(parsed.hostname or "").strip().lower()
    if hostname != "host.docker.internal":
        return base_url
    try:
        socket.gethostbyname(hostname)
        return base_url
    except OSError:
        pass
    replacement = parsed.netloc.replace(parsed.hostname or "", "127.0.0.1", 1)
    return urllib.parse.urlunsplit((parsed.scheme, replacement, parsed.path, parsed.query, parsed.fragment)).rstrip("/")


def _ea_base_url() -> str:
    return _normalize_ea_base_url(_env_value("EA_MCP_BASE_URL") or _env_value("EA_BASE_URL") or "http://127.0.0.1:8090")


def _core_guard_enabled() -> bool:
    return str(os.environ.get("CODEXEA_CORE_GUARD_ENABLED", "1")).strip().lower() not in {"0", "false", "off", "no"}


def _core_min_onemin_credits() -> int:
    try:
        return max(0, int(float(str(os.environ.get("CODEXEA_CORE_MIN_ONEMIN_CREDITS", "100000")))))
    except Exception:
        return 100000


def _onemin_billing_timeout_seconds() -> float:
    return max(_env_float("CODEXEA_ONEMIN_BILLING_TIMEOUT_SECONDS", 30.0), 1.0)


def _onemin_live_status_timeout_seconds() -> float:
    return max(_env_float("CODEXEA_ONEMIN_STATUS_TIMEOUT_SECONDS", 30.0), 1.0)


def _onemin_billing_include_members() -> bool:
    return _env_flag("CODEXEA_ONEMIN_INCLUDE_MEMBERS", True)


def _onemin_billing_capture_raw_text() -> bool:
    return _env_flag("CODEXEA_ONEMIN_CAPTURE_RAW_TEXT", True)


def _ea_status_url() -> str:
    base_url = _env_value("CODEXEA_STATUS_URL")
    if base_url:
        return _normalize_ea_base_url(base_url)
    root = _ea_base_url()
    return f"{root}/v1/codex/status"


def _ea_profiles_url() -> str:
    base_url = _env_value("CODEXEA_PROFILES_URL")
    if base_url:
        return _normalize_ea_base_url(base_url)
    root = _ea_base_url()
    return f"{root}/v1/codex/profiles"


def _ea_onemin_probe_url() -> str:
    root = _ea_base_url()
    return f"{root}/v1/providers/onemin/probe-all"


def _ea_onemin_billing_refresh_url() -> str:
    root = _ea_base_url()
    return f"{root}/v1/providers/onemin/billing-refresh"


def _ea_http_payload(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout_seconds: float = 1.0,
) -> dict[str, Any] | None:
    global _LAST_EA_HTTP_ERROR
    principal_id = (
        _env_value("EA_MCP_PRINCIPAL_ID")
        or _env_value("EA_PRINCIPAL_ID")
        or "codexea-route"
    )
    headers = {"X-EA-Principal-ID": principal_id}
    api_token = _ea_api_token()
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
        headers["X-EA-Api-Token"] = api_token
        headers["X-API-Token"] = api_token
    data = None
    request_method = str(method or "GET").upper()
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(url, headers=headers, method=request_method, data=data)
    try:
        with urllib.request.urlopen(request, timeout=max(float(timeout_seconds or 1.0), 0.1)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except TimeoutError:
        _LAST_EA_HTTP_ERROR = f"timed out after {int(round(float(timeout_seconds or 0)))}s"
        return None
    except urllib.error.HTTPError as exc:
        if exc.code == 401 and not api_token:
            _LAST_EA_HTTP_ERROR = "missing_api_token"
        else:
            _LAST_EA_HTTP_ERROR = f"http_{exc.code}"
        return None
    except urllib.error.URLError as exc:
        _LAST_EA_HTTP_ERROR = str(exc.reason or exc)
        return None
    except ValueError:
        _LAST_EA_HTTP_ERROR = "invalid_json"
        return None
    except OSError as exc:
        _LAST_EA_HTTP_ERROR = str(exc)
        return None
    _LAST_EA_HTTP_ERROR = ""
    return payload if isinstance(payload, dict) else None


def _fleet_db_candidates() -> tuple[Path, ...]:
    explicit_override = str(os.environ.get("CODEXEA_FLEET_DB_PATH") or "").strip()
    if explicit_override:
        return (Path(explicit_override),)
    ordered: list[Path] = []
    for raw in (
        str(os.environ.get("FLEET_DB_PATH") or "").strip(),
        str(ROOT / "state" / "fleet.db"),
        str(ROOT / "fleet.db"),
    ):
        if not raw:
            continue
        path = Path(raw)
        if path not in ordered:
            ordered.append(path)
    return tuple(ordered)


def _load_local_runtime_cache_payload(cache_key: str) -> tuple[dict[str, Any] | None, str]:
    for db_path in _fleet_db_candidates():
        if not db_path.exists():
            continue
        try:
            with sqlite3.connect(str(db_path)) as conn:
                row = conn.execute(
                    "SELECT payload_json, fetched_at FROM runtime_caches WHERE cache_key=?",
                    (cache_key,),
                ).fetchone()
        except sqlite3.Error:
            continue
        if not row:
            continue
        try:
            payload = json.loads(str(row[0] or "{}"))
        except ValueError:
            continue
        if isinstance(payload, dict) and payload:
            return payload, str(row[1] or "").strip()
    return None, ""


def _ea_status_payload(
    *,
    refresh: bool = False,
    window: str = "1h",
    timeout_seconds: float = 2.0,
    prefer_cache: bool = False,
) -> dict[str, Any] | None:
    global _LAST_EA_STATUS_SOURCE, _LAST_EA_STATUS_FETCHED_AT
    if prefer_cache:
        cached_payload, fetched_at = _load_local_runtime_cache_payload(RUNTIME_CACHE_KEY_EA_CODEX_STATUS)
        if isinstance(cached_payload, dict):
            _LAST_EA_STATUS_SOURCE = "local_runtime_cache"
            _LAST_EA_STATUS_FETCHED_AT = fetched_at
            return cached_payload
    url = f"{_ea_status_url()}?window={window}&refresh={1 if refresh else 0}"
    payload = _ea_http_payload(url, timeout_seconds=max(float(timeout_seconds or 0.0), 0.1))
    if isinstance(payload, dict):
        _LAST_EA_STATUS_SOURCE = "live"
        _LAST_EA_STATUS_FETCHED_AT = ""
        return payload
    cached_payload, fetched_at = _load_local_runtime_cache_payload(RUNTIME_CACHE_KEY_EA_CODEX_STATUS)
    if isinstance(cached_payload, dict):
        _LAST_EA_STATUS_SOURCE = "local_runtime_cache"
        _LAST_EA_STATUS_FETCHED_AT = fetched_at
        return cached_payload
    _LAST_EA_STATUS_SOURCE = ""
    _LAST_EA_STATUS_FETCHED_AT = ""
    return None


def _ea_profiles_payload(*, timeout_seconds: float = 2.0, prefer_cache: bool = False) -> dict[str, Any] | None:
    global _LAST_EA_PROFILES_SOURCE, _LAST_EA_PROFILES_FETCHED_AT
    if prefer_cache:
        cached_payload, fetched_at = _load_local_runtime_cache_payload(RUNTIME_CACHE_KEY_EA_CODEX_PROFILES)
        if isinstance(cached_payload, dict):
            _LAST_EA_PROFILES_SOURCE = "local_runtime_cache"
            _LAST_EA_PROFILES_FETCHED_AT = fetched_at
            return cached_payload
    payload = _ea_http_payload(_ea_profiles_url(), timeout_seconds=max(float(timeout_seconds or 0.0), 0.1))
    if isinstance(payload, dict):
        _LAST_EA_PROFILES_SOURCE = "live"
        _LAST_EA_PROFILES_FETCHED_AT = ""
        return payload
    cached_payload, fetched_at = _load_local_runtime_cache_payload(RUNTIME_CACHE_KEY_EA_CODEX_PROFILES)
    if isinstance(cached_payload, dict):
        _LAST_EA_PROFILES_SOURCE = "local_runtime_cache"
        _LAST_EA_PROFILES_FETCHED_AT = fetched_at
        return cached_payload
    _LAST_EA_PROFILES_SOURCE = ""
    _LAST_EA_PROFILES_FETCHED_AT = ""
    return None


def _ea_onemin_probe_payload(*, include_reserve: bool = True) -> dict[str, Any] | None:
    return _ea_http_payload(
        _ea_onemin_probe_url(),
        method="POST",
        payload={"include_reserve": include_reserve},
        timeout_seconds=max(float(os.environ.get("CODEXEA_ONEMIN_PROBE_TIMEOUT_SECONDS") or 180.0), 1.0),
    )


def _ea_onemin_billing_refresh_payload(
    *,
    include_members: bool = True,
    capture_raw_text: bool = True,
    provider_api_all_accounts: bool = False,
    provider_api_continue_on_rate_limit: bool = False,
) -> dict[str, Any] | None:
    return _ea_http_payload(
        _ea_onemin_billing_refresh_url(),
        method="POST",
        payload={
            "include_members": include_members,
            "capture_raw_text": capture_raw_text,
            "provider_api_all_accounts": provider_api_all_accounts,
            "provider_api_continue_on_rate_limit": provider_api_continue_on_rate_limit,
        },
        timeout_seconds=_onemin_billing_timeout_seconds(),
    )


def _seed_local_ea_runtime_env() -> None:
    for key, value in _runtime_env_values().items():
        if value:
            os.environ.setdefault(str(key), str(value))


def _local_onemin_direct_payload(*, probe_all: bool = False, include_reserve: bool = True) -> dict[str, Any] | None:
    try:
        _seed_local_ea_runtime_env()
        for root in ("/docker/EA", "/docker/EA/ea"):
            if root not in sys.path:
                sys.path.insert(0, root)
        from app.services import responses_upstream as upstream  # type: ignore

        probe_payload = upstream.probe_all_onemin_slots(include_reserve=include_reserve) if probe_all else None
        provider_health = upstream._provider_health_report()
        onemin = dict(((provider_health.get("providers") or {}).get("onemin") or {}))
        slot_count = len(onemin.get("slots") or []) if isinstance(onemin.get("slots"), list) else 0
        probe_slot_count = int((probe_payload or {}).get("slot_count") or 0) if isinstance(probe_payload, dict) else 0
        if (not onemin or slot_count <= 0) and probe_slot_count <= 0:
            return None
        payload: dict[str, Any] = {
            "provider_health": {
                "providers": {
                    "onemin": onemin,
                }
            }
        }
        if isinstance(probe_payload, dict):
            payload["probe"] = probe_payload
        return payload
    except Exception:
        return None


def _source_notice(
    *,
    payload_source: str,
    fetched_at: str = "",
    status_error: str = "",
    profiles_error: str = "",
) -> str:
    if payload_source == "direct_local_onemin":
        return "Note: Live CodexEA status is unavailable or stale; using direct local 1min provider health."
    if payload_source == "status_local_runtime_cache":
        detail = _ea_http_error_detail(status_error)
        suffix = f" from {fetched_at}" if fetched_at else ""
        return f"Note: Live CodexEA status is unavailable ({detail}); using local Fleet runtime cache{suffix}."
    if payload_source == "profiles_local_runtime_cache":
        status_detail = _ea_http_error_detail(status_error)
        profiles_detail = _ea_http_error_detail(profiles_error)
        suffix = f" from {fetched_at}" if fetched_at else ""
        return (
            "Note: Live CodexEA status/profiles are unavailable "
            f"({status_detail}; profiles {profiles_detail}); using local Fleet runtime cache{suffix}."
        )
    return ""


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


def _looks_like_query_text(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return False
    if lowered.endswith("?"):
        return True
    return any(lowered == prefix or lowered.startswith(f"{prefix} ") for prefix in FLEET_RUNTIME_QUERY_PREFIXES)


def _looks_like_direct_fleet_runtime_query(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not _looks_like_query_text(lowered):
        return False
    if "eta" in lowered:
        return False
    return _contains_any(lowered, FLEET_RUNTIME_TARGET_TERMS) and _contains_any(lowered, FLEET_RUNTIME_SIGNAL_TERMS)


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
    has_target = bool(_provider_from_text(lowered) or _lane_from_text(lowered))
    has_signal = _contains_any(lowered, TELEMETRY_SIGNAL_TERMS)
    if has_target and has_signal:
        return True
    return _contains_any(lowered, TELEMETRY_SHORTCUT_TERMS)


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


def _format_timestamp(value: Any) -> str:
    if value in (None, ""):
        return ""
    parsed = _parse_utc_datetime(value)
    if parsed is None:
        return str(value).strip()
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


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
    owner = (
        str(slot.get("owner_email") or "").strip()
        or str(slot.get("owner_label") or "").strip()
        or str(slot.get("owner_name") or "").strip()
    )
    slot_env_name = str(slot.get("slot_env_name") or slot.get("account_name") or "").strip()
    if owner and slot_env_name and owner != slot_env_name:
        return f"{owner} [{slot_env_name}]"
    return owner or slot_env_name or f"slot-{index}"


def _render_active_fleet_shard_label(item: dict[str, Any]) -> str:
    label = str(item.get("name") or item.get("_shard") or "").strip() or "unnamed shard"
    active_run_id = str(item.get("active_run_id") or "").strip()
    frontier_count = len(item.get("frontier_ids") or [])
    details: list[str] = []
    if active_run_id:
        details.append(f"run {active_run_id}")
    if frontier_count:
        details.append(f"{frontier_count} milestone{'s' if frontier_count != 1 else ''}")
    if not details:
        return label
    return f"{label} ({', '.join(details)})"


def _fleet_runtime_updated_fragment(updated_at: str) -> str:
    parsed = _parse_utc_datetime(updated_at)
    if parsed is None:
        return f"updated {updated_at}"
    now = _utc_now()
    age = _humanize_age(parsed, now=now)
    stale = " (stale)" if (now - parsed).total_seconds() > FLEET_RUNTIME_STATUS_STALE_SECONDS else ""
    if stale:
        return (
            f"updated {age} at {_format_timestamp(parsed)}{stale}; "
            "run `chummer_design_supervisor status` to refresh this snapshot."
        )
    return f"updated {age} at {_format_timestamp(parsed)}"


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
                "slot_env_name": str(row.get("slot_env_name") or row.get("account_name") or "").strip(),
                "slot": str(row.get("slot") or "").strip(),
                "slot_role": str(row.get("slot_role") or "").strip(),
                "owner_label": str(row.get("owner_label") or "").strip(),
                "owner_name": str(row.get("owner_name") or "").strip(),
                "owner_email": str(row.get("owner_email") or "").strip(),
                "max_credits": _coerce_int(row.get("max_credits")),
                "free_credits": _coerce_int(row.get("free_credits")),
                "basis": str(row.get("basis") or "").strip() or "unknown",
                "state": str(row.get("state") or "").strip() or "unknown",
                "detail": str(row.get("detail") or "").strip(),
                "last_error": str(row.get("last_error") or "").strip(),
                "quarantine_until": str(row.get("quarantine_until") or "").strip(),
                "last_probe_at": row.get("last_probe_at"),
                "last_probe_result": str(row.get("last_probe_result") or "").strip(),
                "last_probe_detail": str(row.get("last_probe_detail") or "").strip(),
                "last_probe_model": str(row.get("last_probe_model") or "").strip(),
                "last_probe_latency_ms": _coerce_int(row.get("last_probe_latency_ms")),
            }
        )

    if not rows:
        providers = ((payload.get("provider_health") or {}).get("providers") or {})
        onemin_row = providers.get("onemin") if isinstance(providers, dict) else None
        if isinstance(onemin_row, dict):
            slot_rows = onemin_row.get("slots")
            if isinstance(slot_rows, list):
                for row in slot_rows:
                    if not isinstance(row, dict):
                        continue
                    rows.append(
                        {
                            "account_name": str(row.get("account_name") or "").strip(),
                            "slot_env_name": str(row.get("slot_env_name") or row.get("account_name") or "").strip(),
                            "slot": str(row.get("slot") or "").strip(),
                            "slot_role": str(row.get("slot_role") or "").strip(),
                            "owner_label": str(row.get("owner_label") or "").strip(),
                            "owner_name": str(row.get("owner_name") or "").strip(),
                            "owner_email": str(row.get("owner_email") or "").strip(),
                            "max_credits": _coerce_int(row.get("max_credits")),
                            "free_credits": _coerce_int(_coalesce(row.get("free_credits"), row.get("estimated_remaining_credits"))),
                            "basis": str(row.get("basis") or onemin_row.get("basis") or payload.get("status_basis") or "profiles_fallback").strip() or "profiles_fallback",
                            "state": str(row.get("state") or onemin_row.get("state") or "").strip() or "unknown",
                            "detail": str(row.get("detail") or "").strip(),
                            "last_error": str(row.get("last_error") or "").strip(),
                            "quarantine_until": str(row.get("quarantine_until") or "").strip(),
                            "last_probe_at": row.get("last_probe_at"),
                            "last_probe_result": str(row.get("last_probe_result") or "").strip(),
                            "last_probe_detail": str(row.get("last_probe_detail") or "").strip(),
                            "last_probe_model": str(row.get("last_probe_model") or "").strip(),
                            "last_probe_latency_ms": _coerce_int(row.get("last_probe_latency_ms")),
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
        "probe_result_counts": {},
        "owner_mapped_slot_count": sum(
            1 for row in rows if str(row.get("owner_label") or row.get("owner_name") or row.get("owner_email") or "").strip()
        ),
        "last_probe_at": max((float(row.get("last_probe_at") or 0.0) for row in rows), default=0.0) or None,
        "slots": [
            {
                "account_name": _onemin_slot_label(row, index + 1),
                "slot_env_name": str(row.get("slot_env_name") or row.get("account_name") or "").strip(),
                "slot": str(row.get("slot") or "").strip(),
                "slot_role": str(row.get("slot_role") or "").strip(),
                "owner_label": str(row.get("owner_label") or "").strip(),
                "owner_name": str(row.get("owner_name") or "").strip(),
                "owner_email": str(row.get("owner_email") or "").strip(),
                "state": str(row.get("state") or "").strip() or "unknown",
                "basis": str(row.get("basis") or "").strip() or "unknown",
                "free_credits": row.get("free_credits"),
                "max_credits": row.get("max_credits"),
                "detail": str(row.get("detail") or "").strip(),
                "last_error": str(row.get("last_error") or "").strip(),
                "quarantine_until": str(row.get("quarantine_until") or "").strip(),
                "last_probe_at": row.get("last_probe_at"),
                "last_probe_result": str(row.get("last_probe_result") or "").strip(),
                "last_probe_detail": str(row.get("last_probe_detail") or "").strip(),
                "last_probe_model": str(row.get("last_probe_model") or "").strip(),
                "last_probe_latency_ms": row.get("last_probe_latency_ms"),
                "revoked_like": _onemin_slot_revoked_like(row),
                "quarantined": bool(str(row.get("quarantine_until") or "").strip()),
            }
            for index, row in enumerate(rows)
        ],
        "probe_note": (
            "unknown_unprobed means no live evidence yet; run `codexea onemin --probe-all` to classify untouched slots explicitly."
            if unknown_unprobed_count > 0
            else ""
        ),
        "status_basis": str(payload.get("status_basis") or "").strip(),
        "incoming_topups_excluded": True,
        "used_precomputed_aggregate": False,
    }
    for row in rows:
        probe_result = str(row.get("last_probe_result") or "").strip()
        if not probe_result:
            continue
        aggregate["probe_result_counts"][probe_result] = int((aggregate["probe_result_counts"] or {}).get(probe_result) or 0) + 1

    if not isinstance(precomputed, dict):
        precomputed = {}

    billing = payload.get("onemin_billing_aggregate")
    if not isinstance(billing, dict):
        billing = {}

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
        "probe_result_counts": precomputed.get("probe_result_counts") if isinstance(precomputed.get("probe_result_counts"), dict) else None,
        "owner_mapped_slot_count": _coerce_int(precomputed.get("owner_mapped_slot_count")),
        "last_probe_at": precomputed.get("last_probe_at"),
        "slots": precomputed.get("slots") if isinstance(precomputed.get("slots"), list) else None,
        "probe_note": precomputed.get("probe_note"),
        "status_basis": precomputed.get("status_basis"),
        "incoming_topups_excluded": _bool_or_none(precomputed.get("incoming_topups_excluded")),
    }
    mapped_billing = {
        "slot_count_with_billing_snapshot": _coerce_int(billing.get("slot_count_with_billing_snapshot")),
        "slot_count_with_member_reconciliation": _coerce_int(billing.get("slot_count_with_member_reconciliation")),
        "sum_max_credits": _coerce_int(billing.get("sum_max_credits")),
        "sum_free_credits": _coerce_int(billing.get("sum_free_credits")),
        "remaining_percent_total": _coerce_float(billing.get("remaining_percent_total")),
        "current_pace_burn_credits_per_hour": _coerce_float(billing.get("current_pace_burn_credits_per_hour")),
        "avg_daily_burn_credits_7d": _coerce_float(billing.get("avg_daily_burn_credits_7d")),
        "next_topup_at": billing.get("next_topup_at"),
        "topup_amount": _coerce_float(billing.get("topup_amount")),
        "hours_until_next_topup": _coerce_float(billing.get("hours_until_next_topup")),
        "hours_remaining_at_current_pace_no_topup": _coerce_float(billing.get("hours_remaining_at_current_pace_no_topup")),
        "hours_remaining_including_next_topup_at_current_pace": _coerce_float(
            billing.get("hours_remaining_including_next_topup_at_current_pace")
        ),
        "days_remaining_including_next_topup_at_7d_avg": _coerce_float(
            billing.get("days_remaining_including_next_topup_at_7d_avg")
        ),
        "depletes_before_next_topup": _bool_or_none(billing.get("depletes_before_next_topup")),
        "basis_summary": _coalesce(billing.get("basis_summary"), mapped_precomputed.get("basis_summary")),
        "basis_counts": billing.get("basis_counts") if isinstance(billing.get("basis_counts"), dict) else None,
        "latest_member_reconciliation_at": billing.get("latest_member_reconciliation_at"),
    }

    for key, value in mapped_precomputed.items():
        if use_precomputed_only:
            aggregate[key] = value
            continue
        if aggregate.get(key) in (None, "") and value not in (None, ""):
            aggregate[key] = value
    for key, value in mapped_billing.items():
        if value not in (None, ""):
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
    if (_coerce_int(aggregate.get("unknown_unprobed_slot_count")) or 0) <= 0:
        aggregate["probe_note"] = ""
    effective_current_pace = _coerce_float(aggregate.get("current_pace_burn_credits_per_hour"))
    observed_usage_burn = _coerce_float(aggregate.get("observed_usage_burn_credits_per_hour"))
    avg_daily_burn_7d = _coerce_float(aggregate.get("avg_daily_burn_credits_7d"))
    avg_hourly_burn_7d = round(float(avg_daily_burn_7d) / 24.0, 2) if avg_daily_burn_7d not in (None, 0) else None
    burn_basis = str(aggregate.get("burn_basis") or "").strip()
    if effective_current_pace in (None, 0):
        if observed_usage_burn not in (None, 0):
            effective_current_pace = observed_usage_burn
            if not burn_basis or burn_basis == "unknown":
                burn_basis = "observed_usage"
        elif avg_hourly_burn_7d not in (None, 0):
            effective_current_pace = avg_hourly_burn_7d
            if not burn_basis or burn_basis == "unknown":
                burn_basis = "7d_average"
        else:
            effective_current_pace = None
            if not burn_basis:
                burn_basis = "unknown"
    elif not burn_basis or burn_basis == "unknown":
        if observed_usage_burn not in (None, 0) and abs(float(effective_current_pace) - float(observed_usage_burn)) < 0.01:
            burn_basis = "observed_usage"
        elif avg_hourly_burn_7d not in (None, 0) and abs(float(effective_current_pace) - float(avg_hourly_burn_7d)) < 0.01:
            burn_basis = "7d_average"
        else:
            burn_basis = "estimated_pool"
    aggregate["current_pace_burn_credits_per_hour"] = effective_current_pace
    aggregate["burn_basis"] = burn_basis or "unknown"
    sum_free_total = _coerce_float(aggregate.get("sum_free_credits"))
    if _coerce_float(aggregate.get("hours_remaining_at_current_pace")) is None and sum_free_total not in (None, 0) and effective_current_pace not in (None, 0):
        aggregate["hours_remaining_at_current_pace"] = round(float(sum_free_total) / float(effective_current_pace), 2)
    if _coerce_float(aggregate.get("hours_remaining_at_current_pace_no_topup")) is None and sum_free_total not in (None, 0) and effective_current_pace not in (None, 0):
        aggregate["hours_remaining_at_current_pace_no_topup"] = round(float(sum_free_total) / float(effective_current_pace), 2)
    aggregate["days_left_at_7d_avg_burn"] = aggregate.get("days_remaining_at_7d_avg_burn")
    aggregate["used_precomputed_aggregate"] = True
    return aggregate


def _render_onemin_slots(
    slots: list[dict[str, Any]],
    *,
    slot_detail: str = "verbose",
) -> list[str]:
    lines = ["Slot details:"]
    labeled_slots = [
        (index, _onemin_slot_label(slot, index), slot)
        for index, slot in enumerate(slots, start=1)
    ]
    for _display_index, label, slot in sorted(labeled_slots, key=lambda item: (str(item[1]).strip().lower(), int(item[0]))):
        slot_role = str(slot.get("slot_role") or "").strip()
        state = str(slot.get("state") or "unknown").strip() or "unknown"
        basis = str(slot.get("basis") or "unknown").strip() or "unknown"
        owner = (
            str(slot.get("owner_email") or "").strip()
            or str(slot.get("owner_label") or "").strip()
            or str(slot.get("owner_name") or "").strip()
        )
        free_credits = _coerce_int(slot.get("free_credits"))
        max_credits = _coerce_int(slot.get("max_credits"))
        if slot_detail == "compact":
            compact_bits = [state, basis]
            if free_credits is not None or max_credits is not None:
                compact_bits.append(f"{_format_int(free_credits)} free / {_format_int(max_credits)} max")
            if owner:
                compact_bits.append(f"owner {owner}")
            lines.append(f"- {label}: " + " | ".join(bit for bit in compact_bits if bit))
            continue
        bits = [
            slot_role,
            state,
            basis,
        ]
        if owner:
            bits.append(f"owner {owner}")
        if free_credits is not None or max_credits is not None:
            bits.append(f"{_format_int(free_credits)} free / {_format_int(max_credits)} max")
        probe_result = str(slot.get("last_probe_result") or "").strip()
        if probe_result:
            bits.append(f"probe {probe_result}")
        if slot.get("revoked_like"):
            bits.append("revoked-like")
        quarantine_until = str(slot.get("quarantine_until") or "").strip()
        if quarantine_until:
            bits.append(f"quarantine {quarantine_until}")
        detail = _shorten(_coalesce(slot.get("last_probe_detail"), slot.get("detail"), slot.get("last_error")) or "", limit=120)
        if detail:
            bits.append(detail)
        lines.append(f"- {label}: " + " | ".join(bit for bit in bits if bit))
    return lines


def _render_onemin_aggregate(
    aggregate: dict[str, Any],
    *,
    include_slots: bool = False,
    slots_detail: str = "verbose",
) -> str:
    slot_count = _coerce_int(aggregate.get("slot_count")) or 0
    known_balance = _coerce_int(aggregate.get("slot_count_with_known_balance"))
    billing_snapshot_count = _coerce_int(aggregate.get("slot_count_with_billing_snapshot"))
    unknown_balance = _coerce_int(aggregate.get("unknown_balance_slot_count"))
    slot_bits = [f"{slot_count} total"]
    if known_balance is not None:
        slot_bits.append(f"{known_balance} with reported balance")
    if billing_snapshot_count not in (None, 0):
        slot_bits.append(f"{billing_snapshot_count} with billing snapshots")
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
    owner_mapped = _coerce_int(aggregate.get("owner_mapped_slot_count"))
    if owner_mapped not in (None, 0):
        lines.append(f"Owner mapping: {owner_mapped} slot{'s' if owner_mapped != 1 else ''} mapped")
    member_snapshot_count = _coerce_int(aggregate.get("slot_count_with_member_reconciliation"))
    if member_snapshot_count not in (None, 0):
        lines.append(f"Member reconciliation: {member_snapshot_count} slot{'s' if member_snapshot_count != 1 else ''} with member snapshots")
    probe_counts = aggregate.get("probe_result_counts")
    if isinstance(probe_counts, dict) and probe_counts:
        probe_bits = []
        for key in sorted(probe_counts):
            count = _coerce_int(probe_counts.get(key))
            if count in (None, 0):
                continue
            probe_bits.append(f"{key} {count}")
        if probe_bits:
            lines.append("Latest explicit probes: " + " | ".join(probe_bits))
    last_probe_at = _format_timestamp(aggregate.get("last_probe_at"))
    if last_probe_at:
        lines.append(f"Last probe at: {last_probe_at}")
    status_basis = str(aggregate.get("status_basis") or "").strip()
    if status_basis:
        lines.append(f"Status basis: {status_basis}")
    next_topup_at = _format_timestamp(aggregate.get("next_topup_at")) or str(aggregate.get("next_topup_at") or "").strip()
    if next_topup_at:
        lines.append("Next top-up:")
        lines.append(f"- At: {next_topup_at}")
        topup_amount = _coerce_float(aggregate.get("topup_amount"))
        if topup_amount is not None:
            amount_text = _format_int(int(topup_amount)) if float(topup_amount).is_integer() else _format_decimal(topup_amount)
            lines.append(f"- Amount: {amount_text}")
        hours_until_topup = _coerce_float(aggregate.get("hours_until_next_topup"))
        if hours_until_topup is not None:
            lines.append(f"- Hours until top-up: {_format_decimal(hours_until_topup, suffix='h')}")
    runway_bits: list[str] = []
    no_topup = _coerce_float(aggregate.get("hours_remaining_at_current_pace_no_topup"))
    with_topup = _coerce_float(aggregate.get("hours_remaining_including_next_topup_at_current_pace"))
    with_topup_7d = _coerce_float(aggregate.get("days_remaining_including_next_topup_at_7d_avg"))
    depletes_before_topup = _bool_or_none(aggregate.get("depletes_before_next_topup"))
    if no_topup is not None:
        runway_bits.append(f"No top-up, current pace: {_format_decimal(no_topup, suffix='h')}")
    if with_topup is not None:
        runway_bits.append(f"Including next top-up, current pace: {_format_decimal(with_topup, suffix='h')}")
    if with_topup_7d is not None:
        runway_bits.append(f"Including next top-up, 7d average: {_format_decimal(with_topup_7d, suffix='d')}")
    if depletes_before_topup is not None:
        runway_bits.append(f"Depletes before next top-up: {'yes' if depletes_before_topup else 'no'}")
    if runway_bits:
        lines.append("Runway:")
        lines.extend(f"- {item}" for item in runway_bits)
    incoming_topups_excluded = _bool_or_none(aggregate.get("incoming_topups_excluded"))
    topups_included = incoming_topups_excluded is False
    lines.append(f"Top-ups: {'included' if topups_included else 'excluded'}")
    if not topups_included:
        lines.append(
            "To include top-up-aware runway in this view, rerun with --billing (or set CODEXEA_CREDITS_INCLUDE_BILLING=1)."
        )
    probe_note = str(aggregate.get("probe_note") or "").strip()
    if probe_note:
        lines.append(f"Probe note: {probe_note}")
    if include_slots:
        slots = aggregate.get("slots")
        if isinstance(slots, list) and slots:
            lines.extend(
                _render_onemin_slots(
                    [slot for slot in slots if isinstance(slot, dict)],
                    slot_detail=slots_detail,
                )
            )
    return "\n".join(lines)


def _render_onemin_probe_summary(probe_payload: dict[str, Any]) -> str:
    slot_count = _coerce_int(probe_payload.get("slot_count")) or 0
    configured_slot_count = _coerce_int(probe_payload.get("configured_slot_count")) or slot_count
    lines = [
        "1min probe-all",
        f"Slots: {slot_count} probed / {configured_slot_count} configured",
    ]
    owner_mapped = _coerce_int(probe_payload.get("owner_mapped_slots"))
    if owner_mapped not in (None, 0):
        lines.append(f"Owner mapping: {owner_mapped} slot{'s' if owner_mapped != 1 else ''} matched")
    result_counts = probe_payload.get("result_counts")
    if isinstance(result_counts, dict) and result_counts:
        bits = []
        for key in sorted(result_counts):
            count = _coerce_int(result_counts.get(key))
            if count in (None, 0):
                continue
            bits.append(f"{key} {count}")
        if bits:
            lines.append("Results: " + " | ".join(bits))
    probe_model = str(probe_payload.get("probe_model") or "").strip()
    if probe_model:
        lines.append(f"Model: {probe_model}")
    last_probe_at = _format_timestamp(probe_payload.get("last_probe_at"))
    if last_probe_at:
        lines.append(f"Completed: {last_probe_at}")
    note = str(probe_payload.get("note") or "").strip()
    if note:
        lines.append(f"Note: {note}")
    return "\n".join(lines)


def _render_onemin_billing_refresh_summary(refresh_payload: dict[str, Any]) -> str:
    binding_count = _coerce_int(refresh_payload.get("connector_binding_count")) or 0
    api_account_count = _coerce_int(refresh_payload.get("api_account_count")) or 0
    api_account_attempted = _coerce_int(refresh_payload.get("api_account_attempted")) or 0
    api_account_skipped = _coerce_int(refresh_payload.get("api_account_skipped")) or 0
    billing_count = _coerce_int(refresh_payload.get("billing_refresh_count")) or 0
    member_count = _coerce_int(refresh_payload.get("member_reconciliation_count")) or 0
    api_billing_count = _coerce_int(refresh_payload.get("api_billing_refresh_count")) or 0
    api_member_count = _coerce_int(refresh_payload.get("api_member_reconciliation_count")) or 0
    api_rate_limited = bool(refresh_payload.get("api_rate_limited"))
    lines = [
        "1min billing refresh",
        f"Bindings: {binding_count}",
        f"API accounts: {api_account_count} configured, {api_account_attempted} attempted, {api_account_skipped} skipped",
        f"Billing snapshots: {billing_count}",
        f"Member reconciliations: {member_count}",
    ]
    if api_rate_limited:
        lines.append("Direct API refresh: rate-limited, throttled")
    if api_billing_count or api_member_count:
        lines.append(f"Direct API refresh: billing {api_billing_count} | members {api_member_count}")
    selected_binding_ids = refresh_payload.get("selected_binding_ids")
    if isinstance(selected_binding_ids, list) and selected_binding_ids:
        lines.append(f"Selected bindings: {len(selected_binding_ids)}")
    skipped = refresh_payload.get("skipped")
    if isinstance(skipped, list) and skipped:
        reason_counts: dict[str, int] = {}
        for row in skipped:
            if not isinstance(row, dict):
                continue
            reason = str(row.get("reason") or "skipped").strip() or "skipped"
            reason_counts[reason] = int(reason_counts.get(reason) or 0) + 1
        if reason_counts:
            bits = [f"{key} {reason_counts[key]}" for key in sorted(reason_counts)]
            lines.append("Skipped: " + " | ".join(bits))
    errors = refresh_payload.get("errors")
    if isinstance(errors, list) and errors:
        error_counts: dict[str, int] = {}
        for row in errors:
            if not isinstance(row, dict):
                continue
            tool_name = str(row.get("tool_name") or "error").strip() or "error"
            error_counts[tool_name] = int(error_counts.get(tool_name) or 0) + 1
        bits = [f"{key} {error_counts[key]}" for key in sorted(error_counts)]
        if bits:
            lines.append("Errors: " + " | ".join(bits))
    note = str(refresh_payload.get("note") or "").strip()
    if note:
        lines.append(f"Note: {note}")
    return "\n".join(lines)


def _billing_refresh_used_cached_state(refresh_payload: dict[str, Any], aggregate: dict[str, Any]) -> bool:
    cached_snapshot_count = _coerce_int(aggregate.get("slot_count_with_billing_snapshot")) or 0
    if cached_snapshot_count <= 0:
        return False
    binding_count = _coerce_int(refresh_payload.get("connector_binding_count")) or 0
    billing_count = _coerce_int(refresh_payload.get("billing_refresh_count")) or 0
    member_count = _coerce_int(refresh_payload.get("member_reconciliation_count")) or 0
    api_billing_count = _coerce_int(refresh_payload.get("api_billing_refresh_count")) or 0
    api_member_count = _coerce_int(refresh_payload.get("api_member_reconciliation_count")) or 0
    return (
        binding_count == 0
        and billing_count == 0
        and member_count == 0
        and api_billing_count == 0
        and api_member_count == 0
    )


def _render_onemin_billing_refresh_cached_note(
    refresh_payload: dict[str, Any],
    *,
    live_probe_refreshed: bool = False,
) -> str:
    note = str(refresh_payload.get("note") or "").strip().rstrip(".")
    suffix = " Live slot balances were refreshed via probe-all." if live_probe_refreshed else ""
    if note:
        return f"Note: {note}. Showing cached billing state.{suffix}"
    return f"Note: Live 1min billing refresh produced no new snapshots; showing cached billing state.{suffix}"


def _route_json_payload(response: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "matched": bool(response.get("matched")),
        "ok": bool(response.get("ok")),
        "exit_code": int(response.get("exit_code") or 0),
    }
    message = str(response.get("message") or "").strip()
    if message:
        payload["message"] = message
    data = response.get("data")
    if isinstance(data, dict):
        payload["data"] = data
        for key, value in data.items():
            if key not in payload:
                payload[key] = value
    else:
        error = str(response.get("error") or "").strip()
        if error:
            payload["error"] = error
    for key, value in response.items():
        if key in {"matched", "ok", "exit_code", "message", "data"}:
            continue
        if key not in payload:
            payload[key] = value
    return payload


def _onemin_aggregate_response(
    *,
    refresh: bool = True,
    window: str = "7d",
    include_slots: bool = False,
    slots_detail: str = "verbose",
    probe_all: bool = False,
    billing: bool = False,
    billing_full_refresh: bool = False,
) -> dict[str, Any]:
    probe_payload = None
    billing_refresh_payload = None
    local_onemin_payload = None
    probe_warning = ""
    probe_error = ""
    billing_error = ""

    def _ensure_local_onemin_payload(*, run_probe: bool) -> dict[str, Any] | None:
        nonlocal local_onemin_payload
        if isinstance(local_onemin_payload, dict) and (not run_probe or isinstance(local_onemin_payload.get("probe"), dict)):
            return local_onemin_payload
        candidate = _local_onemin_direct_payload(probe_all=run_probe, include_reserve=True)
        if isinstance(candidate, dict):
            local_onemin_payload = candidate
        return local_onemin_payload if isinstance(local_onemin_payload, dict) else None

    if probe_all:
        probe_payload = _ea_onemin_probe_payload(include_reserve=True)
        if not isinstance(probe_payload, dict):
            probe_error = str(_LAST_EA_HTTP_ERROR or "did not return JSON").strip()
            local_probe_payload = _ensure_local_onemin_payload(run_probe=True)
            if isinstance(local_probe_payload, dict) and isinstance(local_probe_payload.get("probe"), dict):
                probe_payload = dict(local_probe_payload.get("probe") or {})
                probe_warning = (
                    "Note: Live 1min probe-all via the EA API was unavailable; "
                    "used a direct local 1min probe fallback instead."
                )
            elif probe_error == "missing_api_token":
                probe_warning = (
                    "Note: Live 1min probe-all was skipped because the EA API token is not configured. "
                    "Showing the best available cached aggregate without a fresh probe."
                )
            elif probe_error == "http_403":
                probe_warning = ""
            else:
                probe_warning = (
                    "Note: Live 1min probe-all failed; "
                    f"`/v1/providers/onemin/probe-all` {_ea_http_error_detail(probe_error)}. Showing the best available cached aggregate without a fresh probe."
                )
    if billing:
        billing_refresh_payload = _ea_onemin_billing_refresh_payload(
            include_members=_onemin_billing_include_members(),
            capture_raw_text=_onemin_billing_capture_raw_text(),
            provider_api_all_accounts=billing_full_refresh,
            provider_api_continue_on_rate_limit=billing_full_refresh,
        )
        billing_error = str(_LAST_EA_HTTP_ERROR or "").strip()
    live_status_timeout_seconds = _onemin_live_status_timeout_seconds()
    payload = _ea_status_payload(
        refresh=refresh,
        window=window,
        timeout_seconds=live_status_timeout_seconds,
        prefer_cache=not refresh,
    )
    payload_source = "status"
    payload_fetched_at = _LAST_EA_STATUS_FETCHED_AT
    status_error = str(_LAST_EA_HTTP_ERROR or "").strip()
    profiles_error = ""
    if _LAST_EA_STATUS_SOURCE == "local_runtime_cache":
        payload_source = "status_local_runtime_cache"
    if not isinstance(payload, dict):
        payload = _ea_profiles_payload(timeout_seconds=live_status_timeout_seconds, prefer_cache=not refresh)
        profiles_error = str(_LAST_EA_HTTP_ERROR or "").strip()
        payload_fetched_at = _LAST_EA_PROFILES_FETCHED_AT
        payload_source = "profiles_fallback"
        if _LAST_EA_PROFILES_SOURCE == "local_runtime_cache":
            payload_source = "profiles_local_runtime_cache"
    if not isinstance(payload, dict):
        local_payload = _ensure_local_onemin_payload(run_probe=False)
        if isinstance(local_payload, dict):
            payload = {
                "provider_health": dict(local_payload.get("provider_health") or {}),
            }
            payload_source = "direct_local_onemin"
            payload_fetched_at = ""
    if not isinstance(payload, dict):
        fragments: list[str] = []
        if isinstance(billing_refresh_payload, dict):
            fragments.append(_render_onemin_billing_refresh_summary(billing_refresh_payload))
        if isinstance(probe_payload, dict):
            fragments.append(_render_onemin_probe_summary(probe_payload))
        if fragments:
            if probe_warning:
                fragments.insert(0, probe_warning)
            fragments.append("Live CodexEA status is unavailable right now; showing direct 1min probe data without the full aggregate.")
            data: dict[str, Any] = {}
            if isinstance(probe_payload, dict):
                data["probe"] = probe_payload
            if isinstance(billing_refresh_payload, dict):
                data["billing_lookup"] = billing_refresh_payload
            return {
                "matched": True,
                "ok": True,
                "exit_code": 0,
                "message": "\n\n".join(fragments),
                "data": data,
                "payload_source": payload_source,
                "payload_fetched_at": payload_fetched_at,
                "status_error": status_error,
                "profiles_error": profiles_error,
            }
        if probe_warning:
            return {
                "matched": True,
                "ok": False,
                "exit_code": 1,
                "message": (
                    probe_warning
                    + "\n\nLive CodexEA status is unavailable right now; `codexea credits` requires `/v1/codex/status` or `/v1/codex/profiles`."
                ),
                "payload_source": payload_source,
                "payload_fetched_at": payload_fetched_at,
                "status_error": status_error,
                "profiles_error": profiles_error,
            }
        return {
            "matched": True,
            "ok": False,
            "exit_code": 1,
            "message": "Live CodexEA status is unavailable right now; `codexea credits` requires `/v1/codex/status` or `/v1/codex/profiles`.",
            "payload_source": payload_source,
            "payload_fetched_at": payload_fetched_at,
            "status_error": status_error,
            "profiles_error": profiles_error,
        }
    aggregate = _onemin_aggregate_payload(payload)
    local_aggregate = None
    current_slot_count = int((aggregate or {}).get("slot_count") or 0) if isinstance(aggregate, dict) else 0
    if not isinstance(aggregate, dict) or current_slot_count <= 0:
        local_payload = _ensure_local_onemin_payload(run_probe=False)
        if isinstance(local_payload, dict):
            local_aggregate = _onemin_aggregate_payload(
                {
                    "provider_health": dict(local_payload.get("provider_health") or {}),
                }
            )
    if isinstance(local_aggregate, dict):
        current_slot_count = int((aggregate or {}).get("slot_count") or 0) if isinstance(aggregate, dict) else 0
        local_slot_count = int(local_aggregate.get("slot_count") or 0)
        if local_slot_count > current_slot_count:
            aggregate = local_aggregate
            payload_source = "direct_local_onemin"
            payload_fetched_at = ""
    if not isinstance(aggregate, dict):
        if isinstance(probe_payload, dict):
            fragments = [_render_onemin_probe_summary(probe_payload)]
            if isinstance(billing_refresh_payload, dict):
                fragments.insert(0, _render_onemin_billing_refresh_summary(billing_refresh_payload))
            elif probe_warning:
                fragments.insert(0, probe_warning)
            fragments.append(f"Live CodexEA {payload_source.replace('_', ' ')} returned no 1min aggregate block; showing direct probe data only.")
            data = {"probe": probe_payload}
            if isinstance(billing_refresh_payload, dict):
                data["billing_lookup"] = billing_refresh_payload
            return {
                "matched": True,
                "ok": True,
                "exit_code": 0,
                "message": "\n\n".join(fragments),
                "data": data,
                "payload_source": payload_source,
                "payload_fetched_at": payload_fetched_at,
                "status_error": status_error,
                "profiles_error": profiles_error,
            }
        return {
            "matched": True,
            "ok": False,
            "exit_code": 1,
            "message": "Live CodexEA status refreshed, but no 1min aggregate data was returned.",
            "payload_source": payload_source,
            "payload_fetched_at": payload_fetched_at,
            "status_error": status_error,
            "profiles_error": profiles_error,
        }
    if (
        probe_all
        and not isinstance(probe_payload, dict)
        and probe_error
        and probe_error != "http_403"
        and payload_source not in {
        "status_local_runtime_cache",
        "profiles_local_runtime_cache",
        }
    ):
        return {
            "matched": True,
            "ok": False,
            "exit_code": 1,
            "message": (
                "Live 1min probe-all failed; "
                f"`/v1/providers/onemin/probe-all` {_ea_http_error_detail(probe_error)}."
            ),
            "payload_source": payload_source,
            "payload_fetched_at": payload_fetched_at,
            "status_error": status_error,
            "profiles_error": profiles_error,
        }
    if probe_error == "missing_api_token" or status_error == "missing_api_token" or profiles_error == "missing_api_token":
        aggregate = {
            **aggregate,
            "probe_note": (
                "unknown_unprobed reflects cached slot evidence; a fresh classification requires a configured EA API token "
                "and a live `codexea onemin --probe-all` run."
            ),
        }
    rendered = _render_onemin_aggregate(aggregate, include_slots=include_slots, slots_detail=slots_detail)
    fragments: list[str] = []
    source_notice = _source_notice(
        payload_source=payload_source,
        fetched_at=payload_fetched_at,
        status_error=status_error,
        profiles_error=profiles_error,
    )
    if source_notice:
        fragments.append(source_notice)
    if isinstance(billing_refresh_payload, dict):
        aggregate = {**aggregate, "billing_lookup": billing_refresh_payload}
        if (not billing_full_refresh) and _billing_refresh_used_cached_state(billing_refresh_payload, aggregate):
            fragments.append(
                _render_onemin_billing_refresh_cached_note(
                    billing_refresh_payload,
                    live_probe_refreshed=isinstance(probe_payload, dict),
                )
            )
        else:
            fragments.append(_render_onemin_billing_refresh_summary(billing_refresh_payload))
    elif billing:
        detail = _ea_http_error_detail(billing_error)
        if billing_error == "missing_api_token":
            fragments.append(
                "1min billing refresh\n"
                "Note: Live 1min billing refresh was skipped because the EA API token is not configured; showing cached billing state."
            )
        else:
            fragments.append(
                "1min billing refresh\n"
                f"Note: Live 1min billing refresh is unavailable right now ({detail}); showing cached billing state."
            )
    if probe_warning:
        fragments.append(probe_warning)
    if isinstance(probe_payload, dict):
        fragments.append(_render_onemin_probe_summary(probe_payload))
        aggregate = {**aggregate, "probe": probe_payload}
    fragments.append(rendered)
    rendered = "\n\n".join(fragment.strip() for fragment in fragments if str(fragment).strip())
    return {
        "matched": True,
        "ok": True,
        "exit_code": 0,
        "message": rendered,
        "data": aggregate,
        "payload_source": payload_source,
        "payload_fetched_at": payload_fetched_at,
        "status_error": status_error,
        "profiles_error": profiles_error,
        "source_notice": source_notice,
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


def _fleet_runtime_status_payload() -> dict[str, Any] | None:
    raw_state_root = str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT") or "").strip()
    state_path = Path(raw_state_root) if raw_state_root else (ROOT / "state" / "chummer_design_supervisor")
    if state_path.name != "state.json":
        state_path = state_path / "state.json"
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        command = [
            sys.executable,
            str(ROOT / "scripts" / "chummer_design_supervisor.py"),
            "status",
            "--json",
            "--ignore-nonlinux-desktop-host-proof-blockers",
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except Exception:
            return None
        if completed.returncode != 0:
            return None
        try:
            payload = json.loads(completed.stdout)
        except Exception:
            return None
    return payload if isinstance(payload, dict) else None


def _render_fleet_runtime_status(payload: dict[str, Any]) -> str:
    def _shard_sort_key(item: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(item.get("name") or item.get("_shard") or "").strip().lower(),
            str(item.get("_shard") or "").strip().lower(),
            str(item.get("active_run_id") or "").strip().lower(),
        )

    shards = sorted(
        [item for item in (payload.get("shards") or []) if isinstance(item, dict)],
        key=_shard_sort_key,
    )
    active_shards = [item for item in shards if str(item.get("active_run_id") or "").strip()]
    shard_count = len(shards)
    active_count = len(active_shards)
    mode = str(payload.get("mode") or "unknown").strip() or "unknown"
    updated_at = str(payload.get("updated_at") or "").strip()
    idle_count = max(0, shard_count - active_count)
    open_milestones = list(payload.get("open_milestone_ids") or [])
    active_run = payload.get("active_run") if isinstance(payload.get("active_run"), dict) else {}
    active_run_id = str(active_run.get("run_id") or "").strip()
    active_labels = [_render_active_fleet_shard_label(item) for item in active_shards]
    active_names = ", ".join(label for label in active_labels if label)
    active_label = "active shard" if active_count == 1 else "active shards"
    total_label = "shard" if shard_count == 1 else "shards"
    idle_label = "idle shard" if idle_count == 1 else "idle shards"
    fragments = [f"Live fleet status: {active_count} {active_label} out of {shard_count} total {total_label}, mode {mode}"]
    if idle_count:
        fragments.append(f"{idle_count} {idle_label}")
    if active_names:
        fragments.append(f"active shards {active_names}")
    if active_run_id:
        fragments.append(f"aggregate active run {active_run_id}")
    if open_milestones:
        fragments.append(f"{len(open_milestones)} open milestones")
    if updated_at:
        fragments.append(_fleet_runtime_updated_fragment(updated_at))
    return "; ".join(fragments) + "."


def _fleet_runtime_status_response() -> dict[str, Any]:
    payload = _fleet_runtime_status_payload()
    if not isinstance(payload, dict):
        return {
            "matched": True,
            "ok": False,
            "exit_code": 1,
            "message": (
                "Live fleet runtime status is unavailable right now; `chummer_design_supervisor status --json` could not be read "
                "or executed."
            ),
        }
    return {
        "matched": True,
        "ok": True,
        "exit_code": 0,
        "message": _render_fleet_runtime_status(payload),
    }


def _telemetry_response(text: str) -> dict[str, Any]:
    config = _load_config()
    if _looks_like_direct_fleet_runtime_query(text):
        return _fleet_runtime_status_response()
    if not _looks_like_live_telemetry_query(config, text):
        return {
            "matched": False,
            "ok": False,
            "exit_code": TELEMETRY_EXIT_NOT_MATCHED,
            "message": "Query did not match a live telemetry question.",
            "error": "no_telemetry_match",
        }

    target = _telemetry_target(config, text)
    payload = _ea_status_payload(refresh=True)
    payload_source = "status"
    payload_fetched_at = _LAST_EA_STATUS_FETCHED_AT
    status_error = str(_LAST_EA_HTTP_ERROR or "").strip()
    profiles_error = ""
    if _LAST_EA_STATUS_SOURCE == "local_runtime_cache":
        payload_source = "status_local_runtime_cache"
    if not isinstance(payload, dict):
        payload = _ea_profiles_payload()
        profiles_error = str(_LAST_EA_HTTP_ERROR or "").strip()
        payload_fetched_at = _LAST_EA_PROFILES_FETCHED_AT
        payload_source = "profiles_fallback"
        if _LAST_EA_PROFILES_SOURCE == "local_runtime_cache":
            payload_source = "profiles_local_runtime_cache"
    if not isinstance(payload, dict):
        return {
            "matched": True,
            "ok": False,
            "exit_code": 1,
            "message": "Live CodexEA status is unavailable right now; `/v1/codex/status?refresh=1` did not return data.",
            "payload_source": payload_source,
            "payload_fetched_at": payload_fetched_at,
            "status_error": status_error,
            "profiles_error": profiles_error,
        }

    row_source, rows = _provider_rows_from_payload(payload)
    if not rows:
        return {
            "matched": True,
            "ok": False,
            "exit_code": 1,
            "message": "Live CodexEA status refreshed, but no provider telemetry rows were returned.",
            "payload_source": payload_source,
            "payload_fetched_at": payload_fetched_at,
            "status_error": status_error,
            "profiles_error": profiles_error,
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
            "payload_source": payload_source,
            "payload_fetched_at": payload_fetched_at,
            "status_error": status_error,
            "profiles_error": profiles_error,
        }

    strict_unknown = row_source == "status"
    scope_label = _scope_label(target)
    prefix = "Live CodexEA provider status"
    if scope_label:
        prefix = f"Live {scope_label} status"
    if payload_source.startswith("profiles"):
        prefix += " (profiles fallback)"
    rendered_rows = [_format_telemetry_row(row, strict_unknown=strict_unknown) for row in selected_rows]
    source_notice = _source_notice(
        payload_source=payload_source,
        fetched_at=payload_fetched_at,
        status_error=status_error,
        profiles_error=profiles_error,
    )
    message = prefix + ": " + " | ".join(rendered_rows)
    if source_notice:
        message = source_notice + "\n" + message
    return {
        "matched": True,
        "ok": True,
        "exit_code": 0,
        "message": message,
        "payload_source": payload_source,
        "payload_fetched_at": payload_fetched_at,
        "status_error": status_error,
        "profiles_error": profiles_error,
        "source_notice": source_notice,
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


def infer_interactive_default(lanes: dict[str, Any] | None = None) -> dict[str, str]:
    lane_cfg = (lanes or {}).get("easy") if isinstance(lanes, dict) else {}
    return {
        "lane": "easy",
        "submode": "responses_easy",
        "reasoning_effort": "low",
        "reason": "interactive_easy_locked",
        "task_class": "inspect",
        "runtime_model": str((lane_cfg or {}).get("runtime_model") or ""),
        "provider_hint_order": ",".join((lane_cfg or {}).get("provider_hint_order") or []),
    }


def _route(argv: list[str]) -> dict[str, str]:
    config = _load_config()
    lanes = normalize_lanes_config(config.get("lanes"))
    spider = config.get("spider") if isinstance(config.get("spider"), dict) else {}
    default_lane = "easy"

    if not argv:
        return infer_interactive_default(lanes)

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
    elif preferred_lane == "groundwork":
        submode = "responses_groundwork"
        reason = "groundwork_policy_default"
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
                submode = "responses_easy"
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
    parser = argparse.ArgumentParser(
        description="CodexEA route helper used by codexea wrapper commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Environment:\n"
            "  CODEXEA_CREDITS_PROBE_ALL=0       Disable live 1min slot probing during\n"
            "                                      credits/onemin output.\n"
            "  CODEXEA_CREDITS_INCLUDE_BILLING=0  Disable live 1min billing refresh during\n"
            "                                      credits/onemin output.\n"
            "  CODEXEA_ONEMIN_BILLING_TIMEOUT_SECONDS=30   Billing refresh timeout\n"
            "                                      seconds (default).\n"
            "  CODEXEA_ONEMIN_STATUS_TIMEOUT_SECONDS=10     Status query timeout\n"
            "                                      seconds (default).\n"
            "  CODEXEA_ONEMIN_PROBE_TIMEOUT_SECONDS=180      Probe timeout\n"
            "                                      seconds (default).\n"
            "\n"
            "Examples:\n"
            "  # default (probe-all + billing refresh enabled)\n"
            "  $ CODEXEA_CREDITS_INCLUDE_BILLING=1 codexea onemin\n"
            "\n"
            "  # disable the probe-all pass\n"
            "  $ CODEXEA_CREDITS_PROBE_ALL=0 codexea onemin\n"
            "\n"
            "  # disable the top-up lookup pass\n"
            "  $ CODEXEA_CREDITS_INCLUDE_BILLING=0 codexea onemin\n"
            "\n"
            "  # explicit top-up CLI control\n"
            "  $ codexea --onemin-aggregate --include-topups\n"
            "  $ codexea --onemin-aggregate --no-topups\n"
            "\n"
            "  # machine-readable telemetry output\n"
            "  $ codexea --telemetry-answer --json 1min credits\n"
            "\n"
            "  # machine-readable routing output\n"
            "  $ codexea --json what is the safest lane for a migration fix?\n"
            "\n"
            "  # slot details\n"
            "  $ codexea --onemin-aggregate --slots --slots-detail compact\n"
            "  $ codexea --onemin-aggregate --slots --slots-detail verbose\n"
        ),
    )
    parser.add_argument("--shell", action="store_true")
    parser.add_argument("--telemetry-answer", action="store_true")
    parser.add_argument("--onemin-aggregate", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output when supported")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--slots", action="store_true")
    parser.add_argument(
        "--slots-detail",
        default="verbose",
        choices=("compact", "verbose"),
        help="controls how much detail appears per 1min slot row when --slots is used.",
    )
    parser.add_argument("--probe-all", action="store_true")
    parser.add_argument("--billing", action="store_true")
    parser.add_argument("--include-topups", action="store_true")
    parser.add_argument("--no-topups", action="store_true")
    parser.add_argument("--billing-full-refresh", action="store_true")
    parser.add_argument("--window", default="7d")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args(argv)
    if ns.telemetry_answer:
        response = _telemetry_response(" ".join(ns.args).strip())
        if ns.json:
            print(json.dumps(_route_json_payload(response), indent=2, sort_keys=True))
        else:
            message = str(response.get("message") or "").strip()
            if message:
                stream = sys.stdout if int(response.get("exit_code") or 0) == 0 else sys.stderr
                print(message, file=stream)
        return int(response.get("exit_code") or 0)
    if ns.onemin_aggregate:
        refresh = ns.refresh or ns.onemin_aggregate
        billing = ns.billing or ns.include_topups
        if ns.no_topups:
            billing = False
        response = _onemin_aggregate_response(
            refresh=refresh,
            window=ns.window,
            include_slots=ns.slots,
            slots_detail=ns.slots_detail,
            probe_all=ns.probe_all,
            billing=billing,
            billing_full_refresh=ns.billing_full_refresh,
        )
        if ns.json:
            payload = _route_json_payload(response)
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
            text = "" if value is None else str(value)
            print(f"CODEXEA_ROUTE_{key.upper()}={shlex.quote(text)}")
        return 0
    if ns.json:
        payload = _route_json_payload(
            {
                "matched": True,
                "ok": True,
                "exit_code": 0,
                "message": (
                    f'Routing decision: {routed.get("lane")} lane / {routed.get("submode")} via {routed.get("runtime_model") or "default"}'
                ),
                "data": routed,
            }
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    for key, value in routed.items():
        value_text = "" if value is None else str(value)
        print(f"{key}={value_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
