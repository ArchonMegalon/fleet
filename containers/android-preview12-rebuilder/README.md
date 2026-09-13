# Android rebuild image stages

The default `release-rebuilder` stage installs the locked toolchain and keeps
the existing dormant, credential-free entry point. This recipe does not itself
authorize a rebuild, signing or Play publication.

`--target os-build-tools` stops after the pinned Ubuntu snapshot transaction.
It installs the OS tools and records `/opt/fleet-rebuilder/os-package-inventory.txt`
without downloading or modifying a .NET, Java or Android SDK. This stage supports
reuse of separately qualified SDK trees mounted read-only by the isolated runtime.

Use the repository root as build context with the Dockerfile-specific deny-by-default
ignore file. Do not pass secrets, SSH agents, host networking or SDK directories as
build inputs. Apply build-container resource limits, not merely client-process limits.

An OS-stage image is not a complete builder. Before runtime admission it needs its
own observed image ID and immutable repository digest; the base-image digest must
never stand in for the derived image. The mounted SDK closure, required utilities,
source inputs, dependency access and build receipt must still be verified. In
particular, an OS-stage build does not resolve the current network-isolated runtime
versus online GitHub/NuGet restore mismatch.

Retain only the active, identity-checked image while its build transaction is
unfinished. A local retention tag prevents dangling-image cleanup; it does not
replace immutable image identity or constitute release evidence.

`scripts/android_retained_workload.py` separately validates a retained SDK's
required Android/Maui/Mono profile without running or installing anything. Call
`validate_retained_workload(dotnet_root=..., java_root=..., android_root=...,
lock_path=..., observed={"sdk_version": ..., "workload_version": ...,
"java_version_output": ...})` with absolute canonical paths, the existing
external-rebuilder lock, and caller-captured SDK/workload stdout and Java
`-version` output from the intended namespace. Capture these outputs freshly;
the validator cannot authenticate them and never substitutes installation history.
Pass raw output, including warnings. The known workload-verification warning may
select a descriptor for metadata diagnosis, but is preserved in `workloadWarnings`
with `workloadCommandAccepted=false`; unknown prefixes or multiple versions fail.
`runtimeQualification` remains false even when metadata checks succeed.
It follows the reported workloadset descriptor and selected manifests, resolves
Linux x64/`any` aliases, checks required pack directories and validates the Maui
Controls library archive using the source-pinned existing bootstrap helper.
Its deterministic observation binds selected input bytes, not entire pack trees.
It neither validates all installed workloads nor emits an installed-closure
receipt, qualifies an image, changes the installation recipe or enables release.
The dormant lock and all admission, custody, signing and publication gates remain
unchanged; a successful observation must not replace a missing closure receipt.
