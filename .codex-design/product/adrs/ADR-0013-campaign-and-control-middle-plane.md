# ADR-0013: Campaign and control become first-class middle planes

Date: 2026-03-25

Status: accepted

## Context

The design repo is already strong on repo boundaries, package ownership, release governance, and public-surface policy.

What remained under-modeled was the product middle:

* campaign continuity
* living dossier state
* support/control loop truth

Without those domains, the repo could explain where code belongs more clearly than it could explain:

* what long-lived product state users actually inhabit
* how support reality changes canon and release posture

## Decision

Chummer now canonizes two first-class middle planes:

* campaign continuity, exposed through `Chummer.Campaign.Contracts`
* product control, exposed through `Chummer.Control.Contracts`

Both start as bounded contexts inside `chummer6-hub`.
That is an initial ownership choice, not a claim that Hub should absorb every future middle-layer domain forever.

Supporting canon for this decision is:

* `CAMPAIGN_SPINE_AND_CREW_MODEL.md`
* `CHARACTER_LIFECYCLE_AND_LIVING_DOSSIER.md`
* `PRODUCT_CONTROL_AND_GOVERNOR_LOOP.md`
* `SUPPORT_AND_SIGNAL_OODA_LOOP.md`

## Consequences

### Positive

* the product now has explicit middle-layer truth for runner, crew, campaign, recap, and replay-safe continuity
* support, crash, feedback, and release signals now have a named control-plane home instead of living only as sidecar operator posture
* public product story can shift from only Build / Explain / Run toward Build / Explain / Run / Publish / Improve

### Negative

* Hub must stay disciplined so initial ownership does not collapse back into a hidden super-repo
* more canon files and contract families now need to stay synchronized

## Explicit rejection

The following are rejected:

* leaving campaign continuity as implied behavior spread across mobile, Hub, media, and public copy
* leaving support/control truth as a markdown-only operator habit
* treating repo boundaries as sufficient product architecture when the middle-layer domains are still unnamed
