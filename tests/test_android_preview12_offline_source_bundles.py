"""Real local Git transport checks; no NuGet, SDK, custody or release proof."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from types import SimpleNamespace

import pytest

from scripts import android_preview12_external_rebuilder as fleet
import test_android_preview12_external_rebuilder as fixture


def git(root, *args, binary=False, input=None):
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(root), "-c", "user.name=Offline Fixture",
         "-c", "user.email=offline@example.invalid", "-c", "commit.gpgSign=false", *args],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, input=input,
        env={"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"},
    )
    return result.stdout if binary else result.stdout.decode().strip()


@pytest.fixture(scope="module")
def complete_bundle(tmp_path_factory):
    root = tmp_path_factory.mktemp("complete-offline-source")
    git(root, "init", "--quiet", "--template=")
    (root / "package-source.txt").write_text("ancestor package source\n")
    (root / ".gitignore").write_text("ignored-input\n")
    (root / "relative-link").symlink_to("package-source.txt")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "package-source ancestor")
    ancestor = git(root, "rev-parse", "HEAD")
    (root / "runtime.txt").write_text("runtime source\n")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "runtime head")
    bundle = root.parent / "complete.bundle"
    git(root, "bundle", "create", str(bundle), "HEAD")
    return SimpleNamespace(root=root, path=bundle, ancestor=ancestor,
                           commit=git(root, "rev-parse", "HEAD"), tree=git(root, "rev-parse", "HEAD^{tree}"),
                           tree_sha256=hashlib.sha256(git(root, "ls-tree", "-r", "-z", "--full-tree", "HEAD", binary=True)).hexdigest())


def write_manifest(case):
    case.manifest.write_text(json.dumps(case.rows))
    return case.manifest


def bind_bundle(case, name, path):
    case.rows[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                       "size_bytes": path.stat().st_size}
    write_manifest(case)


@pytest.fixture
def bundles(tmp_path, complete_bundle):
    # Eight independent input files and all eight admitted graph roles. Sharing
    # tiny fixture object content is not a claim about real release revisions.
    case = SimpleNamespace(graph=fixture.graph(fleet), rows={}, manifest=tmp_path / "manifest.json",
                           workspace=tmp_path / "workspace", inputs=tmp_path / "inputs", source=complete_bundle)
    case.inputs.mkdir()
    for row in case.graph["repositories"]:
        row.update(commit=complete_bundle.commit, tree=complete_bundle.tree, tree_sha256=complete_bundle.tree_sha256)
        path = case.inputs / (row["name"] + ".bundle")
        shutil.copyfile(complete_bundle.path, path)
        bind_bundle(case, row["name"], path)
    return case


@pytest.fixture
def git_calls(monkeypatch):
    # Observe every actual process, including subprocess.run inside a validator.
    original, calls = subprocess.Popen, []
    def observe(command, *args, **kwargs):
        calls.append((list(command), kwargs))
        return original(command, *args, **kwargs)
    monkeypatch.setattr(subprocess, "Popen", observe)
    return calls


def materialize(case, **kwargs):
    return fleet.checkout_source_graph_from_bundles(case.graph, case.workspace, case.manifest, **kwargs)


def assert_failed_before_git(case, calls):
    with pytest.raises(fleet.RebuilderError, match="offline source bundle materialization failed"):
        materialize(case)
    assert calls == []
    assert not case.workspace.exists()
    assert not list(case.workspace.parent.glob(".offline-source-*"))


def test_complete_eight_repo_graph_retains_ancestry_and_uses_only_local_bounded_git(bundles, git_calls):
    roots = materialize(bundles)
    assert set(roots) == set(fleet.REPOSITORIES)
    calls = list(git_calls)
    assert len(calls) == 8 * 18  # Includes frozen-attribute checks and three streamed regular files per repo.
    for command, kwargs in calls:
        assert command[0] == "/usr/bin/git"
        assert not any(value in command for value in ("fetch", "clone", "ls-remote", "push", "pull"))
        assert "protocol.https.allow=always" not in command
        assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == ""
        assert kwargs["env"]["GIT_CONFIG_GLOBAL"] == "/dev/null"
        assert kwargs["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
        assert kwargs["stderr"] == subprocess.DEVNULL and kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["umask"] == 0o077
        if "bundle" in command:
            path = Path(command[-1])
            assert path.parent.name.startswith(".offline-source-") and path.parent != bundles.inputs
    for name, root in roots.items():
        assert stat.S_IMODE(root.stat().st_mode) & 0o077 == 0
        assert git(root, "show", bundles.source.ancestor + ":package-source.txt") == "ancestor package source"
        assert git(root, "rev-parse", "HEAD") == bundles.source.commit
        assert git(root, "rev-parse", "HEAD^") == bundles.source.ancestor
        assert git(root, "remote", "get-url", "origin") == fleet.REPOSITORIES[name][2]
        assert (root / ".git/HEAD").read_text().strip() == bundles.source.commit
        assert (root / "relative-link").readlink() == Path("package-source.txt")
        fleet._preserved_git_storage(root, fleet.REPOSITORIES[name][2])
    assert not list(bundles.workspace.parent.glob(".offline-source-*"))


@pytest.mark.parametrize("attack", ["missing", "extra", "extra-row", "wrong-row", "bad-path", "relative-path",
                                    "dot-path", "upper-digest", "bad-digest", "bool-size", "string-size",
                                    "zero-size", "negative-size", "oversize", "size-drift", "hash-drift"])
def test_manifest_rejections_precede_all_git(bundles, git_calls, attack):
    name = next(iter(bundles.rows))
    row = bundles.rows[name]
    if attack == "missing":
        del bundles.rows[name]
    elif attack == "extra":
        bundles.rows["unexpected-secret-value"] = row
    elif attack == "extra-row":
        row["origin"] = "https://example.invalid"
    elif attack == "wrong-row":
        bundles.rows[name] = []
    elif attack == "bad-path":
        row["path"] = 3
    elif attack == "relative-path":
        row["path"] = "relative.bundle"
    elif attack == "dot-path":
        row["path"] = str(bundles.inputs) + "/./file.bundle"
    elif attack in {"upper-digest", "bad-digest"}:
        row["sha256"] = "A" * 64 if attack == "upper-digest" else "no-digest"
    elif attack == "hash-drift":
        row["sha256"] = "0" * 64
    else:
        row["size_bytes"] = {"bool-size": True, "string-size": "2", "zero-size": 0, "negative-size": -1,
                             "oversize": fleet.OFFLINE_BUNDLE_BYTES + 1, "size-drift": row["size_bytes"] + 1}[attack]
    write_manifest(bundles)
    assert_failed_before_git(bundles, git_calls)


@pytest.mark.parametrize("raw", [b"[]", b"\xff", b"{", b'{"private-password\n":0}',
                                 b'{"private-password":1,"private-password":2}',
                                 b'{"value":NaN}', b" " * (fleet.OFFLINE_MANIFEST_BYTES + 1)])
def test_malformed_manifest_diagnostics_do_not_echo_input(bundles, git_calls, raw):
    bundles.manifest.write_bytes(raw)
    assert_failed_before_git(bundles, git_calls)


@pytest.mark.parametrize("attack", ["symlink", "ancestor-link", "hardlink", "directory", "fifo", "missing",
                                    "manifest-link", "manifest-hardlink", "manifest-relative"])
def test_linked_and_nonregular_inputs_are_rejected_before_git(bundles, git_calls, attack):
    name = next(iter(bundles.rows))
    path = Path(bundles.rows[name]["path"])
    if attack.startswith("manifest-"):
        if attack == "manifest-relative":
            bundles.manifest = Path("manifest.json")
        else:
            link = bundles.manifest.with_name("manifest-alias.json")
            if attack == "manifest-link":
                link.symlink_to(bundles.manifest)
            else:
                os.link(bundles.manifest, link)
            bundles.manifest = link
    elif attack == "hardlink":
        os.link(path, path.with_name("hardlink.bundle"))
    elif attack == "ancestor-link":
        alias = bundles.inputs.with_name("alias")
        alias.symlink_to(bundles.inputs, target_is_directory=True)
        bundles.rows[name]["path"] = str(alias / path.name)
        write_manifest(bundles)
    else:
        path.unlink()
        if attack == "symlink":
            path.symlink_to(bundles.source.path)
        elif attack == "directory":
            path.mkdir()
        elif attack == "fifo":
            os.mkfifo(path)
    assert_failed_before_git(bundles, git_calls)


@pytest.mark.parametrize("kind", ["existing", "linked-parent", "relative", "input-output-overlap"])
def test_output_admission_preserves_existing_entries(bundles, git_calls, kind):
    if kind == "existing":
        bundles.workspace.mkdir()
        (bundles.workspace / "sentinel").write_text("keep")
    elif kind == "linked-parent":
        alias = bundles.inputs.with_name("alias")
        alias.symlink_to(bundles.inputs, target_is_directory=True)
        bundles.workspace = alias / "new-workspace"
    elif kind == "relative":
        bundles.workspace = Path("new-workspace")
    else:
        bundles.workspace = bundles.inputs
    with pytest.raises(fleet.RebuilderError):
        materialize(bundles)
    assert git_calls == [] and bundles.inputs.is_dir()
    if kind == "existing":
        assert (bundles.workspace / "sentinel").read_text() == "keep"


@pytest.mark.parametrize("mode", [0o755, 0o770, 0o777])
def test_nonprivate_workspace_parent_is_rejected_before_git(bundles, git_calls, mode):
    bundles.workspace.parent.chmod(mode)
    try:
        assert_failed_before_git(bundles, git_calls)
    finally:
        bundles.workspace.parent.chmod(0o700)


def test_private_parent_under_writable_nonsticky_ancestor_is_rejected(bundles, git_calls):
    shared = bundles.workspace.parent / "shared"
    shared.mkdir()
    shared.chmod(0o777)
    private = shared / "private"
    private.mkdir(mode=0o700)
    bundles.workspace = private / "workspace"
    assert_failed_before_git(bundles, git_calls)


def test_trusted_sticky_ancestor_preserves_private_child_admission(bundles):
    shared = bundles.workspace.parent / "shared"
    shared.mkdir()
    shared.chmod(0o1777)
    private = shared / "private"
    private.mkdir(mode=0o700)
    bundles.workspace = private / "workspace"
    assert len(materialize(bundles)) == 8


def test_foreign_owned_workspace_ancestor_is_rejected_before_git(bundles, git_calls, monkeypatch):
    original = Path.lstat
    foreign = bundles.workspace.parent
    def metadata(path):
        value = original(path)
        if path == foreign:
            fields = {key: getattr(value, key) for key in dir(value) if key.startswith("st_")}
            fields["st_uid"] = os.getuid() + 12345
            return SimpleNamespace(**fields)
        return value
    monkeypatch.setattr(Path, "lstat", metadata)
    assert_failed_before_git(bundles, git_calls)


def test_aggregate_compressed_input_limit_precedes_snapshot(bundles, git_calls, monkeypatch):
    monkeypatch.setattr(fleet, "OFFLINE_TOTAL_BUNDLE_BYTES", 1)
    assert_failed_before_git(bundles, git_calls)


@pytest.mark.parametrize("attack", ["replace", "grow", "shrink", "hardlink"])
def test_mutating_input_during_streamed_snapshot_is_rejected(bundles, git_calls, monkeypatch, attack):
    original, mutated = os.read, False
    target = Path(next(iter(bundles.rows.values()))["path"])
    identity = target.stat()
    def race(fd, count):
        nonlocal mutated
        chunk = original(fd, count)
        if not mutated and os.fstat(fd).st_ino == identity.st_ino:
            mutated = True
            if attack == "replace":
                replacement = target.with_name("replacement.bundle")
                replacement.write_bytes(target.read_bytes())
                replacement.replace(target)
            elif attack == "grow":
                with target.open("ab") as stream:
                    stream.write(b"growth")
            elif attack == "shrink":
                target.write_bytes(b"short")
            else:
                os.link(target, target.with_name("new-link"))
        return chunk
    monkeypatch.setattr(os, "read", race)
    assert_failed_before_git(bundles, git_calls)
    assert mutated


def test_original_bundle_replacement_after_snapshot_is_never_consumed(bundles, monkeypatch):
    original, changed = fleet._offline_git, False
    def replace_original(args, **kwargs):
        nonlocal changed
        if not changed:
            changed = True
            for row in bundles.rows.values():
                Path(row["path"]).write_bytes(b"hostile replacement")
        return original(args, **kwargs)
    monkeypatch.setattr(fleet, "_offline_git", replace_original)
    assert len(materialize(bundles)) == 8


@pytest.mark.parametrize("kind", ["incremental", "truncated", "invalid", "absent-commit", "wrong-tree", "wrong-listing", "wrong-origin"])
def test_real_bundle_or_exact_graph_failure_cleans_exclusive_workspace(bundles, monkeypatch, kind):
    name = next(iter(bundles.rows))
    path = Path(bundles.rows[name]["path"])
    if kind == "incremental":
        path.unlink()
        git(bundles.source.root, "bundle", "create", str(path), "HEAD", "^" + bundles.source.ancestor)
        bind_bundle(bundles, name, path)
    elif kind in {"truncated", "invalid"}:
        path.write_bytes(path.read_bytes()[:-30] if kind == "truncated" else b"not a git bundle")
        bind_bundle(bundles, name, path)
    elif kind == "wrong-origin":
        bundles.graph["repositories"][0]["repository"] = "https://example.invalid/hostile.git"
    else:
        key = {"absent-commit": "commit", "wrong-tree": "tree", "wrong-listing": "tree_sha256"}[kind]
        bundles.graph["repositories"][0][key] = "0" * (64 if key == "tree_sha256" else 40)
    with pytest.raises(fleet.RebuilderError):
        materialize(bundles)
    assert not bundles.workspace.exists()
    assert not list(bundles.workspace.parent.glob(".offline-source-*"))


def test_complete_pack_missing_a_required_source_blob_is_rejected_by_real_fsck(bundles, monkeypatch):
    source = bundles.source.root
    missing_blob = git(source, "rev-parse", "HEAD:package-source.txt")
    objects = [row.split()[0] for row in git(source, "rev-list", "--objects", "HEAD").splitlines()]
    pack = git(source, "pack-objects", "--stdout", binary=True,
               input=("\n".join(value for value in objects if value != missing_blob) + "\n").encode())
    name = next(iter(bundles.rows))
    path = Path(bundles.rows[name]["path"])
    path.write_bytes(("# v2 git bundle\n" + bundles.source.commit + " HEAD\n\n").encode() + pack)
    bind_bundle(bundles, name, path)
    original, calls = fleet._offline_git, []
    def observe(args, **kwargs):
        calls.append(args)
        return original(args, **kwargs)
    monkeypatch.setattr(fleet, "_offline_git", observe)
    with pytest.raises(fleet.RebuilderError):
        materialize(bundles)
    assert any("fsck" in args for args in calls)
    assert not bundles.workspace.exists()


@pytest.mark.parametrize("capability", [b"@filter=blob:none\n", b"@unknown=private-password\n"])
def test_v3_filtered_or_unknown_capability_is_rejected_even_with_complete_pack(bundles, git_calls, capability):
    name = next(iter(bundles.rows))
    path = Path(bundles.rows[name]["path"])
    remainder = path.read_bytes().split(b"\n", 1)[1]
    path.write_bytes(b"# v3 git bundle\n@object-format=sha1\n" + capability + remainder)
    bind_bundle(bundles, name, path)
    assert_failed_before_git(bundles, git_calls)


def test_v3_complete_sha1_bundle_remains_supported(bundles):
    name = next(iter(bundles.rows))
    path = Path(bundles.rows[name]["path"])
    path.write_bytes(b"# v3 git bundle\n@object-format=sha1\n" + path.read_bytes().split(b"\n", 1)[1])
    bind_bundle(bundles, name, path)
    assert len(materialize(bundles)) == 8


@pytest.mark.parametrize("attack", ["bytes", "ignored", "origin"])
def test_post_checkout_tampering_still_reaches_existing_exact_validators(bundles, monkeypatch, attack):
    original, changed = fleet._offline_git, False
    def tamper(args, **kwargs):
        nonlocal changed
        result = original(args, **kwargs)
        if not changed and "checkout" in args:
            changed = True
            root = Path(args[args.index("-C") + 1])
            if attack == "bytes":
                (root / "package-source.txt").write_text("changed")
                original(["-C", str(root), "update-index", "--assume-unchanged", "package-source.txt"], timeout=15)
            elif attack == "ignored":
                (root / "ignored-input").write_text("hidden input")
            else:
                original(["-C", str(root), "remote", "set-url", "origin", "https://example.invalid/changed.git"], timeout=15)
        return result
    monkeypatch.setattr(fleet, "_offline_git", tamper)
    with pytest.raises(fleet.RebuilderError):
        materialize(bundles)
    assert changed and not bundles.workspace.exists()


@pytest.fixture
def crlf_bundles(bundles, tmp_path):
    root = tmp_path / "declared-crlf-bundle"
    root.mkdir()
    git(root, "init", "--quiet", "--template=")
    (root / ".gitattributes").write_bytes(b"*.sln text eol=crlf\n*.props text eol=crlf\n")
    (root / "fixture.sln").write_bytes(b"first\nsecond\n")
    (root / "fixture.props").write_bytes(b"<Project />\n")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "Real declared checkout representation")
    commit, tree = git(root, "rev-parse", "HEAD"), git(root, "rev-parse", "HEAD^{tree}")
    listing = git(root, "ls-tree", "-r", "-z", "--full-tree", commit, binary=True)
    source = root.parent / "declared-crlf.bundle"
    git(root, "bundle", "create", "--version=2", str(source), "HEAD")
    for row in bundles.graph["repositories"]:
        row.update(commit=commit, tree=tree, tree_sha256=hashlib.sha256(listing).hexdigest())
        target = bundles.inputs / (row["name"] + ".bundle")
        shutil.copyfile(source, target)
        bind_bundle(bundles, row["name"], target)
    return bundles


def test_actual_eight_role_import_accepts_exact_declared_crlf_bytes(crlf_bundles, git_calls):
    roots = materialize(crlf_bundles)
    assert set(roots) == set(fleet.REPOSITORIES)
    for root in roots.values():
        assert (root / "fixture.sln").read_bytes() == b"first\r\nsecond\r\n"
        assert (root / "fixture.props").read_bytes() == b"<Project />\r\n"
    conversions = [command for command, _kwargs in git_calls if "cat-file" in command]
    assert len(conversions) == 8 * 3
    assert all("--attr-source=" + crlf_bundles.graph["repositories"][0]["commit"] in command
               and "--filters" in command for command in conversions)


@pytest.mark.parametrize("raw", [b"first\nsecond\n", b"first\r\nsecond\n", b"changed\r\nsecond\r\n"])
def test_exact_import_rejects_postcheckout_eol_or_content_tampering(crlf_bundles, monkeypatch, raw):
    original, changed = fleet._offline_git, False
    def tamper(args, **kwargs):
        nonlocal changed
        result = original(args, **kwargs)
        if not changed and "checkout" in args:
            changed = True
            root = Path(args[args.index("-C") + 1])
            original(["-C", str(root), "update-index", "--assume-unchanged", "fixture.sln"], timeout=15)
            (root / "fixture.sln").write_bytes(raw)
        return result
    monkeypatch.setattr(fleet, "_offline_git", tamper)
    with pytest.raises(fleet.RebuilderError):
        materialize(crlf_bundles)
    assert changed and not crlf_bundles.workspace.exists()


@pytest.mark.parametrize("attack", ["info-attributes", "filter-config"])
def test_import_rejects_checkout_override_before_any_checkout(crlf_bundles, monkeypatch, attack):
    original, changed, checkouts = fleet._offline_git, False, []
    sentinel = crlf_bundles.workspace.parent / "filter-must-not-execute"
    def inject(args, **kwargs):
        nonlocal changed
        if "checkout" in args:
            checkouts.append(args)
        result = original(args, **kwargs)
        if not changed and "remote" in args and "add" in args:
            changed = True
            root = Path(args[args.index("-C") + 1])
            if attack == "info-attributes":
                (root / ".git/info/attributes").write_bytes(b"* -text\n")
            else:
                original(["-C", str(root), "config", "filter.evil.smudge",
                          "/usr/bin/touch " + str(sentinel)], timeout=15)
        return result
    monkeypatch.setattr(fleet, "_offline_git", inject)
    with pytest.raises(fleet.RebuilderError):
        materialize(crlf_bundles)
    assert changed and checkouts == [] and not sentinel.exists()
    assert not crlf_bundles.workspace.exists()


def test_frozen_ui_style_host_absolute_link_is_rejected_without_normalizing_bytes(bundles, tmp_path):
    source = tmp_path / "host-link-source"
    source.mkdir()
    git(source, "init", "--quiet", "--template=")
    (source / "chummer-core-engine").symlink_to("/docker/chummercomplete/chummer-core-engine")
    git(source, "add", ".")
    git(source, "commit", "--quiet", "-m", "host-absolute alias fixture")
    bundle = tmp_path / "host-link.bundle"
    git(source, "bundle", "create", str(bundle), "HEAD")
    name = "chummer6-ui"
    row = next(row for row in bundles.graph["repositories"] if row["name"] == name)
    row.update(commit=git(source, "rev-parse", "HEAD"), tree=git(source, "rev-parse", "HEAD^{tree}"),
               tree_sha256=hashlib.sha256(git(source, "ls-tree", "-r", "-z", "--full-tree", "HEAD", binary=True)).hexdigest())
    bind_bundle(bundles, name, bundle)
    with pytest.raises(fleet.RebuilderError):
        materialize(bundles)
    assert not bundles.workspace.exists()


def test_hostile_ambient_config_templates_and_helpers_are_not_inherited(bundles, tmp_path, monkeypatch):
    home = tmp_path / "hostile-home"
    home.mkdir()
    sentinel = tmp_path / "executed"
    template = home / "template"
    (template / "hooks").mkdir(parents=True)
    hook = template / "hooks/post-checkout"
    hook.write_text("#!/bin/sh\ntouch " + str(sentinel) + "\n")
    hook.chmod(0o700)
    config = home / ".gitconfig"
    config.write_text('[core]\n hooksPath = ' + str(template / "hooks") + '\n[init]\n templateDir = ' + str(template) +
                      '\n[credential]\n helper = !touch ' + str(sentinel) + '\n[protocol]\n allow = always\n')
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_TEMPLATE_DIR", str(template))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.hooksPath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(template / "hooks"))
    assert len(materialize(bundles)) == 8
    assert not sentinel.exists()


def test_failed_import_preserves_directory_replacing_owned_workspace(bundles, monkeypatch):
    moved = bundles.workspace.with_name("moved-owned-workspace")
    def swap(args, **kwargs):
        bundles.workspace.rename(moved)
        bundles.workspace.mkdir()
        (bundles.workspace / "sentinel").write_text("keep replacement")
        raise subprocess.TimeoutExpired(["private-password"], 3, output=b"private-password")
    monkeypatch.setattr(fleet, "_offline_git", swap)
    with pytest.raises(fleet.RebuilderError) as failure:
        materialize(bundles)
    assert str(failure.value) == "offline source bundle materialization failed"
    assert (bundles.workspace / "sentinel").read_text() == "keep replacement"


def test_git_output_limit_and_timeout_are_content_free_and_processes_are_reaped(monkeypatch):
    original, processes = subprocess.Popen, []
    def child(command, **kwargs):
        # Only this subprocess-boundary test substitutes a local Python child;
        # import/verify/unbundle/fsck fixture tests above execute actual Git.
        process = original(["/usr/bin/python3", "-c", "print('private-password' * 1000)"], **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(fleet, "OFFLINE_GIT_OUTPUT_BYTES", 128)
    monkeypatch.setattr(subprocess, "Popen", child)
    with pytest.raises(fleet.RebuilderError, match="output limit") as failure:
        fleet._offline_git(["version"], timeout=1)
    assert "private-password" not in str(failure.value) and processes[0].poll() is not None
    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(["private-password"], 1, output=b"private-password")
    monkeypatch.setattr(subprocess, "Popen", timeout)
    with pytest.raises(fleet.RebuilderError) as failure:
        fleet._offline_git(["version"], timeout=1)
    assert str(failure.value) == "offline Git operation failed"


def test_git_deadline_stops_descendants_without_touching_unrelated_process(tmp_path, monkeypatch):
    original = subprocess.Popen
    child_file = tmp_path / "child-pid"
    program = ("import os,time\nfrom pathlib import Path\n"
               "child = os.fork()\nif child == 0:\n"
               f" Path({str(child_file)!r}).write_text(str(os.getpid()))\n"
               " time.sleep(30)\nelse:\n print('private-password', flush=True)\n time.sleep(30)\n")
    processes = []
    def spawn(command, **kwargs):
        process = original(["/usr/bin/python3", "-c", program], **kwargs)
        processes.append(process)
        return process
    unrelated = original(["/usr/bin/python3", "-c", "import time; time.sleep(30)"], start_new_session=True)
    try:
        monkeypatch.setattr(subprocess, "Popen", spawn)
        with pytest.raises(fleet.RebuilderError, match="time limit") as failure:
            fleet._offline_git(["version"], timeout=1)
        assert "private-password" not in str(failure.value)
        assert processes[0].poll() is not None and unrelated.poll() is None
        child = Path("/proc") / child_file.read_text().strip() / "stat"
        # A killed orphan may briefly await init's reap; it must not execute.
        if child.exists():
            assert child.read_text().split(")", 1)[1].split()[0] == "Z"
    finally:
        unrelated.kill()
        unrelated.wait(timeout=5)


def test_successful_git_group_cleanup_precedes_reaping_leader_pid(monkeypatch):
    spawn, killpg, events = subprocess.Popen, os.killpg, []
    def process(command, **kwargs):
        value = spawn(command, **kwargs)
        wait = value.wait
        def reap(*args, **kwargs):
            events.append("reap")
            return wait(*args, **kwargs)
        monkeypatch.setattr(value, "wait", reap)
        return value
    def signal_group(pid, signal):
        events.append("signal-owned-group")
        return killpg(pid, signal)
    monkeypatch.setattr(subprocess, "Popen", process)
    monkeypatch.setattr(os, "killpg", signal_group)
    assert fleet._offline_git(["version"], timeout=5).startswith("git version ")
    assert events == ["signal-owned-group", "reap"]


def test_cleanup_descriptor_preserves_mid_cleanup_pathname_replacement(tmp_path, monkeypatch):
    root = tmp_path / "owned"
    root.mkdir()
    (root / "owned-file").write_text("remove")
    identity = root.stat()
    original = os.listdir
    moved = tmp_path / "moved-owned"
    def swap(descriptor):
        root.rename(moved)
        root.mkdir()
        (root / "sentinel").write_text("keep")
        return original(descriptor)
    monkeypatch.setattr(os, "listdir", swap)
    fleet._remove_owned_directory(root, identity)
    monkeypatch.setattr(os, "listdir", original)
    assert (root / "sentinel").read_text() == "keep"
    assert list(moved.iterdir()) == []


def test_cleanup_failure_does_not_echo_exception_content(tmp_path, monkeypatch):
    root = tmp_path / "owned"
    root.mkdir()
    identity = root.stat()
    def denied(*args, **kwargs):
        raise OSError("private-password")
    monkeypatch.setattr(os, "open", denied)
    with pytest.raises(fleet.RebuilderError) as failure:
        fleet._remove_owned_directory(root, identity)
    assert str(failure.value) == "offline source cleanup failed"


def test_ordinary_checkout_link_owner_mode_does_not_change_protected_default(bundles, monkeypatch):
    roots = materialize(bundles)
    root = roots["chummer-android"]
    original = Path.stat
    def builder_metadata(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        fields = {key: getattr(value, key) for key in dir(value) if key.startswith("st_")}
        fields["st_uid"] = 12345
        return SimpleNamespace(**fields)
    monkeypatch.setattr(Path, "stat", builder_metadata)
    fleet._resolve_tree_link(root, root / "relative-link", "package-source.txt", "fixture", owner_uid=12345)
    with pytest.raises(fleet.RebuilderError, match="non-root-owned"):
        fleet._resolve_tree_link(root, root / "relative-link", "package-source.txt", "fixture")


@pytest.fixture
def snapshot_events(bundles, monkeypatch):
    """Observe real tiny-file custody; no fake Git, file identities or content."""
    trace = SimpleNamespace(stage=None, snapshots={}, hashes=[], headers=[], events=[],
                            descriptors={}, live={}, retirements=[], processes=[])
    mkdtemp, opening, closing, unlink = fleet.tempfile.mkdtemp, os.open, os.close, os.unlink
    copying, header, offline_git = fleet._copy_offline_input, fleet._offline_bundle_header, fleet._offline_git
    def stage(*args, **kwargs):
        result = mkdtemp(*args, **kwargs)
        if kwargs.get("prefix") == ".offline-source-": trace.stage = Path(result)
        return result
    def open_file(*args, **kwargs):
        fd = opening(*args, **kwargs)
        path = Path(os.readlink("/proc/self/fd/" + str(fd)))
        if path == bundles.workspace.parent or (trace.stage is not None and
                                                (path == trace.stage or path.parent == trace.stage)):
            info = os.fstat(fd)
            record = (path, info.st_dev, info.st_ino)
            trace.descriptors[(fd, info.st_dev, info.st_ino)] = path
            trace.live[fd] = record
            trace.events.append(("open", path.name))
        return fd
    def close_file(fd):
        record = trace.live.get(fd)
        closing(fd)
        if record is not None:
            trace.live.pop(fd)
            trace.events.append(("close", record[0].name))
    def remove(path, *args, **kwargs):
        parent = kwargs.get("dir_fd")
        resolved = Path(path)
        if not resolved.is_absolute() and parent is not None:
            resolved = Path(os.readlink("/proc/self/fd/" + str(parent))) / resolved
        unlink(path, *args, **kwargs)
        if trace.stage is not None and resolved.parent == trace.stage:
            trace.events.append(("unlink", resolved.name))
            trace.retirements.append(resolved.name)
    def copy(source, metadata, output, limit):
        actual = copying(source, metadata, output, limit)
        if source.parent == bundles.inputs:
            trace.hashes.append(source.stem)
            trace.events.append(("hash", source.stem))
        return actual
    def check_header(path):
        result = header(path)
        trace.snapshots[path.stem] = path
        trace.headers.append(path.stem)
        trace.events.append(("header", path.stem))
        return result
    def command(args, **kwargs):
        assert set(trace.hashes) == set(trace.headers) == set(fleet.REPOSITORIES)
        trace.processes.append(list(args))
        result = offline_git(args, **kwargs)
        if "fsck" in args:
            assert "--full" in args and "--strict" in args and "--no-reflogs" in args
            root = Path(args[args.index("-C") + 1])
            name = next(name for name, (_, relative, _) in fleet.REPOSITORIES.items()
                        if root == bundles.workspace / relative)
            trace.events.append(("fsck", name))
        return result
    monkeypatch.setattr(fleet.tempfile, "mkdtemp", stage)
    monkeypatch.setattr(os, "open", open_file); monkeypatch.setattr(os, "close", close_file)
    monkeypatch.setattr(os, "unlink", remove)
    monkeypatch.setattr(fleet, "_copy_offline_input", copy)
    monkeypatch.setattr(fleet, "_offline_bundle_header", check_header)
    monkeypatch.setattr(fleet, "_offline_git", command)
    yield trace
    assert trace.live == {}
    # Also inspect actual descriptor identities, so a missed observer event or
    # reused descriptor number cannot hide an open, already-unlinked snapshot.
    for (fd, device, inode), _path in trace.descriptors.items():
        try: info = os.fstat(fd)
        except OSError: continue
        assert (info.st_dev, info.st_ino) != (device, inode)


def assert_materialization_error(case):
    with pytest.raises(fleet.RebuilderError) as failure:
        materialize(case)
    assert str(failure.value) == "offline source bundle materialization failed"


@pytest.mark.parametrize("different_sizes", [False, True])
def test_snapshot_capacity_order_and_early_retirement_use_real_git(bundles, snapshot_events, monkeypatch, different_sizes):
    trace = snapshot_events
    names = list(fleet.REPOSITORIES)
    if different_sizes:
        header, pack = bundles.source.path.read_bytes().split(b"\n\n", 1)
        # Valid extra ref advertisements change transport size, not the graph.
        for name, padding in zip(names, [0, 3, 1, 3, 0, 2, 1, 2]):
            path = Path(bundles.rows[name]["path"])
            extra = b"" if not padding else ("\n" + bundles.source.commit + " refs/heads/pad-" + "x" * padding).encode()
            path.write_bytes(header + extra + b"\n\n" + pack)
            bind_bundle(bundles, name, path)
    bundles.rows = dict(reversed(list(bundles.rows.items())))
    write_manifest(bundles)
    expected = sorted(names, key=lambda name: (-bundles.rows[name]["size_bytes"], names.index(name)))
    originals = {Path(row["path"]): (Path(row["path"]).read_bytes(), fleet._file_identity(Path(row["path"]).stat()))
                 for row in bundles.rows.values()}
    original, imported, checked_out = fleet._offline_git, [], []
    def observe(args, **kwargs):
        if "unbundle" in args:
            name = Path(args[-1]).stem
            assert trace.snapshots[name].exists()
            imported.append(name)
        if "checkout" in args:
            root = Path(args[args.index("-C") + 1])
            name = next(name for name, (_, relative, _) in fleet.REPOSITORIES.items()
                        if root == bundles.workspace / relative)
            path = trace.snapshots[name]
            assert not path.exists()
            assert not any(record[0] == path for record in trace.live.values())
            fsck = trace.events.index(("fsck", name))
            assert fsck < trace.events.index(("unlink", path.name))
            assert fsck < trace.events.index(("close", path.name))
            checked_out.append(name)
            assert {path.stem for path in trace.stage.iterdir()} == set(expected) - set(checked_out)
        return original(args, **kwargs)
    monkeypatch.setattr(fleet, "_offline_git", observe)
    roots = materialize(bundles)
    assert imported == checked_out == expected
    assert len(trace.hashes) == len(trace.headers) == len(trace.retirements) == 8
    assert set(roots) == set(names) and not trace.stage.exists()
    for name, root in roots.items():
        assert (root / "runtime.txt").read_bytes() == b"runtime source\n"
        assert git(root, "rev-parse", "HEAD") == bundles.source.commit
    for path, (raw, identity) in originals.items():
        assert path.read_bytes() == raw and fleet._file_identity(path.stat()) == identity


@pytest.mark.parametrize("failure_phase", ["verify", "unbundle", "fsck"])
def test_failed_git_never_retires_snapshot_before_strict_fsck_success(bundles, snapshot_events, monkeypatch, failure_phase):
    trace = snapshot_events; original = fleet._offline_git; failed = []
    def fail(args, **kwargs):
        result = original(args, **kwargs)
        if failure_phase in args and not failed:
            assert len(list(trace.stage.iterdir())) == 8 and trace.retirements == []
            assert len([row for row in trace.live.values() if row[0].suffix == ".bundle"]) == 8
            failed.append(True)
            raise OSError("SYNTHETIC-PRIVATE-GIT-DETAIL")
        return result
    monkeypatch.setattr(fleet, "_offline_git", fail)
    assert_materialization_error(bundles)
    assert failed == [True] and not any("checkout" in args for args in trace.processes)
    assert not bundles.workspace.exists() and not trace.stage.exists()


@pytest.mark.parametrize("attack", ["symlink", "hardlink", "replacement", "mutation"])
def test_private_snapshot_tampering_is_rejected_without_erasing_unknown_entries(bundles, snapshot_events, monkeypatch, attack):
    trace = snapshot_events; original = fleet._offline_git; retained = []; fired = []
    def mutate(args, **kwargs):
        result = original(args, **kwargs)
        if not fired:
            fired.append(True)
            path = trace.snapshots[next(iter(fleet.REPOSITORIES))]
            other = path.with_name("unknown-preserved-entry")
            if attack in {"symlink", "replacement"}:
                path.rename(other)
                if attack == "symlink": path.symlink_to(other)
                else: path.write_bytes(other.read_bytes()); path.chmod(0o400)
                retained.extend((path, other))
            elif attack == "hardlink":
                os.link(path, other); retained.extend((path, other))
            else:
                path.chmod(0o600); path.write_bytes(b"SYNTHETIC-MUTATED-SNAPSHOT")
        return result
    monkeypatch.setattr(fleet, "_offline_git", mutate)
    assert_materialization_error(bundles)
    assert fired == [True] and not any("unbundle" in args for args in trace.processes)
    for path in retained: assert os.path.lexists(path)
    assert not bundles.workspace.exists()


@pytest.mark.parametrize("attack", ["stage-replaced", "unknown-child"])
def test_snapshot_cleanup_preserves_unowned_stage_entries(bundles, snapshot_events, monkeypatch, attack):
    trace = snapshot_events; original = fleet._offline_git; preserved = []
    def fail(args, **kwargs):
        result = original(args, **kwargs)
        if not preserved:
            if attack == "stage-replaced":
                trace.stage.rename(trace.stage.with_name("retained-owned-stage"))
                trace.stage.mkdir(mode=0o700)
            sentinel = trace.stage / "unknown-child"
            sentinel.write_bytes(b"SYNTHETIC-KEEP-UNKNOWN")
            preserved.append(sentinel)
            raise OSError("SYNTHETIC-PRIVATE-CLEANUP-DETAIL")
        return result
    monkeypatch.setattr(fleet, "_offline_git", fail)
    assert_materialization_error(bundles)
    assert preserved[0].read_bytes() == b"SYNTHETIC-KEEP-UNKNOWN"
    assert not bundles.workspace.exists()


@pytest.mark.parametrize("operation", ["unlink", "close"])
def test_snapshot_retirement_failure_closes_remaining_descriptors_and_is_sanitized(bundles, snapshot_events, monkeypatch, operation):
    trace = snapshot_events; actual_unlink, actual_close = os.unlink, os.close; failed = []
    def unlink(path, *args, **kwargs):
        if not failed and Path(path).suffix == ".bundle" and any(event[0] == "fsck" for event in trace.events):
            failed.append(True)
            raise OSError("SYNTHETIC-PRIVATE-UNLINK-DETAIL")
        return actual_unlink(path, *args, **kwargs)
    def close(fd):
        record = trace.live.get(fd)
        actual_close(fd)
        if not failed and record is not None and record[0].suffix == ".bundle" and any(event[0] == "fsck" for event in trace.events):
            failed.append(True)
            raise OSError("SYNTHETIC-PRIVATE-CLOSE-DETAIL")
    monkeypatch.setattr(os, operation, unlink if operation == "unlink" else close)
    assert_materialization_error(bundles)
    assert failed == [True] and not any("checkout" in args for args in trace.processes)
    assert not bundles.workspace.exists()


def test_initial_snapshot_fstat_failure_cannot_leak_unregistered_descriptor(bundles, snapshot_events, monkeypatch):
    trace = snapshot_events; actual = os.fstat; failed = []
    def fstat(fd):
        record = trace.live.get(fd)
        if not failed and record is not None and record[0].suffix == ".bundle":
            failed.append(True)
            raise OSError("SYNTHETIC-PRIVATE-FIRST-FSTAT-DETAIL")
        return actual(fd)
    monkeypatch.setattr(os, "fstat", fstat)
    try:
        assert_materialization_error(bundles)
        assert failed == [True] and trace.processes == [] and trace.live == {}
        # The unadmitted named entry is not evidence of safe cleanup ownership.
        assert len(list(trace.stage.iterdir())) == 1
    finally:
        # A regression must fail without leaving its synthetic FD in pytest.
        for fd, (_path, device, inode) in list(trace.live.items()):
            info = actual(fd)
            if (info.st_dev, info.st_ino) == (device, inode): os.close(fd)


@pytest.mark.parametrize("phase", ["capture", "retirement", "final-parent"])
def test_snapshot_fsync_failures_remain_content_free_and_close_all_owned_fds(bundles, snapshot_events, monkeypatch, phase):
    trace = snapshot_events; actual = os.fsync; failed = []
    def fsync(fd):
        record = trace.live.get(fd)
        path = None if record is None else record[0]
        selected = (path is not None and path.suffix == ".bundle" if phase == "capture" else
                    path == trace.stage if phase == "retirement" else path == bundles.workspace.parent)
        if not failed and selected:
            failed.append(True)
            raise OSError("SYNTHETIC-PRIVATE-FSYNC-DETAIL")
        return actual(fd)
    monkeypatch.setattr(os, "fsync", fsync)
    assert_materialization_error(bundles)
    assert failed == [True] and not bundles.workspace.exists()
    if phase == "capture": assert trace.processes == []
    elif phase == "retirement": assert not any("checkout" in args for args in trace.processes)
    else: assert len([args for args in trace.processes if "checkout" in args]) == 8


def test_snapshot_parent_rebinding_preserves_foreign_parent_and_closes_descriptors(bundles, snapshot_events, monkeypatch):
    trace = snapshot_events; original = fleet._offline_git; fired = []
    parent = bundles.workspace.parent; moved = parent.with_name(parent.name + "-retained")
    originals = {Path(row["path"]).relative_to(parent): Path(row["path"]).read_bytes()
                 for row in bundles.rows.values()}
    def replace(args, **kwargs):
        result = original(args, **kwargs)
        if not fired:
            fired.append(True); parent.rename(moved); parent.mkdir(mode=0o700)
            (parent / "unknown-parent-entry").write_bytes(b"SYNTHETIC-KEEP-PARENT")
        return result
    monkeypatch.setattr(fleet, "_offline_git", replace)
    assert_materialization_error(bundles)
    assert fired == [True] and not any("unbundle" in args for args in trace.processes)
    assert (parent / "unknown-parent-entry").read_bytes() == b"SYNTHETIC-KEEP-PARENT"
    for relative, raw in originals.items(): assert (moved / relative).read_bytes() == raw
