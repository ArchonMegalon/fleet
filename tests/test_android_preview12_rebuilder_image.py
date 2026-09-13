"""Offline recipe orchestration only; no apt, NuGet, image build or authority proof."""
from __future__ import annotations

import hashlib
import errno
import importlib.util
import io
import json
import os
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


def platform_tools_zip():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, raw, mode in (("adb", b"nonexecuted adb fixture", 0o755),
                                ("fastboot", b"nonexecuted fastboot fixture", 0o755),
                                ("source.properties", b"Pkg.UserSrc=false\nPkg.Revision=37.0.1\n", 0o644)):
            entry = zipfile.ZipInfo(f"platform-tools/{name}")
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(entry, raw)
    return output.getvalue()


def bundled_metadata():
    # Synthetic XML only; other frameworks must not select net10's linker.
    return (b'<Project><PropertyGroup><NETCoreSdkVersion>10.0.111</NETCoreSdkVersion>'
            b'<BundledNETCoreAppPackageVersion>10.0.11</BundledNETCoreAppPackageVersion>'
            b'</PropertyGroup><ItemGroup><KnownILLinkPack Include="Microsoft.NET.ILLink.Tasks" '
            b'TargetFramework="net10.0" ILLinkPackVersion="10.0.11" />'
            b'<KnownILLinkPack Include="Microsoft.NET.ILLink.Tasks" TargetFramework="net9.0" '
            b'ILLinkPackVersion="9.0.20" /></ItemGroup></Project>')


def metadata_fixture(tmp_path, raw=None):
    path = tmp_path / "sdk" / BOOT.SDK_VERSION / "Microsoft.NETCoreSdk.BundledVersions.props"
    path.parent.mkdir(parents=True)
    path.write_bytes(bundled_metadata() if raw is None else raw)
    return path


def targeting_zip():
    # Real tiny ZIP/extraction, but nonexecuted reference/analyzer fixture bytes.
    namespace = "http://schemas.microsoft.com/packaging/2011/08/nuspec.xsd"
    framework = ('<FileList TargetFrameworkIdentifier=".NETCoreApp" TargetFrameworkVersion="10.0" '
                 'FrameworkName="Microsoft.NETCore.App" Name=".NET Runtime">'
                 '<File Type="Managed" Path="ref/net10.0/System.Runtime.dll" />'
                 '<File Type="Managed" Path="ref/net10.0/netstandard.dll" />'
                 '<File Type="Analyzer" Path="analyzers/dotnet/cs/Fixture.dll" /></FileList>')
    return FIXTURES.zip_bytes([
        ("Microsoft.NETCore.App.Ref.nuspec", (f'<package xmlns="{namespace}"><metadata>'
         '<id>Microsoft.NETCore.App.Ref</id><version>10.0.12</version></metadata></package>').encode()),
        ("Microsoft.NETCore.App.versions.txt", b"a" * 40 + b"\n10.0.12\n"),
        ("data/FrameworkList.xml", framework.encode()),
        ("data/PlatformManifest.txt", b"System.Runtime.dll|Microsoft.NETCore.App.Ref|10.0.0.0|10.0.12\n"),
        ("data/PackageOverrides.txt", b"Microsoft.CSharp|4.7.0\n"),
        ("ref/net10.0/System.Runtime.dll", b"nonexecuted System.Runtime reference fixture"),
        ("ref/net10.0/netstandard.dll", b"nonexecuted netstandard reference fixture"),
        ("ref/net10.0/System.Runtime.xml", b"<doc />"),
        ("analyzers/dotnet/cs/Fixture.dll", b"nonexecuted analyzer fixture"),
        ("useSharedDesignerContext.txt", b""),
    ])


def targeting_fixture(tmp_path):
    archive = tmp_path / "targeting.zip"
    archive.write_bytes(targeting_zip())
    staging = tmp_path / "staging" / BOOT.TARGETING_PACK / BOOT.TARGETING_PACK_VERSION
    staging.mkdir(parents=True)
    FIXTURES.INSTALL._extract_zip(archive, staging, 0)
    dotnet = tmp_path / "dotnet"
    dotnet.mkdir()
    return staging, dotnet, dotnet / "packs" / BOOT.TARGETING_PACK / BOOT.TARGETING_PACK_VERSION


