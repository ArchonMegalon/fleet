#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path


REGISTRY_ROOT = Path("/docker/chummercomplete/chummer-hub-registry")
UI_ROOT = Path("/docker/chummercomplete/chummer6-ui")
PORTAL_ROOT = Path("/docker/chummercomplete/chummer.run-services/Chummer.Portal")
DEFAULT_OUTPUT = REGISTRY_ROOT / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json"
DEFAULT_COMPAT_OUTPUT = REGISTRY_ROOT / ".codex-studio" / "published" / "releases.json"
DEFAULT_DOWNLOADS_DIR = UI_ROOT / "Docker" / "Downloads" / "files"
PORTAL_DOWNLOADS_DIR = PORTAL_ROOT / "downloads" / "files"
REGISTRY_PUBLISHED_DOWNLOADS_DIR = REGISTRY_ROOT / ".codex-studio" / "published" / "files"
DEFAULT_MANIFEST = UI_ROOT / "Docker" / "Downloads" / "RELEASE_CHANNEL.generated.json"
DEFAULT_STARTUP_SMOKE_DIR = REGISTRY_ROOT / ".codex-studio" / "published" / "startup-smoke"
STARTUP_SMOKE_FALLBACK_DIRS = (
    DEFAULT_STARTUP_SMOKE_DIR,
    UI_ROOT / "Docker" / "Downloads" / "startup-smoke",
    UI_ROOT / ".codex-studio" / "published" / "startup-smoke",
    UI_ROOT / ".codex-studio" / "out" / "linux-desktop-exit-gate" / "startup-smoke",
)
REGISTRY_MATERIALIZER = REGISTRY_ROOT / "scripts" / "materialize_public_release_channel.py"
STARTUP_SMOKE_MAX_AGE_SECONDS = 7 * 24 * 3600
STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS = 60
UTC = dt.timezone.utc
PASS_STATUSES = {"pass", "passed", "ready"}
STARTUP_SMOKE_REQUIRED_READY_CHECKPOINT = "pre_ui_event_loop"


def _manifest_artifact_file_names(manifest_path: Path | None) -> list[str]:
    if manifest_path is None or not manifest_path.exists() or not manifest_path.is_file():
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    rows = payload.get("artifacts")
    if not isinstance(rows, list):
        rows = payload.get("downloads")
    if not isinstance(rows, list):
        return []
    file_names: list[str] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        file_name = str(item.get("fileName") or "").strip()
        if not file_name:
            file_name = Path(str(item.get("downloadUrl") or item.get("url") or "").strip()).name
        if file_name:
            file_names.append(file_name)
    return sorted(set(file_names))


def _downloads_dir_match_count(downloads_dir: Path | None, file_names: list[str]) -> int:
    if downloads_dir is None or not downloads_dir.exists() or not downloads_dir.is_dir() or not file_names:
        return 0
    return sum(1 for file_name in file_names if (downloads_dir / file_name).is_file())


