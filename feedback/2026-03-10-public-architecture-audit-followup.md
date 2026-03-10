# Fleet public architecture audit follow-up

Date: 2026-03-10
Audience: `fleet` maintainers
Status: injected feedback

## Summary

This is the strongest version of `fleet` so far.

The control-plane architecture is coherent now:

* five-service control plane
* `/admin` as captain cockpit
* `/admin/details` as raw inventory and settings view
* split desired-state config across root, accounts, policies, routing, groups, and per-project files
* explicit compile model separating modeled truth, dispatchable truth, and execution truth
* admin spec that now matches the real system

Routing, healing, group modeling, and cockpit semantics are materially ahead of where they were before.

## What is now working well

### Config and compile model

* split config is a real improvement over the old monolith
* the three-stage compile model is the right shape for the system
* lifecycle and maturity distinctions are finally explicit enough to separate scaffold truth from dispatchable truth

### Routing and healing

* routing now reads as evidence-driven rather than pure heuristic bootstrap
* Spark-first lanes and heavier model lanes are separated sensibly
* auto-heal and incident playbooks are real enough to count as operating behavior, not just intent
* auto-approval of known safe finding classes is a practical move toward self-healing

### Group modeling

* `chummer-vnext` now behaves like a real mission lane
* captain controls and group roles are meaningful rather than decorative
* only `dispatchable` and `live` members participate in dispatch/runway posture, which is the right fix for scaffold distortion

### Bridge semantics

* the cockpit now thinks in mission, incident, runway, review, and healer terms
* finish outlook, pool share, and recent drain are the right kinds of data to surface
* red-only incident treatment is much closer to an actual operator bridge

## Main remaining gaps

### 1. One more bridge compression pass

The bridge is now a compact ops console, but not yet a true single-glance captain bridge.

Required direction:

* keep the first screen to posture, six lamps, top mission cards, red incidents, and a tiny healer/review strip
* move everything else behind drawers or details
* keep subtraction as the next UI move, not feature accretion

### 2. Program truth still lags fleet sophistication

The control plane is now reasoning better than the underlying program truth can currently justify.

Required direction:

* turn Chummer milestone and design coverage from scaffold truth into dispatchable truth
* keep making milestone coverage concrete enough that the fleet is scheduling present work rather than future aspirations

### 3. Routing/account capability semantics need explicit alignment

Public routing policy and effective controller/account capability handling need to say the same thing.

Required direction:

* document or fix any intentional mismatch between routing preferences and supported ChatGPT-auth model sets
* ensure route class, account capability, and controller allowlist semantics stay aligned

### 4. Review-heal policy still has tension

The review lane is much better, but escalation thresholds and auto-heal posture can still fight each other.

Required direction:

* keep review mostly automatic
* make sure category escalation thresholds do not reintroduce noisy operator-visible review incidents unless that is intentional

## Current verdict

* Architecture: good now.
* Config shape: much better.
* Captain semantics: real.
* Self-healing: real foundation.
* Bridge UX: close, but still one compression pass away.
* Program truth: still behind the sophistication of the fleet.

## Best next milestone

Shrink `/admin` one more time, align routing and account capability semantics, and keep converting Chummer milestone truth from scaffold truth into dispatchable truth.
