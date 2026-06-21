# KARMA FORGE Discovery and House-Rule Intake

## Purpose

KARMA FORGE needs a governed discovery pipeline before it becomes an implementation lane.

The risk is not only engineering complexity.
The risk is table trust:

* who can change the rule
* who can see the change
* what must be explained before play
* what must be portable across devices
* what must be reversible

## Discovery goal

Find the actual demand behind the user's wording.

Examples of likely signal buckets:

* campaign-scoped gear availability overlays
* alternate character-generation presets
* advancement / karma / nuyen pacing variants
* Edge economy variants
* Matrix simplification variants
* magic drain / ritual / spirit variants
* lifestyle and downtime rules
* NPC/opposition scaling
* BLACK LEDGER faction-linked unlocks
* Chummer5a custom-data migration blockers

## Recruitment and intake flow

1. ProductLift public idea/vote cluster
   * public demand collection only; no support, copyrighted source text, or private table material
2. `FacePop` public prompt
   * “Got a house rule your table depends on? Help us make KARMA FORGE useful instead of chaotic.”
3. `Deftform` pre-screen
   * role
   * edition
   * table type
   * rule category
   * severity
   * current workaround
4. `Icanpreneur` adaptive interview
5. `Lunacal` follow-up for high-signal cases
6. `MetaSurvey` quant validation after clustering
7. `Teable` candidate review board as a projection of Hub-owned demand packets
8. Product Governor decision
9. ProductLift, Signitic, or Emailit closeout only after the decision is recorded in Chummer-owned truth

`KARMA_FORGE_DISCOVERY_LAB_WORKFLOWS.yaml` is the machine-readable operating loop for this discovery system.
Teable may expose candidate rows, curator notes, proposed classifications, and reviewer assignments, but write-backs return as `AdminIntent` for Hub validation.

## Icanpreneur interview tracks

### GM house-rule track

Core questions:

* What rule does your table change most often?
* Why does the default behavior not work?
* Who needs to see the change before play?
* Does it affect legality, cost, availability, dice pools, advancement, display text, or only GM guidance?
* Does it apply to one character, one campaign, one scene, one district, or all your games?
* Should players be blocked, warned, or simply informed?
* What should happen when the rule changes mid-campaign?
* How do you currently enforce it?
* Would you share it as a reusable package?

### Player trust track

Core questions:

* What house rules have surprised or frustrated you?
* What do you want Chummer to show before you join a campaign?
* Would you accept a campaign rule change if Chummer showed a before/after build impact?
* What would make a custom rule feel unsafe?
* Do you need rollback, comparison, explanation, or approval?

### Creator / publisher track

Core questions:

* What rule variant would you publish for other tables?
* What compatibility labels would you need?
* How would you version it?
* What would make you confident other GMs can use it?
* Should Chummer provide preview builds, example runners, or test cases?

### Organizer / BLACK LEDGER track

Core questions:

* Do you need season-wide rule environments?
* Should faction projects unlock availability or threats?
* How should players see world-linked rewards?
* Should unlocks be temporary, campaign-scoped, or reusable packs?
* What prevents faction mechanics from feeling unfair?

### Chummer5a veteran / migration track

Core questions:

* What custom data or amend behavior do you rely on today?
* Which files or package types matter most?
* What breaks most often?
* What must Chummer6 preserve?
* What legacy behavior should Chummer6 intentionally not preserve?

## Canonical output: HouseRuleDemandPacket

