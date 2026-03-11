#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


PROJECT_REPO_MAP = {
    "core": "chummer6-core",
    "design": "chummer6-design",
    "ui": "chummer6-ui",
    "hub": "chummer6-hub",
    "mobile": "chummer6-mobile",
    "ui-kit": "chummer6-ui-kit",
    "hub-registry": "chummer6-hub-registry",
    "media-factory": "chummer6-media-factory",
}

PROJECT_CONFIG_DIR = Path("/docker/fleet/config/projects")


def rewrite_repo_binding(project_id: str, repo_name: str) -> None:
    path = PROJECT_CONFIG_DIR / f"{project_id}.yaml"
    text = path.read_text()
    marker = "  repo: "
    lines = text.splitlines()
    changed = False
    for idx, line in enumerate(lines):
        if line.startswith(marker):
            lines[idx] = f"{marker}{repo_name}"
            changed = True
            break
    if not changed:
        raise SystemExit(f"missing review.repo binding in {path}")
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    for project_id, repo_name in PROJECT_REPO_MAP.items():
        rewrite_repo_binding(project_id, repo_name)
        print(f"{project_id}: {repo_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
