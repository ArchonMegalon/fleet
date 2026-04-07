# ONRAMP

## The problem

New, rusty, and skeptical users can hit a wall of jargon, legality, and build-state ambiguity before they feel Chummer is helping them.
The product may be correct and still feel punishing at the table.

## Table pain

* build legality is hard to read in the moment
* "what do I do next?" feels like folklore instead of guidance
* a mistake can make the build feel brittle, not recoverable
* returning users need reorientation, not another full rules lecture
* trust drops fast if advice outruns engine truth

## What it would do

ONRAMP would add a guided-mastery layer for Chummer:

* coached starter builds and edition-aware primers
* "why this next?" guidance grounded in actual rules and current build state
* recovery suggestions when a build becomes illegal, weak, or contradictory
* progressive disclosure that teaches the mental model instead of only hiding complexity

It is a learning-and-confidence horizon, not an auto-build black box.

## Bounded product move

The bounded move is to add one explainable coaching seam at the start of build flow and one recovery seam when the build goes sideways.
ONRAMP should narrow confusion, not expand automation.
It must always show the reason, the rule state, and the narrow set of safe next actions.

## Likely owners

* `chummer6-ui`
* `chummer6-core`
* `chummer6-hub`

## LTD/tool posture

* Assistive drafting tools may help with primer copy, example narration, and sample walk-through text.
* Deterministic engine truth, legality, and recovery advice stay authoritative.
* No tool may silently choose, repair, or auto-advance a build.
* Owned LTDs may support bounded content or capture helpers, but they do not become the product decision layer.

## Dependency foundations

* explain receipts that ordinary users can follow
* starter-lane shells and sample builds
* bounded recommendation seams instead of implicit UI folklore
* reliable legality and conflict detection
* metrics that prove the primary build path is already stable

## Current state

The required foundations exist only in pieces today.
Chummer can already prove parts of the rules, receipts, and recovery posture, but the calm first-run coaching lane is not stitched together as a single flagship experience.
Until those pieces are joined into one deterministic flow, ONRAMP remains a horizon instead of a shipped promise.

## Eventual build path

1. Lock the starter lane around a small number of sample shells and edition-aware primers.
2. Add explainable recommendation seams in UI that always cite deterministic state.
3. Add recovery guidance for illegal or contradictory builds without hiding the underlying break.
4. Teach the same flow through Hub-supported help, examples, and support handoffs.
5. Promote only after the first-run path is stable enough to carry flagship traffic.

## Why it is still a horizon

Guided mastery only helps if it is trustworthy, calm under error, and explicit about why each suggestion exists.
That requires stronger explain receipts, starter-flow discipline, and recovery semantics than the product can yet prove at release quality.
ONRAMP stays parked until Chummer can carry beginners and returners without leaning on tutorial theater or hidden automation.

## Flagship handoff gate

ONRAMP may move from horizon to flagship only when a non-expert can:

* start in a starter shell
* complete a legal starter build
* recover from an introduced legality break
* ask "why this next?" and get a citation-backed answer from deterministic truth
* finish without any hidden auto-choice, unsupported advice, or unexplained correction
* do all of the above on the primary build path while release metrics stay stable
