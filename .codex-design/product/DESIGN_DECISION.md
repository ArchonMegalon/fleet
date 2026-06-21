# Black Ledger Dispatches Design Decision

Black Ledger short stories are implemented as `BlackLedgerDispatch` records.

They are not free-writing output. They are a public-safe narrative layer rendered from:

- `WorldTickReceipt`
- `PlayerSafeNewsProjection`
- `PackagePressureReceipt`
- `CloseoutReceipt`

Authority split:

- fact authority: `chummer6-hub` plus `chummer6-hub-registry`
- narrative policy authority: `chummer6-design`
- draft authority: `executive-assistant` and optional adapters
- publication authority: `chummer6-hub`
- orchestration authority: `fleet`

Public routes:

- `/ledger/dispatches`
- `/ledger/dispatches/{dispatchId}`
- `/ledger/turns/{turn}/dispatches`
- `/ledger/factions/{factionId}/dispatches`

Email digest integration is allowed only after dispatch gating passes.
