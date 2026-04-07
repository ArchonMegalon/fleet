# LOCAL CO-PROCESSOR

## Table pain

Some explain, search, and media-assist workloads are slower, costlier, or more privacy-sensitive when every request has to round-trip through hosted compute.
The product still cannot require every user to run local compute, because the canonical experience must keep working on hosted-only installs and constrained devices.

## Bounded product move

Chummer will allow optional local acceleration or lightweight host strategies where they improve responsiveness, privacy, or cost.
The move is not to make local compute the default product path.
It is to keep hosted-first parity intact while making local acceleration a removable enhancement that can be turned off without breaking the product.
No canonical truth may depend on local runtime availability.

## Owning repos

* `chummer6-core` - portable deterministic engine host strategy, runtime truth, and fallback semantics
* `chummer6-ui` - desktop/workbench entry points, local-acceleration controls, and explain/search/media-assisted surfaces
* `chummer6-mobile` - portable session shell, offline-safe behavior, and any device-local acceleration affordances

## LTD / tool posture

* no mandatory external tool
* optional bounded use of `1min.AI`, `AI Magicx`, or other helpers only when they stay behind adapters and evidence capture
* owned LTDs and external tools may assist with acceleration evidence, drafting, or preview generation, but they do not become product truth or a required runtime
* local compute is an implementation choice, not a promotion dependency

## Dependency foundations

* portable deterministic engine host strategy
* hosted-first parity across explain, search, and media-assist flows
* explicit non-mandatory local runtime policy
* disableable local acceleration paths
* stable adapter boundary between hosted canonical truth and local computation
* clear fallback behavior when local runtime is absent, slow, or fails

## Current state

This lane is still a horizon.
Chummer can describe optional local acceleration, but it does not yet prove that the same journeys stay equivalent when local compute is absent, constrained, or disabled.
The portable host strategy, fallback semantics, and parity evidence are not yet strong enough to make local acceleration a foundation promise.

## Eventual build path

1. Core defines the portable deterministic engine host strategy and the minimum local-acceleration hooks it can expose.
2. UI and mobile wire optional local acceleration into explain, search, and media-assist entry points behind explicit user-visible controls.
3. Hosted-only mode remains fully functional and canonical truth stays hosted.
4. Fleet and the other execution surfaces can observe, measure, and prove local-versus-hosted parity without turning the local lane into a requirement.
5. Release promotion only happens after the local lane has shown measurable latency, cost, or privacy benefit without breaking fallback behavior.

## Why it remains a horizon

Local acceleration is only a win if it stays optional.
Until Chummer can prove that local compute improves the product without becoming a hidden requirement, this stays a horizon rather than a foundation promise.

## Flagship handoff gate

Local co-processor may leave horizon status only when a representative explain, search, or media-assist workflow can be run in both hosted-only and local-accelerated modes with:

* identical canonical outputs or explicitly bounded deltas
* the local runtime fully absent or disabled and the workflow still completing
* no canonical truth or saved artifact depending on local runtime availability
* a documented fallback path for slow, missing, or failed local compute
* measurable latency, cost, or privacy improvement in the local lane
* the same user journey available on desktop-first and mobile/session surfaces where applicable

If that gate cannot be passed, the lane stays a horizon and does not become a flagship promise.
