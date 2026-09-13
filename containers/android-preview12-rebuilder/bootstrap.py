#!/usr/bin/env python3
"""Image-build-only bootstrap; archive inventory and version checks, not authority.

The recovered workload versions do not establish old installed-tree hashes.
No final OCI identity, protected custody, approval or signing receipt is emitted.
"""
from __future__ import annotations

import json
import io
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile


SDK_VERSION = "10.0.110"
WORKLOAD_VERSION = "10.0.112"
NUGET_SOURCE = "https://api.nuget.org/v3/index.json"
MANIFESTS = {"microsoft.net.sdk.android": "36.1.69", "microsoft.net.sdk.maui": "10.0.20",
             "microsoft.net.workload.mono.toolchain.current": "10.0.112",
             "microsoft.net.workload.mono.toolchain.net9": "10.0.112"}
PACKS = {
    "Microsoft.Android.Sdk.Linux": ("36.1.69", "35.0.105"),
    "Microsoft.Android.Ref.36": ("36.1.69",),
    "Microsoft.Maui.Sdk": ("10.0.20", "9.0.120"),
    "Microsoft.NET.Runtime.MonoAOTCompiler.Task": ("10.0.12", "9.0.20"),
    "Microsoft.NET.Runtime.MonoTargets.Sdk": ("10.0.12", "9.0.20"),
    **{f"Microsoft.NETCore.App.Runtime.Mono.android-{abi}": ("10.0.12", "9.0.20")
       for abi in ("arm", "arm64", "x86", "x64")},
    **{f"Microsoft.NETCore.App.Runtime.AOT.linux-x64.Cross.android-{abi}": ("10.0.12", "9.0.20")
       for abi in ("arm", "arm64", "x86", "x64")},
}
LIBRARY_PACKS = {"Microsoft.Maui.Controls": "10.0.20"}


def require_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir() or path.resolve(strict=True) != path:
        raise RuntimeError(f"missing or noncanonical toolchain directory: {path}")


def _unique_json_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError("workload manifest contains duplicate fields")
        result[key] = value
    return result


def _bounded_zip_directory(source, size: int) -> None:
    # Bound the central directory before ZipFile allocates per-member objects.
    # This small library package must not need ZIP64 or multi-disk packaging.
    source.seek(max(0, size - 65557))
    tail = source.read(65557)
    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0 or len(tail) - offset < 22:
        raise ValueError("missing bounded ZIP directory")
    disk, start_disk, count_disk, count, directory_size, directory_offset, comment = struct.unpack_from("<4H2IH", tail, offset + 4)
    end_offset = size - len(tail) + offset
    if (disk or start_disk or not 0 < count == count_disk <= 4096 or directory_size > 8 * 1024 * 1024
            or directory_offset + directory_size != end_offset or offset + 22 + comment != len(tail)):
        raise ValueError("unbounded ZIP directory")
    source.seek(directory_offset)
    remaining = directory_size
    for _ in range(count):
        header = source.read(46)
        if len(header) != 46 or header[:4] != b"PK\x01\x02":
            raise ValueError("invalid ZIP member directory")
        name, extra, comment = struct.unpack_from("<3H", header, 28)
        consumed = 46 + name + extra + comment
        if not 0 < name <= 1024 or consumed > remaining:
            raise ValueError("unbounded ZIP member directory")
        source.seek(name + extra + comment, 1)
        remaining -= consumed
    if remaining:
        raise ValueError("ambiguous ZIP directory count")
    source.seek(0)


def _bounded_zip(source, size):
    _bounded_zip_directory(source, size)
    return zipfile.ZipFile(source)


