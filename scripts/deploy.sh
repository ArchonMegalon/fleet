#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bash scripts/deploy.sh <command> [args]

Commands:
  admin-status
      Print the live admin status JSON.
  cockpit-summary
      Print a compact live cockpit summary.
  operator-summary
      Print the named operator cards and bridge-account pool status.
  run-project-now <project> [project...]
      Trigger immediate project dispatch through the admin plane.
  run-group-audit <group> [group...]
      Trigger immediate group audits through the admin plane.
  approve-audit-task <task_id> [task_id...]
      Approve one or more audit task candidates through the admin plane.
  heal-group-now <group> [group...]
      Publish approved group healing/refill tasks or trigger a fresh group heal pass.
  chummer-portal
      Probe the local Chummer portal landing and key routed health endpoints.
  build-chummer-windows-downloads
      Build Windows desktop artifact(s) for the local Chummer portal and publish them into /downloads.
  build-chummer-desktop-downloads
      Build and publish the default desktop matrix (Windows x64 and macOS ARM64) into /downloads.
  build-chummer-desktop-windows-downloads
      Build and publish both Avalonia and Blazor Windows desktop artifacts into /downloads.
  build-chummer-avalonia-windows-downloads
      Build and publish only the Avalonia Windows desktop artifact into /downloads.
  build-chummer-desktop-macos-arm64-downloads
      Build and publish both Avalonia and Blazor macOS ARM64 desktop artifacts into /downloads.
  build-chummer-avalonia-macos-arm64-downloads
      Build and publish only the Avalonia macOS ARM64 desktop artifact into /downloads.
  inspect-chummer-mobile
      Inspect the Chummer source tree for Android/iOS/mobile deploy targets and package outputs.
  inspect-chummer-play-mobile
      Inspect the chummer-play repo for native mobile or PWA deploy targets.
  patch-chummer-portal-downloads-ui
      Patch the Chummer portal downloads page to expose platform and app-type selectors.
  verify-chummer-portal-downloads-ui
      Verify the live Chummer portal downloads page exposes platform and type selectors.
  rebuild-chummer-portal
      Rebuild and restart the Chummer portal container, then verify the downloads page.
  patch-and-rebuild-chummer-portal-downloads-ui
      Patch the Chummer portal downloads UI, rebuild the portal, and verify the live page.
  patch-chummer-desktop-source
      Patch the real Chummer desktop source tree with the desktop-safe coach client fallback.
  patch-and-build-chummer-windows-downloads
      Patch the real Chummer desktop source tree, then rebuild and republish the Windows desktop download.
  gateway-cockpit
      Fetch the live cockpit payload through the dashboard gateway.
  probe-public-dashboard
      Fetch the public Fleet login shell and dashboard assets with a browser-like user agent.
  inline-fleet-dashboard-assets
      Inline the dashboard bridge CSS and JS into the dashboard HTML shell.
  repair-bridge-accounts
      Validate the named bridge accounts, clear stale backoff, and print the updated operator summary.
  repair-codex-floor
      Reprobe named accounts, relaunch stranded local-review lanes, and retry transiently stranded coding lanes.
  smoke-fleet-dashboard
      Run a browser smoke test against the live Fleet dashboard login and bridge hydration path.
  gateway-root
      Fetch the root dashboard path headers from inside the gateway container.
  host-root
      Fetch the root dashboard path headers from the host-bound gateway port.
  dashboard-logs
      Print recent fleet-dashboard logs.
  service-logs <service> [tail]
      Print recent logs for a compose service.
  service-ps
      Print compose service status.
  project-status <project> [project...]
      Print compact live project rows from the fleet DB.
  compile-status <project> [project...]
      Print live project lifecycle and compile-health rows from admin status.
  run-status <run_id> [run_id...]
      Print compact live run rows from the fleet DB.
  run-log <run_id>
      Print the recorded log path and recent log output for a run.
  recent-runs <project> [limit]
      Print recent live run rows for one project from the fleet DB.
  probe-account-models <alias> [model...]
      Run a minimal Codex probe through the exact fleet account environment and report which models the account accepts.
  quarantine-account <alias> [hours]
      Put an account into live cooldown immediately so the scheduler stops selecting it.
  time-vienna
      Print the current Vienna time.
  verify-config
      Parse the split fleet config and fail on invalid YAML/schema loading.
  verify-chummer-design-authority
      Check that chummer-design matches the live repo graph, mirror coverage, and root canon rules.
  publish-chummer-design-authority
      Commit and push canonical chummer-design truth plus the mirrored chummer-play design context.
  db-schema <table>
      Print the live SQLite schema for a table.
  verify-python <file> [file...]
      Run python3 -m py_compile on one or more files.
  inject-chummer-public-repo-audit
      Publish the latest scoped Chummer public-repo audit feedback into group and repo feedback lanes.
  inject-chummer-design-dropin-pack
      Publish the latest Chummer design drop-in canon pack into design and group feedback lanes.
  inject-chummer-design-authority-audit
      Publish the latest chummer-design authority-gap audit into design and group feedback lanes.
  inject-chummer-master-designer-handoff
      Publish the latest Chummer master-designer handoff report into design and group feedback lanes.
  inject-chummer-dev-group-change-guide
      Publish the latest Chummer dev-group change guide into design, group, and fleet feedback lanes.
  inject-chummer-foundation-horizon-guidance
      Publish the latest Chummer foundation/horizon guidance into design, group, and fleet feedback lanes.
  inject-chummer-immediate-directives
      Publish the latest Chummer immediate directives into design, group, and fleet feedback lanes.
  sanitize-chummer6-hub-googledrive-secrets
      Remove leaked Google Drive secret files from chummer6-hub, replace them with safe templates, rebuild the repo as a fresh single-commit history, and force-push the clean root.
  janitor-chummer6-repos
      Remove tracked worker debris, local caches, generated queue files, and other safe local-only artifacts from the chummer6 repos, then push only the janitor changes.
  purify-chummer6-legacy-roots
      Retire safe legacy roots in chummer6-hub and chummer6-core, switch hub onto the active hosted boundary, verify both repos, and push the purification commits.
  reset-chummer6-histories
      Stop Fleet, rewrite all chummer6 repos to a fresh single-commit history from the current working tree, force-push them, and start Fleet again.
  purge-chummer6-upscaling-model
      Remove the tracked FireAlpha upscaling model from chummer6-core, chummer6-ui, and chummer6-hub, update the local README guidance, and keep the model local-only.
  purge-chummer6-hub-legacy-gpl
      Remove the leftover GPL-marked legacy tree and sample plugin from chummer6-hub, rewrite the hosted-boundary docs/tests, move the active hosted boundary to .NET 10, and run the hub verification lane.
  finish-chummer6-guide
      Create or update the public downstream Chummer6 human-guide repo, render local guide art (and optional provider-backed image assets such as MarkupGo when locally configured), write its human-only content, publish the canonical guide scope note in chummer6-design, and verify Fleet config for the signoff-only guide project.
  janitor-chummer6-control-plane
      Create canonical local repo/doc aliases for the renamed Chummer6 family, rewrite Fleet project bindings to use them, and update the guide verifier to reject stale page names.
  advance-ea-chummer6-worker
      Install or refresh the EA-hosted Chummer6 guide worker and repair the EA help smoke script so the worker can be validated and reused from the approved wrapper path.
  check-ea-chummer6-provider-readiness
      Report which Chummer6 text/media providers are actually configured in the EA environment, without exposing secrets.
  probe-browseract-prompting-workflows
      List BrowserAct workflows visible to EA and check whether Chummer6 Prompting Systems refine, humanizer, and AI Magicx render workflows can be resolved.
  probe-browseract-workflow-api
      Probe common BrowserAct workflow create/import endpoints to see whether the workspace can bootstrap workflows programmatically.
  get-browseract-task <task-id> [status|full]
      Fetch the current BrowserAct task status/body for a known task id from the wrapper path.
  probe-browseract-task-log <task-id>
      Open the BrowserAct dashboard log page for a known task id through the wrapper path and capture the visible log text/artifacts.
  cache-browseract-live-workflow <workflow-id> <workflow-name> <env-id> [env-name-key]
      Cache a known live BrowserAct workflow id/name directly into /docker/EA/.env without waiting for a local result file.
  run-browseract-prompt-refine <prompt> [target]
      Build or refresh the BrowserAct Prompting Systems refine workflow, then run it against the given prompt.
  run-browseract-humanizer <text> [target]
      Run the BrowserAct-backed Undetectable humanizer workflow against the given text and print the humanized output.
  run-browseract-humanizer-existing <workflow-name> <text> [target]
      Run an already-published BrowserAct Undetectable humanizer workflow directly.
  run-browseract-prompt-refine-existing <workflow-name> <prompt> [target]
      Run an already-published BrowserAct Prompting Systems refine workflow directly.
  inspect-browseract-runtime <workflow-name>
      Show the latest materialization/publish artifacts for a live BrowserAct workflow runtime directory.
  show-browseract-runtime-log <workflow-name>
      Print the latest BrowserAct materializer config-log for a live workflow runtime directory.
  probe-ea-chummer6-text-provider [--model MODEL]
      Probe 1min text models for the EA Chummer6 worker from the wrapper path.
  probe-magixai-api-live [--width W] [--height H]
      Probe live AI Magicx API endpoint and auth/header variants through the wrapper path.
  run-ea-chummer6-guide-worker [worker args...]
      Run the EA Chummer6 text/OODA worker only and write/update downstream overrides in Fleet state.
  render-ea-chummer6-media-pack
      Run the EA Chummer6 media worker only and refresh the local media asset pack from the current overrides.
  bootstrap-chummer6-browseract-workflows
      Write the current Chummer6 BrowserAct workflow briefs/specs for Prompting Systems refine, Undetectable humanizer, and AI Magicx render into Fleet state, then probe workflow resolution.
  bootstrap-ea-browseract-architect
      Install the stage-0 BrowserAct architect helpers into EA, emit the seed builder packet, and bootstrap the BrowserAct bootstrap-manager skill.
  ensure-ea-api
      Start the local EA API/runtime stack on the standard compose port and wait for /health.
  seed-browseract-architect-live
      Use the local Playwright wrapper image to log into the BrowserAct dashboard and create the first browseract_architect workflow draft live.
  materialize-browseract-architect-live
      Use the local Playwright wrapper image to open the existing browseract_architect workflow and materialize the packet-defined node sequence live.
  build-browseract-workflow-spec <workflow-name> <purpose> <login-url|none> <tool-url> [--prompt-selector SEL] [--submit-selector SEL] [--result-selector SEL]
      Build a BrowserAct target-workflow spec JSON through the EA bootstrap manager.
  build-prompting-systems-prompt-forge
      Build the Prompting Systems prompt-forge workflow spec with explicit wait, input, and extract steps.
  build-undetectable-humanizer
      Build the Undetectable AI Humanizer workflow spec for BrowserAct-driven text humanization.
  materialize-browseract-workflow-live <spec-json>
      Emit a packet from the given BrowserAct workflow spec JSON and materialize or update that workflow live in the BrowserAct dashboard.
  cleanup-browseract-materializers <workflow-name>
      Stop any in-flight wrapper-driven BrowserAct materializer runs for the given workflow name before retrying a live build.
  publish-browseract-workflow-live <workflow-name> [workflow-id]
      Publish an existing live BrowserAct workflow through the wrapper path and capture the result artifact.
  probe-browseract-architect-build-live
      Use the local Playwright wrapper image to open the existing browseract_architect card and probe the real Build/editor transition live.
  probe-browseract-node-edit-live
      Use the local Playwright wrapper image to probe how an existing browseract_architect node re-enters edit mode in the live builder.
  probe-browser-site-live <name> <url>
      Use the local Playwright wrapper image to capture a live target page, screenshot, HTML, and common selector summary into Fleet state.
  inspect-chummer6-refresh
      Show the currently running EA Chummer6 worker processes and the latest guide/media state files from the wrapper path.
  audit-chummer6-ooda
      Verify that the published Chummer6 guide is driven by a first-class OODA contract and OODA-authored media plan.
  refresh-chummer6-guide-via-ea [worker args...]
  publish-chummer6-from-ea-state
      Advance the EA Chummer6 guide worker, run it to write downstream overrides into Fleet state, then regenerate the published Chummer6 guide from those overrides.
  publish-chummer6-poc-release
      Create or update the first Chummer6 proof-of-concept release shelf from the current published downloads manifest.
  fix-chummer6-audit-gaps
      Normalize canonical chummer6 repo naming in design docs, finish the .NET 10 pin drift called out by audit, and update hub container images to .NET 10.
  fix-chummer6-family-coherence
      Rewrite the public chummer6 family front doors, republish review-context mirrors, correct active design truth-maintenance blockers to the real workspace layout, and refresh the Chummer6 guide wording.
  sync-chummer6-design-truth
      Rewrite the active chummer6 design canon and mirror backlog files to the current chummer6 repo names and real media-factory workspace path.
  apply-ea-audit-hardening
      Apply the current EA hardening pass for startup/runtime-profile truth, typed skill metadata, provider-registry scaffolding, planner fixes, LTD inventory additivity, and deployment/docs cleanup.
  verify-ea-audit-hardening
      Run focused EA verification for the current hardening pass.
  inject-ea-main-branch-audit
      Publish the latest EA main-branch hardening audit into repo and group feedback lanes.
  inject-ea-provider-registry-feedback
      Publish the latest EA provider-registry and Unmixr feedback into repo and group feedback lanes.
  update-ea-ltds-unmixr
      Add or refresh the Unmixr AI Tier 4 entry in /docker/EA/LTDs.md.
  update-ea-ltds-browserly
      Add or refresh the Browserly LTD + provider-registry wiring in /docker/EA.
  update-ea-ltds-onemin-business
      Refresh the 1min.AI holding in /docker/EA/LTDs.md to 3 Advanced Business licenses/accounts.
  inject-ea-provider-keys <json-file>
      Inject local provider keys into /docker/EA/.env only, without syncing them into any Chummer repo.
  inject-browseract-dashboard-credentials <email> <password>
      Save the BrowserAct dashboard login into /docker/EA/.env only for the stage-0 architect/bootstrap lane.
  sync-ea-chummer-provider-envs <key-file>
      Save the local Unmixr key into EA env files, refresh provider examples, and sync provider credentials into Chummer local env files.
  inject-fleet-public-audit
      Publish the latest Fleet public architecture audit follow-up into repo feedback.
  inject-fleet-design-progress-feedback
      Publish the latest Fleet design-progress semantics feedback into repo feedback.
  inject-chummer-public-design-ltd-audit
      Publish the latest Chummer public design/LTD audit into design and group feedback lanes.
  publish-latest-pass
      Commit and push the current fleet, EA, chummer-design, and Chummer runtime changes from this pass.
  publish-repo-all <repo> <commit message...>
      Stage all changes in the target repo, commit if needed, and push the current branch.
  publish-repo-all-to <repo> <remote-or-url> <commit message...>
      Stage all changes in the target repo, commit if needed, and push the current branch to the provided remote name or URL.
  publish-repo-files <repo> <commit message...> -- <file> [file...]
      Stage only the listed files in the target repo, commit if needed, and push the current branch.
  publish-repo-force <repo> <commit message...>
      Stage all changes in the target repo, commit if needed, and force-push the current branch.
  stop-fleet
      Stop the Fleet control-plane services before a disruptive migration.
  rehome-chummer6-repos
      Create fresh chummer6-* repos, reinitialize the current Chummer worktrees with a single initial commit, and set the new repos as origin.
  retarget-chummer6-repos
      Update Fleet project GitHub repo bindings to the new chummer6-* repo names.
  github-rate-limit
      Print the current GitHub core rate-limit status for the active gh auth.
  set-chummer-legacy-repos-private
      Set the previous Chummer GitHub repos to private once their chummer6-* replacements exist.
  rebuild <service> [service...]
      Rebuild and restart one or more compose services.
