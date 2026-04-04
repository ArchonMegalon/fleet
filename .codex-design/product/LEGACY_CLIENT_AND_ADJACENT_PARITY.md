# Legacy Client And Adjacent Parity

## Purpose

Chummer6 must not become a step back from the serious Shadowrun clients people already used to do real work.

This audit names the legacy and adjacent client feature families that still matter, maps them to current Chummer6 design canon, and records the missing or partial families that now have explicit milestone ownership.

## Scope

Included sources:

* `Chummer5a` local source inventory in `/docker/chummer5a/Chummer/Forms`
* `Chummer4` as an SR4 oracle where the current canon already says it should be used that way
* Genesis / CommLink6 public feature docs
* Hero Lab Classic public feature docs for Shadowrun 4th/5th Edition posture

Excluded on purpose:

* plugin framework parity

## Evidence base

### Local legacy inventory

The local `Chummer5a` repo still exposes first-class forms or utilities for:

* dense creation/career shells
* global and character settings
* sourcebook selection and sourcebook metadata editing
* dice roller and initiative utilities
* character roster, updater, export, print, data export, and sheet viewer
* Hero Lab import
* XML editing and translator-era language tooling
* GM and player dashboard surfaces

### SR4 oracle posture

No local `Chummer4` repo mirror is currently present in this workspace.

That means SR4 parity stays governed by the existing design rule: use Chummer4 as a workflow-local oracle where it is the stronger legacy reference for SR4, but do not invent fake source archaeology when the repo is not locally mirrored.

### Adjacent SR6 references

Genesis / CommLink6 public docs show a serious SR6 user expectation set:

* creation plus career mode
* gear compatibility filtering
* configurable "buy" versus "add/manage" posture
* history browsing
* PDF export and optional sheet variants
* online storage
* custom data and custom descriptions
* metaindex / rules reference posture
* JSON / Foundry export
* supplement-book coverage and authored designer tools such as spell, vehicle, cyberdeck, drug, and quality designers

Hero Lab Classic remains a useful adjacent oracle for:

* tab-panel character creation
* automated validation
* print / PDF / mail-style artifact export
* long-lived Shadowrun 4th/5th Edition support posture

## Audit summary

Modernization is allowed.

Chummer6 does not need to clone old forms pixel-for-pixel, and it does not need MDI-style multi-document chrome just because older clients used it.

But every feature family that remains in product scope must satisfy one of these states:

* `covered`: current Chummer6 canon already names a first-class modern equivalent
* `partial`: a modern equivalent exists in fragments, but the family is not yet explicit, complete, or release-gated
* `missing`: current canon does not yet name the family strongly enough for a no-step-back claim

## Family matrix

