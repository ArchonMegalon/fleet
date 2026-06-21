# ADR-0006: Participation Truth Lives in Hub and Sponsored Execution Lives in Fleet

Date: 2026-03-24

Status: accepted

## Context

- Chummer now has an explicit participate and guided-contribution model with sponsor sessions, participant lanes, signed contribution receipts, and recognition projections.
- The workflow was canonized in `PARTICIPATION_AND_BOOSTER_WORKFLOW.md`, but the ownership split was not yet captured as a dedicated ADR.
- Without an ADR, Hub, Fleet, or EA could drift into overlapping product ownership under delivery pressure.

## Decision

- `chummer6-hub` owns sponsor intent, consent, user and group truth, sponsor-session records, ledgers, and recognition policy.
- `fleet` owns participant-lane provisioning, worker-host device auth, lane-local auth/cache storage, sponsored execution policy, and signed contribution receipts.
- `executive-assistant` remains the provider-aware telemetry and runtime substrate underneath managed or participant execution.
- Public language prefers `participate` and `guided contribution`; operator language such as `participant lane` stays downstream of that canon.
- Final landing still goes through review and `jury`.

## Consequences

- Fleet cannot absorb user, group, or reward truth just because it runs the premium lane.
- Hub cannot absorb worker-host auth caches or lane lifecycle internals just because it owns participation UX.
- Recognition must derive from validated contribution receipts rather than raw time or auth completion.
