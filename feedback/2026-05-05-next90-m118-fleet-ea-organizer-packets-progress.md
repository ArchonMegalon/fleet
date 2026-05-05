# M118 Fleet organizer operator packets progress

Package: `next90-m118-fleet-ea-organizer-packets`
Owned surfaces: `organizer_health_packets`, `publication_readiness:operator`

This pass adds the Fleet-owned packet materializer and verifier for milestone `118.4`.

- `scripts/materialize_next90_m118_fleet_ea_organizer_packets.py` now compiles one package-scoped operator packet from the canonical successor registry, the Fleet and design queue rows, Fleet weekly-governor truth, Fleet support-packet truth, Hub local-release proof, and the Hub organizer/creator-publication proof lanes.
- `scripts/verify_next90_m118_fleet_ea_organizer_packets.py` fail-closes drift between the generated packet and the same sibling proof inputs.
- `tests/test_materialize_next90_m118_fleet_ea_organizer_packets.py` and `tests/test_verify_next90_m118_fleet_ea_organizer_packets.py` cover the blocked path when the EA M118 organizer packet contract is still missing, the green path when it exists, and verifier rejection on packet drift.

Current proof posture:

- The new Fleet packet stays fail-closed when the Hub organizer or creator-publication verifiers fail, when the artifact-shelf publication receipt disappears, when the queue or registry row drifts, or when the EA M118 organizer packet contract has not landed yet.
- Fleet now also treats the paired Hub audience-filter receipt as mandatory publication proof. If `artifact_audience_filters` disappears, organizer-health turns blocked, publication readiness turns blocked, and the packet tells operators to restore the missing audience contract before trusting publication-facing summaries.
- Fleet now also refuses placeholder EA packet YAML: the operator-safe baseline pack and the M118 organizer followthrough pack both have to present the expected package ids, milestone ids, owned surfaces, and core contract sections before the packet can unblock.
- Fleet now treats the weekly governor freeze posture as a family rather than one exact string. If the governor packet keeps launch frozen through a derived state such as `freeze_with_rollback_watch`, publication readiness stays on `watch` instead of drifting back to `ready`.
- EA now exposes the M118-specific organizer event-prep packet contract at `/docker/EA/docs/chummer_organizer_packets/CHUMMER_ORGANIZER_PACKET_PACK.yaml`, so the Fleet packet can go green when the sibling Hub proofs and support counters stay aligned.
- The remaining watch-state is publication posture rather than missing implementation: the current weekly governor packet still advertises `freeze_launch`, so publication readiness stays `watch` even though organizer health and support risk pass.
- Fleet now fail-closes premature package closure metadata. If any Fleet queue row, design queue row, or canonical registry work-task flips to `status: complete` without the same `verify_closed_package_only` action and package-specific do-not-reopen reason on all three surfaces, organizer health turns blocked and the verifier forces the package back into proof repair instead of letting future shards reopen or mis-close the slice.
- The verifier now calls out `source_inputs` drift explicitly when upstream packet timestamps or packet-status fields move under a stale generated packet, instead of collapsing those failures into a generic drift message.
- `python3 scripts/verify_next90_m118_fleet_ea_organizer_packets.py` now works repo-locally without a long flag list because the verifier defaults to the same canonical packet and proof paths as the materializer.

Verification:

- `python3 tests/test_materialize_next90_m118_fleet_ea_organizer_packets.py`
- `python3 tests/test_verify_next90_m118_fleet_ea_organizer_packets.py`

This note still does not close the package in queue canon, but the implementation slice is materially complete. The remaining open work is queue/registry closeout authority and operator-loop rollout timing, not missing Fleet packet logic.
