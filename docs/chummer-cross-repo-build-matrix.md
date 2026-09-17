# Chummer cross-repository build matrix

Fleet owns the execution contract and future multi-repository orchestration for
this matrix. `chummer6-design` continues to own product and release-governance
meaning, while `chummer6-hub-registry` remains the only owner of promoted
artifact, release-channel, install, and update-feed truth.

The checked-in matrix is a synthetic test fixture. It is not a source graph,
build receipt, release candidate, artifact receipt, promotion decision, or
publication claim. The workflow's build job is statically disabled and neither
clones sibling repositories nor downloads artifacts.

Before a future `candidate-bound` matrix can become evidence, a separate
reviewed activation change must provide independently verified immutable refs,
assets/member digests, exact workflow run and attempt IDs, artifact IDs and
artifact-byte digests. Activation must not change the closed repository set,
toolchain posture, API-36 device profile, or required journeys.

Validate the synthetic contract locally with:

```sh
python3 scripts/verify_chummer_cross_repo_build_matrix.py \
  --matrix tests/fixtures/chummer_cross_repo_build_matrix.synthetic.json
```
