# Chummer next 12 biggest wins

## Framing

The previous additive and post-audit waves established a much stronger architectural center, support spine, and release-control plane.

The next job is not to widen the map for its own sake.
It is to concentrate the whole project on the 12 highest-leverage wins that move Chummer from "strong, ambitious, mostly proven" to "boring, flagship, daily-use, launch-scale truth."

The machine-readable control plane for this wave lives in `NEXT_12_BIGGEST_WINS_REGISTRY.yaml`.
The filename stays for continuity, but the active wave now also carries milestones `13` through `18` so no-step-back parity is treated as release-blocking flagship work rather than optional migration cleanup.

## Ordering rule

1. finish the desktop flagship lane first,
2. close no-step-back client parity before we call the flagship lane done,
3. make campaign continuity indispensable,
4. widen Build / Explain / exchange where they reinforce daily use,
5. turn trust, publication, and launch scale into boring operator truth.

## Wave 1 - ship the flagship desktop

### 1. Gold install, update, and recovery lane across macOS, Windows, and Linux
Owners: `chummer6-ui`, `chummer6-hub`, `chummer6-hub-registry`, `fleet`, `chummer6-design`
Exit: guided install, claim/link, update, rollback, recovery, and startup smoke behave as one coherent release lane on all promoted desktop platforms.

### 2. Legacy-familiar flagship workbench across SR4, SR6, and Chummer5a mental models
Owners: `chummer6-ui`, `chummer6-core`, `chummer6-design`
Exit: loaded-runner chrome, dense workbench posture, tabs, cyberware dialogs, gear flows, and the rest of the high-friction builder workflows feel familiar to legacy Chummer users while staying ruleset-correct.

### 3. Packaged-binary desktop exit tests and per-head proof that cannot lie
Owners: `fleet`, `chummer6-ui`, `chummer6-hub-registry`
Exit: Avalonia and Blazor promoted heads prove executable menu liveness, workflow execution, visual familiarity, and install/update behavior on shipped artifacts rather than only repo-local fixtures.

## Wave 2 - close no-step-back client parity

### 13. Sourcebook, master-index, rule-snippet, and governed reference parity
Owners: `chummer6-ui`, `chummer6-core`, `chummer6-design`
Exit: sourcebook selection, source metadata, and governed rules-reference lanes become first-class product promises instead of hidden old-client folklore.

### 14. Settings, source toggles, custom-data, XML, and translator successor lane
Owners: `chummer6-ui`, `chummer6-core`, `chummer6-design`
Exit: global settings, character settings, source toggles, custom-data and amend posture, XML bridge posture, and translator-era localization tooling all have one obvious modern successor route.

### 15. Utility and operator parity for dice, initiative, roster, and dashboard work
Owners: `chummer6-ui`, `chummer6-hub`, `chummer6-design`
Exit: dice roller, initiative utilities, roster/watch-folder posture, and operator/dashboard work all have a real promoted Chummer6 lane instead of missing-window excuses.

### 16. Sheet, print, export, viewer, and adjacent exchange parity
Owners: `chummer6-ui`, `chummer6-core`, `chummer6-hub`, `chummer6-design`
Exit: sheet viewing, print/export variants, PDF posture, and adjacent exchange outputs such as JSON/Foundry-class payloads are explicit product promises rather than support cargo.

### 17. Chummer4/5a/Hero Lab/Genesis/CommLink import-oracle closeout
Owners: `chummer6-core`, `chummer6-ui`, `chummer6-design`
Exit: legacy and adjacent imports either land in first-class Chummer6 surfaces with explicit receipts or emit honest bounded-loss receipts backed by oracle coverage.

### 18. SR6 supplement, designer-tool, house-rule, and online-storage successor lane
Owners: `chummer6-core`, `chummer6-ui`, `chummer6-hub`, `chummer6-design`
Exit: serious SR6 expectations exposed by Genesis / CommLink6 such as supplement breadth, authored designers, house-rule posture, and storage continuity feel like a better modern client rather than a reduced rebuild.

## Wave 3 - make campaign continuity indispensable

### 4. Campaign workspace v4: downtime, diary, contacts, heat, aftermath, and return loop
Owners: `chummer6-hub`, `chummer6-ui`, `chummer6-mobile`, `chummer6-core`
Exit: the same campaign truth covers planning, play, recap, downtime, contact changes, consequence tracking, and next-session return without note-shadowing or cross-surface loss.

### 5. GM operations: opposition packets, roster movement, prep library, and event/season controls
Owners: `chummer6-hub`, `chummer6-ui`, `chummer6-core`, `executive-assistant`
Exit: GM and organizer work is a first-class governed product lane rather than a pile of one-off prep tricks.

### 6. Safehouse, travel, offline, and mobile companion continuity
Owners: `chummer6-mobile`, `chummer6-hub`, `chummer6-ui`, `chummer6-hub-registry`
Exit: a claimed user can move between desktop, travel, and mobile play contexts with bounded offline readiness and explicit continuity proof.

## Wave 4 - widen build, explain, and exchange where it matters

### 7. Build Lab from creation to advancement to crew-fit
Owners: `chummer6-core`, `chummer6-ui`, `chummer6-hub`
Exit: character creation, advancement planning, comparison, and crew-fit analysis feel like one grounded build surface instead of disconnected utilities.

### 8. Explain receipts and rule-environment diffs everywhere that support real decisions
Owners: `chummer6-core`, `chummer6-ui`, `chummer6-hub`, `chummer6-design`
Exit: numbers, imports, workflow blockers, campaign constraints, and support diagnoses all show grounded receipts and before/after rule-environment reasoning.

### 9. Portable dossier/campaign exchange plus replay, recap, and module artifacts
Owners: `chummer6-core`, `chummer6-hub`, `chummer6-hub-registry`, `chummer6-media-factory`, `chummer6-ui`
Exit: exchange, replay, recap, and module publication become a real second pillar of product value rather than a backup/export sidecar.

## Wave 5 - turn trust, publication, and launch scale into boring truth

### 10. Public trust and support loop with install-specific diagnosis and fix confirmation
Owners: `chummer6-hub`, `chummer6-hub-registry`, `fleet`, `executive-assistant`, `chummer6-design`
Exit: support can prove what build, channel, fix, and recovery path a user actually has, and public trust surfaces say the same thing.

### 11. Creator publication, discovery, moderation, and shelf posture that survives growth
Owners: `chummer6-media-factory`, `chummer6-hub`, `chummer6-hub-registry`, `chummer6-ui`, `chummer6-design`
Exit: creator outputs, modules, primers, replays, and dossiers can be discovered, compared, moderated, and trusted without collapsing into ungoverned clutter.

### 12. Product pulse v3: adoption, canaries, launch/freeze decisions, and auto-implementation governance
Owners: `product_governor`, `fleet`, `executive-assistant`, `chummer6-design`, `chummer6-hub`
Exit: the governor loop can justify launch, freeze, rollback, or focus shifts from measured truth and can keep the automation frontier aligned with the active product program.
