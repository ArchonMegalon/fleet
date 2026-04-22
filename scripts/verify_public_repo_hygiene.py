#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

MAX_TRACKED_BYTES = 50 * 1024 * 1024
SIZE_EXCEPTIONS: set[str] = set()

EXACT_FORBIDDEN = {
    "$fake": "fake scratch root must not be tracked",
    "controller.db": "runtime database must not be tracked",
    "fleet.db": "runtime database must not be tracked",
    "runtime.ea.env": "non-example runtime env file must not be tracked",
    "runtime.env": "non-example runtime env file must not be tracked",
    ".env": "non-example env file must not be tracked",
}

PREFIX_FORBIDDEN = {
    ".nuget/packages/": "local package cache must not be tracked",
    "logs/": "runtime telemetry or logs must not be tracked",
    "state/": "runtime state must not be tracked",
    "tmp/": "temporary workspace must not be tracked",
}

SUFFIX_FORBIDDEN = {
    ".db": "runtime database must not be tracked",
    ".sqlite": "runtime database must not be tracked",
    ".sqlite3": "runtime database must not be tracked",
}

ALLOWLIST = {
    ".env.example",
    "runtime.env.example",
    "runtime.ea.env.example",
}


def tracked_files(repo_root: Path) -> list[str]:
    output = subprocess.check_output(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        text=False,
    )
    return [path for path in output.decode("utf-8", "replace").split("\0") if path]


def violation_reason(path: str) -> str | None:
    if path in ALLOWLIST:
        return None
    if path in EXACT_FORBIDDEN:
        return EXACT_FORBIDDEN[path]
    for prefix, reason in PREFIX_FORBIDDEN.items():
        if path.startswith(prefix):
            return reason
    if path.endswith(".env") or "/.env." in f"/{path}" or path.startswith(".env."):
        return "non-example env file must not be tracked"
    for suffix, reason in SUFFIX_FORBIDDEN.items():
        if path.endswith(suffix):
            return reason
    return None


def oversize_reason(repo_root: Path, path: str) -> str | None:
    if path in SIZE_EXCEPTIONS:
        return None
    file_path = repo_root / path
    try:
        size = file_path.stat().st_size
    except FileNotFoundError:
        return None
    if size >= MAX_TRACKED_BYTES:
        mib = size / (1024 * 1024)
        return f"tracked file is too large for the public repo ({mib:.2f} MiB >= 50.00 MiB)"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Fleet repo root to inspect",
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()

    violations: list[tuple[str, str]] = []
    for path in tracked_files(repo_root):
        reason = violation_reason(path)
        if reason is None:
            reason = oversize_reason(repo_root, path)
        if reason is not None:
            violations.append((path, reason))

    if violations:
        print("tracked public-repo hygiene violations:", file=sys.stderr)
        for path, reason in sorted(violations):
            print(f" - {path}: {reason}", file=sys.stderr)
        return 1

    print("public repo hygiene ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
