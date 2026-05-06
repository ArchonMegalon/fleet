from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


def _path_env(env_var: str, default: Path) -> Path:
    raw = os.environ.get(env_var)
    if not raw:
        return default
    return Path(raw)


FLEET_ROOT = _path_env("CHUMMER_EXTERNAL_PROOF_FLEET_ROOT", Path("/docker/fleet"))
CHUMMER_COMPLETE_ROOT = _path_env(
    "CHUMMER_EXTERNAL_PROOF_CHUMMER_COMPLETE_ROOT",
    Path("/docker/chummercomplete"),
)

FLEET_PUBLISHED_ROOT = FLEET_ROOT / ".codex-studio" / "published"
DEFAULT_SUPPORT_PACKETS = FLEET_PUBLISHED_ROOT / "SUPPORT_CASE_PACKETS.generated.json"
DEFAULT_EXTERNAL_PROOF_RUNBOOK = FLEET_PUBLISHED_ROOT / "EXTERNAL_PROOF_RUNBOOK.generated.md"
DEFAULT_EXTERNAL_PROOF_COMMANDS_DIR = FLEET_PUBLISHED_ROOT / "external-proof-commands"
DEFAULT_JOURNEY_GATES = FLEET_PUBLISHED_ROOT / "JOURNEY_GATES.generated.json"

RELEASE_CHANNEL_REPO_ROOT = CHUMMER_COMPLETE_ROOT / "chummer-hub-registry"
UI_REPO_ROOT = CHUMMER_COMPLETE_ROOT / "chummer6-ui"
RUN_SERVICES_REPO_ROOT = CHUMMER_COMPLETE_ROOT / "chummer.run-services"
PORTAL_DOWNLOADS_ROOT = RUN_SERVICES_REPO_ROOT / "Chummer.Portal" / "downloads"
LEGACY_PORTAL_DOWNLOADS_ROOT = CHUMMER_COMPLETE_ROOT / "chummer-presentation" / "Chummer.Portal" / "downloads"

UI_LOCAL_RELEASE_PROOF_PATH = UI_REPO_ROOT / ".codex-studio" / "published" / "UI_LOCAL_RELEASE_PROOF.generated.json"
UI_LOCALIZATION_RELEASE_GATE_PATH = UI_REPO_ROOT / ".codex-studio" / "published" / "UI_LOCALIZATION_RELEASE_GATE.generated.json"
UI_DOCKER_DOWNLOADS_ROOT = UI_REPO_ROOT / "Docker" / "Downloads"
UI_DOCKER_DOWNLOADS_FILES_ROOT = UI_DOCKER_DOWNLOADS_ROOT / "files"
UI_DOCKER_DOWNLOADS_STARTUP_SMOKE_ROOT = UI_DOCKER_DOWNLOADS_ROOT / "startup-smoke"
REGISTRY_RELEASE_CHANNEL_PATH = RELEASE_CHANNEL_REPO_ROOT / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json"
PORTAL_RELEASE_CHANNEL_PATH = PORTAL_DOWNLOADS_ROOT / "RELEASE_CHANNEL.generated.json"
LEGACY_PORTAL_RELEASE_CHANNEL_PATH = LEGACY_PORTAL_DOWNLOADS_ROOT / "RELEASE_CHANNEL.generated.json"
RELEASE_CHANNEL_MANIFEST_PATH = UI_REPO_ROOT / "Docker" / "Downloads" / "RELEASE_CHANNEL.generated.json"
RELEASE_CHANNEL_MIRROR_PATH = UI_REPO_ROOT / "Docker" / "Downloads" / "STARTUP_SMOKE" / "RELEASE_CHANNEL.generated.json"
RELEASE_CHANNEL_CANDIDATE_PATHS = (
    REGISTRY_RELEASE_CHANNEL_PATH,
    PORTAL_RELEASE_CHANNEL_PATH,
    LEGACY_PORTAL_RELEASE_CHANNEL_PATH,
    RELEASE_CHANNEL_MANIFEST_PATH,
)
KNOWN_EXTERNAL_PROOF_HOSTS = {"windows", "linux", "macos"}
HOST_CLASS_PLATFORM_ALIASES = {
    "windows": ("windows", "win32", "win"),
    "macos": ("macos", "osx", "darwin"),
    "linux": ("linux",),
}
RELEASE_CHANNEL_REGISTRY_STALE_MAX_AGE_SECONDS = 24 * 3600


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_release_channel_status(value: object) -> str:
    return str(value or "").strip().lower()


