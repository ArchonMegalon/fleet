"""Process/policy tests use a NON-CRYPTOGRAPHIC gh stand-in, clearly not Sigstore.

Only the separately admitted optional upstream-fixture tests use genuine gh,
public Sigstore trust and signatures. Neither kind authenticates Fleet custody.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest

# Import one normal module identity and its existing Fleet helper; no Android
# consumer import and no replacement parser or dynamically reloaded helper.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import android_artifact_origin as origin
from scripts import android_preview12_external_rebuilder as fleet

NOW = datetime(2026, 9, 13, 10, 0, tzinfo=UTC)
SUBJECT = b"stand-in unit fixture only, not a real signed artifact\n"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def policy():
    return origin.OriginPolicy(
        repository="example/repo", repository_id="123", repository_uri="https://github.com/example/repo",
        owner_id="456", owner_uri="https://github.com/example", source_commit="a" * 40,
        signer_commit="b" * 40, source_ref="refs/heads/main",
        workflow_identity="https://github.com/example/repo/.github/workflows/build.yml@refs/heads/main",
        build_config_identity="https://github.com/example/repo/.github/workflows/build.yml@refs/heads/main",
        issuer="https://token.actions.githubusercontent.com", predicate_type="https://slsa.dev/provenance/v1",
        trigger="workflow_dispatch", run_id="1234", run_attempt="2", subject_name="fixture.bin",
        subject_sha256=sha(SUBJECT), visibility="public", runner_environment="github-hosted",
        timestamp_types=("TimestampAuthority",), maximum_age_seconds=3600, future_skew_seconds=30,
    )


def response():
    # Manufactured verified output exercises policy only. No signature claim.
    return [{"verificationResult": {
        "statement": {"_type": "https://in-toto.io/Statement/v1", "predicateType": "https://slsa.dev/provenance/v1",
                      "predicate": {}, "subject": [{"name": "fixture.bin", "digest": {"sha256": sha(SUBJECT)}}]},
        "signature": {"certificate": {
            "issuer": "https://token.actions.githubusercontent.com",
            "subjectAlternativeName": "https://github.com/example/repo/.github/workflows/build.yml@refs/heads/main",
            "buildSignerURI": "https://github.com/example/repo/.github/workflows/build.yml@refs/heads/main",
            "buildSignerDigest": "b" * 40, "runnerEnvironment": "github-hosted",
            "sourceRepositoryURI": "https://github.com/example/repo", "sourceRepositoryIdentifier": "123",
            "sourceRepositoryOwnerIdentifier": "456", "sourceRepositoryDigest": "a" * 40,
            "sourceRepositoryRef": "refs/heads/main", "sourceRepositoryOwnerURI": "https://github.com/example",
            "sourceRepositoryVisibilityAtSigning": "public",
            "buildConfigURI": "https://github.com/example/repo/.github/workflows/build.yml@refs/heads/main",
            "buildConfigDigest": "a" * 40, "buildTrigger": "workflow_dispatch",
            "runInvocationURI": "https://github.com/example/repo/actions/runs/1234/attempts/2",
        }},
        "verifiedTimestamps": [{"type": "TimestampAuthority", "timestamp": "2026-09-13T09:59:00Z"}],
    }}]


def write_pin(path, raw, executable=False):
    path.write_bytes(raw)
    path.chmod(0o700 if executable else 0o600)
    return origin.PinnedFile(path, sha(raw))


def standin(tmp_path, *, value=None, raw=None, mode="success", mutation="", exit_code=0):
    output = json.dumps(response() if value is None else value).encode() if raw is None else raw
    marker = tmp_path / "execution.json"
    # Absolute interpreter is a test fixture dependency, NOT the pinned gh.
    program = f'''#!{sys.executable}
import base64,json,os,signal,sys,time
from pathlib import Path
args=sys.argv[1:]
assert args[:2]==["attestation","verify"]
assert sys.stdin.buffer.read()==b""
assert not any(key in os.environ for key in ["GH_TOKEN","GITHUB_TOKEN","HTTPS_PROXY","LD_PRELOAD","PYTHONPATH"])
assert "HOME" not in os.environ
assert os.environ["GH_CONFIG_DIR"]==str(Path.cwd()/"gh-config")
assert set(os.environ)<=set(["PATH","LANG","LC_ALL","GH_HOST","GH_CONFIG_DIR","XDG_CONFIG_HOME","TMPDIR"])
Path({str(marker)!r}).write_text(json.dumps({{"pid":os.getpid(),"args":args,"cwd":str(Path.cwd())}}))
{mutation}
mode={mode!r}
if mode=="timeout": time.sleep(60)
if mode=="descendant":
 child=os.fork()
 if child==0:
  Path({str(tmp_path / 'child.pid')!r}).write_text(str(os.getpid()))
  time.sleep(60)
  os._exit(0)
 while not Path({str(tmp_path / 'child.pid')!r}).exists(): time.sleep(.005)
if mode in ["stdout-flood","stderr-flood"]:
 while True: os.write(1 if mode=="stdout-flood" else 2,b"PRIVATE UNTRUSTED OUTPUT"*4096)
if mode=="signature-failure":
 os.write(2,b"PRIVATE UNTRUSTED SIGNATURE DIAGNOSTIC")
 sys.exit(1)
os.write(1,base64.b64decode({base64.b64encode(output).decode()!r}))
sys.exit({exit_code})
'''
    pins = [write_pin(tmp_path / "subject.bin", SUBJECT), write_pin(tmp_path / "bundle.json", b'{"unitStandIn":true}'),
            write_pin(tmp_path / "verifier", program.encode(), True), write_pin(tmp_path / "root.json", b'{"unitStandIn":true}')]
    def verify(**kwargs):
        return origin.verify_origin(policy(), *pins, now=NOW, **kwargs)
    return SimpleNamespace(verify=verify, pins=pins, marker=marker)


def test_actual_subprocess_policy_only_happy_path_and_immutable_facts(tmp_path, monkeypatch):
    assert origin._fleet is fleet
    for key in ("GH_TOKEN", "GITHUB_TOKEN", "HTTPS_PROXY", "LD_PRELOAD", "PYTHONPATH"):
        monkeypatch.setenv(key, "MUST NOT INHERIT")
    fixture = standin(tmp_path)
    before = [pin.path.read_bytes() for pin in fixture.pins]
    facts = fixture.verify()
    assert facts.policy == policy()
    assert facts.bundle_sha256 == fixture.pins[1].sha256
    assert facts.verifier_sha256 == fixture.pins[2].sha256
    assert facts.trusted_root_sha256 == fixture.pins[3].sha256
    assert facts.verified_timestamps == (("TimestampAuthority", "2026-09-13T09:59:00Z"),)
    assert facts.checked_at == NOW
    with pytest.raises(FrozenInstanceError):
        facts.bundle_sha256 = "0" * 64
    with pytest.raises(FrozenInstanceError):
        facts.policy.repository = "attacker/repo"
    captured = json.loads(fixture.marker.read_text())
    args = captured["args"]
    assert args == ["attestation", "verify", str(Path(captured["cwd"]) / "subject"),
        "--bundle", str(Path(captured["cwd"]) / "bundle.json"),
        "--custom-trusted-root", str(Path(captured["cwd"]) / "trusted-root.json"),
        "--repo", "example/repo", "--cert-identity", policy().workflow_identity,
        "--cert-oidc-issuer", policy().issuer, "--signer-digest", "b" * 40,
        "--source-digest", "a" * 40, "--source-ref", "refs/heads/main",
        "--predicate-type", policy().predicate_type, "--deny-self-hosted-runners", "--format=json"]
    assert not Path(captured["cwd"]).exists()
    assert before == [pin.path.read_bytes() for pin in fixture.pins]
    assert not hasattr(facts, "eligibleForProtectedSigner")


@pytest.mark.parametrize("field", list(response()[0]["verificationResult"]["signature"]["certificate"]))
def test_each_authenticated_certificate_field_is_required_and_exact(tmp_path, field):
    value = response()
    value[0]["verificationResult"]["signature"]["certificate"][field] = "wrong"
    with pytest.raises(origin.OriginError, match="certificate identity differs"):
        standin(tmp_path, value=value).verify()


@pytest.mark.parametrize("change", ["name", "digest", "digest-extra", "extra-subject", "no-subject", "predicate", "type", "no-certificate"])
def test_subject_and_statement_shapes_fail_closed(tmp_path, change):
    value = response()
    result = value[0]["verificationResult"]
    statement = result["statement"]
    if change == "name": statement["subject"][0]["name"] = "foreign.bin"
    elif change == "digest": statement["subject"][0]["digest"]["sha256"] = "0" * 64
    elif change == "digest-extra": statement["subject"][0]["digest"]["sha512"] = "0" * 128
    elif change == "extra-subject": statement["subject"].append(deepcopy(statement["subject"][0]))
    elif change == "no-subject": del statement["subject"]
    elif change == "predicate": statement["predicateType"] = "https://example.invalid/predicate"
    elif change == "type": statement["_type"] = "https://in-toto.io/Statement/v0.1"
    else: del result["signature"]["certificate"]
    with pytest.raises(origin.OriginError):
        standin(tmp_path, value=value).verify()


@pytest.mark.parametrize("raw", [b'[]', b'{}', b'[{},{}]', b'[null]', b'[{"verificationResult":null}]',
    b'[{"x":1,"x":2}]', b'[NaN]', b'[Infinity]', b'[1e10000]', b'\xff', b'[] trailing',
    b'[],"injected":true', b'[' * 100 + b'0' + b']' * 100])
def test_strict_json_and_verified_shape_rejection(tmp_path, raw):
    with pytest.raises(origin.OriginError):
        standin(tmp_path, raw=raw).verify()


@pytest.mark.parametrize("rows", [[], None, [{"type": "Unverified", "timestamp": "2026-09-13T09:59:00Z"}],
    [{"type": "TimestampAuthority", "timestamp": "2024-09-13T09:59:00Z"}],
    [{"type": "TimestampAuthority", "timestamp": "2026-09-13T10:00:31Z"}],
    [{"type": "TimestampAuthority", "timestamp": "2026-09-13T09:59:00-00:00"}],
    [{"type": "TimestampAuthority", "timestamp": "2026-99-13T09:59:00Z"}], [None]])
def test_verified_timestamp_admission(tmp_path, rows):
    value = response()
    value[0]["verificationResult"]["verifiedTimestamps"] = rows
    with pytest.raises(origin.OriginError):
        standin(tmp_path, value=value).verify()


def test_aware_timestamp_offset_normalizes_and_signer_may_be_reusable(tmp_path):
    value = response()
    result = value[0]["verificationResult"]
    result["verifiedTimestamps"][0]["timestamp"] = "2026-09-13T11:59:00+02:00"
    identity = "https://github.com/trusted/workflows/.github/workflows/sign.yml@" + "b" * 40
    result["signature"]["certificate"]["subjectAlternativeName"] = identity
    result["signature"]["certificate"]["buildSignerURI"] = identity
    fixture = standin(tmp_path, value=value)
    facts = origin.verify_origin(replace(policy(), workflow_identity=identity), *fixture.pins, now=NOW)
    assert facts.verified_timestamps == (("TimestampAuthority", "2026-09-13T09:59:00Z"),)
    assert facts.policy.build_config_identity != facts.policy.workflow_identity


@pytest.mark.parametrize("field,value", [("repository", "example/*"), ("owner_id", "0456"),
    ("repository_id", 123), ("source_commit", "A" * 40), ("source_ref", "refs/heads/a/../main"),
    ("source_ref", "refs/heads/main.lock"), ("repository_uri", "https://attacker.invalid/example/repo"),
    ("build_config_identity", "https://github.com/foreign/repo/.github/workflows/build.yml@refs/heads/main"),
    ("issuer", "https://attacker.invalid"), ("runner_environment", "self-hosted"),
    ("subject_name", "unsafe\nname"), ("timestamp_types", ["TimestampAuthority"]),
    ("timestamp_types", ("TimestampAuthority", "TimestampAuthority")), ("maximum_age_seconds", True),
    ("future_skew_seconds", -1), ("run_attempt", "0")])
def test_policy_has_no_ambient_wildcard_or_mutable_authority(field, value):
    with pytest.raises(origin.OriginError):
        replace(policy(), **{field: value})


@pytest.mark.parametrize("which", range(4))
@pytest.mark.parametrize("change", ["missing", "digest", "symlink"])
def test_missing_or_unpinned_files_reject_before_execution(tmp_path, which, change):
    fixture = standin(tmp_path)
    pin = fixture.pins[which]
    if change == "missing": pin.path.unlink()
    elif change == "digest": pin.path.write_bytes(b"replaced")
    else:
        retained = pin.path.with_suffix(".retained")
        pin.path.rename(retained)
        pin.path.symlink_to(retained)
    with pytest.raises(origin.OriginError): fixture.verify()
    assert not fixture.marker.exists()


@pytest.mark.parametrize("which,limit", [(0, 64), (1, 8), (2, 256), (3, 16)])
def test_oversized_sparse_file_rejects_before_reading_or_launch(tmp_path, which, limit):
    fixture = standin(tmp_path)
    os.truncate(fixture.pins[which].path, limit * 1024 * 1024 + 1)
    with pytest.raises(origin.OriginError): fixture.verify()
    assert not fixture.marker.exists()


@pytest.mark.parametrize("which", range(4))
def test_original_file_byte_drift_is_rejected_after_process(tmp_path, which):
    names = ("subject.bin", "bundle.json", "verifier", "root.json")
    fixture = standin(tmp_path, mutation=f'Path({str(tmp_path / names[which])!r}).write_bytes(b"changed")')
    with pytest.raises(origin.OriginError): fixture.verify()
    assert fixture.marker.exists()


@pytest.mark.parametrize("change", ["replace", "chmod", "link"])
def test_same_bytes_identity_drift_is_not_accepted(tmp_path, change):
    path = tmp_path / "subject.bin"
    mutation = f'p=Path({str(path)!r})\n'
    if change == "replace": mutation += 'q=p.with_suffix(".replacement");q.write_bytes(p.read_bytes());q.chmod(0o600);q.replace(p)'
    elif change == "chmod": mutation += 'p.chmod(0o640)'
    else: mutation += 'os.link(p,p.with_suffix(".alias"))'
    fixture = standin(tmp_path, mutation=mutation)
    with pytest.raises(origin.OriginError, match="changed"): fixture.verify()
    assert path.read_bytes() == SUBJECT


@pytest.mark.parametrize("name", ["subject", "bundle.json", "trusted-root.json", "gh"])
def test_private_verification_copy_drift_is_rejected(tmp_path, name):
    fixture = standin(tmp_path, mutation=f'Path({name!r}).write_bytes(b"changed")')
    with pytest.raises(origin.OriginError): fixture.verify()


@pytest.mark.parametrize("mode,match", [("stdout-flood", "output exceeds bounds"),
    ("stderr-flood", "output exceeds bounds"), ("signature-failure", "cryptographic verification failed"),
    ("timeout", "timed out"), ("descendant", "timed out")])
def test_process_limits_sanitization_and_reaping(tmp_path, monkeypatch, mode, match):
    processes = []
    real_popen = origin.subprocess.Popen
    def start(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(origin.subprocess, "Popen", start)
    fixture = standin(tmp_path, mode=mode)
    with pytest.raises(origin.OriginError, match=match) as caught:
        fixture.verify(timeout_seconds=0.8, stdout_limit=32768, stderr_limit=4096)
    assert "PRIVATE" not in str(caught.value)
    assert len(processes) == 1 and processes[0].returncode is not None
    assert processes[0].stdout.closed and processes[0].stderr.closed
    with pytest.raises(ChildProcessError): os.waitpid(processes[0].pid, os.WNOHANG)
    if mode == "descendant":
        child = int((tmp_path / "child.pid").read_text())
        # Grandchildren are reaped by init, not this library; SIGKILL must leave
        # no running descendant. A transient adopted zombie is not execution.
        state = Path(f"/proc/{child}/stat")
        deadline = time.monotonic() + 1
        while True:
            try:
                stopped = state.read_text().split(") ", 1)[1].split()[0] in {"Z", "X"}
            except FileNotFoundError:
                stopped = True
            if stopped: break
            assert time.monotonic() < deadline, "verifier descendant still running"
            time.sleep(.005)


def test_nonzero_exit_and_failed_verifier_still_recheck_inputs(tmp_path):
    fixture = standin(tmp_path, mutation=f'Path({str(tmp_path / "subject.bin")!r}).write_bytes(b"drift")', exit_code=9)
    with pytest.raises(origin.OriginError, match="identity or digest differs"):
        fixture.verify()


def test_bundle_parser_and_execution_budget_admission(tmp_path):
    fixture = standin(tmp_path)
    fixture.pins[1] = write_pin(fixture.pins[1].path, b'{"x":1,"x":2}')
    with pytest.raises(origin.OriginError, match="JSON"): fixture.verify()
    assert not fixture.marker.exists()
    for kwargs in ({"timeout_seconds": float("nan")}, {"timeout_seconds": True}, {"stdout_limit": 0}, {"stderr_limit": 65537}):
        with pytest.raises(origin.OriginError, match="bounds"): fixture.verify(**kwargs)


# Real fixtures from the cli/cli v2.97.0 tracked test corpus. These public
# artifacts/root/tool pins are test admissions ONLY, never Fleet producer policy.
GH_SHA = "141507c337e8b202ad398550c3b73d72f5af92e86f71665214538a81efd4c409"
ROOT_SHA = "65ca537f6ed8a47fd0e560c421baa1f6c1efb8b25fc200d8c5c02c0e92eb2b9c"
PUBLIC_FILES = {
    "gh": GH_SHA, "github-trusted-root.observed.jsonl": ROOT_SHA,
    "github_provenance_demo-0.0.12-py3-none-any.whl": "ae57936def59bc4c75edd3a837d89bcefc6d3a5e31d55a6fa7a71624f92c3c3b",
    "github_provenance_demo-0.0.12-py3-none-any-bundle.jsonl": "4f8c096e38a0eee242574ab100d16701928605409225e59784a3636f742bb27e",
    "reusable-workflow-artifact": "49a3aa6075e0f49f82843e74b5baa614ad2a588e6675612bf108a0a008c5ac25",
    "reusable-workflow-attestation.sigstore.json": "88e35c3496fc9b9bd29629b69271bd32738e170f0d85a12d67da0c72c743f3bd",
}


@pytest.fixture(params=["demo", "reusable"])
def genuine(request):
    directory = os.environ.get("CHUMMER_ORIGIN_FIXTURE_ROOT")
    if not directory:
        pytest.skip("real pinned gh/root/upstream fixtures not supplied; no Sigstore integration claim")
    root = Path(directory)
    assert root.is_absolute() and root.resolve(strict=True) == root
    for name, expected in PUBLIC_FILES.items():
        assert not (root / name).is_symlink()
        assert sha((root / name).read_bytes()) == expected
    if request.param == "demo":
        admitted = replace(policy(), repository="actions/attest-demo", repository_id="763287532",
            repository_uri="https://github.com/actions/attest-demo", owner_id="44036562", owner_uri="https://github.com/actions",
            source_commit="a6c23b9806c593664f68637c8f9d45dfcf98b2db", signer_commit="a6c23b9806c593664f68637c8f9d45dfcf98b2db",
            workflow_identity="https://github.com/actions/attest-demo/.github/workflows/build-python.yml@refs/heads/main",
            build_config_identity="https://github.com/actions/attest-demo/.github/workflows/build-python.yml@refs/heads/main",
            subject_name="github_provenance_demo-0.0.12-py3-none-any.whl",
            subject_sha256=PUBLIC_FILES["github_provenance_demo-0.0.12-py3-none-any.whl"],
            run_id="8788389601", run_attempt="1", visibility="private")
        names = ("github_provenance_demo-0.0.12-py3-none-any.whl", "github_provenance_demo-0.0.12-py3-none-any-bundle.jsonl")
        historical_now = datetime(2024, 4, 22, 17, 34, tzinfo=UTC)
        timestamp = ("TimestampAuthority", "2024-04-22T17:33:26Z")
    else:
        admitted = replace(policy(), repository="malancas/attest-demo", repository_id="804070735",
            repository_uri="https://github.com/malancas/attest-demo", owner_id="16248153", owner_uri="https://github.com/malancas",
            source_commit="95baf27389e83e6a5c48f42e190d48d7abcea19e", signer_commit="09b495c3f12c7881b3cc17209a327792065c1a1d",
            workflow_identity="https://github.com/github/artifact-attestations-workflows/.github/workflows/attest.yml@09b495c3f12c7881b3cc17209a327792065c1a1d",
            build_config_identity="https://github.com/malancas/attest-demo/.github/workflows/shared.yml@refs/heads/main",
            subject_name="github_provenance_demo-0.0.0-py3-none-any.whl", subject_sha256=PUBLIC_FILES["reusable-workflow-artifact"],
            run_id="9228858953", run_attempt="1", timestamp_types=("Tlog",))
        names = ("reusable-workflow-artifact", "reusable-workflow-attestation.sigstore.json")
        historical_now = datetime(2024, 5, 24, 19, 15, tzinfo=UTC)
        timestamp = ("Tlog", "2024-05-24T19:14:24Z")
    pins = tuple(origin.PinnedFile(root / name, PUBLIC_FILES[name]) for name in
                 (*names, "gh", "github-trusted-root.observed.jsonl"))
    yield SimpleNamespace(policy=admitted, pins=pins, historical_now=historical_now, timestamp=timestamp)
    for name, expected in PUBLIC_FILES.items():
        assert sha((root / name).read_bytes()) == expected


def test_genuine_pinned_gh_sigstore_historical_compatibility_only(genuine):
    facts = origin.verify_origin(genuine.policy, *genuine.pins, now=genuine.historical_now)
    assert facts.verified_timestamps == (genuine.timestamp,)
    assert facts.policy == genuine.policy
    assert facts.verifier_sha256 == GH_SHA and facts.trusted_root_sha256 == ROOT_SHA


def test_genuine_valid_historical_signature_is_stale_at_real_current_clock(genuine):
    now = datetime.now(UTC)
    assert now.year >= 2026
    with pytest.raises(origin.OriginError, match="timestamp is not fresh"):
        origin.verify_origin(genuine.policy, *genuine.pins, now=now)


@pytest.mark.parametrize("change", ["repository", "source", "signer", "subject", "signature"])
def test_genuine_crypto_and_identity_rejections(genuine, tmp_path, change):
    admitted, pins = genuine.policy, list(genuine.pins)
    if change == "repository":
        repository = admitted.repository.split("/")[0] + "/wrong-repo"
        admitted = replace(admitted, repository=repository, repository_uri="https://github.com/" + repository,
            build_config_identity=admitted.build_config_identity.replace(admitted.repository, repository))
    elif change == "source": admitted = replace(admitted, source_commit="0" * 40)
    elif change == "signer": admitted = replace(admitted, signer_commit="0" * 40)
    elif change == "subject":
        pins[0] = write_pin(tmp_path / "tampered-subject", pins[0].path.read_bytes() + b"tampered")
        admitted = replace(admitted, subject_sha256=pins[0].sha256)
    else:
        bundle = json.loads(pins[1].path.read_bytes())
        signature = bytearray(base64.b64decode(bundle["dsseEnvelope"]["signatures"][0]["sig"]))
        signature[0] ^= 1
        bundle["dsseEnvelope"]["signatures"][0]["sig"] = base64.b64encode(signature).decode()
        pins[1] = write_pin(tmp_path / "tampered-bundle.json", json.dumps(bundle).encode())
    # Repin only the deliberate test mutation, so rejection must reach actual
    # gh crypto/policy, not a stale fixture checksum or fake verifier result.
    with pytest.raises(origin.OriginError, match="cryptographic verification failed"):
        origin.verify_origin(admitted, *pins, now=genuine.historical_now)
