# Black Ledger XCOM Globe Spec

## Current shipped posture

Black Ledger now opens on a tactical globe, not the old inline SVG shell.

Primary public experience:

- `/` uses a Black Ledger globe teaser as the emotional front door
- `/ledger` and `/ledger/map` use the same canvas geoscape root against the public map API
- `/account/ledger/onboarding?step=factions` uses the globe as the faction chooser surface

Fallback hierarchy:

1. canvas geoscape
2. list fallback
3. bounded SVG tactical shell

## Required interaction states

- idle slow rotation
- hover faction halo and panel update
- selected faction focus lock
- turn replay from Turn 0 to Turn 1
- mode switching across influence, conflict, intel, economy, magic, matrix, and recent changes
- reduced-motion step replay

## Public safety

- fictional public-safe seed only
- no official Shadowrun names
- no private table data
- no provider branding on public globe or faction promo surfaces

## Proof requirement

The globe is only considered ready when:

- homepage hero globe renders
- `/ledger/map` uses the globe as primary surface
- the SVG shell is fallback only
- motion tests prove state change, not only visibility
- reduced-motion replay remains usable
