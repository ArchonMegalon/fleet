#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


CHUMMERCOMPLETE_ROOT = Path("/docker/chummercomplete")
DESIGN_PROJECTS_DIR = CHUMMERCOMPLETE_ROOT / "chummer-design" / "products" / "chummer" / "projects"
PROJECT_CONFIG_DIR = Path("/docker/fleet/config/projects")

REPO_SYMLINKS = {
    "chummer6-core": CHUMMERCOMPLETE_ROOT / "chummer-core-engine",
    "chummer6-ui": CHUMMERCOMPLETE_ROOT / "chummer-presentation",
    "chummer6-hub": CHUMMERCOMPLETE_ROOT / "chummer.run-services",
    "chummer6-mobile": CHUMMERCOMPLETE_ROOT / "chummer-play",
}

DESIGN_DOC_SYMLINKS = {
    "ui.md": "presentation.md",
    "hub.md": "run-services.md",
    "mobile.md": "play.md",
}

PROJECT_FIELDS = {
    "core": {
        "path": "/docker/chummercomplete/chummer6-core",
        "design_doc": "/docker/chummercomplete/chummer-design/products/chummer/projects/core.md",
    },
    "ui": {
        "path": "/docker/chummercomplete/chummer6-ui",
        "design_doc": "/docker/chummercomplete/chummer-design/products/chummer/projects/ui.md",
    },
    "hub": {
        "path": "/docker/chummercomplete/chummer6-hub",
        "design_doc": "/docker/chummercomplete/chummer-design/products/chummer/projects/hub.md",
    },
    "mobile": {
        "path": "/docker/chummercomplete/chummer6-mobile",
        "design_doc": "/docker/chummercomplete/chummer-design/products/chummer/projects/mobile.md",
    },
}

GUIDE_VERIFY_CMD = (
    "test -f README.md && test -f START_HERE.md && test -f WHAT_CHUMMER6_IS.md && "
    "test -f WHERE_TO_GO_DEEPER.md && test ! -e WHERE_THE_REAL_TRUTH_LIVES.md && "
    "test -f GLOSSARY.md && test -f FAQ.md && test -f NOW/current-phase.md && "
    "test -f NOW/current-status.md && test -f NOW/public-surfaces.md && "
    "test -f PARTS/README.md && test -f PARTS/core.md && test -f PARTS/ui.md && "
    "test -f PARTS/hub.md && test -f PARTS/mobile.md && test -f PARTS/ui-kit.md && "
    "test -f PARTS/hub-registry.md && test -f PARTS/media-factory.md && "
    "test -f PARTS/design.md && test ! -e PARTS/presentation.md && "
    "test ! -e PARTS/run-services.md && test ! -e PARTS/play.md && test ! -e PARTS/fleet.md && "
    "test -f HORIZONS/README.md && test -f HORIZONS/karma-forge.md && "
    "test -f HORIZONS/nexus-pan.md && test -f HORIZONS/alice.md && "
    "test -f HORIZONS/jackpoint.md && test -f HORIZONS/ghostwire.md && "
    "test -f HORIZONS/mirrorshard.md && test -f HORIZONS/rule-x-ray.md && "
    "test -f HORIZONS/heat-web.md && test -f HORIZONS/run-passport.md && "
    "test -f HORIZONS/command-casket.md && test -f HORIZONS/tactical-pulse.md && "
    "test -f HORIZONS/blackbox-loadout.md && test -f HORIZONS/persona-echo.md && "
    "test -f HORIZONS/shadow-market.md && test -f HORIZONS/evidence-room.md && "
    "test -f HORIZONS/threadcutter.md && test -f UPDATES/2026-03.md && "
    "test ! -d scripts && test ! -d src && test ! -d tests && test ! -e VISION.md && "
    "test ! -e ROADMAP.md && test ! -e ARCHITECTURE.md && test ! -e WORKLIST.md && "
    "test ! -e CONTRACT_SETS.yaml && test ! -e GROUP_BLOCKERS.md && "
    "test ! -e runtime-instructions.generated.md && test ! -e QUEUE.generated.yaml"
)


def ensure_symlink(link: Path, target: Path) -> None:
    if not target.exists():
        raise SystemExit(f"missing target for symlink: {target}")
    if link.is_symlink():
        if link.resolve() == target.resolve():
            return
        link.unlink()
    elif link.exists():
        raise SystemExit(f"refusing to replace non-symlink path: {link}")
    link.symlink_to(target)


def rewrite_field(path: Path, marker: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines):
        if line.startswith(marker):
            lines[idx] = f"{marker}{value}"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return
    raise SystemExit(f"missing field {marker!r} in {path}")


def main() -> int:
    for alias_name, target in REPO_SYMLINKS.items():
        ensure_symlink(CHUMMERCOMPLETE_ROOT / alias_name, target)
        print(f"repo-alias: {alias_name} -> {target}")

    for alias_name, target_name in DESIGN_DOC_SYMLINKS.items():
        ensure_symlink(DESIGN_PROJECTS_DIR / alias_name, DESIGN_PROJECTS_DIR / target_name)
        print(f"design-doc-alias: {alias_name} -> {target_name}")

    for project_id, fields in PROJECT_FIELDS.items():
        path = PROJECT_CONFIG_DIR / f"{project_id}.yaml"
        for marker, value in fields.items():
            rewrite_field(path, f"{marker}: ", value)
        print(f"project-config: {project_id}")

    rewrite_field(PROJECT_CONFIG_DIR / "guide.yaml", "verify_cmd: ", GUIDE_VERIFY_CMD)
    print("project-config: guide.verify_cmd")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
