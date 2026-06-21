# ADR-0002: Play Split Ownership Belongs to chummer6-mobile

Date: 2026-03-10

Status: accepted

## Context
- The program milestone source marks the mobile play split as incomplete and calls out package-only dependency enforcement plus play API contract canon as remaining work.
- The ownership matrix assigns play to the mobile/play shell, offline ledger, and local sync client, and forbids builder UX, rules math, and provider secrets there.
- Presentation review guidance already flags direct play-shell ownership in presentation as a P1 issue.

## Decision
- `chummer6-mobile` owns player and GM play-mode shell UX, offline ledger/cache behavior, local sync client behavior, and installable mobile or play-shell surfaces.
- `chummer6-ui` keeps builder, inspector, browser, and desktop workbench UX, but must not continue owning play-shell session or mobile surfaces.
- `chummer6-mobile` may depend only on `Chummer.Engine.Contracts`, `Chummer.Play.Contracts`, and `Chummer.Ui.Kit` for shared cross-repo boundaries unless a later ADR expands that set.
- Provider secrets, rules evaluation, and publication or moderation workflows remain outside `chummer6-mobile`.

## Consequences
- Extraction work moves session-shell ownership out of presentation instead of creating a second presentation-owned mobile path.
- Run-services exposes play-facing APIs through `Chummer.Play.Contracts` rather than through ad hoc client-specific DTOs.
- Play becomes a clean downstream consumer of engine contracts and shared UI primitives, which reduces lockstep risk for later repo extraction.
