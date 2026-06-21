# Shadowrun Anarchy Ruleset Spec

Status: `shipped MVP`

Shadowrun Anarchy is a dedicated Chummer ruleset lane. It is not an SR5 skin, not an SR6 mode, and not a generic package overlay.

Current product posture:
- first-party public route family
- rules-light runner profile
- Black Ledger consequence lens
- dispatch-compatible narrative lane
- portable Chummer-owned JSON export
- dedicated public export and explain receipt routes

Current claim ceiling:
- shipped MVP for Black Ledger, dispatches, mobile play continuity, and portable first-party export
- not ruleset-complete
- not sourcebook-text-complete
- not a claim of full book-level mechanics coverage

Required route family:
- `/anarchy`
- `/play/anarchy`
- `/ledger/anarchy`
- `/ledger/dispatches?ruleset=anarchy`
- `/anarchy/export/runner.json`
- `/anarchy/receipts/explain.json`

Required authority:
- Chummer owns runner profile truth
- Chummer owns export truth
- Chummer owns receipt truth
- adapters may draft around the lane later, but never publish authoritative rules truth