USAGE
}

require_args() {
  if [ "$#" -eq 0 ]; then
    echo "missing arguments" >&2
    exit 1
  fi
}

ensure_chummer_playwright_image() {
  if docker image inspect chummer-playwright:local >/dev/null 2>&1; then
    return 0
  fi
  docker compose -f /docker/chummer5a/docker-compose.yml --profile test --profile portal build chummer-playwright-portal >/dev/null
}

operator_password() {
  if [ -n "${FLEET_OPERATOR_PASSWORD:-}" ]; then
    printf '%s' "${FLEET_OPERATOR_PASSWORD}"
    return 0
  fi
  if [ -f /docker/fleet/runtime.env ]; then
    sed -n 's/^FLEET_OPERATOR_PASSWORD=//p' /docker/fleet/runtime.env | tail -n 1
    return 0
  fi
  echo "FLEET_OPERATOR_PASSWORD is not set and /docker/fleet/runtime.env is missing" >&2
  exit 1
}

admin_status() {
  local password
  password="$(operator_password)"
  if curl -fsS -H "X-Fleet-Operator-Password: ${password}" \
    http://127.0.0.1:8081/api/admin/status >/tmp/fleet_admin_status_wrapper.json 2>/dev/null; then
    cat /tmp/fleet_admin_status_wrapper.json
    return 0
  fi
  docker exec fleet-admin curl -sS -H "X-Fleet-Operator-Password: ${password}" \
    http://127.0.0.1:8092/api/admin/status
}

admin_post() {
  local path="$1"
  local password
  password="$(operator_password)"
  if curl -fsS -o /tmp/fleet_admin_post_wrapper.out -w "%{http_code}\n" \
    -H "X-Fleet-Operator-Password: ${password}" \
    -X POST "http://127.0.0.1:8081${path}" 2>/dev/null; then
    cat /tmp/fleet_admin_post_wrapper.out
    return 0
  fi
  docker exec fleet-admin curl -sS -o /dev/null -w "%{http_code}\n" \
    -H "X-Fleet-Operator-Password: ${password}" \
    -X POST "http://127.0.0.1:8092${path}"
}

fleet_admin_python() {
  docker exec fleet-admin python3 "$@"
}

fleet_admin_shell() {
  docker exec fleet-admin sh -lc "$1"
}

cleanup_chummer6_worker_processes() {
  fleet_admin_shell 'self=$$; for pattern in "/docker/EA/scripts/chummer6_guide_worker.py" "/docker/EA/scripts/chummer6_guide_media_worker.py" "/tmp/chummer6_guide_"; do for pid in $(pgrep -f "$pattern" 2>/dev/null || true); do [ "$pid" = "$self" ] && continue; kill "$pid" 2>/dev/null || true; done; done'
}

cleanup_local_chummer6_worker_processes() {
  local self="$$"
  for pattern in "/docker/EA/scripts/chummer6_guide_worker.py" "/docker/EA/scripts/chummer6_guide_media_worker.py" "/tmp/chummer6_guide_"; do
    for pid in $(pgrep -f "$pattern" 2>/dev/null || true); do
      [ "$pid" = "$self" ] && continue
      kill "$pid" 2>/dev/null || true
    done
  done
}

stop_fleet() {
  docker compose stop fleet-admin fleet-controller fleet-dashboard fleet-auditor fleet-quartermaster fleet-studio
}

start_fleet() {
  docker compose up -d fleet-admin fleet-controller fleet-dashboard fleet-auditor fleet-quartermaster fleet-studio
}

reset_chummer6_histories() {
  stop_fleet
  python3 /docker/fleet/scripts/reset_chummer6_histories.py
  start_fleet
}

operator_summary() {
  admin_status | python3 -c '
import json, sys
data = json.load(sys.stdin)
cards = data.get("cockpit", {}).get("operators", []) or []
accounts = data.get("cockpit", {}).get("runway", {}).get("accounts", []) or []
named = [row for row in accounts if row.get("bridge_name")]
print(json.dumps({
  "operators": [
    {
      "label": card.get("label"),
      "alias": card.get("alias"),
      "token_status": card.get("token_status"),
      "pool_left": card.get("pool_left"),
      "current_summary": card.get("current_summary"),
      "occupied_runs": card.get("occupied_runs"),
      "active_runs": card.get("active_runs"),
    }
    for card in cards
  ],
  "named_accounts": [
    {
      "alias": row.get("alias"),
      "bridge_name": row.get("bridge_name"),
      "standard_pool_state": row.get("standard_pool_state"),
      "spark_pool_state": row.get("spark_pool_state"),
      "active_runs": row.get("active_runs"),
      "recent_backoff": row.get("recent_backoff"),
      "pressure_state": row.get("pressure_state"),
    }
    for row in named
  ],
}, indent=2))
'
}

probe_account_models() {
  require_args "$@"
  docker exec -i fleet-controller python3 - "$@" <<'PY'
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, "/app")
import app  # type: ignore

alias = sys.argv[1]
models = sys.argv[2:] or ["gpt-5.3-codex", "gpt-5.4", "gpt-5-mini", "gpt-5-nano", "gpt-5.3-codex-spark"]
config = app.normalize_config()
account_cfg = (config.get("accounts") or {}).get(alias)
if not account_cfg:
    raise SystemExit(f"unknown account alias: {alias}")

results = []
for model in models:
    env = app.prepare_account_environment(alias, account_cfg)
    cmd = [
        "codex",
        "--ask-for-approval",
        "never",
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--sandbox",
        "danger-full-access",
        "--cd",
        "/tmp",
        "--model",
        model,
        "-",
    ]
    proc = subprocess.run(
        cmd,
        input="Reply with exactly OK.\n",
        text=True,
        capture_output=True,
        env=env,
        timeout=90,
    )
    combined = "\n".join(part for part in [proc.stdout, proc.stderr] if part).strip()
    detail = ""
    if "not supported when using Codex with a ChatGPT account" in combined:
        detail = "unsupported_for_chatgpt_auth"
    elif "rate limit" in combined.lower() or "429" in combined:
        detail = "rate_limited"
    elif proc.returncode == 0:
        detail = "ok"
    else:
        detail = "failed"
    results.append(
        {
            "alias": alias,
            "model": model,
            "exit_code": proc.returncode,
            "result": detail,
            "output_tail": combined[-400:],
        }
    )

print(json.dumps(results, indent=2))
PY
}

quarantine_account() {
  require_args "$@"
  local alias="$1"
  local hours="${2:-12}"
  docker exec -i fleet-controller python3 - "$alias" "$hours" <<'PY'
import datetime as dt
import sqlite3
import sys

alias = sys.argv[1]
hours = float(sys.argv[2])
until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)
db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.execute(
    "UPDATE accounts SET backoff_until=?, last_error=?, updated_at=? WHERE alias=?",
    (
        until.isoformat().replace("+00:00", "Z"),
        "quarantined: current auth rejects all tested Codex models",
        dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        alias,
    ),
)
db.commit()
print(f"{alias} quarantined until {until.isoformat().replace('+00:00', 'Z')}")
PY
}

set_usage_limit_probe_backoff() {
  require_args "$@"
  local alias="$1"
  local probe_json="$2"
  docker exec -i fleet-controller python3 - "$alias" "$probe_json" <<'PY'
import datetime as dt
import json
import re
import sqlite3
import sys

alias = sys.argv[1]
rows = json.loads(sys.argv[2])
tails = [str(row.get("output_tail") or "") for row in rows]
raw = "\n".join(tails)
now = dt.datetime.now(dt.timezone.utc)
probe_until = now + dt.timedelta(hours=2)
reset_at = None
match = re.search(r"try again at\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}\s+\d{1,2}:\d{2}\s+[AP]M)", raw, re.IGNORECASE)
if match:
    candidate = re.sub(r"(\d)(st|nd|rd|th)", r"\1", match.group(1), flags=re.IGNORECASE).strip()
    for fmt in ("%b %d, %Y %I:%M %p", "%B %d, %Y %I:%M %p"):
        try:
            reset_at = dt.datetime.strptime(candidate, fmt).replace(tzinfo=dt.timezone.utc)
            break
        except ValueError:
            continue
if reset_at and reset_at < probe_until:
    probe_until = reset_at
message = (
    f"usage-limited; recheck at {probe_until.isoformat().replace('+00:00', 'Z')} "
    f"(provider reset {reset_at.isoformat().replace('+00:00', 'Z')})"
    if reset_at and reset_at > probe_until
    else f"usage-limited until {(reset_at or probe_until).isoformat().replace('+00:00', 'Z')}"
    if reset_at
    else f"usage-limited; recheck at {probe_until.isoformat().replace('+00:00', 'Z')}"
)
db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.execute(
    "UPDATE accounts SET backoff_until=?, last_error=?, updated_at=? WHERE alias=?",
    (
        probe_until.isoformat().replace("+00:00", "Z"),
        message,
        now.isoformat().replace("+00:00", "Z"),
        alias,
    ),
)
db.commit()
print(message)
PY
}

repair_bridge_accounts() {
  local probe_json
  local probe_result
  for alias in acct-chatgpt-core acct-chatgpt-b; do
    echo "== validate $alias =="
    admin_post "/api/admin/accounts/$alias/validate"
    echo "== probe $alias =="
    probe_json="$(probe_account_models "$alias" gpt-5.3-codex gpt-5-mini gpt-5-nano)"
    printf '%s\n' "$probe_json"
    probe_result="$(
      printf '%s\n' "$probe_json" | python3 -c '
import json
import sys
rows = json.load(sys.stdin)
usable = any(row.get("result") in {"ok", "rate_limited"} for row in rows)
usage_limited = any(
    row.get("result") == "failed" and "usage limit" in str(row.get("output_tail") or "").lower()
    for row in rows
)
if usable:
    print("usable")
elif usage_limited:
    print("usage_limited")
else:
    print("unsupported")
'
    )"
    if [ "$probe_result" = "usable" ]; then
      echo "== clear backoff $alias =="
      admin_post "/api/admin/accounts/$alias/clear-backoff"
    elif [ "$probe_result" = "usage_limited" ]; then
      echo "== set quota reprobe backoff $alias =="
      set_usage_limit_probe_backoff "$alias" "$probe_json"
    else
      echo "== skip clear-backoff $alias (no Codex-compatible model accepted) =="
    fi
  done
  operator_summary
}

