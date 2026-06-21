# Support Packet And Calculation Report UX

**Product:** Chummer6 / SR Campaign OS
**Design area:** Improve, Explain Everywhere, Support
**Status:** Proposal

## Product promise

Support packets should feel like a trust feature, not a punishment.

The user-facing experience is:

> Chummer helps you file a useful issue in 20 seconds.

## Core action

Every important explain drawer may expose:

```text
Report this calculation
```

That action should open a bounded support-packet flow rather than a blank form.

## Default packet contents

```yaml
CalculationReportPacket:
  app_version: required
  platform: required
  release_channel: required
  ruleset_fingerprint: required
  rule_environment_ref: required
  calculated_value: required
  expected_value_user_entered: optional
  explain_trace: required
  source_anchor_refs: optional
  recent_change_receipts: optional
  dossier_snapshot:
    default_posture: redacted_or_minimum_needed
  telemetry_policy:
    local_paths: forbidden
    unbound_source_files: forbidden
```

## Product rules

The packet flow must:

* explain what is included
* allow redacted or minimal posture by default
* keep local file paths and bound-PDF internals out of telemetry
* attach enough structured truth that maintainers can reproduce the complaint

The packet flow must not:

* dump raw diagnostics without explanation
* require the user to write a perfect repro from scratch
* treat support as a vendor form disconnected from product truth

## Visible affordances

Good surfaces for support-packet entry:

* explain drawer
* import or migration review queue
* rule-environment conflict warning
* campaign adoption report
* support and fix-confirmation surfaces

## Repo split

* `chummer6-core`: explain trace, source anchors, ruleset fingerprints, change receipts
* `chummer6-ui`: report-this-calculation affordance and packet review UI
* `chummer6-hub`: support-case intake, packet storage truth, case linkage
* `fleet`: packet-backed repro and journey evidence only after Hub intake normalization

## Release-facing outcome

Users should be able to say:

```text
I reported the wrong number.
The packet already had the math, the ruleset, and what changed.
I did not have to guess what support needed.
```
