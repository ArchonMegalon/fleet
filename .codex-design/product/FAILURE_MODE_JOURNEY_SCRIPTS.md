# Failure Mode Journey Scripts

## Purpose

This file defines the minimum user-visible recovery script for the main Chummer jobs.
It complements `journeys/*.md` by making the failure-mode copy and handoff posture explicit.

## Common script shape

Every promoted failure route must answer:

1. what happened
2. what is safe right now
3. what to do next
4. when to escalate
5. which repo family owns the underlying fix

## Build

### Trigger

Missing rule pack, amend-package conflict, calculation mismatch, import downgrade, or blocked custom-data path.

### User-visible recovery contract

* Explain the active rule environment and the specific mismatch.
* Show whether build truth is blocked, downgraded, or still safe to inspect.
* Offer repair, compare, rollback, or calculation-report routes.

### Escalation

Use the calculation-report or support packet path when the number still looks wrong after the explain route.

## Explain

### Trigger

Explain trace missing, stale, contradictory, or non-grounded.

### User-visible recovery contract

* Say whether the result is still trustworthy.
* Offer one next-safe-action: refresh, reopen explain, compare recent change, or send calculation report.
* Never present folklore or empty debug text as product truth.

### Escalation

Escalate to support packet or known issue when explain cannot regain grounded trust.

## Run

### Trigger

Reconnect failure, stale state, conflict, missing package, or session-handoff mismatch.

### User-visible recovery contract

* Show live/stale/offline/conflict posture explicitly.
* Say whether local view is safe to read, safe to act on, or blocked.
* Offer reconnect, compare, repair, or continue-in-read-only posture as appropriate.

### Escalation

Escalate when campaign or session truth cannot be reconstructed from replay-safe or claimed-device state.

## Publish

### Trigger

Preview/render failure, provenance gap, privacy/IP block, compatibility block, or publish timeout.

### User-visible recovery contract

* Preserve draft and preview state where possible.
* Distinguish retry, rollback, and blocked publication states.
* Tell the user whether anything public actually changed.

### Escalation

Escalate when provenance, compatibility, or privacy review cannot clear and the route cannot finish safely.

## Improve

### Trigger

Crash, install problem, support misroute, public/help/status contradiction, or unresolved known issue.

### User-visible recovery contract

* Name the current status using canonical language.
* Tell the user whether a workaround exists now.
* Tell the user where the real fix or next update will appear.

### Escalation

Escalate when the public route, support route, and actual release truth disagree.

## Rule

No flagship route is complete until its failure script is published and referenced by the owning journey or release gate.
