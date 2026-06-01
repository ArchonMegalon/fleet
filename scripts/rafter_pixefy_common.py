#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path("/docker/chummercomplete")
EA_ENV = Path("/docker/EA/.env")
COMPLETION = ROOT / "_completion"
NOW_ENV = "RAFTER_PIXEFY_GENERATED_AT_UTC"

REQUIRED_REPOS = [
    "ArchonMegalon/Chummer6",
    "ArchonMegalon/chummer6-core",
    "ArchonMegalon/chummer6-ui",
    "ArchonMegalon/chummer6-ui-kit",
    "ArchonMegalon/chummer6-hub",
    "ArchonMegalon/chummer6-hub-registry",
    "ArchonMegalon/chummer6-mobile",
    "ArchonMegalon/chummer6-media-factory",
    "ArchonMegalon/chummer6-design",
    "ArchonMegalon/fleet",
    "ArchonMegalon/executive-assistant",
]

REQUIRED_LIVE_ROUTES = [
    "https://chummer.run/",
    "https://chummer.run/downloads",
    "https://chummer.run/status",
    "https://chummer.run/ledger",
    "https://chummer.run/ledger/map",
    "https://chummer.run/ledger/factions",
    "https://chummer.run/ledger/newsroom",
    "https://chummer.run/play",
    "https://chummer.run/mobile",
    "https://chummer.run/help",
    "https://chummer.run/feedback",
]

REQUIRED_PROMOTED_PLATFORM_HEAD_RID_TUPLES = [
    "avalonia:linux-x64:linux",
    "avalonia:osx-arm64:macos",
    "avalonia:win-x64:windows",
]

RELEASE_CHANNEL_CANDIDATE_PATHS = [
    WORKSPACE_ROOT / "chummer-hub-registry" / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json",
    WORKSPACE_ROOT / "chummer.run-services" / "Chummer.Portal" / "downloads" / "RELEASE_CHANNEL.generated.json",
    WORKSPACE_ROOT / "chummer-presentation" / "Chummer.Portal" / "downloads" / "RELEASE_CHANNEL.generated.json",
    WORKSPACE_ROOT / ".tmp-hub-main-widen" / ".codex-studio" / "published" / "RELEASE_CHANNEL.generated.json",
]

PIXEFY_DEVICES = [
    {"id": "iphone_se", "class": "mobile", "viewport": "375x667"},
    {"id": "iphone_pro", "class": "mobile", "viewport": "393x852"},
    {"id": "iphone_pro_max", "class": "mobile", "viewport": "430x932"},
    {"id": "android_small", "class": "mobile", "viewport": "360x740"},
    {"id": "android_large", "class": "mobile", "viewport": "412x915"},
    {"id": "ipad_portrait", "class": "tablet", "viewport": "768x1024"},
    {"id": "ipad_landscape", "class": "tablet", "viewport": "1024x768"},
    {"id": "desktop_1366", "class": "desktop", "viewport": "1366x768"},
    {"id": "desktop_1440", "class": "desktop", "viewport": "1440x900"},
    {"id": "desktop_1920", "class": "desktop", "viewport": "1920x1080"},
    {"id": "desktop_ultrawide", "class": "desktop", "viewport": "2560x1080"},
]

