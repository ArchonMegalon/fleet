from __future__ import annotations

import os
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

DEFAULT_RELEASE_CHANNEL = RELEASE_CHANNEL_REPO_ROOT / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json"
UI_LOCAL_RELEASE_PROOF_PATH = UI_REPO_ROOT / ".codex-studio" / "published" / "UI_LOCAL_RELEASE_PROOF.generated.json"
UI_LOCALIZATION_RELEASE_GATE_PATH = UI_REPO_ROOT / ".codex-studio" / "published" / "UI_LOCALIZATION_RELEASE_GATE.generated.json"
UI_DOCKER_DOWNLOADS_ROOT = UI_REPO_ROOT / "Docker" / "Downloads"
UI_DOCKER_DOWNLOADS_FILES_ROOT = UI_DOCKER_DOWNLOADS_ROOT / "files"
UI_DOCKER_DOWNLOADS_STARTUP_SMOKE_ROOT = UI_DOCKER_DOWNLOADS_ROOT / "startup-smoke"
RELEASE_CHANNEL_MANIFEST_PATH = UI_REPO_ROOT / "Docker" / "Downloads" / "RELEASE_CHANNEL.generated.json"
RELEASE_CHANNEL_MIRROR_PATH = UI_REPO_ROOT / "Docker" / "Downloads" / "STARTUP_SMOKE" / "RELEASE_CHANNEL.generated.json"
KNOWN_EXTERNAL_PROOF_HOSTS = {"windows", "linux", "macos"}


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
