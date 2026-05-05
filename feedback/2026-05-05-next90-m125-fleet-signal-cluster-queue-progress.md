# M125 Fleet signal-cluster queue synthesis progress

Package: `next90-m125-fleet-add-signal-cluster-to-queue-synthesis-for-repeated-produ`
Owned surfaces: `add_signal_cluster_to_queue:fleet`

This pass lands the Fleet-owned signal-cluster queue synthesis packet for milestone `125.3`.

- `scripts/materialize_next90_m125_fleet_signal_cluster_queue.py` now compiles one package-scoped queue-synthesis artifact from the canonical registry and queue rows, the public-signal canon docs, the weekly product pulse, the support packet feed, and a deterministic signal-source snapshot.
- `scripts/verify_next90_m125_fleet_signal_cluster_queue.py` now recomputes that packet with default canonical inputs so the generated artifact can be revalidated without rebuilding the argument list by hand.
- `tests/test_materialize_next90_m125_fleet_signal_cluster_queue.py` and `tests/test_verify_next90_m125_fleet_signal_cluster_queue.py` cover the green path, the blocked path when a signal packet loses required classification fields, live snapshot derivation when no explicit source file is supplied, and verifier rejection on queue-synthesis drift.

Audit and improvement pass:

- The first live cut overfit `support` keywords and pushed every weekly cluster toward support-closure routing, even when the cluster was really about public guide and trust copy. The routing heuristic now prioritizes public-guide/content/visibility language before generic support language, so visibility and publication clusters resolve to upstream docs/help queue slices instead of the wrong closure lane.
- The live source-family coverage was also undercounting ClickRank because the detector ignored `cluster_id` evidence such as `long_pole_visibility`. The live derivation now folds cluster ids into source-family inference, which restored ClickRank coverage on the emitted queue candidates.

Current proof posture from the live packet:

- The package passes and emits `3` proposal-only queue candidates from the current weekly pulse clusters.
- Current live family coverage is complete for the target public-signal families: `ProductLift`, `Katteb`, `ClickRank`, `support`, and `public-guide`.
- The candidates stay explicitly non-authoritative: Fleet proposes bounded queue slices, while Product Governor and `chummer6-design` remain the canon and owner decision authorities.

Verification:

- `pytest -q /docker/fleet/tests/test_materialize_next90_m125_fleet_signal_cluster_queue.py /docker/fleet/tests/test_verify_next90_m125_fleet_signal_cluster_queue.py`
- `python3 /docker/fleet/scripts/materialize_next90_m125_fleet_signal_cluster_queue.py`
- `python3 /docker/fleet/scripts/verify_next90_m125_fleet_signal_cluster_queue.py`