```yaml
house_rule_demand_packet:
  id: hrp_2026_04_20_001
  title: "Campaign-scoped gear availability overlay"
  source:
    intake_channel: "FacePop -> Deftform -> Icanpreneur"
    respondent_role: "GM"
    edition: "SR6"
    table_type: "home_campaign"
    interview_ref: "icanpreneur_interview_ref"
    consent_ref: "hub_consent_receipt"
  user_words:
    summary: "I want to mark gear unavailable until my campaign unlocks it."
    current_workaround: "Manual review and Discord notes."
  interpreted_need:
    summary: "Campaign-scoped availability overlay with build-impact preview and player-visible receipts."
    confidence: "high"
  affected_domains:
    - gear
    - availability
    - character_build_legality
    - campaign_progression
  desired_scope:
    - campaign
    - reusable_pack_candidate
  likely_chummer_objects:
    - RuleEnvironment
    - AmendPackage
    - CampaignOverlayPackage
    - ActivationReceipt
  possible_black_ledger_objects:
    - WorldOffer
    - ScenarioModifier
  trust_requirements:
    player_visible_before_join: true
    build_diff_required: true
    rollback_required: true
    approval_required: true
    receipt_required: true
  portability_requirements:
    cross_device_restore: true
    package_fingerprint_required: true
  priority_signals:
    blocker_score: 4
    frequency_signal: "medium"
    shareability_score: 5
    implementation_risk: "medium"
    monetization_relevance: "possible_premium_gm_tool"
  classification:
    current_status: "candidate"
    decision_needed: true
    proposed_route: "KARMA_FORGE"
  next_steps:
    - "Collect three example restricted categories."
    - "Validate with player trust track."
    - "Prototype diff preview in RuleEnvironment UX."
```

## Candidate classification

```yaml
candidate_decisions:
  reject:
    meaning: "Not aligned with Chummer scope or trust model."
  document_only:
    meaning: "Needs guidance/help text, not engine or package work."
  preset_candidate:
    meaning: "Can become a named RulesPreset."
  amend_package_candidate:
    meaning: "Needs canonical AmendPackage representation."
  campaign_overlay_candidate:
    meaning: "Applies at campaign/workspace level."
  world_offer_candidate:
    meaning: "Belongs to BLACK LEDGER or mission-market unlocks."
  scenario_modifier_candidate:
    meaning: "Applies to mission/run/district packet."
  core_ruleset_gap:
    meaning: "Actually indicates missing or incorrect engine behavior."
  legacy_import_candidate:
    meaning: "Needed for Chummer5a custom-data migration."
  research_more:
    meaning: "Insufficient confidence."
```

## NextStep process templates

### KARMA FORGE discovery sprint

1. define research question
2. approve interview tracks
3. publish FacePop recruitment prompt
4. publish Deftform pre-screen
5. launch Icanpreneur interviews
6. review first interview cohort
7. cluster findings with EA
8. draft `HouseRuleDemandPacket` outputs
9. run MetaSurvey validation
10. Product Governor decision
11. update KARMA FORGE backlog
12. publish discovery closeout
13. close ProductLift/Emailit/Signitic voter or participant follow-up through Hub-owned receipts

### High-signal house-rule follow-up

1. candidate flagged
2. schedule Lunacal call
3. prepare examples and workaround
4. conduct call
5. update packet
6. classify rule-environment mapping
7. approve or reject prototype

### Rule-pack prototype approval

1. create sample `AmendPackage` or `CampaignOverlayPackage` design
2. generate activation-receipt mock
3. review player-visible diff
4. review rollback path
5. review portability behavior
6. approve prototype
7. add core/UI/Hub tasks

## Quality gate before implementation

A house-rule candidate is not ready for implementation until:

* at least one GM need is clear
* player trust impact is known
* rule-environment mapping is identified
* portability / restore behavior is defined
* rollback and activation-receipt behavior is defined
* copyright / provenance risk is cleared
* Product Governor has assigned a route

## Success metrics

```yaml
metrics:
  interviews_completed:
    target_first_sprint: 30
  gm_interviews:
    target_first_sprint: 12
  player_interviews:
    target_first_sprint: 8
  creator_interviews:
    target_first_sprint: 5
  organizer_interviews:
    target_first_sprint: 3
  chummer5a_veteran_interviews:
    target_first_sprint: 5
  demand_packets_created:
    target_first_sprint: 20
  clusters_with_5_or_more_signals:
    target_first_sprint: 3
  candidates_promoted_to_design:
    target_first_sprint: 2
  candidates_rejected_with_reason:
    target_first_sprint: 5
```

## First implementation rule

The first implementation task is not engine work.
The first implementation task is a governed discovery pipeline:

1. public invitation
2. structured pre-screen
3. adaptive interview
4. normalized packet
5. EA clustering
6. Product Governor decision
7. backlog candidate routing
8. prototype only after trust and scope are known
