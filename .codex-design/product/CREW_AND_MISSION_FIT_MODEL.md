# Crew And Mission Fit Model

**Product:** Chummer6 / SR Campaign OS
**Design area:** Open Runs, Campaign Prep, Crew Analysis
**Status:** Proposal

## Design stance

Crew fit should start useful conversations.
It should not gate play, rank players, or shame builds.

## Core objects

```yaml
CrewCapabilityVector:
  crew_ref: crew_ref
  capabilities:
    face: strong
    matrix: weak
    magic: partial
    stealth: strong
    transport: weak
    healing: missing
    heavy_combat: strong
    legwork: medium
```

```yaml
MissionFitCheck:
  job_packet_ref: job_ref
  crew_ref: crew_ref
  fit:
    overall: risky
    strengths:
      - stealth
      - heavy_combat
    gaps:
      - matrix_support
      - transport_escape
  suggestions:
    - hire_npc_decker
    - acquire_escape_vehicle
    - adjust_legwork_plan
```

## User-facing phrasing

```text
You can take this job, but the crew has weak Matrix coverage.

Suggested prep:
  hire a decker contact
  buy one-shot Matrix support
  reduce Matrix-heavy objectives
```

## Uses

* Open Run join preflight
* GM prep and packet selection
* crew planning between sessions
* spotlight and risk conversation
