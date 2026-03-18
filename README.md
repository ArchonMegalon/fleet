# Codex Fleet Studio Bundle

This bundle deploys five Docker services behind one internal origin:
- `fleet-controller`: the disposable `codex exec` spider / scheduler
- `fleet-studio`: a target-scoped design-control plane for project, group, and fleet sessions
- `fleet-admin`: the operator console for groups, projects, accounts, routing, publish history, and signoff
- `fleet-auditor`: the background scanner that produces findings and candidate tasks
- `fleet-dashboard`: an Nginx gateway that keeps one Cloudflare target and serves the public dashboard, `/admin`, and `/studio`

## Default networking

- Docker network: `codex-fleet-net`
- Shared origin target for a separate `cloudflared` container: `http://fleet-dashboard:8090`
- Default host URL: `http://127.0.0.1:18090`
- Studio URL: `http://127.0.0.1:18090/studio`

## What The Control Plane Adds

Studio lets the admin user:
- discuss project direction and tradeoffs with a design-oriented agent role
- draft publishable artifacts without directly editing repo instructions by hand
- publish approved artifacts into repo-local `.codex-studio/published/`
- publish optional feedback notes into `feedback/` so coding workers see the decision immediately
- target a single project, a whole group, or the fleet itself
- publish coordinated multi-target proposals through `proposal.targets`

Admin adds:
- a forecast-first command deck at `/admin`
- an explorer for raw inventory and control-plane detail at `/admin/details`
- group-first operations views
- account, routing, and project policy controls
- signoff, refill, audit-now, and publish actions
- group run history and publish history
- mission, loop, runway, blocker, and truth-freshness views at `/admin`
- raw cockpit inventory, lamps, attention feeds, worker tables, and control forms at `/admin/details`

Auditor adds:
- repo, milestone, and contract findings
- candidate tasks that can be approved or auto-published at slice boundaries
- group-scoped artifacts such as `GROUP_BLOCKERS.md` and `CONTRACT_SETS.yaml`

Published artifacts can include:
- `VISION.md`
- `ROADMAP.md`
- `ARCHITECTURE.md`
- `runtime-instructions.generated.md`
- `QUEUE.generated.yaml`

Every publish now also writes `.codex-studio/published/compile.manifest.json` with:
- desired-state schema version
- target lifecycle
- published artifact list
- stage provenance for design compile / policy compile / execution compile
- whether dispatchable truth is actually ready for a runnable repo

## Compiled mission model

Fleet now treats modeled truth and dispatchable truth separately.

- design compile: canonical design artifacts become approved repo or group outputs
- policy compile: approved artifacts become queue overlays, runtime instructions, blocker files, and review guidance
- execution compile: policy outputs become concrete dispatchable truth for controller, auditor, healer, and review lanes

Project and group configs also carry lifecycle / maturity:
- `planned`
- `scaffold`
- `dispatchable`
- `live`
- `signoff_only`

Lockstep and runway pressure are computed from dispatch-participating members only, so scaffold repos still receive audit and design attention without distorting live mission posture.

The spider now reads published Studio artifacts before coding. If `QUEUE.generated.yaml` is present, it overlays the configured queue.

### Queue overlay format

```yaml
mode: append   # append | prepend | replace
items:
  - tighten hub route contracts
  - add approval review UI for generated assets
```

## Multi-account support

Both the spider and Studio can use different Codex identities. Map aliases in `config/accounts.yaml` to either:
- API keys (`auth_kind: api_key`)
- ChatGPT auth caches (`auth_kind: chatgpt_auth_json`)

Studio defaults to `acct-studio-a` and then falls back to `acct-shared-b`, but you can change that through the split desired-state config in `config/accounts.yaml`, `config/routing.yaml`, and the relevant project policy file under `config/projects/`.

Important operational rule:
- if multiple aliases share the same ChatGPT `auth.json`, treat them as one effective human account lane
- with one real ChatGPT-authenticated account, the safe fleet-wide parallelism is `1`
- raise the global parallel cap only when you actually add another distinct account or API-key pool

