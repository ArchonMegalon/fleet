# BLACK LEDGER MVP 001

**Product:** Chummer6 / SR Campaign OS
**Design area:** BLACK LEDGER, Campaign Consequence, Newsreel
**Status:** Proposal / first proof slice

## Goal

Prove a living-world consequence loop without requiring broad simulation.

The first slice is:

```text
Seattle Heat Tick 001
```

## Loop

```text
GM closes a run
-> GM files ResolutionReport
-> Chummer proposes deltas
-> GM approves or edits
-> one world tick is recorded
-> one player-safe news item is emitted
-> next-session cockpit shows the consequence
```

## Core objects

```yaml
ResolutionReport:
  run_ref: openrun_001
  approved_by: gm_ref
  outcomes:
    - target_extracted_alive
    - collateral_damage_high
  deltas:
    heat: +2
    faction_pressure:
      renraku: +1
    district_pressure:
      redmond: +1
  publication_candidates:
    - city_ticker_public_safe
    - gm_private_aftermath
```

```yaml
WorldTick:
  world_ref: seattle_207x
  tick_ref: heat_tick_001
  cause_refs:
    - resolution_report_openrun_001
  changes:
    - kind: district_pressure
      district: redmond
      delta: +1
    - kind: faction_alertness
      faction: renraku
      delta: +1
  gm_approved: true
```

```yaml
NewsItem:
  visibility: player_safe
  headline: Security presence rises in Redmond after extraction rumor
  source_refs:
    - world_tick_heat_tick_001
  spoiler_level: low
```

## Rule

The world may react, but only through GM-approved, receipt-backed state.

Rendered news, ticker cards, or media clips never become world truth.

## First release gates

```text
gm_closes_run_and_generates_resolution_report
resolution_report_creates_world_tick_and_player_safe_news_item
```
