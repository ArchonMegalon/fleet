#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import List, Optional


ROOT = Path(__file__).resolve().parents[1]
ADMIN_DIR = ROOT / "admin"
if str(ADMIN_DIR) not in sys.path:
    sys.path.insert(0, str(ADMIN_DIR))

from public_progress import DEFAULT_PROGRESS_REPORT_PATH, build_progress_report_payload


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile PROGRESS_REPORT.generated.json from Fleet milestones, published status, and repo activity."
    )
    parser.add_argument(
        "--repo-root",
        default=str(ROOT),
        help="Fleet repo root",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_PROGRESS_REPORT_PATH),
        help="output path for PROGRESS_REPORT.generated.json",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        help="optional YYYY-MM-DD override for the report date",
    )
    return parser.parse_args(argv)


def parse_as_of(raw: Optional[str]) -> Optional[dt.date]:
    if not raw:
        return None
    return dt.date.fromisoformat(str(raw).strip())


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = Path(args.repo_root).resolve()
    out_path = Path(args.out).resolve()
    try:
        as_of = parse_as_of(args.as_of)
    except ValueError as exc:
        print(f"progress-report materialization failed: invalid --as-of value: {exc}", file=sys.stderr)
        return 1

    payload = build_progress_report_payload(repo_root=repo_root, as_of=as_of)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote progress report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
