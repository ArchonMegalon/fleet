# Fleet Local Design Mirror

This directory is the Fleet-local mirror of approved Chummer canon from `chummer6-design`.
It is a manifest-backed input bundle for workers, review, and materializers, not a local design fork and not a sink for generated Fleet proof.

## What lives here

- `product/`: approved product canon mirrored from `products/chummer/*`
- `repo/IMPLEMENTATION_SCOPE.md`: Fleet boundary and ownership rules
- `review/REVIEW_CONTEXT.md`: Fleet review bar for code and proof changes

## Source of truth

- Canonical source repo: `chummer6-design`
- Canonical manifest: `/docker/chummercomplete/chummer-design/products/chummer/sync/sync-manifest.yaml`
- Fleet repo entry: `repo: fleet`

If this mirror and central canon disagree, central canon wins and the local bundle is considered drifted.

## Drift detection

Fleet should detect mirror drift mechanically before treating it as queue truth:

1. Compare this bundle against the `repo: fleet` entry in the canonical sync manifest.
2. Treat missing files and content mismatches as drift.
3. Cluster repeated observations into one bounded mirror-hygiene slice instead of reopening one-off refresh work for every file.

The design-owned parity check for this repo is:

```bash
python3 /docker/chummercomplete/chummer-design/scripts/ai/publish_local_mirrors.py --check --repo fleet
```

The current Fleet-local mirror check is expected to pass before queue synthesis or
flagship proof refresh proceeds. If this command passes for `fleet`, treat older
mirror-drift findings for this repo as historical until a fresh check says
otherwise.

## Volatile mirrored inputs

Some mirrored files are design-owned generated inputs that legitimately change as
central canon is republished, especially:

- `.codex-design/product/PROGRESS_REPORT.generated.json`
- `.codex-design/product/PROGRESS_REPORT.generated.html`

These files are still part of the approved mirror bundle, but Fleet must only
refresh them through the canonical mirror publisher. Do not regenerate or
rewrite them from Fleet-local proof scripts, and do not treat Fleet-generated
publish output as a substitute for the mirrored design source.

## Fleet-local status contract

Fleet's compact mirror-health state lives outside this bundle at:

- `/var/lib/codex-fleet/state/design_mirror_status.json`

That status file is the Fleet-owned operational snapshot. `.codex-design/`
remains the mirrored canon bundle itself.

## Repair path

Repair this bundle only by republishing from canonical design:

```bash
python3 /docker/chummercomplete/chummer-design/scripts/ai/publish_local_mirrors.py --repo fleet
```

After repair, rerun the `--check` command and keep the resulting parity state in Fleet-owned machine-readable status or short operator summaries, not as generated artifacts inside `.codex-design/`.

## Hard boundaries

- Do not hand-edit mirrored canon here when the change belongs in `chummer6-design`.
- Do not write generated readiness receipts, release proof, or other Fleet materializer output into this tree.
- Do not treat `.codex-design/` as a local policy override path.
- Do keep Fleet-specific drift detection, clustering, and repair orchestration outside this mirror bundle.
