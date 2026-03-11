#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


OWNER = "ArchonMegalon"


@dataclass(frozen=True)
class RepoPair:
    legacy: str
    replacement: str


REPOS = [
    RepoPair("chummer-core-engine", "chummer6-core"),
    RepoPair("chummer-design", "chummer6-design"),
    RepoPair("chummer-presentation", "chummer6-ui"),
    RepoPair("chummer.run-services", "chummer6-hub"),
    RepoPair("chummer-play", "chummer6-mobile"),
    RepoPair("chummer-ui-kit", "chummer6-ui-kit"),
    RepoPair("chummer-hub-registry", "chummer6-hub-registry"),
    RepoPair("chummer-media-factory", "chummer6-media-factory"),
]


def run_json(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise SystemExit((proc.stderr or proc.stdout or "").strip())
    text = (proc.stdout or "").strip()
    return json.loads(text) if text else {}


def ensure_repo_exists(repo: str) -> None:
    proc = subprocess.run(
        ["gh", "api", f"repos/{OWNER}/{repo}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"required replacement repo missing: {OWNER}/{repo}: {(proc.stderr or proc.stdout or '').strip()}")


def set_private(repo: str) -> dict:
    return run_json(["gh", "api", "-X", "PATCH", f"repos/{OWNER}/{repo}", "-f", "private=true"])


def main() -> int:
    results = []
    for pair in REPOS:
        ensure_repo_exists(pair.replacement)
        payload = set_private(pair.legacy)
        results.append(
            {
                "legacy": pair.legacy,
                "replacement": pair.replacement,
                "private": bool(payload.get("private")),
                "visibility": payload.get("visibility"),
            }
        )
        print(f"{pair.legacy}: private={payload.get('private')} visibility={payload.get('visibility')}", flush=True)
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
