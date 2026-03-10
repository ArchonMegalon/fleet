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

- `GET /admin`
- `GET /admin/`
- `GET /admin/login`
- `GET /admin/details`
- `GET /studio`
- `GET /studio/`

### Health

- `GET /health`

### API

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
- `POST /api/admin/studio/proposals/{proposal_id}/publish`

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

Fleet now treats Studio publication as a three-stage compile pipeline:

1. design compile
2. policy compile
3. execution compile

Each Studio publish writes `.codex-studio/published/compile.manifest.json` with:

- schema version
- target type and target id
- target lifecycle
- artifact list
- stage booleans
- `dispatchable_truth_ready`

`/admin/details` now surfaces lifecycle and compile-readiness per project and per group so operator posture can distinguish modeled-but-not-runnable work from dispatchable work.

## Runtime-state touchpoints

`fleet-admin` reads and writes:

- `state/fleet.db`

Current runtime actions:

- pause/resume next scheduling cycle by toggling desired-state `enabled`
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

## Current limitations

- pause still does not interrupt an already running slice; it affects subsequent dispatch
- queue editing is still artifact- and audit-driven rather than a raw inline queue editor
- Studio proposal approval is inline from admin, but Studio authoring itself still lives in `/studio`
- account “drain” is account-wide today; there is not yet a dedicated low-priority-only drain path

## Next steps

1. Add richer inline run inspection with log/final previews from the cockpit
2. Continue compressing the bridge to the smallest viable command surface
3. Expand runway sufficiency and finish forecasting across groups and pools
4. Split the remaining admin monolith into thinner policy/API and bridge presentation layers
5. Add deeper Studio session preview/edit controls from admin
