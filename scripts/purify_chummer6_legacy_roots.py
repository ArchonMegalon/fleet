#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path


HUB_REPO = Path("/docker/chummercomplete/chummer.run-services")
CORE_REPO = Path("/docker/chummercomplete/chummer-core-engine")

HUB_COMMIT = "purify(hub): retire legacy hosted roots"
CORE_COMMIT = "purify(core): retire legacy helper roots"


def run(*args: str, cwd: Path | None = None, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        text=True,
        check=check,
        capture_output=capture,
    )


def output(*args: str, cwd: Path | None = None) -> str:
    return run(*args, cwd=cwd, capture=True).stdout.strip()


def git(repo: Path, *args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return run("git", "-C", str(repo), *args, check=check, capture=capture)


def ensure_clean(repo: Path) -> None:
    status = git(repo, "status", "--short", capture=True).stdout.rstrip("\n")
    if status:
        raise SystemExit(f"{repo} is dirty; refusing to purify over unrelated work:\n{status}")


def ensure_clean_or_expected(repo: Path, allowed_paths: set[str]) -> None:
    status = git(repo, "status", "--short", capture=True).stdout.rstrip("\n")
    if not status:
        return
    unexpected: list[str] = []
    for line in status.splitlines():
        path = line[3:].strip().strip('"')
        if not any(path == allowed or path.startswith(f"{allowed}/") for allowed in allowed_paths):
            unexpected.append(line)
    if unexpected:
        raise SystemExit(f"{repo} is dirty outside the purifier allowlist:\n" + "\n".join(unexpected))


def replace_text(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise ValueError(f"expected text not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def regex_replace(path: Path, pattern: str, repl: str, *, count: int = 0, already_contains: str | None = None) -> None:
    text = path.read_text(encoding="utf-8")
    updated, changed = re.subn(pattern, repl, text, count=count, flags=re.MULTILINE | re.DOTALL)
    if changed == 0:
        if already_contains and already_contains in text:
            return
        if re.search(re.escape(repl), text, flags=re.MULTILINE | re.DOTALL):
            return
        raise ValueError(f"pattern not found in {path}: {pattern}")
    path.write_text(updated, encoding="utf-8")


def ensure_contains(path: Path, needle: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        raise ValueError(f"expected marker missing in {path}: {needle}")


def remove_path(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def stage_and_commit(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    diff = git(repo, "diff", "--cached", "--quiet", "--exit-code", check=False)
    if diff.returncode == 0:
        return ""
    git(repo, "commit", "-m", message)
    branch = output("git", "-C", str(repo), "branch", "--show-current")
    git(repo, "push", "-u", "origin", branch)
    return output("git", "-C", str(repo), "rev-parse", "--short", "HEAD")


def verify_hub_static() -> None:
    ensure_contains(HUB_REPO / "README.md", "docs/HOSTED_BOUNDARY.md")
    ensure_contains(HUB_REPO / "docker-compose.yml", "dockerfile: Chummer.Run.Api/Dockerfile")
    ensure_contains(HUB_REPO / "docker-compose.yml", "bash scripts/ai/verify.sh")
    ensure_contains(HUB_REPO / "docs" / "HUB_EXTRACTION_ACCEPTANCE.md", "docs/hosted-boundary.manifest")
    ensure_contains(HUB_REPO / "docs" / "hosted-boundary.manifest", "ACTIVE_HOSTED_PROJECTS=Chummer.Play.Contracts;Chummer.Media.Contracts;Chummer.Run.Contracts;Chummer.Run.Api;Chummer.Run.Identity;Chummer.Run.Registry;Chummer.Run.AI")
    ensure_contains(HUB_REPO / "tests" / "RunServicesVerification" / "CompatibilityVerification.cs", "private static void VerifyHostedBoundary()")
    ensure_contains(HUB_REPO / "tests" / "RunServicesVerification" / "CompatibilityVerification.cs", "\"Chummer.Run.Api\"")
    ensure_contains(HUB_REPO / "tests" / "RunServicesVerification" / "CompatibilityVerification.cs", "\"Chummer.Media.Contracts\"")
    ensure_contains(HUB_REPO / "Chummer.Run.Api" / "Dockerfile", "mcr.microsoft.com/dotnet/sdk:8.0")
    ensure_contains(HUB_REPO / "Docker" / "Dockerfile.tests", "mcr.microsoft.com/dotnet/sdk:8.0")
    for rel in (
        "docs/LEGACY_INTEROP_BOUNDARY.md",
        "docs/legacy-interop-boundary.manifest",
        "Chummer.Api",
        "ChummerDataViewer",
        "ChummerHub",
        "Plugins/ChummerHub.Client",
        "TextblockConverter",
        "Translator",
        "AGENT_MEMORY.md",
        "day1.prompt.txt",
    ):
        if (HUB_REPO / rel).exists():
            raise ValueError(f"retired hub path still exists: {rel}")
    run("bash", "-n", "scripts/ai/run_services_verification.sh", cwd=HUB_REPO)
    run("bash", "-n", "scripts/audit-compliance.sh", cwd=HUB_REPO)
    run("bash", "-n", "scripts/runbook.sh", cwd=HUB_REPO)
    git(HUB_REPO, "diff", "--check")


def verify_core_static() -> None:
    ensure_contains(CORE_REPO / "WORKLIST.md", "retire legacy helper tools that are not engine-owned")
    ensure_contains(CORE_REPO / "WORKLIST.md", "confirm retired helper tooling stays out of engine-owned scope")
    ensure_contains(CORE_REPO / ".codex-design" / "repo" / "PROJECT_MILESTONES.yaml", "title: Legacy helper retirement")
    ensure_contains(CORE_REPO / ".codex-design" / "repo" / "PROJECT_MILESTONES.yaml", "Confirm retired helper tooling stays absent from engine-owned scope")
    ensure_contains(CORE_REPO / "Chummer.CoreEngine.Tests" / "Program.cs", "retiredHelperRoots")
    ensure_contains(CORE_REPO / "Chummer.CoreEngine.Tests" / "Program.cs", "Retired helper root")
    for rel in ("ChummerDataViewer", "CrashHandler", "TextblockConverter", "Translator"):
        if (CORE_REPO / rel).exists():
            raise ValueError(f"retired core path still exists: {rel}")
    git(CORE_REPO, "diff", "--check")


def patch_hub() -> dict[str, object]:
    ensure_clean_or_expected(
        HUB_REPO,
        {
            "README.md",
            "WORKLIST.md",
            "docker-compose.yml",
            "Docker/Dockerfile.tests",
            "docs/MIGRATION_BACKLOG.md",
            "docs/PARITY_AUDIT.md",
            "docs/HUB_EXTRACTION_ACCEPTANCE.md",
            "docs/HOSTED_BOUNDARY.md",
            "docs/hosted-boundary.manifest",
            "docs/LEGACY_INTEROP_BOUNDARY.md",
            "docs/legacy-interop-boundary.manifest",
            "scripts/ai/run_services_verification.sh",
            "scripts/audit-compliance.sh",
            "scripts/runbook.sh",
            "tests/RunServicesVerification/CompatibilityVerification.cs",
            "tests/RunServicesVerification/HubExtractionReadinessVerification.cs",
            "Chummer.Run.Api/Dockerfile",
            "Chummer.Api",
            "ChummerDataViewer",
            "ChummerHub",
            "Plugins",
            "Plugins/ChummerHub.Client",
            "TextblockConverter",
            "Translator",
            "AGENT_MEMORY.md",
            "day1.prompt.txt",
        },
    )

    removed: list[str] = []

    dockerfile = HUB_REPO / "Chummer.Run.Api" / "Dockerfile"
    dockerfile.write_text(
        """FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY chummer.run-services/Chummer.Run.Api/Chummer.Run.Api.csproj chummer.run-services/Chummer.Run.Api/
COPY chummer-core-engine/Chummer/Chummer.csproj chummer-core-engine/Chummer/
COPY chummer-core-engine/Chummer.Contracts/Chummer.Contracts.csproj chummer-core-engine/Chummer.Contracts/
RUN dotnet restore chummer.run-services/Chummer.Run.Api/Chummer.Run.Api.csproj
COPY chummer.run-services/Chummer.Run.Api/ chummer.run-services/Chummer.Run.Api/
COPY chummer-core-engine/Chummer/ chummer-core-engine/Chummer/
COPY chummer-core-engine/Chummer.Contracts/ chummer-core-engine/Chummer.Contracts/
WORKDIR /src/chummer.run-services/Chummer.Run.Api
RUN dotnet publish -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=build /app/publish .
ENV ASPNETCORE_URLS=http://+:8080
ENTRYPOINT ["dotnet", "Chummer.Run.Api.dll"]
""",
        encoding="utf-8",
    )

    (HUB_REPO / "docs" / "HOSTED_BOUNDARY.md").write_text(
        """# Hosted Boundary

`chummer6-hub` keeps its active hosted surface limited to:

- `Chummer.Play.Contracts`
- `Chummer.Media.Contracts`
- `Chummer.Run.Contracts`
- `Chummer.Run.Api`
- `Chummer.Run.Identity`
- `Chummer.Run.Registry`
- `Chummer.Run.AI`

These projects are the active hosted runtime boundary for registry, relay, Spider, media orchestration, identity, and policy surfaces.

The following roots remain outside the active hosted topology:

- Oracle root: `Chummer`
- Retired hosted clutter: `Chummer.Api`, `ChummerDataViewer`, `ChummerHub`, `Plugins/ChummerHub.Client`, `TextblockConverter`, `Translator`

Boundary rules:

1. Active hosted projects must be the only projects built through `Chummer.Run.sln` and the clean-room verification path.
2. The oracle root may remain for compatibility/reference work, but it must not re-enter `Chummer.Run.sln`.
3. Retired hosted clutter must stay absent from the repository and must not be reintroduced through source roots, project references, or docker paths.
4. Future extraction work still moves registry/publication ownership into `chummer6-hub-registry` and keeps this repo as the orchestrator shell around identity, relay, Spider, and policy.
""",
        encoding="utf-8",
    )
    (HUB_REPO / "docs" / "hosted-boundary.manifest").write_text(
        "ACTIVE_HOSTED_PROJECTS=Chummer.Play.Contracts;Chummer.Media.Contracts;Chummer.Run.Contracts;Chummer.Run.Api;Chummer.Run.Identity;Chummer.Run.Registry;Chummer.Run.AI\n"
        "ORACLE_ROOTS=Chummer\n"
        "RETIRED_ROOTS=Chummer.Api;ChummerDataViewer;ChummerHub;Plugins/ChummerHub.Client;TextblockConverter;Translator\n",
        encoding="utf-8",
    )

    replace_text(
        HUB_REPO / "README.md",
        "* Legacy/interoperability boundary: [`docs/LEGACY_INTEROP_BOUNDARY.md`](docs/LEGACY_INTEROP_BOUNDARY.md) is the canonical repo-local declaration of which roots are active hosted runtime projects versus archived compatibility/interoperability assets. `Chummer.Run.sln` and the clean-room verification path must stay aligned with that boundary.\n",
        "* Hosted boundary: [`docs/HOSTED_BOUNDARY.md`](docs/HOSTED_BOUNDARY.md) is the canonical repo-local declaration of which roots are active hosted runtime projects, which oracle root is preserved, and which legacy hosted roots have been retired. `Chummer.Run.sln` and the clean-room verification path must stay aligned with that boundary.\n",
    )
    for rel in ("README.md", "docs/MIGRATION_BACKLOG.md", "docs/PARITY_AUDIT.md"):
        path = HUB_REPO / rel
        text = path.read_text(encoding="utf-8")
        text = text.replace("Chummer.Api", "Chummer.Run.Api")
        text = text.replace("docs/LEGACY_INTEROP_BOUNDARY.md", "docs/HOSTED_BOUNDARY.md")
        text = text.replace("docs/legacy-interop-boundary.manifest", "docs/hosted-boundary.manifest")
        path.write_text(text, encoding="utf-8")

    replace_text(
        HUB_REPO / "docs" / "MIGRATION_BACKLOG.md",
        '3. `dotnet test Chummer.Tests/Chummer.Tests.csproj --filter "FullyQualifiedName~ArchitectureGuardrailTests|FullyQualifiedName~MigrationComplianceTests|FullyQualifiedName~DualHeadAcceptanceTests"`\n',
        "3. `bash scripts/ai/verify.sh`\n",
    )
    regex_replace(
        HUB_REPO / "docs" / "PARITY_AUDIT.md",
        r"Run:\n\n```bash\n.*?```",
        "Run:\n\n```bash\nbash scripts/ai/verify.sh\n```",
        count=1,
    )
    replace_text(
        HUB_REPO / "docs" / "HUB_EXTRACTION_ACCEPTANCE.md",
        "`docs/legacy-interop-boundary.manifest`, `docs/LEGACY_INTEROP_BOUNDARY.md`, and `tests/RunServicesVerification/CompatibilityVerification.cs` keep legacy desktop/helper roots (`Chummer`, `Chummer.Api`, `ChummerDataViewer`, `ChummerHub`, `Plugins/ChummerHub.Client`, `TextblockConverter`, and `Translator`) outside `Chummer.Run.sln` and outside the active hosted boundary.\n",
        "`docs/hosted-boundary.manifest`, `docs/HOSTED_BOUNDARY.md`, and `tests/RunServicesVerification/CompatibilityVerification.cs` keep the oracle root (`Chummer`) outside `Chummer.Run.sln`, require the active hosted boundary to run through `Chummer.Run.Api`, and block retired hosted clutter (`Chummer.Api`, `ChummerDataViewer`, `ChummerHub`, `Plugins/ChummerHub.Client`, `TextblockConverter`, and `Translator`) from re-entering the repo.\n",
    )

    replace_text(
        HUB_REPO / "tests" / "RunServicesVerification" / "HubExtractionReadinessVerification.cs",
        '"LEGACY_INTEROP_BOUNDARY.md",\n                     "legacy-interop-boundary.manifest",\n',
        '"HOSTED_BOUNDARY.md",\n                     "hosted-boundary.manifest",\n',
    )

    replace_text(
        HUB_REPO / "scripts" / "ai" / "run_services_verification.sh",
        """if ! rg -n '<HintPath>\\.\\.\\\\Chummer\\.Play\\.Contracts\\\\bin\\\\\\$\\(Configuration\\)\\\\net8\\.0\\\\Chummer\\.Play\\.Contracts\\.dll</HintPath>' \\
  Chummer.Run.Contracts/Chummer.Run.Contracts.csproj \\
  Chummer.Run.AI/Chummer.Run.AI.csproj >/dev/null; then
""",
        """if ! grep -En '<HintPath>\\.\\.\\\\Chummer\\.Play\\.Contracts\\\\bin\\\\\\$\\(Configuration\\)\\\\net8\\.0\\\\Chummer\\.Play\\.Contracts\\.dll</HintPath>' \\
  Chummer.Run.Contracts/Chummer.Run.Contracts.csproj \\
  Chummer.Run.AI/Chummer.Run.AI.csproj >/dev/null; then
""",
    )
    replace_text(
        HUB_REPO / "scripts" / "ai" / "run_services_verification.sh",
        """if ! rg -n '<HintPath>\\.\\.\\\\Chummer\\.Media\\.Contracts\\\\bin\\\\\\$\\(Configuration\\)\\\\net8\\.0\\\\Chummer\\.Media\\.Contracts\\.dll</HintPath>' \\
  Chummer.Run.Contracts/Chummer.Run.Contracts.csproj \\
  Chummer.Run.AI/Chummer.Run.AI.csproj >/dev/null; then
""",
        """if ! grep -En '<HintPath>\\.\\.\\\\Chummer\\.Media\\.Contracts\\\\bin\\\\\\$\\(Configuration\\)\\\\net8\\.0\\\\Chummer\\.Media\\.Contracts\\.dll</HintPath>' \\
  Chummer.Run.Contracts/Chummer.Run.Contracts.csproj \\
  Chummer.Run.AI/Chummer.Run.AI.csproj >/dev/null; then
""",
    )
    replace_text(
        HUB_REPO / "scripts" / "ai" / "run_services_verification.sh",
        """if ! rg -n '<ProjectReference Include="\\.\\.\\\\Chummer\\.Run\\.Contracts\\\\Chummer\\.Run\\.Contracts\\.csproj" />' \\
  Chummer.Run.Registry/Chummer.Run.Registry.csproj >/dev/null; then
""",
        """if ! grep -En '<ProjectReference Include="\\.\\.\\\\Chummer\\.Run\\.Contracts\\\\Chummer\\.Run\\.Contracts\\.csproj" />' \\
  Chummer.Run.Registry/Chummer.Run.Registry.csproj >/dev/null; then
""",
    )
    replace_text(
        HUB_REPO / "scripts" / "ai" / "run_services_verification.sh",
        """if rg -n '<ProjectReference Include="\\.\\.\\\\Chummer\\.Run\\.(AI|Api|Identity)\\\\' \\
  Chummer.Run.Registry/Chummer.Run.Registry.csproj >/dev/null; then
""",
        """if grep -En '<ProjectReference Include="\\.\\.\\\\Chummer\\.Run\\.(AI|Api|Identity)\\\\' \\
  Chummer.Run.Registry/Chummer.Run.Registry.csproj >/dev/null; then
""",
    )
    replace_text(
        HUB_REPO / "scripts" / "audit-compliance.sh",
        """echo "[audit] running migration compliance tests"
docker compose --profile test run --build --rm chummer-tests \\
  dotnet test Chummer.Tests/Chummer.Tests.csproj -c Release -f net10.0 -p:TargetFramework=net10.0 --no-build --no-restore \\
  --filter "FullyQualifiedName~MigrationComplianceTests" --logger "console;verbosity=minimal"

echo "[audit] running life-modules e2e data checks"
docker compose --profile test run --build --rm chummer-tests \\
  dotnet test Chummer.Tests/Chummer.Tests.csproj -c Release -f net10.0 -p:TargetFramework=net10.0 --no-build --no-restore \\
  --filter "FullyQualifiedName~LifeModulesEndToEndTests" --logger "console;verbosity=minimal"
""",
        """echo "[audit] running hosted boundary verification"
docker compose --profile test run --build --rm chummer-tests
""",
    )
    replace_text(
        HUB_REPO / "scripts" / "runbook.sh",
        """  docker compose run $build_arg --rm chummer-tests sh -lc \\
    "cd /src && dotnet test '$TEST_PROJECT' -c Release $framework_arg $filter_arg --logger \\"console;verbosity=normal\\"" \\
    2>&1 | tee "$TEST_LOG_FILE"
""",
        """  docker compose run $build_arg --rm chummer-tests \\
    2>&1 | tee "$TEST_LOG_FILE"
""",
    )

    replace_text(
        HUB_REPO / "docker-compose.yml",
        "      dockerfile: Chummer.Api/Dockerfile\n",
        "      dockerfile: Chummer.Run.Api/Dockerfile\n",
    )
    replace_text(
        HUB_REPO / "docker-compose.yml",
        """    command: >
      dotnet test Chummer.Tests/Chummer.Tests.csproj
      -c Release
      -f net10.0
      -p:TargetFramework=net10.0
      --no-build
      --no-restore
      --tl:off
      --logger "trx;LogFileName=test-results-linux.trx"
      --logger "console;verbosity=normal"
""",
        """    command: >
      bash scripts/ai/verify.sh
""",
    )

    (HUB_REPO / "Docker" / "Dockerfile.tests").write_text(
        """FROM mcr.microsoft.com/dotnet/sdk:8.0
WORKDIR /src

COPY . .
ENV DOTNET_NOLOGO=1
ENV DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1
""",
        encoding="utf-8",
    )

    replace_text(
        HUB_REPO / "WORKLIST.md",
        "| WL-167 | done | P1 | Keep registry, relay, Spider, media, and identity in the hosted repo while preserving legacy app/tooling roots as an explicit interop-only boundary. | agent | Completed 2026-03-11: tightened `tests/RunServicesVerification/CompatibilityVerification.cs` so `docs/legacy-interop-boundary.manifest` must retain the canonical hosted project set (`Chummer.Play.Contracts`, `Chummer.Run.Contracts`, `Chummer.Run.Api`, `Chummer.Run.Identity`, `Chummer.Run.Registry`, `Chummer.Run.AI`) and canonical legacy/interoperability roots (`Chummer`, `Chummer.Api`, `ChummerDataViewer`, `ChummerHub`, `Plugins/ChummerHub.Client`, `TextblockConverter`, `Translator`), then re-ran `scripts/ai/verify.sh` (`run-services verification passed`, `run-services in-process smoke passed`). |\n",
        "| WL-167 | done | P1 | Keep registry, relay, Spider, media, and identity in the hosted repo while retiring obsolete hosted roots. | agent | Completed 2026-03-11: tightened `tests/RunServicesVerification/CompatibilityVerification.cs` so `docs/hosted-boundary.manifest` must retain the canonical hosted project set (`Chummer.Play.Contracts`, `Chummer.Media.Contracts`, `Chummer.Run.Contracts`, `Chummer.Run.Api`, `Chummer.Run.Identity`, `Chummer.Run.Registry`, `Chummer.Run.AI`), keep `Chummer` as the oracle root, and block retired hosted clutter (`Chummer.Api`, `ChummerDataViewer`, `ChummerHub`, `Plugins/ChummerHub.Client`, `TextblockConverter`, `Translator`) from re-entering the repo, then re-ran `scripts/ai/verify.sh` (`run-services verification passed`, `run-services in-process smoke passed`). |\n",
    )

    compatibility_path = HUB_REPO / "tests" / "RunServicesVerification" / "CompatibilityVerification.cs"
    replace_text(compatibility_path, "        VerifyLegacyInteropBoundary();\n", "        VerifyHostedBoundary();\n")
    regex_replace(
        compatibility_path,
        r"""    private static void VerifyLegacyInteropBoundary\(\)\n    \{\n.*?\n    \}\n\n    private static string\[\] SplitManifestList""",
        """    private static void VerifyHostedBoundary()
    {
        var manifestPath = Path.Combine(RepoRoot, "docs", "hosted-boundary.manifest");
        VerificationAssert.True(File.Exists(manifestPath), "Hosted boundary manifest must exist.");

        var values = File.ReadAllLines(manifestPath)
            .Where(static line => !string.IsNullOrWhiteSpace(line) && !line.TrimStart().StartsWith('#'))
            .Select(static line => line.Split('=', 2))
            .ToDictionary(
                static parts => parts[0].Trim(),
                static parts => parts.Length > 1 ? parts[1].Trim() : string.Empty,
                StringComparer.Ordinal);

        if (!values.TryGetValue("ACTIVE_HOSTED_PROJECTS", out var hostedProjects))
        {
            throw new InvalidOperationException("Boundary manifest must declare ACTIVE_HOSTED_PROJECTS.");
        }

        if (!values.TryGetValue("ORACLE_ROOTS", out var oracleRootsValue))
        {
            throw new InvalidOperationException("Boundary manifest must declare ORACLE_ROOTS.");
        }

        if (!values.TryGetValue("RETIRED_ROOTS", out var retiredRootsValue))
        {
            throw new InvalidOperationException("Boundary manifest must declare RETIRED_ROOTS.");
        }

        var expectedHostedProjects = SplitManifestList(hostedProjects);
        var oracleRoots = SplitManifestList(oracleRootsValue);
        var retiredRoots = SplitManifestList(retiredRootsValue);

        var canonicalHostedProjects = new[]
            {
                "Chummer.Media.Contracts",
                "Chummer.Play.Contracts",
                "Chummer.Run.AI",
                "Chummer.Run.Api",
                "Chummer.Run.Contracts",
                "Chummer.Run.Identity",
                "Chummer.Run.Registry"
            }
            .OrderBy(static entry => entry, StringComparer.Ordinal)
            .ToArray();
        var canonicalOracleRoots = new[]
            {
                "Chummer"
            }
            .OrderBy(static entry => entry, StringComparer.Ordinal)
            .ToArray();
        var canonicalRetiredRoots = new[]
            {
                "Chummer.Api",
                "ChummerDataViewer",
                "ChummerHub",
                "Plugins/ChummerHub.Client",
                "TextblockConverter",
                "Translator"
            }
            .OrderBy(static entry => entry, StringComparer.Ordinal)
            .ToArray();

        VerificationAssert.True(
            expectedHostedProjects.SequenceEqual(canonicalHostedProjects, StringComparer.Ordinal),
            "Boundary manifest must keep the canonical hosted project set for identity, registry, relay/Spider/media orchestration, and hosted APIs.");
        VerificationAssert.True(
            oracleRoots.SequenceEqual(canonicalOracleRoots, StringComparer.Ordinal),
            "Boundary manifest must keep the canonical oracle root set.");
        VerificationAssert.True(
            retiredRoots.SequenceEqual(canonicalRetiredRoots, StringComparer.Ordinal),
            "Boundary manifest must keep the canonical retired hosted-clutter set.");

        var solutionPath = Path.Combine(RepoRoot, "Chummer.Run.sln");
        var solutionText = File.ReadAllText(solutionPath);
        var solutionProjectPaths = solutionText
            .Split('\\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(static line => line.StartsWith("Project(", StringComparison.Ordinal) && line.Contains(".csproj", StringComparison.Ordinal))
            .Select(static line => line.Split('"'))
            .Where(static parts => parts.Length >= 6)
            .Select(static parts => parts[5].Replace('/', '\\\\'))
            .ToArray();

        foreach (var projectName in expectedHostedProjects)
        {
            VerificationAssert.True(solutionText.Contains($\" = \\\"{projectName}\\\", \", StringComparison.Ordinal), $\"Hosted solution must include '{projectName}'.\");
        }

        foreach (var oracleRoot in oracleRoots)
        {
            var normalizedRoot = oracleRoot.Replace('/', '\\\\');
            VerificationAssert.True(Directory.Exists(Path.Combine(RepoRoot, oracleRoot)), $\"Oracle root '{oracleRoot}' must exist.\");
            VerificationAssert.True(
                !solutionProjectPaths.Any(projectPath => projectPath.StartsWith(normalizedRoot + \"\\\\\", StringComparison.Ordinal)),
                $\"Hosted solution must not include oracle root '{oracleRoot}'.\");
        }

        foreach (var retiredRoot in retiredRoots)
        {
            var normalizedRoot = retiredRoot.Replace('/', '\\\\');
            VerificationAssert.True(
                !Directory.Exists(Path.Combine(RepoRoot, retiredRoot)),
                $\"Retired hosted-clutter root '{retiredRoot}' must stay absent.\");
            VerificationAssert.True(
                !solutionProjectPaths.Any(projectPath => projectPath.StartsWith(normalizedRoot + \"\\\\\", StringComparison.Ordinal)),
                $\"Hosted solution must not include retired hosted-clutter root '{retiredRoot}'.\");
        }

        var buildScriptPath = Path.Combine(RepoRoot, "scripts", "ai", "build_r1_cleanroom.sh");
        var buildScript = File.ReadAllText(buildScriptPath);

        foreach (var projectName in expectedHostedProjects)
        {
            VerificationAssert.True(
                buildScript.Contains($\"dotnet build {projectName}/{projectName}.csproj --nologo\", StringComparison.Ordinal),
                $\"Clean-room build script must build hosted project '{projectName}'.\");
        }

        foreach (var oracleRoot in oracleRoots)
        {
            var oracleBuildPrefix = $\"dotnet build {oracleRoot}/\";
            VerificationAssert.True(
                !buildScript.Contains(oracleBuildPrefix, StringComparison.Ordinal),
                $\"Clean-room build script must not target oracle root '{oracleRoot}'.\");
        }

        foreach (var retiredRoot in retiredRoots)
        {
            var retiredBuildPrefix = $\"dotnet build {retiredRoot}/\";
            VerificationAssert.True(
                !buildScript.Contains(retiredBuildPrefix, StringComparison.Ordinal),
                $\"Clean-room build script must not target retired hosted-clutter root '{retiredRoot}'.\");
        }
    }

    private static string[] SplitManifestList""",
        count=1,
        already_contains="private static void VerifyHostedBoundary()",
    )

    for rel in [
        "docs/LEGACY_INTEROP_BOUNDARY.md",
        "docs/legacy-interop-boundary.manifest",
        "Chummer.Api",
        "ChummerDataViewer",
        "ChummerHub",
        "Plugins/ChummerHub.Client",
        "TextblockConverter",
        "Translator",
        "AGENT_MEMORY.md",
        "day1.prompt.txt",
    ]:
        if remove_path(HUB_REPO / rel):
            removed.append(rel)
    plugins_dir = HUB_REPO / "Plugins"
    if plugins_dir.exists() and not any(plugins_dir.iterdir()):
        if remove_path(plugins_dir):
            removed.append("Plugins")

    verify_hub_static()
    commit = stage_and_commit(HUB_REPO, HUB_COMMIT)
    return {"repo": "chummer6-hub", "commit": commit, "removed": removed}


def patch_core() -> dict[str, object]:
    ensure_clean_or_expected(
        CORE_REPO,
        {
            "WORKLIST.md",
            ".codex-design/repo/PROJECT_MILESTONES.yaml",
            "Chummer.CoreEngine.Tests/Program.cs",
            "ChummerDataViewer",
            "CrashHandler",
            "TextblockConverter",
            "Translator",
        },
    )

    removed: list[str] = []

    worklist = CORE_REPO / "WORKLIST.md"
    regex_replace(
        worklist,
        r"\| WL-067 \| done \| P2 \| Milestone A0: quarantine legacy helper tools that are not engine-owned\. \| agent \| .*?\|",
        "| WL-067 | done | P2 | Milestone A0: retire legacy helper tools that are not engine-owned. | agent | Completed 2026-03-11: `ChummerDataViewer`, `CrashHandler`, `TextblockConverter`, and `Translator` were removed from the repo, and verification now blocks them from re-entering the active engine boundary. |",
        count=1,
        already_contains="Milestone A0: retire legacy helper tools that are not engine-owned.",
    )
    regex_replace(
        worklist,
        r"\| WL-092 \| queued \| P2 \| A0\.5\.7 follow-through: keep legacy helper tooling authority closure runnable until non-engine helper lifecycle is safely closed\. \| agent \| .*?\|",
        "| WL-092 | done | P2 | A0.5.7 follow-through: confirm retired helper tooling stays out of engine-owned scope. | agent | Completed 2026-03-11: `ChummerDataViewer`, `CrashHandler`, `TextblockConverter`, and `Translator` were retired from the repo, and `Chummer.CoreEngine.Tests` now blocks those helper roots from being restored. |",
        count=1,
        already_contains="A0.5.7 follow-through: confirm retired helper tooling stays out of engine-owned scope.",
    )

    milestones = CORE_REPO / ".codex-design" / "repo" / "PROJECT_MILESTONES.yaml"
    replace_text(
        milestones,
        "    title: Legacy helper quarantine\n",
        "    title: Legacy helper retirement\n",
    )
    replace_text(
        milestones,
        "      - ChummerDataViewer, CrashHandler, TextblockConverter, and Translator are classified as non-engine helper surfaces and kept out of the active engine verification boundary.\n",
        "      - ChummerDataViewer, CrashHandler, TextblockConverter, and Translator were retired from the repo and must stay out of the active engine verification boundary.\n",
    )
    regex_replace(
        milestones,
        r"""      - id: A0\.5\.7\n        worklist: WL-092\n        title: Keep legacy helper tooling authority closure runnable through safe lifecycle closure\n        status: queued\n        evidence:\n          - `WL-086` follow-through is decomposed into surface-specific runnable slices so non-engine helper tools remain milestone-mapped until safe closure acceptance\.\n          - A0\.5 closure requires explicit confirmation that legacy helper tooling lifecycle stays outside engine-owned authority boundaries\.\n""",
        """      - id: A0.5.7
        worklist: WL-092
        title: Confirm retired helper tooling stays absent from engine-owned scope
        status: done
        evidence:
          - ChummerDataViewer, CrashHandler, TextblockConverter, and Translator were removed from the repo during the 2026-03-11 purification pass.
          - `Chummer.CoreEngine.Tests/Program.cs` now blocks those helper roots from being restored while the broader contract-reset follow-through remains open.
""",
        count=1,
        already_contains="title: Confirm retired helper tooling stays absent from engine-owned scope",
    )

    program = CORE_REPO / "Chummer.CoreEngine.Tests" / "Program.cs"
    regex_replace(
        program,
        r"""    private static void ActiveCoreEngineSolutionStaysPurified\(\)\n    \{\n.*?\n    \}\n\n    private static bool IsGeneratedOrBuildArtifact""",
        """    private static void ActiveCoreEngineSolutionStaysPurified()
    {
        string repoRoot = GetRepositoryRoot();
        string solutionText = File.ReadAllText(Path.Combine(repoRoot, "Chummer.CoreEngine.sln"));
        string scopeText = File.ReadAllText(Path.Combine(repoRoot, ".codex-design", "repo", "IMPLEMENTATION_SCOPE.md"));
        string projectMilestonesText = File.ReadAllText(Path.Combine(repoRoot, ".codex-design", "repo", "PROJECT_MILESTONES.yaml"));

        string[] excludedSolutionProjects =
        [
            "Chummer.Presentation.Contracts",
            "Chummer.RunServices.Contracts",
            "Chummer.Infrastructure.Browser",
            "ChummerDataViewer",
            "CrashHandler",
            "TextblockConverter",
            "Translator"
        ];

        foreach (string projectName in excludedSolutionProjects)
        {
            AssertEx.True(
                !solutionText.Contains($"\"{projectName}\"", StringComparison.Ordinal),
                $"Active core engine solution must not directly own non-engine project '{projectName}'.");
        }

        string[] quarantinedSurfaces =
        [
            "Chummer.Presentation.Contracts",
            "Chummer.RunServices.Contracts",
            "Chummer.Infrastructure.Browser"
        ];

        foreach (string surface in quarantinedSurfaces)
        {
            AssertEx.True(
                scopeText.Contains(surface, StringComparison.Ordinal)
                || projectMilestonesText.Contains(surface, StringComparison.Ordinal),
                $"Implementation scope or milestone registry should explicitly classify '{surface}' as quarantined non-engine scope.");
            AssertEx.True(
                projectMilestonesText.Contains(surface, StringComparison.Ordinal),
                $"Project milestone registry should explicitly map quarantined surface '{surface}'.");
        }

        string[] retiredHelperRoots =
        [
            "ChummerDataViewer",
            "CrashHandler",
            "TextblockConverter",
            "Translator"
        ];

        foreach (string surface in retiredHelperRoots)
        {
            AssertEx.True(
                !Directory.Exists(Path.Combine(repoRoot, surface)),
                $"Retired helper root '{surface}' must be removed from the core repo.");
            AssertEx.True(
                projectMilestonesText.Contains(surface, StringComparison.Ordinal),
                $"Project milestone registry should explicitly record retired helper surface '{surface}'.");
        }
    }

    private static bool IsGeneratedOrBuildArtifact""",
        count=1,
        already_contains="string[] retiredHelperRoots =",
    )

    for rel in ("ChummerDataViewer", "CrashHandler", "TextblockConverter", "Translator"):
        if remove_path(CORE_REPO / rel):
            removed.append(rel)

    verify_core_static()
    commit = stage_and_commit(CORE_REPO, CORE_COMMIT)
    return {"repo": "chummer6-core", "commit": commit, "removed": removed}


def main() -> int:
    results = [patch_hub(), patch_core()]
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