| Family | Legacy / adjacent expectation | Current Chummer6 design equivalent | Status | Active milestone closure |
| --- | --- | --- | --- | --- |
| Shell and dense workbench orientation | top menu, toolstrip, tabs, status strip, dense central builder | `CHUMMER5A_FAMILIARITY_BRIDGE.md`, `FLAGSHIP_UI_RELEASE_GATE.md`, `FLAGSHIP_RELEASE_ACCEPTANCE.yaml` | partial | `2`, `3` |
| Dense creation and career workflows | creation, advancement, gear, matrix, magic, augment, vehicle, contact flows | `CHUMMER5A_FAMILIARITY_BRIDGE.md`, `DESKTOP_CLIENT_PRODUCT_CUT.md`, `BUILD_LAB_PRODUCT_MODEL.md` | partial | `2`, `7` |
| Identity, contacts, lifestyles, licenses, SINs, history | classic side workflows and career memory | `CHUMMER5A_FAMILIARITY_BRIDGE.md`, `CAMPAIGN_WORKSPACE_AND_DEVICE_ROLES.md`, `CHARACTER_LIFECYCLE_AND_LIVING_DOSSIER.md` | partial | `2`, `4` |
| Sourcebooks, source toggles, rule snippets, master index, PDF/URL reference posture | `Edit Sourcebook Info`, `Sourcebooks to Use`, `MasterIndex`, PDF opening, reference snippets | master-index sourcebook metadata, snippet coverage posture, aggregate reference-source lane posture, explicit reference plus reference-source lane receipts, and explicit source-selection lane receipts are now explicit (governed/stale/missing with governed/stale/missing source counts), including approved local PDF/URL/site-snapshot source targets; the desktop `master_index` dialog now surfaces sourcebook counts, snippet coverage, reference-source posture, import-oracle posture, and SR6 successor posture from the shared catalog; first-class source selection UX is still open | partial | `13` |
| Settings and authored rules-environment posture | global settings, character settings, source toggles, rule-environment visibility | master-index settings lane now projects profile counts, toggle coverage, stale-vs-governed source-toggle posture, and explicit settings/toggle lane receipts from `settings.xml`; the desktop `character_settings` dialog now surfaces settings/source-toggle/custom-data/XML bridge posture so the modern shell does not hide rules-environment truth; first-class settings UX consolidation is still open | partial | `14` |
| Custom data, XML editing, translator tooling, amend authoring bridge | `EditXmlData`, translator-era XML corpus, custom descriptions/data | master-index now projects custom-data directory counts plus missing/stale/governed custom-data lane posture and explicit custom-data/custom-data-authoring/XML-bridge/translator lane receipts from `settings.xml` + enabled overlays, and also projects translator corpus plus bridge posture (`missing`/`stale`/`governed`) with language and overlay counts; the desktop `translator` dialog now surfaces translator-lane posture, bridge posture, overlay counts, and live translator language inventory from the shared catalog; end-user custom-data authoring UX and translator replacement workflow remain open | partial | `14` |
| Dice roller, initiative roller, initiative tracker, combat utilities | standalone utility windows for fast table work | no explicit flagship utility lane today | missing | `15` |
| Character roster, watch folders, GM/player dashboards, multi-character operator tools | `CharacterRoster`, dashboard forms, roster watch folder | campaign and GM canon exists, but desktop utility/operator parity is not explicit enough | partial | `5`, `15` |
| Sheet viewer, print/export, PDF variants, JSON/Foundry exchange | `CharacterSheetViewer`, `PrintMultipleCharacters`, `ExportCharacter`, Genesis JSON/Foundry export | `INTEROP_AND_PORTABILITY_MODEL.md`, `BUILD_LAB_PRODUCT_MODEL.md`; Build Lab projection now exposes explicit governed `workflow.exchange.json`, `workflow.exchange.foundry`, `workflow.viewer.sheet`, and `workflow.export.pdf` lanes, while full end-to-end export/print migration closure remains open | partial | `16` |
| Legacy and adjacent import/oracle parity | Chummer4, Chummer5a, Hero Lab, Genesis/CommLink evidence | master-index now projects import-oracle fixture-family coverage, certification receipt posture, explicit adjacent SR6 oracle coverage posture (Genesis/CommLink), and explicit import plus adjacent-SR6 lane receipts for milestone-17 evidence, and the import parity receipt now fail-closes on explicit `import_oracles` plus `adjacent_oracles` naming for Chummer4/5a/Hero Lab and Genesis/CommLink coverage; full first-class import UX closure remains open | partial | `17` |
| SR6 supplement coverage, designer tools, online storage, house-rule support, metaindex | Genesis/CommLink6 supplement matrix, spell/vehicle/cyberdeck/drug/quality designers, online storage, better house rules | SR6 successor posture now has explicit tool-catalog projection for supplement/designer/house-rule lanes, online-storage continuity receipt posture/coverage, and unified SR6 successor lane receipts from Hub/mobile release-proof artifacts; full authored-designer and storage UX closure remains open | partial | `18` |

## New canon decisions

1. Old-client parity is now judged by feature families, not by whether the new app copied a form name.
2. Third-party serious clients and tools are valid audit oracles when they reveal user expectations Chummer6 still needs to meet.
3. Modern consolidation is good when it preserves or improves the same user job, trust posture, and speed.
4. A missing or partial family must live in machine-readable milestone truth, not only in prose complaints or migration notes.
5. The plugin framework remains intentionally out of scope for this parity program.

## Added milestone lane

The active Fleet wave now carries six explicit no-step-back closure milestones:

* `13` Sourcebook, master-index, rule-snippet, and governed reference parity
* `14` Settings, source toggles, custom-data, XML, and translator successor lane
* `15` Utility and operator parity for dice, initiative, roster, and dashboard work
* `16` Sheet, print, export, viewer, and adjacent exchange parity
* `17` Chummer4/5a/Hero Lab/Genesis/CommLink import-oracle closeout
* `18` SR6 supplement, designer-tool, house-rule, and online-storage successor lane

These milestones do not require clone behavior.

They require a first-class modern equivalent or an explicit bounded replacement story with receipts.
