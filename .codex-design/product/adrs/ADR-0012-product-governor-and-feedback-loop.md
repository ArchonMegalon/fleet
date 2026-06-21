# ADR-0012: Product governor and feedback loop are first-class canon

Date: 2026-03-25

Status: accepted

## Context

The design repo already had:

* a lead designer
* a petition path
* public help and progress surfaces
* crash, bug, and feedback intake canon

What it still lacked was a canonized whole-product operator loop:

* one role for stop, reroute, and release-readiness judgment
* one OODA path from raw signals to governed action
* one operating scorecard for weekly whole-product health

Without that seam, the repo could compile design truth more reliably than product reality.

## Decision

Chummer now canonizes:

* `PRODUCT_GOVERNOR_AND_AUTOPILOT_LOOP.md`
* `FEEDBACK_AND_SIGNAL_OODA_LOOP.md`
* `PRODUCT_HEALTH_SCORECARD.yaml`

The role split is:

* lead designer owns vision, canon, boundaries, and milestone truth
* product governor owns whole-product pulse, stop/reroute authority, and final packet routing
* Hub owns raw intake and reporter-facing closure
* Fleet owns clustering, packet synthesis, and execution aids

## Consequences

### Positive

* whole-product health and scope pressure now have an explicit owner
* support and feedback signals gain one canonical route into docs, code, queue, policy, or canon
* public progress and release posture can be judged against a named operating scorecard

### Negative

* more canon files must stay synchronized
* release and support decisions now need clearer written reasons instead of implicit operator intuition

## Explicit rejection

The following are rejected:

* making the lead designer the raw support inbox
* letting Fleet become canonical support truth
* letting one raw complaint publish directly into queue truth without clustering
* treating merged code as the same thing as user-facing closure
