# Black Ledger Public Seed Spec

Canonical public seed:
- `world_id`: `emerald-sprawl-prelude`
- `public_name`: `Emerald Sprawl: First Pressure`
- `lore_mode`: `public_seed`
- `current_turn`: `1`

Required shape:
- 6 factions
- 8 districts
- Turn 0 seed receipt
- Turn 1 preseeded tick receipt
- seeded events, arcs, package pressure, dispatches, and AI steward posts

Projection rules:
- `/api/v1/ledger/worlds/emerald-sprawl-prelude`
- `/api/v1/ledger/worlds/emerald-sprawl-prelude/map`
- `/api/v1/ledger/worlds/emerald-sprawl-prelude/turns/1`
- `/api/v1/ledger/worlds/emerald-sprawl-prelude/dispatches`

Direct preview teaser rules:
- headline: `Turn 1 already ran. The city is moving.`
- exact body from `PUBLIC_COPY_AND_ROUTE_MODEL.md`
- maximum 3 stats
- maximum 3 hotspots
- primary CTA only: `Open Black Ledger`
- secondary CTA only: `Replay Turn 1`

Homepage rule:
- Black Ledger stays out of the primary homepage and public navigation until the visual,
  replay, and newsroom experience clears the release bar.

The registry seed file is the single source of truth for the public-safe world projection.
