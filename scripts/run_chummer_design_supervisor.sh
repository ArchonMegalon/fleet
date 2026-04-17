#!/usr/bin/env bash
set -euo pipefail

cd /docker/fleet

if [[ -n "${CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS:-}" ]]; then
  : "${CODEXEA_STREAM_IDLE_TIMEOUT_MS:=${CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS}}"
  export CODEXEA_STREAM_IDLE_TIMEOUT_MS
fi
if [[ -n "${CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES:-}" ]]; then
  : "${CODEXEA_STREAM_MAX_RETRIES:=${CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES}}"
  export CODEXEA_STREAM_MAX_RETRIES
fi
if [[ -n "${CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE:-}" ]]; then
  : "${CODEXEA_CORE_RESPONSES_PROFILE:=${CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE}}"
  export CODEXEA_CORE_RESPONSES_PROFILE
fi

if [[ -z "${CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS:-}" ]]; then
  CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS=0
fi
export CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS

common_args=()
project_config_path="${CHUMMER_DESIGN_SUPERVISOR_PROJECT_CONFIG:-/docker/fleet/config/projects/fleet.yaml}"
shard_owner_groups_raw="${CHUMMER_DESIGN_SUPERVISOR_SHARD_OWNER_GROUPS:-}"
shard_focus_profile_groups_raw="${CHUMMER_DESIGN_SUPERVISOR_SHARD_FOCUS_PROFILE_GROUPS:-}"
shard_focus_text_groups_raw="${CHUMMER_DESIGN_SUPERVISOR_SHARD_FOCUS_TEXT_GROUPS:-}"

