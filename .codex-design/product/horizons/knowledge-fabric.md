# KNOWLEDGE FABRIC

## Table pain

Rules answers are expensive, repetitive, and too easy to hallucinate when every help or assistant lane has to reconstruct the same understanding from raw materials on demand.

## Bounded product move

Chummer will build knowledge projections from core-owned source packs and engine truth.
Those projections may include chunks, embeddings, graph edges, searchable receipts, citations, and explain helpers, but they remain derived artifacts rather than a second source of truth.

The product move is not a new canonical rules brain.
It is a grounded explainability layer that can answer, cite, and route, while mechanics authority stays in core.

## Owning repos

* `chummer6-core` - owns engine truth, receipts, and the source packs that projections must derive from
* `chummer6-hub` - owns hosted orchestration, surfaced help/explain entry points, and the user-facing projection shell
* `chummer6-ui` - owns interactive workbench surfaces that render projections, citations, and explain helpers

## LTD / tool posture

* `Prompting Systems` - explain and prompt-shaping support
* `Documentation.AI` - downstream docs/help projection
* `AI Magicx` - bounded synthesis support
* `1min.AI` - bounded specialist explain/generation support
* `BrowserAct` - bounded capture and operator fallback
* `Paperguide` - cited research helper

Owned LTDs and external tools may assist with capture, drafting, or explanation, but they do not become the product decision layer or a second source of truth.
No tool is allowed to compute mechanics outside core.

## Dependency foundations

* core-owned source packs and receipts
* explain provenance canon
* explicit "AI never computes mechanics" rule
* derived-projection storage and publication rules
* surfaced answers must preserve their derivation trail
* fallback behavior must fail closed when receipts or provenance are missing

## Current state

This lane is still a horizon.
The current system can describe the goal, but it does not yet prove that every answer flow stays visibly derived, cited, and non-authoritative across the whole help and assistant path.

## Eventual build path

1. Core publishes stable source packs, receipts, and provenance.
2. The projection pipeline derives searchable answer artifacts from that truth.
3. Hub and UI expose those artifacts as grounded help and assistant surfaces.
4. Any mechanics-sensitive claim routes back to core truth instead of being recomputed in the surface layer.
5. Projection traces, citations, and refusal paths are validated against representative rules questions before broader use.

## Why it remains a horizon

This lane is only safe when the projections are visibly derived, cited, and non-authoritative.
Until Chummer can prove that help and assistant flows stay grounded in core-owned truth, knowledge fabric remains a horizon rather than a product promise.

## Flagship handoff gate

Knowledge fabric may leave horizon status only when a representative rules question can be answered end to end from core-owned source packs with:

* a visible derived-projection trail
* citations attached to the surfaced answer
* no mechanics computed outside core
* a refusal or core-redirect path when provenance is missing or ambiguous
* the same grounded answer reproduced through both hosted and workbench entry points

If that gate cannot be passed, the lane stays a horizon and does not become a flagship promise.
