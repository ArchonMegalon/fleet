import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

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


def admin_cockpit_status() -> Dict[str, Any]:
    headers = {"User-Agent": "codex-fleet-quartermaster"}
    if OPERATOR_PASSWORD:
        headers["X-Fleet-Operator-Password"] = OPERATOR_PASSWORD
    request = urllib.request.Request(f"{ADMIN_URL}/api/cockpit/status", headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def quartermaster_status_payload() -> Dict[str, Any]:
    config_root = CONFIG_PATH.parent
    configs = load_capacity_plane_configs(config_root)
    source = "live_admin"
    degraded = False
    source_status: Dict[str, Any] = {}
    try:
        source_status = admin_cockpit_status()
    except Exception as exc:
        cached = load_cached_plan()
        if cached:
            cached["source"] = "cached_plan"
            cached["degraded"] = True
            cached["error"] = str(exc)
            return cached
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
    plan = build_capacity_plan_payload(source_status, capacity_configs=configs)
    payload = {
        "generated_at": iso(utc_now()),
        "source_generated_at": str(source_status.get("generated_at") or ""),
        "source": source,
        "degraded": degraded,
        "plan": plan,
    }
    save_cached_plan(payload)
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
