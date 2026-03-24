import datetime as dt
import json
import os
import pathlib
import sys
import urllib.request
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse


QUARTERMASTER_DIR = pathlib.Path(__file__).resolve().parent
FLEET_MOUNT_ROOT = pathlib.Path(os.environ.get("FLEET_MOUNT_ROOT", "/docker/fleet"))
ADMIN_HELPERS_DIR = FLEET_MOUNT_ROOT / "admin"
if str(ADMIN_HELPERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADMIN_HELPERS_DIR))

from capacity_plane import build_capacity_plan_payload, load_capacity_plane_configs


UTC = dt.timezone.utc
APP_PORT = int(os.environ.get("APP_PORT", "8094"))
APP_TITLE = "Codex Fleet Quartermaster"
CONFIG_PATH = pathlib.Path(os.environ.get("FLEET_CONFIG_PATH", "/app/config/fleet.yaml"))
STATE_ROOT = pathlib.Path(os.environ.get("FLEET_STATE_ROOT", "/var/lib/codex-fleet/state"))
ADMIN_URL = str(os.environ.get("FLEET_ADMIN_URL", "http://fleet-admin:8092") or "http://fleet-admin:8092").rstrip("/")
OPERATOR_PASSWORD = str(os.environ.get("FLEET_OPERATOR_PASSWORD", "") or "").strip()
PLAN_CACHE_PATH = STATE_ROOT / "quartermaster" / "latest_capacity_plan.json"
TELEMETRY_LOG_PATH = STATE_ROOT / "quartermaster" / "telemetry.jsonl"
DEFAULT_TELEMETRY_LOG_ENTRIES = max(
    1,
    int(os.environ.get("FLEET_QUARTERMASTER_TELEMETRY_LOG_ENTRIES", "1000") or "1000"),
)

