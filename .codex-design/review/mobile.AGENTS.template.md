# Mobile review checklist

Use this review context in the mirrored `chummer6-mobile` repo.

## Mobile-specific focus

- Flag raw source dependencies on UI or hub implementation roots as P1.
- Flag missing offline, stale-state, or replay-safety tests as P1.
- Flag builder or inspector UX added to the dedicated play shell as P1.
- Flag rule evaluation, runtime fingerprint generation, or provider-secret handling in mobile as P1.
- Flag dependencies beyond `Chummer.Engine.Contracts`, `Chummer.Play.Contracts`, and `Chummer.Ui.Kit` without explicit design approval as P1.

## Boundary check

Reject if the change:

- widens mobile into workbench, publish, moderation, or provider-routing ownership
- bypasses the package-only dependency boundary
- invents second semantic event families instead of consuming canonical session truth

## Runtime seam check

Reject if the change:

- weakens rejoin, replay, or resume guarantees
- hides offline queue or cache failures behind silent fallback behavior
- treats cross-device continuity as best-effort instead of explicit stale-lineage-safe behavior

## Review summary

Every substantive review should answer:

- play-shell fit: pass/fail
- package-only fit: pass/fail
- offline-state fit: pass/fail
- mirror fit: pass/fail
- milestone fit: pass/fail
- required design-repo follow-up: yes/no
