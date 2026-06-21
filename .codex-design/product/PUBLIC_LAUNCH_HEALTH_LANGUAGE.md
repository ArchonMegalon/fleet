# Public launch-health language contract

## Purpose

This document defines one shared launch-health vocabulary for all Chummer public surfaces.
It exists so `/downloads`, help, terms pages, update copy, and release status can agree on
what users can act on right now versus what is still blocked, staged, or no longer safe.

## Core launch postures

Use the exact posture terms in public-facing copy and ticket handoff summaries:

- `live`: Recommended public route and entitlement is currently available for the stated platform and account posture.
- `preview`: Official public route exists, but scope, compatibility, or confidence is still bounded and explicitly preview-labeled.
- `fallback`: A secondary route that remains usable when the main route is unavailable, unsupported for a platform, or support-directed.
- `fixed`: A specific issue or bug is resolved on the same user-facing route, channel, and platform where the user is currently attempting to work.
- `revoked`: A previously safe route, version, or claim was intentionally withdrawn and should no longer be treated as usable guidance.
- `blocked`: A route exists in product plans or artifacts but is temporarily not usable for the described audience/platform/channel.

## Posting posture rules

- If a feature or route is `live`, say it is the recommended copy path for normal users.
- If a feature or route is `preview`, say why it is still bounded (compatibility, breadth, confidence, or support scope).
- If a feature or route is `fallback`, explicitly mark it as secondary and keep it operational so users can still complete tasks.
- Use `fixed` only when the fix is actually available on the same route/channel/platform and not merely merged or prepared in branch.
- Use `revoked` immediately when a route, head, or rollout state is pulled from active recommendation.
- Use `blocked` when the copy would otherwise mislead users into expecting a currently unavailable route.
- Never assert two competing postures for the same platform/route in the same claim block.

## Surface rules

Public-facing launch-health statements must include:
Public launch-health language must distinguish live confidence from preview safety, and never conflate fallback or blocked routes with fixed routes.

- A single canonical route posture for each major action (`install`, `recover`, `update`, `report`).
- An explicit note if any route is blocked, including the reason bucket:
  - unsupported platform
  - unsupported entitlement state
  - maintenance window
  - temporary release-pipeline guard
- A short path to the supported action (`go`, `contact`, or `support`) so the user can proceed without guessing.
- A stable posture vocabulary across release shelf, auto-update language, and help copy.

## Forbidden launch-health claims

- Calling a `preview`, `fallback`, or support-only path the same as a `live` route.
- Labeling a route `fixed` when registry and user channel checks still show it as unavailable.
- Treating revoked routes as still active in download, support, or status surfaces.
- Treating blocked routes as "just a little slow" while removing practical call-to-action.

## Copy examples

### Allowed

- "Windows installer is **live**."
- "macOS install command is **preview** and account-gated."
- "Raw archives remain **fallback** for local support flows."
- "A previous version has been **revoked** for this platform."
- "Linux package generation is temporarily **blocked** while we finish startup-safety checks."

### Forbidden

- "Archive packages are the normal route" (when installer is the only canonical route).
- "The route is fixed" (when only a branch or future channel has it).
- "No route is blocked" (when rollout or entitlement currently blocks users).

## Coupling to ownership

- `public_health_posture_posture` and launch-copy governance stay with `chummer6-design`.
- `chummer6-hub` and `fleet` project route projection and rollouts remain authoritative for channel truth.
- `chummer6-hub-registry` project owns promote, revoke, and pause state.
- `chummer6-ui` owns recovery and local update UX behavior once the route is selected.

## Evidence and closure anchor

Updates for this task should be treated as closed only when:

- This file appears in registry evidence for work task `120.5`.
- Every public-facing copy reference uses the same posture terms without contradiction.
- Queue closure includes `frontier_id: 1708070943`, `completion_action: verify_closed_package_only`,
  and an evidence list that includes registry row, queue rows, validator, and this closeout note.
