# Black Ledger Dispatch Spec

Black Ledger Dispatches are Chummer-owned, receipt-backed narrative summaries derived from bounded world facts.

Required fields:
- `dispatch_id`
- `world_id`
- `turn`
- `source_receipt_id`
- `title`
- `summary`
- `body`
- `involved_factions`
- `involved_districts`
- `package_pressure_links`
- `privacy_status`
- `generated_by`
- `human_review_status`
- `created_at_utc`

Authority:
- facts come from `WorldTickReceipt`, `PlayerSafeNewsProjection`, `PackagePressureReceipt`, and `CloseoutReceipt`
- publication lives in `chummer6-hub`
- preseeded fixtures live in `chummer6-hub-registry`
- external tools may draft only and are never publication authority

Public routes:
- `/ledger/dispatches`
- `/ledger/dispatches/{dispatchId}`
- `/ledger/turns/{turn}/dispatches`
- `/ledger/factions/{factionId}/dispatches`

Rules:
- no free-floating fiction
- every dispatch links back to its source receipt
- every dispatch must remain public-safe and provider-neutral
