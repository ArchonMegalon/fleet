# M112 Design Campaign Canon closeout

Package: `next90-m112-design-campaign-canon`
Frontier: `2514722929`
Date: `2026-04-23`

## What shipped

The design-owned campaign OS canon now treats downtime, aftermath, heat, faction posture, contact truth, reputation, and next-session return as one first-class campaign-memory lane.

Updated campaign canon:

* `CAMPAIGN_SPINE_AND_CREW_MODEL.md` now defines campaign memory and consequence truth as part of the canonical campaign spine instead of leaving downtime and relationship fallout implicit.
* `CAMPAIGN_WORKSPACE_AND_DEVICE_ROLES.md` now makes campaign-memory packets, return-loop actions, and consequence cues first-class workspace promises rather than optional recap garnish.
* `journeys/run-a-campaign-and-return.md` now treats downtime, aftermath, heat, faction stance, contact truth, and reputation as part of the main happy path and failure posture.
* `CAMPAIGN_OS_GAP_AND_CHANGE_GUIDE.md` now states that lived campaign-OS maturity requires first-class campaign-memory truth for downtime, aftermath, heat, faction posture, contact truth, reputation, and return-loop actions.
* `scripts/ai/validate_next90_m112_design_campaign_canon.py` now fail-closes the package against campaign-canon doc drift, standard verifier drift, feedback closeout drift, and canonical registry/queue drift.

Validation run:

* `python3 scripts/ai/validate_next90_m112_design_campaign_canon.py`

## Do not reopen

Do not reopen this slice for generic campaign polish.
Reopen only when campaign-memory canon changes require new downtime, aftermath, heat, faction, contact, reputation, or return-loop rules, or when the validator proves drift in the M112 package anchors.
