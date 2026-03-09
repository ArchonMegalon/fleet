# Fleet Feedback: Auditor And Group Runtime

Date: 2026-03-09
Applies to: `fleet`

## Bottom line

The repo improved structurally, but the parts that matter most are still only partly operative:

- `project_groups` exist in config
- group status and ETA render in controller and admin
- `program_milestones.yaml` exists
- but scheduling still needs real group runtime semantics
- there is still no `fleet-auditor` service
- and Studio is still project-scoped rather than target-scoped

This means the Chummer repos are not yet a true lockstep program runtime. They are still separate project schedulers with a group-aware read model layered on top.

## Immediate fleet backlog

1. Make groups first-class runtime entities.
   Add persistent group runtime state such as group phase, blockers, publish events, and coordinated run readiness.

2. Enforce lockstep scheduling semantics.
   Group readiness must gate member dispatch. Contract blockers and runtime readiness need to stop independent advancement.

3. Add a real auditor subsystem.
   It should scan repos read-only for contracts, DTOs, event names, route coverage, queue coverage, and milestone coverage, then publish findings and candidate tasks.

4. Upgrade Studio from project-scoped to target-scoped.
   The runtime should support `target_type: project | group | fleet` and roles including `program_manager`, `contract_steward`, and `auditor`.

5. Add multi-target publish.
   Studio should be able to publish one approved proposal into group artifacts plus per-project feedback notes and queue overlays together.

## Minimal milestone plan

- M1: make groups real with runtime state and scheduler gates
- M2: add `fleet-auditor` runtime and findings tables
- M3: make Studio target-scoped and role-complete
- M4: add multi-target publish and approval flow
- M5: add deterministic contract extraction and drift detection

## Program instruction

Treat this as operative fleet work, not only dashboard polish.

The next layer is not more worker throughput. It is a real group runtime, a real auditor, group-aware Studio sessions, and multi-target publish.
