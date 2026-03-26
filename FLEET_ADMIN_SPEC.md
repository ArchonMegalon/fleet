# Fleet Admin Spec

## Purpose

`fleet-admin` is the write-capable operator console for Codex Fleet.

It exists so:

- YAML remains desired state
- SQLite remains runtime state
- operators stop hand-editing config files for routine project/account/routing work
- the default `/admin` experience is a cockpit, not a registry screen

## Service boundary

`fleet-admin` is a fourth service behind the existing gateway.

It owns:

- the cockpit read model for attention, workers, approvals, and runway
- project/group/account/routing writes to desired state
- runtime controls against `fleet.db`
- audit task approval and publication
- Studio publish preview / approval handoff
- add-project bootstrap helpers for repos mounted under `/docker`

It does not replace:

- `fleet-controller` for scheduling and execution
- `fleet-studio` for design conversations and artifact publication
- `fleet-dashboard` as the shared ingress/gateway container

## Implemented routes

### HTML

- `GET /`
- `GET /progress`
- `GET /progress/`
- `GET /ops`
- `GET /ops/`
- `GET /admin`
- `GET /admin/`
- `GET /admin/login`
- `GET /admin/details`
- `GET /studio`
- `GET /studio/`

### Health

- `GET /health`

### API

- `GET /api/public/status`
- `GET /api/public/progress-report`
- `GET /api/public/progress-poster.svg`
- `GET /api/admin/status`
- `GET /api/cockpit/status`
- `GET /api/cockpit/summary`
- `GET /api/cockpit/attention`
- `GET /api/cockpit/workers`
- `GET /api/cockpit/lamps`
- `GET /api/cockpit/runway`
- `GET /api/cockpit/simulation`
- `POST /api/admin/projects/add`
- `POST /api/admin/projects/bootstrap`
- `POST /api/admin/projects/{project_id}/pause`
- `POST /api/admin/projects/{project_id}/resume`
- `POST /api/admin/projects/{project_id}/clear-cooldown`
- `POST /api/admin/projects/{project_id}/retry`
- `POST /api/admin/projects/{project_id}/run-now`
- `POST /api/admin/projects/{project_id}/review/request`
- `POST /api/admin/projects/{project_id}/review/sync`
- `POST /api/admin/projects/{project_id}/queue`
- `POST /api/admin/projects/{project_id}/account-policy`
- `POST /api/admin/projects/{project_id}/review-policy`
- `POST /api/admin/accounts/upsert`
- `POST /api/admin/accounts/{alias}/state`
- `POST /api/admin/accounts/{alias}/clear-backoff`
- `POST /api/admin/accounts/{alias}/validate`
- `POST /api/admin/routing/update`
- `POST /api/admin/policies/auto-heal`
- `POST /api/admin/routing/classes/{route_class}`
- `POST /api/admin/groups/{group_id}/captain`
- `POST /api/admin/groups/{group_id}/protect`
- `POST /api/admin/groups/{group_id}/drain`
- `POST /api/admin/groups/{group_id}/burst`
- `POST /api/admin/auditor/run-now`
- `POST /api/admin/groups/{group_id}/audit-now`
- `POST /api/admin/groups/{group_id}/pause`
- `POST /api/admin/groups/{group_id}/resume`
- `POST /api/admin/groups/{group_id}/heal-now`
- `POST /api/admin/groups/{group_id}/signoff`
- `POST /api/admin/groups/{group_id}/reopen`
- `POST /api/admin/groups/{group_id}/refill-approved`
- `POST /api/admin/incidents/{incident_id}/auto-resolve`
- `POST /api/admin/incidents/{incident_id}/ack`
- `POST /api/admin/incidents/{incident_id}/escalate`
- `POST /api/admin/policies/auto-heal/category/{category}`
- `POST /api/admin/policies/auto-heal/category/{category}/resolve-now`
- `POST /api/admin/policies/auto-heal/escalation/{category}`
- `POST /api/admin/audit/tasks/{candidate_id}/approve`
- `POST /api/admin/audit/tasks/{candidate_id}/reject`
- `POST /api/admin/audit/tasks/{candidate_id}/publish`
- `POST /api/admin/audit/tasks/{candidate_id}/publish-mode`
- `POST /api/admin/studio/sessions`
- `POST /api/admin/studio/sessions/{session_id}/message`
- `POST /api/admin/studio/proposals/{proposal_id}/publish`
- `POST /api/admin/studio/proposals/{proposal_id}/publish-mode`

### Gateway posture

- `/` is the public Mission Bridge: low-context mission/trust/status view
- `/ops/` is the authenticated Operator Cockpit: compile, dispatch, capacity, support, providers, publish, housekeeping, history, and inventory
- `/dashboard/` remains a legacy compatibility redirect to `/ops/`

## Desired-state touchpoints

`fleet-admin` writes:

- `config/fleet.yaml` as the root loader entrypoint
- `config/accounts.yaml`
- `config/policies.yaml`
- `config/routing.yaml`
- `config/groups.yaml`
- `config/projects/*.yaml`

