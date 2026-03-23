#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


REGISTRY_ROOT = Path("/docker/chummercomplete/chummer-hub-registry")
UI_ROOT = Path("/docker/chummercomplete/chummer6-ui")
DEFAULT_OUTPUT = REGISTRY_ROOT / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json"
DEFAULT_COMPAT_OUTPUT = REGISTRY_ROOT / ".codex-studio" / "published" / "releases.json"
DEFAULT_DOWNLOADS_DIR = UI_ROOT / "Docker" / "Downloads" / "files"
REGISTRY_MATERIALIZER = REGISTRY_ROOT / "scripts" / "materialize_public_release_channel.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fleet control-plane wrapper for registry-owned Chummer desktop release projections.")
    parser.add_argument("--downloads-dir", type=Path, default=DEFAULT_DOWNLOADS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--compat-output", type=Path, default=DEFAULT_COMPAT_OUTPUT)
    parser.add_argument("--runtime-bundles", type=Path)
    parser.add_argument("--channel", default="preview")
    parser.add_argument("--version", default="unpublished")
    parser.add_argument("--published-at", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not REGISTRY_MATERIALIZER.exists():
        raise SystemExit(f"Missing registry materializer: {REGISTRY_MATERIALIZER}")

    cmd = [
        "python3",
        str(REGISTRY_MATERIALIZER),
        "--downloads-dir",
        str(args.downloads_dir),
        "--output",
        str(args.output),
        "--compat-output",
        str(args.compat_output),
        "--channel",
        args.channel,
        "--version",
        args.version,
    ]
    if args.published_at:
        cmd.extend(["--published-at", args.published_at])
    if args.runtime_bundles:
        cmd.extend(["--runtime-bundles", str(args.runtime_bundles)])
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
