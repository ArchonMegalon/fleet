# Parity Completion Instruction

Use this exact instruction:

```text
Work this to completion at maximum practical speed.

Primary goal:
Make Chummer6 Avalonia and Blazor feel and behave as close to Chummer5a as realistically possible, targeting 98%+ similarity in the main shell, utility dialogs, add/edit flows, dense workbench posture, and first-minute veteran workflows. Also align SR4 and SR6 UI wording and posture in the same classic dense style.

Execution model:
- Do not stop after one batch.
- Keep looping autonomously: audit -> implement -> validate -> commit/push -> pick the next highest-value gap -> repeat.
- Use direct owner-repo implementation for the highest-value parity slices.
- In parallel, keep Fleet working adjacent slices, audits, proof refresh, and readiness follow-through.
- Do not wait for Fleet if you can directly improve the owner repo.
- Retask Fleet guidance/handoff whenever the next parity slice changes.

Priority order:
1. Main shell and startup posture
2. Global Settings
3. Master Index
4. Character Roster
5. High-use add/edit dialogs: cyberware, gear, weapons, armor, magic, matrix, vehicles, contacts, qualities, skills
6. Utility dialogs and operator surfaces
7. SR4 and SR6 authored labels/copy/posture
8. Release proof / published artifact follow-through

Rules:
- Fix root causes, not cosmetic one-off hacks.
- Keep the UI dense, classic, and Chummer5a-like by default.
- Remove workspace noise and any browser/dashboard-style detours.
- Preserve menu/toolstrip/status-strip/tab rhythm.
- After every meaningful batch, run the focused UI tests and the four parity gates.
- Commit and push every green slice.
- If something is still not identical, list it explicitly and explain why.

Validation required after each batch:
- DesktopDialogFactoryTests
- AvaloniaFlagshipUiGateTests
- DesktopShellRulesetCatalogTests
- BlazorShellComponentTests
- scripts/ai/milestones/chummer5a-layout-hard-gate.sh
- scripts/ai/milestones/classic-dense-workbench-posture-gate.sh
- scripts/ai/milestones/chummer5a-screenshot-review-gate.sh
- scripts/ai/milestones/chummer5a-desktop-workflow-parity-check.sh

Fleet usage:
- Keep Fleet healthy and verify shards are progressing.
- Keep shard-13 on EA, not code.girschele.com.
- Use Fleet for parallel parity auditing, readiness, and proof follow-through.
- Update Fleet handoff/guide so the active parity slice is always explicit.

Stop only when one of these is true:
1. The parity target is actually finished and validated, with commits pushed.
2. A hard external blocker remains that cannot be solved on this host; if so, leave the system fully prepared, automated, and documented for the external step, and tell me exactly what remains.

When you report back:
- tell me what changed
- tell me what still differs from Chummer5a, item by item, and why
- tell me the current ETA to full finish
- then continue unless you are truly blocked
```

Shorter version if you want it tighter:

```text
Do not stop until Chummer6 UI parity is genuinely finished. Keep looping autonomously: audit, patch, validate, commit/push, and repeat. Use direct owner-repo work for the highest-value parity gaps and use Fleet in parallel for audits, readiness, and proof follow-through. After every batch run the focused UI tests plus the four Chummer5a parity gates. Keep shard-13 on EA. Only stop when parity is actually done and pushed, or when a true external blocker remains and the system is fully prepared for it.
```

Best practical note:
- If you want maximum speed, add: `Commit and push every green slice without asking again.`
- If you want maximum rigor, add: `List every remaining non-identical surface and reason after each batch.`
