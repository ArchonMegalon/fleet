# Black Ledger Preseeded World Spec

## Scope

`emerald-sprawl-prelude` is the canonical public-safe starter world for the Black Ledger preview.

It exists to make `/ledger` feel alive on first load without using official lore, copied sourcebook text, provider-owned data, or private user/campaign state.

## Canon identity

- Internal id: `emerald-sprawl-prelude`
- Public name: `Emerald Sprawl: First Pressure`
- Public label: `Preseeded preview world`
- Public posture: seeded preview and opt-in aggregate only

## Required world shape

- 6 factions
- 8 districts / influence spheres
- 1 preseeded tick already applied
- 3 visible package-pressure candidates
- public-safe faction pressure, package heat, and closeout motion

## Route ownership

- `/ledger`: flagship Black Ledger hub
- `/black-ledger`: public alias
- `/ledger/stats`: public-safe stat drilldown
- `/ledger/factions`: faction and district pressure lane
- `/ledger/packages`: package-pressure lane
- `/ledger/closeouts`: tick receipt and closeout lane

## Public copy constraints

Required:

- `Turn 1 already ran.`
- `Seeded preview and opt-in aggregate only.`
- `The Ledger explains pressure, not people.`

Forbidden:

- official Shadowrun faction or district names
- copied publisher/sourcebook text
- private campaign state
- support-case state
- provider/operator internals
- real-player rankings

## Ownership

- design canon: `chummer6-design`
- seed source of truth: `chummer6-hub-registry`
- public rendering: `chummer6-hub`
