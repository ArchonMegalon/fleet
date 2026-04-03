#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


REGISTRY_ROOT = Path("/docker/chummercomplete/chummer-hub-registry")
UI_ROOT = Path("/docker/chummercomplete/chummer6-ui")
HUB_ROOT = Path("/docker/chummercomplete/chummer.run-services")
DEFAULT_OUTPUT = REGISTRY_ROOT / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json"
DEFAULT_COMPAT_OUTPUT = REGISTRY_ROOT / ".codex-studio" / "published" / "releases.json"
DEFAULT_DOWNLOADS_DIR = UI_ROOT / "Docker" / "Downloads" / "files"
DEFAULT_MANIFEST = UI_ROOT / "Docker" / "Downloads" / "RELEASE_CHANNEL.generated.json"
DEFAULT_PROOF_PATH = HUB_ROOT / ".codex-studio" / "published" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
DEFAULT_STARTUP_SMOKE_DIR = REGISTRY_ROOT / ".codex-studio" / "published" / "startup-smoke"
STARTUP_SMOKE_FALLBACK_DIRS = (
    DEFAULT_STARTUP_SMOKE_DIR,
    UI_ROOT / "Docker" / "Downloads" / "startup-smoke",
    UI_ROOT / ".codex-studio" / "published" / "startup-smoke",
    UI_ROOT / ".codex-studio" / "out" / "linux-desktop-exit-gate" / "startup-smoke",
)
REGISTRY_MATERIALIZER = REGISTRY_ROOT / "scripts" / "materialize_public_release_channel.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fleet control-plane wrapper for registry-owned Chummer desktop release projections.")
    parser.add_argument("--downloads-dir", type=Path, default=DEFAULT_DOWNLOADS_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--compat-output", type=Path, default=DEFAULT_COMPAT_OUTPUT)
    parser.add_argument("--runtime-bundles", type=Path)
    parser.add_argument("--proof", type=Path, default=DEFAULT_PROOF_PATH)
    parser.add_argument("--startup-smoke-dir", type=Path, default=DEFAULT_STARTUP_SMOKE_DIR)
    parser.add_argument("--channel", default="preview")
    parser.add_argument("--version", default="unpublished")
    parser.add_argument("--published-at", default="")
    return parser.parse_args()


def has_startup_smoke_receipts(path: Path | None) -> bool:
    if path is None or not path.exists() or not path.is_dir():
        return False
    return any(path.rglob("startup-smoke-*.receipt.json"))


def resolve_startup_smoke_dir(
    requested_dir: Path | None,
    *,
    fallback_dirs: tuple[Path, ...] = STARTUP_SMOKE_FALLBACK_DIRS,
) -> Path | None:
    if requested_dir and has_startup_smoke_receipts(requested_dir):
        return requested_dir

    # Respect explicit non-default startup-smoke paths without silently swapping in alternates.
    if requested_dir and requested_dir != DEFAULT_STARTUP_SMOKE_DIR:
        return None

    for candidate in fallback_dirs:
        if has_startup_smoke_receipts(candidate):
            return candidate
    return None


def main() -> int:
    args = parse_args()
    if not REGISTRY_MATERIALIZER.exists():
        raise SystemExit(f"Missing registry materializer: {REGISTRY_MATERIALIZER}")

    cmd = [
        "python3",
        str(REGISTRY_MATERIALIZER),
        "--output",
        str(args.output),
        "--compat-output",
        str(args.compat_output),
        "--channel",
        args.channel,
        "--version",
        args.version,
    ]
    if args.manifest and args.manifest.exists():
        cmd.extend(["--manifest", str(args.manifest)])
    else:
        cmd.extend(["--downloads-dir", str(args.downloads_dir)])
    if args.published_at:
        cmd.extend(["--published-at", args.published_at])
    if args.runtime_bundles:
        cmd.extend(["--runtime-bundles", str(args.runtime_bundles)])
    if args.proof and args.proof.exists():
        cmd.extend(["--proof", str(args.proof)])
    startup_smoke_dir = resolve_startup_smoke_dir(args.startup_smoke_dir)
    if startup_smoke_dir is not None:
        cmd.extend(["--startup-smoke-dir", str(startup_smoke_dir)])
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