PIXEFY_ROUTES = [
    {"id": "home", "url": "https://chummer.run/", "checks": ["black_ledger_hero_visible", "primary_cta_visible", "no_dead_buttons", "no_demo_runner_copy"]},
    {"id": "downloads", "url": "https://chummer.run/downloads", "checks": ["platform_cards_visible", "no_contradictory_platform_copy", "no_demo_runner_copy", "download_ctas_visible"]},
    {"id": "status", "url": "https://chummer.run/status", "checks": ["release_channel_visible", "build_visible", "proof_freshness_visible", "no_gold_claim_if_stale"]},
    {"id": "ledger", "url": "https://chummer.run/ledger", "checks": ["ledger_shell_visible", "faction_entry_visible", "globe_or_video_globe_visible", "no_dead_links"]},
    {"id": "ledger_map", "url": "https://chummer.run/ledger/map", "checks": ["globe_large_enough", "markers_readable", "score_strip_readable", "hover_or_focus_states_work"]},
    {"id": "ledger_factions", "url": "https://chummer.run/ledger/factions", "checks": ["all_seeded_factions_visible", "faction_cards_have_logo_or_identity", "no_empty_subpages"]},
    {"id": "ledger_newsroom", "url": "https://chummer.run/ledger/newsroom", "checks": ["newsreel_page_visible", "poster_or_video_visible", "transcript_link_visible"]},
    {"id": "play", "url": "https://chummer.run/play", "checks": ["pwa_install_guidance_visible", "mobile_layout_usable"]},
    {"id": "help", "url": "https://chummer.run/help", "checks": ["support_route_visible", "no_rules_copyright_overexposure"]},
    {"id": "feedback", "url": "https://chummer.run/feedback", "checks": ["productlift_or_feedback_surface_visible", "no_dead_form"]},
]

REPO_PATHS = {
    "ArchonMegalon/Chummer6": WORKSPACE_ROOT / "Chummer6",
    "ArchonMegalon/chummer6-core": WORKSPACE_ROOT / "chummer-core-engine",
    "ArchonMegalon/chummer6-ui": WORKSPACE_ROOT / "chummer-presentation",
    "ArchonMegalon/chummer6-ui-kit": WORKSPACE_ROOT / "chummer-ui-kit",
    "ArchonMegalon/chummer6-hub": WORKSPACE_ROOT / "chummer.run-services",
    "ArchonMegalon/chummer6-hub-registry": WORKSPACE_ROOT / "chummer-hub-registry",
    "ArchonMegalon/chummer6-mobile": WORKSPACE_ROOT / ".tmp-mobile-main-widen",
    "ArchonMegalon/chummer6-media-factory": Path("/docker/fleet/repos/chummer-media-factory"),
    "ArchonMegalon/chummer6-design": WORKSPACE_ROOT / "chummer-design",
    "ArchonMegalon/fleet": ROOT,
    "ArchonMegalon/executive-assistant": Path("/docker/EA"),
}


def now_utc() -> str:
    return os.environ.get(NOW_ENV) or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git_root() -> Path:
    return ROOT


def secret_scan_paths() -> list[Path]:
    return [
        ROOT / "LTDs.md",
        ROOT / "providers" / "rafter" / "local",
        ROOT / "providers" / "pixefy" / "local",
        ROOT / ".github",
    ]