Project routing now supports:
- preferred / burst / reserve account lanes
- Spark eligibility filtering
- group captain policy for priority, service floors, and shed order
- slice-boundary refill from approved auditor tasks
- GitHub-backed Codex review gating after local verify
- evidence-driven route classification (`classification_mode: evidence_v1`) using recent run outcomes instead of keywords alone

## Codex refresh policy

Fleet coding slices do not use the host `codex` install. `codex exec` runs inside the
`fleet-controller` container, and Studio uses the `fleet-studio` container image. Both images install
`@openai/codex` during Docker build.

This repo now includes a `fleet-rebuilder` sidecar that refreshes those images on a daily UTC schedule.
It rebuilds `fleet-controller`, `fleet-studio`, and `fleet-dashboard` by default, forces a recreate so
the new CLI becomes live, rotates a `CODEX_NPM_REFRESH_TOKEN` build arg so the Codex npm layer is
not stuck behind Docker's build cache, and canary-rolls the first configured service before widening
the refresh across the remaining bridge services.

Configure the schedule in `runtime.env`:

```bash
FLEET_REBUILD_ENABLED=true
FLEET_REBUILD_HOUR_UTC=04
FLEET_REBUILD_MINUTE_UTC=15
FLEET_REBUILD_SERVICES="fleet-controller fleet-studio fleet-dashboard"
FLEET_REBUILD_CANARY_ENABLED=true
FLEET_REBUILD_CANARY_SERVICES="fleet-controller"
FLEET_REBUILD_CANARY_TIMEOUT_SECONDS=180
```

Browser-facing operator access is also configured in `runtime.env`:

```bash
FLEET_OPERATOR_AUTH_REQUIRED=true
FLEET_OPERATOR_USER=operator
FLEET_OPERATOR_PASSWORD=replace-with-a-strong-password
```

When enabled, `/admin`, `/admin/details`, `/studio`, `/api/admin/*`, `/api/cockpit/*`, and `/api/studio/*` require the shared operator login served from `/admin/login`.

Auto-heal now uses explicit category playbooks in `config/policies.yaml` for:
- `coverage`
- `review`
- `capacity`
- `contracts`

Each playbook can define deterministic steps, whether an LLM fallback is allowed, whether verify is required, and how many bounded attempts happen before escalation.

## GitHub review lane

Fleet review now defaults to a GitHub-native lane instead of local `codex exec` review.

The Fleet self-project is the intentional exception. Its project policy stays on `review.mode: local` with `trigger: local` so the cheap `groundwork -> review_light -> jury` loop can run end-to-end without waiting on a PR review round-trip while the stack is self-hosting.

The runtime flow is:

1. worker finishes a coding slice and passes local verify
2. fleet commits and pushes a review branch
3. fleet creates or updates a draft PR
4. fleet requests Codex review with `@codex review ...`
5. if the GitHub review lane is throttled or degraded long enough, fleet runs a bounded local fallback review and records the result before escalating

Review fallback defaults:
- mark the lane degraded when GitHub is throttled, when `3+` projects are waiting, or when the oldest wait exceeds `45` minutes
- launch local fallback review after `45` minutes in a degraded lane or after `2` missed wake-up checks
- attempt at most `1` local fallback review per PR head before escalating
6. if fewer than `2` Codex workers are active and no coding slice is dispatchable, fleet backfills with local review work first and queue-generation audits second
7. fleet ingests PR review findings back into project feedback and operator views

Important constraints:
- the separate review bucket comes from GitHub Codex review, not from a local prompt like `review my code`
- local review should be treated as fallback-only for ordinary projects; the Fleet self-project uses local review by design
- queue advance is gated on the GitHub review result when project review is enabled

The controller and admin containers read GitHub auth from a mounted `hosts.yml` at `/run/gh/hosts.yml`, typically provided from `${HOME}/.config/gh`.

## Deploy

Run the installer from a full Fleet source checkout. It copies the full compose bundle (`controller`, `studio`, `admin`, `auditor`, `gateway`, `scripts`, and the split config tree) into the install directory, preserves operator-managed `accounts.yaml` / runtime env files unless `--force` is set, retargets the Fleet self-project from `/docker/fleet` to the installed bundle path, mounts that installed path into the running services, validates the self-project files referenced by `design_doc` and `verify_cmd`, then waits for the compose services plus the dashboard `/health` and `/api/status` checks to come up cleanly.

