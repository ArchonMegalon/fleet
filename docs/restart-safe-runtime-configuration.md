# Restart-Safe Runtime Configuration

## Canonical Surface

The fleet supervisor runtime contract lives in:

- `/docker/fleet/config/projects/fleet.yaml`

Runtime environment files are overlays, not the source of truth:

- `/docker/fleet/runtime.ea.env`
- `/docker/fleet/runtime.env`

Operator environment variables intentionally win over project-config defaults. Use them for temporary overrides only; durable policy belongs in `config/projects/fleet.yaml`.

The host-default state root is `/docker/fleet/state/chummer_design_supervisor`. That path is writable for host-local runs and is the same persisted tree mounted into fleet containers as `/var/lib/codex-fleet`.

## Contract Sections

`supervisor_contract.shard_topology` defines the cold-start shard map:

- shard names and indexes
- default focus owners
- default focus profiles
- default focus text

`supervisor_contract.restart_safe_runtime` defines reboot-safe launcher state:

- canonical config surface
- documented operator contract
- runtime overlay files
- default state root
- default parallel shard count
- clear-lock-on-boot behavior
- generated state paths
- cold-restart validation command and expectations

`supervisor_contract.resource_policy` defines operating profiles:

- `maintenance` for low-pressure keepalive and unblock checks
- `standard` for normal closeout plus successor-wave throughput
- `burst` for explicit high-capacity operation when memory, credits, and queue breadth are healthy

`supervisor_contract.runtime_policy` remains as compatibility metadata for older tooling. New supervisor launcher behavior prefers `restart_safe_runtime` and `resource_policy`.

`queue` and `queue_sources` define the repo-local work posture. `WORKLIST.md` is the replace-mode worklist source, and `config/projects/fleet.yaml` carries structured package queue items.

## Launcher Behavior

`scripts/run_chummer_design_supervisor.sh` hydrates defaults from project config before validating runtime values:

- `CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT`
- `CHUMMER_DESIGN_SUPERVISOR_PARALLEL_SHARDS`
- `CHUMMER_DESIGN_SUPERVISOR_CLEAR_LOCK_ON_BOOT`
- `CHUMMER_DESIGN_SUPERVISOR_OPERATING_PROFILE`
- `CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_*`
- shard focus owner/profile/text groups
- worker lane/model fallbacks

If an environment variable is already set, the launcher preserves it. This keeps emergency operator overrides possible without making env files the durable policy source.

## Cold Restart Validation

Use the configured restart command:

```bash
docker compose -f /docker/fleet/docker-compose.yml up -d --force-recreate fleet-design-supervisor
```

After restart, validate:

- `state/chummer_design_supervisor/active_shards.json` is regenerated from `supervisor_contract.shard_topology` and launcher defaults.
- `host_memory_pressure` reflects the selected `resource_policy` profile.
- `completion_audit.repo_backlog_audit` does not report `WL-305` or `fleet-postclient-restart-safe-config` as active.
- stale completion receipts remain visible and cannot override current repo-local backlog proof.
- Shard focus routing still matches the configured shard topology.
- Stale completion receipts remain visible as proof problems instead of silently satisfying closeout.

## Default Posture

The default profile is `standard`.

`standard` currently starts 13 shards with a low per-shard memory budget and explicit warning/critical thresholds. `burst` is available for broader work when the host and provider lanes are healthy. `maintenance` is the fallback profile for pressure, provider instability, or narrow proof refresh work.