repair_codex_floor() {
  echo "== validate and normalize named bridge accounts =="
  repair_bridge_accounts

  echo "== relaunch stranded local-review lanes =="
  for project_id in ui design; do
    admin_post "/api/admin/projects/${project_id}/review/request"
  done

  echo "== retry transient coding lane failures =="
  for project_id in mobile hub; do
    admin_post "/api/admin/projects/${project_id}/retry"
  done
}

run_project_now() {
  require_args "$@"
  local project
  for project in "$@"; do
    echo "== run now $project =="
    admin_post "/api/admin/projects/$project/run-now"
  done
}

run_group_audit() {
  require_args "$@"
  local group_id
  for group_id in "$@"; do
    echo "== audit $group_id =="
    admin_post "/api/admin/groups/$group_id/audit-now"
  done
}

approve_audit_task() {
  require_args "$@"
  local task_id
  for task_id in "$@"; do
    echo "== approve audit task $task_id =="
    admin_post "/api/admin/audit/tasks/$task_id/approve"
  done
}

heal_group_now() {
  require_args "$@"
  local group
  for group in "$@"; do
    echo "== heal group $group =="
    admin_post "/api/admin/groups/$group/heal-now"
  done
}

commit_and_push_if_needed() {
  local repo="$1"
  local message="$2"
  local branch
  branch="$(git -C "$repo" branch --show-current)"
  if [[ -z "$branch" ]]; then
    echo "Unable to resolve branch for $repo" >&2
    exit 1
  fi
  if git -C "$repo" diff --cached --quiet; then
    echo "== no staged changes in $repo =="
    return 0
  fi
  git -C "$repo" commit -m "$message"
  git -C "$repo" push -u origin "$branch"
}

publish_repo_all() {
  local repo="$1"
  shift || true
  local message="$*"
  require_args "$repo" "$message"
  local branch
  branch="$(git -C "$repo" branch --show-current)"
  if [[ -z "$branch" ]]; then
    echo "Unable to resolve branch for $repo" >&2
    exit 1
  fi
  git -C "$repo" add -A
  if ! git -C "$repo" diff --cached --quiet; then
    git -C "$repo" commit -m "$message"
  else
    echo "== no staged changes in $repo =="
  fi
  git -C "$repo" push -u origin "$branch"
}

publish_repo_all_to() {
  local repo="$1"
  local remote="$2"
  shift 2 || true
  local message="$*"
  require_args "$repo" "$remote" "$message"
  local branch
  branch="$(git -C "$repo" branch --show-current)"
  if [[ -z "$branch" ]]; then
    echo "Unable to resolve branch for $repo" >&2
    exit 1
  fi
  git -C "$repo" add -A
  if ! git -C "$repo" diff --cached --quiet; then
    git -C "$repo" commit -m "$message"
  else
    echo "== no staged changes in $repo =="
  fi
  if [[ "$remote" == git@* || "$remote" == ssh://* ]]; then
    GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -o StrictHostKeyChecking=accept-new}" \
      git -C "$repo" push -u "$remote" "$branch:$branch"
  else
    git -C "$repo" push -u "$remote" "$branch:$branch"
  fi
}

publish_repo_files() {
  local repo="$1"
  shift || true
  require_args "$repo" "$@"
  local args=("$@")
  local sep_index=-1
  local i
  for i in "${!args[@]}"; do
    if [[ "${args[$i]}" == "--" ]]; then
      sep_index="$i"
      break
    fi
  done
  if [[ "$sep_index" -lt 1 ]]; then
    echo "usage: publish-repo-files <repo> <commit message...> -- <file> [file...]" >&2
    exit 1
  fi
  local message_parts=("${args[@]:0:$sep_index}")
  local file_parts=("${args[@]:$((sep_index + 1))}")
  if [[ "${#file_parts[@]}" -eq 0 ]]; then
    echo "publish-repo-files requires at least one file after --" >&2
    exit 1
  fi
  local message="${message_parts[*]}"
  local branch
  branch="$(git -C "$repo" branch --show-current)"
  if [[ -z "$branch" ]]; then
    echo "Unable to resolve branch for $repo" >&2
    exit 1
  fi
  git -C "$repo" add -- "${file_parts[@]}"
  if ! git -C "$repo" diff --cached --quiet; then
    git -C "$repo" commit -m "$message"
  else
    echo "== no staged changes in $repo for requested files =="
  fi
  git -C "$repo" push -u origin "$branch"
}

publish_repo_force() {
  local repo="$1"
  shift || true
  local message="$*"
  require_args "$repo" "$message"
  local branch
  branch="$(git -C "$repo" branch --show-current)"
  if [[ -z "$branch" ]]; then
    echo "Unable to resolve branch for $repo" >&2
    exit 1
  fi
  git -C "$repo" add -A
  if ! git -C "$repo" diff --cached --quiet; then
    git -C "$repo" commit -m "$message"
  else
    echo "== no staged changes in $repo =="
  fi
  git -C "$repo" push -u --force origin "$branch"
}

publish_latest_pass() {
  echo "== stage fleet =="
  git -C /docker/fleet add \
    admin/app.py \
    controller/app.py \
    scripts/deploy.sh \
    scripts/verify_chummer_design_authority.py \
    scripts/publish_chummer_design_authority.py \
    scripts/sync_ea_chummer_provider_envs.py \
    scripts/chummer_public_design_ltd_audit_inject.py \
    scripts/ea_provider_registry_feedback_inject.py \
    scripts/fleet_design_progress_feedback_inject.py \
    feedback/2026-03-11-fleet-design-progress-semantics.md
  commit_and_push_if_needed /docker/fleet "fleet: publish provider sync and feedback tooling"

  echo "== stage EA =="
  git -C /docker/EA add \
    .env.example \
    .env.local.example \
    docker-compose.memory.yml \
    feedback/2026-03-11-ea-provider-registry-and-unmixr.md
  commit_and_push_if_needed /docker/EA "docs(ea): add provider registry and unmixr scaffolding"

  echo "== stage chummer-design =="
  git -C /docker/chummercomplete/chummer-design add \
    feedback/2026-03-11-chummer-public-design-and-ltd-audit.md
  commit_and_push_if_needed /docker/chummercomplete/chummer-design "feedback(design): add public design and ltd audit"

  echo "== stage chummer5a =="
  git -C /docker/chummer5a add \
    .env.example \
    .gitignore \
    docker-compose.yml \
    Chummer.Blazor.Desktop/Program.cs \
    Chummer.Blazor.Desktop/DesktopWorkbenchCoachApiClient.cs \
    Chummer.Portal/PortalPageBuilder.cs \
    Docker/Downloads/releases.json \
    Docker/Downloads/files/chummer-6-avalonia-osx-arm64-20260310-210534.zip \
    Docker/Downloads/files/chummer-6-avalonia-win-x64-20260310-210534.zip \
    Docker/Downloads/files/chummer-6-blazor-osx-arm64-20260310-210534.zip \
    Docker/Downloads/files/chummer-6-blazor-win-x64-20260310-210534.zip
  commit_and_push_if_needed /docker/chummer5a "chore(chummer): publish desktop downloads and provider envs"
}

patch_chummer_desktop_coach_client() {
  local source_root="$1"
  local desktop_program="$source_root/Chummer.Blazor.Desktop/Program.cs"
  local desktop_client="$source_root/Chummer.Blazor.Desktop/DesktopWorkbenchCoachApiClient.cs"

  if [[ ! -f "$desktop_program" ]]; then
    echo "desktop startup file not found: $desktop_program" >&2
    exit 1
  fi

  if ! grep -q "using Chummer.Blazor;" "$desktop_program"; then
    python3 - "$desktop_program" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
needle = "using Chummer.Presentation;\n"
replacement = "using Chummer.Blazor;\nusing Chummer.Presentation;\n"
if needle not in text:
    raise SystemExit(f"needle not found in {path}")
path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
PY
  fi

  if ! grep -q "DesktopWorkbenchCoachApiClient" "$desktop_program"; then
    python3 - "$desktop_program" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
needle = '        appBuilder.Services.AddSingleton<Chummer.Blazor.CharacterOverviewStateBridge>();\n'
replacement = needle + '        appBuilder.Services.AddSingleton<IWorkbenchCoachApiClient, DesktopWorkbenchCoachApiClient>();\n'
if needle not in text:
    raise SystemExit(f"needle not found in {path}")
path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
PY
  fi

  if [[ ! -f "$desktop_client" ]]; then
    cat >"$desktop_client" <<'EOF'
using Chummer.Blazor;
using Chummer.Contracts.AI;

namespace Chummer.Blazor.Desktop;

internal sealed class DesktopWorkbenchCoachApiClient : IWorkbenchCoachApiClient
{
    private static readonly AiNotImplementedReceipt Receipt = new(
        Error: "coach_sidecar_unavailable",
        Operation: "workbench_coach_desktop",
        Message: "Coach sidecar is not configured in the desktop runtime yet.",
        RouteType: AiRouteTypes.Coach);

    public Task<WorkbenchCoachApiCallResult<AiGatewayStatusProjection>> GetStatusAsync(CancellationToken ct = default)
        => Task.FromResult(WorkbenchCoachApiCallResult<AiGatewayStatusProjection>.FromNotImplemented(501, Receipt));

    public Task<WorkbenchCoachApiCallResult<AiProviderHealthProjection[]>> ListProviderHealthAsync(string? routeType = null, CancellationToken ct = default)
        => Task.FromResult(WorkbenchCoachApiCallResult<AiProviderHealthProjection[]>.FromNotImplemented(501, Receipt with { RouteType = routeType ?? AiRouteTypes.Coach }));

    public Task<WorkbenchCoachApiCallResult<AiConversationAuditCatalogPage>> ListConversationAuditsAsync(
        string routeType,
        string? runtimeFingerprint = null,
        int maxCount = 3,
        CancellationToken ct = default)
        => Task.FromResult(WorkbenchCoachApiCallResult<AiConversationAuditCatalogPage>.FromNotImplemented(501, Receipt with { RouteType = routeType ?? AiRouteTypes.Coach }));
}
EOF
  fi
}

build_chummer_windows_downloads() {
  local repo_root="${CHUMMER_PORTAL_REPO_ROOT:-/docker/chummer5a}"
  local build_root="${CHUMMER_DESKTOP_BUILD_ROOT:-/tmp/chummer5a-desktop-build}"
  local source_root="${CHUMMER_DESKTOP_SOURCE_ROOT:-$build_root/src}"
  local rids_csv="${CHUMMER_DESKTOP_RIDS:-${CHUMMER_DESKTOP_RID:-win-x64}}"
  local apps_csv="${CHUMMER_DESKTOP_APPS:-blazor-desktop}"
  local dist_dir="${CHUMMER_DESKTOP_DIST_DIR:-$build_root/dist}"
  local deploy_dir="${CHUMMER_DOWNLOADS_DEPLOY_DIR:-$repo_root/Docker/Downloads}"
  local live_verify_target="${CHUMMER_DOWNLOADS_VERIFY_URL:-http://127.0.0.1:8091}"
  local release_stamp="${CHUMMER_RELEASE_STAMP:-$(date -u +%Y%m%d-%H%M%S)}"
  local release_version="${CHUMMER_RELEASE_VERSION:-Chummer 6 local ${release_stamp}}"
  local release_channel="${CHUMMER_RELEASE_CHANNEL:-preview}"
  local release_published_at
  release_published_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  if [[ ! -d "$repo_root" ]]; then
    echo "Chummer repo root not found: $repo_root" >&2
    exit 1
  fi

  rm -rf "$build_root"
  mkdir -p "$source_root" "$dist_dir/files" "$build_root/dotnet-home" "$build_root/nuget-packages"
  rm -f "$dist_dir/files"/chummer-6-*.zip "$dist_dir/files"/chummer-6-*.tar.gz "$dist_dir/releases.json"

  echo "== stage writable source tree =="
  rsync -a --delete \
    --exclude ".git/" \
    --exclude ".env" \
    --exclude ".tmp/" \
    --exclude "Chummer.Tests/" \
    "$repo_root"/ "$source_root"/
  find "$source_root" -type d \( -name .git -o -name bin -o -name obj -o -name dist -o -name out \) -prune -exec rm -rf {} +

  echo "== inject desktop coach fallback =="
  patch_chummer_desktop_coach_client "$source_root"

  pushd "$source_root" >/dev/null
  IFS=',' read -r -a requested_rids <<<"$rids_csv"
  IFS=',' read -r -a requested_apps <<<"$apps_csv"
  for rid in "${requested_rids[@]}"; do
    rid="$(echo "$rid" | xargs)"
    [[ -n "$rid" ]] || continue

    for app in "${requested_apps[@]}"; do
      app="$(echo "$app" | xargs)"
      [[ -n "$app" ]] || continue

      local project=""
      local archive_slug=""
      case "$app" in
        avalonia)
          project="Chummer.Avalonia/Chummer.Avalonia.csproj"
          archive_slug="avalonia"
          ;;
        blazor-desktop)
          project="Chummer.Blazor.Desktop/Chummer.Blazor.Desktop.csproj"
          archive_slug="blazor"
          ;;
        *)
          echo "Unsupported desktop app '$app'. Supported values: avalonia, blazor-desktop" >&2
          exit 1
          ;;
      esac

      local out_dir="$build_root/output/$archive_slug/$rid/publish"
      local archive_path="$dist_dir/files/chummer-6-$archive_slug-$rid-$release_stamp.zip"
      rm -rf "$(dirname "$out_dir")"

      echo "== restore $project =="
      DOTNET_CLI_HOME="$build_root/dotnet-home" \
      NUGET_PACKAGES="$build_root/nuget-packages" \
      dotnet restore "$project" \
        -p:RestorePackagesPath="$build_root/nuget-packages"

      echo "== publish $project ($rid) =="
      DOTNET_CLI_HOME="$build_root/dotnet-home" \
      NUGET_PACKAGES="$build_root/nuget-packages" \
      dotnet publish "$project" \
        -c Release \
        -r "$rid" \
        --self-contained true \
        -p:PublishSingleFile=true \
        -p:PublishTrimmed=false \
        -p:IncludeNativeLibrariesForSelfExtract=true \
        -p:RestorePackagesPath="$build_root/nuget-packages" \
        -o "$out_dir"

      echo "== package $archive_path =="
      python3 - "$archive_path" "$out_dir" <<'PY'
