# Fleet Admin Spec

## Purpose

`fleet-admin` is the write-capable desired-state and operations surface for Codex Fleet.

It exists so:

- YAML remains desired state
- SQLite remains runtime state
- operators stop hand-editing config files for routine project/account/routing work

## Service boundary

`fleet-admin` is a fourth service behind the existing gateway.

It owns:

- project-registry writes to `config/fleet.yaml`
- account/routing visibility from config
- runtime controls against `fleet.db`
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
- `POST /api/admin/projects/add`
- `POST /api/admin/projects/{project_id}/pause`
- `POST /api/admin/projects/{project_id}/resume`
- `POST /api/admin/projects/{project_id}/clear-cooldown`
- `POST /api/admin/projects/{project_id}/retry`
- `POST /api/admin/projects/{project_id}/run-now`

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
- nudge a project back to `idle` for run-now behavior

## Add Project wizard

The wizard currently collects:

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

## Page layout

The first implementation of `/admin` has:

1. Global summary and YAML/runtime-state explanation
2. Add Project wizard
3. Projects table with runtime status and control actions
4. Accounts table
5. Spider tier-preference table
6. Spider price-table view
7. Recent runs table with links into controller logs/finals

## Current limitations

- account create/edit is read-only today
- studio publication review is visibility-only through the per-project published-file list
- pause does not interrupt an already running slice; it prevents subsequent scheduling
- queue editing for existing projects is still file-level/manual outside the wizard

## Next steps

1. Add project edit and queue-edit UI
2. Add account create/edit UI
3. Add explicit studio publication approve/reject workflow
4. Add richer run inspection with inline logs/finals
5. Add validation for repo-local AI file completeness
