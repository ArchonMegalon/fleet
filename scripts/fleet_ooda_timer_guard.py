#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_WORKSPACE_ROOT = Path("/docker/fleet")
DEFAULT_EA_ROOT = Path("/docker/EA")
FLEET_RUNTIME_DEFAULTS = {
    "CHUMMER_DESIGN_SUPERVISOR_FALLBACK_LANES": "core_rescue,survival,repair",
    "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_LANES": "core_rescue,survival,repair",
    "CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_PRINCIPAL_ID": "codex-fleet",
    "CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_TIMEOUT_SECONDS": "20",
    "EA_MCP_PRINCIPAL_ID": "codex-fleet",
    "EA_PRINCIPAL_ID": "codex-fleet",
}
EA_RUNTIME_DEFAULTS = {
    "EA_RESPONSES_HARD_MAX_ACTIVE_REQUESTS": "20",
    "EA_SURVIVAL_ROUTE_ORDER": "chatplayground,gemini_web,gemini_vortex,onemin",
    "EA_SURVIVAL_MAX_ACTIVE_REQUESTS": "1",
    "EA_SURVIVAL_QUEUE_TIMEOUT_SECONDS": "900",
    "EA_PROVIDER_HEALTH_REGISTRY_TIMEOUT_SECONDS": "10",
}
LOW_CAPACITY_PERCENT = 0.10


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        return default


def coerce_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(str(value))
    except Exception:
        return None


def run_command(
    argv: list[str],
    *,
    cwd: Path,
    timeout: int,
    dry_run: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "argv": argv,
        "cwd": str(cwd),
        "dry_run": dry_run,
        "timeout_seconds": timeout,
    }
    if dry_run:
        payload["returncode"] = 0
        payload["skipped"] = True
        return payload
    try:
        result = subprocess.run(
            argv,
            cwd=str(cwd),
            timeout=timeout,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        payload["returncode"] = 124
        payload["error"] = f"{exc.__class__.__name__}: {exc}"
        return payload
    payload["returncode"] = result.returncode
    payload["stdout_tail"] = result.stdout[-4000:]
    payload["stderr_tail"] = result.stderr[-4000:]
    return payload


def parse_env_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return parse_env_text(path.read_text(encoding="utf-8", errors="ignore"))


def rewrite_env_defaults(text: str, defaults: dict[str, str]) -> tuple[str, list[str]]:
    lines = text.splitlines()
    changed: list[str] = []
    seen: set[str] = set()
    rewritten: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            rewritten.append(line)
            continue
        key, _value = stripped.split("=", 1)
        key = key.strip()
        if key in defaults:
            seen.add(key)
            desired = defaults[key]
            current = line.split("=", 1)[1].strip()
            if current != desired:
                rewritten.append(f"{key}={desired}")
                changed.append(key)
            else:
                rewritten.append(line)
            continue
        rewritten.append(line)
    for key, value in defaults.items():
        if key not in seen:
            rewritten.append(f"{key}={value}")
            changed.append(key)
    suffix = "\n" if text.endswith("\n") or not text else ""
    return "\n".join(rewritten) + suffix, changed


def ensure_env_defaults(path: Path, defaults: dict[str, str], *, dry_run: bool) -> dict[str, Any]:
    original = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    updated, changed = rewrite_env_defaults(original, defaults)
    payload = {"path": str(path), "changed_keys": changed, "changed": bool(changed)}
    if changed and not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")
    return payload


def provider_health_urls(runtime_env: dict[str, str]) -> list[str]:
    raw = runtime_env.get(
        "CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_URL",
        "http://127.0.0.1:8090/v1/responses/_provider_health",
    )
    candidates: list[str] = []
    for url in (raw, raw.replace("host.docker.internal", "127.0.0.1"), "http://127.0.0.1:8090/v1/responses/_provider_health"):
        clean = str(url or "").strip()
        if clean and clean not in candidates:
            candidates.append(clean)
    return candidates


def provider_health_request_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    query["lightweight"] = ["1"]
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query, doseq=True), parsed.fragment)
    )


