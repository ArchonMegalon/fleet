# Black Ledger No-Noise UI Policy

Homepage teaser limits:
- section title: 1
- body sentences: 2
- stats: 3
- hotspots: 3
- primary CTA: 1
- secondary CTA: 1
- total links: 2

Allowed teaser CTAs:
- `Open Black Ledger` -> `/ledger`
- `Replay Turn 1` -> `/ledger/map?replay=turn-1`

Disallowed:
- dead links
- `href=\"#\"`
- `javascript:void`
- placeholder buttons
- generic `Learn more`
- provider, LTD, operator, or env-var terms on public Black Ledger pages
- homepage artifact or proof-card noise

Full `/ledger` actions:
- primary: `Open command map` -> `/ledger/map`
- secondary: `Read dispatches` -> `/ledger/dispatches`
- tertiary: `View status` -> `/status`

Every visible link must resolve to a real route and have proof.
