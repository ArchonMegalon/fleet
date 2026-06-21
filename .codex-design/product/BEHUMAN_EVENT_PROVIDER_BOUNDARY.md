# BeHuman Event Provider Boundary

## Product promise

BeHuman.Online is allowed only as a venue and registration adapter for Chummer-owned events and GM session rooms.

## Allowed event families

- Black Ledger faction salons, watch parties, and public war-room gatherings
- Karma Forge workshops and install/import clinics
- Community hub / ChummerCon / launch-event scheduling
- creator and GM onboarding events
- private or community campaign session live rooms when Chummer remains the session system of record

## Truth order

Chummer remains the source of truth for:

- account identity
- rules truth
- package truth
- release truth
- support case truth
- roadmap truth
- world tick truth
- private runner and campaign state

BeHuman may only hold mirrored venue metadata, registration posture, and operator-facing event logistics.
For GM session venue use, that means the provider only hosts the room link and optional consented attendance follow-through.

## Forbidden provider roles

- sourcebook or rules content processor
- support system of record
- release or package authority
- account or entitlement authority
- private runner or campaign processor
- Black Ledger world-tick authority

## Capacity claims

Do not claim a public registration capacity until a provider verification receipt exists.

The reported purchase is `10 keys`, but any capacity number is provisional until verified in-provider.

## Safe operating modes

- `disabled`: no provider calls, no secrets required
- `manual`: Chummer stores canonical event truth and operators mirror registrations manually
- `manual_link_mode`: required baseline for GM session venue support; the GM pastes a room URL and Chummer keeps campaign/session truth
- `api_verified`: provider API usage allowed only after verification receipt and secret presence
- `webhook_verified`: inbound provider events allowed only after verification receipt, secret presence, and fail-closed signature checks

## Public copy rules

- Public copy may say `hosted with BeHuman` only when provider usage is enabled.
- Public copy must not imply BeHuman owns identity, rules, support, or release truth.
- Public copy must not claim a capacity number without verified receipt proof.

## Verification gates

- a provider verification receipt exists
- fail-closed mode exists when verification is missing
- no public `BEHUMAN_*` secrets leak
- no route or service treats BeHuman as canonical truth
- provider-disabled posture never shows a fake BeHuman create affordance on the GM session venue page
