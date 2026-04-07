# RUN CONTROL

## The pain

Even when Chummer already does a good job on character truth, a GM still ends up stitching the table together with notebooks, chats, spreadsheets, memory, and after-the-fact recaps.
That leaves Chummer adjacent to table control instead of being the surface that actually holds the session together.

## The bounded product move

RUN CONTROL is the future GM operations surface for Chummer.
It would keep session prep, roster, agenda, scene state, live control, recap, dossier, and publication handoff inside one bounded campaign workspace instead of scattering them across tools.

That is a focused table-control move, not a generic collaboration suite and not a rewrite of the rules engine.

## Owning repos

* `chummer6-hub`
* `chummer6-mobile`
* `chummer6-core`
* `chummer6-media-factory`

## LTD / tool posture

Limited tooling is acceptable only as a derivative layer.
Bounded summary, recap, and publication helpers may assist the workflow, but they must never replace the canonical campaign, roster, session, or continuity truth.

Any tool posture that hides state, invents parallel session memory, or behaves like a general-purpose team workspace is outside scope.

## Dependency foundations

RUN CONTROL depends on these foundations being real first:

* durable campaign and runner state
* device-role and entitlement posture
* reconnect-safe live continuity
* recap and dossier pipelines with receipts
* publication seams that can carry campaign outputs without losing provenance

## Current state

The product has not yet proven those foundations at release quality.
Today this remains a horizon because the live table must be boringly reliable before it can be the place people trust for the whole session.

## Eventual build path

The eventual build path is:

1. establish durable campaign, roster, and session truth
2. make live reconnect and device handoff trustworthy
3. attach recap, dossier, and publication outputs to that same truth
4. promote the session workspace into a flagship GM control surface only after the continuity path is proven

## Why it is still a horizon

RUN CONTROL is still a horizon because Chummer has to prove prep, live play, and recovery are dependable before it can claim indispensability at the table.
Until that happens, the lane is aspirational product planning rather than live flagship scope.

## Flagship handoff gate

Treat RUN CONTROL as ready for flagship handoff only when all of the following are true:

* session prep, roster, agenda, scene, and recap state stay consistent across reconnects and device swaps
* offline or partial-offline play returns without losing campaign provenance
* recap and dossier outputs can be generated from campaign truth without manual reconstruction
* publication handoff preserves receipts, authorship, and continuity
* the live surface is reliable enough that a GM can run an entire session without falling back to notebooks, chat logs, or spreadsheet memory

## Hard boundary

* not a generic team-collaboration platform
* not hidden state that bypasses canonical campaign truth
* not a flashy control room built on unreliable session continuity

