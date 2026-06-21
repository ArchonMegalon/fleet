# BeHuman GM Session Venue Spec

## Product rule

BeHuman hosts the live room. Chummer owns the session.

## Allowed use

- private GM game sessions
- campaign session video rooms
- one-shots
- open-table sessions
- faction table events
- GM prep, session zero, and debrief rooms

## Required modes

- `manual_link_mode` is required and must work without provider API access
- `adapter_create_mode` is optional and must fail closed until provider verification and adapter transport are both real

## Required routes

- `/api/v1/account/campaigns/{campaignId}/sessions/{sessionId}/venue`
- `/api/v1/account/campaigns/{campaignId}/sessions/{sessionId}/venue/manual-link`
- `/api/v1/account/campaigns/{campaignId}/sessions/{sessionId}/venue/behuman`
- `/api/v1/account/campaigns/{campaignId}/sessions/{sessionId}/venue/closeout`

## UX boundary

- host the session in a live room
- keep the campaign truth in Chummer
- never show a dead Create BeHuman button when provider posture is disabled or unverified

## Default posture

- private by default
- no public projection by default
- provider email invites disabled by default
- attendance sync requires consent