def fetch_provider_health(runtime_env: dict[str, str], *, timeout: float) -> dict[str, Any]:
    token = runtime_env.get("CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_API_TOKEN", "")
    principal = runtime_env.get("CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_PRINCIPAL_ID", "fleet-ooda-timer")
    headers = {
        "X-EA-Principal-ID": principal or "fleet-ooda-timer",
        "X-Principal-Id": principal or "fleet-ooda-timer",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    errors: list[str] = []
    for url in provider_health_urls(runtime_env):
        try:
            request = urllib.request.Request(provider_health_request_url(url), headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="ignore")
            payload = json.loads(body)
            return {"ok": True, "source_url": url, "payload": payload}
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
            errors.append(f"{url}: {exc}")
    return {"ok": False, "errors": errors, "payload": {}}


def fetch_provider_health_with_retries(
    runtime_env: dict[str, str],
    *,
    timeout: float,
    attempts: int,
    delay_seconds: float,
    dry_run: bool,
) -> dict[str, Any]:
    last_result: dict[str, Any] = {"ok": False, "errors": ["provider-health fetch not attempted"], "payload": {}}
    for attempt in range(max(1, attempts)):
        last_result = fetch_provider_health(runtime_env, timeout=timeout)
        if last_result.get("ok"):
            return last_result
        if dry_run or attempt >= attempts - 1:
            break
        time.sleep(delay_seconds)
    return last_result


def row_capacity(row: dict[str, Any]) -> dict[str, Any]:
    for key in ("capacity_summary", "slot_pool", "capacity"):
        value = row.get(key)
        if isinstance(value, dict):
            return dict(value)
    return {}


def row_state(row: dict[str, Any]) -> str:
    capacity = row_capacity(row)
    return str(row.get("primary_state") or row.get("state") or capacity.get("state") or "").strip().lower()


def row_ready_slots(row: dict[str, Any]) -> int:
    return coerce_int(row_capacity(row).get("ready_slots"), 0)


def row_configured_slots(row: dict[str, Any]) -> int:
    return coerce_int(row_capacity(row).get("configured_slots"), 0)


def row_remaining_percent(row: dict[str, Any]) -> float | None:
    return coerce_float(row_capacity(row).get("remaining_percent_of_max"))


def assess_provider_health_payload(payload: dict[str, Any]) -> dict[str, Any]:
    registry = dict(payload.get("provider_registry") or {})
    provider_rows = [dict(item) for item in registry.get("providers") or [] if isinstance(item, dict)]
    lane_rows = [dict(item) for item in registry.get("lanes") or [] if isinstance(item, dict)]
    problems: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not registry:
        problems.append({"code": "provider_registry_missing", "detail": "provider-health did not include provider_registry"})
    if not lane_rows:
        problems.append({"code": "provider_registry_lanes_missing", "detail": "provider registry did not publish lanes"})

    for provider in provider_rows:
        key = str(provider.get("provider_key") or "").strip()
        state = row_state(provider)
        configured_slots = row_configured_slots(provider)
        ready_slots = row_ready_slots(provider)
        if state == "ready" and configured_slots > 0 and ready_slots <= 0:
            problems.append(
                {
                    "code": "ready_provider_has_zero_ready_slots",
                    "provider_key": key,
                    "configured_slots": configured_slots,
                    "ready_slots": ready_slots,
                }
            )

    lanes_by_profile = {str(row.get("profile") or "").strip(): row for row in lane_rows}
    for profile, lane in lanes_by_profile.items():
        state = row_state(lane)
        configured_slots = row_configured_slots(lane)
        ready_slots = row_ready_slots(lane)
        remaining_percent = row_remaining_percent(lane)
        if state == "ready" and configured_slots > 0 and ready_slots <= 0:
            problems.append(
                {
                    "code": "ready_lane_has_zero_ready_slots",
                    "profile": profile,
                    "primary_provider_key": str(lane.get("primary_provider_key") or ""),
                    "configured_slots": configured_slots,
                    "ready_slots": ready_slots,
                }
            )
        if (
            profile in {"core", "core_rescue"}
            and state == "ready"
            and remaining_percent is not None
            and remaining_percent <= LOW_CAPACITY_PERCENT
        ):
            problems.append(
                {
                    "code": "low_capacity_core_lane_marked_ready",
                    "profile": profile,
                    "remaining_percent_of_max": remaining_percent,
                    "configured_slots": configured_slots,
                    "ready_slots": ready_slots,
                }
            )

    survival = lanes_by_profile.get("survival")
    if not survival:
        problems.append({"code": "survival_lane_missing", "detail": "provider registry did not publish survival lane"})
    else:
        survival_state = row_state(survival)
        survival_ready_slots = row_ready_slots(survival)
        primary_key = str(survival.get("primary_provider_key") or "").strip()
        providers = [dict(item) for item in survival.get("providers") or [] if isinstance(item, dict)]
        browseract_ready = any(
            str(provider.get("provider_key") or "").strip() in {"browseract", "chatplayground"}
            and row_state(provider) == "ready"
            and row_ready_slots(provider) > 0
            for provider in providers
        )
        if survival_state != "ready" or survival_ready_slots <= 0:
            problems.append(
                {
                    "code": "survival_lane_not_ready",
                    "state": survival_state,
                    "ready_slots": survival_ready_slots,
                }
            )
        if primary_key not in {"browseract", "chatplayground"} or not browseract_ready:
            problems.append(
                {
                    "code": "survival_not_backed_by_ready_browseract",
                    "primary_provider_key": primary_key,
                    "browseract_ready": browseract_ready,
                }
            )

    if not problems and provider_rows and not any(row_state(row) == "ready" for row in provider_rows):
        warnings.append("no provider row is currently ready")

    return {
        "status": "fail" if problems else "pass",
        "problems": problems,
        "warnings": warnings,
        "provider_count": len(provider_rows),
        "lane_count": len(lane_rows),
    }


def load_status(workspace_root: Path, *, timeout: int, live_refresh: bool = False) -> dict[str, Any]:
    argv = [sys.executable, "scripts/chummer_design_supervisor.py", "status", "--json"]
    if live_refresh:
        argv.append("--live-refresh")
    try:
        result = subprocess.run(
            argv,
            cwd=str(workspace_root),
            timeout=timeout,
            check=False,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "")
        return {
            "ok": False,
            "returncode": 124,
            "timed_out": True,
            "stdout_tail": stdout[-2000:],
            "stderr_tail": stderr[-2000:] or f"status command timed out after {timeout}s",
        }
    except Exception as exc:
        return {"ok": False, "returncode": 124, "error": f"{exc.__class__.__name__}: {exc}"}
    if result.returncode != 0:
        return {"ok": False, "returncode": result.returncode, "stderr_tail": result.stderr[-2000:]}
    try:
        return {"ok": True, "payload": json.loads(result.stdout)}
    except json.JSONDecodeError as exc:
        return {"ok": False, "returncode": result.returncode, "stderr_tail": str(exc)}


def status_needs_live_refresh(status_payload: dict[str, Any]) -> bool:
    worker_lane_health = status_payload.get("worker_lane_health")
    if not isinstance(worker_lane_health, dict) or not worker_lane_health:
        return True
    if "routable_lanes" not in worker_lane_health:
        return True
    return False


def load_status_with_lane_health(workspace_root: Path, *, timeout: int) -> dict[str, Any]:
    result = load_status(workspace_root, timeout=timeout, live_refresh=False)
    status_payload = dict(result.get("payload") or {}) if result.get("ok") else {}
    if not status_payload or not status_needs_live_refresh(status_payload):
        return result
    refreshed = load_status(workspace_root, timeout=timeout, live_refresh=True)
    if refreshed.get("ok"):
        return refreshed
    result["live_refresh_fallback"] = {key: value for key, value in refreshed.items() if key != "payload"}
    return result


def provider_cache_paths(status_payload: dict[str, Any], workspace_root: Path) -> list[Path]:
    paths: list[Path] = []
    worker_lane_health = dict(status_payload.get("worker_lane_health") or {})
    cache_path = str(worker_lane_health.get("cache_path") or "").strip()
    if cache_path:
        paths.append(Path(cache_path))
    state_root = Path(str(status_payload.get("state_root") or workspace_root / "state/chummer_design_supervisor"))
    paths.append(state_root / "ea_provider_health_cache.json")
    aggregate_root = workspace_root / "state/chummer_design_supervisor"
    paths.append(aggregate_root / "ea_provider_health_cache.json")
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


def remove_provider_cache(paths: list[Path], *, dry_run: bool) -> dict[str, Any]:
    removed: list[str] = []
    for path in paths:
        try:
            if path.exists():
                removed.append(str(path))
                if not dry_run:
                    path.unlink()
        except Exception:
            continue
    return {"removed_paths": removed, "changed": bool(removed)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guard the unattended Fleet OODA Codex timer with deterministic self-heal checks.")
    parser.add_argument("--once", action="store_true", help="Run one guard pass.")
    parser.add_argument("--workspace-root", type=Path, default=DEFAULT_WORKSPACE_ROOT)
    parser.add_argument("--ea-root", type=Path, default=DEFAULT_EA_ROOT)
    parser.add_argument("--target-active", type=int, default=13)
    parser.add_argument("--minimum-active", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--provider-timeout-seconds", type=float, default=None)
    args = parser.parse_args(argv)

    workspace_root = args.workspace_root.resolve()
    ea_root = args.ea_root.resolve()
    fleet_runtime_path = workspace_root / "runtime.env"
    ea_env_path = ea_root / ".env"
    dry_run = bool(args.dry_run)
    report: dict[str, Any] = {
        "generated_at": utc_now(),
        "status": "pass",
        "workspace_root": str(workspace_root),
        "ea_root": str(ea_root),
        "actions": [],
        "blockers": [],
        "warnings": [],
        "requires_codex_patch": False,
    }

    fleet_env_result = ensure_env_defaults(fleet_runtime_path, FLEET_RUNTIME_DEFAULTS, dry_run=dry_run)
    ea_env_result = ensure_env_defaults(ea_env_path, EA_RUNTIME_DEFAULTS, dry_run=dry_run)
    report["runtime_env"] = {"fleet": fleet_env_result, "ea": ea_env_result}

    runtime_env = load_env(fleet_runtime_path)
    if dry_run:
        runtime_env = {**runtime_env, **FLEET_RUNTIME_DEFAULTS}
    provider_timeout = (
        float(args.provider_timeout_seconds)
        if args.provider_timeout_seconds is not None
        else coerce_float(runtime_env.get("CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_TIMEOUT_SECONDS")) or 20.0
    )
    report["provider_health_timeout_seconds"] = provider_timeout
    provider_fetch = fetch_provider_health_with_retries(
        runtime_env,
        timeout=provider_timeout,
        attempts=2,
        delay_seconds=2.0,
        dry_run=dry_run,
    )
    report["provider_health_fetch"] = {
        key: value for key, value in provider_fetch.items() if key != "payload"
    }
    provider_assessment = assess_provider_health_payload(dict(provider_fetch.get("payload") or {})) if provider_fetch.get("ok") else {
        "status": "fail",
        "problems": [{"code": "provider_health_unreachable", "detail": "; ".join(provider_fetch.get("errors") or [])}],
        "warnings": [],
    }
    report["provider_health_assessment"] = provider_assessment

    ea_recreate_attempted = False
    if ea_env_result["changed"] or provider_assessment["status"] == "fail":
        ea_recreate_attempted = True
        action = run_command(
            ["docker", "compose", "up", "-d", "--build", "--force-recreate", "ea-api"],
            cwd=ea_root,
            timeout=240,
            dry_run=dry_run,
        )
        action["reason"] = "ea env changed or provider-health invariant failed"
        report["actions"].append(action)
        provider_fetch = fetch_provider_health_with_retries(
            runtime_env,
            timeout=provider_timeout,
            attempts=8,
            delay_seconds=3.0,
            dry_run=dry_run,
        )
        provider_assessment = assess_provider_health_payload(dict(provider_fetch.get("payload") or {})) if provider_fetch.get("ok") else provider_assessment
        report["provider_health_fetch_after_ea_recreate"] = {
            key: value for key, value in provider_fetch.items() if key != "payload"
        }
        report["provider_health_assessment_after_ea_recreate"] = provider_assessment

    if fleet_env_result["changed"] or ea_recreate_attempted:
        action = run_command(
            ["docker", "compose", "up", "-d", "--force-recreate", "fleet-design-supervisor"],
            cwd=workspace_root,
            timeout=120,
            dry_run=dry_run,
        )
        action["reason"] = "fleet runtime changed or EA provider-health was refreshed"
        report["actions"].append(action)
        if not dry_run:
            time.sleep(8.0)

    status_result = load_status_with_lane_health(workspace_root, timeout=45)
    report["fleet_status_fetch"] = {key: value for key, value in status_result.items() if key != "payload"}
    if not status_result.get("ok"):
        report["warnings"].append("fleet status snapshot unavailable; guard used live provider-health and keeper fallback")
    status_payload = dict(status_result.get("payload") or {}) if status_result.get("ok") else {}
    worker_lane_health = dict(status_payload.get("worker_lane_health") or {})
    worker_lane_reason = str(worker_lane_health.get("reason") or "")
    live_provider_ok = bool(provider_fetch.get("ok"))
    worker_routable_lanes = [str(item) for item in worker_lane_health.get("routable_lanes") or [] if str(item)]
    cached_provider_health_blocking = "using cached provider-health" in worker_lane_reason and not worker_routable_lanes
    if live_provider_ok and (cached_provider_health_blocking or worker_lane_health.get("live_fetch_error")):
        cache_action = remove_provider_cache(provider_cache_paths(status_payload, workspace_root), dry_run=dry_run)
        cache_action["reason"] = "live provider-health succeeded while supervisor status used cached or failed provider-health"
        report["actions"].append(cache_action)
        if cache_action.get("changed"):
            refreshed_status = load_status_with_lane_health(workspace_root, timeout=45)
            report["fleet_status_fetch_after_cache_clear"] = {
                key: value for key, value in refreshed_status.items() if key != "payload"
            }
            if refreshed_status.get("ok"):
                status_result = refreshed_status
                status_payload = dict(refreshed_status.get("payload") or {})
                worker_lane_health = dict(status_payload.get("worker_lane_health") or {})

    active_runs = coerce_int(status_payload.get("active_runs_count"), 0)
    allowed_active = coerce_int(status_payload.get("allowed_active_shards"), 0)
    effective_target = min(int(args.target_active), allowed_active or int(args.target_active))
    if active_runs < effective_target:
        action = run_command(
            [sys.executable, "scripts/fleet_ooda_keeper.py", "--once", "--target-active", str(args.target_active)],
            cwd=workspace_root,
            timeout=120,
            dry_run=dry_run,
        )
        action["reason"] = f"active runs {active_runs} below effective target {effective_target}"
        report["actions"].append(action)
        post_keeper_status_attempts: list[dict[str, Any]] = []
        for attempt in range(4):
            if not dry_run:
                time.sleep(2.0 if attempt == 0 else 8.0)
            refreshed_status = load_status_with_lane_health(workspace_root, timeout=45)
            post_keeper_status_attempts.append(
                {key: value for key, value in refreshed_status.items() if key != "payload"}
            )
            if not refreshed_status.get("ok"):
                continue
            status_result = refreshed_status
            status_payload = dict(refreshed_status.get("payload") or {})
            worker_lane_health = dict(status_payload.get("worker_lane_health") or {})
            active_runs = coerce_int(status_payload.get("active_runs_count"), active_runs)
            allowed_active = coerce_int(status_payload.get("allowed_active_shards"), allowed_active)
            effective_target = min(int(args.target_active), allowed_active or int(args.target_active))
            if active_runs >= min(int(args.minimum_active), effective_target):
                break
        report["fleet_status_fetch_after_keeper"] = post_keeper_status_attempts

    if provider_assessment.get("status") == "fail":
        report["status"] = "blocked"
        report["requires_codex_patch"] = True
        report["blockers"].append(
            "provider-health invariant failed after deterministic guard; scheduled Codex must patch /docker/EA before trusting fleet status"
        )

    if status_payload:
        worker_routable = [str(item) for item in worker_lane_health.get("routable_lanes") or [] if str(item)]
        report["fleet_summary"] = {
            "active_runs_count": active_runs,
            "allowed_active_shards": allowed_active,
            "worker_lane_routable_lanes": worker_routable,
            "eta_status": status_payload.get("eta_status") or (status_payload.get("eta") or {}).get("status"),
        }
        if not worker_routable:
            report["status"] = "blocked"
            report["blockers"].append("fleet worker_lane_health has no routable lanes")
        if active_runs < min(int(args.minimum_active), effective_target):
            report["status"] = "blocked"
            report["blockers"].append(
                f"active shard count {active_runs} is below minimum {min(int(args.minimum_active), effective_target)}"
            )

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