import os
import sys
import zipfile
from pathlib import Path

archive_path = Path(sys.argv[1])
source_dir = Path(sys.argv[2])
archive_path.parent.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(source_dir.rglob("*")):
        if path.is_file():
            zf.write(path, path.relative_to(source_dir))
print(f"wrote {archive_path}")
PY
    done
  done
  popd >/dev/null

  echo "== generate local releases manifest =="
  python3 - "$dist_dir/files" "$dist_dir/releases.json" "$release_version" "$release_channel" "$release_published_at" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path

downloads_dir = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
version = sys.argv[3]
channel = sys.argv[4]
published_at = sys.argv[5]

pattern = re.compile(r"^chummer-6-(?P<app>avalonia|blazor)-(?P<rid>.+)-(?P<stamp>\d{8}-\d{6})\.zip$")
app_labels = {
    "avalonia": "Chummer 6 Avalonia",
    "blazor": "Chummer 6 Blazor",
}
platform_names = {
    "win-x64": "Windows x64",
    "win-arm64": "Windows ARM64",
    "linux-x64": "Linux x64",
    "linux-arm64": "Linux ARM64",
    "osx-arm64": "macOS ARM64",
    "osx-x64": "macOS x64",
}
downloads = []

for artifact in sorted(downloads_dir.iterdir()):
    if not artifact.is_file():
        continue
    match = pattern.match(artifact.name)
    if not match:
        continue
    app = match.group("app")
    rid = match.group("rid")
    stamp = match.group("stamp")
    downloads.append(
        {
            "id": f"{app}-{rid}-{stamp}",
            "platform": f"{app_labels.get(app, app)} {platform_names.get(rid, rid)}",
            "url": f"/downloads/files/{artifact.name}",
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "sizeBytes": artifact.stat().st_size,
        }
    )

manifest = {
    "version": version if downloads else "unpublished",
    "channel": channel,
    "publishedAt": published_at,
    "downloads": downloads,
}
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(f"wrote {manifest_path} with {len(downloads)} download entry(ies)")
PY

  echo "== publish into portal downloads directory =="
  mkdir -p "$deploy_dir/files"
  find "$deploy_dir/files" -maxdepth 1 -type f \( -name "chummer-6-*.zip" -o -name "chummer-6-*.tar.gz" \) -delete
  cp "$dist_dir"/releases.json "$deploy_dir"/releases.json
  find "$dist_dir/files" -maxdepth 1 -type f \( -name "chummer-6-*.zip" -o -name "chummer-6-*.tar.gz" \) -exec cp {} "$deploy_dir/files/" \;

  echo "== verify deployed downloads manifest =="
  CHUMMER_PORTAL_DOWNLOADS_REQUIRE_PUBLISHED_VERSION=true \
  CHUMMER_PORTAL_DOWNLOADS_VERIFY_LINKS=false \
  bash "$repo_root/scripts/verify-releases-manifest.sh" "$deploy_dir/releases.json"

  echo "== verify live portal downloads =="
  CHUMMER_PORTAL_DOWNLOADS_REQUIRE_PUBLISHED_VERSION=true \
  CHUMMER_PORTAL_DOWNLOADS_VERIFY_LINKS=true \
  bash "$repo_root/scripts/verify-releases-manifest.sh" "$live_verify_target"
}

inspect_chummer_mobile() {
  local repo_root="${CHUMMER_PORTAL_REPO_ROOT:-/docker/chummer5a}"
  python3 - "$repo_root" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
mobile_hits = []
tfm_hits = []
publish_profiles = []
manifest_hits = []
mobile_related_files = []

tfm_pattern = re.compile(r"<TargetFrameworks?>(.*?)</TargetFrameworks?>", re.IGNORECASE | re.DOTALL)
keywords = ("android", "ios", "maccatalyst", "mobile", "maui", "apk", "aab", "ipa")

for path in root.rglob("*.csproj"):
    text = path.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    if any(keyword in lowered or keyword in str(path).lower() for keyword in keywords):
        mobile_hits.append(str(path.relative_to(root)))
    for match in tfm_pattern.finditer(text):
        value = " ".join(match.group(1).split())
        if any(token in value.lower() for token in ("android", "ios", "maccatalyst")):
            tfm_hits.append({"project": str(path.relative_to(root)), "tfm": value})

for path in root.rglob("*.pubxml"):
    publish_profiles.append(str(path.relative_to(root)))

for name in ("AndroidManifest.xml", "Info.plist", "Entitlements.plist"):
    manifest_hits.extend(str(path.relative_to(root)) for path in root.rglob(name))

for path in root.rglob("*"):
    if path.is_file() and any(keyword in str(path).lower() for keyword in ("android", "ios", "apk", "aab", "ipa", "mobile")):
        mobile_related_files.append(str(path.relative_to(root)))

result = {
    "repo_root": str(root),
    "mobile_project_candidates": sorted(set(mobile_hits)),
    "mobile_target_frameworks": tfm_hits,
    "publish_profiles": sorted(set(publish_profiles)),
    "mobile_manifests": sorted(set(manifest_hits)),
    "mobile_related_files": sorted(set(mobile_related_files))[:200],
}
print(json.dumps(result, indent=2))
PY
}

inspect_chummer_play_mobile() {
  local repo_root="${CHUMMER_PLAY_REPO_ROOT:-/docker/chummercomplete/chummer-play}"
  python3 - "$repo_root" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
if not root.exists():
    raise SystemExit(f"missing repo: {root}")

tfm_pattern = re.compile(r"<TargetFrameworks?>(.*?)</TargetFrameworks?>", re.IGNORECASE | re.DOTALL)
keywords = ("android", "ios", "maccatalyst", "mobile", "maui", "apk", "aab", "ipa", "pwa", "serviceworker", "manifest.webmanifest")

mobile_projects = []
target_frameworks = []
publish_profiles = []
web_manifests = []
service_workers = []

for path in root.rglob("*.csproj"):
    text = path.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    if any(keyword in lowered or keyword in str(path).lower() for keyword in keywords):
      mobile_projects.append(str(path.relative_to(root)))
    for match in tfm_pattern.finditer(text):
      value = " ".join(match.group(1).split())
      if any(token in value.lower() for token in ("android", "ios", "maccatalyst")):
        target_frameworks.append({"project": str(path.relative_to(root)), "tfm": value})

for path in root.rglob("*.pubxml"):
    publish_profiles.append(str(path.relative_to(root)))

for name in ("manifest.webmanifest", "AndroidManifest.xml", "Info.plist", "Entitlements.plist"):
    web_manifests.extend(str(path.relative_to(root)) for path in root.rglob(name))

for path in root.rglob("*service*worker*"):
    if path.is_file():
        service_workers.append(str(path.relative_to(root)))

print(json.dumps({
    "repo_root": str(root),
    "mobile_projects": sorted(set(mobile_projects)),
    "native_mobile_target_frameworks": target_frameworks,
    "publish_profiles": sorted(set(publish_profiles)),
    "manifests": sorted(set(web_manifests)),
    "service_workers": sorted(set(service_workers)),
}, indent=2))
PY
}

service_logs() {
  require_args "$@"
  local service="$1"
  local tail="${2:-120}"
  docker compose logs --tail="$tail" "$service"
}

service_ps() {
  docker compose ps
}

run_log() {
  require_args "$@"
  local run_id="$1"
  docker exec -i fleet-controller python3 - "$run_id" <<'PY'
import pathlib
import sqlite3
import sys

run_id = int(sys.argv[1])
db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.row_factory = sqlite3.Row
row = db.execute(
    "select id, project_id, status, account_alias, log_path, error_class, error_message from runs where id = ?",
    (run_id,),
).fetchone()
if not row:
    raise SystemExit(f"missing run {run_id}")
print(f"run_id={row['id']}")
print(f"project_id={row['project_id']}")
print(f"status={row['status']}")
print(f"account_alias={row['account_alias']}")
print(f"error_class={row['error_class']}")
print(f"error_message={row['error_message']}")
log_path = pathlib.Path(str(row["log_path"] or "").strip())
print(f"log_path={log_path}")
if log_path.exists():
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    print("--- log tail ---")
    for line in lines[-120:]:
        print(line)
else:
    print("log file missing")
PY
}

patch_chummer_portal_downloads_ui() {
  local repo_root="${CHUMMER_PORTAL_REPO_ROOT:-/docker/chummer5a}"
  local target="$repo_root/Chummer.Portal/PortalPageBuilder.cs"
  if [[ ! -f "$target" ]]; then
    echo "Portal page builder not found: $target" >&2
    exit 1
  fi
  python3 "$repo_root/../fleet/scripts/chummer_portal_downloads_ui_patch.py" "$target"
  echo "== verify patched portal page builder =="
  rg -n "download-platform|download-type|All platforms|All types" "$target"
}

rebuild_chummer_portal() {
  local repo_root="${CHUMMER_PORTAL_REPO_ROOT:-/docker/chummer5a}"
  local compose_file="$repo_root/docker-compose.yml"
  if [[ ! -f "$compose_file" ]]; then
    echo "Chummer portal compose file not found: $compose_file" >&2
    exit 1
  fi

  echo "== rebuild chummer-portal =="
  docker compose -f "$compose_file" build chummer-portal
  echo "== restart chummer-portal =="
  docker compose -f "$compose_file" up -d chummer-portal
  verify_chummer_portal_downloads_ui
}

verify_chummer_portal_downloads_ui() {
  echo "== verify live downloads html =="
  python3 - <<'PY'
import time
import sys
import urllib.request

needles = ["download-platform", "download-type", "All platforms", "All types"]
last_error = None
for _attempt in range(12):
    try:
        html = urllib.request.urlopen("http://127.0.0.1:8091/downloads/", timeout=20).read().decode("utf-8", errors="replace")
        missing = [needle for needle in needles if needle not in html]
        if missing:
            raise RuntimeError(f"missing downloads UI markers: {', '.join(missing)}")
        print("verified downloads UI markers:", ", ".join(needles))
        raise SystemExit(0)
    except Exception as exc:
        last_error = exc
        time.sleep(2)
raise SystemExit(str(last_error) if last_error else "downloads UI verification failed")
PY
}

