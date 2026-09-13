"""Synthetic retained profiles only; no installed SDK or executable is used."""
import importlib.util
import json
import os
from pathlib import Path
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("retained_workload_test", ROOT / "scripts/android_retained_workload.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
WARNING = ('An issue was encountered verifying workloads. For more information, '
           'run "dotnet workload update".')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def prepare(tmp_path, future=False):
    dotnet, java, android = (tmp_path / name for name in ("dotnet", "java", "android"))
    workload, mono, versions = ("10.0.112", "10.0.112", ("10.0.12", "9.0.20")) if future else (
        "10.0.111.1", "10.0.111", ("10.0.11", "9.0.19"))
    (dotnet / "sdk/10.0.110").mkdir(parents=True)
    for path in [dotnet / "dotnet", java / "bin/java", android / "platforms/android-36/android.jar",
                 *(android / "build-tools/36.0.0" / name for name in ("aapt2", "apksigner", "zipalign"))]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"nonexecuted fixture")
    lock = tmp_path / "lock.json"
    write_json(lock, {"toolchain": {"platform": "linux/amd64", "dotnet": {"version": "10.0.110"},
                                  "java": {"version": "17.0.20.1"},
                                  "android_sdk": {"api_level": 36, "build_tools_version": "36.0.0"}}})
    ids = ["microsoft.net.sdk.android", "microsoft.net.sdk.maui",
           "microsoft.net.workload.mono.toolchain.current", "microsoft.net.workload.mono.toolchain.net9"]
    manifests = [{"version": version, "workloads": {}, "packs": {}} for version in ("36.1.69", "10.0.20", mono, mono)]

    def pack(index, logical, physical, version, kind="sdk", alias="any"):
        entry = {"version": version, "kind": kind}
        if logical != physical:
            entry["alias-to"] = {alias: physical}
        manifests[index]["packs"][logical] = entry
        if kind.lower() != "library":
            (dotnet / "packs" / physical / version).mkdir(parents=True, exist_ok=True)

    for major, av, mv in ((10, "36.1.69", "10.0.20"), (9, "35.0.105", "9.0.120")):
        pack(0, f"Microsoft.Android.Sdk.net{major}", "Microsoft.Android.Sdk.Linux", av, "Sdk", "linux-x64")
        pack(1, f"Microsoft.Maui.Sdk.net{major}", "Microsoft.Maui.Sdk", mv)
    pack(0, "Microsoft.Android.Ref.36", "Microsoft.Android.Ref.36", "36.1.69", "framework")
    pack(1, "Microsoft.Maui.Controls", "Microsoft.Maui.Controls", "10.0.20", "library")
    for index, major, version in ((2, 10, versions[0]), (3, 9, versions[1])):
        for name in ("MonoAOTCompiler.Task", "MonoTargets.Sdk"):
            pack(index, f"Microsoft.NET.Runtime.{name}.net{major}", f"Microsoft.NET.Runtime.{name}", version)
        for abi in ("arm", "arm64", "x86", "x64"):
            pack(index, f"Microsoft.NETCore.App.Runtime.Mono.net{major}.android-{abi}",
                 f"Microsoft.NETCore.App.Runtime.Mono.android-{abi}", version, "framework")
            pack(index, f"Microsoft.NETCore.App.Runtime.AOT.Cross.net{major}.android-{abi}",
                 f"Microsoft.NETCore.App.Runtime.AOT.linux-x64.Cross.android-{abi}", version, "sdk", "linux-x64")
    for index, name in enumerate(("android", "maui-base", "mono-current", "mono-net9")):
        manifests[index]["workloads"][name] = {"packs": list(manifests[index]["packs"])}
    manifests[0]["workloads"]["android"]["extends"] = ["mono-current", "mono-net9"]
    manifests[1]["workloads"]["maui-android"] = {"extends": ["android", "maui-base"]}
    paths = [dotnet / "sdk-manifests/10.0.100" / name / value["version"] / "WorkloadManifest.json"
             for name, value in zip(ids, manifests)]
    for path, value in zip(paths, manifests):
        write_json(path, value)
    descriptor = dotnet / "sdk-manifests/10.0.100/workloadsets" / workload / "microsoft.net.workloads.workloadset.json"
    write_json(descriptor, {name: value["version"] + "/10.0.100" for name, value in zip(ids, manifests)})
    library = dotnet / "library-packs/microsoft.maui.controls.10.0.20.nupkg"
    library.parent.mkdir()
    with zipfile.ZipFile(library, "w") as archive:
        archive.writestr("Microsoft.Maui.Controls.nuspec", '<package><metadata><id>Microsoft.Maui.Controls</id>'
                         '<version>10.0.20</version></metadata></package>')
    args = dict(dotnet_root=dotnet, java_root=java, android_root=android, lock_path=lock,
                observed={"sdk_version": "10.0.110", "workload_version": workload,
                          "java_version_output": 'openjdk version "17.0.20.1"\nTemurin-17.0.20.1+1'})
    return args, {"lock": lock, "descriptor": descriptor, "manifest": paths[2], "library": library}, paths


