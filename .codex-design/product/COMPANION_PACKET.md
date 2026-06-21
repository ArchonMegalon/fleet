# Companion Packet

## Purpose

Define the canonical runtime packet that powers the first-party companion.

This file sits one layer below `COMPANION_PERSONA_AND_INTERACTION_MODEL.md` and one layer above `COMPANION_EVENT_SCHEMA.yaml`.

It answers one practical question:

> What exact object should Chummer emit when a companion-worthy fact becomes true?

## Core rule

**Trigger truth stays in Chummer.**
**Phrasing, packs, and media stay downstream.**

That means:
- `chummer6-core`, `chummer6-hub`, and `chummer6-ui` decide whether a trigger fired
- `CompanionPacket` carries inspectable first-party truth
- EA may compile or refresh wording, tone packs, and rare media briefs from that packet
- desktop/mobile runtime must still work if EA, LLM, or media lanes are unavailable

The packet is a truth wrapper, not a chat request.

## Ownership split

### `chummer6-core`
Owns:
- Build Lab trigger truth
- rule-environment and compatibility trigger truth
- deterministic fact refs

### `chummer6-hub`
Owns:
- install, claim, update, support, publication, and campaign-workspace trigger truth
- account, channel, and closure truth
- packet emission for hosted or account-scoped events

### `chummer6-ui`
Owns:
- desktop runtime trigger presentation
- local fallback templates
- suppression execution
- dismissal receipts

### `chummer6-mobile`
Owns:
- mobile runtime trigger presentation
- device-role-specific suppression
- bounded post-session or recap prompts when that lane is active

### `executive-assistant`
Owns:
- downstream companion pack compilation
- locale and tone variants
- annoyance-budget tuning proposals
- media brief preparation
- no trigger authority

### `chummer6-media-factory`
Owns:
- optional attached audio, video, and preview assets
- no trigger authority

## Packet contract

Chummer should emit a `CompanionPacket` whenever the companion runtime needs to decide whether to show:
- a micro-bark
- a bark with action chips
- an evidence drawer
- a rare media-backed scene

The packet must be stable enough to cache, inspect, suppress, replay in tests, and render without a live model call.

## Required fields

- `packet_id`
- `trigger_class`
- `event_type`
- `trigger_version`
- `emitted_at`
- `owning_domain`
- `severity`
- `urgency`
- `locale`
- `surface_allowlist`
- `device_role`
- `install_role`
- `mask_id`
- `persona_mode_default`
- `fact_refs`
- `allowed_actions`
- `suppression`
- `ea_compile`
- `media_eligibility`
- `expiry`

## Field semantics

### Identity

- `packet_id`
  Stable opaque id for this emitted packet instance.
- `trigger_class`
  Named companion trigger from `COMPANION_TRIGGER_REGISTRY.yaml`.
- `event_type`
  Machine-level event family from `COMPANION_EVENT_SCHEMA.yaml`.
- `trigger_version`
  Version of the trigger contract that emitted the packet.

### Context

- `emitted_at`
  UTC timestamp.
- `owning_domain`
  One of: `install`, `update`, `build_lab`, `campaign_workspace`, `runboard`, `support`, `restore`, `publication`, `public_hub`, `table_pulse`.
- `locale`
  BCP-47 locale.
- `surface_allowlist`
  Exact first-party surfaces allowed to render this packet.
- `device_role`
  Current device posture such as `desktop_primary`, `preview_scout`, or `mobile_play`.
- `install_role`
  Current install relationship such as `claimed_primary`, `claimed_secondary`, or `anonymous_public`.

### Presentation posture

- `severity`
  `info`, `celebration`, `caution`, or `blocking`.
- `urgency`
  `ambient`, `suggested`, `interrupting`, or `critical`.
- `mask_id`
  `concierge`, `analyst`, `handler`, or `echo`.
- `persona_mode_default`
  Default tone assumption when the user has not overridden it.
- `allowed_joke_budget`
  `none`, `light`, or `medium`.
- `evidence_drawer_required`
  Whether the user must be able to inspect grounded evidence from the bark.

### Truth and action

- `fact_refs`
  Inspectable first-party references explaining why the packet exists.
- `fact_summary`
  Short machine-readable summary of the facts that changed.
- `allowed_actions`
  Zero to three first-party actions the runtime may expose.
- `forbidden_claims`
  Claims the runtime, EA, or LLM must not improvise from this packet.

### Suppression and safety

