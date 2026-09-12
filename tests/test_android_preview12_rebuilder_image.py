"""Offline recipe orchestration only; no apt, NuGet, image build or authority proof."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import stat
import struct
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "containers/android-preview12-rebuilder"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BOOT = load(RECIPE / "bootstrap.py", "rebuilder_bootstrap_test")
FIXTURES = load(ROOT / "tests/test_android_preview12_toolchain_installer.py", "rebuilder_offline_archives")


def nuspec(package_id="Microsoft.Maui.Controls", version="10.0.20", namespace=True):
    attribute = ' xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd"' if namespace else ""
    return (f'<?xml version="1.0" encoding="utf-8"?><package{attribute}><metadata>'
            f'<id>{package_id}</id><version>{version}</version><description>Offline fixture only</description>'
            '</metadata></package>').encode()


def library_zip(xml=None, extra=()):
    return FIXTURES.zip_bytes([("Microsoft.Maui.Controls.nuspec", nuspec() if xml is None else xml),
                               ("lib/net10.0/_._", b""), *extra])


def prepare(tmp_path, monkeypatch, fault=None):
    value = json.loads((RECIPE / "toolchain.lock.json").read_bytes())
    archives = {
        "dotnet-sdk": FIXTURES.tar_bytes([
            ("dotnet", "file", b"tiny nonexecuted SDK fixture"),
            ("sdk/10.0.110/fixture", "file", b"version directory"),
        ]),
        "temurin-jdk": FIXTURES.tar_bytes([("jdk/bin/java", "file", b"tiny nonexecuted JDK fixture")]),
        "android-sdk-platform": FIXTURES.zip_bytes([("platform/android.jar", b"tiny platform")]),
        "android-build-tools": FIXTURES.zip_bytes([(f"tools/{name}", b"tiny tool")
                                                   for name in ("aapt2", "apksigner", "zipalign")]),
        "bundletool": b"tiny nonexecuted jar",
    }
    urls, calls = {}, []
    for entry in value["archives"]:
        raw = archives[entry["name"]]
        algorithm = "sha512" if "sha512" in entry else "sha256"
        entry[algorithm] = hashlib.new(algorithm, raw).hexdigest()
        entry["destination"] = str(tmp_path / entry["destination"].lstrip("/"))
        urls[entry["url"]] = raw
    manifest, receipt = tmp_path / "manifest.json", tmp_path / "inventory.json"
    manifest.write_text(json.dumps(value))
    dotnet, java, android = (tmp_path / "opt" / name for name in ("dotnet", "jdk", "android-sdk"))
    monkeypatch.setattr(FIXTURES.INSTALL.urllib.request, "urlopen", lambda request, **kw: io.BytesIO(urls[request.full_url]))

    def populate():
        for name, version in BOOT.MANIFESTS.items():
            path = dotnet / "sdk-manifests/10.0.100" / name / version / "WorkloadManifest.json"
            path.parent.mkdir(parents=True)
            content = {"version": version}
            if name == "microsoft.net.sdk.maui":
                content["packs"] = {"Microsoft.Maui.Controls": {
                    "kind": "sdk" if fault == "library-kind" else "library",
                    "version": "10.0.19" if fault == "library-manifest-version" else "10.0.20",
                }}
            path.write_text(json.dumps(content))
            if name == "microsoft.net.sdk.maui" and fault == "library-duplicate-kind":
                path.write_text(path.read_text().replace('"kind": "library"', '"kind": "sdk", "kind": "library"'))
        for name, versions in BOOT.PACKS.items():
            for version in versions:
                (dotnet / "packs" / name / version).mkdir(parents=True, exist_ok=True)
        library = dotnet / "library-packs/microsoft.maui.controls.10.0.20.nupkg"
        library.parent.mkdir()
        library.write_bytes(library_zip())
        if fault == "library-missing":
            library.unlink()
        if fault == "manifest-version":
            path = dotnet / "sdk-manifests/10.0.100/microsoft.net.sdk.android/36.1.69/WorkloadManifest.json"
            path.write_text('{"version":"36.1.68"}')
        if fault == "missing-pack":
            (dotnet / "packs/Microsoft.NETCore.App.Runtime.Mono.android-arm64/10.0.12").rmdir()
        if fault == "linked-pack":
            path = dotnet / "packs/Microsoft.Maui.Sdk/10.0.20"
            path.rmdir()
            path.symlink_to(dotnet / "packs/Microsoft.Maui.Sdk/9.0.120", target_is_directory=True)
        if fault == "missing-api":
            (android / "platforms/android-36/android.jar").unlink()

    def runner(command, **kwargs):
        calls.append(command)
        assert kwargs["check"] is True and kwargs["timeout"] == 1800
        environment = kwargs["env"]
        assert environment["DOTNET_NUGET_SIGNATURE_VERIFICATION"] == "true"
        assert "PRIVATE_TEST_SENTINEL" not in environment.values()
        assert environment["PATH"] == "/usr/bin:/bin"
        if command[0] == "/usr/bin/python3":
            assert command[1:4] == ["-I", "-E", "-S"]
            monkeypatch.setattr(FIXTURES.INSTALL.sys, "argv", command[4:])
            assert FIXTURES.INSTALL.main() == 0  # Real installer, real tar/zip/file extraction.
            if fault == "extra-sdk":
                (dotnet / "sdk/10.0.111").mkdir()
            return subprocess.CompletedProcess(command, 0, "")
        if command[1:3] == ["workload", "install"]:
            assert command[3:9] == ["android", "maui-android", "--version", "10.0.112", "--source", BOOT.NUGET_SOURCE]
            config = Path(command[command.index("--configfile") + 1]).read_text()
            assert "<clear/>" in config and BOOT.NUGET_SOURCE in config
            if fault == "workload-failure":
                raise subprocess.CalledProcessError(1, command)
            populate()
            (Path(environment["NUGET_PACKAGES"]) / "microsoft.maui.controls/10.0.20").mkdir(parents=True)
            return subprocess.CompletedProcess(command, 0, "offline modeled workload install")
        if command[1:] == ["--version"]:
            output = "10.0.111" if fault == "sdk-version" else "10.0.110"
        elif command[1:] == ["workload", "--version"]:
            output = "10.0.113" if fault == "workload-version" else "10.0.112"
        else:
            assert command == [str(java / "bin/java"), "-version"]
            output = 'openjdk version "17.0.20.1"\nTemurin-17.0.20.1+1'
            if fault == "java-version":
                output = 'openjdk version "17.0.20"\nTemurin'
        return subprocess.CompletedProcess(command, 0, output)

    def execute():
        BOOT.bootstrap(ROOT / "containers/android-preview12-signer/install_toolchain.py",
                       manifest, receipt, dotnet, java, android, runner=runner)
    return execute, calls, receipt


def test_real_tiny_offline_archives_and_explicit_workload_orchestration(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "PRIVATE_TEST_SENTINEL")
    execute, calls, receipt = prepare(tmp_path, monkeypatch)
    execute()
    inventory = json.loads(receipt.read_bytes())
    assert set(inventory) == {"contract_name", "lock_sha256", "base_images", "archives"}
    assert inventory["contract_name"] == "fleet.android_preview12_installed_toolchain.v1"
    assert "sha512" in inventory["archives"][0] and "sha256" not in inventory["archives"][0]
    assert sum(command[1:3] == ["workload", "install"] for command in calls) == 1
    assert not any("restore" in command or "update" in command for command in calls)
    assert (tmp_path / "opt/dotnet/library-packs/microsoft.maui.controls.10.0.20.nupkg").is_file()
    assert not (tmp_path / "opt/dotnet/packs/Microsoft.Maui.Controls").exists()
    assert BOOT.LIBRARY_PACKS == {"Microsoft.Maui.Controls": "10.0.20"}


@pytest.mark.parametrize("fault", ["sdk-version", "extra-sdk", "workload-version", "java-version",
                                   "manifest-version", "missing-pack", "linked-pack", "missing-api", "workload-failure",
                                   "library-kind", "library-manifest-version", "library-missing", "library-duplicate-kind"])
def test_bootstrap_version_or_install_failure_cannot_report_success(tmp_path, monkeypatch, fault):
    execute, calls, _ = prepare(tmp_path, monkeypatch, fault)
    with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
        execute()
    if fault in ("sdk-version", "extra-sdk"):
        assert not any(command[1:3] == ["workload", "install"] for command in calls)


@pytest.mark.parametrize("namespace", [False, True])
def test_real_library_zip_nuspec_identity_is_verified_without_extraction(tmp_path, namespace):
    library = tmp_path / "library-packs/microsoft.maui.controls.10.0.20.nupkg"
    library.parent.mkdir()
    library.write_bytes(library_zip(nuspec(namespace=namespace)))
    before = library.read_bytes()
    BOOT.verify_library_pack(tmp_path, "Microsoft.Maui.Controls", "10.0.20")
    assert library.read_bytes() == before
    assert list(library.parent.iterdir()) == [library]


@pytest.mark.parametrize("fault", ["id", "version", "duplicate-id", "duplicate-version", "doctype", "entity",
                                   "extra-nuspec", "nested-nuspec", "duplicate-entry", "escape", "absolute",
                                   "backslash", "link-entry", "file-parent", "corrupt-zip", "corrupt-crc",
                                   "symlink", "linked-parent", "missing", "oversized-nuspec"])
def test_library_archive_cannot_pass_by_filename_alone(tmp_path, fault):
    library = tmp_path / "library-packs/microsoft.maui.controls.10.0.20.nupkg"
    library.parent.mkdir()
    xml, extra = nuspec(), []
    if fault == "id":
        xml = nuspec(package_id="Microsoft.Maui.Other")
    elif fault == "version":
        xml = nuspec(version="10.0.19")
    elif fault == "duplicate-id":
        xml = xml.replace(b"</id>", b"</id><id>Microsoft.Maui.Controls</id>")
    elif fault == "duplicate-version":
        xml = xml.replace(b"</version>", b"</version><version>10.0.20</version>")
    elif fault in ("doctype", "entity"):
        xml = b'<!DOCTYPE package [<!ENTITY value "unsafe">]>' + xml[xml.index(b"<package"):]
    elif fault == "oversized-nuspec":
        xml += b" " * (256 * 1024)
    elif fault in ("extra-nuspec", "duplicate-entry", "escape", "absolute", "backslash", "file-parent"):
        extra = {
            "extra-nuspec": [("Other.nuspec", nuspec())],
            "duplicate-entry": [("LIB/net10.0/_._", b"shadow")],
            "escape": [("../escape", b"unsafe")], "absolute": [("/escape", b"unsafe")],
            "backslash": [("folder\\escape", b"unsafe")], "file-parent": [("lib", b"not a directory")],
        }[fault]
    raw = library_zip(xml, extra)
    if fault == "nested-nuspec":
        raw = FIXTURES.zip_bytes([("nested/Microsoft.Maui.Controls.nuspec", xml)])
    elif fault == "corrupt-zip":
        raw = b"not a ZIP"
    elif fault == "corrupt-crc":
        assert b"Offline fixture only" in raw
        raw = raw.replace(b"Offline fixture only", b"Altered fixture only", 1)
    elif fault == "link-entry":
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("Microsoft.Maui.Controls.nuspec", xml)
            entry = zipfile.ZipInfo("link")
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(entry, "../outside")
        raw = output.getvalue()
    library.write_bytes(raw)
    if fault == "missing":
        library.unlink()
    elif fault == "symlink":
        other = tmp_path / "same-package.nupkg"
        library.rename(other)
        library.symlink_to(other)
    elif fault == "linked-parent":
        directory = tmp_path / "elsewhere"
        library.parent.rename(directory)
        library.parent.symlink_to(directory, target_is_directory=True)
    with pytest.raises(RuntimeError):
        BOOT.verify_library_pack(tmp_path, "Microsoft.Maui.Controls", "10.0.20")


@pytest.mark.parametrize("fault", ["excessive-count", "lying-count", "oversized-archive"])
def test_library_zip_bounds_are_checked_before_zipfile_allocations(tmp_path, monkeypatch, fault):
    path = tmp_path / "library-packs/microsoft.maui.controls.10.0.20.nupkg"
    path.parent.mkdir()
    raw = bytearray(library_zip())
    if fault != "oversized-archive":
        offset = raw.rfind(b"PK\x05\x06")
        count = 4097 if fault == "excessive-count" else 4096
        struct.pack_into("<2H", raw, offset + 8, count, count)
    path.write_bytes(raw)
    if fault == "oversized-archive":
        with path.open("r+b") as stream:
            stream.truncate(64 * 1024 * 1024 + 1)  # Sparse, no large allocation.
    monkeypatch.setattr(BOOT.zipfile, "ZipFile", lambda *args, **kw: pytest.fail("unbounded ZIP constructor"))
    with pytest.raises(RuntimeError):
        BOOT.verify_library_pack(tmp_path, "Microsoft.Maui.Controls", "10.0.20")


def test_missing_pack_reports_exact_path_and_non_authoritative_directory_inventory(tmp_path, monkeypatch, capsys):
    execute, _, _ = prepare(tmp_path, monkeypatch, "missing-pack")
    with pytest.raises(RuntimeError, match=r"Microsoft.NETCore.App.Runtime.Mono.android-arm64/10\.0\.12"):
        execute()
    output = capsys.readouterr().err
    inventory, nuget = [json.loads(line) for line in output.splitlines()]
    assert inventory["diagnostic"] == "non_authoritative_installed_pack_directories"
    row = next(row for row in inventory["packs"] if row["name"] == "Microsoft.NETCore.App.Runtime.Mono.android-arm64")
    assert row["versions"] == ["9.0.20"]
    assert inventory["truncated"] is False
    assert nuget["diagnostic"] == "non_authoritative_private_nuget_directories"
    assert nuget["packs"] == [{"name": "microsoft.maui.controls", "versions": ["10.0.20"]}]
    assert len(output) < 34 * 1024


def test_pack_diagnostic_is_bounded_and_does_not_read_files_or_follow_links(tmp_path, monkeypatch):
    packs = tmp_path / "packs"
    packs.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "not-a-pack").mkdir()
    (packs / "linked-package").symlink_to(outside, target_is_directory=True)
    (packs / "ignored-file").write_bytes(b"DO-NOT-READ-FILE-CONTENTS")
    for index in range(260):
        (packs / f"Pack{index:03}").mkdir()
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("diagnostic read file contents"))
    monkeypatch.setattr(Path, "read_text", lambda self, **kw: pytest.fail("diagnostic read file contents"))
    inventory = BOOT._installed_pack_diagnostic(packs)
    assert inventory["truncated"] is True
    assert len(inventory["packs"]) <= 256
    assert all(row["name"] not in ("linked-package", "ignored-file", "not-a-pack") for row in inventory["packs"])
    assert len(json.dumps(inventory)) <= 17 * 1024


def test_noncanonical_pack_reports_exact_path(tmp_path):
    directory = tmp_path / "real"
    directory.mkdir()
    path = tmp_path / "linked"
    path.symlink_to(directory, target_is_directory=True)
    with pytest.raises(RuntimeError, match=f"directory: {path}"):
        BOOT.require_directory(path)


def test_recipe_binds_exact_archive_metadata_and_keeps_old_image_untouched():
    value = json.loads((RECIPE / "toolchain.lock.json").read_bytes())
    archives = {row["name"]: row for row in value["archives"]}
    assert archives["dotnet-sdk"]["version"] == "10.0.110"
    assert archives["dotnet-sdk"]["strip_components"] == 0
    assert archives["dotnet-sdk"]["sha512"] == "05e5a22cef9f41748bbd63602a6b595322b91214d03b9a00da43d698501648136f1fb2a4fe6ce6ad9c684aa1698376821c8753af0c42e336b8f753f6c078fb28"
    assert archives["temurin-jdk"]["version"] == "17.0.20.1+1"
    assert archives["temurin-jdk"]["sha256"] == "3808d1d15e3ec6bd5b84057fb5d84c33d8a1536a258146bcea2e603fc726e08e"
    assert archives["android-sdk-platform"]["sha256"] == "37607369a28c5b640b3a7998868d45898ebcb777565a0e85f9acf36f29631d2e"
    assert archives["android-build-tools"]["sha256"] == "5d9ac77fb6ff43d9da518a337b4fcf8f9097113df531d99ccefe80ef7ce8250b"
    assert archives["bundletool"]["sha256"] == "a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29"
    docker = (RECIPE / "Dockerfile").read_text()
    base = value["base_images"][0]
    assert f'FROM {base["reference"]}@{base["digest"]}' in docker
    assert base["digest"] == "sha256:e6508f4bfffe893467e70c54b68a2d28b93fc5d1a69f3de0a3ce69d131ca274e"
    assert 'ENTRYPOINT ["/usr/bin/python3", "-I", "-E", "-S", "/opt/fleet-rebuilder/android_preview12_external_rebuilder.py"]' in docker
    assert 'CMD ["--help"]' in docker
    assert "android_preview12_signer.py" not in docker
    assert "installed_closure_receipt_sha256" not in docker
    assert "8.0.424" in (ROOT / "containers/android-preview12-signer/Dockerfile").read_text()
    assert BOOT.MANIFESTS == {"microsoft.net.sdk.android": "36.1.69", "microsoft.net.sdk.maui": "10.0.20",
                              "microsoft.net.workload.mono.toolchain.current": "10.0.112",
                              "microsoft.net.workload.mono.toolchain.net9": "10.0.112"}


@pytest.mark.parametrize("fault", [None, "corrupt", "missing", "extra"])
def test_actual_apt_recipe_block_checks_downloaded_bytes_before_install(tmp_path, fault):
    # Execute the actual RUN block with an offline apt stand-in. This does not
    # model successful OpenPGP verification or claim an actual apt transaction.
    docker = (RECIPE / "Dockerfile").read_text()
    block = docker.split("# BEGIN SNAPSHOT BOOTSTRAP\n", 1)[1].split("# END SNAPSHOT BOOTSTRAP", 1)[0]
    block = block.removeprefix("RUN ")
    block = block.replace("/opt/fleet-rebuilder", str(tmp_path))
    block = block.replace("/tmp/fleet-rebuilder-apt.", str(tmp_path / "lists."))
    source = (RECIPE / "ubuntu.sources").read_text()
    (tmp_path / "ubuntu.sources").write_text(source)
    assert "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg" in source
    assert "https://snapshot.ubuntu.com/ubuntu/20260910T000000Z/" in source
    assert "Check-Valid-Until: no" not in source
    names = [line.split()[1] for line in (RECIPE / "ubuntu-InRelease.SHA256SUMS").read_text().splitlines()]
    assert len(names) == 3
    payloads = {name: f"unsigned offline test fixture {name}".encode() for name in names}
    (tmp_path / "ubuntu-InRelease.SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(raw).hexdigest()}  {name}\n" for name, raw in payloads.items()))
    configuration = tmp_path / "fixture.json"
    configuration.write_text(json.dumps({"directory": str(tmp_path), "fault": fault,
                                         "payloads": {key: value.decode() for key, value in payloads.items()}}))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    standin = bin_dir / "apt-get"
    standin.write_text("#!/usr/bin/python3\n" + r'''
import json, pathlib, sys
config=json.loads(pathlib.Path(sys.argv[0]).parent.parent.joinpath("fixture.json").read_text())
args=sys.argv[1:]; directory=pathlib.Path(config["directory"])
with (directory/"apt-calls.jsonl").open("a") as out: out.write(json.dumps(args)+"\n")
assert "Dir::Etc::sourceparts=-" in args
assert "Dir::Etc::sourcelist="+str(directory/"ubuntu.sources") in args
assert "Acquire::Check-Valid-Until=true" in args
assert "Acquire::AllowInsecureRepositories=false" in args
assert "APT::Get::AllowUnauthenticated=false" in args
lists=pathlib.Path(next(arg.split("=",1)[1] for arg in args if arg.startswith("Dir::State::lists=")))
assert lists.is_dir() and lists.stat().st_mode & 0o077 == 0
if "update" in args:
    assert not list(lists.iterdir())
    for index,(name,raw) in enumerate(config["payloads"].items()):
        if config["fault"]=="missing" and index==0: continue
        (lists/name).write_text("corrupt" if config["fault"]=="corrupt" and index==0 else raw)
    if config["fault"]=="extra": (lists/"unexpected_InRelease").write_text("unadmitted extra fixture")
''')
    standin.chmod(0o755)
    dpkg = bin_dir / "dpkg-query"
    dpkg.write_text("#!/bin/sh\nprintf 'offline-fixture-only\\n'\n")
    dpkg.chmod(0o755)
    result = subprocess.run(["/bin/sh", "-c", block], env={"PATH": f"{bin_dir}:/usr/bin:/bin"},
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
    calls = [json.loads(line) for line in (tmp_path / "apt-calls.jsonl").read_text().splitlines()]
    assert result.returncode == 0 if fault is None else result.returncode != 0
    assert len(calls) == (2 if fault is None else 1)
    if fault is None:
        lists = [next(arg for arg in call if arg.startswith("Dir::State::lists=")) for call in calls]
        assert lists[0] == lists[1]
        assert calls[1][calls[1].index("--no-install-recommends") + 1:] == [
            "git", "jq", "python3", "bash", "openssl", "zip", "unzip", "coreutils", "findutils", "libatomic1", "ca-certificates"]


def test_snapshot_hashes_are_the_exact_reviewed_envelopes():
    hashes = [line.split()[0] for line in (RECIPE / "ubuntu-InRelease.SHA256SUMS").read_text().splitlines()]
    assert hashes == ["cdb2f31d809f589719a53c6ad15f255b27569c4059542ada282aaa21b8e164b0",
                      "2dd519624709e3bc674345fa9ac92f368c160da902f43d978735f102db5d72cf",
                      "78520ae2ab16e7c76d6fa4ca1edf38db9203aaa8b632575aef65444e3bb7f69a"]


def test_dockerfile_specific_context_is_exact_deny_by_default_and_covers_copy():
    # Static declared-context contract, not an emulation of Docker's matcher or
    # evidence of a controlled image build. No checkout credentials are read.
    patterns = [line for line in (RECIPE / "Dockerfile.dockerignore").read_text().splitlines()
                if line and not line.startswith("#")]
    assert patterns == [
        "**", "!containers/", "containers/**",
        "!containers/android-preview12-rebuilder/", "containers/android-preview12-rebuilder/**",
        "!containers/android-preview12-rebuilder/Dockerfile",
        "!containers/android-preview12-rebuilder/Dockerfile.dockerignore",
        "!containers/android-preview12-rebuilder/ubuntu.sources",
        "!containers/android-preview12-rebuilder/ubuntu-InRelease.SHA256SUMS",
        "!containers/android-preview12-rebuilder/toolchain.lock.json",
        "!containers/android-preview12-rebuilder/bootstrap.py",
        "!containers/android-preview12-signer/", "containers/android-preview12-signer/**",
        "!containers/android-preview12-signer/install_toolchain.py",
        "!scripts/", "scripts/**", "!scripts/android_preview12_external_rebuilder.py",
    ]
    allowed_files = {line[1:] for line in patterns if line.startswith("!") and not line.endswith("/")}
    copied_files = set()
    for line in (RECIPE / "Dockerfile").read_text().splitlines():
        if line.startswith("COPY "):
            command, source, destination = line.split()
            assert command == "COPY" and destination.startswith("/opt/fleet-rebuilder/")
            assert source in allowed_files
            assert (ROOT / source).is_file() and not (ROOT / source).is_symlink()
            copied_files.add(source)
        assert not line.startswith("ADD ")
    assert allowed_files == copied_files | {
        "containers/android-preview12-rebuilder/Dockerfile",
        "containers/android-preview12-rebuilder/Dockerfile.dockerignore",
    }
    assert allowed_files.isdisjoint({
        ".env", ".git/config", ".cache/credential", "scripts/.env", "scripts/__pycache__/cached.pyc",
        "containers/android-preview12-rebuilder/.env", "containers/android-preview12-signer/private.pem",
        "config/release/android-preview12-external-rebuilder.json",
    })
