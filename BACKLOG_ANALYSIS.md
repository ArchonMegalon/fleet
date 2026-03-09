# Full Backlog Analysis

Snapshot date: 2026-03-08

Update: after this snapshot, the latent UI and Hub milestone backlogs were materialized into repo-native `WORKLIST.md` queue items so the fleet can schedule them directly. The snapshot counts below still describe the pre-materialization state that motivated that change.

## Scope

This report distinguishes between:

- scheduler-visible backlog: what the fleet is currently queued to run
- explicit repo backlog: work tracked in repo-native queue files
- latent roadmap backlog: work still present only in design docs and not yet decomposed into executable queue items

Sources used:

- `/docker/fleet/config/fleet.yaml`
- `/docker/chummercomplete/chummer-core-engine/WORKLIST.md`
- `/docker/chummercomplete/chummer-presentation/WORKLIST.md`
- `/docker/chummercomplete/chummer.run-services/WORKLIST.md`
- `/docker/EA/TASKS_WORK_LOG.md`
- `/docker/EA/MILESTONE.json`
- `*.design.v2.md` design docs for core, presentation, and run-services
- live fleet state from `/api/status` and `fleet.db`

## Scheduler-visible backlog snapshot

At the time of this snapshot, the fleet saw:

- `core`: `running`, queue `5`, index `1`, remaining `4`
- `ui`: `blocked`, queue `6`, index `0`, remaining `6`
- `hub`: `running`, queue `6`, index `4`, remaining `2`
- `ea`: `running`, queue `124`, index `5`, remaining `119`

Total scheduler-visible remaining slices: `131`

Important: this is not the same as full product completion. It is only the currently materialized queue the fleet knows how to execute.

## Repo-by-repo findings

### core-engine

Explicit tracked backlog:

- `WORKLIST.md` contains `63` `done` items
- `WORKLIST.md` contains `0` `queued`, `0` `in_progress`, `0` `blocked`

Design backlog status:

- design milestones `A1` through `A5` exist in `chummer-core-engine.design.v2.md`
- the worklist also records those milestone families as completed

Interpretation:

- core does not have an unserved queue in `WORKLIST.md`
- the remaining core work is the fleet's coarse post-worklist execution queue:
  - Isolation and compile recovery
  - Contract hardening
  - Structured Explain API hardening
  - Runtime/RulePack determinism hardening
  - Backend primitives for Build Lab / ledger / timeline / validation / explain hooks
- this means core is not “done”, but its remaining backlog is currently tracked at a coarse integration/hardening level rather than a decomposed task ledger

### presentation

Explicit tracked backlog:

- `WORKLIST.md` contains `53` `done` items
- `WORKLIST.md` contains `0` `queued`, `0` `in_progress`, `0` `blocked`

Latent roadmap backlog:

- design milestones `B1` through `B6` remain the real product backlog shape:
  - Explain Everywhere UI
  - Browse + virtualization
  - Build Lab UI
  - GM Board + Spider Feed
  - Session local-first shell
  - Artifact viewer suite

Interpretation:

- presentation's repo-native worklist is effectively a historical completion ledger, not the current feature backlog
- the fleet only sees `6` coarse slices, but the design doc still describes a larger unmaterialized backlog
- this is one of the main reasons the current ETA reads far too optimistic

### run-services / Hub

Explicit tracked backlog:

- `WORKLIST.md` contains `53` `done` items
- `WORKLIST.md` contains `0` `queued`, `0` `in_progress`, `0` `blocked`

Latent roadmap backlog:

- design milestones `C1` through `C7` remain the real product backlog shape:
  - Hub persistence and immutability
  - AI gateway and prompt lab
  - Portrait Forge + packet factory
  - Session Memory Engine
  - Spider Feed and OODA
  - Lore Lens and persona retrieval
  - News/route/media suite

Interpretation:

- Hub is in the same state as presentation: the repo worklist is historical, while the design doc still carries the real undecomposed roadmap
- the fleet currently sees only `6` coarse slices, so any ETA for Hub is an execution ETA for those slices, not a credible product-completion ETA

### EA

Explicit tracked backlog:

- `TASKS_WORK_LOG.md` contains `314` `done` items
- `TASKS_WORK_LOG.md` contains `0` active queue items and `0` blocked items

Milestone backlog:

- `MILESTONE.json` contains `7` `released` capabilities
- `MILESTONE.json` contains `124` `tested` but not `released` capabilities

Interpretation:

- EA's task log is effectively exhausted
- EA's real remaining backlog is the milestone-promotion backlog, and that is already feeding the fleet queue
- this is the only repo where the scheduler currently sees a large explicit backlog source that matches the product state reasonably well

## What this means

1. The fleet ETA is currently an execution ETA for the configured queue, not a product ETA.
2. EA is the only project with a large explicit backlog source currently wired to the scheduler.
3. Presentation and Hub have substantial latent backlog in design docs that has not been decomposed into queue items.
4. Core has a smaller but still coarse remaining backlog: the worklist milestones are done, but the fleet still has integration/hardening slices left.
5. A “16 weeks” intuition is compatible with the evidence if you mean product completion across the unmaterialized presentation/Hub roadmap, not just the current queue.

## Recommended next actions

1. Relabel ETA everywhere as `Configured Queue ETA` until the latent roadmap is materialized.
2. Expand presentation milestone `B1-B6` into repo-native queue items in `WORKLIST.md`.
3. Expand Hub milestone `C1-C7` into repo-native queue items in `WORKLIST.md`.
4. Decide whether core's remaining coarse slices should also be decomposed into task-level worklist items.
5. Keep EA on milestone-capability queue sourcing, since that is already the most truthful explicit backlog in the fleet.

## Bottom line

The full backlog is not “5 core slices + 6 UI slices + 6 Hub slices + EA promotions”.

It is:

- a small coarse execution backlog in `core`
- a large undecomposed design backlog in `presentation`
- a large undecomposed design backlog in `run-services`
- a large explicit milestone-promotion backlog in `EA`

Until presentation and Hub roadmaps are decomposed into executable queue items, any ETA shown by the fleet should be treated as queue burn-down only, not total product completion.