@pytest.mark.parametrize("future", [False, True])
@pytest.mark.parametrize("warning", [False, True])
def test_selected_profile_and_report_are_deterministic(tmp_path, future, warning):
    args, _, _ = prepare(tmp_path, future)
    raw = args["observed"]["workload_version"]
    raw = f"{WARNING}\n{raw}\n\n" if warning else raw
    args["observed"]["workload_version"] = raw
    report = MOD.validate_retained_workload(**args)
    assert report == MOD.validate_retained_workload(**args)
    assert report["success"] is True and report["scope"] == "required_android_maui_mono_profile"
    assert report["observed"] == args["observed"] and len(report["selectedManifests"]) == 4
    assert report["observed"]["workload_version"] == raw
    assert report["workloadWarnings"] == ([WARNING] if warning else [])
    assert report["workloadCommandAccepted"] is (not warning)
    assert report["selectedWorkloadSetVersion"] == ("10.0.112" if future else "10.0.111.1")
    assert len(report["requiredPacks"]) == 26
    assert {row["version"] for row in report["requiredPacks"] if ".Mono.android-" in row["packageId"]} == (
        {"10.0.12", "9.0.20"} if future else {"10.0.11", "9.0.19"})
    assert all({"logicalId", "packageId", "version", "kind", "path"} <= row.keys() for row in report["requiredPacks"])
    assert report["inputFiles"] and all({"role", "sha256", "sizeBytes"} <= row.keys() for row in report["inputFiles"])
    assert all(report[key] is False for key in ("sdkTreesRemeasured", "observedValuesAuthenticated",
                                               "installedClosureReceipt", "releaseEligibility", "runtimeQualification"))


@pytest.mark.parametrize("key,value", [("sdk_version", "10.0.111"), ("workload_version", "10.0.113"),
                                       ("workload_version", "unrecognized warning\n10.0.111.1"),
                                       ("workload_version", "10.0.111.1\n10.0.112"),
                                       ("workload_version", WARNING + "\n\n"),
                                       ("workload_version", WARNING + " 10.0.111.1\n"),
                                       ("java_version_output", 'openjdk version "17.0.20"\nTemurin')])
def test_observation_mismatch(tmp_path, key, value):
    args, _, _ = prepare(tmp_path)
    args["observed"][key] = value
    with pytest.raises(RuntimeError, match=".+"):
        MOD.validate_retained_workload(**args)


@pytest.mark.parametrize("target", ["lock", "descriptor", "manifest"])
@pytest.mark.parametrize("fault", ["syntax", "duplicate"])
def test_invalid_json(tmp_path, target, fault):
    args, files, _ = prepare(tmp_path)
    raw = files[target].read_text()
    value = json.loads(raw)
    key = next(iter(value))
    files[target].write_text("{" if fault == "syntax" else raw[:-1] + "," + json.dumps(key) + ":" + json.dumps(value[key]) + "}")
    with pytest.raises(RuntimeError, match=".+"):
        MOD.validate_retained_workload(**args)


@pytest.mark.parametrize("fault", ["internal-version", "wrong-major", "wrong-family-version", "missing-alias", "absent-alias",
    "unsupported-alias", "traversing-alias", "platform", "descriptor-traversal", "casefold-id",
    "missing-android", "missing-maui-android", "unreachable-pack", "missing-library", "link", "fifo", "helper-hash",
    "wrong-kind", "missing-pack", "missing-manifest", "missing-selected", "directory-version", "root-link",
    "workload-platform", "duplicate-packs", "cycle", "oversized-json", "changed-snapshot"])
