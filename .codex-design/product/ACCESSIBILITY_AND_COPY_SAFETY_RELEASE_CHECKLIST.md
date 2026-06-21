# Accessibility and Copy Safety Release Checklist

## Purpose

This checklist is the minimum release-grade review for flagship surfaces.
It keeps labels, focus order, contrast, motor access, and emergency language from becoming last-minute taste calls.

## Applies to

* desktop workbench
* mobile/play shell
* Hub public and signed-in surfaces
* support, status, feedback, and install routes
* publication and artifact preview surfaces

## Checklist

### Labels and naming

* Interactive controls have visible labels or an explicit accessible-name source.
* Primary actions use verbs that describe the real outcome.
* Status words match the canonical language contract in `KNOWN_ISSUE_AND_FIX_STATUS_LANGUAGE.md`.

### Focus and keyboard

* First focus target is intentional.
* Focus order follows the visible reading order.
* Primary, cancel, retry, and recovery actions are keyboard reachable.
* No mandatory route depends on hover-only discovery.

### Contrast and visibility

* Warning, blocked, preview, stale, and fixed states remain legible in light and dark themes.
* Error and recovery states do not depend on color alone.
* Dense-data surfaces remain scannable without hidden scroll traps.

### Motor accessibility

* Important actions and toggles are reachable with forgiving target sizes.
* Destructive or high-risk actions require clear confirmation or reversal posture.
* Long-running operations expose a non-motor fallback when drag, hover, or press-and-hold behavior would otherwise block completion.

### Copy safety

* Emergency or recovery guidance says what happened, what is safe, and what to do next.
* Copy avoids unbounded promises such as `fixed` or `safe` without evidence.
* Locale-sensitive phrasing avoids slang, hidden negation, or ambiguous pronouns on critical routes.
* Support, release, and in-product copy do not contradict each other about availability or next action.
* Normal user-facing copy uses Chummer-owned surface names instead of provider, LTD, prompt, generation, or automation terms.
* AI/synthetic/provider disclosure appears only when needed for consent, privacy, safety, copyright, or trust.
* Explanatory text is removed or shortened when the workflow can be made self-evident through layout, labels, and state.

## Release rule

Any promoted route that fails this checklist is not flagship-ready, even when the underlying feature technically works.
