# Prep Packet Factory And Procedural Tables

**Product:** Chummer6 / SR Campaign OS
**Design area:** GM Prep, Job Packets, Opposition, Legwork
**Status:** Proposal

## Design stance

Procedural generation only matters when it becomes playable prep.

The product should not begin with broad random-content ambition.
It should begin with one usable packet a GM can run tonight.

## Core object

```yaml
JobPacket:
  hook: string
  patron: contact_or_faction_ref
  target: person_place_object_or_data_ref
  pressure:
    heat: low_medium_high
    faction_attention:
      - faction_ref
  legwork:
    - question
    - suggested_contact_type
    - possible_clue
  opposition_packet_refs:
    - corp_security_light_001
  facility:
    layout_seed: office_lab_warehouse_arcology_node
    security_zones:
      - public
      - restricted
      - secure
  complications:
    - rival_team
    - unexpected_spirit
    - media_attention
  reward_model:
    nuyen_range: [8000, 15000]
    karma_range: [4, 7]
  exports:
    - gm_private_pdf
    - player_safe_brief
    - foundry_or_vtt_hint
```

## First proof

```text
one job
one facility
one opposition packet
one legwork board
one complication
one resolution flow
```

## Repo split

* `chummer6-core`: packet-compatible rules truth, opposition and fit primitives
* `chummer6-hub`: packet storage, campaign linkage, resolution followthrough
* `chummer6-ui`: desktop packet editor and GM prep flow
* `chummer6-media-factory`: optional rendered briefs and packet exports

## Release gate

```text
gm_creates_a_playable_prep_packet
```