load_project_runtime_contract_defaults() {
  local config_path="${1:-}"
  if [[ -z "$config_path" || ! -f "$config_path" ]]; then
    return 0
  fi
  python3 - "$config_path" <<'PY'
import json
import os
import shlex
import sys
from pathlib import Path

try:
    import yaml
except Exception:
    yaml = None

path = Path(sys.argv[1])
payload = {}
if yaml is not None:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
contract = {}
if isinstance(payload, dict):
    contract = payload.get("supervisor_contract") or payload.get("chummer_design_supervisor") or {}
runtime_policy = contract.get("runtime_policy") if isinstance(contract, dict) else {}
if not isinstance(runtime_policy, dict):
    runtime_policy = {}
restart_safe_runtime = contract.get("restart_safe_runtime") if isinstance(contract, dict) else {}
if not isinstance(restart_safe_runtime, dict):
    restart_safe_runtime = {}
launcher_defaults = restart_safe_runtime.get("launcher_defaults")
if not isinstance(launcher_defaults, dict):
    launcher_defaults = {}
top_level_resource_policy = contract.get("resource_policy") if isinstance(contract, dict) else {}
if not isinstance(top_level_resource_policy, dict):
    top_level_resource_policy = {}
topology = contract.get("shard_topology") if isinstance(contract, dict) else {}
configured = topology.get("configured_shards") if isinstance(topology, dict) else []
if not isinstance(configured, list):
    configured = []

def list_text(value):
    if isinstance(value, list):
        rows = value
    elif value is None:
        rows = []
    else:
        rows = str(value).replace(";", ",").split(",")
    return [str(item).strip() for item in rows if str(item).strip()]

def groups_for(key):
    rows = []
    for item in configured:
        if not isinstance(item, dict):
            rows.append("")
            continue
        rows.append(",".join(list_text(item.get(key))))
    return ";".join(rows)

def scalar(value):
    if isinstance(value, bool):
        return "1" if value else "0"
    if value is None:
        return ""
    return str(value).strip()

def joined(value):
    return ",".join(list_text(value))

legacy_resource_policy = runtime_policy.get("resource_policy")
if not isinstance(legacy_resource_policy, dict):
    legacy_resource_policy = {}

profiles = top_level_resource_policy.get("operating_profiles")
if not isinstance(profiles, dict):
    profiles = {}
default_profile = scalar(top_level_resource_policy.get("default_operating_profile")) or scalar(
    legacy_resource_policy.get("operating_profile")
) or "standard"
selected_profile = scalar(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_OPERATING_PROFILE")) or default_profile
selected_resource_profile = profiles.get(selected_profile)
if not isinstance(selected_resource_profile, dict):
    selected_resource_profile = profiles.get(default_profile)
if not isinstance(selected_resource_profile, dict):
    selected_resource_profile = {}
resource_profile = {**legacy_resource_policy, **selected_resource_profile}

exports = {
    "project_contract_shard_focus_profile_groups": groups_for("focus_profile"),
    "project_contract_shard_owner_groups": groups_for("focus_owner"),
    "project_contract_shard_focus_text_groups": groups_for("focus_text"),
    "project_contract_state_root": scalar(launcher_defaults.get("state_root") or runtime_policy.get("state_root")),
    "project_contract_parallel_shards": scalar(
        launcher_defaults.get("parallel_shards")
        or resource_profile.get("max_active_shards")
        or runtime_policy.get("shard_count")
    ),
    "project_contract_clear_lock_on_boot": scalar(
        launcher_defaults.get("clear_lock_on_boot", runtime_policy.get("clear_lock_on_boot"))
    ),
    "project_contract_health_max_age_seconds": scalar(
        resource_profile.get("health_max_age_seconds") or runtime_policy.get("health_max_age_seconds")
    ),
    "project_contract_shard_start_stagger_seconds": scalar(runtime_policy.get("shard_start_stagger_seconds")),
    "project_contract_frontier_derive_mode": scalar(runtime_policy.get("frontier_derive_mode")),
    "project_contract_dynamic_account_routing": scalar(runtime_policy.get("dynamic_account_routing")),
    "project_contract_prefer_full_ea_lanes": scalar(runtime_policy.get("prefer_full_ea_lanes")),
    "project_contract_pin_account_aliases": scalar(runtime_policy.get("pin_account_aliases")),
    "project_contract_worker_bin": scalar(runtime_policy.get("worker_bin")),
    "project_contract_worker_lane": scalar(runtime_policy.get("worker_lane")),
    "project_contract_worker_model": scalar(runtime_policy.get("worker_model")),
    "project_contract_fallback_lanes": joined(runtime_policy.get("fallback_lanes")),
    "project_contract_fallback_models": joined(runtime_policy.get("fallback_models")),
    "project_contract_operating_profile": scalar(selected_profile),
    "project_contract_memory_dispatch_reserve_gib": scalar(resource_profile.get("memory_dispatch_reserve_gib")),
    "project_contract_memory_dispatch_shard_budget_gib": scalar(resource_profile.get("memory_dispatch_shard_budget_gib")),
    "project_contract_memory_dispatch_warning_available_percent": scalar(
        resource_profile.get("memory_dispatch_warning_available_percent")
    ),
    "project_contract_memory_dispatch_critical_available_percent": scalar(
        resource_profile.get("memory_dispatch_critical_available_percent")
    ),
    "project_contract_memory_dispatch_warning_swap_used_percent": scalar(
        resource_profile.get("memory_dispatch_warning_swap_used_percent")
    ),
    "project_contract_memory_dispatch_critical_swap_used_percent": scalar(
        resource_profile.get("memory_dispatch_critical_swap_used_percent")
    ),
    "project_contract_memory_dispatch_parked_poll_seconds": scalar(
        top_level_resource_policy.get("memory_dispatch_parked_poll_seconds")
        or legacy_resource_policy.get("memory_dispatch_parked_poll_seconds")
    ),
}
for key, value in exports.items():
    print(f"{key}={shlex.quote(value)}")
PY
}

apply_env_default() {
  local name="$1"
  local value="${2:-}"
  if [[ -n "${value//[[:space:]]/}" && -z "${!name:-}" ]]; then
    printf -v "$name" '%s' "$value"
    export "$name"
  fi
}

project_contract_defaults="$(load_project_runtime_contract_defaults "$project_config_path")"
if [[ -n "$project_contract_defaults" ]]; then
  eval "$project_contract_defaults"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT "${project_contract_state_root:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_PARALLEL_SHARDS "${project_contract_parallel_shards:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_CLEAR_LOCK_ON_BOOT "${project_contract_clear_lock_on_boot:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_HEALTH_MAX_AGE_SECONDS "${project_contract_health_max_age_seconds:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_SHARD_START_STAGGER_SECONDS "${project_contract_shard_start_stagger_seconds:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_FRONTIER_DERIVE_MODE "${project_contract_frontier_derive_mode:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_DYNAMIC_ACCOUNT_ROUTING "${project_contract_dynamic_account_routing:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_PREFER_FULL_EA_LANES "${project_contract_prefer_full_ea_lanes:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_PIN_ACCOUNT_ALIASES "${project_contract_pin_account_aliases:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN "${project_contract_worker_bin:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_WORKER_LANE "${project_contract_worker_lane:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_WORKER_MODEL "${project_contract_worker_model:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_FALLBACK_LANES "${project_contract_fallback_lanes:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_FALLBACK_MODELS "${project_contract_fallback_models:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_OPERATING_PROFILE "${project_contract_operating_profile:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_RESERVE_GIB "${project_contract_memory_dispatch_reserve_gib:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_SHARD_BUDGET_GIB "${project_contract_memory_dispatch_shard_budget_gib:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT "${project_contract_memory_dispatch_warning_available_percent:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT "${project_contract_memory_dispatch_critical_available_percent:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT "${project_contract_memory_dispatch_warning_swap_used_percent:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT "${project_contract_memory_dispatch_critical_swap_used_percent:-}"
  apply_env_default CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_PARKED_POLL_SECONDS "${project_contract_memory_dispatch_parked_poll_seconds:-}"
  if [[ -z "${shard_focus_profile_groups_raw//[[:space:]]/}" ]]; then
    shard_focus_profile_groups_raw="${project_contract_shard_focus_profile_groups:-}"
  fi
  if [[ -z "${shard_owner_groups_raw//[[:space:]]/}" ]]; then
    shard_owner_groups_raw="${project_contract_shard_owner_groups:-}"
  fi
  if [[ -z "${shard_focus_text_groups_raw//[[:space:]]/}" ]]; then
    shard_focus_text_groups_raw="${project_contract_shard_focus_text_groups:-}"
  fi
fi

state_root_base="${CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT:-}"
parallel_shards_raw="${CHUMMER_DESIGN_SUPERVISOR_PARALLEL_SHARDS:-1}"
background_mode="$(printf '%s' "${CHUMMER_DESIGN_SUPERVISOR_BACKGROUND_MODE:-0}" | tr '[:upper:]' '[:lower:]')"
shard_owner_groups_raw="${CHUMMER_DESIGN_SUPERVISOR_SHARD_OWNER_GROUPS:-${shard_owner_groups_raw:-}}"
shard_focus_profile_groups_raw="${CHUMMER_DESIGN_SUPERVISOR_SHARD_FOCUS_PROFILE_GROUPS:-${shard_focus_profile_groups_raw:-}}"
shard_account_groups_raw="${CHUMMER_DESIGN_SUPERVISOR_SHARD_ACCOUNT_GROUPS:-}"
shard_focus_text_groups_raw="${CHUMMER_DESIGN_SUPERVISOR_SHARD_FOCUS_TEXT_GROUPS:-${shard_focus_text_groups_raw:-}}"
shard_frontier_id_groups_raw="${CHUMMER_DESIGN_SUPERVISOR_SHARD_FRONTIER_ID_GROUPS:-}"
shard_worker_bin_groups_raw="${CHUMMER_DESIGN_SUPERVISOR_SHARD_WORKER_BINS:-}"
shard_worker_lane_groups_raw="${CHUMMER_DESIGN_SUPERVISOR_SHARD_WORKER_LANES:-}"
shard_worker_model_groups_raw="${CHUMMER_DESIGN_SUPERVISOR_SHARD_WORKER_MODELS:-}"
dynamic_account_routing_mode="$(printf '%s' "${CHUMMER_DESIGN_SUPERVISOR_DYNAMIC_ACCOUNT_ROUTING:-auto}" | tr '[:upper:]' '[:lower:]')"
pinned_account_aliases_mode="$(printf '%s' "${CHUMMER_DESIGN_SUPERVISOR_PIN_ACCOUNT_ALIASES:-0}" | tr '[:upper:]' '[:lower:]')"
clear_lock_on_boot="${CHUMMER_DESIGN_SUPERVISOR_CLEAR_LOCK_ON_BOOT:-0}"
shard_start_stagger_seconds="${CHUMMER_DESIGN_SUPERVISOR_SHARD_START_STAGGER_SECONDS:-3}"
frontier_derive_timeout_seconds="${CHUMMER_DESIGN_SUPERVISOR_FRONTIER_DERIVE_TIMEOUT_SECONDS:-15}"
frontier_derive_mode="$(printf '%s' "${CHUMMER_DESIGN_SUPERVISOR_FRONTIER_DERIVE_MODE:-auto}" | tr '[:upper:]' '[:lower:]')"

case "$(printf '%s' "${CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS:-0}" | tr '[:upper:]' '[:lower:]')" in
  1|true|yes|on)
    common_args+=(--ignore-nonlinux-desktop-host-proof-blockers)
    ;;
esac

if [[ ! "$parallel_shards_raw" =~ ^[0-9]+$ ]]; then
  parallel_shards_raw=1
fi
parallel_shards=$(( parallel_shards_raw < 1 ? 1 : parallel_shards_raw ))
if (( parallel_shards > 1 )) && [[ -z "$state_root_base" ]]; then
  printf 'run_chummer_design_supervisor: parallel shards requires CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT; collapsing to 1.\n' >&2
  parallel_shards=1
fi
if [[ ! "$shard_start_stagger_seconds" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  shard_start_stagger_seconds=3
fi
if [[ ! "$frontier_derive_timeout_seconds" =~ ^[0-9]+$ ]]; then
  frontier_derive_timeout_seconds=15
fi

case "$(printf '%s' "${CHUMMER_DESIGN_SUPERVISOR_PRINT_RUNTIME_POLICY:-0}" | tr '[:upper:]' '[:lower:]')" in
  1|true|yes|on)
    printf 'project_config=%s\n' "$project_config_path"
    printf 'state_root=%s\n' "$state_root_base"
    printf 'parallel_shards=%s\n' "$parallel_shards"
    printf 'clear_lock_on_boot=%s\n' "$clear_lock_on_boot"
    printf 'health_max_age_seconds=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_HEALTH_MAX_AGE_SECONDS:-}"
    printf 'operating_profile=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_OPERATING_PROFILE:-}"
    printf 'memory_dispatch_reserve_gib=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_RESERVE_GIB:-}"
    printf 'memory_dispatch_shard_budget_gib=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_SHARD_BUDGET_GIB:-}"
    printf 'memory_dispatch_warning_available_percent=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT:-}"
    printf 'memory_dispatch_critical_available_percent=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT:-}"
    printf 'memory_dispatch_warning_swap_used_percent=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT:-}"
    printf 'memory_dispatch_critical_swap_used_percent=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT:-}"
    printf 'memory_dispatch_parked_poll_seconds=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_PARKED_POLL_SECONDS:-}"
    printf 'dynamic_account_routing=%s\n' "$dynamic_account_routing_mode"
    printf 'prefer_full_ea_lanes=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_PREFER_FULL_EA_LANES:-}"
    printf 'pin_account_aliases=%s\n' "$pinned_account_aliases_mode"
    printf 'worker_bin=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN:-}"
    printf 'worker_lane=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_WORKER_LANE:-}"
    printf 'worker_model=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_WORKER_MODEL:-}"
    printf 'fallback_lanes=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_FALLBACK_LANES:-}"
    printf 'fallback_models=%s\n' "${CHUMMER_DESIGN_SUPERVISOR_FALLBACK_MODELS:-}"
    printf 'shard_owner_groups=%s\n' "$shard_owner_groups_raw"
    printf 'shard_focus_profile_groups=%s\n' "$shard_focus_profile_groups_raw"
    printf 'shard_focus_text_groups=%s\n' "$shard_focus_text_groups_raw"
    exit 0
    ;;
esac

shard_focus_profile_groups_raw="${shard_focus_profile_groups_raw//$'\n'/;}"
IFS=';' read -r -a shard_focus_profile_groups <<<"$shard_focus_profile_groups_raw"
shard_owner_groups_raw="${shard_owner_groups_raw//$'\n'/;}"
IFS=';' read -r -a shard_owner_groups <<<"$shard_owner_groups_raw"
shard_account_groups_raw="${shard_account_groups_raw//$'\n'/;}"
IFS=';' read -r -a shard_account_groups <<<"$shard_account_groups_raw"
shard_focus_text_groups_raw="${shard_focus_text_groups_raw//$'\n'/;}"
IFS=';' read -r -a shard_focus_text_groups <<<"$shard_focus_text_groups_raw"
shard_frontier_id_groups_raw="${shard_frontier_id_groups_raw//$'\n'/;}"
IFS=';' read -r -a shard_frontier_id_groups <<<"$shard_frontier_id_groups_raw"
shard_worker_bin_groups_raw="${shard_worker_bin_groups_raw//$'\n'/;}"
IFS=';' read -r -a shard_worker_bins <<<"$shard_worker_bin_groups_raw"
shard_worker_lane_groups_raw="${shard_worker_lane_groups_raw//$'\n'/;}"
IFS=';' read -r -a shard_worker_lanes <<<"$shard_worker_lane_groups_raw"
shard_worker_model_groups_raw="${shard_worker_model_groups_raw//$'\n'/;}"
IFS=';' read -r -a shard_worker_models <<<"$shard_worker_model_groups_raw"

append_split_flags() {
  local -n dest="$1"
  local flag="$2"
  local raw="${3:-}"
  local item
  raw="${raw//$'\n'/,}"
  raw="${raw//;/,}"
  IFS=',' read -r -a items <<<"$raw"
  for item in "${items[@]}"; do
    item="${item#"${item%%[![:space:]]*}"}"
    item="${item%"${item##*[![:space:]]}"}"
    if [[ -n "$item" ]]; then
      dest+=("$flag" "$item")
    fi
  done
}

filter_shard_passthrough_args() {
  local -n dest="$1"
  shift
  local skip_next=0
  local arg=""
  dest=()
  for arg in "$@"; do
    if (( skip_next )); then
      skip_next=0
      continue
    fi
    case "$arg" in
      --state-root|--focus-owner|--focus-text|--frontier-id|--account-alias|--account-owner-id|--worker-bin|--worker-lane|--worker-model)
        skip_next=1
        continue
        ;;
      --state-root=*|--focus-owner=*|--focus-text=*|--frontier-id=*|--account-alias=*|--account-owner-id=*|--worker-bin=*|--worker-lane=*|--worker-model=*)
        continue
        ;;
    esac
    dest+=("$arg")
  done
}

is_truthy_value() {
  case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes|on)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

uses_ea_worker_routing() {
  local worker_lane="${1:-}"
  local worker_model="${2:-}"
  case "$worker_model" in
    ea-*)
      return 0
      ;;
  esac
  case "$worker_lane" in
    easy|repair|groundwork|review_light|core|core_authority|core_booster|core_rescue|review_shard|audit_shard|survival)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

use_dynamic_account_routing() {
  local worker_lane="${1:-${CHUMMER_DESIGN_SUPERVISOR_WORKER_LANE:-}}"
  local worker_model="${2:-${CHUMMER_DESIGN_SUPERVISOR_WORKER_MODEL:-}}"
  if is_truthy_value "$pinned_account_aliases_mode"; then
    return 1
  fi
  case "$dynamic_account_routing_mode" in
    1|true|yes|on|dynamic)
      return 0
      ;;
    0|false|no|off|pinned)
      return 1
      ;;
  esac
  uses_ea_worker_routing "$worker_lane" "$worker_model"
}

worker_bin_uses_codexea() {
  local worker_bin="${1:-${CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN:-codex}}"
  local token=""
  token="$(basename "$worker_bin" | tr '[:upper:]' '[:lower:]')"
  [[ "$token" == "codexea" ]]
}

should_derive_frontier() {
  case "$frontier_derive_mode" in
    1|true|yes|on|derive)
      return 0
      ;;
    0|false|no|off|skip)
      return 1
      ;;
  esac
  (( parallel_shards <= 1 ))
}

frontier_derive_is_forced() {
  case "$frontier_derive_mode" in
    1|true|yes|on|derive)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

shard_manifest_path() {
  if [[ -z "$state_root_base" ]]; then
    return 1
  fi
  printf '%s/active_shards.json\n' "$state_root_base"
}

published_shard_frontier_ids() {
  local shard_index="${1:-}"
  if [[ -z "$shard_index" ]]; then
    return 0
  fi
  local path="/docker/fleet/.codex-studio/published/full-product-frontiers/shard-${shard_index}.generated.yaml"
  if [[ ! -f "$path" ]]; then
    return 0
  fi
  python3 - "$path" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
ids = []
capture = False
for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.rstrip()
    if line.strip() == "frontier_ids:":
        capture = True
        continue
    if not capture:
        continue
    stripped = line.strip()
    if not stripped:
        continue
    if stripped.startswith("- "):
        value = stripped[2:].strip()
        if value.isdigit():
            ids.append(value)
        continue
    break
print(",".join(ids))
PY
}

write_active_shard_manifest() {
  local manifest_path=""
  manifest_path="$(shard_manifest_path)" || return 0
  mkdir -p "$state_root_base"
  python3 - "$manifest_path" "$@" <<'PY'
import json
import hashlib
from datetime import datetime, timezone
import sys
from pathlib import Path

path = Path(sys.argv[1])
def split_list(raw: str) -> list[str]:
    compact = str(raw or "").replace("\n", ",").replace(";", ",")
    return [item.strip() for item in compact.split(",") if item.strip()]

rows = []
for raw_item in sys.argv[2:]:
    item = str(raw_item).strip()
    if not item:
        continue
    if "\t" not in item:
        rows.append(item)
        continue
    parts = item.split("\t")
    while len(parts) < 9:
        parts.append("")
    def looks_like_worker_bin(value: str) -> bool:
        token = str(value or "").strip().rsplit("/", 1)[-1].lower()
        return token in {"codex", "codexea"}
    if len(parts) >= 10:
        name, index, frontier_ids, focus_profile, focus_owner, account_alias, focus_text, worker_bin, worker_lane, worker_model = parts[:10]
    elif len(parts) == 9 and (not parts[3].strip() or looks_like_worker_bin(parts[7])):
        name, index, frontier_ids, focus_profile, focus_owner, account_alias, focus_text, worker_bin, worker_lane = parts[:9]
        worker_model = ""
    else:
        name, index, frontier_ids, focus_owner, account_alias, focus_text, worker_bin, worker_lane, worker_model = parts[:9]
        focus_profile = ""
    entry = {"name": name.strip()}
    if str(index).strip().isdigit():
        entry["index"] = int(str(index).strip())
    frontier = [int(value) for value in split_list(frontier_ids) if value.isdigit()]
    if frontier:
        entry["frontier_ids"] = frontier
    for key, raw_value in (
        ("focus_profile", focus_profile),
        ("focus_owner", focus_owner),
        ("account_alias", account_alias),
        ("focus_text", focus_text),
    ):
        values = split_list(raw_value)
        if values:
            entry[key] = values
    if str(worker_bin).strip():
        entry["worker_bin"] = str(worker_bin).strip()
    if str(worker_lane).strip():
        entry["worker_lane"] = str(worker_lane).strip()
    if str(worker_model).strip():
        entry["worker_model"] = str(worker_model).strip()
    rows.append(entry)

topology_fingerprint = hashlib.sha256(
    json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
payload = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "manifest_kind": "configured_shard_topology",
    "topology_fingerprint": topology_fingerprint,
    "configured_shard_count": len(rows),
    "configured_shards": rows,
    "active_run_count": None,
    "active_shards": rows,
}
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

build_loop_args() {
  local -n dest="$1"
  local shard_index="$2"
  local shard_focus_profile="${3:-}"
  local shard_group="${4:-}"
  local shard_accounts="${5:-}"
  local shard_focus_text="${6:-}"
  local shard_frontier_ids="${7:-}"
  local shard_worker_bin="${8:-}"
  local shard_worker_lane="${9:-}"
  local shard_worker_model="${10:-}"
  local effective_worker_bin="${shard_worker_bin:-${CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN:-codex}}"
  local shard_state_root=""
  IFS='|' read -r shard_worker_lane shard_worker_model <<<"$(resolve_shard_worker_profile "$effective_worker_bin" "$shard_focus_text" "$shard_worker_lane" "$shard_worker_model")"
  dest=("${common_args[@]}")
  if [[ -n "$state_root_base" ]]; then
    shard_state_root="$state_root_base"
    if (( parallel_shards > 1 )); then
      shard_state_root="${state_root_base}/shard-${shard_index}"
      mkdir -p "$shard_state_root"
    fi
    dest+=(--state-root "$shard_state_root")
    if [[ "$clear_lock_on_boot" == "1" ]]; then
      rm -f "$shard_state_root/loop.lock"
    fi
  fi
  if [[ -n "$shard_group" ]]; then
    append_split_flags "$1" --focus-owner "$shard_group"
  fi
  if [[ -n "$shard_focus_profile" ]]; then
    append_split_flags "$1" --focus-profile "$shard_focus_profile"
  fi
  if [[ -n "$shard_accounts" ]] && ! use_dynamic_account_routing "$shard_worker_lane" "$shard_worker_model"; then
    append_split_flags "$1" --account-alias "$shard_accounts"
  fi
  if [[ -n "$shard_focus_text" ]]; then
    append_split_flags "$1" --focus-text "$shard_focus_text"
  fi
  if [[ -n "$shard_frontier_ids" ]]; then
    append_split_flags "$1" --frontier-id "$shard_frontier_ids"
  fi
  if [[ -n "$effective_worker_bin" ]]; then
    dest+=(--worker-bin "$effective_worker_bin")
  fi
  if [[ -n "$shard_worker_lane" ]]; then
    dest+=(--worker-lane "$shard_worker_lane")
  fi
  if [[ -n "$shard_worker_model" ]]; then
    dest+=(--worker-model "$shard_worker_model")
  elif [[ -n "$shard_worker_lane" ]]; then
    dest+=(--worker-model "")
  fi
}

detached_log_path() {
  local shard_index="$1"
  if [[ -n "$state_root_base" ]]; then
    local shard_state_root="$state_root_base"
    if (( parallel_shards > 1 )); then
      shard_state_root="${state_root_base}/shard-${shard_index}"
    fi
    mkdir -p "$shard_state_root"
    printf '%s/supervisor.log\n' "$shard_state_root"
    return 0
  fi
  printf '/tmp/chummer_design_supervisor_shard_%s.log\n' "$shard_index"
}

launch_detached_loop() {
  local shard_index="$1"
  shift
  local log_path=""
  log_path="$(detached_log_path "$shard_index")"
  setsid -f python3 scripts/chummer_design_supervisor.py loop "$@" \
    >>"$log_path" \
    2>&1 \
    < /dev/null
}

normalize_shard_worker_model() {
  local shard_worker_lane="${1:-}"
  local shard_worker_model="${2:-}"
	case "$shard_worker_lane:$shard_worker_model" in
	    core:ea-coder-hard-batch|core:ea-coder-hard|\
	    core_authority:ea-coder-hard-batch|core_authority:ea-coder-hard|\
	    core_booster:ea-coder-hard-batch|core_booster:ea-coder-hard|\
	    core_rescue:ea-coder-hard-batch|core_rescue:ea-coder-hard|\
	    review_shard:ea-coder-hard-batch|review_shard:ea-coder-hard|\
	    audit_shard:ea-coder-hard-batch|audit_shard:ea-coder-hard)
	      if [[ -n "$shard_worker_model" ]]; then
	        printf '%s' "$shard_worker_model"
	      else
	        printf '%s' 'ea-coder-hard'
	      fi
	      ;;
    *)
      printf '%s' "$shard_worker_model"
      ;;
  esac
}

prefer_full_ea_lanes() {
  case "${CHUMMER_DESIGN_SUPERVISOR_PREFER_FULL_EA_LANES:-0}" in
    1|true|TRUE|yes|YES|on|ON)
      return 0
      ;;
  esac
  return 1
}

resolve_shard_worker_profile() {
  local shard_worker_bin="${1:-${CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN:-codex}}"
  local shard_focus_text="${2:-}"
  local shard_worker_lane="${3:-}"
  local shard_worker_model="${4:-}"
  local focus_text_lower=""
  local resolved_lane="${shard_worker_lane:-}"
  local resolved_model="${shard_worker_model:-}"

  if ! worker_bin_uses_codexea "$shard_worker_bin"; then
    printf '%s|%s\n' "$resolved_lane" "$resolved_model"
    return 0
  fi

  focus_text_lower="$(printf '%s' "$shard_focus_text" | tr '[:upper:]' '[:lower:]')"

	  case "$resolved_lane" in
	    core|core_authority|core_booster|core_rescue)
	      if [[ -z "$resolved_model" ]]; then
	        resolved_model="ea-coder-hard"
	      fi
      resolved_model="$(normalize_shard_worker_model "$resolved_lane" "$resolved_model")"
      printf '%s|%s\n' "$resolved_lane" "$resolved_model"
      return 0
      ;;
  esac

  case "$resolved_lane" in
	    groundwork|repair|review_shard|audit_shard|survival|easy|jury|review_light)
	      if prefer_full_ea_lanes && [[ "$resolved_lane" =~ ^(repair|survival)$ ]]; then
	        resolved_lane="core"
	        resolved_model="ea-coder-hard"
	      fi
      if [[ "$resolved_lane" == "easy" ]]; then
        resolved_model=""
      fi
      resolved_model="$(normalize_shard_worker_model "$resolved_lane" "$resolved_model")"
      printf '%s|%s\n' "$resolved_lane" "$resolved_model"
      return 0
      ;;
  esac

  case "$focus_text_lower" in
    *bootstrap*|*install-linking*|*claim-restore*|*handoff-tests*|*download-tests*)
      resolved_lane="repair"
      resolved_model="ea-coder-fast"
      ;;
    *canon*|*design-guide*|*legacy-user*)
      resolved_lane="easy"
      resolved_model=""
      ;;
    *branding*|*icon*|*troll*|*overlay-6*|*assets*|*desktop-brand*)
      resolved_lane="groundwork"
      resolved_model="ea-groundwork-gemini"
      ;;
    *downloads*|*handoff*|*dispatch*|*exe-first*|*linux-download*|*account-gating*)
      resolved_lane="groundwork"
      resolved_model="ea-groundwork-gemini"
      ;;
    *supervisor*|*ooda*|*currentness*|*autofix*|*queue*|*blockers*)
      resolved_lane="survival"
      resolved_model="ea-coder-survival"
      ;;
	    *desktop-exit-gate*|*platform-gates*|*startup-smoke*|*release-gates*|*release-proof*|*flagship-readiness*|*grade-bar*|*materializer*|*proof*)
	      resolved_lane="audit_shard"
	      resolved_model="ea-coder-hard"
	      ;;
	    *visual-similarity*|*parity*)
	      resolved_lane="review_shard"
	      resolved_model="ea-coder-hard"
	      ;;
  esac

	  if prefer_full_ea_lanes && [[ "$resolved_lane" =~ ^(repair|survival)$ ]]; then
	    resolved_lane="core"
	    resolved_model="ea-coder-hard"
	  fi

  resolved_model="$(normalize_shard_worker_model "$resolved_lane" "$resolved_model")"
  printf '%s|%s\n' "$resolved_lane" "$resolved_model"
}

