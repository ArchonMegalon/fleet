# Chummer6 Product Vision Audit

- generated_at: 2026-04-30T16:19:22.331179Z
- active_runs_count: 0
- productive_active_runs_count: 0
- nonproductive_active_runs_count: 0
- remaining_open_milestones: 11
- missing_frontier_ids: []
- ui_parity_visual_yes_no: 74/10
- ui_parity_behavioral_yes_no: 74/10

## What Users Still Want Or Miss

- Tell me what I can do right now, why, and what rule or source backs it.
- Adopt my current campaign without rebuilding my table from scratch.
- Keep campaign memory, consequences, and runner goals alive between sessions.
- Make the dense veteran workflows feel as fast and familiar as Chummer5A.
- Give me trusted mobile or companion continuity for travel, recap, and return moments.
- Let me publish, recap, share, and form tables from the same canonical campaign truth.

## Repo-Grounded Lost Potential Findings

### 1. The campaign OS promise still does not land at the table in the moments the canon says should feel magical.

- severity: high
- category: lost_potential
- owner_shards: ['shard-7', 'shard-1', 'shard-4', 'shard-6']
- milestone_area: Living campaign loop / lost-potential wave / mobile play shell
- reason: The canon explicitly says Chummer should feel like an explainable campaign OS with action help, local rule anchors, campaign adoption, runner goals, prep packets, and BLACK LEDGER consequence loops, but those loops still sit in open readiness or successor-wave posture rather than feeling closed in flagship truth.
- user_impact: Players and GMs do not yet get the calm-under-pressure payoff: what can I do right now, why, and what changed because of the last run.
- users_want_or_miss: ['tell me what I can still do right now', 'open the exact source or rule anchor without breaking flow', 'adopt my existing campaign without rebuilding everything', 'close a run and immediately see approved consequences']
- gates_to_close: ['live combat round with action budgets', 'local source or rule anchor open', 'existing campaign adoption', 'runner goal update', 'GM prep packet', 'ResolutionReport to WorldTick to player-safe news']
- evidence_paths: ['/docker/chummercomplete/chummer-design/products/chummer/ROADMAP.md', '/docker/chummercomplete/chummer-design/products/chummer/CONFIDENCE_READINESS_AND_CONTINUITY_GUIDE.md', '/docker/chummercomplete/chummer-design/products/chummer/LIVING_CAMPAIGN_LOOP_MATERIALIZATION_GUIDE.md', '/docker/chummercomplete/chummer-design/products/chummer/LOST_POTENTIAL_MATERIALIZATION_WAVE.md', '/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml', '/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json']

### 2. Veteran replacement still leaks on dense sub-workflows, so trust is broader than it is deep.

- severity: high
- category: visual_and_behavioral_parity
- owner_shards: ['shard-4', 'shard-6', 'shard-9', 'shard-13']
- milestone_area: Chummer5A parity closure and veteran replacement
- reason: The current parity matrix is still visual 74/10 and behavioral 74/10, with open families around translator/XML, dense builder and career flows, dice and initiative, import oracles, Hero Lab, contacts, lifestyles, history, and print/export surfaces.
- user_impact: A veteran Chummer5A user can still hit moments where the flow is slower, less familiar, or less trusted than the old tool.
- users_want_or_miss: ['the same dense builder rhythm as Chummer5A', 'fast import and migration rails', 'trusted dice, initiative, and table utility moments', 'full roster, contacts, lifestyles, and history comfort']
- gates_to_close: ['translator route screenshot/runtime proof', 'xml amendment editor screenshot/runtime proof', 'dense builder and career workflow proof', 'dice and initiative workflow proof', 'contacts and lifestyles proof', 'import oracles and Hero Lab proof']
- evidence_paths: ['/docker/chummercomplete/chummer-presentation/.codex-studio/published/CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json', '/docker/chummercomplete/chummer-design/products/chummer/CONFIDENCE_READINESS_AND_CONTINUITY_GUIDE.md', '/docker/chummercomplete/chummer-design/products/chummer/ROADMAP.md']

### 3. The trust story is stronger in canon than in the executable proof shelf.

