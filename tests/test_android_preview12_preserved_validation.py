"""Real filesystem/qualified-consumer rejection tests, not a release proof.

Custody metadata is modeled for unprivileged temporary fixtures. The isolated
toolchain tests additionally label modeled prior Android/provenance gates; the
new receipt, tree hashing and transaction binding checks remain real. No test
claims successful qualified-consumer validation or protected runtime authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace

import pytest

import test_android_preview12_external_rebuilder as fixture
import test_android_preview12_protected_transaction as transaction
import test_android_preview12_toolchain_tree as tree_fixture
from test_android_preview12_toolchain_tree import tree


@pytest.fixture
def fleet():
    return fixture.load_module()


@pytest.fixture
def mount_model(tmp_path, monkeypatch):
    """Model custody metadata only; links, Git objects and bytes remain real."""
    original_stat = Path.stat
    original_fstat = os.fstat
    writable, foreign = set(), set()

    def metadata(path, *args, **kwargs):
        value = original_stat(path, *args, **kwargs)
        fields = {name: getattr(value, name) for name in dir(value) if name.startswith("st_")}
        fields["st_uid"] = 123 if path in foreign else 0
        if not path.is_relative_to(tmp_path):
            fields["st_mode"] &= ~0o022  # Temporary ancestors are not protected mounts.
        return SimpleNamespace(**fields)

    monkeypatch.setattr(Path, "stat", metadata)
    def fd_metadata(descriptor):
        value = original_fstat(descriptor)
        fields = {name: getattr(value, name) for name in dir(value) if name.startswith("st_")}
        fields["st_uid"] = 0
        return SimpleNamespace(**fields)
    monkeypatch.setattr(os, "fstat", fd_metadata)
    monkeypatch.setattr(os, "getuid", lambda: 0)
    monkeypatch.setattr(os, "statvfs", lambda path: SimpleNamespace(
        f_flag=0 if any(Path(path) == root or Path(path).is_relative_to(root) for root in writable) else os.ST_RDONLY))
    return writable, foreign


def protected(path, raw=b"public offline test fixture"):
    path.write_bytes(raw)
    path.chmod(0o600)
    return path


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Offline Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgSign=false", *args], check=True, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"},
    ).stdout.strip()


def repository(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init", "--quiet")
    protected(root / "source.txt", b"reviewed source")
    protected(root / ".gitignore", b"*.env\n")
    git(root, "add", "source.txt", ".gitignore")
    git(root, "commit", "--quiet", "-m", "Offline exact source")
    return root, git(root, "rev-parse", "HEAD")


def inputs(fleet, tmp_path):
    roots = {}
    for name in ("workspace_root", "authority_root", "dotnet_root", "java_root", "android_sdk_root"):
        roots[name] = tmp_path / name
        roots[name].mkdir(mode=0o700)
    lock = json.loads(fixture.LOCK.read_bytes())
    return {
        **roots,
        "lock_path": protected(tmp_path / "lock.json", fixture.LOCK.read_bytes()),
        "source_graph": protected(tmp_path / "source-graph.json", json.dumps(transaction.source_graph(fleet, lock)).encode()),
        "package_authority": protected(roots["authority_root"] / "package-authority.json", b"{}"),
        "bundletool": protected(tmp_path / "bundletool.jar"),
        "upload_certificate": protected(tmp_path / "public-upload-certificate.pem"),
        "java_tool_observation": protected(tmp_path / "java-observation.json", b"{}"),
        "installed_closure_receipt": protected(tmp_path / "installed-closure.json", b'{"offline":"fixture"}\n'),
    }


def capture_only(fleet, values):
    # Exercise input capture independently; this is deliberately NOT an
    # admitted factory and is never supplied to a signing transaction.
    value = object.__new__(fleet.PreservedProtectedValidation)
    value.workspace_root, value.authority_root = values["workspace_root"], values["authority_root"]
    value.files = {name: values["lock_path" if name == "lock" else name] for name in (
        "lock", "source_graph", "package_authority", "bundletool", "upload_certificate", "java_tool_observation",
        "installed_closure_receipt")}
    value.tool_roots = {name: values[f"{name}_root"] for name in ("dotnet", "java", "android_sdk")}
    value._limits = {}
    return value


def test_real_writable_mount_is_not_preserved_custody(fleet, tmp_path):
    # No mount/ownership mock: a writable temporary filesystem cannot qualify.
    assert not os.statvfs(tmp_path).f_flag & os.ST_RDONLY
    with pytest.raises(fleet.RebuilderError):
        fleet._preserved_path(tmp_path, "workspace", directory=True)


@pytest.mark.parametrize("fault", ["relative", "missing", "symlink", "writable", "foreign", "mode"])
def test_preserved_paths_reject_noncanonical_or_mutable_inputs(fleet, tmp_path, mount_model, fault):
    path = protected(tmp_path / "input")
    writable, foreign = mount_model
    if fault == "relative":
        path = Path("relative")
    elif fault == "missing":
        path.unlink()
    elif fault == "symlink":
        link = tmp_path / "link"
        link.symlink_to(path)
        path = link
    elif fault == "writable":
        writable.add(path)
    elif fault == "foreign":
        foreign.add(path)
    else:
        path.chmod(0o622)
    with pytest.raises(fleet.RebuilderError):
        fleet._preserved_path(path, "fixture")


@pytest.mark.parametrize("leaf", ["nested", "nested/file"])
def test_readonly_root_cannot_hide_writable_nested_mount(fleet, tmp_path, mount_model, leaf):
    (tmp_path / "nested").mkdir()
    protected(tmp_path / "nested/file")
    mount_model[0].add(tmp_path / leaf)
    assert os.statvfs(tmp_path).f_flag & os.ST_RDONLY
    with pytest.raises(fleet.RebuilderError, match="read-only"):
        fleet._preserved_tree(tmp_path, "fixture")


def test_preserved_inventory_allows_only_contained_safe_links(fleet, tmp_path, mount_model):
    root = tmp_path / "root"
    root.mkdir()
    protected(root / "file")
    (root / "link").symlink_to("file")
    fleet._preserved_tree(root, "fixture")
    (root / "link").unlink()
    outside = protected(tmp_path / "outside")
    (root / "link").symlink_to(outside)
    with pytest.raises(fleet.RebuilderError):
        fleet._preserved_tree(root, "fixture")


def test_preserved_inventory_rejects_foreign_owned_link_itself(fleet, tmp_path, mount_model):
    root = tmp_path / "root"
    root.mkdir()
    protected(root / "file")
    link = root / "link"
    link.symlink_to("file")
    fleet._preserved_tree(root, "fixture")
    mount_model[1].add(link)
    assert stat.S_IMODE(link.lstat().st_mode) == 0o777
    with pytest.raises(fleet.RebuilderError, match="link is not root-owned"):
        fleet._preserved_tree(root, "fixture")


def test_complete_preserved_git_bytes_pass_without_changing_repository(fleet, tmp_path, mount_model):
    root, commit = repository(tmp_path)
    before = git(root, "status", "--porcelain")
    fleet._preserved_repository_bytes(root, commit)
    assert git(root, "status", "--porcelain") == before == ""


def test_preserved_git_blob_streams_beyond_eight_megabytes(fleet, tmp_path, mount_model, monkeypatch):
    root, _ = repository(tmp_path)
    path = root / "large-source.bin"
    with path.open("wb") as stream:
        for _ in range(9):
            stream.write(b"x" * (1024 * 1024))
    git(root, "add", path.name)
    git(root, "commit", "--quiet", "-m", "Offline nine MiB source")
    commit = git(root, "rev-parse", "HEAD")
    sizes = tree_fixture.instrument_reads(fleet, monkeypatch)
    fleet._preserved_repository_bytes(root, commit)
    assert len(sizes) >= 20 and max(sizes) == 1024 * 1024


@pytest.mark.parametrize("relative", ["objects/info/alternates", "objects/info/http-alternates", "commondir",
                                       "gitdir", "shallow", "worktrees", "modules", "info/grafts", "refs/replace"])
def test_external_git_storage_rejected_before_any_git_execution(fleet, tmp_path, mount_model, monkeypatch, relative):
    root, commit = repository(tmp_path)
    path = root / ".git" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    protected(path, b"/unreviewed/external-storage")
    monkeypatch.setattr(fleet, "_git", lambda *args, **kwargs: pytest.fail("must not consult Git"))
    with pytest.raises(fleet.RebuilderError, match="external or replacement"):
        fleet._preserved_repository_bytes(root, commit)


@pytest.mark.parametrize("relative", ["hooks/post-index-change", "hooks/pre-commit", "objects/pack/partial.promisor"])
def test_hooks_and_partial_clone_markers_are_rejected_before_git(fleet, tmp_path, mount_model, monkeypatch, relative):
    root, commit = repository(tmp_path)
    path = root / ".git" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    protected(path, b"nonexecuted hostile fixture")
    path.chmod(0o700)
    monkeypatch.setattr(fleet, "_git", lambda *args, **kwargs: pytest.fail("must not consult Git"))
    with pytest.raises(fleet.RebuilderError, match="active hooks|partial clone"):
        fleet._preserved_repository_bytes(root, commit)


@pytest.mark.parametrize("extra", [
    "\n[include]\npath = /unreviewed/config\n", "\n[includeIf \"gitdir:*\"]\npath = /unreviewed/config\n",
    "\n[filter \"unreviewed\"]\nclean = executable-helper\n", "\n[core]\nfsmonitor = executable-helper\n",
    "\n[core]\nworktree = /other/worktree\n", "\n[core]\nsshcommand = executable-helper\n",
    "\n[extensions]\nworktreeConfig = true\n", "\n[credential]\nhelper = executable-helper\n",
    "\n[remote \"origin\"]\nurl = https://unreviewed.invalid/repo.git\nfetch = +refs/heads/*:refs/remotes/origin/*\n",
])
def test_git_config_helpers_or_external_authority_rejected_before_git(fleet, tmp_path, mount_model, monkeypatch, extra):
    root, commit = repository(tmp_path)
    path = root / ".git/config"
    path.write_text(path.read_text() + extra)
    monkeypatch.setattr(fleet, "_git", lambda *args, **kwargs: pytest.fail("must not consult Git"))
    with pytest.raises(fleet.RebuilderError, match="helper-free clone"):
        fleet._preserved_repository_bytes(root, commit)


@pytest.mark.parametrize("fault", ["hidden-edit", "ignored-extra", "extra-directory", "missing", "mode", "link", "external-git"])
def test_actual_git_objects_reject_hidden_or_incomplete_source(fleet, tmp_path, mount_model, fault):
    root, commit = repository(tmp_path)
    if fault == "hidden-edit":
        git(root, "update-index", "--assume-unchanged", "source.txt")
        (root / "source.txt").write_bytes(b"unreviewed source")
        assert git(root, "status", "--porcelain") == ""
    elif fault == "ignored-extra":
        protected(root / "unreviewed.env")
        assert git(root, "status", "--porcelain") == ""
    elif fault == "extra-directory":
        (root / "unreviewed").mkdir()
    elif fault == "missing":
        (root / "source.txt").unlink()
    elif fault == "mode":
        (root / "source.txt").chmod(0o700)
    elif fault == "link":
        (root / "source.txt").unlink()
        (root / "source.txt").symlink_to(".gitignore")
    else:
        (root / ".git").rename(tmp_path / "external-git")
        (root / ".git").symlink_to(tmp_path / "external-git", target_is_directory=True)
    with pytest.raises(fleet.RebuilderError):
        fleet._preserved_repository_bytes(root, commit)


def test_input_capture_binds_every_separate_public_input(fleet, tmp_path, mount_model):
    values = inputs(fleet, tmp_path)
    value = capture_only(fleet, values)
    first = value._capture_inputs()
    assert set(first) == {"lock", "source_graph", "package_authority", "bundletool", "upload_certificate",
                          "java_tool_observation", "installed_closure_receipt"}
    for name, path in value.files.items():
        original = path.read_bytes()
        path.write_bytes(original + b"drift")
        assert value._capture_inputs()[name] != first[name]
        path.write_bytes(original)
    after = value._capture_inputs()
    assert {key: row for key, row in after.items() if key != "installed_closure_receipt"} \
        == {key: row for key, row in first.items() if key != "installed_closure_receipt"}
    assert after["installed_closure_receipt"][1] == first["installed_closure_receipt"][1]
    assert after["installed_closure_receipt"][0] != first["installed_closure_receipt"][0]


def modeled_toolchain_boundary(fleet, tmp_path, monkeypatch):
    """Exercise real _check_exact toolchain work, not a qualified factory.

    Prior source/Android consumer and public-certificate operations are modeled
    explicitly. No receipt/path/hash/tree/closure or bind_transaction gate is
    replaced. The tiny tool files are never executed.
    """
    values = inputs(fleet, tmp_path)
    value = capture_only(fleet, values)
    value.lock = json.loads(values["lock_path"].read_bytes())
    value.graph = json.loads(values["source_graph"].read_bytes())
    observed = {}
    for name, root in value.tool_roots.items():
        protected(root / "tiny-nonexecuted-tool", name.encode())
        digest, count, size = fleet._tree_digest(root, f"offline {name}")
        value.lock["toolchain"][name].update(tree_sha256=digest, file_count=count, size_bytes=size)
        observed[name] = {"treeSha256": digest, "fileCount": count, "sizeBytes": size}
    value.lock["toolchain"].update(
        bundletool_sha256=hashlib.sha256(values["bundletool"].read_bytes()).hexdigest(),
        installed_closure_receipt_sha256=hashlib.sha256(values["installed_closure_receipt"].read_bytes()).hexdigest(),
        builder_image="offline-builder@sha256:" + "a" * 64,
        signer_image="offline-signer@sha256:" + "b" * 64,
    )
    protected(values["lock_path"], json.dumps(value.lock).encode())
    value._bindings = value._capture_inputs()
    events, traversals = [], []
    public_tools = {name: protected(tmp_path / f"nonexecuted-{name}") for name in ("python3", "openssl")}
    android_root = value.workspace_root / "chummer-android"
    value.android = SimpleNamespace(
        ROOT=android_root,
        __file__=str(android_root / value.lock["android_authority"]["attestation_consumer"]["path"]),
        _trusted_system_executable=lambda path, label: public_tools[path.name],
        _run_validator=lambda *args: events.append("modeled-source-validator"),
        _load_trusted_java_toolchain=lambda path: {
            "tools": {"java": value.tool_roots["java"] / "bin/java"},
            "dotnet": value.tool_roots["dotnet"] / "dotnet",
        },
    )
    value._functions = {}
    monkeypatch.setattr(value, "_check_source", lambda: events.append("modeled-source-check"))
    monkeypatch.setattr(fleet, "_validate_android_consumer_inputs", lambda *args: events.append("modeled-consumer-inputs"))

    def public_certificate(command, **kwargs):
        assert command == [str(public_tools["openssl"]), "x509", "-in", str(values["upload_certificate"]),
                           "-noout", "-fingerprint", "-sha256"]
        events.append("modeled-public-certificate")
        return subprocess.CompletedProcess(command, 0, "sha256 Fingerprint=" + fleet.UPLOAD_CERTIFICATE_SHA256)

    monkeypatch.setattr(fleet.subprocess, "run", public_certificate)
    actual_tree_digest = fleet._tree_digest

    def measured(root, label):
        traversals.append(root)
        return actual_tree_digest(root, label)

    monkeypatch.setattr(fleet, "_tree_digest", measured)
    expected = {
        "platform": "linux/amd64", **observed,
        "bundletoolSha256": value.lock["toolchain"]["bundletool_sha256"],
        "installedClosureReceiptSha256": value.lock["toolchain"]["installed_closure_receipt_sha256"],
        "reportedBuilderImage": value.lock["toolchain"]["builder_image"],
        "plannedSignerImage": value.lock["toolchain"]["signer_image"],
        "builderExecutionProvenanceAuthenticated": False, "protectedSignerRuntimeVerified": False,
    }
    expected["closureSha256"] = hashlib.sha256(
        json.dumps(expected, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    lease = SimpleNamespace(
        handoff={"bindings": {"sourceGraphSha256": value._bindings["source_graph"],
                              "toolchainClosureSha256": expected["closureSha256"]}},
        toolchain={"builderClosureSha256": expected["closureSha256"],
                   "installedClosureReceiptSha256": expected["installedClosureReceiptSha256"]},
        java_root=value.tool_roots["java"],
    )
    return value, values, lease, expected, events, traversals


def test_installed_closure_receipt_is_mandatory(fleet, tmp_path, monkeypatch):
    values = inputs(fleet, tmp_path)
    del values["installed_closure_receipt"]
    monkeypatch.setattr(fleet.PreservedProtectedValidation, "_capture_inputs",
                        lambda self: pytest.fail("missing mandatory argument must precede capture"))
    with pytest.raises(TypeError, match="installed_closure_receipt"):
        fleet.PreservedProtectedValidation(**values)


@pytest.mark.parametrize("fault", ["missing", "symlink", "writable", "foreign", "mode"])
def test_installed_closure_receipt_requires_preserved_custody(fleet, tmp_path, mount_model, fault):
    values = inputs(fleet, tmp_path)
    path = values["installed_closure_receipt"]
    if fault == "missing":
        path.unlink()
    elif fault == "symlink":
        path.unlink()
        path.symlink_to(protected(tmp_path / "other-receipt"))
    elif fault == "writable":
        mount_model[0].add(path)
    elif fault == "foreign":
        mount_model[1].add(path)
    else:
        path.chmod(0o644)  # Root-owned/read-only still must be owner-only.
    with pytest.raises(fleet.RebuilderError):
        capture_only(fleet, values)._capture_inputs()


def test_installed_closure_receipt_rejects_real_writable_environment(fleet, tmp_path):
    value = capture_only(fleet, inputs(fleet, tmp_path))
    assert not os.statvfs(tmp_path).f_flag & os.ST_RDONLY
    with pytest.raises(fleet.RebuilderError):
        value._capture_installed_closure_receipt()


def test_measured_closure_reuses_three_real_tree_measurements_without_provenance(
    fleet, tmp_path, tree, mount_model, monkeypatch,
):
    value, values, lease, expected, _, traversals = modeled_toolchain_boundary(fleet, tmp_path, monkeypatch)
    assert value._check_exact() == expected
    assert traversals == list(value.tool_roots.values())
    assert expected["builderExecutionProvenanceAuthenticated"] is False
    assert expected["protectedSignerRuntimeVerified"] is False
    before = json.dumps(lease.toolchain, sort_keys=True)
    traversals.clear()
    value.bind_transaction(values["lock_path"].read_bytes(), lease, value.load_consumer)
    assert traversals == list(value.tool_roots.values())
    assert json.dumps(lease.toolchain, sort_keys=True) == before
    assert not isinstance(lease, fleet.AuthenticatedRebuildHandoff)


@pytest.mark.parametrize("fault", ["bytes", "same-bytes-replacement", "wrong-lock-digest", "tree-bytes"])
def test_installed_closure_receipt_and_live_tool_bytes_cannot_drift(
    fleet, tmp_path, tree, mount_model, monkeypatch, fault,
):
    value, values, _, _, _, traversals = modeled_toolchain_boundary(fleet, tmp_path, monkeypatch)
    path = values["installed_closure_receipt"]
    if fault == "bytes":
        path.write_bytes(path.read_bytes() + b"drift")
    elif fault == "same-bytes-replacement":
        replacement = protected(tmp_path / "replacement", path.read_bytes())
        replacement.replace(path)
    elif fault == "wrong-lock-digest":
        # A wrong digest present at initial admission, not only later drift.
        value.lock["toolchain"]["installed_closure_receipt_sha256"] = "0" * 64
        protected(values["lock_path"], json.dumps(value.lock).encode())
        value._bindings = value._capture_inputs()
    else:
        (value.tool_roots["dotnet"] / "tiny-nonexecuted-tool").write_bytes(b"changed tool")
    with pytest.raises(fleet.RebuilderError, match="input bytes changed|receipt differs|tool tree differs"):
        value._check_exact()
    if fault in ("bytes", "same-bytes-replacement"):
        assert traversals == []


def test_installed_closure_receipt_replacement_during_measurement_is_rejected(
    fleet, tmp_path, tree, mount_model, monkeypatch,
):
    value, values, _, _, _, _ = modeled_toolchain_boundary(fleet, tmp_path, monkeypatch)
    path = values["installed_closure_receipt"]
    replacement = protected(tmp_path / "replacement", path.read_bytes())
    actual = fleet._measured_toolchain_closure

    def replace_after_measurement(*args):
        result = actual(*args)
        replacement.replace(path)
        return result

    monkeypatch.setattr(fleet, "_measured_toolchain_closure", replace_after_measurement)
    with pytest.raises(fleet.RebuilderError, match="receipt changed during validation"):
        value._check_exact()


@pytest.mark.parametrize("field", ["handoff", "builder", "both", "receipt"])
def test_measured_closure_rejects_mismatched_transaction_claims(
    fleet, tmp_path, tree, mount_model, monkeypatch, field,
):
    value, values, lease, _, _, _ = modeled_toolchain_boundary(fleet, tmp_path, monkeypatch)
    if field in ("handoff", "both"):
        lease.handoff["bindings"]["toolchainClosureSha256"] = "0" * 64
    if field in ("builder", "both"):
        lease.toolchain["builderClosureSha256"] = "0" * 64
    if field == "receipt":
        lease.toolchain["installedClosureReceiptSha256"] = "0" * 64
    with pytest.raises(fleet.RebuilderError, match="measured toolchain differs"):
        value.bind_transaction(values["lock_path"].read_bytes(), lease, value.load_consumer)


@pytest.mark.parametrize("operation", ["execute", "reconcile"])
def test_measured_closure_rejects_before_privileged_transaction_work(
    fleet, tmp_path, tree, mount_model, monkeypatch, operation,
):
    value, values, claims, _, events, _ = modeled_toolchain_boundary(fleet, tmp_path, monkeypatch)
    claims.handoff["bindings"]["toolchainClosureSha256"] = "0" * 64
    claims.toolchain["builderClosureSha256"] = "0" * 64  # Coherently wrong, not inconsistent metadata.
    recovery_root = tmp_path / "recovery"
    recovery_root.mkdir(mode=0o700)
    attempt = "d" * 64
    if operation == "reconcile":
        (recovery_root / attempt).mkdir(mode=0o700)
    # Explicitly model ONLY earlier configuration/authentication to reach the
    # real preserved binding. This capability is synthetic, never production.
    lease = fleet.AuthenticatedRebuildHandoff(
        claims.handoff, {}, claims.toolchain, {}, claims.java_root, recovery_root, lambda: None)
    assert "external rebuilder lock is dormant" in fleet.validate_lock(
        value.lock, values["lock_path"].read_bytes())
    monkeypatch.setattr(fleet, "validate_lock", lambda *args: [])
    monkeypatch.setattr(fleet, "_validate_authenticated_handoff",
                        lambda *args, **kwargs: events.append("modeled-earlier-authentication"))

    def forbidden(*args, **kwargs):
        pytest.fail("unbound toolchain reached consumer, ledger, credentials or signing")

    for name in ("load_reviewed_ledger", "reserve_signing_attempt", "sign_aab"):
        monkeypatch.setattr(fleet, name, forbidden)
    monkeypatch.setattr(value, "load_consumer", forbidden)
    output = tmp_path / "must-not-exist"

    def fixture_paths(root):
        # The tree fixture models os.scandir for measured metadata. Use the
        # actual directory names here without depending on its return protocol.
        paths = set()
        for name in os.listdir(root):
            path = root / name
            paths.add(path)
            if path.is_dir() and not path.is_symlink():
                paths.update(fixture_paths(path))
        return paths

    paths_before = fixture_paths(tmp_path)
    args = [values["lock_path"], lambda *args: lease, value.load_consumer, tmp_path, {}]
    if operation == "execute":
        args.append(forbidden)  # credential admission
    args.extend([value, output])
    with pytest.raises(fleet.RebuilderError, match="measured toolchain differs"):
        getattr(fleet, f"{operation}_protected_signer_transaction")(
            *args, attempt_id=attempt, two_green_artifact_id=123, two_green_artifact_sha256="e" * 64)
    assert "modeled-earlier-authentication" in events and "modeled-public-certificate" in events
    assert fixture_paths(tmp_path) == paths_before
    assert not output.exists()


@pytest.mark.parametrize("fault", ["overlap", "foreign-authority", "deleted-workspace", "incomplete-source"])
def test_factory_fails_before_consumer_import_when_preserved_inputs_are_unavailable(
    fleet, tmp_path, mount_model, monkeypatch, fault,
):
    values = inputs(fleet, tmp_path)
    if fault == "overlap":
        values["java_root"] = values["dotnet_root"]
    elif fault == "foreign-authority":
        values["package_authority"] = protected(tmp_path / "outside-authority.json")
    elif fault == "deleted-workspace":
        values["workspace_root"].rmdir()
    monkeypatch.setattr(fleet, "validate_android_consumer", lambda *args: pytest.fail("must not import consumer"))
    with pytest.raises(fleet.RebuilderError):
        fleet.PreservedProtectedValidation(**values)


@pytest.mark.parametrize("fault", ["loader", "lock", "graph", "java"])
def test_exact_transaction_binding_rejects_substitution_before_revalidation(
    fleet, tmp_path, mount_model, monkeypatch, fault,
):
    values = inputs(fleet, tmp_path)
    value = capture_only(fleet, values)
    value._bindings = value._capture_inputs()
    lease = SimpleNamespace(handoff={"bindings": {"sourceGraphSha256": value._bindings["source_graph"]}},
                            java_root=value.tool_roots["java"])
    lock_raw, loader = values["lock_path"].read_bytes(), value.load_consumer
    if fault == "loader":
        loader = lambda: None
    elif fault == "lock":
        lock_raw += b" "
    elif fault == "graph":
        lease.handoff["bindings"]["sourceGraphSha256"] = "0" * 64
    else:
        lease.java_root = tmp_path / "different-java"
    monkeypatch.setattr(value, "_check_exact", lambda: pytest.fail("must reject substitution first"))
    with pytest.raises(fleet.RebuilderError, match="authenticated transaction"):
        value.bind_transaction(lock_raw, lease, loader)


def test_factory_rejects_fake_consumer_before_any_validation(fleet):
    value = object.__new__(fleet.PreservedProtectedValidation)
    value.android = object()
    with pytest.raises(fleet.RebuilderError, match="exact preserved consumer"):
        value(android=object(), signed_aab=None, source_graph=None, sidecar=None,
              two_green_receipt=None, approval=None)


@pytest.fixture
def actual_consumer(fleet):
    configured = os.environ.get("CHUMMER_ANDROID_CURRENT_ROOT")
    if not configured:
        pytest.skip("exact qualified Android checkout required")
    root = Path(configured)
    lock, _ = fleet.load_lock(fixture.LOCK)
    return fleet.validate_android_consumer(root, lock)


def test_real_7cef_protected_entry_rejects_deleted_builder_workspace(actual_consumer, tmp_path):
    android = actual_consumer
    aab, graph = protected(tmp_path / "signed.aab"), protected(tmp_path / "source-graph.json", b"{}")
    claims = {"aab": {"sha256": hashlib.sha256(aab.read_bytes()).hexdigest()},
              "sourceGraph": {"sha256": hashlib.sha256(graph.read_bytes()).hexdigest()}}
    with pytest.raises(ValueError, match="release workspace"):
        android._protected_validation(
            claims, aab, graph, tmp_path / "receipt.json", tmp_path / "approval.json",
            workspace_root=tmp_path / "deleted-builder-workspace",
            package_authority=tmp_path / "missing-package.json", authority_root=tmp_path,
            bundletool=tmp_path / "missing-bundletool.jar", upload_certificate=tmp_path / "missing-public.pem",
            java_tool_authority=tmp_path / "missing-observation.json")


def test_real_7cef_tool_observation_does_not_accept_archive_inventory(actual_consumer, tmp_path):
    inventory = protected(tmp_path / "archive-inventory.json", json.dumps({
        "contract_name": "fleet.android_preview12_installed_toolchain.v1", "archives": [],
    }).encode())
    with pytest.raises(ValueError, match="fields are not exact"):
        actual_consumer._load_trusted_java_toolchain(inventory)


def test_real_7cef_still_rejects_valid_0777_tool_links(actual_consumer, tree):
    _fleet_model, root, _overrides = tree
    protected(root / "real-file")
    assert actual_consumer._trusted_tree_digest(root, "qualified Android tool closure")[1] == 1
    link = root / "contained-link"
    link.symlink_to("real-file")
    assert stat.S_IMODE(link.lstat().st_mode) == 0o777
    # This is an actual qualified-consumer failure, not Fleet's repaired hash.
    # Ownership/ancestry are modeled, while the same real file/link/0777 mode
    # remain. The actual consumer passes the regular file immediately above.
    with pytest.raises(ValueError, match="writable or non-root-owned content"):
        actual_consumer._trusted_tree_digest(root, "qualified Android tool closure")
