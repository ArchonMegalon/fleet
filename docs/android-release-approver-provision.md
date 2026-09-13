# One-time protected Android approver provisioning

This workflow provisions a separate Ed25519 environment identity. It does not
change the existing RSA identity, issuer policy, Android trust, or release
activation, and cannot issue release approvals or upload AABs. Merge the reviewed
workflow to current protected Fleet main before dispatching it.

Pull requests and main pushes affecting these five files run a separate `verify`
job with deterministic public test keys and the same hashed dependencies. That
job has no protected environment or secret injection. Require its successful
hosted result for the exact reviewed source before merging; the key jobs execute
only on `workflow_dispatch`. This adds no branch-protection exceptions.

The two dispatch modes use separate jobs in the fixed environment
`android-preview12-release-approval` (ID `21501373212`), repository
`ArchonMegalon/fleet` (ID `1176287728`). Generate never receives an existing
private secret. It creates an Ed25519 key in Python memory, serializes canonical
PKCS8 DER as Base64 in memory, and seals that ASCII value with Libsodium to the
reviewed GitHub environment public key pinned in the helper. Both public bytes
and key ID came from the operator's authenticated API read and are enforced by
source before generation or private-key access. A dispatcher cannot substitute
another recipient. The runner does not claim to refresh environment metadata.
The operator must recheck environment identity/protection and this exact
recipient before dispatch and import. A rotated key requires a new reviewed pin;
there is no runtime override or fallback.

Only a closed-schema JSON observation containing sealed ciphertext, public key,
and exact workflow/run/destination bindings is uploaded. Retention is one day.
Treat the artifact and its metadata as public. Sealed boxes protect the private
value for GitHub's recipient key; **they do not authenticate the sender**. The
controller must independently bind the successful hosted run, job, workflow
source, artifact ID, and archive digest before importing any ciphertext.

GitHub's environment-secret PUT is create-or-update, not atomic create-only.
Workflow concurrency serializes key dispatches separately from PR/main tests.
An administrator or another
writer could change the slot between a GET and PUT. Use one coordinated operator,
check the exact slot immediately before the one import, and never blindly retry
a write or generate another key after a lost acknowledgment. The independent
prove dispatch determines whether the expected key was actually injected.

