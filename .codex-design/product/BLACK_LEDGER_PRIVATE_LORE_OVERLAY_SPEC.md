# Black Ledger Private Lore Overlay Spec

Purpose:
- authenticated campaign owners can attach private labels to public-safe archetypes without changing public routes

Public routes must never render them.

API:
- `POST /api/v1/account/campaigns/{campaignId}/ledger/private-lore-overlay`

Constraints:
- `world_id` must be `emerald-sprawl-prelude`
- `public_projection_allowed` is always `false`
- overlay labels are never shown on:
  - `/ledger`
  - `/ledger/map`
  - `/ledger/dispatches`
  - public digests
  - screenshot proof
  - route proof
  - `llms.txt`

Allowed private render surfaces:
- `/account/campaigns/{campaignId}/ledger`
- `/account/campaigns/{campaignId}/ledger/map`

Reserved future route:
- `/admin/lore-packs/licensed-canon`
