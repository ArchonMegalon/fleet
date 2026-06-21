# ADR-0005: Public Surface Meaning Is Design-First

Date: 2026-03-24

Status: accepted

## Context

- `chummer.run` and `Chummer6` already serve different public jobs, but the decision memory for that split lived mostly in prose canon.
- The design repo now owns the landing manifest, feature registry, user model, auth posture, guide policy, and public help copy.
- Hub and downstream guide generators consume that truth, but neither should become a second public feature map.

## Decision

- `chummer.run` is the product front door, proof shelf, and invitation surface.
- `Chummer6` is the deeper explainer and horizon guide.
- Canonical public meaning lands in `chummer6-design` first through files such as:
  - `PUBLIC_LANDING_POLICY.md`
  - `PUBLIC_LANDING_MANIFEST.yaml`
  - `PUBLIC_FEATURE_REGISTRY.yaml`
  - `PUBLIC_USER_MODEL.md`
  - `PUBLIC_GUIDE_POLICY.md`
- Hub may project this truth and downstream guides may explain it, but neither may redefine public feature, route, or availability meaning.

## Consequences

- Public-surface drift is a design defect, not a copy-edit issue.
- Landing, guide, and public account surfaces must agree on available, preview, and horizon posture.
- Public-surface work now has an ADR-grade anchor instead of relying only on scattered canon files.
