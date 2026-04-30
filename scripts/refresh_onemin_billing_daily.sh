#!/usr/bin/env bash
set -euo pipefail

timestamp() {
  date --iso-8601=seconds
}

echo "[$(timestamp)] starting 1min billing refresh"

docker exec ea-api python - <<'PY'
import json
import os
import sys

import requests

base_url = "http://127.0.0.1:8090"
api_token = str(os.environ.get("EA_API_TOKEN") or "").strip()
principal_id = "codex-fleet"

if not api_token:
    raise SystemExit("EA_API_TOKEN missing in ea-api container")

headers = {
    "Authorization": f"Bearer {api_token}",
    "X-EA-Principal-ID": principal_id,
}

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

aggregate = requests.get(
    f"{base_url}/v1/providers/onemin/aggregate?scope=global",
    headers=headers,
    timeout=300,
)
aggregate.raise_for_status()
aggregate_json = aggregate.json()

summary = {
    "refresh_status": refresh.status_code,
    "scheduled_binding_jobs": len(refresh_json.get("scheduled_binding_jobs") or []),
    "browseract_billing_results": len(refresh_json.get("billing_results") or []),
    "browseract_member_results": len(refresh_json.get("member_results") or []),
    "provider_api_results": len(refresh_json.get("provider_api_results") or []),
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
