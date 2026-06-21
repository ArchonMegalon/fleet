# Chummer6 Public Guide User-First Audit

Date: 2026-06-18

## Verdict

The public repo was still too close to an internal evidence bundle. A casual visitor could see generated receipts, verifier vocabulary, and horizon taxonomy before understanding the product.

The target first impression is:

```text
I can tell what Chummer6 is.
I can tell whether I can use it today.
I can find the right download or first-run path.
I can see the exciting campaign layer without confusing it with shipped desktop scope.
I can go deeper only when I choose to.
```

## P0 Findings

### 1. Root file list looked like a harness

Root-level files such as `CHUMMER6_PUBLIC_RELEASE_TRUTH_PACKET.generated.json`, `CHUMMER6_GUIDE_GENERATOR_REGISTRY_ALIGNMENT.generated.json`, and `FINAL_CHUMMER6_DOCS_GENERATION_VERDICT.md` made the repo look generated before it looked useful.

Fix:

- sync machine receipts to `.guide-internal/receipts`
- remove stale generated receipts from repo root
- add a first-impression verifier so they do not leak back

### 2. Onramp was wrongly classified as a horizon

Onramp is not a speculative future lane. It is the first-run and recovery path for new, rusty, or blocked users.

Fix:

- remove Onramp from the horizon registry
- delete the obsolete horizon source file
- add `ONRAMP_STARTER_LANE.md`
- generate top-level `ONRAMP.md`
- route new/rusty users to a first-session guide from `START_HERE.md` and `README.md`

### 3. README answered audit questions before user questions

The old front door led with "Chummer Public Guide," "clear public proof," and broad status boundaries. That is accurate but cold.

Fix:

- title the repo `Chummer6`
- lead with build/use value
- name the primary user routes first
- explain availability in user language
- keep scope honesty without proof-dump phrasing

### 4. Horizons index insulted the reader

The Horizons index said all listed pages were future ideas, while several entries represent live or early product slices. That reads careless and patronizing.

Fix:

- retitle the index as `Campaign tools`
- split normal product areas, expansion bets, and folded-in infrastructure
- keep exact availability on `STATUS.md`

## P1 Findings

### 5. Start Here did not include the obvious beginner path

The first user question is often "I am new or rusty, what do I do?" It should not be buried under future planning.

Fix:

- generate `START_HERE.md` from design
- lead with "I want to try Chummer"
- route new or rusty users to the first-session guide without making starter help sound like a product lane

### 6. "Wow" was present but not sequenced

The repo had powerful surfaces: ALICE, Origin Dossier, Living World, Runner Passport, Black Ledger, Table Pulse. The problem was order. Visitors need "what can I do tonight?" before the larger world.

Fix:

- README path order: Download, first-session guide, Status, Start Here, What Chummer6 Is, migration, live campaign surfaces, help, campaign tools
- "Campaign tools" becomes the deeper path for product areas and expansion bets, not the first frame

### 7. Internal checks were necessary but visually too loud

The verification scripts and receipts are useful. They should support claims, not dominate the public surface.

Fix:

- keep scripts under `scripts/`
- keep receipts under `.guide-internal/receipts`
- add `verify_public_guide_first_impression.py`

## User Questions The Guide Must Answer

- What is Chummer6?
- Can I try it today?
- Which file do I download?
- I am new or rusty. Where do I start?
- I used Chummer5a. What changed?
- Is the math explainable?
- What is the cool campaign layer?
- What is live versus future-facing?
- Where do I get help?
- Where can I contribute or report a problem?

## Regression Rules

- No root `*.generated.json` files.
- No root internal verdict files.
- No `HORIZONS/onramp.md`.
- README starts with `# Chummer6`.
- README links `START_HERE.md`, `ONRAMP.md`, `DOWNLOAD.md`, `STATUS.md`, and `HORIZONS/README.md`.
- `START_HERE.md` leads with the try-it-now path and keeps the first-session guide one click away.
- `ONRAMP.md` is a practical first-run/recovery page and does not appear under `HORIZONS/`.
- Onramp art is emitted under `assets/pages/`, not `assets/horizons/`.
- Campaign tools index splits product areas, expansion bets, and folded-in infrastructure instead of flattening them into one horizon list.

## 2026-06-18 Humanized Regeneration Follow-Up

The regenerated Chummer6 guide now treats Origin Dossier as a real horizon in both the root and derived horizon registries, while Onramp stays a top-level first-run and recovery page.

Additional fixes:

- moved visible Onramp art from the horizon asset path to the page asset path
- removed API route lists and checklist-style copy from the public Onramp page
- translated horizon stage labels into reader-facing availability language
- kept Origin Dossier prominent in the public guide and connected to ALICE, scoped audiobook handoff, and approved canon
- kept the blocked Origin Dossier MagicFit full reel out of public links because the public URL is not live
- verified the linked Table Pulse and ALICE horizon videos still expose AAC audio streams
- replaced presentation-doc checklist headings such as "Guardrails" and "What belongs here" with user-facing section names
