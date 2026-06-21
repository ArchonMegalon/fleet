# ADR-0017: first-party companion runtime and bounded voice mode

## Status
Accepted

## Context

Project Chummer already has:
- accepted companion-channel identity policy in Hub
- a desktop startup companion implementation with explicit text-only and voice-opt-in posture
- bounded public trust and concierge widget posture for `FacePop`
- structured media posture for `vidBoard`, `Soundmadeseen`, `Unmixr AI`, `MarkupGo`, and `PeekShot`

What was still missing was one canonical rule set for the in-client companion itself:
- one identity instead of multiple unrelated bots
- first-party runtime ownership instead of vendor-widget drift
- bounded signal sources
- explicit voice consent posture
- a machine-readable contract for event packets, scripts, media cues, and interaction receipts

Without that canon, the desktop or mobile companion risked drifting into:
- generic chatbot behavior
- cross-app or ambient-surveillance creep
- vendor-managed runtime behavior
- media polish without trustworthy trigger discipline

## Decision

Project Chummer recognizes one canonical in-client companion identity:

`Switch` -> first-party companion runtime behind Chummer-owned triggers, templates, and receipts

This lane must remain first-party on desktop and mobile:
- `chummer6-ui` owns desktop runtime presentation
- `chummer6-mobile` owns mobile runtime presentation
- `chummer6-core` and `chummer6-hub` emit structured truth packets
- LLM routes may phrase but may not invent product truth

The companion may use multiple masks and tone levels, but it remains one identity.

Voice posture is bounded:
- default is text-only
- first voice posture is explicit push-to-talk
- hands-free is later, separately gated, and off by default

The companion may react only to Chummer-owned or explicitly user-provided signals.
It may not observe other apps, hidden clipboard state, ambient room audio, or undeclared telemetry.

Vendor posture is split:
- `FacePop` may appear only on Hub-owned public concierge surfaces
- `vidBoard`, `Soundmadeseen`, `Unmixr AI`, `MarkupGo`, and `PeekShot` may provide authored downstream media or voice assets
- no vendor widget or provider becomes the runtime companion authority on desktop or mobile

## Consequences

### Positive
- Chummer gains a consistent companion identity across install, build, campaign, support, and publication surfaces.
- Runtime companion behavior stays inspectable and bounded by first-party truth.
- Voice can land with a clean consent story instead of surveillance creep.
- Public concierge and media polish can expand without contaminating authenticated runtime surfaces.

### Negative
- Companion design must now be governed as a first-class product lane instead of ad-hoc copy.
- The runtime needs structured packet and script contracts rather than loose prose or inline UI strings alone.
- Overuse or poor annoyance-budget discipline would make the companion feel noisy quickly.

## Required follow-through

- add `COMPANION_PERSONA_AND_INTERACTION_MODEL.md`
- add `COMPANION_EVENT_SCHEMA.yaml`
- keep repo-local implementation notes subordinate to canonical companion design
- extend journey or release gates to prove companion trigger truth, dismissability, locale fallback, and voice opt-in behavior

## Rule

Chummer may make the companion feel personal.
It may not make the companion behave invasive.
