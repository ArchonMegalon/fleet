# Program Truth-Convergence Audit

Date: 2026-03-16
Scope: Chummer6, chummer6-design, chummer6-core, chummer6-ui, chummer6-mobile, chummer6-hub, chummer6-ui-kit, chummer6-hub-registry, chummer6-media-factory, fleet, executive-assistant.

Use this as backlog input for Fleet coordination work. This is not a code-review finding set; it is a repo-surface and program-truth audit that should drive queue shaping, status generation, and cross-repo convergence work.

## Program-level verdict

- The architecture is coherent.
- The org still has a truth-convergence problem.
- Central design owns precedence, boundaries, package ownership, and milestone exits, but release blockers remain `A0`, `A1`, `A2`, `C1`, and `D1`.
- Public readiness is still narrated inconsistently across the guide, release shelf, Fleet deployment model, and live access posture.
- Treat the program as on vision but under-converged.

## Priority order to enforce

1. Design + Fleet + Guide: unify public-status truth first.
2. Core + Hub + Mobile: close `A1`, `A2`, and `D1` with visibly single-owned semantics and wrapper-only transport layers.
3. Hub + Hub-registry + Media-factory: finish owner transfer, not just package existence.
4. UI + UI-kit: make the tree and dependency graph prove the split.
5. EA: harden runtime truth while remaining subordinate to design canon.

## Fleet-specific changes

- Stop hand-maintaining a second architecture brain.
- Generate program milestones, public status, and lifecycle posture from `chummer6-design` canon plus repo verification evidence.
- Export one canonical public-status payload and make the guide and EA consume it.
- Reconcile lifecycle language across `scaffold`, `dispatchable`, `live`, boundary-purity scores, and public-promotion states.

## Guide-specific changes that Fleet should drive

- Replace handwritten readiness prose with generated status input.
- Split public status into three labels:
  - `installability`
  - `promotion_state`
  - `access_posture`
- Keep the guide signoff-only and downstream-only.

## Core / Hub / UI / Mobile / ui-kit / registry / media cues that affect Fleet queue shaping

- Core: tree still signals mixed ownership; boundary closure must include repo-shape verification.
- UI: `B2` is root surgery, not feature work; repo body still overclaims legacy presentation ownership.
- Mobile: remaining work is cross-repo canon, not local features.
- Hub: active tree still source-owns media/registry seams that central canon says belong elsewhere.
- UI-kit: success is downstream duplication becoming impossible, not package internals alone.
- Hub-registry: package extraction is not closure until read/write authority visibly leaves hub.
- Media-factory: shift from scaffold evidence to clearly running service proof.

## EA-specific guardrail

- EA should not become a second product-definition engine for Chummer.
- Chummer-specific EA skills must consume canonical design and canonical public-status inputs, not infer product truth ad hoc from repo surfaces.

## Working rule for Fleet coding slices

When a slice touches readiness language, lifecycle posture, public targets, blockers, milestone truth, or cross-repo authority claims:

- prefer generated canonical inputs over handwritten repo-local prose
- treat repo-local “done” claims as suspect unless they align with central canon
- avoid introducing new truth summaries in Fleet when a generated artifact can carry the same meaning

## Concrete backlog implications

- Add generated public-status export for guide and EA consumers.
- Add an explicit status taxonomy that distinguishes:
  - `repo_local_complete`
  - `package_canonical`
  - `boundary_pure`
  - `publicly_promoted`
- Audit Fleet config and dashboard language for stale split-era names and parallel readiness claims.
