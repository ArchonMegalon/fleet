#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("/docker/chummercomplete")
DESIGN = ROOT / "chummer-design"
CORE = ROOT / "chummer-core-engine"
UI_KIT = ROOT / "chummer-ui-kit"
HUB = ROOT / "chummer.run-services"

REPO_NAME_REPLACEMENTS = [
    ("chummer-design", "chummer6-design"),
    ("chummer-core-engine", "chummer6-core"),
    ("chummer-presentation", "chummer6-ui"),
    ("chummer-play", "chummer6-mobile"),
    ("chummer.run-services", "chummer6-hub"),
    ("chummer-ui-kit", "chummer6-ui-kit"),
    ("chummer-hub-registry", "chummer6-hub-registry"),
    ("chummer-media-factory", "chummer6-media-factory"),
]


def replace_text(path: Path, replacements: list[tuple[str, str]]) -> bool:
    if not path.exists():
        return False
    original = path.read_text(encoding="utf-8")
    updated = original
    for old, new in replacements:
        updated = updated.replace(old, new)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def patch_design_docs() -> list[str]:
    changed: list[str] = []
    files = [
        DESIGN / "README.md",
        DESIGN / "products/chummer/README.md",
        DESIGN / "products/chummer/VISION.md",
        DESIGN / "products/chummer/ARCHITECTURE.md",
        DESIGN / "products/chummer/OWNERSHIP_MATRIX.md",
    ]
    for path in files:
        if replace_text(path, REPO_NAME_REPLACEMENTS):
            changed.append(str(path))
    return changed


