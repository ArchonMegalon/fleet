#!/usr/bin/env bash
set -euo pipefail

fleet_root="/docker/fleet"
readiness_out="$fleet_root/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json"
readiness_state_mirror_out="$fleet_root/state/chummer_design_supervisor/artifacts/FLAGSHIP_PRODUCT_READINESS.generated.json"
readiness_design_mirror_out="$fleet_root/.codex-design/product/FLAGSHIP_PRODUCT_READINESS.generated.json"
state_root_default="$fleet_root/state/chummer_design_supervisor"
ui_refresh_wait_timeout_seconds="${CHUMMER_FLAGSHIP_UI_REFRESH_WAIT_TIMEOUT_SECONDS:-1800}"
ui_refresh_poll_interval_seconds="${CHUMMER_FLAGSHIP_UI_REFRESH_POLL_INTERVAL_SECONDS:-5}"

resolve_ui_repo_root() {
  if [[ -n "${CHUMMER_UI_REPO_ROOT:-}" ]]; then
    printf '%s\n' "$CHUMMER_UI_REPO_ROOT"
    return 0
  fi
  local candidate
  for candidate in \
    /docker/chummercomplete/chummer6-ui \
    /docker/chummercomplete/chummer6-ui-finish \
    /docker/chummercomplete/chummer-presentation
  do
    if [[ -d "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

ui_root="$(resolve_ui_repo_root)"
b14_script="$ui_root/scripts/ai/milestones/b14-flagship-ui-release-gate.sh"
b14_lock_dir="$ui_root/.codex-studio/locks/b14-flagship-ui-release-gate.lock"
ui_flagship_receipt_path="$ui_root/.codex-studio/published/UI_FLAGSHIP_RELEASE_GATE.generated.json"
ui_visual_gate_path="$ui_root/.codex-studio/published/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
ui_parity_audit_path="$ui_root/.codex-studio/published/CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json"

if ! [[ "$ui_refresh_wait_timeout_seconds" =~ ^[0-9]+$ ]]; then
  ui_refresh_wait_timeout_seconds=1800
fi
if ! [[ "$ui_refresh_poll_interval_seconds" =~ ^[0-9]+$ ]] || [[ "$ui_refresh_poll_interval_seconds" -le 0 ]]; then
  ui_refresh_poll_interval_seconds=5
fi

ui_receipt_mtime() {
  local target="$1"
  if [[ -f "$target" ]]; then
    stat -c '%Y' "$target"
  else
    printf '0\n'
  fi
}

ui_refresh_active() {
  if [[ -d "$b14_lock_dir" ]]; then
    return 0
  fi
  if pgrep -f "$b14_script" >/dev/null 2>&1; then
    return 0
  fi
  if pgrep -f "scripts/ai/milestones/b14-flagship-ui-release-gate.sh" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

wait_for_ui_refresh() {
  local baseline_flagship_mtime="$1"
  local baseline_visual_mtime="$2"
  local waited=0

  while ui_refresh_active; do
    if (( waited >= ui_refresh_wait_timeout_seconds )); then
      echo "[flagship-readiness] FAIL: timed out waiting for UI flagship proof refresh to finish." >&2
      return 1
    fi
    sleep "$ui_refresh_poll_interval_seconds"
    waited=$((waited + ui_refresh_poll_interval_seconds))
  done

  local current_flagship_mtime
  local current_visual_mtime
  current_flagship_mtime="$(ui_receipt_mtime "$ui_flagship_receipt_path")"
  current_visual_mtime="$(ui_receipt_mtime "$ui_visual_gate_path")"
  if (( current_flagship_mtime <= baseline_flagship_mtime )); then
    echo "[flagship-readiness] FAIL: UI flagship release receipt did not refresh." >&2
    return 1
  fi
  if (( current_visual_mtime <= baseline_visual_mtime )); then
    echo "[flagship-readiness] FAIL: desktop visual familiarity receipt did not refresh." >&2
    return 1
  fi
}

refresh_full_product_frontier() {
  local requested_state_root="${CHUMMER_FLAGSHIP_STATE_ROOT:-$state_root_default}"
  local state_roots=()
  local shard_root

  if [[ -d "$requested_state_root" ]]; then
    state_roots+=("$requested_state_root")
  fi

  if [[ -d /var/lib/codex-fleet/chummer_design_supervisor ]]; then
    for shard_root in /var/lib/codex-fleet/chummer_design_supervisor/shard-*; do
      [[ -d "$shard_root" ]] || continue
      if [[ " ${state_roots[*]} " != *" $shard_root "* ]]; then
        state_roots+=("$shard_root")
      fi
    done
  fi

  if ((${#state_roots[@]} == 0)); then
    echo "[flagship-readiness] FAIL: no supervisor state root available for full-product frontier refresh." >&2
    return 1
  fi

  local state_root
  for state_root in "${state_roots[@]}"; do
    python3 - "$state_root" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, "/docker/fleet/scripts")
import chummer_design_supervisor as supervisor

state_root = Path(sys.argv[1]).resolve()
args = supervisor._runtime_snapshot_args_for_state_root(state_root)
base = supervisor.derive_context(args)
supervisor.derive_flagship_product_context(args, state_root, base_context=base)
PY
  done
}

if [[ ! -x "$b14_script" && ! -f "$b14_script" ]]; then
  echo "[flagship-readiness] FAIL: missing UI flagship proof script: $b14_script" >&2
  exit 1
fi

baseline_ui_flagship_mtime="$(ui_receipt_mtime "$ui_flagship_receipt_path")"
baseline_ui_visual_mtime="$(ui_receipt_mtime "$ui_visual_gate_path")"

if ui_refresh_active; then
  echo "[flagship-readiness] reusing active UI flagship proof refresh at $ui_root"
else
  cd "$ui_root"
  CHUMMER_DESKTOP_VISUAL_SKIP_PREREQUISITE_RECEIPT_REFRESH=1 bash "$b14_script"
fi

wait_for_ui_refresh "$baseline_ui_flagship_mtime" "$baseline_ui_visual_mtime"

cd "$fleet_root"
python3 scripts/codex-shims/codexea_ui_parity_audit_probe.py
python3 scripts/materialize_next90_m136_fleet_aggregate_readiness_parity_gates.py
python3 scripts/materialize_next90_m138_fleet_hero_path_projections.py
python3 scripts/materialize_next90_m138_fleet_hero_path_closeout_gates.py
python3 scripts/materialize_flagship_product_readiness.py --out "$readiness_out" --mirror-out "$readiness_state_mirror_out"
cp "$readiness_out" "$readiness_design_mirror_out"
python3 scripts/materialize_weekly_governor_packet.py
refresh_full_product_frontier
