# M129 Design account and community canon closeout

Package: `next90-m129-design-close-public-auth-identity-channel-linking-participation`
Frontier: `3846410661`
Date: `2026-05-05`

## What shipped

The design-owned public-auth, identity and channel-linking, participation, account-aware front-door, and community-ledger canon now read as one reusable product story instead of parallel entry models.

Updated canon:

* `PUBLIC_AUTH_FLOW.md` now states that `/participate` is the guest-readable account-aware front door while `/home` and `/account` remain the signed-in community-ledger shell.
* `PUBLIC_USER_MODEL.md` now defines community-ledger relationship states for claim, membership, participation, reward, entitlement, linked-channel, and recovery posture without implying ledger membership for guests.
* `IDENTITY_AND_CHANNEL_LINKING_MODEL.md` now says linked identities and linked channels attach to the Hub community ledger and cannot stand in for reward, entitlement, or sponsor-session truth.
* `ACCOUNT_AWARE_INSTALL_AND_SUPPORT_LINKING.md` now binds account-aware front-door posture to Hub community-ledger plus Registry-backed channel truth instead of local auth folklore.
* `NEXT_WAVE_ACCOUNT_AWARE_FRONT_DOOR.md` and `COMMUNITY_SPONSORSHIP_BACKLOG.md` now close the public front door, community-ledger split, and Fleet evidence boundary into one canon bundle.
* `PUBLIC_PART_REGISTRY.yaml` now exposes account-aware home and account posture for claim, participation, reward, and recovery as part of the Hub public summary.
* `scripts/ai/validate_next90_m129_design_account_community_canon.py` now fail-closes the package against doc drift, standard verifier drift, feedback closeout drift, and canonical registry plus design queue drift.

Validation run:

* `python3 scripts/ai/validate_next90_m129_design_account_community_canon.py`
* `bash scripts/ai/verify.sh`

## Do not reopen

Do not reopen this slice for generic auth, account, or landing polish.
Reopen only when public-auth, linked identity or channel posture, account-aware front-door promises, or the Hub/Fleet community-ledger split changes enough to require new canon or when the validator proves drift in the M129 package anchors.