derive_frontier_fingerprint() {
  local -a derive_args=("$@")
  local payload=""
  if (( frontier_derive_timeout_seconds > 0 )); then
    if ! payload="$(timeout "${frontier_derive_timeout_seconds}" python3 scripts/chummer_design_supervisor.py status --json "${derive_args[@]}")"; then
      printf 'run_chummer_design_supervisor: frontier derive timed out or failed; falling back to focus-only shard identity\n' >&2
      return 0
    fi
  else
    if ! payload="$(python3 scripts/chummer_design_supervisor.py status --json "${derive_args[@]}")"; then
      printf 'run_chummer_design_supervisor: failed to derive frontier via status --json; falling back to focus-only shard identity\n' >&2
      return 0
    fi
  fi
  PAYLOAD_JSON="$payload" python3 - <<'PY'
import json
import os
import sys

try:
    payload = json.loads(os.environ.get("PAYLOAD_JSON", ""))
except Exception:
    print("run_chummer_design_supervisor: status --json returned invalid JSON", file=sys.stderr)
    raise SystemExit(1)
frontier = payload.get("frontier_ids") or []
fingerprint = ",".join(str(item) for item in frontier if str(item).strip())
print(fingerprint)
PY
}

normalize_frontier_fingerprint() {
  python3 - "$1" <<'PY'
import sys

raw = str(sys.argv[1] if len(sys.argv) > 1 else "")
tokens = []
for part in raw.replace("\n", ",").replace(";", ",").split(","):
    token = part.strip()
    if not token:
        continue
    try:
        number = int(token)
    except ValueError:
        continue
    if number > 0:
        tokens.append(str(number))
print(",".join(tokens))
PY
}

