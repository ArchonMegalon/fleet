# Fleet implementation scope

## Mission

`fleet` is the worker orchestration and landing-control plane for Chummer-adjacent repo work.
It exists to execute mirrored canon safely and cheaply first, not to redefine product truth.

## Owns

* cheap-first automation policy for repo work
* queue selection, worker topology, and execution telemetry
* machine-readable mirror/parity verification for mirrored canon
* clustered queue synthesis when repeated drift findings point at one root cause
* jury-gated landing control for protected branches
* premium burst scheduling on top of the cheap baseline
* lane-local worker auth/cache state on the execution host
* dynamic participant-lane registration after explicit Hub consent
* sponsor-session execution metadata on participant lanes
* signed contribution receipts emitted back to Hub after meaningful work

## Must not own

* product architecture canon
* package or contract ownership truth
* Hub-issued user identity/session truth
* canonical user/group/community ledger truth
* direct participant-consent UX
* raw participant auth state in shared databases or repo files
* merge authority outside the configured review/jury policy
* canonical product/design decisions that belong in `chummer6-design`

## Baseline execution rule

The default Chummer/Fleet execution plane remains cheap-first:

* groundwork and easy work run on the cheap baseline
* premium execution is additive, not substitutive
* final landing authority remains with the review/jury lane

The cheap baseline must not be weakened just because premium capacity exists.

## Mirror and synthesis rule

Fleet should own the repeatable mechanics of mirror/parity checking and feedback clustering.

Allowed:

* compact machine-readable parity state
* a Fleet-owned mirror status artifact that can be read without opening design-side checksum ledgers
* short human summaries for mirror drift
* synthesis of repeated uncovered-scope findings into fewer clearer queue rows

Forbidden:

* pushing giant checksum markdown tables back onto the design repo as the main operational record
* turning repeated low-synthesis audit spam directly into queue truth without clustering

Preferred operational surfaces:

* Fleet-owned state such as `design_mirror_status.json`
* synthesized queue candidates that keep `source_items` metadata instead of one task per uncovered-scope bullet

## Premium burst rule

Premium burst is allowed only as an explicit second plane on top of the cheap baseline.

Allowed premium burst types:

* managed core burst
* participant direct burst

Participant direct burst requires:

* explicit user consent in Hub
* device-code auth initiated on the Fleet worker host
* lane-local auth/cache storage
* premium-eligible slice policy
* jury-gated landing
* signed contribution receipts back to Hub

Managed core burst remains operator-governed.

## Boundary truth

The Fleet premium burst boundary is considered healthy when:

* `fleet` consumes mirrored canon from `chummer6-design`
* `chummer6-hub` owns the consent/sponsorship UX
* `chummer6-hub` owns account, group, reward, and entitlement truth
* `fleet` owns the actual worker process, auth helper, and dynamic participant lane lifecycle
* `executive-assistant` remains the managed substrate for operator-governed lanes and telemetry
* final landing still goes through `jury`

## Review bar

Reject changes that:

* turn premium lanes into the new default baseline
* let participant lanes land or merge independently
* store raw participant Codex/OpenAI auth data in Hub
* bypass mirrored design canon with repo-local policy inventions
* blur the difference between managed EA core burst and participant direct burst
