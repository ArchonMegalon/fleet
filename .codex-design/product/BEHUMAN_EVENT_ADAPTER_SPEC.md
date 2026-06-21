# BeHuman Event Adapter Spec

## Product rule

BeHuman may host the room. Chummer keeps the truth.

## Allowed provider roles

- public event venue host for community-facing sessions
- public registration mirror for explicitly enabled event flows
- private GM session room host when a signed-in Chummer campaign/session page remains the system of record

## Forbidden provider roles

- campaign truth
- runner sheet storage
- GM-only secrets
- rules or sourcebook truth
- Black Ledger world-tick authority
- package, release, support, or roadmap truth

## Operating modes

- `disabled`
  - no provider dependency
  - no secrets required
  - no public create affordance
- `manual_link_mode`
  - required baseline for GM session venue support
  - Chummer stores the canonical session state and the provider only receives a room URL the GM chose to paste
- `api_create_mode`
  - optional only after verification
  - must fail closed when the provider posture, secrets, or transport are missing

## GM session extension

- GMs may attach a BeHuman room to a Chummer campaign session.
- Players join through a signed-in Chummer session venue page, not through a public provider-first flow.
- The public-safe route may describe venue posture without exposing private room truth.
- Attendance sync is optional and consent-gated.

## Verification gates

- no public `BEHUMAN_*` secret leak
- no route lets BeHuman become campaign/session truth
- manual-link mode works without provider API access
- create mode stays unavailable unless verification and transport are both real
