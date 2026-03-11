#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from pathlib import Path


REPO = Path("/docker/chummercomplete/chummer.run-services")
DOTNET_SDK_VERSION = "10.0.103"
DOTNET_TFM = "net10.0"

REMOVE_PATHS = [
    Path("Chummer"),
    Path("Plugins/SamplePlugin"),
    Path("Chummer.sln"),
    Path("Chummer.sln.DotSettings"),
    Path("appveyor.yml"),
    Path("cs_license.txt"),
    Path("xml_license.txt"),
    Path("mklicese.sh"),
]

LICENSE_TEXT = """# Chummer6 Hub License

Copyright (c) ArchonMegalon.
All rights reserved.

This repository is not offered under the GNU General Public License.
No license is granted to copy, redistribute, sublicense, or create derivative
works from this source without prior written permission from the copyright
holder, except where a separate third-party notice explicitly says otherwise.

Any third-party dependencies, tools, or assets referenced by this repository
retain their own licenses.
"""

README_TEXT = """# chummer6-hub

Hosted orchestration and play API boundary for Chummer6.

## What this repo is

`chummer6-hub` owns the hosted Chummer surface:

- `Chummer.Play.Contracts`
- `Chummer.Media.Contracts`
- `Chummer.Run.Contracts`
- `Chummer.Run.Api`
- `Chummer.Run.Identity`
- `Chummer.Run.Registry`
- `Chummer.Run.AI`

This repo is the orchestrator shell for identity, relay, approvals, memory,
AI orchestration, hosted play APIs, registry-facing publication seams, and
media orchestration contracts.

## What this repo is not

This repo is not the legacy WinForms app, not a compatibility archive, and not
the home for retired desktop helpers or sample plugins.

It does not own:

- the engine/runtime reducer truth
- the player/GM/mobile shell
- shared UI-kit primitives
- render-only media execution ownership
- a preserved GPL oracle tree

## Boundary truth

Canonical hosted boundary guidance lives in:

- `docs/HOSTED_BOUNDARY.md`
- `docs/HUB_EXTRACTION_ACCEPTANCE.md`
- `tests/RunServicesVerification/CompatibilityVerification.cs`

The active build and verification path is:

```bash
bash scripts/ai/verify.sh
```
"""

HOSTED_BOUNDARY_TEXT = """# Hosted Boundary

`chummer6-hub` keeps its active hosted surface limited to:

- `Chummer.Play.Contracts`
- `Chummer.Media.Contracts`
- `Chummer.Run.Contracts`
- `Chummer.Run.Api`
- `Chummer.Run.Identity`
- `Chummer.Run.Registry`
- `Chummer.Run.AI`

These projects are the active hosted runtime boundary for registry, relay,
Spider, media orchestration, identity, and policy surfaces.

No legacy oracle root is preserved inside this repo anymore.

Retired roots that must stay absent:

- `Chummer`
- `Chummer.Api`
- `ChummerDataViewer`
- `ChummerHub`
- `Plugins/ChummerHub.Client`
- `Plugins/SamplePlugin`
- `TextblockConverter`
- `Translator`

Boundary rules:

1. Active hosted projects must be the only projects built through `Chummer.Run.sln` and the clean-room verification path.
2. No legacy oracle/application root may be reintroduced into this repo as a compatibility anchor.
3. Retired hosted clutter must stay absent from the repository and must not be reintroduced through source roots, project references, or docker paths.
4. Future extraction work still moves registry/publication ownership into `chummer6-hub-registry` and keeps this repo as the orchestrator shell around identity, relay, Spider, and policy.
"""

HOSTED_BOUNDARY_MANIFEST = """ACTIVE_HOSTED_PROJECTS=Chummer.Play.Contracts;Chummer.Media.Contracts;Chummer.Run.Contracts;Chummer.Run.Api;Chummer.Run.Identity;Chummer.Run.Registry;Chummer.Run.AI
ORACLE_ROOTS=
RETIRED_ROOTS=Chummer;Chummer.Api;ChummerDataViewer;ChummerHub;Plugins/ChummerHub.Client;Plugins/SamplePlugin;TextblockConverter;Translator
"""

