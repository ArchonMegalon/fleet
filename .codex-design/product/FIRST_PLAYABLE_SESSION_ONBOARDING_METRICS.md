# First playable session onboarding metrics and claims

## Purpose

This file defines what Chummer may count as a first-playable-session success and
what it may publicly claim about onboarding before the broader launch-health
wave compiles those signals into governor and trust surfaces.

The goal is not to turn onboarding into a vanity funnel.
The goal is to prove that a new user can reach a legal, understandable, and
table-ready first session without hiding blockers behind vague success copy.

## Product promise

Chummer should help a new player move from "I might join this table" to
"I know whether I am ready, what runner I am bringing, what the table expects,
and what to do next" in one bounded guided lane.

That promise stays bounded:

* desktop remains the expert flagship
* no-desktop entry remains welcome for beginner-safe participation, not a
  desktop replacement claim
* primers, briefing artifacts, and support-safe recovery remain secondary to
  governed install, claim, campaign, roster, and rule-environment truth

## First-playable-session definition

A user reaches `first_playable_session_started` only when all of the following
are true in one guided lane:

* the user saw an explicit onboarding entry point instead of a hidden support or
  insider route
* the lane made its device posture explicit: `flagship_desktop`,
  `desktop_guest`, `no_desktop_public`, or `recovery_resume`
* the active runner path is clear: starter runner chosen, approved existing
  runner chosen, or guided build completed to a legal table-ready state
* the campaign primer or equivalent table-orientation packet was opened
* the mission or first-session briefing was opened, acknowledged, or explicitly
  marked not required by the host lane
* the user received a table handoff, accepted-run receipt, or launch-ready next
  action instead of generic "come back later" copy
* if a blocker occurred, the lane exposed the next safe action or support-safe
  recovery action before abandonment

This metric does not require:

* a permanent claimed desktop install for the `no_desktop_public` lane
* a full bespoke character build before the first table contact
* retention, repeat play, payment, or creator activity

## Stage contract

Every first-session lane must project the same bounded stage IDs so drop-off and
handoff can be compared honestly:

1. `entry_visible`
2. `lane_selected`
3. `identity_or_guest_confirmed`
4. `runner_path_ready`
5. `campaign_primer_seen`
6. `session_briefing_seen`
7. `table_handoff_ready`
8. `first_playable_session_started`

Allowed lane-specific skips:

* `desktop_guest` may skip persistent claim but must still expose whether that
  choice limits later continuity.
* `no_desktop_public` may skip desktop install and claim but must still expose
  legality preflight, table contract, and the one next safe action.
* `recovery_resume` may skip `campaign_primer_seen` only when the same campaign
  primer receipt is already linked on the install or campaign record.

No lane may silently skip:

* `runner_path_ready`
* `table_handoff_ready`
* blocker explanation when the user cannot proceed

## Success scorecard

The governor loop should track these lane-level metrics as the minimum release
truth for onboarding:

| Metric | Meaning | Initial threshold |
| --- | --- | --- |
| `completion_rate` | `first_playable_session_started / entry_visible` for the lane | `>=70%` on `flagship_desktop`, `>=55%` on `no_desktop_public` |
| `time_to_first_playable_session_p75_minutes` | p75 minutes from `entry_visible` to `first_playable_session_started` | `<=45` desktop, `<=20` no-desktop |
| `blocker_recovery_rate` | share of blocked starts that reach a later stage after a next-safe-action or recovery prompt | `>=60%` |
| `primer_and_briefing_coverage_rate` | completed starts with both primer and briefing receipts when the lane requires them | `>=85%` |
| `desktop_escalation_after_no_desktop_preflight_rate` | no-desktop starts that are later told desktop is required after already passing preflight | `0` |
| `support_escape_rate` | starts that end in unbounded support detours without a typed blocker reason | `0` |

The governor should not widen onboarding claims beyond one repo lane until:

* the metric thresholds above hold for two consecutive weekly pulse reviews
* each measured lane has at least `100` starts and `30` completed first-playable
  sessions in the review window
* blocker families are typed strongly enough that the top two failure modes
  produce bounded owner actions instead of generic "improve onboarding" notes

## Bounded onboarding claims

Allowed claims:

* Chummer can guide a new player to a first playable session through an explicit
  starter lane.
* A no-desktop visitor can determine fit, pass preflight, and receive a
  receipt-like table handoff before deciding whether desktop is needed later.
* Primer and briefing artifacts are first-class support for onboarding, but they
  stay tied to campaign and rule-environment truth.
* Onboarding drop-offs feed the product-governor loop as typed funnel evidence.

Forbidden claims:

* mobile or public onboarding replaces the flagship desktop experience
* every new player can build a forever runner before first table contact
* support is unnecessary because the lane is fully self-healing
* onboarding completion proves long-term retention, monetization, or creator
  adoption
* a user is "ready" when the lane still hides rule, legality, schedule, or
  device blockers behind generic success copy

## Product-governor handoff

The onboarding package must hand the weekly governor pulse one bounded summary
per lane:

* current `completion_rate`
* current `time_to_first_playable_session_p75_minutes`
* top typed blocker family
* whether the lane is claimable, warning-only, or blocked
* the one next owner action when the lane is below threshold

If those facts are missing, the governor may say only that onboarding remains
in progress.

## Telemetry contract

Implementation-facing event names, rollups, and workflow IDs live in
`PRODUCT_USAGE_TELEMETRY_EVENT_SCHEMA.md`.
The privacy and retention posture stays owned by
`PRODUCT_USAGE_TELEMETRY_MODEL.md` and
`PRIVACY_AND_RETENTION_BOUNDARIES.md`.

The required daily rollup for this package is `first_playable_session_daily`.
It must stay lane-scoped and typed enough to distinguish:

* entry visibility failures
* runner-readiness failures
* primer or briefing misses
* table-handoff failures
* support-safe recovery wins versus unbounded support escapes
