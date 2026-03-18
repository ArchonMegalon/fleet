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
    "hub-registry": {
        "path": "/docker/chummercomplete/chummer-hub-registry",
        "design_doc": "/docker/chummercomplete/chummer-design/products/chummer/projects/hub-registry.md",
    },
    "ui-kit": {
        "path": "/docker/chummercomplete/chummer-ui-kit",
        "design_doc": "/docker/chummercomplete/chummer-design/products/chummer/projects/ui-kit.md",
    },
    "media-factory": {
        "path": "/docker/fleet/repos/chummer-media-factory",
        "design_doc": "/docker/chummercomplete/chummer-design/products/chummer/projects/media-factory.md",
    },
}

GUIDE_VERIFY_CMD = "python3 /docker/fleet/scripts/verify_chummer6_guide_surface.py"


def ensure_symlink(link: Path, target: Path) -> None:
    if not target.exists():
        raise SystemExit(f"missing target for symlink: {target}")
    if link.is_symlink():
        if link.resolve() == target.resolve():
            return
        link.unlink()
    elif link.exists():
        # Historical repo layouts include both legacy and canonical names as real directories/files.
        # In that case the alias path is already materialized and should not be replaced here.
        return
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