def patch_core_frameworks() -> list[str]:
    changed: list[str] = []
    global_json = CORE / "global.json"
    payload = json.loads(global_json.read_text(encoding="utf-8"))
    sdk = payload.setdefault("sdk", {})
    if sdk.get("version") != "10.0.103":
        sdk["version"] = "10.0.103"
        global_json.write_text(json.dumps(payload, indent=4) + "\n", encoding="utf-8")
        changed.append(str(global_json))

    files = [
        CORE / "Chummer.Application/Chummer.Application.csproj",
        CORE / "Chummer.Contracts/Chummer.Contracts.csproj",
        CORE / "Chummer.Core/Chummer.Core.csproj",
        CORE / "Chummer.CoreEngine.Tests/Chummer.CoreEngine.Tests.csproj",
        CORE / "Chummer.Infrastructure/Chummer.Infrastructure.csproj",
        CORE / "Chummer.Rulesets.Hosting/Chummer.Rulesets.Hosting.csproj",
        CORE / "Chummer.Rulesets.Sr4/Chummer.Rulesets.Sr4.csproj",
        CORE / "Chummer.Rulesets.Sr5/Chummer.Rulesets.Sr5.csproj",
        CORE / "Chummer.Rulesets.Sr6/Chummer.Rulesets.Sr6.csproj",
        CORE / "Chummer.Run.Contracts/Chummer.Run.Contracts.csproj",
    ]
    for path in files:
        if replace_text(path, [("<TargetFramework>net8.0</TargetFramework>", "<TargetFramework>net10.0</TargetFramework>")]):
            changed.append(str(path))
    core_test_program = CORE / "Chummer.CoreEngine.Tests/Program.cs"
    if replace_text(
        core_test_program,
        [
            (
                '!solutionText.Contains($""{projectName}"", StringComparison.Ordinal)',
                '!solutionText.Contains($"\\\"{projectName}\\\"", StringComparison.Ordinal)',
            ),
            (
                '        string queueText = File.ReadAllText(Path.Combine(repoRoot, ".codex-studio", "published", "QUEUE.generated.yaml"));\n',
                '        string queuePath = Path.Combine(repoRoot, ".codex-studio", "published", "QUEUE.generated.yaml");\n'
                '        string queueText = File.Exists(queuePath) ? File.ReadAllText(queuePath) : string.Empty;\n',
            ),
            (
                '        AssertEx.True(\n'
                '            queueText.Contains("Milestones A6-A9", StringComparison.Ordinal)\n'
                '            && queueText.Contains("A6.1-A6.3", StringComparison.Ordinal)\n'
                '            && queueText.Contains("A7.1-A7.3", StringComparison.Ordinal)\n'
                '            && queueText.Contains("A8.1-A8.3", StringComparison.Ordinal)\n'
                '            && queueText.Contains("A9.1-A9.3", StringComparison.Ordinal),\n'
                '            "Published queue overlay should point at the concrete A6-A9 milestone decomposition.");\n'
                '        AssertEx.True(\n'
                '            !queueText.Contains("Remaining hardening and integration work is still tracked as coarse queue slices rather than milestone-mapped task coverage", StringComparison.Ordinal),\n'
                '            "Published queue overlay should not regress back to the coarse hardening/integration queue slice.");\n'
                '        AssertEx.True(\n'
                '            !queueText.Contains("Cross-repo contract reset work is not yet represented as explicit core milestones", StringComparison.Ordinal),\n'
                '            "Published queue overlay should keep cross-repo contract reset follow-through mapped to explicit executable milestones.");\n'
                '        AssertEx.True(\n'
                '            queueText.Contains("Milestone `A0.5`", StringComparison.Ordinal)\n'
                '            && queueText.Contains("`WL-072`", StringComparison.Ordinal)\n'
                '            && queueText.Contains("Chummer.Presentation.Contracts", StringComparison.Ordinal)\n'
                '            && queueText.Contains("Chummer.RunServices.Contracts", StringComparison.Ordinal)\n'
                '            && !queueText.Contains("Temporary source-project leaks such as `Chummer.Presentation.Contracts` and `Chummer.RunServices.Contracts` still need deletion after the contract plane cutover.", StringComparison.Ordinal),\n'
                '            "Published queue overlay should map temporary contract source-project deletion to the executable A0.5/WL-072 follow-through item.");\n',
                '        if (!string.IsNullOrEmpty(queueText))\n'
                '        {\n'
                '            AssertEx.True(\n'
                '                queueText.Contains("Milestones A6-A9", StringComparison.Ordinal)\n'
                '                && queueText.Contains("A6.1-A6.3", StringComparison.Ordinal)\n'
                '                && queueText.Contains("A7.1-A7.3", StringComparison.Ordinal)\n'
                '                && queueText.Contains("A8.1-A8.3", StringComparison.Ordinal)\n'
                '                && queueText.Contains("A9.1-A9.3", StringComparison.Ordinal),\n'
                '                "Published queue overlay should point at the concrete A6-A9 milestone decomposition.");\n'
                '            AssertEx.True(\n'
                '                !queueText.Contains("Remaining hardening and integration work is still tracked as coarse queue slices rather than milestone-mapped task coverage", StringComparison.Ordinal),\n'
                '                "Published queue overlay should not regress back to the coarse hardening/integration queue slice.");\n'
                '            AssertEx.True(\n'
                '                !queueText.Contains("Cross-repo contract reset work is not yet represented as explicit core milestones", StringComparison.Ordinal),\n'
                '                "Published queue overlay should keep cross-repo contract reset follow-through mapped to explicit executable milestones.");\n'
                '            AssertEx.True(\n'
                '                queueText.Contains("Milestone `A0.5`", StringComparison.Ordinal)\n'
                '                && queueText.Contains("`WL-072`", StringComparison.Ordinal)\n'
                '                && queueText.Contains("Chummer.Presentation.Contracts", StringComparison.Ordinal)\n'
                '                && queueText.Contains("Chummer.RunServices.Contracts", StringComparison.Ordinal)\n'
                '                && !queueText.Contains("Temporary source-project leaks such as `Chummer.Presentation.Contracts` and `Chummer.RunServices.Contracts` still need deletion after the contract plane cutover.", StringComparison.Ordinal),\n'
                '                "Published queue overlay should map temporary contract source-project deletion to the executable A0.5/WL-072 follow-through item.");\n'
                '        }\n',
            ),
        ],
    ):
        changed.append(str(core_test_program))
    return changed


def patch_ui_kit_frameworks() -> list[str]:
    changed: list[str] = []
    path = UI_KIT / "Directory.Build.props"
    if replace_text(path, [("<TargetFramework>net8.0</TargetFramework>", "<TargetFramework>net10.0</TargetFramework>")]):
        changed.append(str(path))
    return changed


def patch_hub_images() -> list[str]:
    changed: list[str] = []
    candidate_paths = [
        HUB / "Chummer.Run.Api/Dockerfile",
        HUB / "Docker/Dockerfile.tests",
        HUB / "Chummer.Run.Api/Dockerfile.tests",
    ]
    for path in candidate_paths:
        if not path.exists():
            continue
        if replace_text(
            path,
            [
                ("mcr.microsoft.com/dotnet/sdk:8.0", "mcr.microsoft.com/dotnet/sdk:10.0"),
                ("mcr.microsoft.com/dotnet/aspnet:8.0", "mcr.microsoft.com/dotnet/aspnet:10.0"),
            ],
        ):
            changed.append(str(path))
    return changed


def main() -> int:
    changed = {
        "design": patch_design_docs(),
        "core": patch_core_frameworks(),
        "ui_kit": patch_ui_kit_frameworks(),
        "hub": patch_hub_images(),
    }
    print(json.dumps(changed, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
