# UI review checklist

Use this review context in the mirrored `chummer6-ui` repo.

## UI-specific focus

- Flag rules math or engine authority logic in UI as P1.
- Flag session or mobile routes left in workbench/browser packages as P1.
- Flag direct play-shell ownership that should live in `chummer6-mobile` as P1.
- Flag shared component changes that bypass `Chummer.Ui.Kit` package ownership as P1.
- Flag workbench code that introduces offline ledger or sync-cache behavior as P1.

## Boundary check

Reject if the change:

- leaves dedicated play/mobile behavior in UI-owned packages
- reintroduces copied shared contracts or source-level UI-kit ownership
- treats feature completion as proof that the boundary reset is done

## Contract check

Reject if the change:

- creates a duplicate shared DTO family
- uses ambiguous or legacy package names when canon is already defined
- moves rules truth, explain traces, or runtime semantics into UI-owned code

## Review summary

Every substantive review should answer:

- scope fit: pass/fail
- boundary fit: pass/fail
- contract fit: pass/fail
- mirror fit: pass/fail
- milestone fit: pass/fail
- required design-repo follow-up: yes/no