def resolve_downloads_dir(
    requested_dir: Path | None,
    *,
    manifest_path: Path | None = None,
    fallback_dirs: tuple[Path, ...] = (PORTAL_DOWNLOADS_DIR, REGISTRY_PUBLISHED_DOWNLOADS_DIR),
) -> Path | None:
    requested = requested_dir if requested_dir is not None else DEFAULT_DOWNLOADS_DIR
    manifest_file_names = _manifest_artifact_file_names(manifest_path)
    if not manifest_file_names:
        return requested

    best_dir = requested
    best_score = _downloads_dir_match_count(requested, manifest_file_names)
    for candidate in fallback_dirs:
        candidate_score = _downloads_dir_match_count(candidate, manifest_file_names)
        if candidate_score > best_score:
            best_dir = candidate
            best_score = candidate_score
    return best_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fleet control-plane wrapper for registry-owned Chummer desktop release projections.")
    parser.add_argument("--downloads-dir", type=Path, default=DEFAULT_DOWNLOADS_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--compat-output", type=Path, default=DEFAULT_COMPAT_OUTPUT)
    parser.add_argument("--runtime-bundles", type=Path)
    parser.add_argument("--proof", type=Path)
    parser.add_argument("--startup-smoke-dir", type=Path, default=DEFAULT_STARTUP_SMOKE_DIR)
    parser.add_argument("--startup-smoke-max-age-seconds", type=int, default=STARTUP_SMOKE_MAX_AGE_SECONDS)
    parser.add_argument("--channel", default="preview")
    parser.add_argument("--version", default="unpublished")
    parser.add_argument("--published-at", default="")
    return parser.parse_args()


def parse_iso(value: object) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def startup_smoke_recorded_at(payload: dict[str, object]) -> dt.datetime | None:
    for key in ("recordedAtUtc", "completedAtUtc", "generatedAt", "generated_at", "startedAtUtc"):
        parsed = parse_iso(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def has_startup_smoke_receipts(path: Path | None, *, max_age_seconds: int = STARTUP_SMOKE_MAX_AGE_SECONDS) -> bool:
    if path is None or not path.exists() or not path.is_dir():
        return False
    now = dt.datetime.now(UTC)
    for receipt in path.rglob("startup-smoke-*.receipt.json"):
        try:
            payload = json.loads(receipt.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status") or "").strip().lower()
        if status not in PASS_STATUSES:
            continue
        ready_checkpoint = str(payload.get("readyCheckpoint") or "").strip().lower()
        if ready_checkpoint != STARTUP_SMOKE_REQUIRED_READY_CHECKPOINT:
            continue
        recorded_at = startup_smoke_recorded_at(payload)
        if recorded_at is None:
            continue
        future_skew_seconds = int((recorded_at - now).total_seconds())
        if future_skew_seconds > STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS:
            continue
        if max_age_seconds >= 0:
            age_seconds = max(0, int((now - recorded_at).total_seconds()))
            if age_seconds > max_age_seconds:
                continue
        return True
    return False


def resolve_startup_smoke_dir(
    requested_dir: Path | None,
    *,
    max_age_seconds: int = STARTUP_SMOKE_MAX_AGE_SECONDS,
    fallback_dirs: tuple[Path, ...] = STARTUP_SMOKE_FALLBACK_DIRS,
) -> Path | None:
    if requested_dir and has_startup_smoke_receipts(requested_dir, max_age_seconds=max_age_seconds):
        return requested_dir

    # Respect explicit non-default startup-smoke paths without silently swapping in alternates.
    if requested_dir and requested_dir != DEFAULT_STARTUP_SMOKE_DIR:
        return None

    for candidate in fallback_dirs:
        if has_startup_smoke_receipts(candidate, max_age_seconds=max_age_seconds):
            return candidate
    return None


def main() -> int:
    args = parse_args()
    if not REGISTRY_MATERIALIZER.exists():
        raise SystemExit(f"Missing registry materializer: {REGISTRY_MATERIALIZER}")

    downloads_dir = resolve_downloads_dir(args.downloads_dir, manifest_path=args.manifest)
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
    if downloads_dir is not None and downloads_dir.exists():
        cmd.extend(["--downloads-dir", str(downloads_dir)])
    if args.published_at:
        cmd.extend(["--published-at", args.published_at])
    if args.runtime_bundles:
        cmd.extend(["--runtime-bundles", str(args.runtime_bundles)])
    if args.proof and args.proof.exists():
        cmd.extend(["--proof", str(args.proof)])
    startup_smoke_dir = resolve_startup_smoke_dir(
        args.startup_smoke_dir,
        max_age_seconds=args.startup_smoke_max_age_seconds,
    )
    if startup_smoke_dir is not None:
        cmd.extend(["--startup-smoke-dir", str(startup_smoke_dir)])
        cmd.extend(["--startup-smoke-max-age-seconds", str(args.startup_smoke_max_age_seconds)])
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