- severity: high
- category: trust_and_release_proof
- owner_shards: ['shard-7', 'shard-1', 'shard-4', 'shard-6']
- milestone_area: Desktop release proof, installer truth, and restore confidence
- reason: The product canon emphasizes confidence, boring trust, and public proof shelf discipline, but desktop release closure still depends on stale or mismatched Windows startup-smoke proof and a still-open desktop-client readiness key.
- user_impact: Users may believe the product promise less at exactly the moments where they need confidence most: install, update, restore, and first-launch recovery.
- users_want_or_miss: ['a boring installer and update path', 'honest proof that the promoted build actually launches', 'confidence that recovery and restore really work']
- gates_to_close: ['Windows startup smoke against promoted bytes', 'desktop executable exit gate', 'release-channel and proof-shelf freshness']
- evidence_paths: ['/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json', '/docker/chummercomplete/chummer-design/products/chummer/ROADMAP.md', '/docker/chummercomplete/chummer-design/products/chummer/CONFIDENCE_READINESS_AND_CONTINUITY_GUIDE.md']

### 4. Mobile and companion continuity are still warnings even though the canon makes them part of the moat.

- severity: medium
- category: mobile_continuity
- owner_shards: ['shard-7', 'shard-1', 'shard-4', 'shard-6']
- milestone_area: Mobile play shell and return-moment continuity
- reason: Readiness still carries `mobile_play_shell=warning` while the canon says mobile should become the player and GM shell for table return, recap, continuity, and travel moments. Current leading reason: Recover-from-sync-conflict journey is blocked, not ready..
- user_impact: The product is still strongest at the desk, not in the between-session and at-table moments that actually drive habit and return.
- users_want_or_miss: ['phone-safe recap and next-step continuity', 'player-safe consequence feed', 'offline or degraded-network companion moments']
- gates_to_close: ['mobile recap and briefing continuity', 'player-safe consequence feed', 'travel and degraded-network companion views']
- evidence_paths: ['/docker/chummercomplete/chummer-design/products/chummer/CONFIDENCE_READINESS_AND_CONTINUITY_GUIDE.md', '/docker/chummercomplete/chummer-design/products/chummer/ROADMAP.md', '/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json', '/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml']

### 5. The horizon brands and community surfaces are named, but they are not yet woven back into the core product loop.

- severity: medium
- category: horizon_integration
- owner_shards: ['shard-10', 'shard-11']
- milestone_area: Media and social horizon tranche / artifact and community loop
- reason: The successor wave explicitly defines JACKPOINT, RUNBOOK PRESS, GHOSTWIRE, RUNSITE, TABLE PULSE, and Community Hub, but today they still read more like deferred horizons than like emotional extensions of build, play, campaign, recap, and trust.
- user_impact: Users miss the feeling that campaign artifacts, recaps, prep packets, route packs, and community moments belong to one coherent ecosystem.
- users_want_or_miss: ['shareable recap and publication artifacts', 'community-safe open-run and roster formation loops', 'route, travel, and observer moments tied to real campaign truth']
- gates_to_close: ['artifact studio and press workflow', 'open runs and Community Hub formation', 'route pack and travel continuity proof', 'bounded table-pulse and replay surfaces']
- evidence_paths: ['/docker/chummercomplete/chummer-design/products/chummer/ROADMAP.md', '/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml', '/docker/chummercomplete/chummer-design/products/chummer/projects/hub-registry.md', '/docker/fleet/repos/chummer-media-factory/docs/chummer-media-factory.design.v1.md']

### 6. The gating workflow still proves broad readiness more easily than the exact sub-flows that matter to humans.

- severity: medium
- category: workflow_gate_discipline
- owner_shards: ['shard-7', 'shard-1', 'shard-4', 'shard-6']
- milestone_area: Journey gates, screenshot packs, runtime-backed parity contracts
- reason: The repo now has real parity and readiness gates, but the remaining UI families are still unproven because those exact sub-dialogs and workflow moments are not all under direct screenshot/runtime contract yet.
- user_impact: A product manager or veteran tester can still feel that something is off even while the global readiness story looks healthier.
- users_want_or_miss: ['proof for the exact dialogs they actually use', 'behavioral parity, not just route existence', 'fewer places where visual drift hides behind aggregate green status']
- gates_to_close: ['sub-dialog screenshot packs', 'behavioral parity assertions for veteran flows', 'proof-shelf freshness for promoted artifacts']
- evidence_paths: ['/docker/chummercomplete/chummer-presentation/.codex-studio/published/CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json', '/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json', '/docker/chummercomplete/chummer-design/products/chummer/ROADMAP.md']

## Integration Opportunities

### 1. Community scheduling or roster-formation LTD