```bash
./deploy-fleet.sh
```

Or choose a different host port/network:

```bash
./deploy-fleet.sh --host-port 18190 --network-name my-fleet-net
```

## Common operations

Restart after config changes:

```bash
cd /opt/codex-fleet && docker compose up -d --build
```

Check the controller dashboard API:

```bash
curl http://127.0.0.1:18090/api/status
```

If `deploy-fleet.sh` exits non-zero, inspect the emitted `docker compose ps` / `docker compose logs` output first; the installer now fails closed when the packaged bundle does not boot cleanly.

Packaged installs are now self-contained for the Fleet self-project. A clean host no longer needs a separate `/docker/fleet` checkout just to make the installed controller target itself.

Run a nonstop project loop that keeps one project continuously dispatching:

```bash
python3 scripts/fleet_codex_nonstop.py <project-id>
```

If another nonstop loop is already running for the same `<project-id>`, the second process exits with a clear lock message.

Options let you tolerate breaks without exiting:

```bash
python3 scripts/fleet_codex_nonstop.py <project-id> --include-review --include-signoff --max-idle-ticks 0
```

Use `--never-stop` to keep cycling through breaks (review, signoff, cooldown, no remaining work) without ending the process:

```bash
python3 scripts/fleet_codex_nonstop.py <project-id> --never-stop
```

Set `--max-idle-ticks` to a positive number to stop after that many consecutive empty ticks; leave it at `0` for indefinite nonstop operation.

Install the local Codex launch shims tracked in this repo:

```bash
bash scripts/install_codex_and_codexea_shims.sh
```

That installs:
- `~/bin/codex` for the normal local wrapper
- `~/.local/bin/codexea` for the Codex + EA MCP wrapper
- `~/.local/bin/codexaudit` for the EA audit/jury wrapper
- `~/.local/bin/codexea-watchdog` for the CodexEA idle-nudge wrapper
- `~/.local/bin/codexsurvival` for the EA survival backup wrapper
- `~/.codex/prompts/ea_interactive_bootstrap.md` for the EA interactive bootstrap prompt
- `~/.codex/prompts/ea_survival_bootstrap.md` for the EA survival bootstrap prompt
- an `ea-mcp` Codex MCP server entry pointing at `scripts/ea_mcp_bridge.py`

Default behavior:
- `codex` now prepends the EA interactive bootstrap by default when that prompt file is installed, keeps the normal built-in OpenAI / ChatGPT model path unless you explicitly override it, and biases ordinary sessions toward EA MCP tools and Gemini-backed structured work before spending on long local turns.
- `codexea` now locks ordinary sessions to the EA `easy` Responses path by default, treats `--interactive` as a compatibility alias for the plain TUI path, prefers the live `/v1/codex/profiles` model for that lane when EA reports one, emits a startup `Trace:` line that reflects the real provider path, and still rejects ad hoc model/provider/profile overrides on the locked easy path. If EA `easy` is unhealthy, that failure does not imply a fallback to the built-in ChatGPT provider.
- `codexaudit` now pins the EA `jury` lane, routes to `ea-audit-jury`, disables the cheap post-audit loop so audit sessions do not recursively self-review, and probes the BrowserAct audit path up front. If the audit connector is missing it now fails fast with a short error instead of dropping you into a JSON-only dead end. Set `CODEXAUDIT_ALLOW_SOFT_FALLBACK=1` to degrade to `ea-coder-fast` explicitly when you still want a non-jury fallback.
- `codexea credits` and `codexea onemin` now force a live `/v1/codex/status?refresh=1` aggregate for the 1min pool, including slot count, free/max credits, percent left, current-pace ETA, the 7-day average-burn runway, owner-ledger matches, and latest explicit probe results. Add `--json` for scripting, or `--probe-all` to run `POST /v1/providers/onemin/probe-all` before rendering.
- `codexea onemin/credits` includes an optional live top-up refresh pass via `POST /v1/providers/onemin/billing-refresh` (`--billing`, enabled by default in the live `codexea` shell) that adds:
  - last browser refresh timestamp
  - binding count processed
  - direct API account attempt/skip counts
  - billing/member reconciliation counts
  - top-up ETA and amount from parsed usage snapshots
  To disable this pass, set `CODEXEA_CREDITS_INCLUDE_BILLING=0`.
