#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import List

import yaml
from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest

from verify_status_plane_semantics import (
    DEFAULT_STATUS_PLANE_PATH,
    StatusPlaneDriftError,
    build_expected_status_plane,
    load_admin_status,
)

UTC = dt.timezone.utc


def iso_now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile STATUS_PLANE.generated.yaml from live Fleet readiness/deployment semantics."
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_STATUS_PLANE_PATH),
        help="output path for STATUS_PLANE.generated.yaml",
    )
    parser.add_argument(
        "--status-json",
        default=None,
        help="optional path to admin status JSON payload (used for offline/test runs)",
    )
    parser.add_argument(
        "--status-json-out",
        default=None,
        help="optional path to write the exact admin status JSON snapshot used for this materialization",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    output_path = Path(args.out).resolve()
    status_json_path = Path(args.status_json).resolve() if args.status_json else None
    status_json_out_path = Path(args.status_json_out).resolve() if args.status_json_out else None

    try:
        admin_status = load_admin_status(status_json_path)
    except StatusPlaneDriftError as exc:
        print(f"status-plane materialization failed: {exc}", file=sys.stderr)
        return 1
    payload = build_expected_status_plane(admin_status)
    payload["generated_at"] = iso_now()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    if status_json_out_path is not None:
        status_json_out_path.parent.mkdir(parents=True, exist_ok=True)
        status_json_out_path.write_text(json.dumps(admin_status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_repo_root = repo_root_for_published_path(output_path)
    if manifest_repo_root is not None:
        write_compile_manifest(manifest_repo_root)
    print(f"wrote status plane: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
