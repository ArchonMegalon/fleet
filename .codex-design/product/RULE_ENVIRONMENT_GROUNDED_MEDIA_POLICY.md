# Rule environment grounded media policy

## Purpose

Rule-environment explain surfaces may use companion cards, narrated clips, and optional presenter media to reduce friction.
They may not become a second rules authority.

This file defines the truth order, receipt floor, and fallback rules for any media companion that talks about:

* active rule environment
* amend-package activation
* legality or blocking posture
* before/after rule-environment diffs
* restore, import, support, or campaign drift caused by environment changes

## Product promise

Users should be able to move from a plain-language explanation to inspectable rule truth without leaving the same first-party surface family.

If Chummer says a rule environment changed, blocked something, or made a build legal, the user must be able to inspect:

* the exact activation or diff receipt
* the active rule-environment identity and fingerprint
* the specific amend packages or source packs involved
* the same packet or anchor set that the media companion summarized

## Truth order

Rule-environment media companions stay below engine truth in this order:

1. compiled rule-environment receipt or explain packet
2. active and compared rule-environment identities
3. source anchors and amend-package diff anchors
4. approved text fallback and launch labels
5. optional companion card, narration, or presenter media

Approval may allow publication.
It may not authorize a rule claim that is missing packet scope, receipt scope, or source-anchor scope.

## Required receipt floor

Every grounded rule-environment media launch must preserve:

* `packet_revision_id`
* `active_rule_environment_digest`
* `compared_rule_environment_digest` when a diff is involved
* `activation_receipt_ref` or `diff_receipt_ref`
* `anchor_scope_ids`
* `approval_scope`

`Open activation receipt` or `Open diff receipt` must remain available wherever the companion can launch.

If any required field is missing, stale, or contradictory, the launch surface must fail closed to the inspectable packet, receipt sheet, or localized text fallback instead of pretending the companion is enough.

## Surface rules

The same grounded rule-environment truth must be visible on:

* Rules Navigator
* Build Lab
* import and migration follow-through
* diagnostics and support follow-through
* campaign drift and restore flows

Media companions may summarize the active environment, what changed, and the next safe action.
They may not become the only place where legality, blocker scope, or amend-package impact can be inspected.

## Grounded media rule

Media companions can cite but never replace engine truth.

That means:

* narration may restate the receipt-backed change in plain language
* narration may not invent legality, recommendation, or compatibility claims outside the packet scope
* presenter mode may not hide the active rule-environment badge, receipt entry point, or text fallback
* a missing media render must not block the text-first rule-environment explanation path

## Approval and localization

Approval truth is bounded metadata, not mechanical authority.

Localized variants must preserve:

* receipt labels
* rule-environment badges
* blocker severity
* the exact distinction between active, compared, missing, downgraded, and blocked package posture

Locale fallback may degrade presentation polish.
It may not paraphrase away receipt identity or make a stale environment look current.

## Forbidden outcomes

The product must fail closed when a grounded rule-environment companion would otherwise:

* claim legality without an activation or diff receipt
* summarize a different rule-environment revision than the active compute result
* imply that approval or polished media can overrule inspectable engine truth
* replace the only visible recovery or next-step action with presenter-only narration

## Ownership split

* `chummer6-core` owns receipt and explain-packet truth
* `chummer6-ui` owns rule-environment inspection and launch affordances
* `chummer6-hub` owns campaign, support, and restore follow-through surfaces that reuse the same receipts
* `chummer6-media-factory` may render optional companions from approved packet scope only
* `chummer6-design` owns this truth-order policy and the fail-closed product promise