The workflow has no admin token. It uses `GITHUB_TOKEN` with `contents: read`
only for labeled authenticated current-main GETs before and after installing
the exact hashed CPython 3.12 Linux wheels. It makes no environment or secret
public-key GETs. Protected run
[34783917379](https://github.com/ArchonMegalon/fleet/actions/runs/34783917379)
failed with HTTP 403 before generation under the former API-read design; that
failure remains evidence, not a successful provisioning observation. This
reviewed source-pin path replaces that unsupported read assumption. There is no
403 fallback, fabricated environment snapshot, or credential substitution.
The final key process performs no network calls or subprocesses.

Python and the GitHub-hosted runner are the volatile-memory trust boundary:
immutable byte copies are not guaranteed to be zeroized, and environment secret
injection is visible to the trusted runner process. Core dumps are disabled.
There are no plaintext key files, command-line key arguments, key logs, or
uploaded raw DER/Base64 key material. Administrators and reviewed main source
retain their normal authority; this does not claim HSM or hardware isolation.

## Generate, inspect, and import once

Use the existing operator GitHub CLI authentication with environment-secret
administration permission. Do not place that credential on the workflow runner.
Run these blocks in a dedicated Bash session, preserving its variables between
blocks. Every block enables strict error handling: a failed guard must terminate
the sequence before dispatch or import. They handle only public metadata and
GitHub-encrypted ciphertext. Set `task_packet` to a fresh private local directory.

```bash
set -euo pipefail
task_packet=$(mktemp -d)
task_api=repos/ArchonMegalon/fleet/environments/android-preview12-release-approval
task_pin_id=3380204578043523366
task_pin_key='KehADg5PaYNI/6mRiXvHp3Nwk2h+F55K0cMJWv/Dcz8='
gh api repos/ArchonMegalon/fleet > "$task_packet/repository.json"
jq -e '.id == 1176287728 and .full_name == "ArchonMegalon/fleet"' "$task_packet/repository.json"
gh api repos/ArchonMegalon/fleet/branches/main > "$task_packet/main.before-dispatch.json"
jq -e '.name == "main" and .protected == true' "$task_packet/main.before-dispatch.json"
task_sha=$(jq -r .commit.sha "$task_packet/main.before-dispatch.json")
task_nonce=$(openssl rand -hex 32)
gh api "$task_api" > "$task_packet/environment.before-dispatch.json"
jq -e '.id == 21501373212 and .name == "android-preview12-release-approval" and .url == "https://api.github.com/repos/ArchonMegalon/fleet/environments/android-preview12-release-approval" and .can_admins_bypass == false and .deployment_branch_policy == {protected_branches:true,custom_branch_policies:false} and any(.protection_rules[]; .type == "branch_policy")' "$task_packet/environment.before-dispatch.json"
gh api "$task_api/secrets/public-key" > "$task_packet/recipient.json"
jq -e --arg id "$task_pin_id" --arg key "$task_pin_key" '.key_id == $id and .key == $key' "$task_packet/recipient.json"
gh api "$task_api/secrets?per_page=100" > "$task_packet/slots.before.json"
jq -e '.total_count <= 100 and all(.secrets[]; .name != "ANDROID_PREVIEW12_RELEASE_APPROVAL_ED25519_PRIVATE_KEY_PKCS8_B64")' "$task_packet/slots.before.json"
jq -n --arg sha "$task_sha" --arg nonce "$task_nonce" --slurpfile key "$task_packet/recipient.json" \
  '{ref:"main",inputs:{mode:"generate",request_nonce:$nonce,expected_execution_sha:$sha,recipient_key_id:$key[0].key_id,recipient_public_key:$key[0].key,expected_public_key_spki:""}}' \
  > "$task_packet/generate-dispatch.json"
gh api --method POST repos/ArchonMegalon/fleet/actions/workflows/android-release-approver-provision.yml/dispatches --input "$task_packet/generate-dispatch.json"
```

Identify the exact run created by that dispatch and wait for its conclusion.
Do not use a rerun: `run_attempt` must equal one. Before downloading, use GitHub's
run and attempt-jobs endpoints to verify all of: the fixed repository IDs,
`workflow_dispatch`, `head_branch=main`, `head_sha=$task_sha`, the expected workflow
path/ID, attempt one, success, and the `generate` job's success. Main must still be
the reviewed commit when the workflow admits its source. If several dispatches
are plausible, resolve their nonce and metadata; do not choose merely “latest.”

```bash
set -euo pipefail
# Set task_run to the exact independently checked successful generation run ID.
gh api "repos/ArchonMegalon/fleet/actions/runs/$task_run" > "$task_packet/run.json"
gh api "repos/ArchonMegalon/fleet/actions/runs/$task_run/attempts/1/jobs" > "$task_packet/jobs.json"
gh api "repos/ArchonMegalon/fleet/actions/runs/$task_run/artifacts" > "$task_packet/artifacts.json"
task_artifact=$(jq -r --arg name "android-release-approver-generate-$task_run-1" \
  '.artifacts | map(select(.name == $name and .expired == false)) | if length == 1 then .[0].id else error("ambiguous artifact") end' "$task_packet/artifacts.json")
gh api "repos/ArchonMegalon/fleet/actions/artifacts/$task_artifact" > "$task_packet/artifact.json"
jq -e --argjson run "$task_run" --arg sha "$task_sha" \
  '.workflow_run.id == $run and .workflow_run.repository_id == 1176287728 and .workflow_run.head_repository_id == 1176287728 and .workflow_run.head_branch == "main" and .workflow_run.head_sha == $sha and .expired == false and .size_in_bytes > 0 and .size_in_bytes <= 65536 and (.digest | test("^sha256:[0-9a-f]{64}$"))' \
  "$task_packet/artifact.json"
gh api "repos/ArchonMegalon/fleet/actions/artifacts/$task_artifact/zip" > "$task_packet/artifact.zip"
test "$(wc -c < "$task_packet/artifact.zip")" -le 65536
test "$(sha256sum "$task_packet/artifact.zip" | cut -d ' ' -f 1)" = "$(jq -r '.digest | sub("^sha256:"; "")' "$task_packet/artifact.json")"
"$task_python" -I -B -c 'import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    members = archive.infolist()
    assert len(members) == 1
    entry = members[0]
    assert entry.filename == "android-release-approver-observation.json"
    assert not entry.is_dir() and not entry.flag_bits & 1
    assert 0 < entry.file_size <= 8192 and entry.compress_size <= 65536
    with archive.open(entry) as stream:
        raw = stream.read(8193)
    assert len(raw) == entry.file_size
    sys.stdout.buffer.write(raw)' "$task_packet/artifact.zip" > "$task_packet/generate.json"
```

Set `task_python` to the Python executable in an isolated environment containing
the hash-locked dependencies before the extraction step. The guards above check
artifact run/repository/branch/head and compressed/uncompressed bounds before
reading its JSON. Run the checked-in verifier below. Local verification validates
the envelope and bindings, not the independent GitHub provenance checks above.

```bash
set -euo pipefail
"$task_python" -I -B scripts/android_preview12_release_approver_provision.py verify \
  --observation "$task_packet/generate.json" --mode generate --nonce "$task_nonce" \
  --execution-sha "$task_sha" --run-id "$task_run" --run-attempt 1 \
  --recipient-key-id "$(jq -r .key_id "$task_packet/recipient.json")" \
  --recipient-public-key "$(jq -r .key "$task_packet/recipient.json")"
# Re-read immediately before import: exact protected environment, recipient, empty slot.
gh api "$task_api" > "$task_packet/environment.before-import.json"
jq -e '.id == 21501373212 and .name == "android-preview12-release-approval" and .url == "https://api.github.com/repos/ArchonMegalon/fleet/environments/android-preview12-release-approval" and .can_admins_bypass == false and .deployment_branch_policy == {protected_branches:true,custom_branch_policies:false} and any(.protection_rules[]; .type == "branch_policy")' "$task_packet/environment.before-import.json"
gh api "$task_api/secrets/public-key" > "$task_packet/recipient.before-import.json"
jq -e --arg id "$task_pin_id" --arg key "$task_pin_key" --slurpfile old "$task_packet/recipient.json" '.key_id == $id and .key == $key and .key_id == $old[0].key_id and .key == $old[0].key' "$task_packet/recipient.before-import.json"
gh api "$task_api/secrets?per_page=100" > "$task_packet/slots.before-import.json"
jq -e '.total_count <= 100 and all(.secrets[]; .name != "ANDROID_PREVIEW12_RELEASE_APPROVAL_ED25519_PRIVATE_KEY_PKCS8_B64")' "$task_packet/slots.before-import.json"
jq '{key_id:.recipientKeyId, encrypted_value:.encryptedValue}' "$task_packet/generate.json" > "$task_packet/import.json"
# Exactly one write. Retain the HTTP status; do not repeat it on any uncertainty.
if gh api --include --method PUT "$task_api/secrets/ANDROID_PREVIEW12_RELEASE_APPROVAL_ED25519_PRIVATE_KEY_PKCS8_B64" --input "$task_packet/import.json" > "$task_packet/import-response.txt" 2> "$task_packet/import-error.txt"; then
  if ! head -n 1 "$task_packet/import-response.txt" | tr -d '\r' | grep -Eq '^HTTP/[0-9.]+ 201( |$)'; then
    printf '%s\n' 'Import did not confirm creation (201); stop writes and reconcile with custody proof.' >&2
    exit 1
  fi
else
  printf '%s\n' 'Import acknowledgment is uncertain; stop writes and reconcile with custody proof.' >&2
  exit 1
fi
```

If the slot already exists, do not overwrite it. Only HTTP 201 confirms creation;
204 means an existing secret was updated and is not an accepted create result.
If the PUT returns 204 or its result is ambiguous, stop writing and perform the
matching custody proof; do not regenerate or retry PUT. Retain the response/error
metadata to reconcile the administrative race or lost acknowledgment.

## Prove independent injection

Use the same generation nonce and exact observed SPKI. Re-read protected main,
environment identity/protection, recipient, and the existing secret's metadata,
preserving the reviewed generation receipt. No plaintext secret is retrieved.
The proof binds its own run/attempt/source and the fixed destination, so it may
run on a later separately reviewed main that contains this same workflow.

```bash
set -euo pipefail
gh api repos/ArchonMegalon/fleet/branches/main > "$task_packet/main.before-proof.json"
jq -e '.name == "main" and .protected == true' "$task_packet/main.before-proof.json"
task_proof_sha=$(jq -r .commit.sha "$task_packet/main.before-proof.json")
gh api "$task_api" > "$task_packet/environment.before-proof.json"
jq -e '.id == 21501373212 and .name == "android-preview12-release-approval" and .url == "https://api.github.com/repos/ArchonMegalon/fleet/environments/android-preview12-release-approval" and .can_admins_bypass == false and .deployment_branch_policy == {protected_branches:true,custom_branch_policies:false} and any(.protection_rules[]; .type == "branch_policy")' "$task_packet/environment.before-proof.json"
gh api "$task_api/secrets/public-key" > "$task_packet/proof-recipient.json"
jq -e --arg id "$task_pin_id" --arg key "$task_pin_key" '.key_id == $id and .key == $key' "$task_packet/proof-recipient.json"
gh api "$task_api/secrets?per_page=100" > "$task_packet/slots.before-proof.json"
jq -e '.total_count <= 100 and ([.secrets[] | select(.name == "ANDROID_PREVIEW12_RELEASE_APPROVAL_ED25519_PRIVATE_KEY_PKCS8_B64")] | length) == 1' "$task_packet/slots.before-proof.json"
jq -n --arg sha "$task_proof_sha" --arg nonce "$task_nonce" \
  --slurpfile key "$task_packet/proof-recipient.json" --slurpfile generated "$task_packet/generate.json" \
  '{ref:"main",inputs:{mode:"prove",request_nonce:$nonce,expected_execution_sha:$sha,recipient_key_id:$key[0].key_id,recipient_public_key:$key[0].key,expected_public_key_spki:$generated[0].publicKeySpkiDerBase64}}' \
  > "$task_packet/prove-dispatch.json"
gh api --method POST repos/ArchonMegalon/fleet/actions/workflows/android-release-approver-provision.yml/dispatches --input "$task_packet/prove-dispatch.json"
```

Repeat the run/job/artifact checks for the exact `prove` run and its
`android-release-approver-prove-RUNID-1` artifact, then verify its JSON:

```bash
set -euo pipefail
"$task_python" -I -B scripts/android_preview12_release_approver_provision.py verify \
  --observation "$task_packet/prove.json" --mode prove --nonce "$task_nonce" \
  --execution-sha "$task_proof_sha" --run-id "$task_proof_run" --run-attempt 1 \
  --recipient-key-id "$(jq -r .key_id "$task_packet/proof-recipient.json")" \
  --recipient-public-key "$(jq -r .key "$task_packet/proof-recipient.json")" \
  --public-key-spki "$(jq -r .publicKeySpkiDerBase64 "$task_packet/generate.json")"
```

The signed bytes begin with `fleet/android-release-approver/custody-proof/v1`
followed by a NUL and canonical JSON of the fixed public fields. This is not
Android's release-approval message format. No arbitrary message, approval
payload, Play credential, or AAB is accepted. A valid proof establishes that this
protected job received the expected key; it does not activate trust or authorize
a release. Subsequent reviewed issuer/Android trust configuration is separate.

References: [GitHub environment secrets API](https://docs.github.com/en/rest/actions/secrets),
[GitHub job workflow context](https://docs.github.com/en/enterprise-cloud%40latest/actions/reference/workflows-and-actions/contexts),
[Libsodium sealed boxes through PyNaCl](https://pynacl.readthedocs.io/en/latest/public/),
and [cryptography serialization](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/serialization/).
Wheel hashes come from the corresponding official PyPI release JSON for
cryptography 50.0.1, PyNaCl 1.6.2, cffi 2.1.1, and pycparser 3.0.
