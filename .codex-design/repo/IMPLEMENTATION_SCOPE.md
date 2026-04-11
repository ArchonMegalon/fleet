# Fleet implementation scope

## Mission

`fleet` is the worker orchestration and landing-control plane for Chummer-adjacent repo work.
It exists to execute mirrored canon safely and cheaply first, not to redefine product truth.

## Control-plane autonomy scope

The live autonomous designer and product-governor perimeter in Fleet is the `control-plane` group:

* `fleet`
* `executive-assistant`

This scope is intentionally narrow.

Inside:

* Fleet control services, Studio/admin/operator flows, and published control artifacts
* EA runtime posture, mirror drift, synthesis helpers, and operator-facing telemetry

Outside:

* sidecar repos such as `arr` and `arr-v2`
* the legacy oracle repo `chummer5a`

Inclusion in the perimeter does not promote EA to canon owner status.
It stays a governance-adjacent runtime substrate that the operator loop may observe and route through, not a second source of product truth.

## OODA placement rule

The product-governor and support/control OODA semantics are canon owned by
`chummer6-design`:

* `PRODUCT_GOVERNOR_AND_AUTOPILOT_LOOP.md`
* `PRODUCT_CONTROL_AND_GOVERNOR_LOOP.md`
* `SUPPORT_AND_SIGNAL_OODA_LOOP.md`
* `FEEDBACK_AND_SIGNAL_OODA_LOOP.md`

The live executable loop belongs in Fleet:

* Fleet runs the durable observe/orient/decide/act services, traces, canaries,
  packets, dashboards, and publishable operator evidence.
* Hub remains the source of truth for the user, campaign, community, install,
  and support/control data those loops consume or update.
* Shell sessions may launch, inspect, or debug the loop, but the shell is not
  the durable control-plane home.

## Owns

* cheap-first automation policy for repo work
* queue selection, worker topology, and execution telemetry
* machine-readable mirror/parity verification for mirrored canon
* clustered queue synthesis when repeated drift findings point at one root cause
* operator-facing designer and product-governor studio surfaces that publish proposal artifacts and feedback notes downstream of central canon
* evidence packet synthesis for support, feedback, and public-surface drift after Hub-owned intake exists
* jury-gated landing control for protected branches
* premium burst scheduling on top of the cheap baseline
* lane-local worker auth/cache state on the execution host
* dynamic participant-lane registration after explicit Hub consent
* sponsor-session execution metadata on participant lanes
* signed contribution receipts emitted back to Hub after meaningful work
* publish/sync mechanics for downstream public artifacts once design-owned meaning already exists
* release matrix expansion and multi-repo release orchestration once repo-local build recipes already exist
* verify/promotion/signoff evidence for release waves

## Must not own

* product architecture canon
* package or contract ownership truth
* Hub-issued user identity/session truth
* canonical user/group/community ledger truth
* direct participant-consent UX
* raw participant auth state in shared databases or repo files
* merge authority outside the configured review/jury policy
* canonical product/design decisions that belong in `chummer6-design`
* canonical product-governor authority rules or whole-product pulse truth
* the meaning of the `chummer.run` landing page or registered overlays
* installer recipe truth
* canonical release-channel or update-feed truth

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
* participation semantics compiled from `products/chummer/PARTICIPATION_AND_BOOSTER_WORKFLOW.md`

Managed core burst remains operator-governed.

## Sequencing constraint

Do not add more guided-contribution product features to Fleet until Hub's reusable user/group/ledger spine exists.

Allowed while that backbone is still being built:

* lane-local participant auth and worker execution
* explicit premium-burst scheduling
* signed contribution receipts
* sponsor-session execution metadata

Forbidden before Hub catches up:

* Fleet-owned boost-code product logic
* Fleet-owned user or group identity truth
* Fleet-owned reward, badge, leaderboard, or entitlement logic
* ad hoc product UX that bypasses the Hub account/community plane

Fleet should stay ahead on execution mechanics, not on community product semantics.

## Boundary truth

The Fleet premium burst boundary is considered healthy when:

* `fleet` consumes mirrored canon from `chummer6-design`
* `chummer6-hub` owns the consent/sponsorship UX
* `chummer6-hub` owns account, group, reward, and entitlement truth
* `fleet` owns the actual worker process, auth helper, and dynamic participant lane lifecycle
* `executive-assistant` remains the managed substrate for operator-governed lanes and telemetry
* final landing still goes through `jury`
* guide/build verification reads design-owned canon directly instead of hiding it behind EA helper truth

The next product wave is Hub-first:

* Hub grows accounts, groups, ledgers, and participation UX
* Fleet remains the sponsor-session execution plane underneath that UX

## Review bar

Reject changes that:

* turn premium lanes into the new default baseline
* let participant lanes land or merge independently
* store raw participant Codex/OpenAI auth data in Hub
* bypass mirrored design canon with repo-local policy inventions
* blur the difference between managed EA core burst and participant direct burst
* skip fail-closed completion evidence when desktop flagship proof is missing real workbench-first startup, a first-class master index or character roster, or in-product claim/recovery handling
* let Fleet mark the desktop flagship as complete while the user still sees a generic shell, a browser-ritual claim detour, or a framework-first installer choice
