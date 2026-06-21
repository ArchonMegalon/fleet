# Onboarding and Empty-State Journey Contract

## Purpose

This contract defines the first-run and no-data posture for flagship surfaces.

## Rules

* Every major surface must tell the user the next safe action.
* Empty state must explain what exists, what does not exist yet, and how to start.
* Recovery-start states must differ from true first-run states.
* No onboarding route may surprise the user with hidden telemetry, hidden account requirements, or hidden route changes.

## Required surfaces

### Desktop first run

* open the real workbench or guided restore continuation
* identify install claim or account posture honestly
* avoid dashboard-first decorative detours

### Hosted help, downloads, and support

* explain whether the route is public, account-gated, preview, or blocked
* tell the user where the primary download or recovery route lives

### Mobile and live-play empty state

* say whether the user is waiting for campaign truth, missing rule packs, or simply has no current session

## Mandatory copy elements

* one next-safe-action
* one bounded fallback
* one trust note when the user should not yet trust the current state

## Rule

Every major journey in `USER_JOURNEYS.md` must have a first-run and no-data story before flagship readiness can remain green.
