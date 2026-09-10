#!/usr/bin/env python3
"""Image-build-only bootstrap; archive inventory and version checks, not authority.

The recovered workload versions do not establish old installed-tree hashes.
No final OCI identity, protected custody, approval or signing receipt is emitted.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile


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
    "Microsoft.Maui.Controls": ("10.0.20",),
    "Microsoft.NET.Runtime.MonoAOTCompiler.Task": ("10.0.12", "9.0.20"),
    "Microsoft.NET.Runtime.MonoTargets.Sdk": ("10.0.12", "9.0.20"),
    **{f"Microsoft.NETCore.App.Runtime.Mono.android-{abi}": ("10.0.12", "9.0.20")
       for abi in ("arm", "arm64", "x86", "x64")},
    **{f"Microsoft.NETCore.App.Runtime.AOT.linux-x64.Cross.android-{abi}": ("10.0.12", "9.0.20")
       for abi in ("arm", "arm64", "x86", "x64")},
}


def require_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir() or path.resolve(strict=True) != path:
        raise RuntimeError("missing or noncanonical toolchain directory")


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
        value = json.loads(path.read_bytes())
        if not isinstance(value, dict) or value.get("version") != version:
            raise RuntimeError("workload manifest version differs")
    for name, versions in PACKS.items():
        for version in versions:
            require_directory(dotnet_root / "packs" / name / version)
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
        verify_installed_versions(dotnet_root, java_root, android_root, probe)


if __name__ == "__main__":
    base = Path("/opt/fleet-rebuilder")
    bootstrap(base / "install_toolchain.py", base / "toolchain.lock.json", base / "archive-inventory.json",
              Path("/opt/dotnet"), Path("/opt/jdk"), Path("/opt/android-sdk"))
    print("toolchain version checks passed; installed-tree and protected execution authority remain unestablished")
