# Fleet flagship-readiness overclaim correction

Date: 2026-04-11
Audience: `fleet`
Status: injected feedback

## Problem

Fleet is too optimistic about Chummer readiness.
Structural milestone closure and repo-surface coverage are being interpreted too close to `ready`, even though the flagship bar still requires stronger lived-product proof:

* veteran familiarity
* dense workbench acceptance
* primary-route honesty
* screenshot/task-speed proof
* support friction truth

## Required changes

* Split readiness reporting into at least:
  * `architecture_ready`
  * `flagship_ready`
  * `veteran_ready`
  * `primary_route_ready`
* Make milestone closure insufficient on its own for any flagship-ready or replacement-ready output.
* Surface hard failure reasons when desktop familiarity, noise budget, or task-speed proof is missing.
* Add product-governor dashboard views for:
  * Chummer5a screenshot familiarity deltas
  * dense-workbench/noise-budget drift
  * veteran first-minute orientation failures
  * support and browser-ritual friction
  * primary-head versus fallback-head route truth

## Required guardrail

`remaining_milestones: []` must not imply `ready to replace Chummer5a`.
If flagship/veteran evidence is missing, Fleet should say so plainly and fail readiness despite milestone-green state.
