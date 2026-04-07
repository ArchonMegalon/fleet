# NEXUS-PAN

## The table pain

When phones, tablets, or laptops drift apart during play, the table stops trusting the screen.
Players hesitate, GMs re-verify state by hand, and the session loses its shape while everyone waits for the devices to agree again.

## The bounded product move

Chummer would keep reconnects and shared session state steady enough that players can jump back in without the GM rebuilding context by hand.
The move is deliberately narrow: carry the canonical session record through handoff, preserve the current play context, and surface stale, pending, and conflicted state honestly.
It extends the core rules and session record instead of inventing a second source of truth.
It also covers premium degraded-mode behavior: clear offline posture, safe local continuity, and honest conflict recovery when the network or device handoff goes bad.

## Likely owners

Primary owning repos:

* `chummer6-core` - durable session truth, sync bundles, and conflict semantics
* `chummer6-mobile` - play shell, offline local continuity, and reconnect UX
* `chummer6-hub` - session authority, identity anchoring, and recovery orchestration

Adjacent surface work may touch `chummer6-ui` for surfaced state, but this horizon is not owned there.

## LTD/tool posture

No external tool is required for the canonical core of this horizon.
The LTD posture stays conservative: no new long-lived dependency, no helper that can become the source of truth, and no operator aid that can outrank the session record.
If projections or operator aids appear later, they remain downstream helpers only.

## Dependency foundations

Before this can be a flagship lane, these foundations have to exist and stay boring under stress:

* durable session state
* reliable sync bundles
* visible reconnect explanations
* in-session reliability
* offline-capable local state
* explicit stale, pending, and conflicted state
* stable device-role and handoff semantics
* canonical identity/session anchoring in Hub

## Current state

The live release still needs boringly reliable session continuity.
The system can describe reconnects, but it cannot yet promise stress-safe handoff across devices and networks without creating more confusion than it removes.

## Eventual build path

1. Prove durable session truth and replay-safe sync bundles in `chummer6-core`.
2. Wire mobile-local continuity, offline posture, and reconnect recovery in `chummer6-mobile`.
3. Anchor identity, recovery routing, and handoff authority in `chummer6-hub`.
4. Add only surfaced state and operator-visible explanations outside the core path.
5. Promote the combined flow into flagship work only after the stress gate stays green across repeated disconnect, reconnect, and device-swap cases.

## Why it is still a horizon

This remains a horizon because the product still lacks the foundation that would make PAN continuity boring instead of fragile.
Until reconnects, sync recovery, and shared-state handoffs stay solid under stress, a richer PAN layer would add another place to debug instead of removing table pain.

## Flagship handoff gate

This horizon becomes flagship-ready only when a player can drop from one device, reconnect from another, and return to the same canonical session state without GM repair work.
The gate must prove all of the following in one end-to-end flow:

* the session resumes from the same authoritative record
* stale, pending, and conflicted fields are visible instead of hidden
* offline local continuity survives the disconnect window
* the GM does not rebuild context by hand
* the flow survives repeated reconnect, offline, and device-swap stress on the real release path
