# Contrast audit proof closure

Goal: remove the remaining “manual review wall” from the polish claim so whole-product closure does not depend on a pass artifact with thousands of review-required rows.

Why this is still open:
- `/docker/chummercomplete/_completion/chummer_run_redesign_closure/CONTRAST_AUDIT.generated.json` currently reports:
  - `status: pass`
  - `review_required_count: 6534`

Required closure:
- determine whether the contrast audit should be narrowed to the real flagship/public surfaces or materially improved so the review-required population collapses
- if the residual review set is intentionally non-blocking, split it into a scoped non-blocking artifact and keep the flagship polish verdict free of bulk manual-review debt
- regenerate the closeout bundle so “fully polished” does not rest on an artifact that still advertises mass manual review

Primary sources:
- `/docker/chummercomplete/_completion/chummer_run_redesign_closure/CONTRAST_AUDIT.generated.json`
- `/docker/chummercomplete/_completion/chummer_run_redesign_closure/FINAL_CHUMMER_RUN_UX_VERDICT.md`
- `/docker/chummercomplete/chummer.run-services/tests/public/contrast-audit.spec.ts`

Exit condition:
- contrast proof is either genuinely green at bounded scope or explicitly split into blocking vs non-blocking lanes
- flagship/public polish claims no longer depend on `review_required_count: 6534`
