# Dormant offline release source-test inputs

This source-only adapter does not activate a builder, change an Android pin,
admit a signing key, issue approval, or authorize upload. The checked-in lock
remains dormant. Android owns the test installer and exact dependency semantics.

The `prepare-rebuild` CLI takes three explicit test-only paths:

- `--test-bootstrap-dir`: exactly the two files in Android's bootstrap lock.
- `--test-wheelhouse`: exactly the eleven hash-pinned CI wheels.
- `--test-oracle-root`: an independently stored clean `chummer5a` checkout at
  the exact Android workflow pin, including its five inventory roots.

The closed `RELEASE_TEST_CONSUMERS` table distinguishes the checked-in historical
build script (no test-input capability) from the reviewed offline-runner script
(all three required). Unknown scripts fail closed. This is compatibility, not
qualification: the caller still needs an exact admitted source graph and lock.

Inputs must be canonical, build-user-owned, mutually disjoint, outside all
other build inputs/outputs and not writable by others. Oracle links, shared Git
storage, hooks, partial clones, ignored/untracked source and modified tracked
bytes are rejected before a build. Its complete object database must equal the
reachable closure of its admitted commit: an ordinary development clone with
unrelated objects is not an admissible input. Counts, total bytes, individual
files and Git subprocess output are bounded; expanded checkout still needs the
enclosing builder filesystem quota.

Fleet verifies the exact Android helper and its tracked import/input closure,
then calls only its capture functions. No installer or test suite runs in Fleet.
Captured public files go into private scratch; only verified Git objects go
into a new helper-free oracle under the disposable workspace. The actual Android
build receives the two snapshot-directory environment variables and retains its
original isolated test runner. Input mounts must remain read-only and private
scratch must permit executing the copied venv interpreter/native wheel code.
Container policy remains separately owner-admitted; this change does not edit it.

The oracle is not a ninth runtime repository. Cleanup runs before returning from
the child-build boundary, including exceptions. The existing preserved signer
workspace rejects unrelated contents and is unchanged. Source inputs are never
deleted; only newly owned staging directories are cleaned.

## Bounded full-oracle capacity

The oracle inventory admits at most **3 GiB of regular-file logical bytes**
across checkout and Git storage together. The independent **512 MiB per file**
and **250,000 entries** (including directories) limits are unchanged, as are
ownership, link/config rejection, exact commit/tree/reachable-object closure,
checkout verification and strict Git fsck. This does not widen product-bundle
limits or authorize partial history, omitted tracked files or unrelated objects.

Read-only metadata of the retained transport candidate for
`fe4355d06c98cd9b7feade89f5fc1a0e438f7ce3` on 2026-09-16 recorded:

| Component | Logical bytes |
| --- | ---: |
| Checkout | 1,240,994,870 |
| Packs, indexes and reverse indexes | 1,345,350,073 |
| Other Git files | 3,005,080 |
| Total | 2,589,350,023 |

The conservative allocation estimate was 2,673,321,045 bytes. The logical total
exceeds the former 2 GiB limit; 3 GiB is a finite allowance for this complete
representation, not a claim that it passed oracle verification. Capacity tests
use sparse placeholders for those component totals, not real Git payloads.

Filesystem quotas remain separately mandatory. A future transport retaining up
to 2 GiB of source storage while producing up to 3 GiB of final oracle needs a
new quota of at least **6 GiB**, and must admit the actual filesystem only when
available bytes are at least **5 GiB + 64 MiB**, with sufficient free inodes and
filesystem/metadata overhead accounted for. Recheck the required host free-space
floor before allocating that quota. The frozen failed 5 GiB transport packet is
unchanged; its old 2 GiB output limit and 4 GiB + 64 MiB admission are not a retry
plan for this ceiling.

The enclosing builder must separately budget an additional staged oracle of up
to 3 GiB while retaining its input, alongside the runtime repositories,
bootstrap/wheel inputs, restore/build outputs, logs, filesystem overhead and
reserve. The transport's 6 GiB minimum is **not** a whole-builder capacity claim.
Neither this policy nor the sparse tests establish a successful real-oracle
import, first producer, independent rebuild, signing or release.

## Verification

Portable boundary tests remain in `test_android_preview12_rebuild_input_boundaries.py`.
Logical-byte boundaries and the measured-size regression are in
`test_android_preview12_transport_capacity.py`.
The positive integration lane is deliberately separate and **fails** without an
explicit reviewed source root; it is not silently skipped by ordinary Fleet CI:

```sh
CHUMMER_ANDROID_RELEASE_TEST_RUNNER_ROOT=/absolute/reviewed/chummer-android \
  python3 -m pytest -q tests/integration_android_release_test_inputs.py
```

That lane uses the actual admitted Android capture helper and small local Git
fixtures with inert hash-pinned data. It executes no pip, SDK build, container,
signing or provider action. Until CI is deliberately wired to a qualified Android
pin and this explicit command, its result is local source-bound evidence only.
After Android qualification, a separate transaction must refresh the consumer
lock and admit the public input mounts; this source patch does neither.