def verify_library_pack(dotnet_root: Path, package_id: str, version: str) -> None:
    # SDK WorkloadResolver installs Library packs as single nupkg files here,
    # not as extracted SDK pack directories or a persistent NuGet global cache.
    path = dotnet_root / "library-packs" / f"{package_id.lower()}.{version}.nupkg"
    require_directory(path.parent)
    failure = f"missing, unsafe or mismatched installed library pack: {path}"
    if path.is_symlink() or not path.is_file() or path.resolve(strict=True) != path:
        raise RuntimeError(failure)
    before = path.stat()
    if not 0 < before.st_size <= 64 * 1024 * 1024:
        raise RuntimeError(failure)
    identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_uid,
                              value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    try:
        with path.open("rb") as source:
            captured = source.read(64 * 1024 * 1024 + 1)
            if len(captured) != before.st_size or identity(os.fstat(source.fileno())) != identity(before):
                raise RuntimeError(failure)
        # Bound and parse one owned archive snapshot; a replaced central
        # directory cannot invalidate the admission bounds between two reads.
        with io.BytesIO(captured) as source, _bounded_zip(source, len(captured)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > 4096:
                raise RuntimeError(failure)
            names, total, nuspecs = {}, 0, []
            for entry in entries:
                raw_name = entry.filename
                name = raw_name.removesuffix("/")
                relative = PurePosixPath(name)
                mode = stat.S_IFMT(entry.external_attr >> 16)
                if (raw_name != entry.orig_filename or "\x00" in raw_name or "\\" in name or ":" in name
                        or not name or relative.is_absolute() or ".." in relative.parts
                        or str(relative) != name or name.casefold() in names
                        or mode not in (0, stat.S_IFREG, stat.S_IFDIR)
                        or (mode == stat.S_IFDIR and not entry.is_dir())
                        or (mode == stat.S_IFREG and entry.is_dir()) or entry.flag_bits & 1
                        or (entry.is_dir() and entry.file_size != 0)
                        or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    raise RuntimeError(failure)
                names[name.casefold()] = entry.is_dir()
                total += entry.file_size
                if total > 512 * 1024 * 1024 or entry.file_size > 128 * 1024 * 1024:
                    raise RuntimeError(failure)
                if name.casefold().endswith(".nuspec"):
                    nuspecs.append(entry)
            for name in names:
                if any(str(parent) in names and not names[str(parent)] for parent in PurePosixPath(name).parents):
                    raise RuntimeError(failure)
            if (len(nuspecs) != 1 or nuspecs[0].filename.casefold() != f"{package_id}.nuspec".casefold()
                    or nuspecs[0].is_dir() or nuspecs[0].file_size > 256 * 1024):
                raise RuntimeError(failure)
            # Stream every member to EOF for CRC/truncation checks without
            # extracting anything. Only the bounded nuspec is retained.
            nuspec = bytearray()
            for entry in entries:
                consumed = 0
                with archive.open(entry) as member:
                    while chunk := member.read(1024 * 1024):
                        consumed += len(chunk)
                        if consumed > entry.file_size:
                            raise RuntimeError(failure)
                        if entry is nuspecs[0]:
                            nuspec.extend(chunk)
                if consumed != entry.file_size:
                    raise RuntimeError(failure)
            text = bytes(nuspec).decode("utf-8-sig", errors="strict")
            if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
                raise RuntimeError(failure)
            root = ET.fromstring(text)
            if root.tag.rsplit("}", 1)[-1] != "package":
                raise RuntimeError(failure)
            namespace = root.tag[:-len("package")]

            def one_child(parent, name):
                matches = [child for child in parent if child.tag.rsplit("}", 1)[-1] == name]
                if len(matches) != 1 or matches[0].tag != namespace + name:
                    raise RuntimeError(failure)
                return matches[0]

            metadata = one_child(root, "metadata")
            for name, expected in (("id", package_id), ("version", version)):
                element = one_child(metadata, name)
                if element.text != expected or len(element) or element.attrib:
                    raise RuntimeError(failure)
            if (path.is_symlink()
                    or path.resolve(strict=True) != path or identity(path.stat()) != identity(before)):
                raise RuntimeError(failure)
    except (OSError, ValueError, struct.error, ET.ParseError, zipfile.BadZipFile, NotImplementedError):
        raise RuntimeError(failure) from None


def _installed_pack_diagnostic(packs: Path) -> dict:
    """Bounded directory names only: not file contents or installed authority."""
    result = {"diagnostic": "non_authoritative_installed_pack_directories", "packs": [], "truncated": False}

    def names(path, limit):
        found = []
        if path.is_symlink():
            raise OSError("linked inventory directory")
        with os.scandir(path) as entries:
            for index, entry in enumerate(entries):
                if index == limit:
                    result["truncated"] = True
                    break
                if entry.is_dir(follow_symlinks=False):
                    found.append(entry.name)
        return sorted(found)

    try:
        for name in names(packs, 256):
            row = {"name": name[:128], "versions": [value[:128] for value in names(packs / name, 32)]}
            if len(json.dumps(result)) + len(json.dumps(row)) > 16 * 1024:
                result["truncated"] = True
                break
            result["packs"].append(row)
    except OSError:
        result["unavailable"] = True
    return result


def verify_installed_versions(dotnet_root: Path, java_root: Path, android_root: Path, probe) -> None:
    require_directory(dotnet_root / "sdk")
    if sorted(path.name for path in (dotnet_root / "sdk").iterdir()) != [SDK_VERSION]:
        raise RuntimeError("installed SDK set differs from exact SDK 10.0.110")
    require_directory(dotnet_root / "sdk" / SDK_VERSION)
    if probe([str(dotnet_root / "dotnet"), "--version"]) != SDK_VERSION:
        raise RuntimeError("SDK version probe differs")
    if probe([str(dotnet_root / "dotnet"), "workload", "--version"]) != WORKLOAD_VERSION:
        raise RuntimeError("workload set version differs")
    java = probe([str(java_root / "bin/java"), "-version"])
    if 'version "17.0.20.1"' not in java or "Temurin" not in java:
        raise RuntimeError("Temurin JDK version differs")
    for name, version in MANIFESTS.items():
        path = dotnet_root / "sdk-manifests/10.0.100" / name / version / "WorkloadManifest.json"
        require_directory(path.parent)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise RuntimeError("workload manifest missing or unsafe")
        value = json.loads(path.read_bytes(), object_pairs_hook=_unique_json_fields)
        if not isinstance(value, dict) or value.get("version") != version:
            raise RuntimeError("workload manifest version differs")
        if name == "microsoft.net.sdk.maui":
            declarations = value.get("packs")
            for package_id, package_version in LIBRARY_PACKS.items():
                declaration = declarations.get(package_id) if isinstance(declarations, dict) else None
                if (not isinstance(declaration, dict) or declaration.get("kind") != "library"
                        or declaration.get("version") != package_version):
                    raise RuntimeError(f"workload library declaration differs: {package_id} {package_version}")
    for name, versions in PACKS.items():
        for version in versions:
            try:
                require_directory(dotnet_root / "packs" / name / version)
            except RuntimeError:
                print(json.dumps(_installed_pack_diagnostic(dotnet_root / "packs"), sort_keys=True), file=sys.stderr)
                raise
    for package_id, version in LIBRARY_PACKS.items():
        verify_library_pack(dotnet_root, package_id, version)
    for path in (android_root / "platforms/android-36/android.jar",
                 *(android_root / "build-tools/36.0.0" / name for name in ("aapt2", "apksigner", "zipalign"))):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("Android API/build-tools 36 missing")


def bootstrap(installer: Path, manifest: Path, receipt: Path, dotnet_root: Path,
              java_root: Path, android_root: Path, *, runner=subprocess.run) -> None:
    with tempfile.TemporaryDirectory(prefix="fleet-rebuilder-bootstrap-") as temporary:
        cache = Path(temporary)
        config = cache / "NuGet.Config"
        config.write_text('<configuration><packageSources><clear/><add key="nuget.org" '
                          f'value="{NUGET_SOURCE}"/></packageSources></configuration>', encoding="utf-8")
        environment = {
            "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            "DOTNET_ROOT": str(dotnet_root), "JAVA_HOME": str(java_root),
            "DOTNET_CLI_HOME": str(cache / "cli-home"), "NUGET_PACKAGES": str(cache / "nuget"),
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1",
            "DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE": "true",
            "DOTNET_NUGET_SIGNATURE_VERIFICATION": "true",
        }

        def probe(command):
            result = runner(command, check=True, env=environment, cwd=cache, timeout=1800,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            return result.stdout.strip()

        probe(["/usr/bin/python3", "-I", "-E", "-S", str(installer), str(manifest), str(receipt)])
        # Refuse an unexpected SDK before allowing any workload resolution.
        require_directory(dotnet_root / "sdk")
        if sorted(path.name for path in (dotnet_root / "sdk").iterdir()) != [SDK_VERSION]:
            raise RuntimeError("unexpected SDK before workload installation")
        if probe([str(dotnet_root / "dotnet"), "--version"]) != SDK_VERSION:
            raise RuntimeError("SDK version probe differs")
        probe([str(dotnet_root / "dotnet"), "workload", "install", "android", "maui-android",
               "--version", WORKLOAD_VERSION, "--source", NUGET_SOURCE,
               "--configfile", str(config), "--disable-parallel"])
        try:
            verify_installed_versions(dotnet_root, java_root, android_root, probe)
        except RuntimeError:
            # Observe only this transaction's generated private cache, never
            # ambient NUGET_PACKAGES or a caller-controlled external directory.
            nuget = cache / "nuget"
            if (not cache.is_symlink() and cache.resolve(strict=True) == cache
                    and cache.stat().st_uid == os.getuid() and not cache.stat().st_mode & 0o077
                    and not nuget.is_symlink()):
                diagnostic = _installed_pack_diagnostic(nuget)
                diagnostic["diagnostic"] = "non_authoritative_private_nuget_directories"
                print(json.dumps(diagnostic, sort_keys=True), file=sys.stderr)
            raise


if __name__ == "__main__":
    base = Path("/opt/fleet-rebuilder")
    bootstrap(base / "install_toolchain.py", base / "toolchain.lock.json", base / "archive-inventory.json",
              Path("/opt/dotnet"), Path("/opt/jdk"), Path("/opt/android-sdk"))
    print("toolchain version checks passed; installed-tree and protected execution authority remain unestablished")
