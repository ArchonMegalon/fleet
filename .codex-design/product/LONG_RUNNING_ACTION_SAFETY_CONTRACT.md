# Long-Running Action Safety Contract

## Purpose

This file defines retry, cancel, rollback, and non-lossy recovery posture for long-running build, run, publish, and improve lanes.

## Action classes

* install_or_update
* claimed_restore
* import_or_migration
* sync_or_reconnect
* publish_or_render
* support_packet_submission

## Required behaviors

### Retry

The user can retry when the system knows the last attempt did not commit durable truth.

### Cancel

Cancel must stop further mutation where possible and must say what state was preserved.

### Rollback

Rollback must be offered when a committed change can return to a prior governed state without inventing data.

### Safe fallback

When neither retry nor rollback is safe, the system must expose a read-only, draft-preserving, or support-routed fallback instead of pretending success.

## Forbidden behaviors

* silent last-write-wins on shared truth
* spinner-only suspense with no cancel or fallback
* success messaging before durable commit or release truth exists
* destructive cancel that discards recoverable draft state without warning

## Rule

Every long-running promoted route must name which of retry, cancel, rollback, or safe fallback is legal.
