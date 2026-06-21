# Known Issue and Fix Status Language

## Purpose

This file standardizes the public, support, and in-product status words for release and support closure.

## Canonical terms

### `known_issue`

The problem is real, understood enough to name, and still open.
It must link to the current workaround, next action, or tracking posture.

### `in_progress`

Work is actively underway, but the user must not treat the fix as available yet.
It must name the next owner or release lane.

### `fixed_pending_release`

The fix exists in code or internal proof, but it has not reached the affected user route or channel yet.
This state must not be shortened to `fixed`.

### `fixed`

Use only when the fix is available on the same channel or route family the user is being asked to trust.

### `blocked`

The route is not usable now.
It must say the next safe action or explicit wait posture.

### `revoked`

The route was intentionally removed from recommendation or use.
It must no longer read like a valid primary path.

### `preview`

The route is usable for bounded real use, but it has not earned flagship wording.

## Forbidden shortcuts

Do not say:

* fixed, when the reporter's channel has not changed
* resolved, when only the PR merged
* available now, when the route is still blocked or review-required
* in progress, without a named owner or next lane

## Evidence rule

Every `fixed`, `released_to_reporter_channel`, or public fix notice must cite release or support truth that the user can actually reach.
