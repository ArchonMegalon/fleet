# Campaign Adoption Wizard

**Product:** Chummer6 / SR Campaign OS
**Design area:** Intake, Migration, Campaign Continuity
**Status:** Proposal / flagship journey candidate

## Problem

Most tables will not start clean.
They already have runners, history gaps, house rules, contacts, debts, and unfinished jobs.

Chummer should let them keep playing without pretending missing history does not exist.

## Flow

```text
1. Create campaign from existing table.
2. Enter or import current runners.
3. Mark unknown history explicitly.
4. Capture active house rules.
5. Capture active contacts, debts, jobs, heat, and rewards.
6. Choose "start ledger from today."
7. Produce Adoption Confidence report.
```

## Output

```yaml
CampaignAdoptionRecord:
  campaign_ref: campaign_ref
  safe_to_play: true
  confidence_percent: 81
  known:
    runners: 4
    active_jobs: 2
    contacts: 7
    house_rules: 3
  unknowns:
    - exact_karma_spend_history
    - old_gear_legality
  recommended_next_actions:
    - start_ledger_from_today
    - preserve_legacy_notes
    - revalidate_future_changes_only
```

## Rule

Unknown provenance stays explicit.
The wizard must never silently invent history just to make import feel clean.

## Release gate

```text
existing_campaign_adopted_without_rebuilding_full_history
```