Desired-state schema version: `2026-03-10.v1`

The desired-state model is now explicitly split between:

- modeled truth: design canon, blockers, milestones, contracts, lifecycle, and review policy
- dispatchable truth: queue overlays, runtime instructions, execution-ready slices, and account/routing decisions

Project and group configs now carry lifecycle / maturity:

- `planned`
- `scaffold`
- `dispatchable`
- `live`
- `signoff_only`

Dispatch participation is limited to `dispatchable` and `live`. `planned`, `scaffold`, and `signoff_only` still remain visible to audit and design flows, but they no longer distort lockstep dispatch or runway posture.

Fields currently managed through the UI include project metadata, lifecycle/maturity, project account/review/auto-heal policy, group captain and group auto-heal policy, routing classes, and account state/policy.

## Compile model

Fleet now treats Studio publication as a five-stage compile pipeline:

1. design compile
2. policy compile
3. execution compile
4. package compile
5. capacity compile

Each Studio publish writes `.codex-studio/published/compile.manifest.json` with:

- schema version
- target type and target id
- target lifecycle
- artifact list
- stage booleans
- `dispatchable_truth_ready`

`dispatchable_truth_ready` is scoped to execution/package truth only.
It does not claim that lifecycle-required `design_compile` or `policy_compile` stages are complete; those remain separate readiness checks.
For `dispatchable` and `live` repos, `package compile` and `capacity compile` are lifecycle-required checks as well.

`/admin/details` now surfaces lifecycle and compile-readiness per project and per group so operator posture can distinguish modeled-but-not-runnable work from dispatchable work.

Fleet also compiles a public downstream artifact:

- `.codex-studio/published/PROGRESS_REPORT.generated.json`
- `.codex-studio/published/PROGRESS_HISTORY.generated.json`

The public `/progress` route renders from that generated artifact when present, with a live compile fallback for local/dev runs.

## Runtime-state touchpoints

`fleet-admin` reads and writes:

- `state/fleet.db`

Current runtime actions:

- pause/resume desired-state scheduling via `enabled`, with pause also interrupting an already running slice
- clear cooldown
- reset failures and last error for retry
- nudge a project back to `dispatch_pending` for run-now behavior

## Operator auth

- `/admin*`, `/api/admin*`, `/api/cockpit*`, `/studio*`, and `/api/studio*` are protected by the shared operator login when `FLEET_OPERATOR_AUTH_REQUIRED=true`.
- `GET /health` remains unauthenticated for container health checks.
- The login form is served from `GET /admin/login` and sets the shared operator session cookie used by both admin and studio.

## Bootstrap Project flow

The bootstrap flow currently collects:

- project ID
- repo path
- design doc path
- verify command
- account aliases
- initial queue
- feedback dir
- state file
- bootstrap toggle

Validation:

- repo path must be absolute
- repo path must live under `/docker`
- repo path must be visible inside the container
- project ID must be unique

Bootstrap behavior:

- create `feedback/` plus `.applied.log`
- create `.codex-studio/published/`
- create `scripts/ai/`
- seed `.agent-memory.md` if missing
- seed `.agent-state.json` if missing
- seed `scripts/ai/verify.sh` if missing

## Cockpit layout

The current `/admin` landing page is cockpit-first and condensed:

1. Posture / best-next-action hero
2. Group mission cards
3. Red-only incident rail
4. Pool runway with captain levers
5. Lamps plus per-category auto-heal controls and playbook context
6. Compact active-slices / review-gate / healer strips
7. Drawers for incident, group, and lamp context instead of page jumps for common operator actions
8. `/admin/details` for Projects, Groups, Reviews, Audit, Milestones, Accounts, Routing, History, Studio, and Settings

## Routing and healing posture

- routing classification now defaults to `evidence_v1`, using recent run outcomes as well as tier heuristics
- auto-heal is configured as explicit category playbooks with deterministic steps, optional LLM fallback, verify requirements, and bounded attempts
- review auto-heal thresholds are intentionally bounded (`review_stall_sla_minutes: 3`, `max_review_retriggers_per_head: 1`), with degraded-lane local fallback review after `45` minutes or `2` missed wake-up checks
- the scheduler maintains a floor of `2` active Codex workers; when no coding slice is dispatchable, it backfills with local review work first and queue-generation audits second
- runtime-complete groups are auto-signed off when there is no remaining refill, review, audit, or milestone backlog path

## Next steps

1. Keep `/studio` as the long-form workspace while trimming duplicate admin/studio surface area
2. Continue splitting the remaining admin monolith into thinner policy/API and bridge presentation layers after the new `admin/studio_views.py` extraction
3. Keep the public bridge compact while deepening operator-only drilldowns in `/admin/details`
4. Extend consistency guards from route wiring into stronger behavioral assertions around group/runtime transitions
5. Add drilldowns that compare published packet intent against later runtime/group outcomes across more than the current target/status summary

Current consistency guard:

- `python3 scripts/check_consistency.py` validates route semantics, review posture, account-alias truth, and the key project/group transition hooks across the split desired-state files.