def prepare(tmp_path, monkeypatch, fault=None):
    value = json.loads((RECIPE / "toolchain.lock.json").read_bytes())
    archives = {
        "netcore-app-ref": targeting_zip(),
        "dotnet-sdk": FIXTURES.tar_bytes([
            ("dotnet", "file", b"tiny nonexecuted SDK fixture"),
            (f"sdk/{BOOT.SDK_VERSION}/fixture", "file", b"version directory"),
            (f"sdk/{BOOT.SDK_VERSION}/Microsoft.NETCoreSdk.BundledVersions.props", "file",
             bundled_metadata().replace(b"10.0.111", b"10.0.110") if fault == "bundled-before-install"
             else bundled_metadata()),
        ]),
        "temurin-jdk": FIXTURES.tar_bytes([("jdk/bin/java", "file", b"tiny nonexecuted JDK fixture")]),
        "android-sdk-platform": FIXTURES.zip_bytes([("platform/android.jar", b"tiny platform")]),
        "android-platform-tools": platform_tools_zip(),
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
        if entry["name"] == "netcore-app-ref":
            monkeypatch.setattr(BOOT, "TARGETING_PACK_STAGING", Path(entry["destination"]))
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
        if fault == "missing-platform-tools":
            (android / "platform-tools").rename(android / "not-platform-tools")
        if fault == "bundled-after-install":
            (dotnet / "sdk" / BOOT.SDK_VERSION / "Microsoft.NETCoreSdk.BundledVersions.props").unlink()
        if fault == "targeting-after-install":
            (dotnet / "packs" / BOOT.TARGETING_PACK / BOOT.TARGETING_PACK_VERSION / "ref/net10.0/System.Runtime.dll").unlink()

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
                (dotnet / "sdk/10.0.110").mkdir()
            if fault == "targeting-before-install":
                (BOOT.TARGETING_PACK_STAGING / "data/FrameworkList.xml").unlink()
            return subprocess.CompletedProcess(command, 0, "")
        if command[1:3] == ["workload", "install"]:
            assert not BOOT.TARGETING_PACK_STAGING.exists()
            BOOT.verify_targeting_pack(dotnet / "packs" / BOOT.TARGETING_PACK / BOOT.TARGETING_PACK_VERSION)
            assert command[3:9] == ["android", "maui-android", "--version", "10.0.112", "--source", BOOT.NUGET_SOURCE]
            config = Path(command[command.index("--configfile") + 1]).read_text()
            assert "<clear/>" in config and BOOT.NUGET_SOURCE in config
            if fault == "workload-failure":
                raise subprocess.CalledProcessError(1, command)
            populate()
            (Path(environment["NUGET_PACKAGES"]) / "microsoft.maui.controls/10.0.20").mkdir(parents=True)
            return subprocess.CompletedProcess(command, 0, "offline modeled workload install")
        if command[1:] == ["--version"]:
            output = "10.0.110" if fault == "sdk-version" else BOOT.SDK_VERSION
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
    tools = tmp_path / "opt/android-sdk/platform-tools"
    for name in ("adb", "fastboot"):
        assert stat.S_IMODE((tools / name).stat().st_mode) == 0o755
        assert not any(command[0] == str(tools / name) for command in calls)
    assert (tools / "source.properties").read_bytes() == b"Pkg.UserSrc=false\nPkg.Revision=37.0.1\n"


@pytest.mark.parametrize("fault", ["sdk-version", "extra-sdk", "workload-version", "java-version",
                                   "manifest-version", "missing-pack", "linked-pack", "missing-api", "workload-failure",
                                   "library-kind", "library-manifest-version", "library-missing", "library-duplicate-kind",
                                   "missing-platform-tools", "bundled-before-install", "bundled-after-install",
                                   "targeting-before-install", "targeting-after-install"])
def test_bootstrap_version_or_install_failure_cannot_report_success(tmp_path, monkeypatch, fault):
    execute, calls, _ = prepare(tmp_path, monkeypatch, fault)
    with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
        execute()
    if fault in ("sdk-version", "extra-sdk", "bundled-before-install", "targeting-before-install"):
        assert not any(command[1:3] == ["workload", "install"] for command in calls)


def test_targeting_pack_promotes_complete_tiny_zip_with_public_modes(tmp_path):
    staging, dotnet, destination = targeting_fixture(tmp_path)
    before = BOOT.verify_targeting_pack(staging, public_modes=False)
    for name, row in before.items():
        (staging / name).chmod(0o700 if row[0] else 0o600)
    with pytest.raises(RuntimeError, match="tree admission"):
        BOOT.verify_targeting_pack(staging)
    BOOT.promote_targeting_pack(staging, dotnet)
    after = BOOT.verify_targeting_pack(destination)
    assert not staging.exists()
    assert {name: row[2:] for name, row in before.items()} == {name: row[2:] for name, row in after.items()}
    assert all(row[1] == (0o755 if row[0] else 0o644) for row in after.values())
    assert destination.parent.stat().st_mode & 0o777 == 0o755
    assert (dotnet / "packs").stat().st_mode & 0o777 == 0o755


@pytest.mark.parametrize("name", ["data/FrameworkList.xml", "data/PlatformManifest.txt", "data/PackageOverrides.txt",
                                  "Microsoft.NETCore.App.Ref.nuspec", "ref/net10.0/System.Runtime.dll",
                                  "analyzers/dotnet/cs/Fixture.dll"])
def test_targeting_pack_missing_required_payload_cannot_promote(tmp_path, name):
    staging, dotnet, destination = targeting_fixture(tmp_path)
    (staging / name).unlink()
    with pytest.raises(RuntimeError, match="targeting pack"):
        BOOT.promote_targeting_pack(staging, dotnet)
    assert staging.is_dir() and not destination.exists()


@pytest.mark.parametrize("fault", ["empty", "symlink", "hardlink", "fifo", "directory", "wrong-version",
                                   "duplicate-id", "omitted-declaration", "wrong-framework", "linked-root", "overlap"])
def test_targeting_pack_hostile_payload_cannot_promote(tmp_path, fault):
    staging, dotnet, destination = targeting_fixture(tmp_path)
    path = staging / "ref/net10.0/System.Runtime.dll"
    if fault == "hardlink":
        os.link(path, tmp_path / "extra-link")
    elif fault in ("empty", "symlink", "fifo", "directory"):
        path.unlink()
        if fault == "empty":
            path.touch()
        elif fault == "symlink":
            path.symlink_to(staging / "ref/net10.0/netstandard.dll")
        elif fault == "fifo":
            os.mkfifo(path)
        else:
            path.mkdir()
    elif fault in ("wrong-version", "duplicate-id"):
        path = staging / "Microsoft.NETCore.App.Ref.nuspec"
        raw = path.read_bytes()
        path.write_bytes(raw.replace(b"10.0.12", b"10.0.11") if fault == "wrong-version" else
                         raw.replace(b"</metadata>", b"<id>Microsoft.NETCore.App.Ref</id></metadata>"))
    elif fault in ("omitted-declaration", "wrong-framework"):
        path = staging / "data/FrameworkList.xml"
        path.write_bytes(path.read_bytes().replace(b'<File Type="Managed" Path="ref/net10.0/System.Runtime.dll" />', b"")
                         if fault == "omitted-declaration" else path.read_bytes().replace(b'"10.0"', b'"9.0"'))
    elif fault == "linked-root":
        original = staging.with_name("original")
        staging.rename(original)
        staging.symlink_to(original, target_is_directory=True)
    else:
        dotnet = staging.parent
    with pytest.raises(RuntimeError):
        BOOT.promote_targeting_pack(staging, dotnet)
    assert not destination.exists()


@pytest.mark.parametrize("kind", ["empty-directory", "file", "symlink"])
def test_targeting_pack_destination_is_never_overwritten(tmp_path, kind):
    staging, dotnet, destination = targeting_fixture(tmp_path)
    destination.parent.mkdir(parents=True)
    if kind == "empty-directory":
        destination.mkdir()
    elif kind == "file":
        destination.write_bytes(b"existing")
    else:
        destination.symlink_to(tmp_path / "absent")
    before = destination.lstat()
    with pytest.raises(RuntimeError, match="already exists"):
        BOOT.promote_targeting_pack(staging, dotnet)
    assert destination.lstat() == before and staging.is_dir()


@pytest.mark.parametrize("fault", ["destination-race", "cross-device"])
def test_targeting_pack_atomic_rename_has_no_replace_or_copy_fallback(tmp_path, monkeypatch, fault):
    staging, dotnet, destination = targeting_fixture(tmp_path)
    rename = BOOT._rename_targeting_pack

    def fail_promotion(source, target):
        if fault == "cross-device":
            raise OSError(errno.EXDEV, "synthetic cross-device boundary")
        target.mkdir()
        rename(source, target)

    monkeypatch.setattr(BOOT, "_rename_targeting_pack", fail_promotion)
    with pytest.raises(RuntimeError, match="no-replace promotion failed"):
        BOOT.promote_targeting_pack(staging, dotnet)
    assert staging.is_dir()
    assert list(destination.iterdir()) == [] if fault == "destination-race" else not destination.exists()


def test_bundled_metadata_selects_exact_net10_declarations_without_execution(tmp_path):
    metadata_fixture(tmp_path, b"\t\r\n" + bundled_metadata())
    assert BOOT.verify_sdk_bundled_metadata(tmp_path) is None


@pytest.mark.parametrize("encoding", ["utf-16le", "utf-16be"])
def test_bundled_metadata_rejects_nul_interleaved_declarations_before_parse(tmp_path, monkeypatch, encoding):
    xml = (b'<!DOCTYPE Project [<!ENTITY sdk "10.0.111">]>'
           + bundled_metadata().replace(b"10.0.111", b"&sdk;"))
    metadata_fixture(tmp_path, xml.decode("ascii").encode(encoding))
    monkeypatch.setattr(BOOT.ET, "fromstring", lambda *args: pytest.fail("UTF-16 reached XML parser"))
    with pytest.raises(RuntimeError, match="XML controls"):
        BOOT.verify_sdk_bundled_metadata(tmp_path)


@pytest.mark.parametrize("control", [b"\x00", b"\x01", b"\x0b", b"\x0c", b"\x1f"])
def test_bundled_metadata_rejects_xml_controls_before_parse(tmp_path, monkeypatch, control):
    metadata_fixture(tmp_path, control + bundled_metadata())
    monkeypatch.setattr(BOOT.ET, "fromstring", lambda *args: pytest.fail("control reached XML parser"))
    with pytest.raises(RuntimeError, match="XML controls"):
        BOOT.verify_sdk_bundled_metadata(tmp_path)


@pytest.mark.parametrize("old,new", [
    (b"10.0.111", b"10.0.110"),
    (b">10.0.11<", b">10.0.10<"),
    (b'ILLinkPackVersion="10.0.11"', b'ILLinkPackVersion="10.0.10"'),
    (b'TargetFramework="net10.0"', b'TargetFramework="net8.0"'),
    (b'Include="Microsoft.NET.ILLink.Tasks"', b'Include="Other.Linker"'),
    (b"<NETCoreSdkVersion>10.0.111</NETCoreSdkVersion>", b""),
    (b"<BundledNETCoreAppPackageVersion>10.0.11</BundledNETCoreAppPackageVersion>", b""),
    (b"</PropertyGroup>", b"<NETCoreSdkVersion>10.0.111</NETCoreSdkVersion></PropertyGroup>"),
    (b'TargetFramework="net9.0"', b'TargetFramework="net10.0"'),
    (b"<PropertyGroup>", b'<PropertyGroup Condition="false">'),
    (b"<ItemGroup>", b'<ItemGroup Condition="false">'),
    (b"<NETCoreSdkVersion>", b'<NETCoreSdkVersion Condition="false">'),
    (b'ILLinkPackVersion="10.0.11"', b'ILLinkPackVersion="10.0.11" Condition="false"'),
    (b"NETCoreSdkVersion", b"netcoresdkversion"),
    (b"<Project>", b'<Project xmlns="urn:unexpected">'),
    (b"</Project>", b""),
    (b"<Project>", b'<!DOCTYPE Project [<!ENTITY v "10.0.111">]><Project>'),
    (b"<Project>", b"\xff<Project>"),
])
def test_bundled_metadata_rejects_missing_mismatched_or_ambiguous_values(tmp_path, old, new):
    metadata_fixture(tmp_path, bundled_metadata().replace(old, new))
    with pytest.raises(RuntimeError, match="SDK bundled metadata"):
        BOOT.verify_sdk_bundled_metadata(tmp_path)


@pytest.mark.parametrize("fault", ["missing", "empty", "oversized", "symlink", "hardlink", "directory", "fifo"])
def test_bundled_metadata_rejects_unsafe_file_before_open(tmp_path, monkeypatch, fault):
    path = metadata_fixture(tmp_path)
    if fault == "hardlink":
        os.link(path, tmp_path / "extra-link")
    else:
        path.unlink()
        if fault == "empty":
            path.touch()
        elif fault == "oversized":
            path.write_bytes(b" " * (256 * 1024 + 1))
        elif fault == "symlink":
            other = tmp_path / "outside"
            other.write_bytes(bundled_metadata())
            path.symlink_to(other)
        elif fault == "directory":
            path.mkdir()
        elif fault == "fifo":
            os.mkfifo(path)
    monkeypatch.setattr(BOOT.os, "open", lambda *args, **kw: pytest.fail("unsafe metadata reached open"))
    with pytest.raises(RuntimeError, match="SDK bundled metadata"):
        BOOT.verify_sdk_bundled_metadata(tmp_path)


@pytest.mark.parametrize("fault", ["parent-link", "relative"])
def test_bundled_metadata_rejects_noncanonical_directory(tmp_path, monkeypatch, fault):
    metadata_fixture(tmp_path)
    if fault == "parent-link":
        root = tmp_path / "alias"
        root.symlink_to(tmp_path, target_is_directory=True)
    else:
        monkeypatch.chdir(tmp_path.parent)
        root = Path(tmp_path.name)
    with pytest.raises(RuntimeError, match="directory"):
        BOOT.verify_sdk_bundled_metadata(root)


def test_bundled_metadata_rechecks_path_identity_after_parse(tmp_path, monkeypatch):
    path = metadata_fixture(tmp_path)
    parse = BOOT.ET.fromstring

    def replace_during_parse(raw):
        path.rename(tmp_path / "original")
        path.write_bytes(raw.encode())
        return parse(raw)

    monkeypatch.setattr(BOOT.ET, "fromstring", replace_during_parse)
    with pytest.raises(RuntimeError, match="file changed"):
        BOOT.verify_sdk_bundled_metadata(tmp_path)


def test_bundled_metadata_byte_and_node_bounds(tmp_path):
    raw = bundled_metadata()
    path = metadata_fixture(tmp_path, raw + b" " * (256 * 1024 - len(raw)))
    BOOT.verify_sdk_bundled_metadata(tmp_path)
    path.write_bytes(raw.replace(b"</Project>", b"<Other/>" * 4096 + b"</Project>"))
    with pytest.raises(RuntimeError, match="XML shape"):
        BOOT.verify_sdk_bundled_metadata(tmp_path)


def test_bundled_metadata_rechecks_identity_on_open(tmp_path, monkeypatch):
    path = metadata_fixture(tmp_path)
    original_open = BOOT.os.open

    def change_before_open(*args, **kwargs):
        path.write_bytes(bundled_metadata() + b" ")
        return original_open(*args, **kwargs)

    monkeypatch.setattr(BOOT.os, "open", change_before_open)
    with pytest.raises(RuntimeError, match="file identity"):
        BOOT.verify_sdk_bundled_metadata(tmp_path)


@pytest.mark.parametrize("fault", ["missing-root", "linked-root", "linked-parent", "relative-root"])
def test_platform_tools_requires_canonical_directory(tmp_path, monkeypatch, fault):
    execute, _, _ = prepare(tmp_path, monkeypatch)
    execute()
    android = tmp_path / "opt/android-sdk"
    directory = android / "platform-tools"
    if fault in ("missing-root", "linked-root"):
        target = directory.with_name("relocated-platform-tools")
        directory.rename(target)
        if fault == "linked-root":
            directory.symlink_to(target, target_is_directory=True)
    elif fault == "linked-parent":
        alias = tmp_path / "alias"
        alias.symlink_to(android, target_is_directory=True)
        android = alias
    else:
        monkeypatch.chdir(tmp_path)
        android = Path("opt/android-sdk")
    with pytest.raises(RuntimeError, match="directory"):
        BOOT.verify_platform_tools(android)


@pytest.mark.parametrize("name", ["adb", "fastboot", "source.properties"])
@pytest.mark.parametrize("fault", ["missing", "symlink", "hardlink", "empty", "directory", "fifo"])
def test_platform_tools_rejects_unsafe_files_before_open(tmp_path, monkeypatch, name, fault):
    execute, _, _ = prepare(tmp_path, monkeypatch)
    execute()
    android = tmp_path / "opt/android-sdk"
    path = android / "platform-tools" / name
    if fault == "hardlink":
        os.link(path, path.with_name("extra-link"))
    else:
        path.unlink()
        if fault == "symlink":
            other = tmp_path / "outside"
            other.write_bytes(b"Pkg.Revision=37.0.1\n")
            path.symlink_to(other)
        elif fault == "empty":
            path.touch(mode=0o755)
        elif fault == "directory":
            path.mkdir()
        elif fault == "fifo":
            os.mkfifo(path)
    monkeypatch.setattr(BOOT.os, "open", lambda *args, **kw: pytest.fail("unsafe file reached open"))
    with pytest.raises(RuntimeError, match="platform-tools"):
        BOOT.verify_platform_tools(android)


@pytest.mark.parametrize("name", ["adb", "fastboot"])
def test_platform_tools_rejects_nonexecutable_tool_without_launch(tmp_path, monkeypatch, name):
    execute, _, _ = prepare(tmp_path, monkeypatch)
    execute()
    android = tmp_path / "opt/android-sdk"
    (android / "platform-tools" / name).chmod(0o644)
    with pytest.raises(RuntimeError, match="platform-tools"):
        BOOT.verify_platform_tools(android)


@pytest.mark.parametrize("raw", [
    b"Pkg.UserSrc=false\n", b"Pkg.Revision=37.0.0\n", b"Pkg.Revision=37.0.1.0\n",
    b"Pkg.Revision=\n", b"pkg.revision=37.0.1\n", b"Pkg.Revision:37.0.1\n",
    b"Pkg.Revision 37.0.1\n", b"Pkg.Revision=37.0.1\nPkg.Revision=37.0.1\n",
    b"Pkg.Revision=37.0.0\n Pkg.Revision =37.0.1\n",
    b"Pkg.Revision=37.0.1\nPkg.Revision=37.0.0\n",
    b"Pkg.Revision=37.0.1\nPkg\\.Revision=37.0.0\n",
    b"Pkg.Revision=37.0.1\\\n", b"Pkg.Revision=37.0.1\x00\n",
    b"Pkg.Revision=37.0.1\x0b\n", b"Pkg.Revision=37.0.1\x7f\n",
    b"Pkg.Revision=37.0.1\n#\xff", b"Pkg.Revision=37.0.1\n" + b"#" * 4096,
])
def test_platform_tools_rejects_ambiguous_wrong_or_unbounded_revision(tmp_path, monkeypatch, raw):
    execute, _, _ = prepare(tmp_path, monkeypatch)
    execute()
    android = tmp_path / "opt/android-sdk"
    (android / "platform-tools/source.properties").write_bytes(raw)
    if len(raw) > 4096:
        monkeypatch.setattr(BOOT.os, "open", lambda *args, **kw: pytest.fail("oversized metadata reached open"))
    with pytest.raises(RuntimeError, match="platform-tools"):
        BOOT.verify_platform_tools(android)


@pytest.mark.parametrize("raw", [b"Pkg.Revision=37.0.1", b"# comment\r\n! comment\r\n\r\nPkg.Revision = 37.0.1\r\n",
                                b"\tPkg.Revision\t=\t37.0.1\t\nPkg.UserSrc=false\n"])
def test_platform_tools_accepts_plain_property_whitespace_without_rewriting(tmp_path, monkeypatch, raw):
    execute, calls, _ = prepare(tmp_path, monkeypatch)
    execute()
    android = tmp_path / "opt/android-sdk"
    properties = android / "platform-tools/source.properties"
    properties.write_bytes(raw)
    before = list(calls)
    BOOT.verify_platform_tools(android)
    assert properties.read_bytes() == raw and calls == before


@pytest.mark.parametrize("replace", [False, True])
def test_platform_tools_detects_metadata_drift_during_read(tmp_path, monkeypatch, replace):
    execute, _, _ = prepare(tmp_path, monkeypatch)
    execute()
    android = tmp_path / "opt/android-sdk"
    properties = android / "platform-tools/source.properties"
    original_fstat, calls = os.fstat, 0

    def drift(fd):
        nonlocal calls
        calls += 1
        if calls == 2:
            if replace:
                other = properties.with_name("replacement")
                other.write_bytes(properties.read_bytes())
                other.replace(properties)
            else:
                properties.write_bytes(b"Pkg.UserSrc=false\nPkg.Revision=37.0.0\n")
        return original_fstat(fd)

    monkeypatch.setattr(BOOT.os, "fstat", drift)
    with pytest.raises(RuntimeError, match="platform-tools"):
        BOOT.verify_platform_tools(android)
    assert calls == 2  # Both actual descriptor checks were reached.


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
    assert archives["dotnet-sdk"]["version"] == BOOT.SDK_VERSION == "10.0.111"
    assert BOOT.BUNDLED_RUNTIME_VERSION == "10.0.11"
    assert archives["dotnet-sdk"]["url"] == "https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.111/dotnet-sdk-10.0.111-linux-x64.tar.gz"
    assert archives["dotnet-sdk"]["strip_components"] == 0
    assert archives["dotnet-sdk"]["sha512"] == "aae221be96a3b510d5b6fffefc69d8ad2fa595a1430299419316bb71c65f260a457ca9af24d044e1709b28a9118798caafec535ccfe58f7767c5acb735c00392"
    assert archives["netcore-app-ref"] == {
        "name": "netcore-app-ref", "version": "10.0.12",
        "url": "https://api.nuget.org/v3-flatcontainer/microsoft.netcore.app.ref/10.0.12/microsoft.netcore.app.ref.10.0.12.nupkg",
        "sha256": "bf6e0a1fa7b5ce6a9bbfb7191d2c3151c2d6f812eafabee833fd000c1293b872",
        "format": "zip", "destination": "/opt/fleet-targeting-pack-staging/Microsoft.NETCore.App.Ref/10.0.12",
        "strip_components": 0,
    }
    assert str(BOOT.TARGETING_PACK_STAGING) == archives["netcore-app-ref"]["destination"]
    assert BOOT.PACKS["Microsoft.NETCore.App.Ref"] == ("10.0.12",)
    assert archives["temurin-jdk"]["version"] == "17.0.20.1+1"
    assert archives["temurin-jdk"]["sha256"] == "3808d1d15e3ec6bd5b84057fb5d84c33d8a1536a258146bcea2e603fc726e08e"
    assert archives["android-sdk-platform"]["sha256"] == "37607369a28c5b640b3a7998868d45898ebcb777565a0e85f9acf36f29631d2e"
    assert archives["android-platform-tools"] == {
        "name": "android-platform-tools", "version": "37.0.1",
        "url": "https://dl.google.com/android/repository/platform-tools_r37.0.1-linux.zip",
        "sha256": "d230f13842f60f782a8645f9c813f8f845bf36089ea7289f28c48f17979313f1",
        "format": "zip", "destination": "/opt/android-sdk/platform-tools", "strip_components": 1,
    }
    assert BOOT.PLATFORM_TOOLS_VERSION == "37.0.1"
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


def test_os_build_tools_target_stops_before_sdk_install_and_preserves_default_stage():
    # Recipe boundary only. Real image identity, tool execution and installed
    # SDK closure still need their own observed runtime receipts.
    docker = (RECIPE / "Dockerfile").read_text()
    base = json.loads((RECIPE / "toolchain.lock.json").read_bytes())["base_images"][0]
    assert [line for line in docker.splitlines() if line.startswith("FROM ")] == [
        f'FROM {base["reference"]}@{base["digest"]} AS os-build-tools',
        "FROM os-build-tools AS release-rebuilder",
    ]
    tools, release = docker.split("FROM os-build-tools AS release-rebuilder\n")
    assert "# END SNAPSHOT BOOTSTRAP" in tools
    assert [line for line in tools.splitlines() if line.startswith("COPY ")] == [
        "COPY containers/android-preview12-rebuilder/ubuntu.sources /opt/fleet-rebuilder/ubuntu.sources",
        "COPY containers/android-preview12-rebuilder/ubuntu-InRelease.SHA256SUMS /opt/fleet-rebuilder/ubuntu-InRelease.SHA256SUMS",
    ]
    assert sum(line.startswith("RUN ") for line in tools.splitlines()) == 1
    assert all(token not in tools for token in (
        "install_toolchain.py", "bootstrap.py", "workload install", "ENTRYPOINT", "--mount=",
    ))
    assert "dpkg-query -W > /opt/fleet-rebuilder/os-package-inventory.txt" in tools
    assert "RUN /usr/bin/python3 -I -E -S /opt/fleet-rebuilder/bootstrap.py" in release
    assert "&& /usr/bin/python3 -I -E -S /opt/fleet-rebuilder/android_preview12_external_rebuilder.py --help" in release
    assert release.rstrip().endswith('CMD ["--help"]')


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
