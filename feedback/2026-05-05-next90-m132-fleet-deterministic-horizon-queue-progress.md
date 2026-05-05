# Next90 M132.6 Fleet Deterministic Horizon Queue

- Package: `next90-m132-fleet-schedule-deterministic-horizon-slices-only-after-owner-h`
- Frontier: `8249224665`
- Date: `2026-05-05`

Implemented the deterministic-horizon queue guard as both a live Fleet packet and an actual supervisor rule. The supervisor now treats milestone `132` queue rows as a stricter subclass of horizon work: they stay blocked unless the general handoff gate task `126.1` is done, the deterministic design gate task `132.7` is done, and the horizon registry carries the required handoff/proof/stop-condition fields for the owning repo.

Audit refinements:

- the deterministic milestone is now gated in the live scheduler instead of relying only on offline packet review
- the packet uses line-wrap-safe horizon-rule markers so the canon check tracks source truth instead of YAML formatting noise
- deterministic queue rows are measured separately from broader horizon work, which keeps the monitor specific to the M132 contract

Live result after materialization:

- packet status: `pass`
- deterministic queue gate: `blocked`
- blocked deterministic queue items: `7`
- handoff design gate status: `unknown`
- deterministic design gate status: `unknown`

That posture is expected right now: the package shipped, but the deterministic tranche remains fail-closed until the design-owned gate rows and horizon-proof fields become explicit enough for safe scheduling.