def test_invalid_profile_fails_closed(tmp_path, monkeypatch, fault):
    args, files, paths = prepare(tmp_path)
    path = files["descriptor"] if fault in ("descriptor-traversal", "casefold-id", "missing-selected") else (
        paths[0] if fault == "missing-android" else paths[1] if fault == "missing-maui-android" else files["manifest"])
    value = json.loads(path.read_bytes())
    logical = "Microsoft.NETCore.App.Runtime.AOT.Cross.net10.android-arm"
    if fault == "internal-version":
        value["version"] = "10.0.112"
    elif fault in ("wrong-major", "wrong-family-version"):
        value["packs"][logical]["version"] = "9.0.19" if fault == "wrong-major" else "10.0.12"
        (args["dotnet_root"] / "packs" / value["packs"][logical]["alias-to"]["linux-x64"] /
         value["packs"][logical]["version"]).mkdir(parents=True, exist_ok=True)
    elif fault == "absent-alias":
        value["packs"][logical].pop("alias-to")
    elif fault in ("missing-alias", "unsupported-alias", "traversing-alias"):
        value["packs"][logical]["alias-to"] = {"missing-alias": {}, "unsupported-alias": {"win-x64": "other"},
                                              "traversing-alias": {"linux-x64": "../escape"}}[fault]
    elif fault == "platform":
        lock = json.loads(files["lock"].read_bytes())
        lock["toolchain"]["platform"] = "linux/arm64"
        write_json(files["lock"], lock)
    elif fault == "descriptor-traversal":
        value["microsoft.net.sdk.android"] = "../escape/10.0.100"
    elif fault == "casefold-id":
        value["Microsoft.NET.Sdk.Android"] = value["microsoft.net.sdk.android"]
    elif fault in ("missing-android", "missing-maui-android"):
        value["workloads"]["unrelated"] = value["workloads"].pop(fault.removeprefix("missing-"))
    elif fault == "unreachable-pack":
        value["workloads"]["mono-current"]["packs"].remove(logical)
    elif fault == "missing-library":
        files["library"].unlink()
    elif fault == "helper-hash":
        monkeypatch.setattr(MOD, "BOOTSTRAP_SHA256", "0" * 64)
    elif fault == "wrong-kind":
        value["packs"][logical]["kind"] = "framework"
    elif fault == "missing-pack":
        (args["dotnet_root"] / "packs" / value["packs"][logical]["alias-to"]["linux-x64"] /
         value["packs"][logical]["version"]).rmdir()
    elif fault == "missing-selected":
        value.pop("microsoft.net.sdk.android")
    elif fault == "workload-platform":
        value["workloads"]["mono-current"]["platforms"] = ["win-x64"]
    elif fault == "duplicate-packs":
        value["workloads"]["mono-current"]["packs"].append(logical)
    elif fault == "cycle":
        value["workloads"]["mono-current"]["extends"] = ["android"]
    elif fault == "changed-snapshot":
        original_read = MOD._read
        def changing_read(candidate, *args, **kwargs):
            result = original_read(candidate, *args, **kwargs)
            if Path(candidate) == files["manifest"]:
                monkeypatch.setattr(MOD, "_read", original_read)
                files["manifest"].write_bytes(files["manifest"].read_bytes() + b" ")
            return result
        monkeypatch.setattr(MOD, "_read", changing_read)
    write_json(path, value)
    if fault in ("link", "fifo"):
        target = path.with_name("identical.json")
        path.rename(target)
        path.symlink_to(target) if fault == "link" else os.mkfifo(path)
    elif fault == "missing-manifest":
        path.unlink()
    elif fault == "directory-version":
        path.parent.rename(path.parent.with_name("10.0.112"))
    elif fault == "root-link":
        target = tmp_path / "real-dotnet"
        args["dotnet_root"].rename(target)
        args["dotnet_root"].symlink_to(target, target_is_directory=True)
    elif fault == "oversized-json":
        path.write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(RuntimeError, match=".+"):
        MOD.validate_retained_workload(**args)
