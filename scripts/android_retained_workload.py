"""Read-only required-pack observations; not installed-closure or release authority.

The caller supplies captured CLI outputs. This module neither runs commands nor
authenticates their freshness. Historical installation metadata is never used.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import types


BOOTSTRAP_SHA256 = "07ea6bce94b9edc6d50a977d70a75623c958ebf41c27f9800e06d4fa6d2e6440"
_VERSION = re.compile(r"(?:0|[1-9][0-9]{0,5})(?:\.(?:0|[1-9][0-9]{0,5})){2,3}\Z")
_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_RID = "linux-x64"
_WORKLOAD_WARNING = ('An issue was encountered verifying workloads. For more information, '
                     'run "dotnet workload update".')


def _need(condition, message):
    if not condition:
        raise RuntimeError(message)


def _version(value):
    _need(isinstance(value, str) and _VERSION.fullmatch(value), "invalid version")
    return value


def _segment(value):
    _need(isinstance(value, str) and _SEGMENT.fullmatch(value), "unsafe path segment")
    return value


def _workload_output(raw):
    lines = raw.rstrip("\n").split("\n")
    _need(len(lines) == 1 or len(lines) == 2 and lines[0] == _WORKLOAD_WARNING,
          "unrecognized or ambiguous workload output")
    return _version(lines[-1]), lines[:-1]


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _path(value, directory=False):
    raw = os.fspath(value)
    path = Path(raw)
    _need(isinstance(raw, str) and len(raw) <= 4096 and path.is_absolute()
          and str(path) == raw and ".." not in path.parts and len(path.parts) <= 64,
          "noncanonical input path")
    for parent in reversed(path.parents):
        _need(stat.S_ISDIR(parent.lstat().st_mode), f"linked or missing parent: {parent}")
    metadata = path.lstat()
    _need((stat.S_ISDIR if directory else stat.S_ISREG)(metadata.st_mode),
          f"missing or unsafe {'directory' if directory else 'file'}: {path}")
    return path, _identity(metadata)


def _read(path, limit, capture=True):
    path, before = _path(path)
    _need(0 < before[5] <= limit, f"unbounded or empty input: {path}")
    digest, data, count = hashlib.sha256(), bytearray(), 0
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as source:
        _need(_identity(os.fstat(source.fileno())) == before, "input changed before read")
        while chunk := source.read(min(1024 * 1024, limit + 1 - count)):
            count += len(chunk)
            _need(count <= limit, "input exceeds byte limit")
            digest.update(chunk)
            if capture:
                data.extend(chunk)
        _need(count == before[5] and _identity(os.fstat(source.fileno())) == before,
              "input changed during read")
    _need(_path(path)[1] == before, "input changed after read")
    return bytes(data), digest.hexdigest(), count, before


def _unique(pairs):
    result, seen = {}, set()
    for key, value in pairs:
        _need(key.casefold() not in seen, "duplicate JSON field or case-folded identifier")
        seen.add(key.casefold())
        result[key] = value
    return result


def _json(data):
    value = json.loads(data, object_pairs_hook=_unique,
                       parse_constant=lambda _: _need(False, "non-finite JSON value"))
    remaining = 20000

    def bound(node, depth=0):
        nonlocal remaining
        remaining -= 1
        _need(remaining >= 0 and depth <= 16, "JSON structure exceeds bounds")
        if isinstance(node, (dict, list)):
            _need(len(node) <= 1024, "JSON collection exceeds bounds")
            for child in (list(node) + list(node.values()) if isinstance(node, dict) else node):
                bound(child, depth + 1)
        elif isinstance(node, str):
            _need(len(node) <= 4096 and "\x00" not in node, "unbounded JSON string")
        else:
            _need(node is None or isinstance(node, (bool, int)), "unsupported JSON value")
    bound(value)
    _need(isinstance(value, dict), "JSON root must be an object")
    return value


def _requirements(major, api):
    android, maui = "microsoft.net.sdk.android", "microsoft.net.sdk.maui"
    rows = [(android, f"Microsoft.Android.Ref.{api}", f"Microsoft.Android.Ref.{api}", "framework"),
            (maui, "Microsoft.Maui.Controls", "Microsoft.Maui.Controls", "library")]
    for net in (major, major - 1):
        rows += [(android, f"Microsoft.Android.Sdk.net{net}", "Microsoft.Android.Sdk.Linux", "sdk"),
                 (maui, f"Microsoft.Maui.Sdk.net{net}", "Microsoft.Maui.Sdk", "sdk")]
        mono = "microsoft.net.workload.mono.toolchain." + ("current" if net == major else f"net{net}")
        for family in ("MonoAOTCompiler.Task", "MonoTargets.Sdk"):
            physical = "Microsoft.NET.Runtime." + family
            rows.append((mono, f"{physical}.net{net}", physical, "sdk"))
        for abi in ("arm", "arm64", "x86", "x64"):
            prefix = "Microsoft.NETCore.App.Runtime."
            rows += [(mono, f"{prefix}Mono.net{net}.android-{abi}", f"{prefix}Mono.android-{abi}", "framework"),
                     (mono, f"{prefix}AOT.Cross.net{net}.android-{abi}", f"{prefix}AOT.{_RID}.Cross.android-{abi}", "sdk")]
    return rows


def validate_retained_workload(*, dotnet_root, java_root, android_root, lock_path, observed):
    """Validate the required profile using caller-captured outputs; execute nothing.

    ``observed`` must contain sdk_version, workload_version, java_version_output;
    each value is the raw corresponding CLI output (including warnings).
    Capture SDK/workload stdout and Java -version output freshly in the intended
    namespace before calling. These strings are not self-authenticating evidence.
    ``lock_path`` is the existing external-rebuilder lock, not an installation plan.
    """
    try:
        return _validate(dotnet_root, java_root, android_root, lock_path, observed)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        raise RuntimeError(f"invalid retained workload input: {error}") from None


def _validate(dotnet_root, java_root, android_root, lock_path, observed):
    files, directories, presence = {}, {}, {}

    def directory(path):
        path, identity = _path(path, directory=True)
        if path in directories:
            _need(directories[path] == identity, "directory changed during validation")
        directories[path] = identity
        return path

    def read(role, path, limit=1024 * 1024, capture=True):
        data, digest, count, identity = _read(path, limit, capture)
        files[role] = (Path(path), limit, digest, count, identity)
        return data

    dotnet, java, android = map(directory, (dotnet_root, java_root, android_root))
    lock = _json(read("lock", lock_path))["toolchain"]
    _need(lock["platform"] == "linux/amd64", "unsupported platform")
    sdk, jdk = _version(lock["dotnet"]["version"]), _version(lock["java"]["version"])
    api, build_tools = lock["android_sdk"]["api_level"], _version(lock["android_sdk"]["build_tools_version"])
    _need(type(api) is int and 1 <= api <= 999, "invalid Android API")
    _need(len(sdk.split(".")) == 3, "unsupported SDK version")
    major, minor, patch = map(int, sdk.split("."))
    _need(major >= 2, "unsupported SDK major")
    band = f"{major}.{minor}.{patch // 100 * 100}"
    _need(isinstance(observed, dict) and set(observed) == {"sdk_version", "workload_version", "java_version_output"},
          "expected explicit caller-captured CLI outputs")
    _need(all(isinstance(value, str) and 0 < len(value) <= 8192 and "\x00" not in value
              for value in observed.values()), "invalid observed CLI output")
    _need(observed["sdk_version"].strip() == sdk, "observed SDK version differs from lock")
    workload_version, workload_warnings = _workload_output(observed["workload_version"])
    _need(re.findall(r'^(?:openjdk|java) version "([^"]+)"', observed["java_version_output"], re.MULTILINE) == [jdk],
          "observed Java version differs from lock")
    directory(dotnet / "sdk" / sdk)
    for path in (dotnet / "dotnet", java / "bin/java", android / f"platforms/android-{api}/android.jar",
                 *(android / "build-tools" / build_tools / name for name in ("aapt2", "apksigner", "zipalign"))):
        presence[path] = _path(path)[1]  # Presence only, not executable content hashes.

    descriptor = _json(read("workloadset", dotnet / "sdk-manifests" / band / "workloadsets"
                            / workload_version / "microsoft.net.workloads.workloadset.json"))
    selected = {}
    for name, value in descriptor.items():
        _segment(name)
        _need(isinstance(value, str) and value.count("/") == 1, "invalid selected manifest reference")
        version, feature_band = map(_version, value.split("/"))
        _need(len(feature_band.split(".")) == 3, "invalid manifest feature band")
        selected[name.casefold()] = (version, feature_band)
    requirements = _requirements(major, api)
    manifests, workloads, declarations = {}, {}, {}
    for name in sorted({row[0] for row in requirements}):
        _need(name in selected, f"missing selected manifest: {name}")
        version, feature_band = selected[name]
        manifest = _json(read("manifest:" + name, dotnet / "sdk-manifests" / feature_band
                              / name / version / "WorkloadManifest.json"))
        _need(manifest.get("version") == version, f"selected manifest version differs: {name}")
        manifests[name] = manifest
        for field, target in (("workloads", workloads), ("packs", declarations)):
            entries = manifest.get(field)
            _need(isinstance(entries, dict) and 0 < len(entries) <= 512, f"invalid manifest {field}")
            for identifier, entry in entries.items():
                _segment(identifier)
                key = identifier.casefold()
                _need(key not in target and isinstance(entry, dict), f"duplicate or invalid {field} declaration")
                target[key] = (name, entry)

    reachable, visiting, visited = set(), set(), set()

    def names(entry, field):
        values = entry.get(field, [])
        _need(isinstance(values, list) and len(values) <= 512, f"invalid workload {field}")
        values = [_segment(value).casefold() for value in values]
        _need(len(set(values)) == len(values), f"duplicate workload {field}")
        return values

    def visit(identifier):
        _need(identifier in workloads and identifier not in visiting, "missing or cyclic required workload")
        if identifier in visited:
            return
        visiting.add(identifier)
        entry = workloads[identifier][1]
        _need("platforms" not in entry or _RID in names(entry, "platforms"), "unsupported workload platform")
        reachable.update(names(entry, "packs"))
        for parent in names(entry, "extends"):
            visit(parent)
        visiting.remove(identifier)
        visited.add(identifier)
    visit("android")
    visit("maui-android")

    bootstrap = Path(__file__).resolve().parents[1] / "containers/android-preview12-rebuilder/bootstrap.py"
    read("validator", Path(__file__).absolute(), 64 * 1024)
    source = read("libraryValidator", bootstrap, 64 * 1024)
    _need(hashlib.sha256(source).hexdigest() == BOOTSTRAP_SHA256, "library validator source hash differs")
    helper = types.ModuleType("_pinned_retained_library_validator")
    exec(compile(source, str(bootstrap), "exec"), helper.__dict__)  # __main__ is never entered.
    rows, mono_versions = [], {}
    for owner, logical, physical, kind in sorted(requirements):
        _need(logical.casefold() in reachable and logical.casefold() in declarations,
              f"missing required pack declaration: {logical}")
        actual_owner, declaration = declarations[logical.casefold()]
        _need(actual_owner == owner and str(declaration.get("kind")).lower() == kind,
              f"misdeclared required pack: {logical}")
        version = _version(declaration.get("version"))
        alias = declaration.get("alias-to")
        if alias is None:
            resolved = logical
        else:
            _need(isinstance(alias, dict) and 0 < len(alias) <= 32, "invalid pack alias")
            for rid, target in alias.items():
                _segment(rid)
                _segment(target)
            _need(not (_RID in alias and "any" in alias and alias[_RID] != alias["any"]), "ambiguous pack alias")
            resolved = alias.get(_RID, alias.get("any"))
        _need(resolved == physical, f"unsupported or missing pack alias: {logical}")
        if ".mono.toolchain." in owner:
            _need(mono_versions.setdefault(owner, version) == version, "contradictory Mono family versions")
        net = re.search(r"\.net([0-9]+)(?:\.|$)", logical)
        if net and owner != "microsoft.net.sdk.android":
            _need(int(version.split(".")[0]) == int(net[1]), "pack version targets wrong framework")
        if logical in (f"Microsoft.Android.Ref.{api}", f"Microsoft.Android.Sdk.net{major}",
                       "Microsoft.Maui.Controls", f"Microsoft.Maui.Sdk.net{major}"):
            _need(version == manifests[owner]["version"], "pack and selected manifest versions differ")
        if kind == "library":
            relative = f"library-packs/{physical.lower()}.{version}.nupkg"
            read("library:" + physical, dotnet / relative, 64 * 1024 * 1024, capture=False)
            helper.verify_library_pack(dotnet, physical, version)
        else:
            relative = f"packs/{physical}/{version}"
            directory(dotnet / relative)
        rows.append(dict(logicalId=logical, packageId=physical, version=version, kind=kind, path=relative))

    for path, limit, digest, count, identity in files.values():
        _, after_digest, after_count, after_identity = _read(path, limit, capture=False)
        _need((after_digest, after_count, after_identity) == (digest, count, identity), "bound input changed")
    for path, identity in directories.items():
        _need(_path(path, directory=True)[1] == identity, "required directory changed")
    for path, identity in presence.items():
        _need(_path(path)[1] == identity, "required file changed")
    return dict(success=True, scope="required_android_maui_mono_profile", observed=dict(sorted(observed.items())),
                selectedWorkloadSetVersion=workload_version, workloadWarnings=workload_warnings,
                workloadCommandAccepted=not workload_warnings,
                runtimeQualification=False,
                selectedManifests=[dict(id=name, version=selected[name][0], featureBand=selected[name][1])
                                   for name in sorted(manifests)], requiredPacks=rows,
                inputFiles=[dict(role=role, sha256=value[2], sizeBytes=value[3]) for role, value in sorted(files.items())],
                sdkTreesRemeasured=False, observedValuesAuthenticated=False,
                installedClosureReceipt=False, releaseEligibility=False)