normalize_shard_focus_fingerprint() {
  python3 - "$@" <<'PY'
import sys

parts = []
for raw in sys.argv[1:]:
    compact = str(raw or "").replace("\n", ",").replace(";", ",")
    values = [item.strip().lower() for item in compact.split(",") if item.strip()]
    if values:
        parts.append(",".join(values))
print("|".join(parts))
PY
}

reset_shard_runtime_state() {
  local shard_index="$1"
  if [[ -z "$state_root_base" ]]; then
    return 0
  fi
  local shard_state_root="$state_root_base"
  if (( parallel_shards > 1 )); then
    shard_state_root="${state_root_base}/shard-${shard_index}"
  fi
  rm -f \
    "$shard_state_root/account_runtime.json" \
    "$shard_state_root/state.json" \
    "$shard_state_root/active_run.json" \
    "$shard_state_root/loop.lock"
}

archive_retired_shard_state_roots() {
  if [[ -z "$state_root_base" || ! -d "$state_root_base" ]]; then
    return 0
  fi
  local retired_root="$state_root_base/retired-shards"
  local archive_stamp
  archive_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  shopt -s nullglob
  local candidate=""
  for candidate in "$state_root_base"/shard-*; do
    [[ -d "$candidate" ]] || continue
    local shard_name="${candidate##*/}"
    local keep=0
    local active_name=""
    for active_name in "${active_shard_names[@]:-}"; do
      if [[ "$shard_name" == "$active_name" ]]; then
        keep=1
        break
      fi
    done
    if (( keep == 1 )); then
      continue
    fi
    mkdir -p "$retired_root"
    local target_path="$retired_root/${shard_name}-${archive_stamp}"
    while [[ -e "$target_path" ]]; do
      target_path="${retired_root}/${shard_name}-${archive_stamp}-${RANDOM}"
    done
    if mv "$candidate" "$target_path"; then
      printf 'run_chummer_design_supervisor: archived retired shard state %s -> %s\n' "$candidate" "$target_path" >&2
    fi
  done
  shopt -u nullglob
}

