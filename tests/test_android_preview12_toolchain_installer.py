"""Offline archive tests only: no image, workload, or installed-tree authority."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import tarfile
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "preview12_toolchain_installer", ROOT / "containers/android-preview12-signer/install_toolchain.py"
)
assert SPEC and SPEC.loader
INSTALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALL)


def tar_bytes(members):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, kind, value in members:
            member = tarfile.TarInfo(name)
            member.mode = 0o755 if name.endswith("dotnet") else 0o644
            if kind == "file":
                member.size = len(value)
                archive.addfile(member, io.BytesIO(value))
                continue
            member.type = {"symlink": tarfile.SYMTYPE, "hardlink": tarfile.LNKTYPE,
                           "directory": tarfile.DIRTYPE, "fifo": tarfile.FIFOTYPE}[kind]
            member.linkname = value
            archive.addfile(member)
    return output.getvalue()


def zip_bytes(members):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in members:
            archive.writestr(name, data)
    return output.getvalue()


def entry(tmp_path, name="sdk", *, algorithm="sha256", archive_format="tar.gz", version="10.0.110", data=None):
    if data is None:
        data = tar_bytes([("sdk/dotnet", "file", b"tiny executable")])
    value = {
        "name": name, "version": version, "url": f"https://archives.example.test/{name}",
        "format": archive_format, "destination": str(tmp_path / "installed" / name),
        "strip_components": 0 if archive_format == "file" else 1,
        algorithm: hashlib.new(algorithm, data).hexdigest(),
    }
    return value, data


def manifest(entries):
    return {
        "contract_name": "fleet.android_preview12_toolchain.v1", "contract_version": 1,
        "platform": "linux/amd64", "base_images": [{
            "name": "synthetic-test-base", "version": "test", "reference": "example.test/base:test",
            "digest": "sha256:" + "a" * 64,
        }], "archives": entries,
    }


def invoke(tmp_path, monkeypatch, value, archives):
    lock = tmp_path / "lock.json"
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    lock.write_bytes(raw)
    receipt = tmp_path / "inventory.json"
    requests = []
    def download(request, timeout):
        requests.append(request.full_url)
        assert timeout == 120
        return io.BytesIO(archives[request.full_url])
    monkeypatch.setattr(INSTALL.urllib.request, "urlopen", download)
    monkeypatch.setattr(INSTALL.sys, "argv", ["installer", str(lock), str(receipt)])
    assert INSTALL.main() == 0
    return json.loads(receipt.read_bytes()), requests, raw


@pytest.mark.parametrize("version,algorithm", [("35.0.0", "sha256"), ("36.0.0", "sha512")])
def test_real_archive_install_preserves_selected_digest_and_version_paths(tmp_path, monkeypatch, version, algorithm):
    sdk, sdk_bytes = entry(tmp_path, algorithm=algorithm)
    tools_bytes = zip_bytes([(f"android-{version}/{name}", name.encode())
                             for name in ("aapt2", "apksigner", "zipalign")])
    tools, _ = entry(tmp_path, "android-build-tools", archive_format="zip", version=version,
                     data=tools_bytes)
    tools["destination"] = str(tmp_path / "installed" / "android-sdk" / "build-tools" / version)
    standalone, file_bytes = entry(tmp_path, "bundletool", archive_format="file", data=b"tiny jar")
    entries = [sdk, tools, standalone]
    value = manifest(entries)
    receipt, requests, raw = invoke(tmp_path, monkeypatch, value, {
        sdk["url"]: sdk_bytes, tools["url"]: tools_bytes, standalone["url"]: file_bytes,
    })
    expected = {
        "contract_name": "fleet.android_preview12_installed_toolchain.v1",
        "lock_sha256": hashlib.sha256(raw).hexdigest(), "base_images": value["base_images"],
        "archives": [{key: item[key] for key in ("name", "version", "url", "sha256", "sha512") if key in item}
                     for item in entries],
    }
    assert receipt == expected  # Deliberately no invented observed-tree/security fields.
    assert requests == [item["url"] for item in entries]
    assert (Path(sdk["destination"]) / "dotnet").read_bytes() == b"tiny executable"
    for name in ("aapt2", "apksigner", "zipalign"):
        path = Path(tools["destination"]) / name
        assert path.read_bytes() == name.encode()
        assert stat.S_IMODE(path.stat().st_mode) == 0o755
    assert Path(standalone["destination"]).read_bytes() == file_bytes


@pytest.mark.parametrize("algorithm", ["sha256", "sha512"])
def test_hash_mismatch_never_extracts_or_creates_destination(tmp_path, monkeypatch, algorithm):
    value, data = entry(tmp_path, algorithm=algorithm)
    value[algorithm] = "0" * (64 if algorithm == "sha256" else 128)
    monkeypatch.setattr(INSTALL, "_extract_tar", lambda *args: pytest.fail("extraction reached"))
    with pytest.raises(RuntimeError, match="mismatch"):
        invoke(tmp_path, monkeypatch, manifest([value]), {value["url"]: data})
    assert not (tmp_path / "installed").exists()
    assert not (tmp_path / "inventory.json").exists()


BAD_ENTRIES = [
    ("sha256", None), ("sha256", "A" * 64), ("sha256", "a" * 63),
    ("sha256", "a" * 64 + "\n"), ("sha256", True), ("sha512", "a" * 128),
    ("sha1", "a" * 40), ("md5", "a" * 32), ("name", "../escape"),
    ("name", "/escape"), ("name", "."), ("name", "a/b"), ("name", "a\\b"),
    ("name", "a\n"), ("name", False), ("version", ""), ("version", 36),
    ("url", "http://example.test/a"), ("url", "file:///etc/hosts"),
    ("url", "https://user:password@example.test/a"), ("url", "https://example.test/a?q=secret"),
    ("url", "https://example.test/a#fragment"), ("url", "https://example.test/a\n"),
    ("format", "tar"), ("format", None), ("strip_components", True),
    ("strip_components", -1), ("strip_components", "1"), ("strip_components", 33),
    ("destination", "relative"), ("destination", "/"), ("destination", "//tmp/escape"),
    ("destination", "/tmp/../escape"), ("destination", "/tmp//escape"),
    ("destination", "/tmp/escape/"), ("unknown", "value"),
]


@pytest.mark.parametrize("key,value", BAD_ENTRIES)
def test_all_entries_prevalidated_before_network_or_mutation(tmp_path, monkeypatch, key, value):
    first, _ = entry(tmp_path)
    invalid, _ = entry(tmp_path, "second")
    invalid[key] = value
    reject_without_actions(tmp_path, monkeypatch, manifest([first, invalid]))


def reject_without_actions(tmp_path, monkeypatch, value):
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps(value))
    monkeypatch.setattr(INSTALL.sys, "argv", ["installer", str(lock), str(tmp_path / "inventory.json")])
    monkeypatch.setattr(INSTALL.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network reached"))
    monkeypatch.setattr(INSTALL.tempfile, "TemporaryDirectory", lambda *a, **k: pytest.fail("scratch mutation reached"))
    with pytest.raises(RuntimeError):
        INSTALL.main()
    assert not (tmp_path / "installed").exists()
    assert not (tmp_path / "inventory.json").exists()


@pytest.mark.parametrize("kind", ["name", "url", "destination", "parent", "child", "receipt"])
def test_duplicate_or_overlapping_destinations_fail_preflight(tmp_path, monkeypatch, kind):
    first, _ = entry(tmp_path)
    second, _ = entry(tmp_path, "second")
    if kind in ("name", "url", "destination"):
        second[kind] = first[kind]
    elif kind == "parent":
        second["destination"] = str(Path(first["destination"]).parent)
    elif kind == "child":
        second["destination"] = str(Path(first["destination"]) / "child")
    else:
        second["destination"] = str(tmp_path / "inventory.json")
    reject_without_actions(tmp_path, monkeypatch, manifest([first, second]))


@pytest.mark.parametrize("kind", ["weak_only", "missing", "bad_sha512", "file_strip", "wrong_tools_path",
                                  "wrong_tools_version", "symlink_ancestor", "existing_destination"])
def test_additional_invalid_archive_shapes(tmp_path, monkeypatch, kind):
    value, _ = entry(tmp_path)
    if kind == "weak_only":
        value["sha1"] = value.pop("sha256")[:40]
    elif kind == "missing":
        value.pop("sha256")
    elif kind == "bad_sha512":
        value["sha512"] = value.pop("sha256")
    elif kind == "file_strip":
        value["format"] = "file"
    elif kind.startswith("wrong_tools"):
        value.update(name="android-build-tools", format="zip", version="36.0.0")
        if kind == "wrong_tools_version":
            value["destination"] = str(tmp_path / "build-tools" / "35.0.0")
    elif kind == "symlink_ancestor":
        (tmp_path / "alias").symlink_to(tmp_path, target_is_directory=True)
        value["destination"] = str(tmp_path / "alias" / "target")
    else:
        (tmp_path / "already-there").mkdir()
        value["destination"] = str(tmp_path / "already-there")
    reject_without_actions(tmp_path, monkeypatch, manifest([value]))


def test_duplicate_json_checksum_field_rejected_before_actions(tmp_path, monkeypatch):
    value, _ = entry(tmp_path)
    lock = tmp_path / "lock.json"
    raw = json.dumps(manifest([value])).replace('"sha256":', '"sha256":"' + "0" * 64 + '","sha256":')
    lock.write_text(raw)
    monkeypatch.setattr(INSTALL.sys, "argv", ["installer", str(lock), str(tmp_path / "inventory.json")])
    monkeypatch.setattr(INSTALL.urllib.request, "urlopen", lambda *a, **k: pytest.fail("network reached"))
    with pytest.raises(RuntimeError, match="duplicate JSON"):
        INSTALL.main()


def test_tar_preserves_real_contained_symlinks_hardlinks_and_link_ancestors(tmp_path, monkeypatch):
    raw = tar_bytes([
        ("sdk/bin/dotnet", "file", b"real data"),
        ("sdk/dotnet", "symlink", "bin/dotnet"),
        ("sdk/alias", "symlink", "bin"),
        ("sdk/alias/extra", "file", b"through contained directory link"),
        ("sdk/bin/copy", "hardlink", "sdk/bin/dotnet"),
        ("sdk/bin/relative", "symlink", "../bin/dotnet"),
    ])
    value, _ = entry(tmp_path, algorithm="sha512", data=raw)
    invoke(tmp_path, monkeypatch, manifest([value]), {value["url"]: raw})
    root = Path(value["destination"])
    assert (root / "dotnet").is_symlink()
    assert (root / "dotnet").read_bytes() == b"real data"
    assert (root / "bin/relative").read_bytes() == b"real data"
    assert (root / "bin/extra").read_bytes() == b"through contained directory link"
    assert (root / "bin/copy").stat().st_ino == (root / "bin/dotnet").stat().st_ino


@pytest.mark.parametrize("kind", ["chained_escape", "absolute_link", "relative_escape", "cycle",
                                  "replace_link", "hardlink_escape", "fifo", "traversal", "duplicate"])
def test_hostile_tar_cannot_escape_or_emit_success_receipt(tmp_path, monkeypatch, kind):
    cases = {
        "chained_escape": [("sdk/dir", "symlink", "."), ("sdk/dir/escape", "symlink", "../outside"),
                           ("sdk/dir/escape/pwn", "file", b"bad")],
        "absolute_link": [("sdk/link", "symlink", str(tmp_path / "outside"))],
        "relative_escape": [("sdk/link", "symlink", "../outside")],
        "cycle": [("sdk/a", "symlink", "b"), ("sdk/b", "symlink", "a")],
        "replace_link": [("sdk/data", "file", b"original"), ("sdk/a", "symlink", "data"),
                         ("sdk/a", "file", b"overwrite")],
        "hardlink_escape": [("sdk/link", "hardlink", "../outside/sentinel")],
        "fifo": [("sdk/fifo", "fifo", "")],
        "traversal": [("sdk/../outside/pwn", "file", b"bad")],
        "duplicate": [("sdk/a", "file", b"one"), ("sdk/a", "file", b"two")],
    }
    outside = tmp_path / "installed" / "outside"
    outside.mkdir(parents=True)
    (outside / "sentinel").write_bytes(b"unchanged")
    raw = tar_bytes(cases[kind])
    value, _ = entry(tmp_path, data=raw)
    with pytest.raises(RuntimeError):
        invoke(tmp_path, monkeypatch, manifest([value]), {value["url"]: raw})
    assert list(outside.iterdir()) == [outside / "sentinel"]
    assert (outside / "sentinel").read_bytes() == b"unchanged"
    assert not (tmp_path / "inventory.json").exists()


@pytest.mark.parametrize("kind", ["symlink", "traversal", "duplicate", "fifo"])
def test_hostile_zip_members_fail_closed(tmp_path, monkeypatch, kind):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        item = zipfile.ZipInfo("sdk/link" if kind != "traversal" else "sdk/../escape")
        if kind in ("symlink", "fifo"):
            item.create_system = 3
            item.external_attr = ((stat.S_IFLNK if kind == "symlink" else stat.S_IFIFO) | 0o777) << 16
        archive.writestr(item, b"../outside")
        if kind == "duplicate":
            with pytest.warns(UserWarning, match="Duplicate name"):
                archive.writestr(item, b"different")
    raw = output.getvalue()
    value, _ = entry(tmp_path, archive_format="zip", data=raw)
    with pytest.raises(RuntimeError):
        invoke(tmp_path, monkeypatch, manifest([value]), {value["url"]: raw})
    assert not (tmp_path / "inventory.json").exists()


def test_unchanged_checked_in_legacy_manifest_validates(tmp_path):
    value = json.loads((ROOT / "config/release/android-preview12-signer-toolchain.lock.json").read_bytes())
    # Only relocate installation outputs; legacy schema and checksum fields are unchanged.
    for archive in value["archives"]:
        archive["destination"] = str(tmp_path / archive["destination"].lstrip("/"))
    assert INSTALL._validate_manifest(value, tmp_path / "inventory.json") == value["archives"]


@pytest.mark.parametrize("field,value", [("contract_version", True), ("platform", "linux/arm64"),
                                       ("base_images", []), ("archives", []), ("unknown", 1)])
def test_malformed_manifest_preflight(tmp_path, monkeypatch, field, value):
    archive, _ = entry(tmp_path)
    bad = manifest([archive])
    bad[field] = value
    reject_without_actions(tmp_path, monkeypatch, bad)