app = FastAPI(title=APP_TITLE)


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso(value: Optional[dt.datetime]) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_cached_plan() -> Dict[str, Any]:
    if not PLAN_CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(PLAN_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_cached_plan(payload: Dict[str, Any]) -> None:
    PLAN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_CACHE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def telemetry_log_entry_limit() -> int:
    settings = load_quartermaster_settings()
    telemetry_cfg = dict(settings.get("telemetry") or {})
    raw_value = telemetry_cfg.get("rolling_log_entries")
    try:
        return max(1, int(raw_value or DEFAULT_TELEMETRY_LOG_ENTRIES))
    except (TypeError, ValueError):
        return DEFAULT_TELEMETRY_LOG_ENTRIES


def _cap_value(plan: Dict[str, Any], key: str) -> Any:
    caps = dict(plan.get("caps") or {})
    payload = caps.get(key)
    if isinstance(payload, dict):
        return payload.get("value")
    return payload


def build_telemetry_log_entry(payload: Dict[str, Any]) -> Dict[str, Any]:
    plan = dict(payload.get("plan") or {})
    inputs = dict(plan.get("inputs") or {})
    runway = dict(plan.get("runway") or {})
    findings = list(plan.get("typed_findings") or [])
    return {
        "generated_at": str(payload.get("generated_at") or ""),
        "source_generated_at": str(payload.get("source_generated_at") or ""),
        "source": str(payload.get("source") or ""),
        "degraded": bool(payload.get("degraded")),
        "cache_state": str(payload.get("cache_state") or ""),
        "tick_reason": str(payload.get("tick_reason") or ""),
        "limiting_cap": str(plan.get("limiting_cap") or ""),
        "lane_targets": dict(plan.get("lane_targets") or {}),
        "inputs": {
            "active_boosters": inputs.get("active_boosters"),
            "active_packages": inputs.get("active_packages"),
            "pre_audit_equivalent_workers": inputs.get("pre_audit_equivalent_workers"),
            "pre_audit_spare_workers": inputs.get("pre_audit_spare_workers"),
            "ready_dispatchable_packages": inputs.get("ready_dispatchable_packages"),
            "ready_work_reserve_shortfall": inputs.get("ready_work_reserve_shortfall"),
            "ready_participant_accounts": inputs.get("ready_participant_accounts"),
            "participant_account_count": inputs.get("participant_account_count"),
        },
        "caps": {
            "audit_cap": _cap_value(plan, "audit_cap"),
            "credit_cap_until_next_topup": _cap_value(plan, "credit_cap_until_next_topup"),
            "project_safety_cap": _cap_value(plan, "project_safety_cap"),
            "review_cap": _cap_value(plan, "review_cap"),
            "scope_cap": _cap_value(plan, "scope_cap"),
            "slot_cap": _cap_value(plan, "slot_cap"),
            "useful_work_cap": _cap_value(plan, "useful_work_cap"),
        },
        "runway": {
            "hours_remaining_no_topup": runway.get("hours_remaining_no_topup"),
            "hours_until_next_topup": runway.get("hours_until_next_topup"),
            "cycle_days_remaining": runway.get("cycle_days_remaining"),
        },
        "typed_findings": [str((item or {}).get("type") or "") for item in findings if isinstance(item, dict)],
    }


def append_telemetry_log(payload: Dict[str, Any]) -> None:
    entry = build_telemetry_log_entry(payload)
    try:
        TELEMETRY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        lines: List[str] = []
        if TELEMETRY_LOG_PATH.exists():
            try:
                lines = [line for line in TELEMETRY_LOG_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
            except Exception:
                lines = []
        lines.append(json.dumps(entry, sort_keys=True))
        limit = telemetry_log_entry_limit()
        if len(lines) > limit:
            lines = lines[-limit:]
        TELEMETRY_LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        return


def load_telemetry_log(*, limit: int = 100) -> List[Dict[str, Any]]:
    if not TELEMETRY_LOG_PATH.exists():
        return []
    try:
        lines = [line for line in TELEMETRY_LOG_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return []
    capped_limit = max(1, min(int(limit or 100), telemetry_log_entry_limit()))
    entries: List[Dict[str, Any]] = []
    for line in lines[-capped_limit:]:
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def load_quartermaster_settings() -> Dict[str, Any]:
    configs = load_capacity_plane_configs(CONFIG_PATH.parent)
    return dict(configs.get("quartermaster") or {})


def cached_plan_age_seconds(payload: Dict[str, Any]) -> Optional[float]:
    generated_at = str((payload or {}).get("generated_at") or "")
    if not generated_at:
        return None
    if generated_at.endswith("Z"):
        generated_at = generated_at[:-1] + "+00:00"
    try:
        generated = dt.datetime.fromisoformat(generated_at).astimezone(UTC)
    except ValueError:
        return None
    return max(0.0, (utc_now() - generated).total_seconds())


def plan_ttl_seconds() -> int:
    settings = load_quartermaster_settings()
    baseline = max(30, int(settings.get("baseline_tick_seconds") or settings.get("refresh_seconds") or 600))
    event_min = max(30, int(settings.get("event_tick_min_seconds") or min(baseline, 90) or 90))
    return max(event_min, int(settings.get("plan_ttl_seconds") or max(baseline, 900)))


def admin_cockpit_status() -> Dict[str, Any]:
    headers = {"User-Agent": "codex-fleet-quartermaster"}
    if OPERATOR_PASSWORD:
        headers["X-Fleet-Operator-Password"] = OPERATOR_PASSWORD
    request = urllib.request.Request(f"{ADMIN_URL}/api/cockpit/status", headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_plan_payload(*, source: str, degraded: bool, source_status: Dict[str, Any], tick_reason: str = "") -> Dict[str, Any]:
    config_root = CONFIG_PATH.parent
    configs = load_capacity_plane_configs(config_root)
    plan = build_capacity_plan_payload(source_status, capacity_configs=configs)
    return {
        "generated_at": iso(utc_now()),
        "source_generated_at": str(source_status.get("generated_at") or ""),
        "source": source,
        "degraded": degraded,
        "tick_reason": str(tick_reason or "").strip(),
        "cache_state": "fresh",
        "plan": plan,
    }


def quartermaster_status_payload(*, force_refresh: bool = False, tick_reason: str = "") -> Dict[str, Any]:
    cached = load_cached_plan()
    cache_age = cached_plan_age_seconds(cached)
    if cached and not force_refresh:
        payload = dict(cached)
        payload["cache_state"] = "stale" if cache_age is not None and cache_age > float(plan_ttl_seconds()) else "fresh"
        return payload

    source = "live_admin"
    degraded = False
    source_status: Dict[str, Any] = {}
    try:
        source_status = admin_cockpit_status()
        payload = build_plan_payload(source=source, degraded=degraded, source_status=source_status, tick_reason=tick_reason)
        save_cached_plan(payload)
        append_telemetry_log(payload)
        return payload
    except Exception as exc:
        if cached:
            payload = dict(cached)
            payload["source"] = "cached_plan"
            payload["degraded"] = True
            payload["error"] = str(exc)
            payload["cache_state"] = "stale"
            append_telemetry_log(payload)
            return payload
        degraded = True
        source = "no_admin_status"
        source_status = {
            "generated_at": iso(utc_now()),
            "projects": [],
            "groups": [],
            "config": {"policies": {}, "spider": {}, "projects": []},
            "cockpit": {
                "summary": {},
                "mission_board": {},
                "capacity_forecast": {},
                "jury_telemetry": {},
                "runway": {},
            },
        }
        payload = build_plan_payload(source=source, degraded=degraded, source_status=source_status, tick_reason=tick_reason)
        payload["error"] = str(exc)
        save_cached_plan(payload)
        append_telemetry_log(payload)
        return payload


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/api/status")
def api_status() -> Dict[str, Any]:
    return quartermaster_status_payload()


@app.get("/api/capacity-plan")
def api_capacity_plan() -> Dict[str, Any]:
    return quartermaster_status_payload().get("plan", {})


@app.get("/api/telemetry-log")
def api_telemetry_log(limit: int = 100) -> Dict[str, Any]:
    entries = load_telemetry_log(limit=limit)
    return {
        "path": str(TELEMETRY_LOG_PATH),
        "count": len(entries),
        "limit": max(1, min(int(limit or 100), telemetry_log_entry_limit())),
        "entries": entries,
    }


@app.post("/api/tick")
def api_tick(reason: str = "") -> Dict[str, Any]:
    return quartermaster_status_payload(force_refresh=True, tick_reason=reason)
