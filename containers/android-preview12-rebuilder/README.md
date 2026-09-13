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