append_split_flags common_args --account-owner-id "${CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_OWNER_IDS:-}"
if ! use_dynamic_account_routing "${CHUMMER_DESIGN_SUPERVISOR_WORKER_LANE:-}" "${CHUMMER_DESIGN_SUPERVISOR_WORKER_MODEL:-}"; then
  append_split_flags common_args --account-alias "${CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_ALIASES:-}"
fi
append_split_flags common_args --focus-profile "${CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE:-}"
append_split_flags common_args --focus-owner "${CHUMMER_DESIGN_SUPERVISOR_FOCUS_OWNER:-}"
append_split_flags common_args --focus-text "${CHUMMER_DESIGN_SUPERVISOR_FOCUS_TEXT:-}"
passthrough_args=()
filter_shard_passthrough_args passthrough_args "$@"

if (( parallel_shards <= 1 )); then
  args=()
  active_shard_names=("shard-1")
  archive_retired_shard_state_roots
  write_active_shard_manifest "shard-1"$'\t'"1"$'\t'"${shard_frontier_id_groups[0]:-}"$'\t'"${shard_focus_profile_groups[0]:-}"$'\t'"${shard_owner_groups[0]:-}"$'\t'"${shard_account_groups[0]:-}"$'\t'"${shard_focus_text_groups[0]:-}"$'\t'"${shard_worker_bins[0]:-${CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN:-codex}}"$'\t'"${shard_worker_lanes[0]:-}"$'\t'"${shard_worker_models[0]:-}"
  build_loop_args args 1 "${shard_focus_profile_groups[0]:-}" "${shard_owner_groups[0]:-}" "${shard_account_groups[0]:-}" "${shard_focus_text_groups[0]:-}" "${shard_frontier_id_groups[0]:-}" "${shard_worker_bins[0]:-}" "${shard_worker_lanes[0]:-}" "${shard_worker_models[0]:-}"
  if [[ "$background_mode" == "1" || "$background_mode" == "true" || "$background_mode" == "yes" ]]; then
    launch_detached_loop 1 "${passthrough_args[@]}" "${args[@]}"
    sleep 1
    exit 0
  fi
  exec python3 scripts/chummer_design_supervisor.py loop "${passthrough_args[@]}" "${args[@]}"
