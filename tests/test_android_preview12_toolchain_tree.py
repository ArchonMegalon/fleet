"""Real filesystem links with modeled root ownership, never deployment proof."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tree(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "preview12_tree_test", ROOT / "scripts/android_preview12_external_rebuilder.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / "tree"
    root.mkdir(mode=0o755)
    overrides = {}
    real_stat, real_scandir, real_fstat = Path.stat, os.scandir, os.fstat

    def metadata(path, value):
        result = {name: getattr(value, name) for name in dir(value) if name.startswith("st_")}
        result["st_uid"] = 0  # Allows the same tests under an unprivileged runner.
        if path in root.parents:
            result["st_mode"] &= ~0o022  # Model immutable ancestry, not a trusted /tmp.
        result.update(overrides.get(path, {}))
        return SimpleNamespace(**result)

    def path_stat(path, *, follow_symlinks=True):
        return metadata(path, real_stat(path, follow_symlinks=follow_symlinks))

    class Entry:
        def __init__(self, value):
            self.value, self.path, self.name = value, value.path, value.name

        def stat(self, *, follow_symlinks=True):
            return metadata(Path(self.path), self.value.stat(follow_symlinks=follow_symlinks))

        def __getattr__(self, name):
            return getattr(self.value, name)

    def scandir(path):
        with real_scandir(path) as entries:
            return [Entry(value) for value in entries]

    monkeypatch.setattr(Path, "stat", path_stat)
    monkeypatch.setattr(module.os, "scandir", scandir)
    monkeypatch.setattr(module.os, "fstat", lambda descriptor: metadata(None, real_fstat(descriptor)))
    return module, root, overrides


def write(path, raw=b"payload", mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(mode)
    return path


def file_row(name, raw, mode=0o644):
    return f"F\0{name}\0{mode:o}\0{len(raw)}\0{hashlib.sha256(raw).hexdigest()}\n".encode()


def test_regular_tree_retains_exact_legacy_rows(tree):
    module, root, _ = tree
    write(root / "z", b"top")
    (root / "bin").mkdir(mode=0o755)
    (root / "bin").chmod(0o755)
    write(root / "bin/tool", b"executable", 0o755)
    expected = hashlib.sha256(
        b"D\0bin\0" + b"755\n"
        + file_row("z", b"top") + file_row("bin/tool", b"executable", 0o755)
    ).hexdigest()
    assert module._tree_digest(root, "fixture") == (expected, 2, 13)


def test_real_symlink_0777_is_admitted_and_digest_binds_text_and_target_bytes(tree):
    module, root, _ = tree
    write(root / "data", b"first")
    (root / "alias").symlink_to("data")
    assert stat.S_IMODE((root / "alias").lstat().st_mode) == 0o777
    expected = hashlib.sha256(b"L\0alias\0" + b"777\0data\n" + file_row("data", b"first")).hexdigest()
    first = module._tree_digest(root, "fixture")
    assert first == (expected, 1, 5)
    (root / "alias").unlink()
    (root / "alias").symlink_to("./data")
    changed_text = module._tree_digest(root, "fixture")
    assert changed_text[0] != first[0] and changed_text[1:] == first[1:]
    write(root / "data", b"other")
    changed_bytes = module._tree_digest(root, "fixture")
    assert changed_bytes[0] != changed_text[0] and changed_bytes[1:] == first[1:]


def test_real_directory_relative_parent_and_absolute_internal_links(tree):
    module, root, _ = tree
    write(root / "bin/tool", b"tool")
    (root / "bin").chmod(0o755)
    (root / "dir-alias").symlink_to("bin", target_is_directory=True)
    (root / "relative").symlink_to("dir-alias/../bin/tool")
    (root / "absolute").symlink_to(root / "bin/tool")
    (root / "bin/parent").symlink_to("../bin/tool")
    digest, count, size = module._tree_digest(root, "fixture")
    assert len(digest) == 64 and count == 1 and size == 4
    assert (root / "relative").read_bytes() == b"tool"
    assert (root / "bin/parent").read_bytes() == b"tool"


@pytest.mark.parametrize("kind", ["escape", "dangling", "cycle", "self", "out-and-back", "transient-parent",
                                  "file-slash", "file-dot", "too-many-hops"])
def test_unsafe_real_links_rejected(tree, kind):
    module, root, _ = tree
    write(root / "data")
    outside = write(root.parent / "outside-data")
    if kind == "escape":
        (root / "link").symlink_to(outside)
    elif kind == "dangling":
        (root / "link").symlink_to("missing")
    elif kind == "self":
        (root / "link").symlink_to("link")
    elif kind == "cycle":
        (root / "link").symlink_to("other")
        (root / "other").symlink_to("link")
    elif kind == "out-and-back":
        (root.parent / "outside-link").symlink_to(root / "data")
        (root / "link").symlink_to(root.parent / "outside-link")
        assert (root / "link").resolve(strict=True) == root / "data"
    elif kind == "transient-parent":
        (root / "link").symlink_to("../tree/data")
        assert (root / "link").resolve(strict=True) == root / "data"
    elif kind in ("file-slash", "file-dot"):
        (root / "link").symlink_to("data/" if kind == "file-slash" else "data/.")
        assert not (root / "link").exists()
    else:
        for index in range(67):
            (root / f"link-{index:03}").symlink_to(f"link-{index + 1:03}" if index < 66 else "data")
    with pytest.raises(module.RebuilderError):
        module._tree_digest(root, "fixture")


@pytest.mark.parametrize("kind", ["link-owner", "file-owner", "directory-owner", "file-mode", "directory-mode", "root-mode"])
def test_linked_target_ownership_and_real_permission_fences_remain(tree, kind):
    module, root, overrides = tree
    target = write(root / "bin/data")
    (root / "bin").chmod(0o755)
    link = root / "a-link"
    link.symlink_to("bin/data")
    if kind == "link-owner":
        overrides[link] = {"st_uid": 1001}
    elif kind == "file-owner":
        overrides[target] = {"st_uid": 1001}
    elif kind == "directory-owner":
        overrides[target.parent] = {"st_uid": 1001}
    elif kind == "file-mode":
        target.chmod(0o664)
    elif kind == "directory-mode":
        target.parent.chmod(0o775)
    else:
        root.chmod(0o775)
    with pytest.raises(module.RebuilderError):
        module._tree_digest(root, "fixture")


def instrument_reads(module, monkeypatch, action=None):
    original = module.os.fdopen
    sizes = []

    class Reader:
        def __init__(self, stream):
            self.stream, self.acted = stream, False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def seek(self, offset):
            assert offset == 0
            return self.stream.seek(offset)

        def read(self, amount=-1):
            assert 0 < amount <= 1024 * 1024, "unbounded/oversized toolchain read"
            sizes.append(amount)
            data = self.stream.read(amount)
            if action and not self.acted:
                self.acted = True
                action()
            return data

    def fdopen(*args, **kwargs):
        assert kwargs.get("buffering") == 0, "second pass must not reuse buffered bytes"
        return Reader(original(*args, **kwargs))
    monkeypatch.setattr(module.os, "fdopen", fdopen)
    return sizes


def test_streaming_is_bounded_and_retains_exact_file_digest(tree, monkeypatch):
    module, root, _ = tree
    raw = b"x" * (2 * 1024 * 1024 + 19)
    write(root / "data", raw)
    sizes = instrument_reads(module, monkeypatch)
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("whole-file allocation reached"))
    assert module._tree_digest(root, "fixture") == (hashlib.sha256(file_row("data", raw)).hexdigest(), 1, len(raw))
    assert len(sizes) >= 8 and max(sizes) == 1024 * 1024


@pytest.mark.parametrize("mutation", ["replace", "truncate", "same-size", "grow", "mode", "remove", "symlink"])
def test_source_drift_during_stream_fails_closed(tree, monkeypatch, mutation):
    module, root, _ = tree
    path = write(root / "data", b"before")
    replacement = root.parent / "replacement"

    def mutate():
        if mutation == "replace":
            write(replacement, b"before")
            os.replace(replacement, path)
        elif mutation in ("truncate", "same-size", "grow"):
            path.write_bytes({"truncate": b"", "same-size": b"edited", "grow": b"after-growing"}[mutation])
        elif mutation == "mode":
            path.chmod(0o666)
        elif mutation == "remove":
            path.unlink()
        else:
            write(replacement, b"before")
            path.unlink()
            path.symlink_to(replacement)

    instrument_reads(module, monkeypatch, mutate)
    with pytest.raises(module.RebuilderError, match="changed while hashing"):
        module._tree_digest(root, "fixture")


def test_persistent_same_size_rewrite_with_identical_metadata_rejected(tree, monkeypatch):
    module, root, overrides = tree
    path = write(root / "data", b"before")
    metadata = path.lstat()
    timestamp_quantum = {"st_mtime_ns": metadata.st_mtime_ns, "st_ctime_ns": metadata.st_ctime_ns}
    overrides[path] = timestamp_quantum
    actual_fstat = module.os.fstat
    monkeypatch.setattr(module.os, "fstat", lambda descriptor: SimpleNamespace(
        **{**vars(actual_fstat(descriptor)), **timestamp_quantum}))
    mutations = []

    def rewrite_once():
        path.write_bytes(b"edited")  # Real same-inode persistent write; only timestamp precision is modeled.
        mutations.append(True)
        assert module._file_identity(path.lstat()) == module._file_identity(metadata)

    instrument_reads(module, monkeypatch, rewrite_once)
    with pytest.raises(module.RebuilderError, match="changed while hashing"):
        module._tree_digest(root, "fixture")
    assert mutations == [True]
    assert path.read_bytes() == b"edited"


@pytest.mark.parametrize("phase", ["before-open", "opened-fd", "after-fd", "after-second-fd", "after-path"])
def test_uid_drift_at_each_stability_boundary_rejected(tree, monkeypatch, phase):
    module, root, overrides = tree
    path = write(root / "data")
    metadata = path.lstat()
    real_fstat = module.os.fstat
    calls = 0
    if phase == "before-open":
        overrides[path] = {"st_uid": 1001}
    elif phase in ("opened-fd", "after-fd", "after-second-fd"):
        def fstat(descriptor):
            nonlocal calls
            calls += 1
            value = real_fstat(descriptor)
            if calls == {"opened-fd": 1, "after-fd": 2, "after-second-fd": 3}[phase]:
                return SimpleNamespace(**{**vars(value), "st_uid": 1001})
            return value
        monkeypatch.setattr(module.os, "fstat", fstat)
    else:
        instrument_reads(module, monkeypatch, lambda: overrides.update({path: {"st_uid": 1001}}))
    with pytest.raises(module.RebuilderError, match="changed while hashing"):
        module._stable_file_sha256(path, metadata, "fixture")


def test_symlink_swap_between_lstat_and_open_never_reads_target(tree, monkeypatch):
    module, root, _ = tree
    path = write(root / "data")
    outside = write(root.parent / "outside", b"must not be read")
    original_open = module.os.open

    def swapped(value, flags, *args, **kwargs):
        assert flags & getattr(os, "O_NOFOLLOW", 0)
        path.unlink()
        path.symlink_to(outside)
        return original_open(value, flags, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", swapped)
    monkeypatch.setattr(module.os, "fdopen", lambda *a, **kw: pytest.fail("target stream reached"))
    with pytest.raises(module.RebuilderError, match="changed while hashing"):
        module._tree_digest(root, "fixture")
