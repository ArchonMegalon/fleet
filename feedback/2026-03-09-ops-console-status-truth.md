# Fleet Ops Console and Status Truth Feedback

Date: 2026-03-09

## Core direction

- Replace misleading `complete` language with `queue_exhausted`.
- Expose `why stopped`, backlog source health, next action, and unblocker as first-class runtime fields.
- Treat `/admin` as an operator console before it is an inventory registry.
- Surface stopped-but-not-signed-off projects, blocker groups, cooldowns, account pressure, and runs needing attention on the first screen.
- Provide an explicit refill path from audit findings and approved task candidates instead of silently parking exhausted queues.

## Concrete asks

1. Add `stop_reason`, `queue_source_health`, `backlog_source`, `next_action`, and `unblocker` to project status payloads.
2. Make `queue_exhausted` visible everywhere users currently see queue state.
3. Add manual auditor and group refill controls to `/admin`.
4. Keep account and routing controls on the first screen.
5. Preserve the distinction between queue exhaustion and product signoff.
