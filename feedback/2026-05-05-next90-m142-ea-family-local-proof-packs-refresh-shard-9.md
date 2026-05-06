# NEXT90 M142 EA family-local proof packs refresh

Refreshed the EA-owned M142 proof slice against shard-9 and the current fail-closed desktop readiness state instead of leaving the family-local pack pinned to the older successor-wave snapshot.

Changes in this refresh:
- added `docs/chummer5a-oracle/m142_family_local_proof_packs.yaml` and `.md` so the dense-builder, dice/initiative, and identity/contacts/lifestyles/history families each carry a standalone packet with exact screenshots, review receipts, interaction receipts, and parity verdicts
- added `scripts/materialize_next90_m142_ea_family_local_proof_packs.py` and `scripts/verify_next90_m142_ea_family_local_proof_packs.py` so the shard-9 packet can be regenerated and fail closed on drift
- corrected `docs/chummer5a-oracle/veteran_workflow_packs.yaml` so its task-local context and whole-product coverage now reflect the current shard-9 frontier and the live `desktop_client` readiness gap honestly

Current release truth remains unchanged:
- `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json` still reports `status=fail` with `missing_keys=["desktop_client"]`
- the refreshed EA proof packet supports review of that missing desktop lane; it does not overwrite the owner-repo desktop executable or release-channel blockers
