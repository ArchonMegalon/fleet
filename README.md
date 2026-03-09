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
- group-first operations views
- account, routing, and project policy controls
- signoff, refill, audit-now, and publish actions
- group run history and publish history

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

Studio defaults to `acct-studio-a` and then falls back to `acct-shared-b`, but you can change that in `config/fleet.yaml`.

Project routing now supports:
- preferred / burst / reserve account lanes
- Spark eligibility filtering
- group captain policy for priority, service floors, and shed order
- slice-boundary refill from approved auditor tasks
- GitHub-backed Codex review gating after local verify

## GitHub review lane

Fleet review now defaults to a GitHub-native lane instead of local `codex exec` review.

The runtime flow is:

1. worker finishes a coding slice and passes local verify
2. fleet commits and pushes a review branch
3. fleet creates or updates a draft PR
4. fleet requests Codex review with `@codex review ...`
5. fleet ingests PR review findings back into project feedback and operator views

Important constraints:
- the separate review bucket comes from GitHub Codex review, not from a local prompt like `review my code`
- local review should be treated as fallback-only
- queue advance is gated on the GitHub review result when project review is enabled

The controller and admin containers read GitHub auth from a mounted `hosts.yml` at `/run/gh/hosts.yml`, typically provided from `${HOME}/.config/gh`.

## Deploy

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

Check Studio sessions:

```bash
curl http://127.0.0.1:18090/api/studio/status
```

Request or sync a review manually:

```bash
curl -X POST http://127.0.0.1:18090/api/projects/core/review/request
curl -X POST http://127.0.0.1:18090/api/projects/core/review/sync
```

Connect an existing Cloudflare container to the shared network once:

```bash
docker network connect codex-fleet-net <cloudflared-container>
```

## Recommended admin flow

1. Open `/admin` to review groups, queues, account pressure, and audit findings.
2. Run `Audit Now` or `Refill Approved Tasks` from the relevant group if queues are exhausted.
3. Open `/studio` for a project, group, or fleet target when you need scoped design or planning help.
4. Review the proposal and publish approved artifacts or coordinated multi-target outputs.
5. Use `/admin` review controls to request or sync GitHub Codex review when a repo needs an explicit re-review.
6. Let the spider continue coding slices; it will ingest published runtime instructions, feedback notes, review findings, and queue overlays automatically.
