# Black Ledger Map And Faction Intel Spec

## Map contract

The Black Ledger map is a vector-first public surface.

Required:

- inline SVG or equivalent vector geometry
- district polygons
- dominant faction labels
- influence and heat values
- keyboard accessible district focus states
- mobile-safe district fallback cards

Forbidden:

- blurry bitmap map as the actual world surface
- color-only faction differentiation
- tiny unreadable mobile labels

## District contract

Each district must expose:

- `id`
- `name`
- `polygon`
- `dominant_faction`
- `influence`
- `heat`
- public-safe summary

## Faction intel contract

Each faction must expose:

- public name
- type / role summary
- management posts
- public-safe pressure stats
- no private runner or support detail

## Public entry posture

Black Ledger is not a primary homepage slice in the current public posture. The direct
preview route may remain available for proof, internal review, and users who already
know where to look, but the homepage should not make it one of the first decisions.

When Black Ledger returns to the homepage, the slice must show:

- a visible Black Ledger gate
- a current turn marker
- 4 stat cards
- package pressure visibility
- a privacy note
- CTA into `/ledger`

## Ledger page additions

The flagship `/ledger` page must also show:

- turn navigation for the seeded live preview and deterministic turn-two preview
- AI stewardship posts with bounded public summaries
- a public-safe stewardship transfer preview receipt
- hash-backed tick receipt metadata for the currently selected turn
