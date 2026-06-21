# Runner Resume And Goal Pins

**Product:** Chummer6 / SR Campaign OS
**Design area:** Living Dossier, Campaign Continuity, Mobile Home
**Status:** Proposal

## Product rule

The good kind of engagement is continuity and anticipation.

Users should return because:

* their runner has a visible future
* rewards changed real goals
* the dossier remembers consequences

## Core objects

```yaml
CareerMetric:
  dossier_ref: runner_ref
  metric_key: nuyen_earned_lifetime
  value: 184000
  source_refs:
    - run_resolution_001
    - run_resolution_002
```

```yaml
GoalPin:
  dossier_ref: runner_ref
  target_kind: gear
  target_ref: wired_reflexes_rating_2
  label: Wired Reflexes Rating 2
  requires:
    nuyen: 149000
    downtime_days: 7
    rule_environment_ref: campaign_rule_env_ref
    approval: restricted_gear_if_needed
  progress:
    saved_nuyen: 47000
    karma_reserved: 0
  next_safe_action: add_to_nuyen_envelope
```

## User loops

### Runner Resume

```text
Runs survived
Karma earned
Nuyen earned
Contacts gained
Favors owed
Heat survived
Major scars and consequences
```

### Goal Pins

```text
Next cyberware
Next spell or focus
Next deck upgrade
Next vehicle or drone
Next lifestyle target
```

## Release gate

```text
player_pins_upgrade_and_tracks_progress_after_reward
```