- Example:

```text
1min billing refresh
Bindings: 3
API accounts: 2 configured, 2 attempted, 0 skipped
Billing snapshots: 3
Member reconciliations: 2
Direct API refresh: billing 2 | members 2
Direct API refresh: rate-limited, throttled
Next top-up at: 2026-03-31T00:00:00Z
Top-up amount: 2000000
Hours until top-up: 320.5

1min aggregate
...
```
- Set `CODEXEA_MODE=responses` or `CODEXEA_MODE=mcp` only when debugging an explicit non-easy lane. On ordinary `codexea` easy runs the shim rejects `CODEXEA_MODE` unless `CODEXEA_ALLOW_EASY_MODE_OVERRIDE=1` is set deliberately for debugging.
- `CODEXEA_BASE_PROFILE` still applies to explicit MCP runs, but ordinary `codexea` sessions no longer rely on a separate base profile to stay off the built-in provider path.
- Set `CODEX_PREFER_EA_MCP=0` or `CODEX_WRAPPER_DISABLE_BOOTSTRAP=1` if you need one plain session without the EA MCP bootstrap.
- Set `CODEX_FORCE_DEFAULT_PROVIDER=0` only if you intentionally want the normal `codex` wrapper to stop forcing the built-in OpenAI provider for ordinary runs.
- Set `CODEXEA_INTERACTIVE_ALWAYS_EASY=0` only if you intentionally want `codexea` to resume using the full lane router for ordinary interactive sessions; otherwise completed interactive runs now emit a compact async post-audit packet to `ea-review-light`.

Use `codexsurvival` for slow backup work against EA's `ea-coder-survival` alias. It is best suited to bounded `codex exec` style runs because EA's survival lane is background/poll oriented in v1.

Bare `codexea` sessions keep the watchdog off by default. Set `CODEXEA_ENABLE_WATCHDOG=1` if you want the idle-nudge wrapper, or run `codexea-watchdog` directly and override its behavior with `CODEXEA_WATCHDOG_INTERVAL` or `CODEXEA_WATCHDOG_PROMPT`.

Check Studio sessions:

```bash
curl http://127.0.0.1:18090/api/studio/status
```

Run the cross-file consistency guard:

```bash
python3 scripts/check_consistency.py
```

Check the operator status feeds:

```bash
curl http://127.0.0.1:18090/api/admin/status
curl http://127.0.0.1:18090/api/cockpit/mission-board
curl http://127.0.0.1:18090/api/cockpit/blocker-forecast
```

Request or sync a review manually:

```bash
curl -X POST http://127.0.0.1:18090/api/admin/projects/core/review/request
curl -X POST http://127.0.0.1:18090/api/admin/projects/core/review/sync
```

Connect an existing Cloudflare container to the shared network once:

```bash
docker network connect codex-fleet-net <cloudflared-container>
```

## Recommended admin flow

1. Open `/admin` and read the Command Deck first: current slice, next transition, mission runway, blockers, truth freshness, and the active cheap review loop should tell you what is moving and what stops next.
2. Resolve the top approval or bottleneck from the Command Deck before opening raw tables.
3. Use `/admin/details` as the Explorer for Projects, Groups, Reviews, Audit, Milestones, Accounts, Routing, History, Studio, and Settings when you need inventory-level inspection, lifecycle/compile detail, or policy edits.
4. Open `/studio` for a project, group, or fleet target when you need scoped design or planning help; `/admin` now previews pending Studio publish items without forcing a page jump for common approvals.
5. Use the GitHub review lane from `/admin` to request, retrigger, or sync Codex review when queue advance is gated on PR review.
6. Let the spider continue coding slices; it will ingest published runtime instructions, feedback notes, review findings, design mirrors, compile manifests, and queue overlays automatically.