def run_git_grep(pattern: str) -> list[str]:
    paths = [str(path.relative_to(ROOT)) for path in secret_scan_paths() if path.exists()]
    if not paths:
        return []
    result = subprocess.run(
        ["git", "grep", "-nI", "-E", pattern, "--", *paths],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode not in (0, 1):
        return [f"git_grep_failed:{result.returncode}"]
    return [line for line in result.stdout.splitlines() if line.strip()]


def load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_json(path)
    except (OSError, json.JSONDecodeError):
        return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def active_release_binding(generated_at_utc: str | None = None) -> dict[str, Any]:
    generated = generated_at_utc or now_utc()
    checked = [str(path) for path in RELEASE_CHANNEL_CANDIDATE_PATHS]
    for path in RELEASE_CHANNEL_CANDIDATE_PATHS:
        payload = load_optional_json(path)
        if not payload:
            continue

        coverage = payload.get("desktopTupleCoverage") if isinstance(payload.get("desktopTupleCoverage"), dict) else {}
        promoted_tuples = _string_list(coverage.get("promotedPlatformHeadRidTuples"))
        missing_tuples = _string_list(coverage.get("missingRequiredPlatformHeadRidTuples"))
        missing_required = [
            tuple_id
            for tuple_id in REQUIRED_PROMOTED_PLATFORM_HEAD_RID_TUPLES
            if tuple_id not in promoted_tuples
        ]
        channel_id = str(payload.get("channelId") or payload.get("channel") or "").strip()
        release_status = str(payload.get("status") or "").strip()
        rollout_state = str(payload.get("rolloutState") or "").strip()
        version = str(payload.get("version") or payload.get("releaseVersion") or "").strip()
        artifacts = payload.get("artifacts")
        verification_failures = []
        if channel_id != "public_stable":
            verification_failures.append("release_channel_not_public_stable")
        if release_status != "published":
            verification_failures.append("release_status_not_published")
        if rollout_state != "public_stable":
            verification_failures.append("release_rollout_state_not_public_stable")
        if not version:
            verification_failures.append("release_version_missing")
        if missing_tuples:
            verification_failures.append("release_channel_missing_promoted_tuples")
        if missing_required:
            verification_failures.append("release_channel_missing_required_build_tuple")

        return {
            "verified_at_utc": generated,
            "source_path": str(path),
            "source_paths_checked": checked,
            "base_url": "https://chummer.run",
            "channelId": channel_id,
            "channel": str(payload.get("channel") or channel_id),
            "status": release_status,
            "rolloutState": rollout_state,
            "version": version,
            "publishedAt": payload.get("publishedAt") or payload.get("published_at"),
            "generatedAt": payload.get("generatedAt") or payload.get("generated_at"),
            "artifact_count": len(artifacts) if isinstance(artifacts, list) else None,
            "promotedPlatformHeadRidTuples": promoted_tuples,
            "requiredPromotedPlatformHeadRidTuples": REQUIRED_PROMOTED_PLATFORM_HEAD_RID_TUPLES,
            "missingRequiredPlatformHeadRidTuples": missing_tuples,
            "missingRequiredPromotedPlatformHeadRidTuples": missing_required,
            "verification_status": "pass" if not verification_failures else "fail",
            "verification_failures": verification_failures,
        }

    return {
        "verified_at_utc": generated,
        "source_path": "",
        "source_paths_checked": checked,
        "base_url": "https://chummer.run",
        "channelId": "",
        "channel": "",
        "status": "missing",
        "rolloutState": "",
        "version": "",
        "publishedAt": None,
        "generatedAt": None,
        "artifact_count": None,
        "promotedPlatformHeadRidTuples": [],
        "requiredPromotedPlatformHeadRidTuples": REQUIRED_PROMOTED_PLATFORM_HEAD_RID_TUPLES,
        "missingRequiredPlatformHeadRidTuples": [],
        "missingRequiredPromotedPlatformHeadRidTuples": REQUIRED_PROMOTED_PLATFORM_HEAD_RID_TUPLES,
        "verification_status": "fail",
        "verification_failures": ["release_channel_manifest_missing"],
    }


def parse_env_file(path: Path = EA_ENV) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def secret_fingerprint(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16] if value else ""


def probe_url(url: str, *, timeout: int = 25) -> dict[str, Any]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "chummer-rafter-pixefy-release-gate/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(600_000).decode("utf-8", "ignore")
            lowered = body.lower()
            return {
                "url": url,
                "status_code": int(response.status),
                "body_bytes_sampled": len(body.encode("utf-8")),
                "ok": 200 <= int(response.status) < 400,
                "forbidden_public_copy_hits": [
                    label
                    for label, patterns in {
                        "demo runner": ("demo runner",),
                        "debug": ("debug",),
                        "repo copy": ("repo tour", "repository tour", "github repo", "source repo"),
                        "codex": ("codex",),
                    }.items()
                    if any(pattern in lowered for pattern in patterns)
                ],
            }
    except Exception as exc:  # noqa: BLE001 - gate receipt needs exact failure class.
        return {
            "url": url,
            "status_code": None,
            "body_bytes_sampled": 0,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "forbidden_public_copy_hits": [],
        }
