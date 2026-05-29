#!/usr/bin/env bash
set -euo pipefail

timestamp() {
  date --iso-8601=seconds
}

echo "[$(timestamp)] starting 1min billing refresh"

docker exec -i ea-api python - <<'PY'
import json
import os

import requests

base_url = "http://127.0.0.1:8090"
api_token = str(os.environ.get("EA_API_TOKEN") or "").strip()
principal_id = ""
for env_name in ("EA_OPERATOR_PRINCIPAL_IDS", "EA_OPERATOR_PRINCIPALS"):
    raw = str(os.environ.get(env_name) or "").strip()
    if not raw:
        continue
    for item in raw.split(","):
        item = str(item or "").strip()
        if item:
            principal_id = item
            break
    if principal_id:
        break
if not principal_id:
    principal_id = str(os.environ.get("EA_DEFAULT_PRINCIPAL_ID") or "").strip() or "codex-fleet"

headers = {"X-EA-Principal-ID": principal_id}
if api_token:
    headers["Authorization"] = f"Bearer {api_token}"

refresh_payload = {
    "include_members": True,
    "capture_raw_text": True,
    "provider_api_all_accounts": True,
    "provider_api_continue_on_rate_limit": True,
}

refresh = requests.post(
    f"{base_url}/v1/providers/onemin/billing-refresh",
    headers=headers,
    json=refresh_payload,
    timeout=1800,
)
refresh.raise_for_status()
refresh_json = refresh.json()
aggregate_json = refresh_json.get("global_aggregate_snapshot") or {}

summary = {
    "principal_id": principal_id,
    "refresh_status": refresh.status_code,
    "scheduled_binding_jobs": len(refresh_json.get("scheduled_binding_jobs") or []),
    "browseract_billing_results": len(refresh_json.get("billing_results") or []),
    "browseract_member_results": len(refresh_json.get("member_results") or []),
    "api_billing_refresh_count": int(refresh_json.get("api_billing_refresh_count") or 0),
    "api_member_reconciliation_count": int(refresh_json.get("api_member_reconciliation_count") or 0),
    "provider_api_scope": refresh_json.get("provider_api_scope"),
    "api_rate_limited": bool(refresh_json.get("api_rate_limited")),
    "errors": len(refresh_json.get("errors") or []),
    "aggregate_account_count": aggregate_json.get("account_count"),
    "aggregate_ready_account_count": aggregate_json.get("ready_account_count"),
    "aggregate_sum_free_credits": aggregate_json.get("sum_free_credits"),
    "aggregate_actual_free_credits_total": aggregate_json.get("actual_free_credits_total"),
    "aggregate_estimated_free_credits_total": aggregate_json.get("estimated_free_credits_total"),
}
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "[$(timestamp)] 1min billing refresh finished"
