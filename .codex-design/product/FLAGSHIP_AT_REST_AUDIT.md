# Flagship At-Rest Audit

## Current strength

The user-facing Black Ledger and flagship shell work is close to release quality:

- real-Earth WebGL globe is in place
- action-heavy newsreel and seeded turn beats exist
- turn calculation and public watch routes are live
- Build Ghost feedback/report routing is present
- flagship shell, guide, UI, and media packages are already in flight

## Remaining gaps before true at-rest flagship quality

The remaining risk is operational and release-plane quality, not basic product direction.

### 1. Fleet control-plane truth still drifts

Observed repeatedly:

- `projects.status` falls out of sync with `runtime_tasks`
- honest active lanes relapse to `waiting_capacity`, `dispatch_pending`, or stale failed text
- the OODA operator has to manually re-run sync to restore truth

Self-heal audit finding:

- the fleet does have self-heal components, but they are not authoritative enough at the moment of runtime mutation
- `sync_project_progress_from_packages()` is only reached from selected package-status and operator paths, not as a guaranteed consequence of every runtime-task transition
- the keeper can repair `stale_inactive` rows on a pass, but that is periodic repair, not immediate convergence
- the recurring `hub` drift proves the current design can repair truth after the fact, but does not yet keep it converged by default

At-rest design target:

- runtime-task insert/update/delete must trigger project-truth reconciliation deterministically
- controller restart, orphan requeue, stale-worker cleanup, and package launch must all end in the same project/runtime/package truth without waiting for the next keeper pass
- self-heal should be measured by soak receipts, not by whether a human can resync the rows manually

At-rest requirement:

- controller, admin, and keeper must converge on the same live runtime truth
- stale rows must self-heal without operator intervention
- completed lanes must stay complete, and queued lanes must stay honestly queued

### 2. ETA and status publication are not authoritative enough

Observed repeatedly:

- `status-lite` is unavailable, stale, or wrong
- fallback ETA is sometimes the only signal
- humans have to inspect the DB directly to know whether the fleet is progressing

At-rest requirement:

- a live status endpoint must stay up
- ETA must be machine-published and clearly sourced
- runtime, queue, and blocker counts must match DB truth without operator correction

### 3. Credit and billing truth are not flagship-grade yet

Observed repeatedly:

- local refresh plumbing can run, but upstream billing refresh is slow/stale
- runtime aggregate can be freshly written while still carrying stale-cache provenance
- top-up fields remain unreliable

At-rest requirement:

- refresh path must have one authoritative source of truth
- stale cache fallback must be clearly marked and bounded
- credit authority, next top-up, and billing freshness must be publishable without manual investigation

### 4. Live release truth still needs final convergence gates

Recent release work materially improved this, but it is still the last category that can damage trust.

At-rest requirement:

- canonical downloads truth, surface refs, install-aware registry, and desktop route truth must converge from one authoritative graph
- local bundle truth, live shelf truth, and final verifier truth must agree or fail before publish
- flagship release readiness should fail closed when operations are not at rest

## Fleet packages queued from this audit

- `next90-m147-fleet-rest-state-convergence`
- `next90-m147-fleet-credit-authority-hardening`
- `next90-m147-hub-live-release-truth-hardening`
- `next90-m147-fleet-at-rest-readiness-gates`
- `next90-m147-fleet-rest-soak-proof`

## Release bar

Do not call the whole system flagship-grade just because the backlog drains.

Call it flagship-grade only when:

- product surface quality is strong
- control-plane truth is self-healing
- ETA/status publication is trustworthy
- credit/billing authority is fresh enough to operate without manual DB archaeology
- live release truth is closed under canonical verification