smoke_fleet_dashboard() {
  local compose_file="${CHUMMER_PORTAL_REPO_ROOT:-/docker/chummer5a}/docker-compose.yml"
  local dashboard_url="${FLEET_DASHBOARD_SMOKE_URL:-http://fleet-dashboard:8090}"
  local dashboard_network="${FLEET_DASHBOARD_SMOKE_NETWORK:-codex-fleet-net}"
  local password
  password="$(operator_password)"

  if [[ ! -f "$compose_file" ]]; then
    echo "Chummer compose file not found: $compose_file" >&2
    exit 1
  fi

  echo "== build playwright smoke image =="
  docker compose -f "$compose_file" --profile test --profile portal build chummer-playwright-portal >/dev/null

  FLEET_DASHBOARD_SMOKE_URL="$dashboard_url" \
  FLEET_DASHBOARD_SMOKE_NETWORK="$dashboard_network" \
  FLEET_OPERATOR_PASSWORD="$password" \
  docker run --rm -i \
    --network "$dashboard_network" \
    -e FLEET_DASHBOARD_SMOKE_URL \
    -e FLEET_OPERATOR_PASSWORD \
    chummer-playwright:local node - <<'NODE'
'use strict';

const { chromium } = require('playwright');

const baseUrl = String(process.env.FLEET_DASHBOARD_SMOKE_URL || 'https://fleet.girschele.com').replace(/\/+$/, '');
const password = String(process.env.FLEET_OPERATOR_PASSWORD || '');

if (!password) {
  throw new Error('FLEET_OPERATOR_PASSWORD is required for smoke_fleet_dashboard');
}

const errors = [];
const requestLog = [];
let cockpitStatusSeen = false;
let cockpitStatusOk = false;
let cockpitPayloadSummary = null;

const failOnTextPatterns = [
  /Bridge script failed to load/i,
  /Bridge load failed/i,
  /Bridge assets did not finish loading/i,
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ ignoreHTTPSErrors: true });

  page.on('console', (msg) => {
    const type = msg.type();
    const text = msg.text();
    console.log(`console:${type}: ${text}`);
    if (type === 'error') {
      errors.push(`console error: ${text}`);
    }
  });
  page.on('pageerror', (error) => {
    const message = error && (error.stack || error.message) ? (error.stack || error.message) : String(error);
    console.log(`pageerror: ${message}`);
    errors.push(`pageerror: ${message}`);
  });
  page.on('requestfailed', (request) => {
    const message = request.failure() && request.failure().errorText ? request.failure().errorText : 'request failed';
    const url = request.url();
    console.log(`requestfailed: ${url} :: ${message}`);
    requestLog.push({ url, failure: message });
    errors.push(`requestfailed: ${url} :: ${message}`);
  });
  page.on('response', async (response) => {
    const url = response.url();
    if (!url.includes('/api/cockpit/status')) {
      return;
    }
    cockpitStatusSeen = true;
    console.log(`cockpit-response: ${response.status()} ${url}`);
    if (response.ok()) {
      cockpitStatusOk = true;
      try {
        const payload = await response.json();
        cockpitPayloadSummary = payload && payload.cockpit && payload.cockpit.summary ? payload.cockpit.summary : null;
      } catch (error) {
        errors.push(`cockpit json parse failed: ${error instanceof Error ? error.message : String(error)}`);
      }
    } else {
      errors.push(`cockpit status not ok: ${response.status()}`);
    }
  });

  try {
    await page.goto(`${baseUrl}/admin/login?next=%2Fdashboard%2F`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.fill('#password', password);
    await Promise.all([
      page.waitForURL((url) => url.pathname === '/dashboard/' || url.pathname === '/dashboard', { timeout: 30000 }),
      page.locator('button[type="submit"]').click(),
    ]);

    await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
    await page.waitForFunction(() => window.__fleetBridgeReady === true, null, { timeout: 30000 });

    const recommendedAction = (await page.locator('#recommended-action').textContent()) || '';
    const postureState = (await page.locator('#posture-state').textContent()) || '';
    const operatorCards = await page.locator('#operator-grid .operator-card, #operator-grid .empty').count();

    console.log(`recommended-action: ${recommendedAction}`);
    console.log(`posture-state: ${postureState}`);
    console.log(`operator-cards: ${operatorCards}`);
    if (cockpitPayloadSummary) {
      console.log(`cockpit-summary: ${JSON.stringify(cockpitPayloadSummary)}`);
    }

    if (!cockpitStatusSeen) {
      errors.push('cockpit status was never requested');
    }
    if (!cockpitStatusOk) {
      errors.push('cockpit status never returned 200');
    }
    if (postureState.trim() === '...') {
      errors.push('posture state never hydrated');
    }
    if (operatorCards < 1) {
      errors.push('operator cards did not render');
    }
    if (failOnTextPatterns.some((pattern) => pattern.test(recommendedAction))) {
      errors.push(`dashboard error banner still present: ${recommendedAction}`);
    }
    if (requestLog.some((entry) => /bridge\.(js|css)/.test(entry.url))) {
      errors.push('bridge asset request failed');
    }

    if (errors.length) {
      throw new Error(errors.join('\n'));
    }

    console.log('fleet dashboard smoke completed');
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : error);
  process.exit(1);
});
NODE
}