fi

pids=()
declare -A frontier_fingerprints=()
active_shard_names=()
active_shard_indexes=()
active_manifest_rows=()
if [[ -n "$state_root_base" ]]; then
  rm -f \
    "$state_root_base/active_shards.json" \
    "$state_root_base/active_run.json"
fi
cleanup() {
  trap - EXIT TERM INT
  local pid
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait || true
}
trap cleanup EXIT TERM INT

preseed_manifest_rows=()
if [[ -n "$state_root_base" ]] && (( parallel_shards > 1 )); then
  for ((shard_index = 1; shard_index <= parallel_shards; shard_index++)); do
    shard_frontier_ids_raw="${shard_frontier_id_groups[$((shard_index - 1))]:-}"
    if [[ -z "${shard_frontier_ids_raw//[[:space:]]/}" ]] && ! frontier_derive_is_forced; then
      shard_frontier_ids_raw="$(published_shard_frontier_ids "$shard_index")"
    fi
    shard_manifest_worker_bin="${shard_worker_bins[$((shard_index - 1))]:-${CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN:-codex}}"
    shard_manifest_worker_lane="${shard_worker_lanes[$((shard_index - 1))]:-}"
    IFS='|' read -r shard_manifest_worker_lane shard_manifest_worker_model <<<"$(resolve_shard_worker_profile "$shard_manifest_worker_bin" "${shard_focus_text_groups[$((shard_index - 1))]:-}" "$shard_manifest_worker_lane" "${shard_worker_models[$((shard_index - 1))]:-}")"
    shard_manifest_accounts="${shard_account_groups[$((shard_index - 1))]:-}"
    if use_dynamic_account_routing "$shard_manifest_worker_lane" "$shard_manifest_worker_model"; then
      shard_manifest_accounts=""
    fi
    normalized_frontier_ids=""
    if [[ -n "${shard_frontier_ids_raw//[[:space:]]/}" ]]; then
      normalized_frontier_ids="$(normalize_frontier_fingerprint "$shard_frontier_ids_raw")"
    fi
    preseed_manifest_rows+=(
      "shard-${shard_index}"$'\t'"${shard_index}"$'\t'"${normalized_frontier_ids}"$'\t'"${shard_focus_profile_groups[$((shard_index - 1))]:-}"$'\t'"${shard_owner_groups[$((shard_index - 1))]:-}"$'\t'"${shard_manifest_accounts}"$'\t'"${shard_focus_text_groups[$((shard_index - 1))]:-}"$'\t'"${shard_manifest_worker_bin}"$'\t'"${shard_manifest_worker_lane}"$'\t'"${shard_manifest_worker_model}"
    )
  done
  if (( ${#preseed_manifest_rows[@]} > 0 )); then
    write_active_shard_manifest "${preseed_manifest_rows[@]}"
  fi
fi

for ((shard_index = 1; shard_index <= parallel_shards; shard_index++)); do
  shard_args=()
  shard_frontier_ids_raw="${shard_frontier_id_groups[$((shard_index - 1))]:-}"
  if [[ -z "${shard_frontier_ids_raw//[[:space:]]/}" ]] && ! frontier_derive_is_forced; then
    shard_frontier_ids_raw="$(published_shard_frontier_ids "$shard_index")"
  fi
  shard_focus_fingerprint="$(normalize_shard_focus_fingerprint "${CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE:-},${shard_focus_profile_groups[$((shard_index - 1))]:-}" "${shard_owner_groups[$((shard_index - 1))]:-}" "${shard_focus_text_groups[$((shard_index - 1))]:-}")"
  shard_account_fingerprint="$(normalize_shard_focus_fingerprint "${shard_account_groups[$((shard_index - 1))]:-}")"
  effective_shard_worker_bin="${shard_worker_bins[$((shard_index - 1))]:-${CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN:-codex}}"
  reset_shard_runtime_state "$shard_index"
  build_loop_args shard_args "$shard_index" "${shard_focus_profile_groups[$((shard_index - 1))]:-}" "${shard_owner_groups[$((shard_index - 1))]:-}" "${shard_account_groups[$((shard_index - 1))]:-}" "${shard_focus_text_groups[$((shard_index - 1))]:-}" "$shard_frontier_ids_raw" "${shard_worker_bins[$((shard_index - 1))]:-}" "${shard_worker_lanes[$((shard_index - 1))]:-}" "${shard_worker_models[$((shard_index - 1))]:-}"
  frontier_fingerprint=""
  if [[ -n "${shard_frontier_ids_raw//[[:space:]]/}" ]]; then
    frontier_fingerprint="$(normalize_frontier_fingerprint "$shard_frontier_ids_raw")"
  elif should_derive_frontier; then
    frontier_fingerprint="$(derive_frontier_fingerprint "${shard_args[@]}" "$@")"
  fi
  if [[ -z "$frontier_fingerprint" ]]; then
    frontier_fingerprint="focus:${shard_focus_fingerprint}"
  fi
  shard_identity_key="${frontier_fingerprint}|${shard_focus_fingerprint}"
  if [[ -n "$shard_account_fingerprint" ]]; then
    shard_identity_key+="|account:${shard_account_fingerprint}"
  fi
  IFS='|' read -r shard_identity_worker_lane shard_identity_worker_model <<<"$(resolve_shard_worker_profile "$effective_shard_worker_bin" "${shard_focus_text_groups[$((shard_index - 1))]:-}" "${shard_worker_lanes[$((shard_index - 1))]:-}" "${shard_worker_models[$((shard_index - 1))]:-}")"
  if [[ -n "$shard_identity_worker_lane" ]]; then
    shard_identity_key+="|lane:${shard_identity_worker_lane}"
  fi
  if [[ -n "$effective_shard_worker_bin" ]]; then
    shard_identity_key+="|bin:${effective_shard_worker_bin}"
  fi
  normalized_shard_worker_model="${shard_identity_worker_model:-}"
  if [[ -n "$normalized_shard_worker_model" ]]; then
    shard_identity_key+="|model:${normalized_shard_worker_model}"
  fi
  if [[ -n "${frontier_fingerprints[$shard_identity_key]:-}" ]]; then
    printf 'run_chummer_design_supervisor: skipping shard-%s because its derived shard identity duplicates shard-%s (%s)\n' "$shard_index" "${frontier_fingerprints[$shard_identity_key]}" "$shard_identity_key" >&2
    continue
  fi
  frontier_fingerprints[$shard_identity_key]="$shard_index"
  active_shard_names+=("shard-${shard_index}")
  active_shard_indexes+=("$shard_index")
  active_manifest_rows+=("shard-${shard_index}"$'\t'"${shard_index}"$'\t'"${frontier_fingerprint}"$'\t'"${shard_focus_profile_groups[$((shard_index - 1))]:-}"$'\t'"${shard_owner_groups[$((shard_index - 1))]:-}"$'\t'"${shard_account_groups[$((shard_index - 1))]:-}"$'\t'"${shard_focus_text_groups[$((shard_index - 1))]:-}"$'\t'"${effective_shard_worker_bin}"$'\t'"${shard_identity_worker_lane}"$'\t'"${normalized_shard_worker_model}")
done

if (( ${#active_shard_indexes[@]} == 0 )); then
  args=()
  active_shard_names=("shard-1")
  archive_retired_shard_state_roots
  write_active_shard_manifest "shard-1"$'\t'"1"$'\t'"${shard_frontier_id_groups[0]:-}"$'\t'"${shard_focus_profile_groups[0]:-}"$'\t'"${shard_owner_groups[0]:-}"$'\t'"${shard_account_groups[0]:-}"$'\t'"${shard_focus_text_groups[0]:-}"$'\t'"${shard_worker_bins[0]:-${CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN:-codex}}"$'\t'"${shard_worker_lanes[0]:-}"$'\t'"${shard_worker_models[0]:-}"
  build_loop_args args 1 "${shard_focus_profile_groups[0]:-}" "${shard_owner_groups[0]:-}" "${shard_account_groups[0]:-}" "${shard_focus_text_groups[0]:-}" "${shard_frontier_id_groups[0]:-}" "${shard_worker_bins[0]:-}" "${shard_worker_lanes[0]:-}" "${shard_worker_models[0]:-}"
  exec python3 scripts/chummer_design_supervisor.py loop "${passthrough_args[@]}" "${args[@]}"
fi

archive_retired_shard_state_roots
write_active_shard_manifest "${active_manifest_rows[@]}"

for shard_index in "${active_shard_indexes[@]}"; do
  if (( ${#pids[@]} > 0 )) && [[ "$shard_start_stagger_seconds" != "0" ]]; then
    sleep "$shard_start_stagger_seconds"
  fi
  shard_args=()
  build_loop_args shard_args "$shard_index" "${shard_focus_profile_groups[$((shard_index - 1))]:-}" "${shard_owner_groups[$((shard_index - 1))]:-}" "${shard_account_groups[$((shard_index - 1))]:-}" "${shard_focus_text_groups[$((shard_index - 1))]:-}" "${shard_frontier_id_groups[$((shard_index - 1))]:-}" "${shard_worker_bins[$((shard_index - 1))]:-}" "${shard_worker_lanes[$((shard_index - 1))]:-}" "${shard_worker_models[$((shard_index - 1))]:-}"
  if [[ "$background_mode" == "1" || "$background_mode" == "true" || "$background_mode" == "yes" ]]; then
    launch_detached_loop "$shard_index" "${passthrough_args[@]}" "${shard_args[@]}"
    continue
  fi
  python3 scripts/chummer_design_supervisor.py loop "${passthrough_args[@]}" "${shard_args[@]}" &
  pids+=("$!")
done

if [[ "$background_mode" == "1" || "$background_mode" == "true" || "$background_mode" == "yes" ]]; then
  sleep 1
  exit 0
fi

status=0
if (( ${#pids[@]} > 0 )); then
  # Wait on the shell's live child table instead of a static PID list.
  # Some shard loops can exit before this point, and passing stale PIDs to
  # `wait -n` can raise "no such job" and tear down an otherwise healthy fleet.
  if wait -n; then
    status=0
  else
    status=$?
  fi
fi
cleanup
exit "$status"