HUB_EXTRACTION_ACCEPTANCE_TEXT = """# Hub Extraction Acceptance

`docs/hosted-boundary.manifest`, `docs/HOSTED_BOUNDARY.md`, and `tests/RunServicesVerification/CompatibilityVerification.cs` keep the hosted boundary limited to the canonical `Chummer.Run.*`, `Chummer.Play.Contracts`, and `Chummer.Media.Contracts` surface, require the active hosted boundary to run through `Chummer.Run.Api`, target the hosted runtime on `net10.0`, and block retired legacy roots (`Chummer`, `Chummer.Api`, `ChummerDataViewer`, `ChummerHub`, `Plugins/ChummerHub.Client`, `Plugins/SamplePlugin`, `TextblockConverter`, and `Translator`) from re-entering the repo.

## Worklist and issue anchors

This acceptance gate closes the hosted split/purification work tracked under:

- WL-085
- WL-086
- WL-088
- WL-089
- WL-095
- WL-098
- WL-102
- WL-104
- WL-111
- WL-118
- WL-120
- WL-125
- WL-137
- WL-140
- WL-145
- WL-148
- WL-149
- WL-150
- WL-151
- WL-153
- WL-155

Issue and migration anchors preserved in this acceptance narrative:

- 1926
- 2369
- 3948
- 4333
- 4334
- 4338
- 4339
- 4367
- 8667
- 8668
- 8697
- 8698
- 11709
- 21817
- 21924
- 53652
- 53653
- 53654

## Boundary artifacts that must stay aligned

- Chummer.Run.Registry
- Chummer.Play.Contracts
- Chummer.Media.Contracts
- PublicationVerification.cs
- CompatibilityVerification.cs
- HOSTED_BOUNDARY.md
- hosted-boundary.manifest
- .codex-design/product/README.md
- .codex-design/repo/IMPLEMENTATION_SCOPE.md
- .codex-design/review/REVIEW_CONTEXT.md
- PROGRAM_MILESTONES.yaml
- scripts/ai/verify.sh
"""

GLOBAL_JSON_TEXT = """{
  "sdk": {
    "version": "10.0.103",
    "rollForward": "latestFeature"
  }
}
"""

COMPATIBILITY_VERIFICATION_BLOCK = r"""        var solutionPath = Path\.Combine\(RepoRoot, "Chummer\.Run\.sln"\);
.*?
        var buildScriptPath = Path\.Combine\(RepoRoot, "scripts", "ai", "build_r1_cleanroom\.sh"\);"""

COMPATIBILITY_VERIFICATION_REPLACEMENT = r"""        var solutionPath = Path.Combine(RepoRoot, "Chummer.Run.sln");
        var solutionText = File.ReadAllText(solutionPath);
        var solutionProjectPaths = solutionText
            .Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(static line => line.StartsWith("Project(", StringComparison.Ordinal) && line.Contains(".csproj", StringComparison.Ordinal))
            .Select(static line => line.Split('"'))
            .Where(static parts => parts.Length >= 6)
            .Select(static parts => parts[5].Replace('/', '\\'))
            .ToArray();

        foreach (var projectName in expectedHostedProjects)
        {
            VerificationAssert.True(solutionText.Contains($" = \"{projectName}\", ", StringComparison.Ordinal), $"Hosted solution must include '{projectName}'.");
        }

        foreach (var oracleRoot in oracleRoots)
        {
            var normalizedRoot = oracleRoot.Replace('/', '\\');
            VerificationAssert.True(Directory.Exists(Path.Combine(RepoRoot, oracleRoot)), $"Oracle root '{oracleRoot}' must exist.");
            VerificationAssert.True(
                !solutionProjectPaths.Any(projectPath => projectPath.StartsWith(normalizedRoot + "\\", StringComparison.Ordinal)),
                $"Hosted solution must not include oracle root '{oracleRoot}'.");
        }

        foreach (var retiredRoot in retiredRoots)
        {
            var normalizedRoot = retiredRoot.Replace('/', '\\');
            VerificationAssert.True(
                !Directory.Exists(Path.Combine(RepoRoot, retiredRoot)),
                $"Retired hosted-clutter root '{retiredRoot}' must stay absent.");
            VerificationAssert.True(
                !solutionProjectPaths.Any(projectPath => projectPath.StartsWith(normalizedRoot + "\\", StringComparison.Ordinal)),
                $"Hosted solution must not include retired hosted-clutter root '{retiredRoot}'.");
        }

        var buildScriptPath = Path.Combine(RepoRoot, "scripts", "ai", "build_r1_cleanroom.sh");"""


def write_text(rel_path: str, content: str) -> None:
    path = REPO / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def remove_path(rel_path: Path) -> str | None:
    path = REPO / rel_path
    if not path.exists():
        return None
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return str(rel_path)


def replace_text(rel_path: str, old: str, new: str) -> None:
    path = REPO / rel_path
    text = path.read_text(encoding="utf-8")
    if old in text:
        path.write_text(text.replace(old, new), encoding="utf-8")
        return
    if new in text:
        return
    raise SystemExit(f"expected text not found in {rel_path}")


