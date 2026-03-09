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

### Health

- `GET /health`

### API

- `GET /api/admin/status`
- `GET /api/cockpit/summary`
- `GET /api/cockpit/attention`
- `GET /api/cockpit/workers`
- `GET /api/cockpit/runway`
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
- `POST /api/admin/routing/classes/{route_class}`
- `POST /api/admin/groups/{group_id}/captain`
- `POST /api/admin/groups/{group_id}/protect`
- `POST /api/admin/groups/{group_id}/drain`
- `POST /api/admin/groups/{group_id}/burst`
- `POST /api/admin/auditor/run-now`
- `POST /api/admin/groups/{group_id}/audit-now`
- `POST /api/admin/groups/{group_id}/pause`
- `POST /api/admin/groups/{group_id}/resume`
- `POST /api/admin/groups/{group_id}/signoff`
- `POST /api/admin/groups/{group_id}/reopen`
- `POST /api/admin/groups/{group_id}/refill-approved`
- `POST /api/admin/audit/tasks/{candidate_id}/approve`
- `POST /api/admin/audit/tasks/{candidate_id}/reject`
- `POST /api/admin/audit/tasks/{candidate_id}/publish`
- `POST /api/admin/audit/tasks/{candidate_id}/publish-mode`
- `POST /api/admin/studio/proposals/{proposal_id}/publish`

## Desired-state touchpoints

`fleet-admin` writes:

- `config/fleet.yaml`

Fields currently managed through the UI:

- `projects[].id`
- `projects[].path`
- `projects[].design_doc`
- `projects[].verify_cmd`
- `projects[].feedback_dir`
- `projects[].state_file`
- `projects[].enabled`
- `projects[].accounts`
- `projects[].runner`
- `projects[].queue`

## Runtime-state touchpoints

`fleet-admin` reads and writes:

- `state/fleet.db`

Current runtime actions:

- pause/resume next scheduling cycle by toggling desired-state `enabled`
- clear cooldown
- reset failures and last error for retry
- nudge a project back to `ready` for run-now behavior

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

The current `/admin` landing page is cockpit-first:

1. Mission Strip
2. Attention Center
3. Active Workers
4. Group Priority Ladder
5. Account Pressure and Pool Runway
6. Review and Approval Gate
7. Auditor card
8. Detail panes for Projects, Groups, Reviews, Audit, Milestones, Accounts, Routing, History, Studio, and Settings

## Current limitations

- pause still does not interrupt an already running slice; it affects subsequent dispatch
- queue editing is still artifact- and audit-driven rather than a raw inline queue editor
- Studio proposal approval is inline from admin, but Studio authoring itself still lives in `/studio`
- account “drain” is account-wide today; there is not yet a dedicated low-priority-only drain path

## Next steps

1. Add richer inline run inspection with log/final previews from the cockpit
2. Add saved filters and scopes for the detail panes
3. Add stronger per-account runway forecasting
4. Add deeper Studio session preview/edit controls from admin
5. Add validation for repo-local AI file completeness