- `suppression`
  Carries cooldown, repetition, and escalation rules.
- `privacy_class`
  `public_safe`, `signed_in`, `campaign_private`, `gm_private`, or `support_private`.
- `requires_user_gesture_for_voice`
  Whether voice interaction must stay push-to-talk or text-only.
- `suppress_until`
  Optional explicit timestamp when the packet becomes displayable again.
- `expiry`
  Packet expiry time; expired packets must not render.

### Downstream compile and media

- `ea_compile`
  Declares whether EA may compile phrasing or packs from this packet.
- `fallback_pack_id`
  First-party pack id to use when EA or live phrasing is unavailable.
- `media_eligibility`
  Whether this packet may attach optional pre-rendered audio, video, or cards.
- `media_ref`
  Optional attached media artifact ref resolved by Chummer-owned stores.

## Suppression model

Every packet should carry a suppression block like this:

```yaml
suppression:
  cooldown_scope: trigger_class_per_surface
  cooldown_seconds: 14400
  max_impressions_per_day: 2
  requires_material_change: true
  reset_on_action:
    - clicked_primary_action
    - opened_evidence_drawer
```

This is not optional product polish.
Without explicit suppression semantics, the companion becomes noise.

## EA compile model

EA compile is allowed only when the packet says so.

Example:

```yaml
ea_compile:
  eligible: true
  mode: precompiled_pack_preferred
  allowed_outputs:
    - line_variant_pack
    - locale_variant_pack
    - rare_media_brief
  runtime_blocking: false
```

Rules:
- EA may restyle presentation
- EA may not decide whether the packet fired
- EA may not add unsupported facts
- runtime must have a local fallback path

## Media model

Most packets should stay text-first.

Media-backed moments should be rare and high-trust:
- first launch
- mission briefing ready
- campaign primer ready
- fix-confirmation
- player-safe recap prompt

Example:

```yaml
media_eligibility:
  allowed: true
  render_modes:
    - bark_with_chips
    - evidence_drawer
    - companion_scene
  autoplay_policy: click_to_play
  preferred_lane: vidBoard
  required_text_fallback: true
```

## Minimal packet example

```yaml
packet_id: cp_01hsupportfix
trigger_class: support_fix_confirmation
event_type: fix_closure
trigger_version: 1
emitted_at: 2026-04-16T20:00:00Z
owning_domain: support
severity: celebration
urgency: suggested
locale: en-US
surface_allowlist:
  - home_cockpit
  - support_case_detail
device_role: desktop_primary
install_role: claimed_primary
mask_id: concierge
persona_mode_default: practical
allowed_joke_budget: light
evidence_drawer_required: true
fact_refs:
  - kind: support_case
    ref: support_case:sc_12345
  - kind: release_channel
    ref: release_channel:preview
  - kind: install
    ref: install:inst_abc123
fact_summary:
  fix_reached_user_channel: true
  update_available_now: true
allowed_actions:
  - id: open_update_flow
    label: Update now
  - id: show_fix_receipt
    label: Show why
forbidden_claims:
  - do_not_claim_issue_fixed_before_channel_truth
suppression:
  cooldown_scope: trigger_class_per_install
  cooldown_seconds: 28800
  max_impressions_per_day: 1
  requires_material_change: true
ea_compile:
  eligible: true
  mode: precompiled_pack_preferred
  runtime_blocking: false
  fallback_pack_id: support_fix_confirmation_default
media_eligibility:
  allowed: true
  render_modes:
    - bark_with_chips
    - companion_scene
  autoplay_policy: never
  preferred_lane: vidBoard
  required_text_fallback: true
expiry: 2026-04-23T20:00:00Z
```

## Release-proof expectations

The companion lane should eventually prove:
- packets are emitted from Chummer-owned facts
- packets still render with EA disabled
- packets still render with media lanes disabled
- suppression prevents repetition
- evidence drawers open when required
- locale fallback works
- voice remains opt-in

## Follow-through

This file should remain aligned with:
- `COMPANION_PERSONA_AND_INTERACTION_MODEL.md`
- `COMPANION_EVENT_SCHEMA.yaml`
- `COMPANION_TRIGGER_REGISTRY.yaml`
- `BUILD_LAB_PRODUCT_MODEL.md`
- `CAMPAIGN_WORKSPACE_AND_DEVICE_ROLES.md`
- `ACCOUNT_AWARE_INSTALL_AND_SUPPORT_LINKING.md`
