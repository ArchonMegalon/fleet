# QUICKSILVER

## The problem

Chummer can be powerful without feeling flagship-fast.
If expert users still wait on screens, fight click friction, or lose flow during dense edits, the workbench stays capable but not elite.

## Horizon discipline

| Aspect | Discipline |
| --- | --- |
| Pain | Expert users lose flow to screen waits, click friction, context loss, and repetitive mechanical work in dense build/inspect sessions. |
| Bounded product move | Turn the workbench into a shortcut-first, command-surface, low-latency expert lane for build and inspect work. |
| Owning repos | `chummer6-ui`, `chummer6-ui-kit`, `chummer6-core` |
| LTD / tool posture | No external tool is required for the core horizon. Local profiling, telemetry, and benchmark helpers may support tuning, but the speed model must stay owned by the app. |
| Dependency foundations | Explicit interaction latency budgets, dense-state virtualization, keyboard and command seams, batch-safe editing, undo and cancel-safe transactions, and ruleset-specific composition seams. |
| Current state | Chummer still lacks boringly reliable proof that dense workbench flows stay fast and trustworthy under stress. |
| Eventual build path | Tighten UI command seams, add context-preserving split and pin surfaces, harden search / compare / jump, and prove the flows against real dense data. |
| Why it is still a horizon | Speed can still break legality, explainability, or the guided path if it is built before the foundations are stable. |
| Flagship handoff gate | Promote only when supported expert flows meet explicit latency budgets in real workbench scenarios, preserve undo / cancel safety, keep the guided path intact, and satisfy flagship release acceptance without unsafe caching or stale state. |

## What it would do

QUICKSILVER would turn the workbench into a true expert-speed surface:

* command-surface and shortcut-first flows for common build and inspect tasks
* near-instant search, compare, and jump behavior
* batch-safe edit patterns for repetitive mechanical work
* split and pinned inspection surfaces that preserve context under pressure

It is not a different rules engine.
It is the speed and command horizon for the same trusted product truth.

## Likely owners

* `chummer6-ui`
* `chummer6-ui-kit`
* `chummer6-core`

## Hard boundary

* not a command surface that hides legality or explainability
* not speed theater built from unsafe caching or stale state
* not keyboard-only elitism that breaks the primary guided path

## Why it is not ready yet

Chummer still needs stronger present-tense proof that dense workbench flows stay trustworthy and fast under stress.
Until that foundation is boringly reliable, QUICKSILVER remains a horizon rather than a release claim.