probe_public_dashboard() {
  local base_url="${FLEET_PUBLIC_DASHBOARD_URL:-https://fleet.girschele.com}"
  python3 - "$base_url" <<'PY'
import json
import ssl
import sys
import urllib.error
import urllib.request

base = sys.argv[1].rstrip("/")
targets = [
    ("dashboard", f"{base}/dashboard/"),
    ("login", f"{base}/admin/login?next=%2Fdashboard%2F"),
]

context = ssl.create_default_context()
results = []
for label, url in targets:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Accept": "*/*" if label != "login" else "text/html,application/xhtml+xml",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20, context=context) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            results.append(
                {
                    "target": label,
                    "url": url,
                    "status": response.status,
                    "content_type": response.headers.get("Content-Type"),
                    "cache_control": response.headers.get("Cache-Control"),
                    "edge_protected": False,
                    "bridge_inline": "__fleetBridgeReady" in body,
                    "dashboard_shell": "Captain's Bridge" in body,
                    "preview": " ".join(body.split())[:200],
                }
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        results.append(
            {
                "target": label,
                "url": url,
                "status": exc.code,
                "content_type": exc.headers.get("Content-Type"),
                "cache_control": exc.headers.get("Cache-Control"),
                "edge_protected": exc.code in {401, 403},
                "bridge_inline": "__fleetBridgeReady" in body,
                "dashboard_shell": "Captain's Bridge" in body,
                "preview": " ".join(body.split())[:200],
            }
        )
    except Exception as exc:  # noqa: BLE001
        results.append(
            {
                "target": label,
                "url": url,
                "error": str(exc),
            }
        )

print(json.dumps(results, indent=2))
PY
}

inline_fleet_dashboard_assets() {
  python3 /docker/fleet/scripts/inline_fleet_dashboard_assets.py
}

patch_chummer_desktop_source() {
  local repo_root="${CHUMMER_PORTAL_REPO_ROOT:-/docker/chummer5a}"
  local patch_root="${CHUMMER_DESKTOP_SOURCE_PATCH_ROOT:-/tmp/chummer-desktop-source-patch}"

  if [[ ! -d "$repo_root" ]]; then
    echo "Chummer repo root not found: $repo_root" >&2
    exit 1
  fi

  echo "== patch desktop coach fallback in source repo =="
  rm -rf "$patch_root"
  mkdir -p "$patch_root/Chummer.Blazor.Desktop"
  cp "$repo_root/Chummer.Blazor.Desktop/Program.cs" "$patch_root/Chummer.Blazor.Desktop/Program.cs"
  patch_chummer_desktop_coach_client "$patch_root"
  docker run --rm \
    -v "$repo_root:/work" \
    -v "$patch_root:/patch:ro" \
    --entrypoint sh \
    nginx:1.27-alpine \
    -c 'cp /patch/Chummer.Blazor.Desktop/Program.cs /work/Chummer.Blazor.Desktop/Program.cs && chmod 0644 /work/Chummer.Blazor.Desktop/Program.cs && cp /patch/Chummer.Blazor.Desktop/DesktopWorkbenchCoachApiClient.cs /work/Chummer.Blazor.Desktop/DesktopWorkbenchCoachApiClient.cs && chmod 0644 /work/Chummer.Blazor.Desktop/DesktopWorkbenchCoachApiClient.cs'

  echo "== verify patched source files =="
  sed -n '1,80p' "$repo_root/Chummer.Blazor.Desktop/Program.cs"
  sed -n '1,120p' "$repo_root/Chummer.Blazor.Desktop/DesktopWorkbenchCoachApiClient.cs"
}

case "${1:-}" in
  admin-status)
    admin_status
    ;;
  chummer-portal)
    python3 - <<'PY'
import json
import urllib.error
import urllib.request

targets = [
    ("landing", "http://127.0.0.1:8091/"),
    ("api_health", "http://127.0.0.1:8091/api/health"),
    ("hub_health", "http://127.0.0.1:8091/hub/health"),
    ("session_health", "http://127.0.0.1:8091/session/health"),
    ("coach_health", "http://127.0.0.1:8091/coach/health"),
    ("avalonia_health", "http://127.0.0.1:8091/avalonia/health"),
    ("docs", "http://127.0.0.1:8091/docs/"),
    ("downloads", "http://127.0.0.1:8091/downloads/"),
]

results = []
for name, url in targets:
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            body = response.read(240).decode("utf-8", errors="replace")
            results.append(
                {
                    "target": name,
                    "url": url,
                    "status": response.status,
                    "content_type": response.headers.get("Content-Type"),
                    "preview": " ".join(body.split())[:160],
                }
            )
    except urllib.error.HTTPError as exc:
        body = exc.read(240).decode("utf-8", errors="replace")
        results.append(
            {
                "target": name,
                "url": url,
                "status": exc.code,
                "content_type": exc.headers.get("Content-Type"),
                "preview": " ".join(body.split())[:160],
            }
        )
    except Exception as exc:  # noqa: BLE001
        results.append(
            {
                "target": name,
                "url": url,
                "error": str(exc),
            }
        )

print(json.dumps(results, indent=2))
PY
    ;;
  build-chummer-windows-downloads)
    build_chummer_windows_downloads
    ;;
  build-chummer-desktop-downloads)
    CHUMMER_DESKTOP_RIDS="win-x64,osx-arm64" CHUMMER_DESKTOP_APPS="avalonia,blazor-desktop" build_chummer_windows_downloads
    ;;
  build-chummer-desktop-windows-downloads)
    CHUMMER_DESKTOP_APPS="avalonia,blazor-desktop" build_chummer_windows_downloads
    ;;
  build-chummer-avalonia-windows-downloads)
    CHUMMER_DESKTOP_APPS="avalonia" build_chummer_windows_downloads
    ;;
  build-chummer-desktop-macos-arm64-downloads)
    CHUMMER_DESKTOP_RIDS="osx-arm64" CHUMMER_DESKTOP_APPS="avalonia,blazor-desktop" build_chummer_windows_downloads
    ;;
  build-chummer-avalonia-macos-arm64-downloads)
    CHUMMER_DESKTOP_RIDS="osx-arm64" CHUMMER_DESKTOP_APPS="avalonia" build_chummer_windows_downloads
    ;;
  inspect-chummer-mobile)
    inspect_chummer_mobile
    ;;
  inspect-chummer-play-mobile)
    inspect_chummer_play_mobile
    ;;
  patch-chummer-portal-downloads-ui)
    patch_chummer_portal_downloads_ui
    ;;
  verify-chummer-portal-downloads-ui)
    verify_chummer_portal_downloads_ui
    ;;
  rebuild-chummer-portal)
    rebuild_chummer_portal
    ;;
  patch-and-rebuild-chummer-portal-downloads-ui)
    patch_chummer_portal_downloads_ui
    rebuild_chummer_portal
    ;;
  patch-chummer-desktop-source)
    patch_chummer_desktop_source
    ;;
  patch-and-build-chummer-windows-downloads)
    patch_chummer_desktop_source
    build_chummer_windows_downloads
    ;;
  cockpit-summary)
    admin_status | python3 -c '
import json, sys
data = json.load(sys.stdin)
summary = data.get("summary", {})
cockpit = data.get("cockpit", {})
workers = cockpit.get("workers", [])
projects = data.get("projects", [])
print(json.dumps({
  "fleet_health": data.get("fleet_health"),
  "active_workers": summary.get("active_workers"),
  "open_incidents": summary.get("open_incidents"),
  "approvals_waiting": summary.get("approvals_waiting"),
  "workers": [
    {
      "project_id": worker.get("project_id") or worker.get("id"),
      "status": worker.get("status") or worker.get("phase"),
      "slice": worker.get("current_slice"),
    }
    for worker in workers
  ],
  "project_states": [
    {
      "project_id": project.get("project_id") or project.get("id"),
      "status": project.get("status") or project.get("runtime_status_internal"),
      "runtime_status": project.get("runtime_status"),
      "active_run_id": project.get("active_run_id"),
      "next_action": project.get("next_action"),
      "cooldown_until": project.get("cooldown_until"),
    }
    for project in projects
  ],
}, indent=2))
'
    ;;
  operator-summary)
    operator_summary
    ;;
  run-project-now)
    shift
    run_project_now "$@"
    ;;
  run-group-audit)
    shift
    run_group_audit "$@"
    ;;
  approve-audit-task)
    shift
    approve_audit_task "$@"
    ;;
  heal-group-now)
    shift
    heal_group_now "$@"
    ;;
  gateway-cockpit)
    docker exec fleet-dashboard wget --header="X-Fleet-Operator-Password: $(operator_password)" -qO- http://127.0.0.1:8090/api/cockpit/status | python3 -c '
import json, sys
data = json.load(sys.stdin)
cockpit = data.get("cockpit", {})
summary = cockpit.get("summary", {})
print(json.dumps({
  "fleet_health": summary.get("fleet_health"),
  "active_workers": summary.get("active_workers"),
  "open_incidents": summary.get("open_incidents"),
  "approvals_waiting": summary.get("approvals_waiting"),
  "worker_ids": [worker.get("project_id") for worker in (cockpit.get("workers") or [])],
}, indent=2))
'
    ;;
  probe-public-dashboard)
    probe_public_dashboard
    ;;
  inline-fleet-dashboard-assets)
    inline_fleet_dashboard_assets
    ;;
  repair-bridge-accounts)
    repair_bridge_accounts
    ;;
  repair-codex-floor)
    repair_codex_floor
    ;;
  smoke-fleet-dashboard)
    smoke_fleet_dashboard
    ;;
  gateway-root)
    docker exec fleet-dashboard wget -S -O /dev/null http://127.0.0.1:8090/
    ;;
  host-root)
    curl -sS -D - -o /dev/null http://127.0.0.1:18090/
    ;;
  dashboard-logs)
    docker compose logs --tail="${2:-80}" fleet-dashboard
    ;;
  service-logs)
    shift
    service_logs "$@"
    ;;
  service-ps)
    service_ps
    ;;
  project-status)
    shift
    require_args "$@"
    docker exec -i fleet-controller python3 - "$@" <<'PY'
import json
import sqlite3
import sys

db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.row_factory = sqlite3.Row
for project_id in sys.argv[1:]:
    row = db.execute(
        """
        select id as project_id, status, active_run_id, current_slice, cooldown_until,
               last_run_at, last_error, spider_tier, spider_model, spider_reason,
               queue_index, queue_json, updated_at
          from projects
         where id = ?
        """,
        (project_id,),
    ).fetchone()
    print(json.dumps(dict(row) if row else {"project_id": project_id, "missing": True}, indent=2))
PY
    ;;
  compile-status)
    shift
    require_args "$@"
    admin_status | python3 -c '
import json, sys
data = json.load(sys.stdin)
targets = set(sys.argv[1:])
rows = []
for project in data.get("projects", []):
    project_id = str(project.get("id") or "")
    if project_id in targets:
        rows.append({
            "project_id": project_id,
            "lifecycle": project.get("lifecycle"),
            "runtime_status": project.get("runtime_status"),
            "compile": project.get("compile"),
            "compile_health": project.get("compile_health"),
        })
print(json.dumps(rows, indent=2))
' "$@"
    ;;
  run-status)
    shift
    require_args "$@"
    docker exec -i fleet-controller python3 - "$@" <<'PY'
import json
import sqlite3
import sys

db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.row_factory = sqlite3.Row
for run_id in sys.argv[1:]:
    row = db.execute(
        """
        select id, project_id, status, started_at, finished_at,
               model, account_alias, slice_name, job_kind, error_class, error_message
          from runs
         where id = ?
        """,
        (run_id,),
    ).fetchone()
    print(json.dumps(dict(row) if row else {"id": run_id, "missing": True}, indent=2))
PY
    ;;
  run-log)
    shift
    run_log "$@"
    ;;
  recent-runs)
    shift
    require_args "$@"
    project_id="$1"
    limit="${2:-10}"
    docker exec -i fleet-controller python3 - "$project_id" "$limit" <<'PY'
import json
import sqlite3
import sys

project_id = sys.argv[1]
limit = int(sys.argv[2])
db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.row_factory = sqlite3.Row
rows = db.execute(
    """
    select id, project_id, status, started_at, finished_at, job_kind, slice_name,
           error_class, error_message, decision_reason
      from runs
     where project_id = ?
     order by id desc
     limit ?
    """,
    (project_id, limit),
).fetchall()
print(json.dumps([dict(row) for row in rows], indent=2))
PY
    ;;
  probe-account-models)
    shift
    probe_account_models "$@"
    ;;
  quarantine-account)
    shift
    quarantine_account "$@"
    ;;
  time-vienna)
    TZ=Europe/Vienna date '+%Y-%m-%d %H:%M:%S %Z'
    ;;
  verify-config)
    python3 - <<'PY'
import pathlib
import sys
import yaml

root = pathlib.Path("/docker/fleet/config")
paths = [root / "fleet.yaml", root / "accounts.yaml", root / "policies.yaml", root / "routing.yaml", root / "groups.yaml"]
projects_dir = root / "projects"
paths.extend(sorted(projects_dir.glob("*.yaml")))
for path in paths:
    with path.open("r", encoding="utf-8") as handle:
        yaml.safe_load(handle)
print("config ok")
PY
    ;;
  verify-chummer-design-authority)
    python3 /docker/fleet/scripts/verify_chummer_design_authority.py
    ;;
  publish-chummer-design-authority)
    python3 /docker/fleet/scripts/publish_chummer_design_authority.py
    ;;
  db-schema)
    shift
    require_args "$@"
    docker exec -i fleet-controller python3 - "$@" <<'PY'
import json
import sqlite3
import sys

db = sqlite3.connect("/var/lib/codex-fleet/fleet.db")
db.row_factory = sqlite3.Row
for table_name in sys.argv[1:]:
    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    print(json.dumps({
        "table": table_name,
        "columns": [dict(row) for row in rows],
    }, indent=2))
PY
    ;;
  verify-python)
    shift
    require_args "$@"
    python3 -m py_compile "$@"
    ;;
  inject-chummer-public-repo-audit)
    python3 /docker/fleet/scripts/chummer_public_repo_audit_inject.py
    ;;
  inject-chummer-design-dropin-pack)
    python3 /docker/fleet/scripts/chummer_design_dropin_pack_inject.py
    ;;
  inject-chummer-design-authority-audit)
    python3 /docker/fleet/scripts/chummer_design_authority_audit_inject.py
    ;;
  inject-chummer-master-designer-handoff)
    python3 /docker/fleet/scripts/chummer_master_designer_handoff_inject.py
    ;;
  inject-chummer-dev-group-change-guide)
    python3 /docker/fleet/scripts/chummer_dev_group_change_guide_inject.py
    ;;
  inject-chummer-foundation-horizon-guidance)
    python3 /docker/fleet/scripts/chummer_foundation_horizon_feedback_inject.py
    ;;
  inject-chummer-immediate-directives)
    python3 /docker/fleet/scripts/chummer_immediate_directives_feedback_inject.py
    ;;
  sanitize-chummer6-hub-googledrive-secrets)
    python3 /docker/fleet/scripts/sanitize_chummer6_hub_googledrive_secrets.py
    ;;
  janitor-chummer6-repos)
    python3 /docker/fleet/scripts/janitor_chummer6_repos.py
    ;;
  purify-chummer6-legacy-roots)
    python3 /docker/fleet/scripts/purify_chummer6_legacy_roots.py
    ;;
  reset-chummer6-histories)
    reset_chummer6_histories
    ;;
  purge-chummer6-upscaling-model)
    python3 /docker/fleet/scripts/purge_chummer6_upscaling_model.py
    ;;
  purge-chummer6-hub-legacy-gpl)
    python3 /docker/fleet/scripts/purge_chummer6_hub_legacy_gpl.py
    docker exec fleet-studio bash -lc 'cd /docker/chummercomplete/chummer.run-services && bash scripts/ai/verify.sh'
    ;;
  finish-chummer6-guide)
    python3 /docker/fleet/scripts/finish_chummer6_guide.py
    bash /docker/fleet/scripts/deploy.sh verify-config
    ;;
  janitor-chummer6-control-plane)
    python3 /docker/fleet/scripts/janitor_chummer6_control_plane.py
    bash /docker/fleet/scripts/deploy.sh verify-config
    ;;
  advance-ea-chummer6-worker)
    python3 /docker/fleet/scripts/advance_ea_chummer6_worker.py
    bash /docker/EA/scripts/smoke_help.sh
    ;;
  run-ea-chummer6-guide-worker)
    shift
    python3 /docker/fleet/scripts/advance_ea_chummer6_worker.py
    bash /docker/EA/scripts/smoke_help.sh
    cleanup_local_chummer6_worker_processes
    cleanup_chummer6_worker_processes
    python3 /docker/EA/scripts/chummer6_guide_worker.py "$@"
    ;;
  render-ea-chummer6-media-pack)
    shift
    python3 /docker/fleet/scripts/advance_ea_chummer6_worker.py
    cleanup_local_chummer6_worker_processes
    cleanup_chummer6_worker_processes
    fleet_admin_python /docker/EA/scripts/chummer6_guide_media_worker.py render-pack "$@"
    ;;
  check-ea-chummer6-provider-readiness)
    python3 /docker/fleet/scripts/advance_ea_chummer6_worker.py
    fleet_admin_python /docker/EA/scripts/chummer6_provider_readiness.py
    ;;
  probe-browseract-prompting-workflows)
    python3 /docker/fleet/scripts/advance_ea_chummer6_worker.py
    fleet_admin_python /docker/EA/scripts/chummer6_browseract_prompting_systems.py list-workflows
    fleet_admin_python /docker/EA/scripts/chummer6_browseract_prompting_systems.py check --kind refine
    fleet_admin_python /docker/EA/scripts/chummer6_browseract_humanizer.py check
    fleet_admin_python /docker/EA/scripts/chummer6_browseract_prompting_systems.py check --kind magixai_render
    ;;
  cache-browseract-workflow-id)
    shift
    if [ "$#" -lt 2 ]; then
      echo "usage: cache-browseract-workflow-id <result-json> <env-id> [env-query]" >&2
      exit 1
    fi
    python3 /docker/fleet/scripts/cache_browseract_named_workflow.py \
      --result "$1" \
      --env-id "$2" \
      --env-query "${3:-}"
    ;;
  cache-browseract-live-workflow)
    shift
    if [ "$#" -lt 3 ]; then
      echo "usage: cache-browseract-live-workflow <workflow-id> <workflow-name> <env-id> [env-name-key]" >&2
      exit 1
    fi
    workflow_id="$1"
    workflow_name="$2"
    env_id="$3"
    env_name_key="${4:-}"
    python3 - <<PY
from pathlib import Path

env_path = Path("/docker/EA/.env")
assignments = {
    "${env_id}": "${workflow_id}",
}
if "${env_name_key}":
    assignments["${env_name_key}"] = "${workflow_name}"
lines = []
if env_path.exists():
    lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
seen = set()
output = []
for raw in lines:
    if "=" not in raw:
        output.append(raw)
        continue
    key, _value = raw.split("=", 1)
    name = key.strip()
    if name in assignments:
        output.append(f"{name}={assignments[name]}")
        seen.add(name)
    else:
        output.append(raw)
for name, value in assignments.items():
    if name not in seen:
        output.append(f"{name}={value}")
env_path.write_text("\\n".join(output).rstrip() + "\\n", encoding="utf-8")
print({"status": "ok", "env": str(env_path), "updated": sorted(assignments)})
PY
    ;;
  probe-browseract-workflow-api)
    python3 /docker/fleet/scripts/probe_browseract_workflow_api.py
    ;;
  get-browseract-task)
    shift
    if [ "$#" -lt 1 ]; then
      echo "usage: get-browseract-task <task-id> [status|full]" >&2
      exit 1
    fi
    python3 /docker/fleet/scripts/browseract_get_task.py "$1" --mode "${2:-full}"
    ;;
  probe-browseract-task-log)
    shift
    if [ "$#" -lt 1 ]; then
      echo "usage: probe-browseract-task-log <task-id>" >&2
      exit 1
    fi
    task_id="$1"
    browseract_user="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_USERNAME="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    browseract_pass="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_PASSWORD="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    if [ -z "$browseract_user" ] || [ -z "$browseract_pass" ]; then
      echo "BrowserAct dashboard credentials are missing from /docker/EA/.env" >&2
      exit 1
    fi
    ensure_chummer_playwright_image
    docker run --rm -i \
      -v /docker/fleet:/docker/fleet \
      -e BROWSERACT_USERNAME="$browseract_user" \
      -e BROWSERACT_PASSWORD="$browseract_pass" \
      -e BROWSERACT_TASK_ID="$task_id" \
      -e BROWSERACT_STATE_DIR="/docker/fleet/state/browseract_bootstrap/log_probe/${task_id}" \
      chummer-playwright:local \
      node - </docker/fleet/scripts/browseract_task_log_probe.cjs
    ;;
  run-browseract-prompt-refine)
    shift
    if [ "$#" -lt 1 ]; then
      echo "usage: run-browseract-prompt-refine <prompt> [target]" >&2
      exit 1
    fi
    prompt_input="$1"
    target_input="${2:-chummer6}"
    workflow_name="${CHUMMER6_BROWSERACT_PROMPT_RUNTIME_WORKFLOW:-prompting_systems_prompt_forge_runtime}"
    spec_path="/docker/fleet/state/browseract_bootstrap/runtime/${workflow_name}.workflow.json"
    fleet_admin_python /docker/fleet/scripts/build_prompting_systems_prompt_forge.py \
      --workflow-name "$workflow_name" \
      --literal-prompt "$prompt_input" \
      --output-path "$spec_path"
    bash /docker/fleet/scripts/deploy.sh materialize-browseract-workflow-live "$spec_path"
    CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_ID="" \
    CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_QUERY="$workflow_name" \
      python3 /docker/EA/scripts/chummer6_browseract_prompting_systems.py refine \
        --prompt "$prompt_input" \
        --target "$target_input"
    ;;
  run-browseract-humanizer)
    shift
    if [ "$#" -lt 1 ]; then
      echo "usage: run-browseract-humanizer <text> [target]" >&2
      exit 1
    fi
    text_input="$1"
    target_input="${2:-chummer6}"
    workflow_name="${CHUMMER6_BROWSERACT_HUMANIZER_RUNTIME_WORKFLOW:-undetectable_humanizer_runtime}"
    spec_path="/docker/fleet/state/browseract_bootstrap/runtime/${workflow_name}.workflow.json"
    fleet_admin_python /docker/fleet/scripts/build_undetectable_humanizer.py \
      --workflow-name "$workflow_name" \
      --literal-text "$text_input" \
      --output-path "$spec_path"
    bash /docker/fleet/scripts/deploy.sh materialize-browseract-workflow-live "$spec_path"
    CHUMMER6_BROWSERACT_HUMANIZER_WORKFLOW_ID="" \
    CHUMMER6_BROWSERACT_HUMANIZER_WORKFLOW_QUERY="$workflow_name" \
      python3 /docker/EA/scripts/chummer6_browseract_humanizer.py humanize \
        --text "$text_input" \
        --target "$target_input"
    ;;
  run-browseract-humanizer-existing)
    shift
    if [ "$#" -lt 2 ]; then
      echo "usage: run-browseract-humanizer-existing <workflow-name> <text> [target]" >&2
      exit 1
    fi
    workflow_name="$1"
    text_input="$2"
    target_input="${3:-chummer6}"
    CHUMMER6_BROWSERACT_HUMANIZER_WORKFLOW_ID="" \
    CHUMMER6_BROWSERACT_HUMANIZER_WORKFLOW_QUERY="$workflow_name" \
      python3 /docker/EA/scripts/chummer6_browseract_humanizer.py humanize \
        --text "$text_input" \
        --target "$target_input"
    ;;
  run-browseract-prompt-refine-existing)
    shift
    if [ "$#" -lt 2 ]; then
      echo "usage: run-browseract-prompt-refine-existing <workflow-name> <prompt> [target]" >&2
      exit 1
    fi
    workflow_name="$1"
    prompt_input="$2"
    target_input="${3:-chummer6}"
    CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_ID="" \
    CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_QUERY="$workflow_name" \
      python3 /docker/EA/scripts/chummer6_browseract_prompting_systems.py refine \
        --prompt "$prompt_input" \
        --target "$target_input"
    ;;
  inspect-browseract-runtime)
    shift
    if [ "$#" -lt 1 ]; then
      echo "usage: inspect-browseract-runtime <workflow-name>" >&2
      exit 1
    fi
    workflow_name="$1"
    slug="$(python3 - "$workflow_name" <<'PY'
import sys
name = str(sys.argv[1] or '').strip()
slug = ''.join(ch.lower() if ch.isalnum() else '_' for ch in name)
while '__' in slug:
    slug = slug.replace('__', '_')
print(slug.strip('_') or 'workflow')
PY
)"
    runtime_dir="/docker/fleet/state/browseract_bootstrap/runtime/${slug}"
    publish_dir="/docker/fleet/state/browseract_bootstrap/runtime/${slug}_publish"
    if [ ! -d "$runtime_dir" ] && [ ! -d "$publish_dir" ]; then
      echo "missing BrowserAct runtime directories for $workflow_name" >&2
      exit 1
    fi
    python3 - "$workflow_name" "$runtime_dir" "$publish_dir" <<'PY'
import json
import os
import sys
from pathlib import Path

workflow_name, runtime_dir_raw, publish_dir_raw = sys.argv[1:4]
rows = {"workflow_name": workflow_name}
for label, raw in (("runtime", runtime_dir_raw), ("publish", publish_dir_raw)):
    path = Path(raw)
    if not path.exists():
        rows[label] = None
        continue
    files = sorted(path.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    rows[label] = {
        "path": str(path),
        "latest": [entry.name for entry in files[:12]],
    }
    result = path / "result.json"
    if result.exists():
        try:
            rows[label]["result"] = json.loads(result.read_text(encoding="utf-8"))
        except Exception as exc:
            rows[label]["result_error"] = str(exc)
print(json.dumps(rows, indent=2, ensure_ascii=True))
PY
    ;;
  show-browseract-runtime-log)
    shift
    if [ "$#" -lt 1 ]; then
      echo "usage: show-browseract-runtime-log <workflow-name>" >&2
      exit 1
    fi
    workflow_name="$1"
    slug="$(python3 - "$workflow_name" <<'PY'
import sys
name = str(sys.argv[1] or '').strip()
slug = ''.join(ch.lower() if ch.isalnum() else '_' for ch in name)
while '__' in slug:
    slug = slug.replace('__', '_')
print(slug.strip('_') or 'workflow')
PY
)"
    log_path="/docker/fleet/state/browseract_bootstrap/runtime/${slug}/config-log.jsonl"
    if [ ! -f "$log_path" ]; then
      echo "missing config log: $log_path" >&2
      exit 1
    fi
    tail -n 120 "$log_path"
    ;;
  probe-ea-chummer6-text-provider)
    shift
    fleet_admin_python /docker/fleet/scripts/probe_chummer6_text_provider.py "$@"
    ;;
  bootstrap-chummer6-browseract-workflows)
    python3 /docker/fleet/scripts/advance_ea_chummer6_worker.py
    python3 /docker/fleet/scripts/bootstrap_chummer6_browseract_workflows.py
    fleet_admin_python /docker/EA/scripts/chummer6_browseract_prompting_systems.py list-workflows
    fleet_admin_python /docker/EA/scripts/chummer6_browseract_prompting_systems.py check --kind refine
    fleet_admin_python /docker/EA/scripts/chummer6_browseract_prompting_systems.py check --kind magixai_render
    fleet_admin_python /docker/EA/scripts/chummer6_browseract_humanizer.py check
    ;;
  bootstrap-ea-browseract-architect)
    python3 /docker/fleet/scripts/bootstrap_ea_browseract_architect.py
    fleet_admin_python /docker/EA/scripts/browseract_architect.py emit \
      --spec /docker/fleet/state/browseract_bootstrap/browseract_architect.seed.json \
      --output /docker/fleet/state/browseract_bootstrap/browseract_architect.packet.json
    python3 /docker/EA/scripts/bootstrap_browseract_bootstrap_skill.py
    python3 /docker/EA/scripts/bootstrap_browseract_workflow_repair_skill.py
    fleet_admin_python /docker/EA/scripts/browseract_architect.py check
    ;;
  ensure-ea-api)
    docker compose -f /docker/EA/docker-compose.yml up -d ea-db ea-api ea-worker ea-scheduler
    python3 - <<'PY'
import json
import time
import urllib.error
import urllib.request

url = "http://127.0.0.1:8090/health"
deadline = time.time() + 90
last_error = "not_started"
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            body = response.read().decode("utf-8", errors="replace")
        print(json.dumps({"status": "ok", "url": url, "body": body[:240]}))
        raise SystemExit(0)
    except Exception as exc:
        last_error = str(exc)
        time.sleep(2)
print(json.dumps({"status": "error", "url": url, "reason": last_error}))
raise SystemExit(1)
PY
    ;;
  seed-browseract-architect-live)
    python3 /docker/fleet/scripts/bootstrap_ea_browseract_architect.py
    fleet_admin_python /docker/EA/scripts/browseract_architect.py emit \
      --spec /docker/fleet/state/browseract_bootstrap/browseract_architect.seed.json \
      --output /docker/fleet/state/browseract_bootstrap/browseract_architect.packet.json
    ensure_chummer_playwright_image
    browseract_user="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_USERNAME="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    browseract_pass="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_PASSWORD="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    if [ -z "$browseract_user" ] || [ -z "$browseract_pass" ]; then
      echo "BrowserAct dashboard credentials are missing from /docker/EA/.env" >&2
      exit 1
    fi
    docker run --rm -i \
      -v /docker/fleet:/docker/fleet \
      -e BROWSERACT_USERNAME="$browseract_user" \
      -e BROWSERACT_PASSWORD="$browseract_pass" \
      chummer-playwright:local \
      node - </docker/fleet/scripts/browseract_seed_playwright.cjs
    ;;
  materialize-browseract-architect-live)
    python3 /docker/fleet/scripts/bootstrap_ea_browseract_architect.py
    fleet_admin_python /docker/EA/scripts/browseract_architect.py emit \
      --spec /docker/fleet/state/browseract_bootstrap/browseract_architect.seed.json \
      --output /docker/fleet/state/browseract_bootstrap/browseract_architect.packet.json
    ensure_chummer_playwright_image
    browseract_user="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_USERNAME="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    browseract_pass="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_PASSWORD="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    if [ -z "$browseract_user" ] || [ -z "$browseract_pass" ]; then
      echo "BrowserAct dashboard credentials are missing from /docker/EA/.env" >&2
      exit 1
    fi
    docker run --rm -i \
      -v /docker/fleet:/docker/fleet \
      -e BROWSERACT_USERNAME="$browseract_user" \
      -e BROWSERACT_PASSWORD="$browseract_pass" \
      chummer-playwright:local \
      node - </docker/fleet/scripts/browseract_materialize_architect.cjs
    python3 /docker/fleet/scripts/cache_browseract_architect_workflow.py
    fleet_admin_python /docker/EA/scripts/browseract_architect.py check
    ;;
  build-browseract-workflow-spec)
    shift
    if [ "$#" -lt 4 ]; then
      echo "usage: build-browseract-workflow-spec <workflow-name> <purpose> <login-url|none> <tool-url> [--prompt-selector SEL] [--submit-selector SEL] [--result-selector SEL]" >&2
      exit 1
    fi
    fleet_admin_python /docker/EA/scripts/browseract_bootstrap_manager.py \
      --workflow-name "$1" \
      --purpose "$2" \
      --login-url "$3" \
      --tool-url "$4" \
      "${@:5}"
    ;;
  build-prompting-systems-prompt-forge)
    fleet_admin_python /docker/fleet/scripts/build_prompting_systems_prompt_forge.py
    ;;
  build-undetectable-humanizer)
    fleet_admin_python /docker/fleet/scripts/build_undetectable_humanizer.py
    ;;
  materialize-browseract-workflow-live)
    shift
    if [ "$#" -lt 1 ]; then
      echo "usage: materialize-browseract-workflow-live <spec-json> [workflow-id]" >&2
      exit 1
    fi
    spec_path="$1"
    workflow_id_hint="${2:-}"
    if [ ! -f "$spec_path" ]; then
      echo "missing spec: $spec_path" >&2
      exit 1
    fi
    python3 /docker/fleet/scripts/bootstrap_ea_browseract_architect.py
    slug="$(python3 - "$spec_path" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
name = str(data.get('workflow_name') or 'workflow').strip() or 'workflow'
slug = ''.join(ch.lower() if ch.isalnum() else '_' for ch in name)
while '__' in slug:
    slug = slug.replace('__', '_')
print(slug.strip('_') or 'workflow')
PY
)"
    packet_path="/docker/fleet/state/browseract_bootstrap/runtime/${slug}.packet.json"
    state_dir="/docker/fleet/state/browseract_bootstrap/runtime/${slug}"
    fleet_admin_python /docker/EA/scripts/browseract_architect.py emit \
      --spec "$spec_path" \
      --output "$packet_path"
    ensure_chummer_playwright_image
    browseract_user="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_USERNAME="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    browseract_pass="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_PASSWORD="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    if [ -z "$browseract_user" ] || [ -z "$browseract_pass" ]; then
      echo "BrowserAct dashboard credentials are missing from /docker/EA/.env" >&2
      exit 1
    fi
    workflow_name="$(python3 - "$spec_path" <<'PY'
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
print(str(data.get('workflow_name') or '').strip())
PY
)"
    pkill -f "BROWSERACT_WORKFLOW_NAME=$workflow_name" >/dev/null 2>&1 || true
    pkill -f "/docker/fleet/state/browseract_bootstrap/runtime/${slug}.packet.json" >/dev/null 2>&1 || true
    capture_snapshots="${BROWSERACT_CAPTURE_SNAPSHOTS:-0}"
    capture_html="${BROWSERACT_CAPTURE_HTML:-0}"
    lock_path="/tmp/browseract_materialize.lock"
    (
      flock -w 600 9 || {
        echo "timed out waiting for BrowserAct materializer lock" >&2
        exit 1
      }
      docker run --rm -i \
        -v /docker/fleet:/docker/fleet \
        -e BROWSERACT_USERNAME="$browseract_user" \
        -e BROWSERACT_PASSWORD="$browseract_pass" \
        -e BROWSERACT_PACKET_PATH="$packet_path" \
        -e BROWSERACT_STATE_DIR="$state_dir" \
        -e BROWSERACT_WORKFLOW_NAME="$workflow_name" \
        -e BROWSERACT_WORKFLOW_ID="$workflow_id_hint" \
        -e BROWSERACT_CAPTURE_SNAPSHOTS="$capture_snapshots" \
        -e BROWSERACT_CAPTURE_HTML="$capture_html" \
        chummer-playwright:local \
        node - </docker/fleet/scripts/browseract_materialize_architect.cjs
    ) 9>"$lock_path"
    ;;
  cleanup-browseract-materializers)
    shift
    if [ "$#" -lt 1 ]; then
      echo "usage: cleanup-browseract-materializers <workflow-name>" >&2
      exit 1
    fi
    workflow_name="$1"
    slug="$(python3 - "$workflow_name" <<'PY'
import sys
name = str(sys.argv[1] or '').strip()
slug = ''.join(ch.lower() if ch.isalnum() else '_' for ch in name)
while '__' in slug:
    slug = slug.replace('__', '_')
print(slug.strip('_') or 'workflow')
PY
)"
    pkill -f "BROWSERACT_WORKFLOW_NAME=$workflow_name" >/dev/null 2>&1 || true
    pkill -f "/docker/fleet/state/browseract_bootstrap/runtime/${slug}.packet.json" >/dev/null 2>&1 || true
    ;;
  publish-browseract-workflow-live)
    shift
    if [ "$#" -lt 1 ]; then
      echo "usage: publish-browseract-workflow-live <workflow-name> [workflow-id]" >&2
      exit 1
    fi
    workflow_name="$1"
    workflow_id="${2:-}"
    slug="$(python3 - "$workflow_name" <<'PY'
import sys
name = str(sys.argv[1] or '').strip()
slug = ''.join(ch.lower() if ch.isalnum() else '_' for ch in name)
while '__' in slug:
    slug = slug.replace('__', '_')
print(slug.strip('_') or 'workflow')
PY
)"
    state_dir="/docker/fleet/state/browseract_bootstrap/runtime/${slug}_publish"
    browseract_user="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_USERNAME="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    browseract_pass="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_PASSWORD="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    if [ -z "$browseract_user" ] || [ -z "$browseract_pass" ]; then
      echo "BrowserAct dashboard credentials are missing from /docker/EA/.env" >&2
      exit 1
    fi
    ensure_chummer_playwright_image
    docker run --rm -i \
      -v /docker/fleet:/docker/fleet \
      -e BROWSERACT_USERNAME="$browseract_user" \
      -e BROWSERACT_PASSWORD="$browseract_pass" \
      -e BROWSERACT_STATE_DIR="$state_dir" \
      -e BROWSERACT_WORKFLOW_NAME="$workflow_name" \
      -e BROWSERACT_WORKFLOW_ID="$workflow_id" \
      chummer-playwright:local \
      node - </docker/fleet/scripts/browseract_publish_workflow.cjs
    ;;
  probe-browseract-architect-build-live)
    browseract_user="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_USERNAME="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    browseract_pass="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_PASSWORD="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    if [ -z "$browseract_user" ] || [ -z "$browseract_pass" ]; then
      echo "BrowserAct dashboard credentials are missing from /docker/EA/.env" >&2
      exit 1
    fi
    docker run --rm -i \
      -v /docker/fleet:/docker/fleet \
      -e BROWSERACT_USERNAME="$browseract_user" \
      -e BROWSERACT_PASSWORD="$browseract_pass" \
      chummer-playwright:local \
      node - </docker/fleet/scripts/browseract_probe_architect_build.cjs
    ;;
  probe-browseract-node-edit-live)
    ensure_chummer_playwright_image
    browseract_user="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_USERNAME="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    browseract_pass="$(python3 - <<'PY'
from pathlib import Path
value = ""
env = Path("/docker/EA/.env")
if env.exists():
    for raw in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if raw.startswith("BROWSERACT_PASSWORD="):
            value = raw.split("=", 1)[1].strip()
            break
print(value)
PY
)"
    if [ -z "$browseract_user" ] || [ -z "$browseract_pass" ]; then
      echo "BrowserAct dashboard credentials are missing from /docker/EA/.env" >&2
      exit 1
    fi
    docker run --rm -i \
      -v /docker/fleet:/docker/fleet \
      -e BROWSERACT_USERNAME="$browseract_user" \
      -e BROWSERACT_PASSWORD="$browseract_pass" \
      chummer-playwright:local \
      node - </docker/fleet/scripts/browseract_probe_node_edit.cjs
    ;;
  probe-browser-site-live)
    shift
    if [ "$#" -lt 2 ]; then
      echo "usage: probe-browser-site-live <name> <url>" >&2
      exit 1
    fi
    ensure_chummer_playwright_image
    probe_name="$1"
    probe_url="$2"
    docker run --rm -i \
      -v /docker/fleet:/docker/fleet \
      -e PROBE_NAME="$probe_name" \
      -e PROBE_TARGET_URL="$probe_url" \
      chummer-playwright:local \
      node - </docker/fleet/scripts/browser_site_probe.cjs
    ;;
  probe-ea-chummer6-media-provider)
    python3 /docker/fleet/scripts/advance_ea_chummer6_worker.py
    shift
    fleet_admin_python /docker/fleet/scripts/probe_chummer6_media_provider.py "$@"
    ;;
  probe-magixai-api-live)
    shift
    python3 /docker/fleet/scripts/probe_magixai_api.py "$@"
    ;;
  inspect-chummer6-refresh)
    python3 /docker/fleet/scripts/advance_ea_chummer6_worker.py
    fleet_admin_shell 'echo "== fleet-admin worker pids =="; ps -ef | grep -E "chummer6_guide_(worker|media_worker)|chummer6_browseract_prompting_systems" | grep -v grep || true; echo "== state files =="; ls -l /docker/fleet/state/chummer6 2>/dev/null || true; echo "== recent media outputs =="; ls -l /docker/chummercomplete/Chummer6/assets/hero /docker/chummercomplete/Chummer6/assets/horizons 2>/dev/null || true'
    ;;
  audit-chummer6-ooda)
    python3 /docker/fleet/scripts/finish_chummer6_guide.py --audit-only
    ;;
  publish-chummer6-from-ea-state)
    python3 /docker/fleet/scripts/advance_ea_chummer6_worker.py
    cleanup_local_chummer6_worker_processes
    cleanup_chummer6_worker_processes
    fleet_admin_python /docker/EA/scripts/chummer6_guide_media_worker.py render-pack
    python3 /docker/fleet/scripts/finish_chummer6_guide.py
    bash /docker/fleet/scripts/deploy.sh verify-config
    ;;
  refresh-chummer6-guide-via-ea)
    shift
    python3 /docker/fleet/scripts/advance_ea_chummer6_worker.py
    bash /docker/EA/scripts/smoke_help.sh
    fleet_admin_python /docker/EA/scripts/chummer6_provider_readiness.py
    fleet_admin_python /docker/EA/scripts/bootstrap_chummer6_guide_skill.py
    cleanup_local_chummer6_worker_processes
    cleanup_chummer6_worker_processes
    python3 /docker/EA/scripts/chummer6_guide_worker.py "$@"
    fleet_admin_python /docker/EA/scripts/chummer6_guide_media_worker.py render-pack
    python3 /docker/fleet/scripts/finish_chummer6_guide.py
    bash /docker/fleet/scripts/deploy.sh verify-config
    ;;
  publish-chummer6-poc-release)
    python3 /docker/fleet/scripts/publish_chummer6_poc_release.py
    ;;
  fix-chummer6-audit-gaps)
    python3 /docker/fleet/scripts/fix_chummer6_audit_gaps.py
    ;;
  fix-chummer6-family-coherence)
    python3 /docker/fleet/scripts/fix_chummer6_family_coherence.py
    python3 /docker/fleet/scripts/finish_chummer6_guide.py
    ;;
  sync-chummer6-design-truth)
    python3 /docker/fleet/scripts/sync_chummer6_design_truth.py
    ;;
  apply-ea-audit-hardening)
    python3 /docker/fleet/scripts/apply_ea_audit_hardening.py
    ;;
  verify-ea-audit-hardening)
    (
      cd /docker/EA
      python3 -m py_compile \
        ea/app/settings.py \
        ea/app/container.py \
        ea/app/api/app.py \
        ea/app/api/dependencies.py \
        ea/app/services/task_contracts.py \
        ea/app/services/skills.py \
        ea/app/services/planner.py \
        ea/app/services/ltd_inventory_api.py \
        ea/app/services/ltd_inventory_markdown.py \
        ea/app/services/provider_registry.py \
        tests/test_runtime_profile.py \
        tests/test_provider_registry.py \
        tests/test_planner_edge_cases.py
    )
    python3 /docker/fleet/scripts/verify_ea_audit_hardening.py
    ;;
  inject-ea-main-branch-audit)
    python3 /docker/fleet/scripts/ea_main_branch_audit_inject.py
    ;;
  inject-ea-provider-registry-feedback)
    python3 /docker/fleet/scripts/ea_provider_registry_feedback_inject.py
    ;;
  update-ea-ltds-unmixr)
    python3 /docker/fleet/scripts/update_ea_ltds_unmixr.py
    ;;
  update-ea-ltds-browserly)
    python3 /docker/fleet/scripts/update_ea_ltds_browserly.py
    ;;
  update-ea-ltds-onemin-business)
    python3 /docker/fleet/scripts/update_ea_ltds_onemin_business.py
    ;;
  inject-ea-provider-keys)
    shift
    require_args "$@"
    python3 /docker/fleet/scripts/inject_ea_provider_keys.py "$@"
    ;;
  inject-browseract-dashboard-credentials)
    shift
    require_args "$@"
    if [ "$#" -lt 2 ]; then
      echo "usage: bash scripts/deploy.sh inject-browseract-dashboard-credentials <email> <password>" >&2
      exit 1
    fi
    tmp_json="$(mktemp /tmp/browseract_dashboard_creds.XXXXXX.json)"
    python3 - "$tmp_json" "$1" "$2" <<'PY'
import json, sys
path, email, password = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, "w", encoding="utf-8") as fh:
    json.dump(
        {
            "BROWSERACT_USERNAME": email,
            "BROWSERACT_PASSWORD": password,
        },
        fh,
        ensure_ascii=True,
    )
PY
    python3 /docker/fleet/scripts/inject_ea_provider_keys.py "$tmp_json"
    rm -f "$tmp_json"
    ;;
  sync-ea-chummer-provider-envs)
    shift
    require_args "$@"
    python3 /docker/fleet/scripts/sync_ea_chummer_provider_envs.py "$@"
    ;;
  inject-fleet-public-audit)
    python3 /docker/fleet/scripts/fleet_public_audit_inject.py
    ;;
  inject-fleet-design-progress-feedback)
    python3 /docker/fleet/scripts/fleet_design_progress_feedback_inject.py
    ;;
  inject-chummer-public-design-ltd-audit)
    python3 /docker/fleet/scripts/chummer_public_design_ltd_audit_inject.py
    ;;
  publish-latest-pass)
    publish_latest_pass
    ;;
  publish-repo-all)
    shift
    publish_repo_all "$@"
    ;;
  publish-repo-all-to)
    shift
    publish_repo_all_to "$@"
    ;;
  publish-repo-files)
    shift
    publish_repo_files "$@"
    ;;
  publish-repo-force)
    shift
    publish_repo_force "$@"
    ;;
  stop-fleet)
    stop_fleet
    ;;
  rehome-chummer6-repos)
    python3 /docker/fleet/scripts/rehome_chummer6_repos.py
    ;;
  retarget-chummer6-repos)
    python3 /docker/fleet/scripts/retarget_chummer6_repos.py
    ;;
  github-rate-limit)
    gh api rate_limit --jq '.resources.core | {limit, remaining, used, reset}'
    ;;
  set-chummer-legacy-repos-private)
    python3 /docker/fleet/scripts/set_chummer_legacy_repos_private.py
    ;;
  rebuild)
    shift
    require_args "$@"
    docker compose up -d --build "$@"
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    echo "unknown command: $1" >&2
    usage >&2
    exit 1
    ;;
esac
