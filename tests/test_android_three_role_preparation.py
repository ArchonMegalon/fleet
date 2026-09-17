"""Offline composition only; no hosted deployment or authentication claim.

The existing four-role fixture is deliberately synthetic. Real materializer,
consumer parsers and Jobs API validators run; only public API responses are
modeled. No production credentials, processes, sockets or owner are created.
"""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import shlex
import stat

import pytest
import yaml

from scripts import android_deployment_materializer as materializer
from scripts import android_hosted_controller_roles as hosted
from scripts import android_workflow_identity as identity
from scripts import android_workflow_job_binder as binder
import test_android_deployment_materializer as profile_fixture
import test_android_workflow_identity as api_fixture


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _write(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    path.write_bytes(raw)
    path.chmod(0o600)
    return _sha(raw)


@pytest.fixture(autouse=True)
def no_external_actions(monkeypatch):
    attempts = []
    def forbidden(*_args, **_kwargs):
        attempts.append(True)
        pytest.fail("unexpected external action in offline composition test")
    monkeypatch.setattr(identity, "_fetch", forbidden)
    monkeypatch.setattr(identity, "authenticate_workflow_job", forbidden)
    monkeypatch.setattr(identity.origin, "_run", forbidden)
    monkeypatch.setattr(hosted.oidc, "_request_token", forbidden)
    monkeypatch.setattr(hosted.rendezvous, "HostedClient", forbidden)
    monkeypatch.setattr(materializer.owner, "LocalCaptureOwner", forbidden)
    yield
    # Production fail-closed wrappers catch BaseException; an intercepted call
    # must still fail this test even if the wrapper normalizes its exception.
    assert attempts == []


@pytest.fixture
def packet(tmp_path):
    profile = profile_fixture._profile(tmp_path)
    context = profile_fixture._context()
    profile_path = tmp_path / "synthetic-profile.json"
    context_path = tmp_path / "synthetic-context.json"
    profile_sha = _write(profile_path, profile)
    context_sha = _write(context_path, context)
    outputs = tmp_path / "outputs"
    outputs.mkdir(mode=0o700)
    return profile, context, profile_path, profile_sha, context_path, context_sha, outputs


def _args(packet, role):
    _, _, profile, profile_sha, context, context_sha, outputs = packet
    return ["--profile", str(profile), "--profile-sha256", profile_sha,
            "--context", str(context), "--context-sha256", context_sha,
            "--role", role, "--output", str(outputs / (role + ".json"))]


def _render_all(packet):
    _, _, profile, profile_sha, context, context_sha, outputs = packet
    result = {}
    for role in materializer.ROLES:
        output = outputs / (role + ".json")
        digest = materializer.materialize(profile, profile_sha, context, context_sha, output, role)
        raw = output.read_bytes()
        assert digest == _sha(raw)
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
        result[role] = json.loads(raw)
    return result


def test_four_real_consumer_documents_preserve_authority_while_rebinding_context(packet):
    profile, context, profile_path, profile_sha, context_path, context_sha, _ = packet
    unchanged = deepcopy(profile)
    before = json.loads(profile_path.read_bytes())
    rendered = _render_all(packet)
    assert profile == unchanged
    assert _sha(profile_path.read_bytes()) == profile_sha
    assert _sha(context_path.read_bytes()) == context_sha
    for role, value in rendered.items():
        assert value["pins"] == before[role]["pins"]
        assert value["artifact_policy"]["subject_sha256"] == before[role]["artifact_policy"]["subject_sha256"]
        assert value["artifact_policy"]["predicate_type"] == before[role]["artifact_policy"]["predicate_type"]
        assert value["artifact_policy"]["source_commit"] == context["fleet_sha"]
        for name, job in value["role_binding"]["templates"].items():
            original = before[role]["role_binding"]["templates"][name]
            assert job == original | {key: context["fleet_sha"] if key in {"sha", "workflow_sha"}
                                      else context[key] for key in materializer.MUTABLE_JOB_FIELDS}
    for role in binder.ROLES:
        assert rendered[role]["transport_inputs"] == before[role]["transport_inputs"]
    protected = rendered["protected"]
    for name in ("persistent", "secret_inputs", "runtime_policy"):
        assert protected[name] == before["protected"][name]
    assert protected["launcher"]["code_pins"] == before["protected"]["launcher"]["code_pins"]
    assert protected["launcher"]["attempt"] == context["transaction_id"]
    assert protected["launcher"]["output"].endswith("/outputs/" + context["transaction_id"])


@pytest.mark.parametrize("role", materializer.ROLES)
@pytest.mark.parametrize("field", ["profile", "context"])
def test_cli_rejects_changed_bytes_under_previously_admitted_digest(packet, capsys, role, field):
    index = 2 if field == "profile" else 4
    path = packet[index]
    # Equivalent JSON with different bytes must not acquire the old admission.
    path.write_bytes(path.read_bytes() + b" ")
    assert materializer.main(_args(packet, role)) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == materializer.ERROR + "\n"
    assert list(packet[-1].iterdir()) == []


@pytest.mark.parametrize("wrong_sha", [
    "5732c7803c934a6eeb02ab8dbe474e5ea9703755",  # Android commit, not Fleet workflow.
    "914e33fd3f4961824338dcfaeca8a618569f6907",  # Base code, not a future workflow commit.
])
def test_context_requires_the_same_future_fleet_and_workflow_commit(packet, wrong_sha):
    profile, context, *_ = packet
    context["fleet_sha"] = wrong_sha
    with pytest.raises(materializer.MaterializerError, match="^" + materializer.ERROR + "$"):
        materializer.render(profile, context, "capture")
    assert list(packet[-1].iterdir()) == []


def _modeled_metadata(rendered, monkeypatch):
    binding = rendered["owner"]["role_binding"]
    names, templates = binder.validate_role_binding(binding)
    policy = templates["capture"]
    run_url = identity.API + "/repos/" + policy.repository + "/actions/runs/" + policy.run_id
    attempt_url = run_url + "/attempts/" + policy.run_attempt
    jobs_url = attempt_url + "/jobs?per_page=100&page=1"
    attempt = api_fixture.api_attempt()
    attempt.update(id=int(policy.run_id), run_attempt=int(policy.run_attempt), head_sha=policy.sha,
                   path=".github/workflows/fleet.yml", url=run_url,
                   html_url="https://github.com/" + policy.repository + "/actions/runs/" + policy.run_id)
    attempt["head_commit"]["id"] = policy.sha
    jobs = {"total_count": 3, "jobs": []}
    for index, role in enumerate(binder.ROLES):
        row = deepcopy(api_fixture.api_jobs()["jobs"][0])
        job_id, check_id = 1700 + index, 1900 + index
        row.update(id=job_id, run_id=int(policy.run_id), run_attempt=int(policy.run_attempt),
                   run_url=run_url, head_sha=policy.sha, name=names[role],
                   url=identity.API + "/repos/" + policy.repository + "/actions/jobs/" + str(job_id),
                   html_url="https://github.com/" + policy.repository + "/actions/runs/" + policy.run_id + "/job/" + str(job_id),
                   check_run_url=identity.API + "/repos/" + policy.repository + "/check-runs/" + str(check_id))
        jobs["jobs"].append(row)
    calls = []
    def fetch(url, deadline):
        calls.append((url, deadline))
        assert url in {attempt_url, jobs_url}
        return api_fixture.raw(attempt if url == attempt_url else jobs)
    monkeypatch.setattr(identity, "_fetch", fetch)
    return binding, templates, jobs, calls


def test_real_renderer_to_binder_changes_only_observed_check_ids(packet, monkeypatch):
    rendered = _render_all(packet)
    binding, templates, _, calls = _modeled_metadata(rendered, monkeypatch)
    before = deepcopy(binding)
    result = binder.bind_deployment_roles(binding=binding, current_policies=templates)
    assert binding == before
    for index, role in enumerate(binder.ROLES):
        assert asdict(result[role]) == asdict(templates[role]) | {"check_run_id": str(1900 + index)}
    assert len(calls) == 2 and calls[0][1] == calls[1][1]
    # The authentication trap above was never called: these are expectations,
    # not authenticated facts, issued challenges, leases or signing authority.


@pytest.mark.parametrize("role_index", [0, 1, 2])
@pytest.mark.parametrize("state", ["queued", "missing", "completed"])
def test_serial_or_terminal_role_cannot_satisfy_materialized_binding(packet, monkeypatch, role_index, state):
    rendered = _render_all(packet)
    binding, templates, jobs, calls = _modeled_metadata(rendered, monkeypatch)
    if state == "missing":
        jobs["jobs"].pop(role_index)
        jobs["total_count"] -= 1
    else:
        jobs["jobs"][role_index]["status"] = state
        if state == "completed":
            jobs["jobs"][role_index]["conclusion"] = "success"
    with pytest.raises(binder.JobBindingError, match="^" + binder.ERROR + "$"):
        binder.bind_deployment_roles(binding=binding, current_policies=templates)
    assert len(calls) == 2


@pytest.mark.parametrize("phase,role", [("capture", "capture"), ("emission-prepare", "emission")])
def test_rendering_and_job_discovery_do_not_provision_hosted_inputs(packet, monkeypatch, phase, role):
    rendered = _render_all(packet)
    _, _, _, calls = _modeled_metadata(rendered, monkeypatch)
    output = packet[-1] / (role + ".json")
    assert not hosted._path(rendered[role]["attempt_directory"]).exists()
    for path in rendered[role]["transport_inputs"].values():
        assert not hosted._path(path).exists()
    with pytest.raises(hosted.RoleError, match="^" + hosted.ERROR + "$"):
        hosted.run(phase, output, _sha(output.read_bytes()))
    assert len(calls) == 2  # Real discovery succeeded; missing custody still rejects.
    assert not hosted._path(rendered[role]["attempt_directory"]).exists()


SOURCE_SUITES = (
    "tests/test_android_three_role_preparation.py",
    "tests/test_android_deployment_materializer.py",
    "tests/test_android_deployment_materializer_adversarial.py",
    "tests/test_android_hosted_controller_roles.py",
    "tests/test_android_workflow_job_binder.py",
    "tests/test_android_protected_job_supervisor.py",
    "tests/test_android_hosted_input_stager.py",
    "tests/test_android_hosted_source_admission.py",
    "tests/test_android_hosted_phase_caller.py",
)


def test_source_ci_is_read_only_pr_and_main_push_without_operational_jobs():
    root = Path(__file__).resolve().parents[1]
    raw = (root / ".github/workflows/android-role-source-tests.yml").read_text()
    workflow = yaml.safe_load(raw)
    assert set(workflow) == {"name", "on", "permissions", "jobs"}
    assert workflow["on"] == {"pull_request": None, "push": {"branches": ["main"]}}
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"source-unit-tests"}
    job = workflow["jobs"]["source-unit-tests"]
    assert set(job) == {"runs-on", "timeout-minutes", "steps"}
    assert job["runs-on"] == "ubuntu-24.04" and job["timeout-minutes"] == 5
    checkout, tests = job["steps"]
    assert checkout == {
        "uses": "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
        "with": {"fetch-depth": 1, "persist-credentials": False},
    }
    assert set(tests) == {"name", "shell", "run"} and tests["shell"] == "bash"
    # Exact shapes exclude environments, secrets, uploads, OIDC/package grants,
    # services, reusable/dynamic execution and additional action steps.
    assert "${{" not in raw
    body = tests["run"]
    assert "/usr/bin/python3.12 -I -m venv" in body
    assert "os.getuid() != 0 and os.getgid() != 0" in body
    tokens = shlex.split(body.replace("\\\n", " "))
    for flag in ("--isolated", "--require-hashes", "--only-binary=:all:", "--no-deps",
                 "--no-cache-dir", "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
                 "PYTHONDONTWRITEBYTECODE=1", "no:cacheprovider"):
        assert flag in tokens
    assert tokens[tokens.index("--index-url") + 1] == "https://pypi.org/simple"
    assert tokens[tokens.index("-r") + 1] == "tests/android-role-source-requirements.txt"
    assert "-I -m pip --isolated check" in body
    assert [token for token in tokens if token.startswith("tests/test_")] == list(SOURCE_SUITES)
    assert all((root / suite).is_file() for suite in SOURCE_SUITES)


def test_source_ci_lock_is_exact_hashed_binary_test_closure_only():
    path = Path(__file__).resolve().parent / "android-role-source-requirements.txt"
    raw = "\n".join(line for line in path.read_text().splitlines() if not line.startswith("#"))
    entries = raw.replace("\\\n", "").strip().splitlines()
    pins = {}
    for entry in entries:
        match = re.fullmatch(r"([A-Za-z]+)==([0-9.]+) +--hash=sha256:([0-9a-f]{64})", entry)
        assert match is not None
        name, version, _digest = match.groups()
        assert name.lower() not in pins
        pins[name.lower()] = version
    assert pins == {
        "cffi": "2.1.1", "cryptography": "50.0.1", "iniconfig": "2.3.0",
        "packaging": "26.3", "pluggy": "1.6.0", "pycparser": "3.0",
        "pygments": "2.21.0", "pyjwt": "2.13.0", "pytest": "9.0.2", "pyyaml": "6.0.2",
    }