def replace_regex(rel_path: str, pattern: str, new: str) -> None:
    path = REPO / rel_path
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, lambda _match: new, text, count=1, flags=re.DOTALL)
    if count:
        path.write_text(updated, encoding="utf-8")
        return
    if new in text:
        return
    raise SystemExit(f"expected regex not found in {rel_path}")


def replace_many(rel_path: str, replacements: list[tuple[str, str]]) -> None:
    path = REPO / rel_path
    text = path.read_text(encoding="utf-8")
    updated = text
    for old, new in replacements:
        updated = updated.replace(old, new)
    if updated != text:
        path.write_text(updated, encoding="utf-8")


def main() -> int:
    removed = [item for item in (remove_path(path) for path in REMOVE_PATHS) if item]

    write_text("global.json", GLOBAL_JSON_TEXT)
    write_text("LICENSE", LICENSE_TEXT)
    write_text("README.md", README_TEXT)
    write_text("docs/HOSTED_BOUNDARY.md", HOSTED_BOUNDARY_TEXT)
    write_text("docs/hosted-boundary.manifest", HOSTED_BOUNDARY_MANIFEST)
    write_text("docs/HUB_EXTRACTION_ACCEPTANCE.md", HUB_EXTRACTION_ACCEPTANCE_TEXT)

    replace_text(
        "tests/RunServicesVerification/CompatibilityVerification.cs",
        """        var canonicalOracleRoots = new[]
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
""",
        """        var canonicalOracleRoots = Array.Empty<string>();
        var canonicalRetiredRoots = new[]
            {
                "Chummer",
                "Chummer.Api",
                "ChummerDataViewer",
                "ChummerHub",
                "Plugins/ChummerHub.Client",
                "Plugins/SamplePlugin",
                "TextblockConverter",
                "Translator"
            }
            .OrderBy(static entry => entry, StringComparer.Ordinal)
            .ToArray();
""",
    )

    replace_text(
        "WORKLIST.md",
        "keep `Chummer` as the oracle root, and block retired hosted clutter (`Chummer.Api`, `ChummerDataViewer`, `ChummerHub`, `Plugins/ChummerHub.Client`, `TextblockConverter`, `Translator`) from re-entering the repo",
        "remove the remaining legacy `Chummer` oracle root and block retired hosted clutter (`Chummer.Api`, `ChummerDataViewer`, `ChummerHub`, `Plugins/ChummerHub.Client`, `Plugins/SamplePlugin`, `TextblockConverter`, `Translator`) from re-entering the repo",
    )

    replace_regex(
        "tests/RunServicesVerification/CompatibilityVerification.cs",
        COMPATIBILITY_VERIFICATION_BLOCK,
        COMPATIBILITY_VERIFICATION_REPLACEMENT,
    )

    for rel_path in (
        "Chummer.Play.Contracts/Chummer.Play.Contracts.csproj",
        "Chummer.Media.Contracts/Chummer.Media.Contracts.csproj",
        "Chummer.Run.Contracts/Chummer.Run.Contracts.csproj",
        "Chummer.Run.Api/Chummer.Run.Api.csproj",
        "Chummer.Run.Identity/Chummer.Run.Identity.csproj",
        "Chummer.Run.Registry/Chummer.Run.Registry.csproj",
        "Chummer.Run.AI/Chummer.Run.AI.csproj",
    ):
        replace_many(rel_path, [("net8.0", DOTNET_TFM)])

    replace_many(
        "scripts/ai/run_services_verification.sh",
        [
            ("net8.0", DOTNET_TFM),
            ("net8\\.0", "net10\\.0"),
            ("Microsoft.NETCore.App 8\\.", "Microsoft.NETCore.App 10\\."),
            ("Microsoft.AspNetCore.App 8\\.", "Microsoft.AspNetCore.App 10\\."),
            ("installed .NET 8 SDK/reference/runtime locations", "installed .NET 10 SDK/reference/runtime locations"),
        ],
    )
    replace_many(
        "scripts/ai/run_services_smoke.sh",
        [
            ("net8.0", DOTNET_TFM),
            ("net8\\.0", "net10\\.0"),
            ("Microsoft.NETCore.App 8\\.", "Microsoft.NETCore.App 10\\."),
            ("Microsoft.AspNetCore.App 8\\.", "Microsoft.AspNetCore.App 10\\."),
            ("installed .NET 8 SDK/reference/runtime locations", "installed .NET 10 SDK/reference/runtime locations"),
        ],
    )

    print(
        {
            "repo": "chummer6-hub",
            "removed": removed,
            "license": "proprietary",
            "target_framework": DOTNET_TFM,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