def _parse_release_channel_generated_at(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _release_channel_status_rank(status: str) -> int:
    if status in {"published", "public"}:
        return 3
    if status in {"protected_preview", "preview"}:
        return 2
    if status in {"unpublished", "draft"}:
        return 1
    return 0


def _release_channel_coverage_rank(payload: object) -> int:
    if not isinstance(payload, dict):
        return 0
    coverage = payload.get("desktopTupleCoverage")
    if not isinstance(coverage, dict):
        return 0
    missing_platforms = coverage.get("missingRequiredPlatforms")
    missing_pairs = coverage.get("missingRequiredPlatformHeadPairs")
    missing_tuples = coverage.get("missingRequiredPlatformHeadRidTuples")
    external_requests = coverage.get("externalProofRequests")
    if not all(
        isinstance(value, list)
        for value in (missing_platforms, missing_pairs, missing_tuples, external_requests)
    ):
        return 0
    if missing_platforms or missing_pairs or missing_tuples or external_requests:
        return 1
    return 2


def _release_channel_has_tuple_coverage(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    coverage = payload.get("desktopTupleCoverage")
    return isinstance(coverage, dict)


def _release_channel_authority_rank(candidate: Path, payload: object) -> int:
    if not _release_channel_has_tuple_coverage(payload):
        return 0
    normalized_candidate = str(candidate.resolve())
    if normalized_candidate == str(REGISTRY_RELEASE_CHANNEL_PATH.resolve()):
        return 1
    parent_name = candidate.parent.name.strip().lower()
    return int(parent_name == "registry")


def _candidate_can_supersede_registry(candidate: Path) -> bool:
    normalized_candidate = str(candidate.resolve())
    if normalized_candidate in {
        str(PORTAL_RELEASE_CHANNEL_PATH.resolve()),
        str(LEGACY_PORTAL_RELEASE_CHANNEL_PATH.resolve()),
    }:
        return True
    ancestor_names = {part.strip().lower() for part in candidate.parts if str(part).strip()}
    return bool({"portal", "chummer.portal"} & ancestor_names)


def _candidate_is_ui_docker_manifest(candidate: Path) -> bool:
    normalized_candidate = str(candidate.resolve())
    if normalized_candidate == str(RELEASE_CHANNEL_MANIFEST_PATH.resolve()):
        return True
    parts = [part.strip().lower() for part in candidate.parts if str(part).strip()]
    return "docker" in parts and "downloads" in parts


def resolve_release_channel_path(*, candidates: tuple[Path, ...] | None = None) -> Path:
    override = str(os.environ.get("CHUMMER_EXTERNAL_PROOF_RELEASE_CHANNEL", "") or "").strip()
    if override:
        return Path(override)

    candidate_paths = candidates or RELEASE_CHANNEL_CANDIDATE_PATHS
    candidate_infos: list[dict[str, object]] = []
    fallback_path: Path | None = None
    for index, candidate in enumerate(candidate_paths):
        if not candidate.is_file():
            continue
        fallback_path = fallback_path or candidate
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        artifacts = [item for item in (payload.get("artifacts") or []) if isinstance(item, dict)]
        artifactful = int(bool(artifacts))
        status = _normalize_release_channel_status(payload.get("status"))
        status_rank = _release_channel_status_rank(status)
        coverage_rank = _release_channel_coverage_rank(payload)
        authority_rank = _release_channel_authority_rank(candidate, payload)
        published_with_artifacts = int(status_rank >= 2 and artifactful)
        startup_smoke_available = int((candidate.parent / "startup-smoke").is_dir())
        generated_at = _parse_release_channel_generated_at(
            payload.get("generatedAt") or payload.get("generated_at")
        )
        generated_at_ts = generated_at.timestamp() if generated_at is not None else float("-inf")
        candidate_infos.append(
            {
                "path": candidate,
                "index": index,
                "payload": payload,
                "artifacts": artifacts,
                "artifactful": artifactful,
                "status_rank": status_rank,
                "coverage_rank": coverage_rank,
                "authority_rank": authority_rank,
                "published_with_artifacts": published_with_artifacts,
                "startup_smoke_available": startup_smoke_available,
                "generated_at_ts": generated_at_ts,
                "channel_id": str(payload.get("channelId") or payload.get("channel") or "").strip().lower(),
                "version": str(payload.get("version") or payload.get("releaseVersion") or "").strip(),
            }
        )

    now_ts = _utc_now().timestamp()
    stale_registry_paths: set[Path] = set()
    for info in candidate_infos:
        if int(info.get("authority_rank") or 0) < 1:
            continue
        registry_channel_id = str(info.get("channel_id") or "").strip().lower()
        registry_version = str(info.get("version") or "").strip()
        registry_quality = (
            int(info.get("coverage_rank") or 0),
            int(info.get("published_with_artifacts") or 0),
            int(info.get("status_rank") or 0),
            int(info.get("artifactful") or 0),
        )
        if not registry_channel_id or not registry_version:
            continue
        for candidate in candidate_infos:
            if candidate is info:
                continue
            candidate_path = candidate["path"]
            if not isinstance(candidate_path, Path):
                continue
            if str(candidate.get("channel_id") or "").strip().lower() != registry_channel_id:
                continue
            if str(candidate.get("version") or "").strip() != registry_version:
                continue
            candidate_quality = (
                int(candidate.get("coverage_rank") or 0),
                int(candidate.get("published_with_artifacts") or 0),
                int(candidate.get("status_rank") or 0),
                int(candidate.get("artifactful") or 0),
            )
            if _candidate_can_supersede_registry(candidate_path) and candidate_quality > registry_quality:
                stale_registry_paths.add(info["path"])
                break
            registry_generated_at_ts = float(info.get("generated_at_ts") or float("-inf"))
            candidate_generated_at_ts = float(candidate.get("generated_at_ts") or float("-inf"))
            registry_is_stale = (
                registry_generated_at_ts != float("-inf")
                and now_ts - registry_generated_at_ts > RELEASE_CHANNEL_REGISTRY_STALE_MAX_AGE_SECONDS
            )
            candidate_path = candidate["path"]
            if (
                candidate_quality == registry_quality
                and registry_is_stale
                and candidate_generated_at_ts > registry_generated_at_ts
                and isinstance(candidate_path, Path)
                and _candidate_is_ui_docker_manifest(candidate_path)
            ):
                stale_registry_paths.add(info["path"])
                break

    best_path: Path | None = None
    best_score: tuple[int, int, int, int, int, int, float, int] | None = None
    for info in candidate_infos:
        candidate = info["path"]
        authority_rank = int(info.get("authority_rank") or 0)
        if candidate in stale_registry_paths:
            authority_rank = -1
        score = (
            authority_rank,
            int(info.get("coverage_rank") or 0),
            int(info.get("published_with_artifacts") or 0),
            int(info.get("status_rank") or 0),
            int(info.get("artifactful") or 0),
            int(info.get("startup_smoke_available") or 0),
            float(info.get("generated_at_ts") or float("-inf")),
            -int(info.get("index") or 0),
        )
        if best_score is None or score > best_score:
            best_score = score
            best_path = candidate
    if best_path is not None:
        return best_path
    if fallback_path is not None:
        return fallback_path
    return RELEASE_CHANNEL_MANIFEST_PATH


DEFAULT_RELEASE_CHANNEL = resolve_release_channel_path()


def normalize_external_proof_relative_path(value: object, *, allow_nested: bool = True, field: str = "path") -> str:
    """Normalize a planner-supplied artifact or receipt path.

    The accepted values must be relative, not absolute, and must not contain parent-directory
    traversal segments.
    """

    raw = str(value or "").strip()
    if not raw:
        return ""

    normalized = raw.replace("\\", "/").strip()
    if normalized.startswith("/"):
        raise ValueError(f"{field} must be relative (got absolute path: {value!r})")
    if ".." in PurePosixPath(normalized).parts:
        raise ValueError(f"{field} must not contain '..' segments: {value!r}")
    parts = [part for part in PurePosixPath(normalized).parts if part]
    if not parts:
        return ""
    if any(part == "." for part in parts):
        raise ValueError(f"{field} must not contain '.' segments: {value!r}")
    if ":" in normalized:
        raise ValueError(f"{field} must not contain drive-style segments: {value!r}")
    if not allow_nested and len(parts) > 1:
        raise ValueError(f"{field} must not contain nested directories: {value!r}")
    return "/".join(parts)


def build_download_path(relative_path: str, *, base_root: Path | None = None) -> Path:
    base = UI_DOCKER_DOWNLOADS_ROOT if base_root is None else base_root
    normalized = normalize_external_proof_relative_path(relative_path)
    return base / normalized


def normalize_external_proof_tuple_id(
    value: object,
    *,
    field: str = "tuple_id",
    allow_unknown_host: bool = False,
) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    parts = [part.strip() for part in raw.split(":")]
    if len(parts) != 3:
        raise ValueError(f"{field} must be in <head>:<rid>:<host> format: {value!r}")
    if any(not part for part in parts):
        raise ValueError(f"{field} must not contain empty tuple segments: {value!r}")

    host = parts[2].lower()
    if not allow_unknown_host and host not in KNOWN_EXTERNAL_PROOF_HOSTS:
        allowed_hosts = ", ".join(sorted(KNOWN_EXTERNAL_PROOF_HOSTS))
        raise ValueError(
            f"{field} has unknown host '{host}' (expected one of: {allowed_hosts})"
        )
    parts[2] = host
    return ":".join(parts)


def host_class_matches_platform_hint(host_class: object, expected_host_contains: object) -> bool:
    actual = str(host_class or "").strip().lower()
    expected = str(expected_host_contains or "").strip().lower()
    if not expected:
        return True
    if not actual:
        return False
    aliases = HOST_CLASS_PLATFORM_ALIASES.get(expected, (expected,))
    return any(alias and alias in actual for alias in aliases)
