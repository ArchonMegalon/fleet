#!/usr/bin/env bash
set -euo pipefail

timestamp() {
  date --iso-8601=seconds
}

load_local_ea_env() {
  _load_dotenv_file() {
    local dotenv_path="$1"
    local line key value
    [[ -f "$dotenv_path" ]] || return 0
    while IFS= read -r line || [[ -n "$line" ]]; do
      line="${line%$'\r'}"
      [[ -n "${line//[[:space:]]/}" ]] || continue
      [[ "${line#\#}" != "$line" ]] || true
      if [[ "${line#\#}" != "$line" ]]; then
        continue
      fi
      [[ "$line" == *=* ]] || continue
      key="${line%%=*}"
      value="${line#*=}"
      key="${key#"${key%%[![:space:]]*}"}"
      key="${key%"${key##*[![:space:]]}"}"
      [[ -n "$key" ]] || continue
      if [[ "$key" == export[[:space:]]* ]]; then
        key="${key#export }"
        key="${key#"${key%%[![:space:]]*}"}"
      fi
      if [[ ${#value} -ge 2 ]]; then
        if [[ "$value" == \"*\" && "$value" == *\" ]]; then
          value="${value:1:${#value}-2}"
        elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
          value="${value:1:${#value}-2}"
        fi
      fi
      export "$key=$value"
    done < "$dotenv_path"
  }

  _load_dotenv_file /docker/EA/.env
  _load_dotenv_file /docker/EA/.env.local
}

emit_reconciliation_python() {
  cat <<'PY'
import json
import os
import time
from pathlib import Path

from app.api.routes import providers as providers_route
from app.api.routes import responses as responses_route

def _int_env(name: str, default: int) -> int:
    raw = str(os.environ.get(name) or "").strip()
    try:
        value = int(raw) if raw else default
    except Exception:
        value = default
    return max(0, value)


def _float_env(name: str, default: float) -> float:
    raw = str(os.environ.get(name) or "").strip()
    try:
        value = float(raw) if raw else default
    except Exception:
        value = default
    return max(0.0, value)


def _state_path() -> Path:
    raw = str(os.environ.get("ONEMIN_PROVIDER_API_RECONCILIATION_CURSOR_PATH") or "").strip()
    return Path(raw or "/tmp/onemin_provider_api_reconciliation_cursor.json")


def _read_state() -> dict[str, object]:
    path = _state_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_state(payload: dict[str, object]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _fleet_provider_health_bridge_path() -> Path:
    return Path("/docker/fleet/state/chummer_design_supervisor/ea_provider_health_cache.json")


def _publish_fleet_provider_health_bridge(payload: dict[str, object]) -> None:
    if not isinstance(payload, dict) or not payload:
        return
    path = _fleet_provider_health_bridge_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        bridge_payload = {
            "cached_at": providers_route.upstream.now_utc_iso(),
            "payload": payload,
            "source_url": "docker://ea-api/refresh_onemin_provider_api_reconciliation",
            "last_live_fetch_failed_at": "",
            "last_live_fetch_error": "",
        }
        path.write_text(json.dumps(bridge_payload, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        pass


owner_rows = [
    row for row in providers_route.upstream.onemin_owner_rows()
    if str(row.get("account_name") or "").strip() and str(row.get("owner_email") or "").strip()
]
account_labels = [str(row.get("account_name") or "").strip() for row in owner_rows]
state = _read_state()
max_accounts = _int_env("ONEMIN_PROVIDER_API_RECONCILIATION_MAX_ACCOUNTS", 6)
if max_accounts > 0 and account_labels:
    prior_cursor = _int_env("ONEMIN_PROVIDER_API_RECONCILIATION_CURSOR", int(state.get("cursor") or 0))
    start_index = prior_cursor % len(account_labels)
    selected_labels = list(account_labels[start_index : start_index + max_accounts])
    if len(selected_labels) < max_accounts:
        selected_labels.extend(account_labels[: max_accounts - len(selected_labels)])
    account_labels = selected_labels
    next_cursor = (start_index + len(account_labels)) % len(owner_rows)
else:
    next_cursor = 0
batch_size = _int_env("ONEMIN_PROVIDER_API_RECONCILIATION_BATCH_SIZE", 2) or 2
batch_delay_seconds = _float_env("ONEMIN_PROVIDER_API_RECONCILIATION_BATCH_DELAY_SECONDS", 5.0)
timeout_seconds = _int_env("ONEMIN_PROVIDER_API_RECONCILIATION_TIMEOUT_SECONDS", 300) or 300

billing_results = []
member_results = []
errors = []
attempted_count = 0
skipped_count = 0
rate_limited = False

for batch_start in range(0, len(account_labels), batch_size):
    batch_labels = set(account_labels[batch_start : batch_start + batch_size])
    if not batch_labels:
        continue
    (
        batch_billing_results,
        batch_member_results,
        batch_errors,
        batch_attempted_count,
        batch_skipped_count,
        batch_rate_limited,
    ) = providers_route._refresh_onemin_via_provider_api(
        include_members=False,
        timeout_seconds=timeout_seconds,
        all_accounts=False,
        continue_on_rate_limit=True,
        account_labels=batch_labels,
    )
    billing_results.extend(batch_billing_results or [])
    member_results.extend(batch_member_results or [])
    errors.extend(batch_errors or [])
    attempted_count += int(batch_attempted_count or 0)
    skipped_count += int(batch_skipped_count or 0)
    rate_limited = bool(rate_limited or batch_rate_limited)
    if batch_rate_limited and batch_errors:
        break
    if batch_start + batch_size < len(account_labels) and batch_delay_seconds > 0:
        time.sleep(batch_delay_seconds)

responses_route.invalidate_provider_health_snapshot_cache(lightweight=None)
lightweight_payload = responses_route._provider_health_snapshot(lightweight=True)
full_payload = responses_route._provider_health_snapshot(lightweight=False)
responses_route.remember_provider_health_snapshot_cache(lightweight=True, payload=lightweight_payload)
responses_route.remember_provider_health_snapshot_cache(lightweight=False, payload=full_payload)
_publish_fleet_provider_health_bridge(lightweight_payload)

onemin = dict(((lightweight_payload.get("providers") or {}).get("onemin") or {}))
summary = {
    "attempted_count": attempted_count,
    "skipped_count": skipped_count,
    "billing_result_count": len(billing_results or []),
    "member_result_count": len(member_results or []),
    "selected_account_count": len(account_labels),
    "selected_account_labels": account_labels,
    "error_count": len(errors or []),
    "rate_limited": bool(rate_limited),
    "live_dispatchable_slot_count": onemin.get("live_dispatchable_slot_count"),
    "live_ready_slot_count": onemin.get("live_ready_slot_count"),
    "ready_slot_count": onemin.get("ready_slot_count"),
    "fresh_actual_billing_funded_slot_count": onemin.get("fresh_actual_billing_funded_slot_count"),
    "stale_actual_billing_funded_slot_count": onemin.get("stale_actual_billing_funded_slot_count"),
    "billing_reconciliation_needed": onemin.get("billing_reconciliation_needed"),
    "billing_reconciliation_reason": onemin.get("billing_reconciliation_reason"),
}
_write_state(
    {
        "cursor": next_cursor,
        "total_account_count": len(owner_rows),
        "selected_account_count": len(account_labels),
        "selected_account_labels": account_labels,
        "attempted_count": attempted_count,
        "skipped_count": skipped_count,
        "rate_limited": bool(rate_limited),
        "updated_at": providers_route.upstream.now_utc_iso(),
    }
)
print(json.dumps(summary, indent=2, sort_keys=True))
if errors:
    print(json.dumps({"sample_errors": errors[:10]}, indent=2, sort_keys=True))
PY
}

echo "[$(timestamp)] starting 1min provider-api reconciliation"

if docker exec ea-api true >/dev/null 2>&1; then
  emit_reconciliation_python | docker exec -i ea-api python -
elif [[ -d /docker/EA/ea/app ]]; then
  load_local_ea_env
  emit_reconciliation_python | env PYTHONPATH=/docker/EA/ea python3 -
else
  echo "[$(timestamp)] unable to reach ea-api via docker exec and no local /docker/EA/ea checkout is available" >&2
  exit 1
fi

echo "[$(timestamp)] 1min provider-api reconciliation finished"
