# Source Anchor And Local Rulebook Binding

**Product:** Chummer6 / SR Campaign OS  
**Design area:** Explain Everywhere, Rules Navigator, Build, Play  
**Status:** Proposal / release-gated loop

## Product rule

Chummer should help users open the right rule page without becoming a rulebook host.

This lane is the source-open branch of `EXPLAIN_EVERY_VALUE_AND_GROUNDED_FOLLOW_UP.md`, not a detached citation garnish.
Every `SourceAnchor` shown to a user must stay attached to the same `ExplanationPacket`, bounded follow-up packet, or migration receipt that made the claim.

It must not:

* distribute copyrighted PDFs
* upload user PDFs to cloud storage
* depend on remote rulebook hosting for explain receipts

## Core objects

```yaml
SourceAnchor:
  id: sr6_core_minor_actions
  ruleset: sr6
  source_pack_ref: sr6_core
  locale: en-US
  page: 40
  section_hint: Minor Actions
  anchor_key: sr6.core.actions.minor
  binding_policy: user_local_file_only
```

```yaml
LocalSourceBinding:
  install_ref: device_claim_ref
  source_pack_ref: sr6_core
  local_file_hash: local_only
  local_path_storage: device_private
  cloud_sync: false
```

## Explain drawer behavior

The source row is part of the same text-first explain drawer or quick-explain panel that owns the current value.
It must not appear as floating chrome with no packet, stale-state, or follow-up truth behind it.

If a binding exists:

```text
Source: SR6 Core, p. 40
[Open local rulebook]
```

If a binding does not exist:

```text
Source: SR6 Core, p. 40
Bind your local PDF on this device to open directly.
```

If the underlying snapshot, rule environment, or migration receipt changes, the open-local affordance must go visibly stale with the rest of the explanation surface instead of pretending the previous anchor still matches current truth.

## Privacy rule

Local file paths and local hashes stay device-private.
They do not become public telemetry, support payload defaults, or campaign truth.

## Repo split

* `chummer6-core`: source anchors, citations, ruleset mapping
* `chummer6-ui`: desktop binding workflow and Rules Navigator surfaces
* `chummer6-mobile`: local open-on-device affordance where the platform permits it
* `chummer6-hub`: no cloud authority over local rulebook files

## First release gate

```text
user_opens_local_rulebook_from_explain_drawer
```

Exit:

* a user binds one local PDF on one device
* a calculated value cites a `SourceAnchor` from the same packet-backed explain surface that produced the value
* the cited local rulebook page opens from the explain drawer or quick-explain panel
* stale packet state disables or refreshes the local-open affordance before Chummer claims current truth again