- repo_grounded: False
- owner_shards: ['shard-7', 'shard-6', 'shard-11']
- thesis: An acquisition or deeper integration around scheduling, campaign-group movement, and community roster formation would slot cleanly into Open Runs and Community Hub.
- why_fit: The canon already defines Open Runs, Community Hub, campaign-group movement, and organizer operations; what is missing is a truly great social and logistics layer around them.
- evidence_paths: ['/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml', '/docker/chummercomplete/chummer-design/products/chummer/CONFIDENCE_READINESS_AND_CONTINUITY_GUIDE.md']

### 2. Creator publication or editorial LTD

- repo_grounded: False
- owner_shards: ['shard-10', 'shard-11']
- thesis: A creator-publication, editorial, or print-oriented acquisition would fit RUNBOOK PRESS, JACKPOINT, and artifact shelf v2.
- why_fit: The repo already wants discovery, lineage, moderation, trust ranking, publication, and press-like artifact flows; an existing publishing asset could accelerate that lane materially.
- evidence_paths: ['/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml', '/docker/chummercomplete/chummer-design/products/chummer/projects/hub-registry.md', '/docker/fleet/repos/chummer-media-factory/docs/chummer-media-factory.design.v1.md']

### 3. Travel, route, or venue-intelligence LTD

- repo_grounded: False
- owner_shards: ['shard-7', 'shard-1', 'shard-4', 'shard-6']
- thesis: A route-pack or travel-operations acquisition would strengthen RUNSITE and mobile travel continuity.
- why_fit: The canon already names route packs, travel moments, mobile continuity, and observer views; the missing leverage is a stronger real-world travel and location intelligence substrate.
- evidence_paths: ['/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml', '/docker/chummercomplete/chummer-design/products/chummer/ROADMAP.md']

### 4. Privacy-safe coaching or post-session analytics LTD

- repo_grounded: False
- owner_shards: ['shard-7', 'shard-1', 'shard-4', 'shard-6']
- thesis: A bounded coaching or after-action analytics asset would accelerate TABLE PULSE without making it a second campaign truth source.
- why_fit: The canon explicitly wants bounded, privacy-safe post-session coaching; the hard part is productizing that loop without becoming creepy or authoritative.
- evidence_paths: ['/docker/chummercomplete/chummer-design/products/chummer/ROADMAP.md', '/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml', '/docker/chummercomplete/chummer-design/products/chummer/CONFIDENCE_READINESS_AND_CONTINUITY_GUIDE.md']

### 5. Manual-intake or migration-confidence LTD

- repo_grounded: False
- owner_shards: ['shard-4']
- thesis: A scanning, migration, or import-normalization asset would make manual intake and veteran migration much less expensive.
- why_fit: Confidence guide canon makes manual intake and migration confidence a core promise, and the current parity matrix still shows import/oracle and Hero Lab proof gaps.
- evidence_paths: ['/docker/chummercomplete/chummer-design/products/chummer/CONFIDENCE_READINESS_AND_CONTINUITY_GUIDE.md', '/docker/chummercomplete/chummer-presentation/.codex-studio/published/CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json', '/docker/chummercomplete/chummer-design/products/chummer/ROADMAP.md']

## Gate Recommendations

- Materialize the lost-potential wave as real screenshot and runtime journeys: The canon already names eight concrete loops; they should become visible release gates, not just roadmap language.
- Split parity proof by family instead of one broad veteran-replacement story: Translator/XML, import/oracles, dense builder, dice, contacts/lifestyles, and print/export need independent screenshot/runtime proof.
- Make promoted Windows bytes the only allowed desktop-proof target: That removes the stale-proof class of failure and aligns install truth with what users actually download.
- Gate community and horizon surfaces against core campaign truth: JACKPOINT, RUNBOOK PRESS, RUNSITE, TABLE PULSE, GHOSTWIRE, and Community Hub should enrich campaign truth, never fork it.

## Notes

- No missing flagship frontier milestone IDs were found in the live open milestone aggregate.
- The current parity audit reports zero currently-present removable Chummer6-only extras.
- Desktop readiness remains `missing`. Leading reason: Executable desktop exit gate proof is missing or not passed. Desktop shell/install/support liveliness must be proven from shipped artifacts.
- Other current readiness warnings: mobile=warning, ui_kit_and_flagship_polish=warning, media_artifacts=warning. mobile reason: Recover-from-sync-conflict journey is blocked, not ready.. polish reason: Build/explain/publish journey is blocked, not ready.. media reason: Build/explain/publish journey is blocked, not ready..
- The current opportunity audit is repo-grounded first and marks speculative acquisition or integration ideas explicitly as speculative.
