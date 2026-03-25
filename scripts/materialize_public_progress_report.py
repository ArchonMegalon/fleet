#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path
from typing import List, Optional


ROOT = Path(__file__).resolve().parents[1]
ADMIN_DIR = ROOT / "admin"
if str(ADMIN_DIR) not in sys.path:
    sys.path.insert(0, str(ADMIN_DIR))

from public_progress import (
    CANON_PROGRESS_HTML_PATH,
    CANON_PROGRESS_HISTORY_PATH,
    CANON_PROGRESS_POSTER_PATH,
    CANON_PROGRESS_REPORT_PATH,
    DEFAULT_PROGRESS_HISTORY_PATH,
    DEFAULT_POSTER_PATH,
    DEFAULT_PROGRESS_REPORT_PATH,
    HUB_PROGRESS_HTML_PATH,
    HUB_PROGRESS_HISTORY_PATH,
    HUB_PROGRESS_MIRROR_DIR,
    HUB_PROGRESS_POSTER_PATH,
    HUB_PROGRESS_REPORT_PATH,
    build_progress_report_payload,
    load_progress_history_payload,
    merge_progress_history,
    poster_svg_text,
    progress_history_snapshot,
    render_progress_report_html,
)
from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest


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
        default=str(CANON_PROGRESS_REPORT_PATH),
        help="output path for PROGRESS_REPORT.generated.json",
    )
    parser.add_argument(
        "--html-out",
        default=None,
        help="optional output path for PROGRESS_REPORT.generated.html",
    )
    parser.add_argument(
        "--poster-out",
        default=None,
        help="optional output path for PROGRESS_REPORT_POSTER.svg",
    )
    parser.add_argument(
        "--preview-out",
        default=None,
        help="optional Fleet-local preview copy of PROGRESS_REPORT.generated.json",
    )
    parser.add_argument(
        "--history-out",
        default=None,
        help="optional output path for PROGRESS_HISTORY.generated.json",
    )
    parser.add_argument(
        "--mirror-root",
        default=str(HUB_PROGRESS_MIRROR_DIR.parent.parent),
        help="optional Hub repo root whose .codex-design/product mirror should receive the generated bundle",
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


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _canonical_bundle_requested(out_path: Path) -> bool:
    return out_path.resolve() == CANON_PROGRESS_REPORT_PATH.resolve()


def _mirror_bundle(html_path: Path, json_path: Path, poster_path: Path, history_path: Path | None, mirror_root: Path) -> None:
    mirror_dir = mirror_root / ".codex-design" / "product"
    mirror_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(json_path, HUB_PROGRESS_REPORT_PATH if mirror_dir == HUB_PROGRESS_MIRROR_DIR else mirror_dir / json_path.name)
    shutil.copy2(html_path, HUB_PROGRESS_HTML_PATH if mirror_dir == HUB_PROGRESS_MIRROR_DIR else mirror_dir / html_path.name)
    shutil.copy2(poster_path, HUB_PROGRESS_POSTER_PATH if mirror_dir == HUB_PROGRESS_MIRROR_DIR else mirror_dir / poster_path.name)
    if history_path is not None:
        shutil.copy2(history_path, HUB_PROGRESS_HISTORY_PATH if mirror_dir == HUB_PROGRESS_MIRROR_DIR else mirror_dir / history_path.name)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = Path(args.repo_root).resolve()
    out_path = Path(args.out).resolve()
    html_out = Path(args.html_out).resolve() if args.html_out else None
    poster_out = Path(args.poster_out).resolve() if args.poster_out else None
    preview_out = Path(args.preview_out).resolve() if args.preview_out else None
    history_out = Path(args.history_out).resolve() if args.history_out else None
    mirror_root = Path(args.mirror_root).resolve() if str(args.mirror_root or "").strip() else None
    try:
        as_of = parse_as_of(args.as_of)
    except ValueError as exc:
        print(f"progress-report materialization failed: invalid --as-of value: {exc}", file=sys.stderr)
        return 1

    if html_out is None and _canonical_bundle_requested(out_path):
        html_out = CANON_PROGRESS_HTML_PATH
    if poster_out is None and _canonical_bundle_requested(out_path):
        poster_out = CANON_PROGRESS_POSTER_PATH
    if preview_out is None and _canonical_bundle_requested(out_path):
        preview_out = DEFAULT_PROGRESS_REPORT_PATH
    if history_out is None and _canonical_bundle_requested(out_path):
        history_out = CANON_PROGRESS_HISTORY_PATH

    existing_history = None
    if history_out is not None:
        existing_history = load_progress_history_payload(repo_root=repo_root)

    payload = build_progress_report_payload(repo_root=repo_root, as_of=as_of, history_payload=existing_history)
    history_payload = None
    if history_out is not None:
        assert existing_history is not None
        history_payload = merge_progress_history(existing_history, payload)
        payload = build_progress_report_payload(repo_root=repo_root, as_of=as_of, history_payload=history_payload)
    json_text = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    _write_text(out_path, json_text)
    if preview_out is not None:
        _write_text(preview_out, json_text)
    if history_out is not None and history_payload is not None:
        history_text = json.dumps(history_payload, indent=2, sort_keys=False) + "\n"
        _write_text(history_out, history_text)
        if _canonical_bundle_requested(out_path):
            _write_text(DEFAULT_PROGRESS_HISTORY_PATH, history_text)
    if html_out is not None:
        _write_text(html_out, render_progress_report_html(payload))
    if poster_out is not None:
        _write_text(poster_out, poster_svg_text(DEFAULT_POSTER_PATH))
    if mirror_root is not None and html_out is not None and poster_out is not None:
        _mirror_bundle(html_out, out_path, poster_out, history_out, mirror_root)
    manifest_targets = [candidate for candidate in (out_path, preview_out, history_out) if candidate is not None]
    if any(repo_root_for_published_path(candidate) == repo_root for candidate in manifest_targets):
        write_compile_manifest(repo_root)

    print(f"wrote progress report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
