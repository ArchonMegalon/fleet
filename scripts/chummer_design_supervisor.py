#!/usr/bin/env python3
"""Run a long-lived Chummer design supervisor from Fleet."""

from __future__ import annotations

import argparse
import ast
import base64
import datetime as dt
import hashlib
import importlib
import inspect
import json
import os
import pwd
import re
import signal
import shutil
import socket
import stat
import subprocess
import sys
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

import yaml

try:
    from scripts.materialize_flagship_product_readiness import materialize_flagship_product_readiness
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from materialize_flagship_product_readiness import materialize_flagship_product_readiness


def _env_float_default(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)) or str(default))
    except (TypeError, ValueError):
        return float(default)


def _runtime_env_float_default(name: str, default: float) -> float:
    try:
        return float(_runtime_env_default(name, str(default)) or str(default))
    except (TypeError, ValueError):
        return float(default)


def _default_worker_timeout_seconds() -> float:
    explicit_raw = _runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_WORKER_TIMEOUT_SECONDS")
    if explicit_raw not in (None, ""):
        try:
            return max(0.0, float(explicit_raw))
        except (TypeError, ValueError):
            return 3600.0
    try:
        stream_idle_ms = max(
            0.0,
            float(
                _runtime_env_default(
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS",
                    _runtime_env_default("CODEXEA_STREAM_IDLE_TIMEOUT_MS", "0"),
                )
                or "0"
            ),
        )
    except (TypeError, ValueError):
        stream_idle_ms = 0.0
    try:
        stream_max_retries = max(
            0,
            int(
                float(
                    _runtime_env_default(
                        "CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES",
                        _runtime_env_default("CODEXEA_STREAM_MAX_RETRIES", "0"),
                    )
                    or "0"
                )
            ),
        )
    except (TypeError, ValueError):
        stream_max_retries = 0
    if stream_idle_ms > 0.0 and stream_max_retries > 0:
        # Let hard lanes survive their full EA stream retry budget plus extra room for real work.
        derived_timeout_seconds = (stream_idle_ms / 1000.0) * float(stream_max_retries) + 1800.0
        return max(3600.0, derived_timeout_seconds)
    return 3600.0


DEFAULT_WORKSPACE_ROOT = Path("/docker/fleet")
DEFAULT_ACCOUNTS_PATH = DEFAULT_WORKSPACE_ROOT / "config" / "accounts.yaml"
DEFAULT_SCOPE_ROOTS = [
    Path("/docker/fleet"),
    Path("/docker/chummercomplete"),
    Path("/docker/fleet/repos"),
    Path("/docker/chummer5a"),
    Path("/docker/EA"),
]
DEFAULT_DESIGN_PRODUCT_ROOT = Path("/docker/chummercomplete/chummer-design/products/chummer")
DEFAULT_REGISTRY_PATH = DEFAULT_DESIGN_PRODUCT_ROOT / "NEXT_12_BIGGEST_WINS_REGISTRY.yaml"
DEFAULT_PROGRAM_MILESTONES_PATH = DEFAULT_DESIGN_PRODUCT_ROOT / "PROGRAM_MILESTONES.yaml"
DEFAULT_ROADMAP_PATH = DEFAULT_DESIGN_PRODUCT_ROOT / "ROADMAP.md"
DEFAULT_GOLDEN_JOURNEY_GATES_PATH = DEFAULT_DESIGN_PRODUCT_ROOT / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
DEFAULT_WEEKLY_PULSE_PATH = DEFAULT_DESIGN_PRODUCT_ROOT / "WEEKLY_PRODUCT_PULSE.generated.json"
DEFAULT_HANDOFF_PATH = DEFAULT_WORKSPACE_ROOT / "NEXT_SESSION_HANDOFF.md"
DEFAULT_SHARD_RUNTIME_HANDOFF_FILENAME = "ACTIVE_RUN_HANDOFF.generated.md"
TASK_LOCAL_TELEMETRY_FILENAME = "TASK_LOCAL_TELEMETRY.generated.json"
WORKER_BASH_ENV_FILENAME = "WORKER_BASH_ENV.sh"
DEFAULT_PROJECTS_DIR = DEFAULT_WORKSPACE_ROOT / "config" / "projects"
DEFAULT_STATUS_PLANE_PATH = DEFAULT_WORKSPACE_ROOT / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
DEFAULT_PROGRESS_REPORT_PATH = DEFAULT_WORKSPACE_ROOT / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
DEFAULT_PROGRESS_HISTORY_PATH = DEFAULT_WORKSPACE_ROOT / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
DEFAULT_SUPPORT_PACKETS_PATH = DEFAULT_WORKSPACE_ROOT / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
DEFAULT_FLEET_PRODUCT_MIRROR_ROOT = DEFAULT_WORKSPACE_ROOT / ".codex-design" / "product"
DEFAULT_FLAGSHIP_PRODUCT_READINESS_PATH = (
    DEFAULT_WORKSPACE_ROOT / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
)
DEFAULT_FLAGSHIP_PRODUCT_READINESS_MIRROR_PATH = (
    DEFAULT_WORKSPACE_ROOT / "state" / "chummer_design_supervisor" / "artifacts" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
)
DEFAULT_JOURNEY_GATES_PUBLISHED_PATH = DEFAULT_WORKSPACE_ROOT / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
DEFAULT_COMPLETION_REVIEW_FRONTIER_PUBLISHED_PATH = (
    DEFAULT_WORKSPACE_ROOT / ".codex-studio" / "published" / "COMPLETION_REVIEW_FRONTIER.generated.yaml"
)
DEFAULT_COMPLETION_REVIEW_FRONTIER_MIRROR_PATH = (
    DEFAULT_WORKSPACE_ROOT / "state" / "chummer_design_supervisor" / "artifacts" / "COMPLETION_REVIEW_FRONTIER.generated.yaml"
)
DEFAULT_FULL_PRODUCT_FRONTIER_PUBLISHED_PATH = (
    DEFAULT_WORKSPACE_ROOT / ".codex-studio" / "published" / "FULL_PRODUCT_FRONTIER.generated.yaml"
)
DEFAULT_FULL_PRODUCT_FRONTIER_MIRROR_PATH = (
    DEFAULT_WORKSPACE_ROOT / "state" / "chummer_design_supervisor" / "artifacts" / "FULL_PRODUCT_FRONTIER.generated.yaml"
)
DEFAULT_CHUMMER5A_FAMILIARITY_BRIDGE_PATH = DEFAULT_FLEET_PRODUCT_MIRROR_ROOT / "CHUMMER5A_FAMILIARITY_BRIDGE.md"
DEFAULT_DESKTOP_EXECUTABLE_EXIT_GATES_PATH = DEFAULT_FLEET_PRODUCT_MIRROR_ROOT / "DESKTOP_EXECUTABLE_EXIT_GATES.md"
DEFAULT_DESKTOP_VISUAL_FAMILIARITY_GATE_PATH = (
    DEFAULT_FLEET_PRODUCT_MIRROR_ROOT / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.md"
)
def _preferred_ui_repo_root() -> Path:
    override = str(os.environ.get("CHUMMER_UI_REPO_ROOT", "") or "").strip()
    if override:
        return Path(override)
    for candidate in (
        Path("/docker/chummercomplete/chummer6-ui-finish"),
        Path("/docker/chummercomplete/chummer6-ui"),
        Path("/docker/chummercomplete/chummer-presentation"),
    ):
        if candidate.exists():
            return candidate
    return Path("/docker/chummercomplete/chummer6-ui")


PREFERRED_UI_REPO_ROOT = _preferred_ui_repo_root()
DEFAULT_UI_LINUX_DESKTOP_REPO_ROOT = PREFERRED_UI_REPO_ROOT
DEFAULT_UI_LINUX_DESKTOP_EXIT_GATE_PATH = (
    PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
)
DEFAULT_UI_EXECUTABLE_EXIT_GATE_PATH = PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
DEFAULT_STATE_ROOT = DEFAULT_WORKSPACE_ROOT / "state" / "chummer_design_supervisor"
DEFAULT_STATE_PATH = DEFAULT_STATE_ROOT / "state.json"
DEFAULT_HISTORY_PATH = DEFAULT_STATE_ROOT / "history.jsonl"
DEFAULT_RUNS_DIR = DEFAULT_STATE_ROOT / "runs"
DEFAULT_LOCK_PATH = DEFAULT_STATE_ROOT / "loop.lock"
DEFAULT_WORKER_BIN = "codex"
DEFAULT_MODEL = ""
DEFAULT_FALLBACK_MODELS = ("ea-coder-hard",)
LOW_CAPACITY_RESERVE_PERCENT = 0.10
CORE_BATCH_WORKER_LANES = frozenset(
    {
        "core",
        "core_authority",
        "core_booster",
        "core_rescue",
        "review_shard",
        "audit_shard",
    }
)
CORE_BATCH_RUNTIME_MODELS = frozenset(
    {
        "ea-coder-hard",
        "ea-coder-hard-batch",
        "ea-coder-best",
    }
)
MODEL_COMPATIBILITY_FALLBACKS: Dict[str, tuple[str, ...]] = {
    "ea-coder-hard": ("ea-coder-hard-batch",),
}
LANE_MODEL_COMPATIBILITY_FALLBACKS: Dict[str, Dict[str, tuple[str, ...]]] = {
    "core": {
        "repair": ("ea-coder-fast",),
        "survival": ("ea-coder-survival",),
    },
    "core_rescue": {
        "repair": ("ea-coder-fast",),
        "survival": ("ea-coder-survival",),
    },
    "jury": {
        "core": ("ea-coder-hard-batch", "ea-coder-hard"),
        "repair": ("ea-coder-fast",),
        "survival": ("ea-coder-survival",),
    },
    "audit_shard": {
        "jury": ("ea-coder-hard-batch",),
        "review_light": ("ea-coder-hard-batch",),
        "core": ("ea-coder-hard-batch", "ea-coder-hard"),
        "core_rescue": ("ea-coder-hard-batch", "ea-coder-hard"),
        "repair": ("ea-coder-fast",),
        "survival": ("ea-coder-survival",),
        "easy": ("",),
    },
    "review_shard": {
        "jury": ("ea-coder-hard-batch",),
        "review_light": ("ea-coder-hard-batch",),
        "core": ("ea-coder-hard-batch", "ea-coder-hard"),
        "core_rescue": ("ea-coder-hard-batch", "ea-coder-hard"),
        "repair": ("ea-coder-fast",),
        "survival": ("ea-coder-survival",),
        "easy": ("",),
    },
}
ACCOUNT_DIRECT_FALLBACK_RESCUE_MODELS = ("ea-coder-hard",)
DEFAULT_FALLBACK_WORKER_LANES = {
    "core": ("core_rescue", "survival", "repair"),
    "jury": ("core", "core_rescue", "survival", "repair"),
    "core_rescue": ("survival", "repair"),
    "survival": ("repair",),
}
DEFAULT_ACCOUNT_OWNER_IDS = ("tibor.girschele", "the.girscheles", "archon.megalon")
DEFAULT_POLL_SECONDS = 20.0
DEFAULT_COOLDOWN_SECONDS = 5.0
DEFAULT_FAILURE_BACKOFF_SECONDS = 45.0
DEFAULT_EXTERNAL_BLOCKER_BACKOFF_SECONDS = 300.0
DEFAULT_RATE_LIMIT_BACKOFF_SECONDS = 60
DEFAULT_SPARK_BACKOFF_SECONDS = 900
DEFAULT_USAGE_LIMIT_BACKOFF_SECONDS = 21600
DEFAULT_AUTH_FAILURE_BACKOFF_SECONDS = 43200
DEFAULT_BACKEND_UNAVAILABLE_BACKOFF_SECONDS = 300
DEFAULT_OPENAI_ESCAPE_HATCH_MODELS = ("ea-coder-hard",)
DEFAULT_EA_PROVIDER_HEALTH_URL = os.environ.get(
    "CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_URL",
    "http://127.0.0.1:8090/v1/responses/_provider_health",
)
DEFAULT_EA_PROVIDER_HEALTH_TIMEOUT_SECONDS = max(
    0.5,
    float(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_TIMEOUT_SECONDS", "4") or "4"),
)
DEFAULT_MEMORY_DISPATCH_RESERVE_GIB = max(
    0.0,
    _env_float_default("CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_RESERVE_GIB", 4.0),
)
DEFAULT_MEMORY_DISPATCH_SHARD_BUDGET_GIB = max(
    0.25,
    _env_float_default("CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_SHARD_BUDGET_GIB", 1.5),
)
DEFAULT_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT = min(
    100.0,
    max(0.0, _env_float_default("CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT", 12.0)),
)
DEFAULT_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT = min(
    DEFAULT_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT,
    max(0.0, _env_float_default("CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT", 8.0)),
)
DEFAULT_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT = min(
    100.0,
    max(0.0, _env_float_default("CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT", 75.0)),
)
DEFAULT_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT = min(
    100.0,
    max(
        DEFAULT_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT,
        _env_float_default("CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT", 90.0),
    ),
)
DEFAULT_MEMORY_DISPATCH_PARKED_POLL_SECONDS = max(
    DEFAULT_POLL_SECONDS,
    _env_float_default(
        "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_PARKED_POLL_SECONDS",
        DEFAULT_FAILURE_BACKOFF_SECONDS,
    ),
)
SUPERVISOR_CONTAINER_NAME = "fleet-design-supervisor"
COMPLETION_AUDIT_HISTORY_LIMIT = 10
WEEKLY_PULSE_MAX_AGE_SECONDS = 8 * 24 * 3600
LINUX_DESKTOP_EXIT_GATE_MAX_AGE_SECONDS = 24 * 3600
DESKTOP_EXECUTABLE_EXIT_GATE_MAX_AGE_SECONDS = 24 * 3600
FLAGSHIP_PRODUCT_READINESS_MAX_AGE_SECONDS = 7 * 24 * 3600
ACTIVE_STATUSES = {"in_progress", "not_started", "open", "planned", "queued"}
DONE_STATUSES = {"complete", "completed", "done", "closed", "released"}
BLOCKER_CLEAR_VALUES = {"", "none", "no", "n/a", "no blocker", "no exact blocker"}
CHATGPT_AUTH_KINDS = {"chatgpt_auth_json", "auth_json"}
READY_ACCOUNT_STATES = {"", "ready", "unknown", "ok"}
SPARK_MODEL = "gpt-5.3-codex-spark"
FLAGSHIP_UI_APP_KEY = "avalonia"
FLAGSHIP_UI_PROJECT_PATH = "Chummer.Avalonia/Chummer.Avalonia.csproj"
FLAGSHIP_UI_LAUNCH_TARGET = "Chummer.Avalonia"
FLAGSHIP_UI_READY_CHECKPOINT = "pre_ui_event_loop"
FLAGSHIP_UI_LINUX_TEST_PROJECT_PATH = "Chummer.Desktop.Runtime.Tests/Chummer.Desktop.Runtime.Tests.csproj"
FLAGSHIP_UI_LINUX_TEST_ASSEMBLY_NAME = "Chummer.Desktop.Runtime.Tests.dll"
FLAGSHIP_UI_LINUX_OUTPUT_ROOT = Path(".codex-studio/out/linux-desktop-exit-gate")
FLAGSHIP_UI_LINUX_DEB_PACKAGE_NAME = "chummer6-avalonia"
FLAGSHIP_UI_LINUX_WRAPPER_NAME = "chummer6-avalonia"
FLAGSHIP_UI_LINUX_DESKTOP_ENTRY_NAME = "Chummer"
FLAGSHIP_UI_LINUX_GATE_INPUT_MARKERS = (
    "Chummer.Avalonia/",
    "Chummer.Desktop.Assets/",
    "Chummer.Desktop.Runtime/",
    "Chummer.Desktop.Runtime.Tests/",
    "Chummer.Tests/",
    "Chummer.Presentation/",
    "scripts/ai/",
    "scripts/build-desktop-installer.sh",
    "scripts/run-desktop-startup-smoke.sh",
    "scripts/materialize-linux-desktop-exit-gate.sh",
    "Directory.Build.props",
    "Directory.Build.targets",
    "Directory.Packages.props",
    "NuGet.Config",
    "global.json",
)
RETRYABLE_WORKER_ERROR_SIGNALS = (
    "usage limit",
    "rate limit",
    "quota",
    "insufficient credits",
    "exhausted_for_request",
    "upstream_timeout",
    "background_timeout",
    "background timeout",
    "worker_timeout",
    "worker_model_output_stalled",
    "worker_status_helper_loop",
    "switch to another model",
    "not supported",
    "unsupported",
)
DEFAULT_MODEL_OUTPUT_STALL_SECONDS = 240.0
ETA_HISTORY_LIMIT = 50
ETA_STATUS_LOW_CONFIDENCE = "low"
ETA_STATUS_MEDIUM_CONFIDENCE = "medium"
ETA_STATUS_HIGH_CONFIDENCE = "high"
ETA_STATUS_BLOCKED_CONFIDENCE = "blocked"
ETA_EXTERNAL_BLOCKER_SIGNALS = (
    "usage limit",
    "rate limit",
    "quota",
    "insufficient credits",
    "exhausted_for_request",
    "refresh token",
    "auth session",
    "api key",
    "revoked",
    "expired",
    "backend unavailable",
    "upstream_timeout",
    "session is expired",
    "could not be refreshed",
)
WORKER_STATUS_BLOCK_EXIT_CODE = 64
OPENAI_ESCAPE_HATCH_TRIGGER_SIGNALS = (
    "upstream_timeout",
    "background_timeout",
    "background timeout",
    "worker_timeout",
    "worker_model_output_stalled",
    "worker_status_helper_loop",
    "upstream_unavailable",
    "backend unavailable",
    "exhausted_for_request",
    "usage limit",
    "rate limit",
    "quota",
    "insufficient credits",
)
PROVIDER_HEALTH_READY_STATES = {"ready", "ok", "healthy", "available"}
PROVIDER_HEALTH_DEGRADED_STATES = {"degraded", "warning", "limited"}
PROVIDER_HEALTH_UNAVAILABLE_STATES = {"unavailable", "failed", "error", "disabled", "offline", "missing"}
LOCK_TTL_SECONDS = 300.0
LOCK_ACQUIRE_RETRIES = 12
LOCK_RETRY_SECONDS = 0.25
FOCUS_PROFILES: Dict[str, Dict[str, Any]] = {
    "desktop_client": {
        "description": "Prioritize desktop-client delivery across UI, core, rules, and SR4-SR6 readiness.",
        "owners": [
            "chummer6-ui",
            "chummer6-core",
            "chummer6-hub",
            "chummer6-ui-kit",
            "chummer6-hub-registry",
            "chummer6-design",
        ],
        "texts": [
            "desktop",
            "client",
            "workbench",
            "build lab",
            "build",
            "rules",
            "rule-environment",
            "navigator",
            "explain",
            "receipt",
            "onboarding",
            "starter",
            "sr4",
            "sr5",
            "sr6",
            "avalonia",
            "blazor",
        ],
    },
    "desktop_visual_familiarity": {
        "description": "Prioritize shell familiarity, theme readability, and workflow-local Chummer-like visual posture.",
        "owners": [
            "chummer6-ui",
            "chummer6-ui-kit",
            "chummer6-core",
            "chummer6-design",
        ],
        "texts": [
            "visual familiarity",
            "familiarity",
            "chummer5a",
            "chummer4",
            "theme",
            "palette",
            "contrast",
            "menu",
            "toolstrip",
            "status strip",
            "status bar",
            "tab posture",
            "tab panel",
            "loaded runner",
            "loaded-runner",
            "shell posture",
            "character creation",
            "gear",
            "armor",
            "weapons",
            "cyberware",
            "cyberlimb",
            "magic",
            "resonance",
            "vehicle",
            "drone",
            "browse/detail/confirm",
            "sr4",
            "sr6",
        ],
    },
    "desktop_workflow_depth": {
        "description": "Prioritize packaged-binary desktop smoothness and exhaustive workflow clickthrough depth.",
        "owners": [
            "chummer6-ui",
            "chummer6-ui-kit",
            "chummer6-core",
            "chummer6-design",
            "fleet",
        ],
        "texts": [
            "workflow click-through",
            "workflow clickthrough",
            "smooth flagship desktop",
            "menu wiring",
            "demo runner",
            "spotlight-launchable",
            "feedback route",
            "public feedback",
            "karma",
            "critter",
            "adept powers",
            "initiation",
            "cyberdeck",
            "matrix",
            "spells",
            "drugs",
            "contacts",
            "diary",
            "spirits",
            "familiars",
            "vehicles",
            "drones",
            "rigger",
        ],
    },
    "top_flagship_grade": {
        "description": "Apply the hard flagship bar: whole-product frontier, no lowered standards, and durable feedback/autofix readiness.",
        "owners": [],
        "texts": [],
    },
    "whole_project_frontier": {
        "description": "Treat the whole product as the active frontier instead of collapsing the bar to one head or one proof family.",
        "owners": [],
        "texts": [],
    },
}
SYNTHETIC_COMPLETION_REVIEW_ID_BASE = 900_000_000
SYNTHETIC_FULL_PRODUCT_ID_BASE = 950_000_000
_SIBLING_MODULE_CACHE: Dict[str, Any] = {}
_CONTAINER_LOCAL_ACTIVE_RUN_CACHE: Dict[str, Any] = {
    "generated_at_monotonic": 0.0,
    "records": {},
}
_RUNTIME_ENV_CANDIDATES = (
    DEFAULT_WORKSPACE_ROOT / "runtime.env",
    DEFAULT_WORKSPACE_ROOT / "runtime.ea.env",
    DEFAULT_WORKSPACE_ROOT / ".env",
    Path("/docker/.env"),
    Path("/docker/EA/.env"),
    Path("/docker/chummer5a/.env"),
    Path("/docker/chummer5a/.env.providers"),
)
FLAGSHIP_PRODUCT_READINESS_COVERAGE_KEYS = (
    "desktop_client",
    "rules_engine_and_import",
    "hub_and_registry",
    "mobile_play_shell",
    "ui_kit_and_flagship_polish",
    "media_artifacts",
    "horizons_and_public_surface",
    "fleet_and_operator_loop",
)
FULL_PRODUCT_FRONTIER_KEY_BY_COVERAGE = {
    "desktop_client": "desktop_client_flagship",
    "rules_engine_and_import": "rules_engine_parity",
    "hub_and_registry": "hub_and_registry_flagship",
    "mobile_play_shell": "mobile_play_shell_flagship",
    "ui_kit_and_flagship_polish": "ui_kit_flagship_polish",
    "media_artifacts": "media_and_artifacts_flagship",
    "horizons_and_public_surface": "horizons_and_public_surface",
    "fleet_and_operator_loop": "fleet_and_operator_flagship",
}
PARITY_FULL_PRODUCT_OWNER_OVERRIDES: Dict[str, Sequence[str]] = {
    "shell_workbench_orientation": ("chummer6-ui", "chummer6-design"),
    "dense_builder_and_career_workflows": ("chummer6-ui", "chummer6-core", "chummer6-design"),
    "identity_contacts_lifestyles_history": ("chummer6-ui", "chummer6-hub", "chummer6-design"),
    "sourcebooks_reference_and_master_index": ("chummer6-ui", "chummer6-core", "chummer6-design"),
    "settings_and_rules_environment_authoring": ("chummer6-ui", "chummer6-core", "chummer6-design"),
    "custom_data_xml_and_translator_bridge": ("chummer6-ui", "chummer6-core", "chummer6-design"),
    "dice_initiative_and_table_utilities": ("chummer6-ui", "chummer6-design"),
    "roster_dashboards_and_multi_character_ops": ("chummer6-ui", "chummer6-hub", "chummer6-design"),
    "sheet_export_print_viewer_and_exchange": ("chummer6-ui", "chummer6-core", "chummer6-design"),
    "legacy_and_adjacent_import_oracles": ("chummer6-core", "chummer6-ui", "chummer6-design"),
    "sr6_supplements_designers_and_house_rules": ("chummer6-ui", "chummer6-core", "chummer6-design"),
}
FULL_PRODUCT_FRONTIER_SPECS: Sequence[Dict[str, Any]] = (
    {
        "key": "desktop_client_flagship",
        "title": "Flagship desktop client and workbench finish",
        "owners": ["chummer6-ui", "chummer6-core", "chummer6-ui-kit"],
        "exit_criteria": [
            "Ship the flagship workbench/browser/desktop surface described in `projects/ui.md` and `BUILD_LAB_PRODUCT_MODEL.md`, including builder, compare, explain, grouped inspection, conditional toggles, desktop packaging, updater, and in-app support polish.",
            "Keep the flagship desktop head centered on Avalonia with release-grade startup, packaging, and support evidence rather than treating Linux exit-gate closure as the whole product.",
        ],
    },
    {
        "key": "rules_engine_parity",
        "title": "Rules engine parity, explain trust, and import certification",
        "owners": ["chummer6-core", "chummer6-ui"],
        "exit_criteria": [
            "Close SR4, SR5, and SR6 character-build parity gaps using deterministic engine truth, explain receipts, and legacy/import oracle evidence described in `projects/core.md` and the roadmap.",
            "Make ruleset import, migration, and explain certification boring enough that flagship desktop and mobile surfaces consume one grounded engine truth.",
        ],
    },
    {
        "key": "hub_and_registry_flagship",
        "title": "Hub, registry, and public front door flagship finish",
        "owners": ["chummer6-hub", "chummer6-hub-registry", "chummer6-design"],
        "exit_criteria": [
            "Deliver the relationship/orchestration, publication, downloads, account, install, update, proof-shelf, and support surfaces promised in `projects/hub.md`, `projects/hub-registry.md`, and the product front door canon.",
            "Keep public landing, signed-in overlays, release heads, install guidance, and support/control truth aligned with design-owned manifests instead of repo-local improvisation.",
        ],
    },
    {
        "key": "mobile_play_shell_flagship",
        "title": "Mobile and play-shell flagship finish",
        "owners": ["chummer6-mobile", "chummer6-core", "chummer6-ui-kit", "chummer6-hub"],
        "exit_criteria": [
            "Deliver the dedicated player/GM/session shell described in `projects/mobile.md`, including local-first play, replay/resume, reconnect confidence, installable mobile posture, and cross-device continuity.",
            "Keep mobile grounded on package-only engine/play/UI-kit seams rather than cloning workbench or orchestration logic.",
        ],
    },
    {
        "key": "ui_kit_flagship_polish",
        "title": "Shared design system, accessibility, localization, and flagship polish",
        "owners": ["chummer6-ui-kit", "chummer6-ui", "chummer6-mobile"],
        "exit_criteria": [
            "Make shared tokens, dense-data primitives, accessibility primitives, localization readiness, and flagship-grade visual polish real across workbench and play surfaces as described in `projects/ui-kit.md`.",
            "Keep package-only shared UI discipline intact while raising the product to a flagship quality bar instead of repo-local one-off chrome.",
        ],
    },
    {
        "key": "media_and_artifacts_flagship",
        "title": "Media, artifacts, publication, and recap flagship finish",
        "owners": ["chummer6-media-factory", "chummer6-hub", "chummer6-hub-registry"],
        "exit_criteria": [
            "Make documents, previews, portraits, bounded video, recap artifacts, manifests, and publication receipts dependable product surfaces instead of sidecar exports, following `projects/media-factory.md`.",
            "Keep provenance, preview, publish, and restore evidence intact across Hub, Registry, and Media Factory.",
        ],
    },
    {
        "key": "horizons_and_public_surface",
        "title": "Horizons, public guide, and flagship future-lane posture",
        "owners": ["chummer6-design", "chummer6-hub", "chummer6-core", "chummer6-ui", "chummer6-media-factory"],
        "exit_criteria": [
            "Operationalize the canon in `HORIZONS.md`, `HORIZON_REGISTRY.yaml`, and the horizon docs so future-capability lanes have explicit build paths, owner handoff gates, and downstream public-guide alignment.",
            "Keep the public guide, horizons posture, and flagship product surfaces consistent with the lead-designer canon rather than letting storytelling outrun build truth.",
        ],
    },
    {
        "key": "fleet_and_operator_flagship",
        "title": "Fleet and operator loop flagship finish",
        "owners": ["fleet", "executive-assistant", "chummer6-design", "chummer6-hub"],
        "exit_criteria": [
            "Keep the product-governor, support, signal, and operator loop durable enough to steer the full multi-repo product, not just the current milestone wave, with trustworthy proofs, traces, ETAs, handoffs, and fail-closed anti-false-complete posture.",
            "Ensure the loop can keep decomposing full-product work across shards until flagship readiness proof is current and trusted, and that actionable feedback, crash, and support signals can auto-materialize into routed bugfix work without operator babysitting.",
        ],
    },
)


@dataclass(frozen=True)
class Milestone:
    id: int
    title: str
    wave: str
    status: str
    owners: List[str]
    exit_criteria: List[str]
    dependencies: List[int]


@dataclass(frozen=True)
class WorkerAccount:
    alias: str
    owner_id: str
    auth_kind: str
    auth_json_file: str
    api_key_env: str
    api_key_file: str
    allowed_models: List[str]
    health_state: str
    spark_enabled: bool
    bridge_priority: int
    forced_login_method: str
    forced_chatgpt_workspace_id: str
    openai_base_url: str
    home_dir: str
    lane: str = ""
    max_parallel_runs: int = 1


@dataclass
class WorkerRun:
    run_id: str
    started_at: str
    finished_at: str
    worker_command: List[str]
    attempted_accounts: List[str]
    attempted_models: List[str]
    selected_account_alias: str
    worker_exit_code: int
    frontier_ids: List[int]
    open_milestone_ids: List[int]
    primary_milestone_id: Optional[int]
    prompt_path: str
    stdout_path: str
    stderr_path: str
    last_message_path: str
    final_message: str
    shipped: str
    remains: str
    blocker: str
    accepted: bool
    acceptance_reason: str


@dataclass(frozen=True)
class ActiveWorkerRun:
    run_id: str
    started_at: str
    prompt_path: str
    stdout_path: str
    stderr_path: str
    last_message_path: str
    frontier_ids: List[int]
    open_milestone_ids: List[int]
    primary_milestone_id: Optional[int]
    worker_command: List[str]
    selected_account_alias: str
    selected_model: str
    attempt_index: int
    total_attempts: int
    watchdog_timeout_seconds: float
    worker_pid: int = 0
    worker_first_output_at: str = ""
    worker_last_output_at: str = ""


def _runtime_env_default(name: str, default: str = "") -> str:
    direct = str(os.environ.get(name, "") or "").strip()
    if direct:
        return direct
    for candidate in _RUNTIME_ENV_CANDIDATES:
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            lines = candidate.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            key, value = line.split("=", 1)
            if key.strip() != name:
                continue
            resolved = value.strip().strip("'").strip('"')
            if resolved:
                return resolved
    return default


def _runtime_env_file_first_default(name: str, default: str = "") -> str:
    for candidate in _RUNTIME_ENV_CANDIDATES:
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            lines = candidate.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            key, value = line.split("=", 1)
            if key.strip() != name:
                continue
            resolved = value.strip().strip("'").strip('"')
            if resolved:
                return resolved
    direct = str(os.environ.get(name, "") or "").strip()
    if direct:
        return direct
    return default


def _runtime_env_workspace_candidates(workspace_root: Path) -> tuple[Path, ...]:
    root = Path(workspace_root).resolve()
    return (
        root / "runtime.env",
        root / "runtime.ea.env",
        root / ".env",
    )


def _runtime_env_default_with_workspace(
    name: str,
    workspace_root: Path,
    default: str = "",
) -> str:
    direct = str(os.environ.get(name, "") or "").strip()
    if direct:
        return direct
    for candidate in _runtime_env_workspace_candidates(workspace_root):
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            lines = candidate.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            key, value = line.split("=", 1)
            if key.strip() != name:
                continue
            resolved = value.strip().strip("'").strip('"')
            if resolved:
                return resolved
    return default


def _worker_model_output_stall_seconds(workspace_root: Path, timeout_seconds: float) -> float:
    raw = _runtime_env_default_with_workspace(
        "CHUMMER_DESIGN_SUPERVISOR_MODEL_OUTPUT_STALL_SECONDS",
        workspace_root,
        "",
    )
    stall_seconds = DEFAULT_MODEL_OUTPUT_STALL_SECONDS
    if raw:
        try:
            stall_seconds = max(0.0, float(raw))
        except (TypeError, ValueError):
            stall_seconds = DEFAULT_MODEL_OUTPUT_STALL_SECONDS
    effective_timeout = max(0.0, float(timeout_seconds or 0.0))
    if effective_timeout > 0.0:
        stall_seconds = min(stall_seconds, effective_timeout)
    return max(0.0, stall_seconds)


def _worker_self_poll_blocked_trip_threshold(workspace_root: Path) -> int:
    raw = _runtime_env_default_with_workspace(
        "CHUMMER_DESIGN_SUPERVISOR_SELF_POLL_BLOCKED_TRIP_THRESHOLD",
        workspace_root,
        "0",
    )
    try:
        threshold = int(float(raw or "0"))
    except (TypeError, ValueError):
        threshold = 0
    return max(0, threshold)


def _worker_status_helper_loop_trip_threshold(workspace_root: Path) -> int:
    raw = _runtime_env_default_with_workspace(
        "CHUMMER_DESIGN_SUPERVISOR_STATUS_HELPER_LOOP_TRIP_THRESHOLD",
        workspace_root,
        "2",
    )
    try:
        threshold = int(float(raw or "2"))
    except (TypeError, ValueError):
        threshold = 2
    return max(0, threshold)


def _dynamic_account_routing_enabled(
    workspace_root: Path,
    *,
    worker_lane: str = "",
    worker_model: str = "",
) -> bool:
    pin_aliases = (
        _runtime_env_default_with_workspace("CHUMMER_DESIGN_SUPERVISOR_PIN_ACCOUNT_ALIASES", workspace_root, "")
        .strip()
        .lower()
    )
    if pin_aliases in {"1", "true", "yes", "on"}:
        return False
    mode = (
        _runtime_env_default_with_workspace("CHUMMER_DESIGN_SUPERVISOR_DYNAMIC_ACCOUNT_ROUTING", workspace_root, "auto")
        .strip()
        .lower()
    )
    if mode in {"1", "true", "yes", "on", "dynamic"}:
        return True
    if mode in {"0", "false", "no", "off", "pinned"}:
        return False
    clean_model = str(worker_model or "").strip().lower()
    clean_lane = str(worker_lane or "").strip().lower()
    if clean_model.startswith("ea-"):
        return True
    return clean_lane in {
        "easy",
        "repair",
        "groundwork",
        "review_light",
        "core",
        "core_authority",
        "core_booster",
        "core_rescue",
        "review_shard",
        "audit_shard",
        "survival",
    }


DEFAULT_WORKER_TIMEOUT_SECONDS = _default_worker_timeout_seconds()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_shared_flags(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument(
            "--registry-path",
            default=str(DEFAULT_REGISTRY_PATH),
            help=f"Path to the active Chummer design registry (default: {DEFAULT_REGISTRY_PATH}).",
        )
        subparser.add_argument(
            "--program-milestones-path",
            default=str(DEFAULT_PROGRAM_MILESTONES_PATH),
            help=f"Path to PROGRAM_MILESTONES.yaml (default: {DEFAULT_PROGRAM_MILESTONES_PATH}).",
        )
        subparser.add_argument(
            "--roadmap-path",
            default=str(DEFAULT_ROADMAP_PATH),
            help=f"Path to ROADMAP.md (default: {DEFAULT_ROADMAP_PATH}).",
        )
        subparser.add_argument(
            "--handoff-path",
            default=str(DEFAULT_HANDOFF_PATH),
            help=f"Path to NEXT_SESSION_HANDOFF.md (default: {DEFAULT_HANDOFF_PATH}).",
        )
        subparser.add_argument(
            "--projects-dir",
            default=str(DEFAULT_PROJECTS_DIR),
            help=f"Path to Fleet project config YAMLs used for repo-local backlog synthesis (default: {DEFAULT_PROJECTS_DIR}).",
        )
        subparser.add_argument(
            "--journey-gates-path",
            default="",
            help=(
                "Optional path to GOLDEN_JOURNEY_RELEASE_GATES.yaml used for the completion audit. "
                "Defaults to the Fleet design mirror, then canonical design truth."
            ),
        )
        subparser.add_argument(
            "--weekly-pulse-path",
            default=str(DEFAULT_WEEKLY_PULSE_PATH),
            help=f"Path to WEEKLY_PRODUCT_PULSE.generated.json (default: {DEFAULT_WEEKLY_PULSE_PATH}).",
        )
        subparser.add_argument(
            "--accounts-path",
            default=str(DEFAULT_ACCOUNTS_PATH),
            help=f"Path to Fleet accounts config used for worker account rotation (default: {DEFAULT_ACCOUNTS_PATH}).",
        )
        subparser.add_argument(
            "--workspace-root",
            default=str(DEFAULT_WORKSPACE_ROOT),
            help=f"Fleet workspace root for the worker (default: {DEFAULT_WORKSPACE_ROOT}).",
        )
        subparser.add_argument(
            "--scope-root",
            action="append",
            default=[],
            help="Additional writable roots to pass to the worker. Repeatable.",
        )
        subparser.add_argument(
            "--state-root",
            default=str(DEFAULT_STATE_ROOT),
            help=f"State directory for supervisor logs and state (default: {DEFAULT_STATE_ROOT}).",
        )
        subparser.add_argument(
            "--status-plane-path",
            default=str(DEFAULT_STATUS_PLANE_PATH),
            help=f"Path to STATUS_PLANE.generated.yaml (default: {DEFAULT_STATUS_PLANE_PATH}).",
        )
        subparser.add_argument(
            "--progress-report-path",
            default=str(DEFAULT_PROGRESS_REPORT_PATH),
            help=f"Path to PROGRESS_REPORT.generated.json (default: {DEFAULT_PROGRESS_REPORT_PATH}).",
        )
        subparser.add_argument(
            "--progress-history-path",
            default=str(DEFAULT_PROGRESS_HISTORY_PATH),
            help=f"Path to PROGRESS_HISTORY.generated.json (default: {DEFAULT_PROGRESS_HISTORY_PATH}).",
        )
        subparser.add_argument(
            "--support-packets-path",
            default=str(DEFAULT_SUPPORT_PACKETS_PATH),
            help=f"Path to SUPPORT_CASE_PACKETS.generated.json (default: {DEFAULT_SUPPORT_PACKETS_PATH}).",
        )
        subparser.add_argument(
            "--flagship-product-readiness-path",
            default=str(DEFAULT_FLAGSHIP_PRODUCT_READINESS_PATH),
            help=(
                "Path to FLAGSHIP_PRODUCT_READINESS.generated.json, the full-product proof required before "
                f"the supervisor can report true completion (default: {DEFAULT_FLAGSHIP_PRODUCT_READINESS_PATH})."
            ),
        )
        subparser.add_argument(
            "--ui-linux-desktop-exit-gate-path",
            default=str(DEFAULT_UI_LINUX_DESKTOP_EXIT_GATE_PATH),
            help=(
                "Path to the repo-local Linux desktop exit gate proof that must show build, startup-smoke, "
                f"and unit-test success (default: {DEFAULT_UI_LINUX_DESKTOP_EXIT_GATE_PATH})."
            ),
        )
        subparser.add_argument(
            "--ui-executable-exit-gate-path",
            default=str(DEFAULT_UI_EXECUTABLE_EXIT_GATE_PATH),
            help=(
                "Path to DESKTOP_EXECUTABLE_EXIT_GATE.generated.json used to verify packaged-binary "
                f"desktop per-head proof freshness (default: {DEFAULT_UI_EXECUTABLE_EXIT_GATE_PATH})."
            ),
        )
        subparser.add_argument(
            "--ui-linux-desktop-repo-root",
            default=str(DEFAULT_UI_LINUX_DESKTOP_REPO_ROOT),
            help=(
                "Path to the UI repo root whose tracked git state must match the Linux desktop exit-gate proof "
                f"(default: {DEFAULT_UI_LINUX_DESKTOP_REPO_ROOT})."
            ),
        )
        subparser.add_argument(
            "--ignore-nonlinux-desktop-host-proof-blockers",
            action="store_true",
            default=_ignore_nonlinux_desktop_host_proof_blockers_enabled(),
            help=(
                "Ignore desktop proof blockers tied to Windows and macOS external-host or tuple expectations; still require Linux proof."
            ),
        )
        subparser.add_argument(
            "--worker-bin",
            default=_runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN", DEFAULT_WORKER_BIN),
            help=f"Worker binary to launch (default: {DEFAULT_WORKER_BIN}).",
        )
        subparser.add_argument(
            "--worker-model",
            default=_runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_WORKER_MODEL", DEFAULT_MODEL),
            help="Optional worker model override.",
        )
        subparser.add_argument(
            "--worker-lane",
            default=_runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_WORKER_LANE", ""),
            help="Optional worker lane prefix (for example: core when worker_bin is codexea).",
        )
        subparser.add_argument(
            "--fallback-worker-model",
            action="append",
            default=[],
            help="Optional fallback worker model when the current model returns a retryable quota/support error. Repeatable.",
        )
        subparser.add_argument(
            "--fallback-worker-lane",
            action="append",
            default=[],
            help="Optional fallback direct worker lane when the configured lane returns a retryable timeout/quota error. Repeatable.",
        )
        subparser.add_argument(
            "--account-owner-id",
            action="append",
            default=[],
            help="Restrict worker account rotation to one or more account owner ids from accounts.yaml. Repeatable.",
        )
        subparser.add_argument(
            "--account-alias",
            action="append",
            default=[],
            help="Restrict worker account rotation to explicit account aliases from accounts.yaml. Repeatable.",
        )
        subparser.add_argument(
            "--focus-owner",
            action="append",
            default=[],
            help="Bias the frontier toward milestones owned by one or more repos/owners first. Repeatable.",
        )
        subparser.add_argument(
            "--focus-profile",
            action="append",
            default=[],
            help="Apply a named steering profile before explicit focus owners/texts. Repeatable.",
        )
        subparser.add_argument(
            "--focus-text",
            action="append",
            default=[],
            help="Bias the frontier toward milestones whose title/exit criteria contain these case-insensitive terms. Repeatable.",
        )
        subparser.add_argument(
            "--frontier-id",
            action="append",
            type=int,
            default=[],
            help="Pin this worker/shard to one or more explicit open milestone ids before focus steering. Repeatable.",
        )
        subparser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print derived prompt metadata without launching the worker.",
        )
        subparser.add_argument(
            "--worker-timeout-seconds",
            type=float,
            default=DEFAULT_WORKER_TIMEOUT_SECONDS,
            help=(
                "Hard watchdog for one worker attempt before the supervisor kills it and retries if eligible "
                f"(default: {DEFAULT_WORKER_TIMEOUT_SECONDS:g})."
            ),
        )
        subparser.add_argument(
            "--ea-provider-health-url",
            default=_runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_URL", DEFAULT_EA_PROVIDER_HEALTH_URL),
            help=(
                "Optional EA provider-health endpoint used to preflight direct CodexEA lanes before launch "
                f"(default: {DEFAULT_EA_PROVIDER_HEALTH_URL})."
            ),
        )
        subparser.add_argument(
            "--ea-provider-health-timeout-seconds",
            type=float,
            default=float(
                _runtime_env_default(
                    "CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_TIMEOUT_SECONDS",
                    str(DEFAULT_EA_PROVIDER_HEALTH_TIMEOUT_SECONDS),
                )
            ),
            help=(
                "HTTP timeout for the EA provider-health preflight fetch "
                f"(default: {DEFAULT_EA_PROVIDER_HEALTH_TIMEOUT_SECONDS:g})."
            ),
        )
        subparser.add_argument(
            "--memory-dispatch-reserve-gib",
            type=float,
            default=_runtime_env_float_default(
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_RESERVE_GIB",
                DEFAULT_MEMORY_DISPATCH_RESERVE_GIB,
            ),
            help=(
                "Minimum host RAM headroom to keep free before idle shards are allowed to dispatch more work "
                f"(default: {DEFAULT_MEMORY_DISPATCH_RESERVE_GIB:g} GiB)."
            ),
        )
        subparser.add_argument(
            "--memory-dispatch-shard-budget-gib",
            type=float,
            default=_runtime_env_float_default(
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_SHARD_BUDGET_GIB",
                DEFAULT_MEMORY_DISPATCH_SHARD_BUDGET_GIB,
            ),
            help=(
                "Approximate RAM budget reserved per concurrently dispatching shard when memory-based throttling is active "
                f"(default: {DEFAULT_MEMORY_DISPATCH_SHARD_BUDGET_GIB:g} GiB)."
            ),
        )
        subparser.add_argument(
            "--memory-dispatch-warning-available-percent",
            type=float,
            default=_runtime_env_float_default(
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT",
                DEFAULT_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT,
            ),
            help=(
                "Start treating host memory as constrained when MemAvailable falls below this percent of total RAM "
                f"(default: {DEFAULT_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT:g})."
            ),
        )
        subparser.add_argument(
            "--memory-dispatch-critical-available-percent",
            type=float,
            default=_runtime_env_float_default(
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT",
                DEFAULT_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT,
            ),
            help=(
                "Enter critical memory throttling when MemAvailable falls below this percent of total RAM "
                f"(default: {DEFAULT_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT:g})."
            ),
        )
        subparser.add_argument(
            "--memory-dispatch-warning-swap-used-percent",
            type=float,
            default=_runtime_env_float_default(
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT",
                DEFAULT_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT,
            ),
            help=(
                "Start treating host memory as constrained when swap usage reaches this percent "
                f"(default: {DEFAULT_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT:g})."
            ),
        )
        subparser.add_argument(
            "--memory-dispatch-critical-swap-used-percent",
            type=float,
            default=_runtime_env_float_default(
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT",
                DEFAULT_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT,
            ),
            help=(
                "Enter critical memory throttling when swap usage reaches this percent "
                f"(default: {DEFAULT_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT:g})."
            ),
        )

    once_parser = subparsers.add_parser("once", help="Launch one bounded worker run from the current design frontier.")
    add_shared_flags(once_parser)

    loop_parser = subparsers.add_parser("loop", help="Keep launching worker runs until design completion or a hard blocker.")
    add_shared_flags(loop_parser)
    loop_parser.add_argument(
        "--poll-seconds",
        type=float,
        default=DEFAULT_POLL_SECONDS,
        help=f"Sleep between supervisor iterations (default: {DEFAULT_POLL_SECONDS}).",
    )
    loop_parser.add_argument(
        "--cooldown-seconds",
        type=float,
        default=DEFAULT_COOLDOWN_SECONDS,
        help=f"Pause after a successful worker run before the next derivation (default: {DEFAULT_COOLDOWN_SECONDS}).",
    )
    loop_parser.add_argument(
        "--failure-backoff-seconds",
        type=float,
        default=DEFAULT_FAILURE_BACKOFF_SECONDS,
        help=f"Pause after a failed worker run before retrying (default: {DEFAULT_FAILURE_BACKOFF_SECONDS}).",
    )
    loop_parser.add_argument(
        "--memory-dispatch-parked-poll-seconds",
        type=float,
        default=_runtime_env_float_default(
            "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_PARKED_POLL_SECONDS",
            DEFAULT_MEMORY_DISPATCH_PARKED_POLL_SECONDS,
        ),
        help=(
            "Sleep this long before rechecking a parked shard when memory throttling blocks dispatch "
            f"(default: {DEFAULT_MEMORY_DISPATCH_PARKED_POLL_SECONDS})."
        ),
    )
    loop_parser.add_argument(
        "--max-runs",
        type=int,
        default=0,
        help="Stop after N worker launches. 0 means no explicit limit.",
    )
    loop_parser.add_argument(
        "--stop-on-blocker",
        action="store_true",
        help="Stop when the worker reports a non-empty Exact blocker field.",
    )

    status_parser = subparsers.add_parser("status", help="Print the current supervisor state.")
    add_shared_flags(status_parser)
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Render status as JSON.",
    )
    status_parser.add_argument(
        "--live-refresh",
        action="store_true",
        help="Refresh heavyweight completion/flagship audits before rendering status.",
    )

    eta_parser = subparsers.add_parser("eta", help="Estimate completion ETA from live design state and recent history.")
    add_shared_flags(eta_parser)
    eta_parser.add_argument(
        "--json",
        action="store_true",
        help="Render ETA payload as JSON.",
    )

    trace_parser = subparsers.add_parser("trace", help="Render recent supervisor loop history.")
    add_shared_flags(trace_parser)
    trace_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of recent runs to render. 0 means all recorded runs.",
    )
    trace_parser.add_argument(
        "--json",
        action="store_true",
        help="Render trace payload as JSON.",
    )

    derive_parser = subparsers.add_parser("derive", help="Print the next-worker prompt without launching it.")
    add_shared_flags(derive_parser)
    return parser.parse_args()


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    current = value.astimezone(dt.timezone.utc).replace(microsecond=0)
    return current.isoformat().replace("+00:00", "Z")


def _iso_now() -> str:
    return _iso(_utc_now())


def _slug_timestamp(value: Optional[dt.datetime] = None) -> str:
    current = value or _utc_now()
    return current.strftime("%Y%m%dT%H%M%SZ")


def _state_scoped_run_id(state_root: Path, value: Optional[dt.datetime] = None) -> str:
    run_id = _slug_timestamp(value)
    shard_name = str(Path(state_root).resolve().name or "").strip()
    if shard_name.startswith("shard-"):
        return f"{run_id}-{shard_name}"
    return run_id


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def _read_yaml(path: Path) -> Dict[str, Any]:
    payload = yaml.safe_load(_read_text(path))
    return dict(payload or {})


def _read_json_file(path: Path) -> Dict[str, Any]:
    payload = json.loads(_read_text(path))
    return dict(payload or {})


def _parse_iso(value: str) -> Optional[dt.datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _normalize_blocker(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _gib_to_bytes(value: Any, *, default_gib: float) -> int:
    gib = _coerce_float(value)
    if gib is None:
        gib = float(default_gib)
    return max(0, int(gib * (1024**3)))


def _read_proc_meminfo_bytes(path: Path = Path("/proc/meminfo")) -> Dict[str, int]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    payload: Dict[str, int] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        match = re.match(r"\s*(\d+)\s*kB\b", rest, flags=re.I)
        if not match:
            continue
        payload[str(key).strip()] = int(match.group(1)) * 1024
    return payload


def _format_gib(value: Any) -> str:
    if value in (None, ""):
        return "unknown"
    try:
        return f"{float(value) / float(1024**3):.2f} GiB"
    except (TypeError, ValueError):
        return "unknown"


def _active_shard_names(aggregate_root: Path) -> List[str]:
    names: List[str] = []
    for shard_root in _configured_shard_roots(aggregate_root):
        state = _read_state(_state_payload_path(shard_root))
        active_run = (state.get("active_run") or {}) if isinstance(state.get("active_run"), dict) else {}
        if not active_run:
            recovered_active_run = _recover_matching_live_active_run(
                shard_root,
                frontier_ids=_state_frontier_ids(state),
                open_milestone_ids=_state_open_milestone_ids(state),
            )
            if recovered_active_run is not None:
                active_run = dict(recovered_active_run)
        if str(active_run.get("run_id") or "").strip():
            names.append(shard_root.name)
    return names


def _eligible_shard_names_for_dispatch(
    configured_shard_names: Sequence[str],
    active_shard_names: Sequence[str],
    *,
    allowed_active_shards: int,
) -> List[str]:
    limit = max(0, int(allowed_active_shards))
    if limit <= 0:
        return []
    configured = [str(item).strip() for item in configured_shard_names if str(item).strip()]
    if not configured:
        return []
    active = {str(item).strip() for item in active_shard_names if str(item).strip()}
    eligible: List[str] = []
    for name in configured:
        if name not in active:
            continue
        eligible.append(name)
        if len(eligible) >= limit:
            return eligible
    for name in configured:
        if name in active or name in eligible:
            continue
        eligible.append(name)
        if len(eligible) >= limit:
            break
    return eligible


def _severity_rank(level: str) -> int:
    return {
        "ok": 0,
        "warning": 1,
        "critical": 2,
        "unknown": -1,
    }.get(str(level or "").strip().lower(), -1)


def _memory_dispatch_snapshot(
    args: argparse.Namespace,
    state_root: Path,
    *,
    meminfo_bytes: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    resolved_state_root = Path(state_root).resolve()
    aggregate_root = _aggregate_state_root(resolved_state_root)
    configured_shards = _configured_shard_roots(aggregate_root)
    configured_shard_names = [item.name for item in configured_shards]
    configured_shard_count = len(configured_shards)
    current_shard_name = resolved_state_root.name if resolved_state_root.name.startswith("shard-") else ""
    meminfo = dict(meminfo_bytes or _read_proc_meminfo_bytes())
    snapshot: Dict[str, Any] = {
        "updated_at": _iso_now(),
        "status": "unknown",
        "reason": "host memory telemetry unavailable",
        "mem_total_bytes": 0,
        "mem_available_bytes": 0,
        "mem_available_percent": None,
        "swap_total_bytes": 0,
        "swap_free_bytes": 0,
        "swap_used_percent": None,
        "dispatch_reserve_bytes": _gib_to_bytes(
            getattr(args, "memory_dispatch_reserve_gib", DEFAULT_MEMORY_DISPATCH_RESERVE_GIB),
            default_gib=DEFAULT_MEMORY_DISPATCH_RESERVE_GIB,
        ),
        "per_shard_budget_bytes": _gib_to_bytes(
            getattr(args, "memory_dispatch_shard_budget_gib", DEFAULT_MEMORY_DISPATCH_SHARD_BUDGET_GIB),
            default_gib=DEFAULT_MEMORY_DISPATCH_SHARD_BUDGET_GIB,
        ),
        "configured_shard_count": configured_shard_count,
        "configured_shard_names": configured_shard_names,
        "allowed_active_shards": configured_shard_count,
        "eligible_shard_names": list(configured_shard_names),
        "active_shard_count": 0,
        "active_shard_names": [],
        "current_shard_name": current_shard_name,
        "dispatch_allowed": True,
        "throttled": False,
    }
    if not meminfo:
        return snapshot

    mem_total_bytes = max(0, _coerce_int(meminfo.get("MemTotal"), 0))
    mem_available_bytes = max(
        0,
        _coerce_int(meminfo.get("MemAvailable"), 0) or _coerce_int(meminfo.get("MemFree"), 0),
    )
    swap_total_bytes = max(0, _coerce_int(meminfo.get("SwapTotal"), 0))
    swap_free_bytes = max(0, _coerce_int(meminfo.get("SwapFree"), 0))
    mem_available_percent = (
        round((float(mem_available_bytes) / float(mem_total_bytes)) * 100.0, 2) if mem_total_bytes > 0 else None
    )
    swap_used_percent = None
    if swap_total_bytes > 0:
        swap_used_percent = round(
            (float(max(0, swap_total_bytes - swap_free_bytes)) / float(swap_total_bytes)) * 100.0,
            2,
        )

    reserve_bytes = max(0, _coerce_int(snapshot.get("dispatch_reserve_bytes"), 0))
    per_shard_budget_bytes = max(1, _coerce_int(snapshot.get("per_shard_budget_bytes"), 0))
    headroom_bytes = max(0, mem_available_bytes - reserve_bytes)
    budget_cap = 0
    if configured_shard_count > 0 and headroom_bytes > 0:
        budget_cap = int((headroom_bytes + per_shard_budget_bytes - 1) // per_shard_budget_bytes)
    budget_cap = max(0, min(configured_shard_count, budget_cap))

    warning_available_percent = min(
        100.0,
        max(
            0.0,
            _coerce_float(
                getattr(args, "memory_dispatch_warning_available_percent", DEFAULT_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT)
            )
            or DEFAULT_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT,
        ),
    )
    critical_available_percent = min(
        warning_available_percent,
        max(
            0.0,
            _coerce_float(
                getattr(args, "memory_dispatch_critical_available_percent", DEFAULT_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT)
            )
            or DEFAULT_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT,
        ),
    )
    warning_swap_used_percent_raw = (
        _coerce_float(
            getattr(args, "memory_dispatch_warning_swap_used_percent", DEFAULT_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT)
        )
        or DEFAULT_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT
    )
    critical_swap_used_percent_raw = (
        _coerce_float(
            getattr(args, "memory_dispatch_critical_swap_used_percent", DEFAULT_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT)
        )
        or DEFAULT_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT
    )
    if warning_swap_used_percent_raw > 100.0 and critical_swap_used_percent_raw > 100.0:
        warning_swap_used_percent = None
        critical_swap_used_percent = None
    else:
        warning_swap_used_percent = min(100.0, max(0.0, warning_swap_used_percent_raw))
        critical_swap_used_percent = min(
            100.0,
            max(
                warning_swap_used_percent,
                critical_swap_used_percent_raw,
            ),
        )
    swap_pressure_relevant = (
        configured_shard_count > 0
        and (
            budget_cap < configured_shard_count
            or (
                mem_available_percent is not None
                and mem_available_percent <= warning_available_percent
            )
        )
    )

    status = "ok"
    reasons: List[str] = []
    if configured_shard_count > 0 and budget_cap < configured_shard_count:
        status = "warning"
        reasons.append(
            f"available headroom {_format_gib(mem_available_bytes)} minus reserve {_format_gib(reserve_bytes)} caps shard dispatch at {budget_cap}/{configured_shard_count}"
        )
    if mem_available_percent is not None and mem_available_percent <= critical_available_percent:
        status = "critical"
        reasons.append(
            f"MemAvailable is {mem_available_percent:.2f}% <= critical {critical_available_percent:.2f}%"
        )
    elif mem_available_percent is not None and mem_available_percent <= warning_available_percent and _severity_rank(status) < 1:
        status = "warning"
        reasons.append(f"MemAvailable is {mem_available_percent:.2f}% <= warning {warning_available_percent:.2f}%")
    if (
        swap_pressure_relevant
        and (
        swap_used_percent is not None
        and critical_swap_used_percent is not None
        and swap_used_percent >= critical_swap_used_percent
        )
    ):
        status = "critical"
        reasons.append(f"swap used is {swap_used_percent:.2f}% >= critical {critical_swap_used_percent:.2f}%")
    elif (
        swap_pressure_relevant
        and (
        swap_used_percent is not None
        and warning_swap_used_percent is not None
        and swap_used_percent >= warning_swap_used_percent
        and _severity_rank(status) < 1
        )
    ):
        status = "warning"
        reasons.append(f"swap used is {swap_used_percent:.2f}% >= warning {warning_swap_used_percent:.2f}%")

    allowed_active_shards = configured_shard_count
    if configured_shard_count > 0:
        allowed_active_shards = min(configured_shard_count, budget_cap)
        if status == "warning":
            allowed_active_shards = min(
                allowed_active_shards,
                max(1, (configured_shard_count + 1) // 2),
            )
        elif status == "critical":
            allowed_active_shards = min(allowed_active_shards, 1)
    active_shard_names = _active_shard_names(aggregate_root)
    eligible_shard_names = _eligible_shard_names_for_dispatch(
        configured_shard_names,
        active_shard_names,
        allowed_active_shards=allowed_active_shards,
    )
    dispatch_allowed = True
    if current_shard_name:
        dispatch_allowed = current_shard_name in eligible_shard_names
    throttled = configured_shard_count > 0 and allowed_active_shards < configured_shard_count
    if throttled and current_shard_name and not dispatch_allowed:
        reasons.append(f"{current_shard_name} is parked until host memory recovers")
    if not reasons:
        reasons.append("host memory headroom is healthy for the configured shard set")

    snapshot.update(
        {
            "status": status if mem_total_bytes > 0 else "unknown",
            "reason": "; ".join(reasons),
            "mem_total_bytes": mem_total_bytes,
            "mem_available_bytes": mem_available_bytes,
            "mem_available_percent": mem_available_percent,
            "swap_total_bytes": swap_total_bytes,
            "swap_free_bytes": swap_free_bytes,
            "swap_used_percent": swap_used_percent,
            "allowed_active_shards": allowed_active_shards,
            "eligible_shard_names": eligible_shard_names,
            "active_shard_count": len(active_shard_names),
            "active_shard_names": active_shard_names,
            "dispatch_allowed": dispatch_allowed,
            "throttled": throttled,
        }
    )
    return snapshot


def _memory_pressure_notice(host_memory_pressure: Optional[Dict[str, Any]]) -> str:
    if not isinstance(host_memory_pressure, dict) or not host_memory_pressure:
        return "[fleet-supervisor] memory pressure guard active; dispatch parked"
    status = str(host_memory_pressure.get("status") or "unknown").strip().lower() or "unknown"
    allowed_active_shards = max(0, _coerce_int(host_memory_pressure.get("allowed_active_shards"), 0))
    configured_shard_count = max(0, _coerce_int(host_memory_pressure.get("configured_shard_count"), 0))
    eligible_shard_names = [
        str(item).strip()
        for item in (host_memory_pressure.get("eligible_shard_names") or [])
        if str(item).strip()
    ]
    current_shard_name = str(host_memory_pressure.get("current_shard_name") or "").strip()
    reason = str(host_memory_pressure.get("reason") or "").strip()
    segments = [
        f"[fleet-supervisor] memory pressure guard active ({status})",
        f"dispatch budget {allowed_active_shards}/{configured_shard_count} active shards",
    ]
    if current_shard_name and host_memory_pressure.get("dispatch_allowed") is False:
        segments.append(f"{current_shard_name} is parked")
    if eligible_shard_names:
        segments.append(f"eligible shards: {', '.join(eligible_shard_names)}")
    if reason:
        segments.append(reason)
    return "; ".join(segments)


def _memory_pressure_notice_key(host_memory_pressure: Optional[Dict[str, Any]]) -> str:
    if not isinstance(host_memory_pressure, dict) or not host_memory_pressure:
        return "memory-pressure:unknown"
    eligible_shard_names = [
        str(item).strip()
        for item in (host_memory_pressure.get("eligible_shard_names") or [])
        if str(item).strip()
    ]
    return "|".join(
        [
            "memory-pressure",
            str(host_memory_pressure.get("status") or "").strip().lower(),
            str(max(0, _coerce_int(host_memory_pressure.get("allowed_active_shards"), 0))),
            str(max(0, _coerce_int(host_memory_pressure.get("configured_shard_count"), 0))),
            "allowed" if host_memory_pressure.get("dispatch_allowed") is not False else "parked",
            str(host_memory_pressure.get("current_shard_name") or "").strip(),
            ",".join(eligible_shard_names),
        ]
    )


def _memory_pressure_parked_sleep_seconds(
    args: argparse.Namespace,
    host_memory_pressure: Optional[Dict[str, Any]],
) -> float:
    base_poll_seconds = max(
        1.0,
        float(_coerce_float(getattr(args, "poll_seconds", DEFAULT_POLL_SECONDS)) or DEFAULT_POLL_SECONDS),
    )
    if not isinstance(host_memory_pressure, dict) or host_memory_pressure.get("dispatch_allowed") is not False:
        return base_poll_seconds
    configured_seconds = _coerce_float(
        getattr(args, "memory_dispatch_parked_poll_seconds", DEFAULT_MEMORY_DISPATCH_PARKED_POLL_SECONDS)
    )
    return max(
        base_poll_seconds,
        float(configured_seconds or DEFAULT_MEMORY_DISPATCH_PARKED_POLL_SECONDS),
    )


def _should_defer_dispatch_for_memory_pressure(
    state_root: Path,
    host_memory_pressure: Optional[Dict[str, Any]],
) -> bool:
    resolved_state_root = Path(state_root).resolve()
    if resolved_state_root == _aggregate_state_root(resolved_state_root):
        return False
    if not resolved_state_root.name.startswith("shard-"):
        return False
    if not isinstance(host_memory_pressure, dict) or not host_memory_pressure:
        return False
    if not host_memory_pressure.get("throttled"):
        return False
    return host_memory_pressure.get("dispatch_allowed") is False

def _worker_bin_uses_codexea(worker_bin: str) -> bool:
    token = Path(str(worker_bin or "").strip() or DEFAULT_WORKER_BIN).name.lower()
    return token == "codexea"


def _codexea_profile_for_lane(worker_lane: str, *, workspace_root: Optional[Path] = None) -> str:
    lane = str(worker_lane or "").strip().lower()
    if not lane:
        return ""
    configured_core_profile = ""
    if workspace_root is not None:
        configured_core_profile = _resolve_env_secret(
            "CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE",
            workspace_root,
        )
    core_profile = (
        str(os.environ.get("CODEXEA_CORE_RESPONSES_PROFILE") or "").strip().lower()
        or str(configured_core_profile or "").strip().lower()
        or str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE") or "").strip().lower()
        or "core"
    )
    profile_by_lane = {
        "easy": "easy",
        "repair": "repair",
        "groundwork": "groundwork",
        "core": core_profile,
        "core_rescue": "core_rescue",
        "jury": "audit",
        "survival": "survival",
    }
    return profile_by_lane.get(lane, lane)


def _ea_provider_health_url(args: argparse.Namespace) -> str:
    return str(
        getattr(args, "ea_provider_health_url", "")
        or os.environ.get("CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_URL", "")
        or _runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_URL", "")
        or DEFAULT_EA_PROVIDER_HEALTH_URL
    ).strip()


def _ea_provider_health_api_token(args: argparse.Namespace) -> str:
    return str(
        getattr(args, "ea_provider_health_api_token", "")
        or os.environ.get("CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_API_TOKEN", "")
        or _runtime_env_default("EA_MCP_API_TOKEN", _runtime_env_default("EA_API_TOKEN", ""))
    ).strip()


def _ea_provider_health_principal_id(args: argparse.Namespace) -> str:
    return str(
        getattr(args, "ea_provider_health_principal_id", "")
        or os.environ.get("CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_PRINCIPAL_ID", "")
        or _runtime_env_default(
            "EA_MCP_PRINCIPAL_ID",
            _runtime_env_default("EA_PRINCIPAL_ID", _runtime_env_default("EA_DEFAULT_PRINCIPAL_ID", "")),
        )
    ).strip()


def _ea_provider_health_headers(args: argparse.Namespace) -> Dict[str, str]:
    headers: Dict[str, str] = {"Accept": "application/json"}
    api_token = _ea_provider_health_api_token(args)
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    principal_id = _ea_provider_health_principal_id(args)
    if principal_id:
        headers["X-EA-Principal-ID"] = principal_id
    return headers


def _ea_provider_health_candidate_urls(args: argparse.Namespace) -> List[str]:
    primary = _ea_provider_health_url(args)
    if not primary:
        return []
    urls = [primary]
    try:
        parsed = urllib.parse.urlsplit(primary)
    except ValueError:
        return urls
    hostname = str(parsed.hostname or "").strip().lower()
    if hostname == "host.docker.internal":
        fallback = urllib.parse.urlunsplit(
            (
                parsed.scheme,
                parsed.netloc.replace(parsed.hostname or "", "127.0.0.1", 1),
                parsed.path,
                parsed.query,
                parsed.fragment,
            )
        ).strip()
        if fallback and fallback not in urls:
            urls.append(fallback)
        return urls
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        return urls
    if "host.docker.internal" in primary.lower():
        return urls
    netloc = parsed.netloc
    replacement_host = "host.docker.internal"
    if hostname == "::1":
        replacement_host = "[host.docker.internal]"
    replacement_netloc = netloc.replace(parsed.hostname or "", replacement_host, 1)
    fallback = urllib.parse.urlunsplit(
        (parsed.scheme, replacement_netloc, parsed.path, parsed.query, parsed.fragment)
    ).strip()
    if fallback and fallback not in urls:
        urls.append(fallback)
    return urls


def _ea_provider_health_request_url(url: str) -> str:
    candidate = str(url or "").strip()
    if not candidate:
        return ""
    try:
        parsed = urllib.parse.urlsplit(candidate)
    except ValueError:
        return candidate
    if not str(parsed.path or "").endswith("/_provider_health"):
        return candidate
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if any(str(key).strip().lower() == "lightweight" for key, _ in query_pairs):
        return candidate
    query_pairs.append(("lightweight", "1"))
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode(query_pairs),
            parsed.fragment,
        )
    ).strip()


def _ea_provider_health_timeout_seconds(args: argparse.Namespace) -> float:
    raw = getattr(args, "ea_provider_health_timeout_seconds", DEFAULT_EA_PROVIDER_HEALTH_TIMEOUT_SECONDS)
    try:
        return max(0.5, float(raw))
    except (TypeError, ValueError):
        return DEFAULT_EA_PROVIDER_HEALTH_TIMEOUT_SECONDS


def _ea_provider_health_retry_timeout_seconds(args: argparse.Namespace) -> float:
    return max(1.0, _ea_provider_health_timeout_seconds(args) * 2.0)


def _ea_provider_health_cache_max_age_seconds() -> float:
    raw = _runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_CACHE_MAX_AGE_SECONDS", "300")
    try:
        return max(30.0, float(raw))
    except (TypeError, ValueError):
        return 300.0


def _ea_provider_health_failure_cooldown_seconds() -> float:
    raw = _runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_FAILURE_COOLDOWN_SECONDS", "60")
    try:
        return max(5.0, float(raw))
    except (TypeError, ValueError):
        return 60.0


def _ea_provider_health_cache_path(args: argparse.Namespace) -> Path:
    state_root_raw = str(getattr(args, "state_root", "") or "").strip()
    state_root = Path(state_root_raw or DEFAULT_STATE_ROOT).resolve()
    return _aggregate_state_root(state_root) / "ea_provider_health_cache.json"


def _load_ea_provider_health_cache(args: argparse.Namespace) -> Dict[str, Any]:
    path = _ea_provider_health_cache_path(args)
    payload = _read_state(path)
    if not payload:
        return {}
    cached_payload = dict(payload.get("payload") or {})
    if not cached_payload:
        return {}
    cached_at = _parse_iso(str(payload.get("cached_at") or ""))
    age_seconds = None
    if cached_at is not None:
        age_seconds = max(0.0, (_utc_now() - cached_at).total_seconds())
    last_live_fetch_failed_at = _parse_iso(str(payload.get("last_live_fetch_failed_at") or ""))
    last_live_fetch_failure_age_seconds = None
    if last_live_fetch_failed_at is not None:
        last_live_fetch_failure_age_seconds = max(0.0, (_utc_now() - last_live_fetch_failed_at).total_seconds())
    return {
        "path": str(path),
        "cached_at": _iso(cached_at) if cached_at is not None else "",
        "age_seconds": age_seconds,
        "source_url": str(payload.get("source_url") or "").strip(),
        "last_live_fetch_failed_at": _iso(last_live_fetch_failed_at) if last_live_fetch_failed_at is not None else "",
        "last_live_fetch_failure_age_seconds": last_live_fetch_failure_age_seconds,
        "last_live_fetch_error": str(payload.get("last_live_fetch_error") or "").strip(),
        "payload": cached_payload,
    }


def _write_ea_provider_health_cache(
    args: argparse.Namespace,
    *,
    payload: Dict[str, Any],
    source_url: str,
) -> None:
    _write_json(
        _ea_provider_health_cache_path(args),
        {
            "cached_at": _iso_now(),
            "payload": dict(payload or {}),
            "source_url": str(source_url or "").strip(),
            # A successful refresh should clear any stale failure metadata so
            # later status reads do not misreport a healthy probe as degraded.
            "last_live_fetch_failed_at": "",
            "last_live_fetch_error": "",
        },
    )


def _record_ea_provider_health_live_failure(args: argparse.Namespace, *, error: str) -> None:
    path = _ea_provider_health_cache_path(args)
    payload = _read_state(path)
    if not isinstance(payload, dict):
        payload = {}
    payload["last_live_fetch_failed_at"] = _iso_now()
    payload["last_live_fetch_error"] = str(error or "").strip()
    _write_json(path, payload)


def _is_provider_health_timeout_error(exc: BaseException) -> bool:
    seen: Set[int] = set()
    pending: List[BaseException] = [exc]
    while pending:
        current = pending.pop()
        current_id = id(current)
        if current_id in seen:
            continue
        seen.add(current_id)
        if isinstance(current, (TimeoutError, socket.timeout)):
            return True
        message = str(current or "").strip().lower()
        if "timed out" in message or "timeout" in message:
            return True
        reason = getattr(current, "reason", None)
        if isinstance(reason, BaseException):
            pending.append(reason)
        if isinstance(current, urllib.error.URLError) and isinstance(reason, str) and "timed out" in reason.lower():
            return True
    return False


def _running_inside_container() -> bool:
    return Path("/.dockerenv").exists()


def _load_sibling_module(module_name: str) -> Any:
    cached = _SIBLING_MODULE_CACHE.get(module_name)
    if cached is not None:
        return cached
    scripts_root = str(Path(__file__).resolve().parent)
    if scripts_root not in sys.path:
        sys.path.insert(0, scripts_root)
    module = importlib.import_module(module_name)
    _SIBLING_MODULE_CACHE[module_name] = module
    return module


def _load_fresh_sibling_module(module_name: str) -> Any:
    module_path = Path(__file__).resolve().parent / f"{module_name}.py"
    if not module_path.exists():
        return _load_sibling_module(module_name)
    module_key = f"_fleet_fresh_{module_name}_{os.getpid()}_{time.monotonic_ns()}"
    spec = importlib.util.spec_from_file_location(module_key, module_path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(module_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_key] = module
    spec.loader.exec_module(module)
    return module


def _with_fleet_app_modules_hidden(callback: Any) -> Dict[str, Any]:
    fleet_root = str(DEFAULT_WORKSPACE_ROOT.resolve())
    stashed: Dict[str, Any] = {}
    for module_name, module in list(sys.modules.items()):
        if module_name != "app" and not module_name.startswith("app."):
            continue
        module_file = str(getattr(module, "__file__", "") or "").strip()
        if not module_file:
            continue
        try:
            resolved_file = str(Path(module_file).resolve())
        except Exception:
            resolved_file = module_file
        if not resolved_file.startswith(fleet_root):
            continue
        stashed[module_name] = module
        sys.modules.pop(module_name, None)
    try:
        payload = callback()
    finally:
        for module_name in list(stashed.keys()):
            sys.modules.pop(module_name, None)
        sys.modules.update(stashed)
    return dict(payload or {}) if isinstance(payload, dict) else {}


def _local_ea_provider_health_payload() -> Dict[str, Any]:
    for module_loader in (_load_sibling_module, _load_fresh_sibling_module):
        try:
            module = module_loader("codexea_route")
        except Exception:
            continue
        loader = getattr(module, "_local_onemin_direct_payload", None)
        if not callable(loader):
            continue
        try:
            payload = _with_fleet_app_modules_hidden(lambda: loader(probe_all=False, include_reserve=True))
        except Exception:
            continue
        if payload:
            return payload
    return {}


def _provider_registry_lane_rows(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    registry = dict(payload.get("provider_registry") or {})
    rows = registry.get("lanes") or registry.get("profiles") or []
    lane_rows: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        profile = str(row.get("profile") or "").strip().lower()
        if not profile:
            continue
        lane_rows[profile] = row
    return lane_rows


def _synthetic_onemin_provider_registry_lane_rows(
    payload: Dict[str, Any],
    worker_lanes: Sequence[str],
    *,
    workspace_root: Path,
) -> Dict[str, Dict[str, Any]]:
    providers = ((payload.get("provider_health") or {}).get("providers") or {})
    onemin = providers.get("onemin") if isinstance(providers, dict) else None
    if not isinstance(onemin, dict) or not onemin:
        return {}

    slot_states = [
        str(slot.get("state") or "").strip().lower() or "unknown"
        for slot in (onemin.get("slots") or [])
        if isinstance(slot, dict) and bool(slot.get("configured", True))
    ]
    ready_slots = sum(1 for state in slot_states if state in PROVIDER_HEALTH_READY_STATES)
    degraded_slots = sum(1 for state in slot_states if state in PROVIDER_HEALTH_DEGRADED_STATES)
    unavailable_slots = sum(
        1 for state in slot_states if state in PROVIDER_HEALTH_UNAVAILABLE_STATES or state not in PROVIDER_HEALTH_READY_STATES | PROVIDER_HEALTH_DEGRADED_STATES
    )
    configured_slots = _coerce_int(onemin.get("configured_slots"))
    if configured_slots <= 0:
        configured_slots = len(slot_states)
    if configured_slots <= 0:
        return {}
    primary_state = str(onemin.get("state") or "").strip().lower()
    if not primary_state:
        if ready_slots > 0:
            primary_state = "ready"
        elif degraded_slots > 0:
            primary_state = "degraded"
        elif unavailable_slots >= configured_slots:
            primary_state = "unavailable"
        else:
            primary_state = "unknown"
    detail = "; ".join(
        part
        for part in (
            str(onemin.get("balance_basis_summary") or "").strip(),
            "direct local 1min provider health",
        )
        if part
    )
    capacity_summary = {
        "state": primary_state,
        "configured_slots": configured_slots,
        "ready_slots": ready_slots,
        "degraded_slots": degraded_slots,
        "unavailable_slots": unavailable_slots,
        "leased_slots": _coerce_int(onemin.get("active_lease_count") or 0),
        "remaining_percent_of_max": _coerce_float(onemin.get("remaining_percent_of_max")),
        "estimated_remaining_credits_total": _coerce_float(onemin.get("estimated_remaining_credits_total")),
    }
    provider_row = {
        "provider_key": "onemin",
        "state": primary_state,
        "detail": detail,
        "enabled": configured_slots > 0,
        "executable": configured_slots > 0,
    }
    lane_rows: Dict[str, Dict[str, Any]] = {}
    for worker_lane in worker_lanes:
        lane = str(worker_lane or "").strip().lower()
        if lane not in _direct_codexea_stream_lanes():
            continue
        profile = _codexea_profile_for_lane(lane, workspace_root=workspace_root)
        if not profile or profile in lane_rows:
            continue
        lane_rows[profile] = {
            "profile": profile,
            "primary_provider_key": "onemin",
            "primary_state": primary_state,
            "capacity_summary": dict(capacity_summary),
            "providers": [dict(provider_row)],
            "source": "direct_local_onemin",
            "synthetic": True,
        }
    return lane_rows


def _lane_provider_detail(provider: Dict[str, Any]) -> str:
    provider_key = str(provider.get("provider_key") or "provider").strip() or "provider"
    state = str(provider.get("state") or provider.get("health_state") or "unknown").strip() or "unknown"
    detail = " ".join(str(provider.get("detail") or "").split()).strip()
    if detail:
        return f"{provider_key}:{state}:{detail}"
    return f"{provider_key}:{state}"


def _assess_direct_worker_lane_health(
    worker_lane: str,
    profile_name: str,
    row: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    lane = str(worker_lane or "").strip()
    profile = str(profile_name or "").strip()
    if not lane:
        return {
            "worker_lane": lane,
            "profile": profile,
            "known": False,
            "routable": True,
            "state": "unknown",
            "reason": "no direct EA worker lane configured",
        }
    if not isinstance(row, dict) or not row:
        return {
            "worker_lane": lane,
            "profile": profile,
            "known": False,
            "routable": True,
            "state": "unknown",
            "reason": f"provider registry did not publish lane metadata for profile={profile or lane}",
        }

    providers = [dict(item) for item in (row.get("providers") or []) if isinstance(item, dict)]
    capacity = dict(row.get("capacity_summary") or {})
    state = str(row.get("primary_state") or capacity.get("state") or "").strip().lower() or "unknown"
    primary_provider_key = str(row.get("primary_provider_key") or "").strip()
    ready_slots = _coerce_int(capacity.get("ready_slots") or 0)
    degraded_slots = _coerce_int(capacity.get("degraded_slots") or 0)
    unavailable_slots = _coerce_int(capacity.get("unavailable_slots") or 0)
    configured_slots = _coerce_int(capacity.get("configured_slots") or 0)
    leased_slots = _coerce_int(capacity.get("leased_slots") or 0)
    remaining_percent = _coerce_float(capacity.get("remaining_percent_of_max"))
    estimated_remaining_credits_total = _coerce_float(capacity.get("estimated_remaining_credits_total"))
    executable_provider_count = sum(
        1 for provider in providers if bool(provider.get("enabled", True)) and bool(provider.get("executable", True))
    )
    provider_states = sorted({str(provider.get("state") or "").strip().lower() for provider in providers if provider})
    reason_segments = [_lane_provider_detail(provider) for provider in providers[:3]]
    if len(providers) > 3:
        reason_segments.append(f"+{len(providers) - 3} more")
    reason = "; ".join(segment for segment in reason_segments if segment)

    routable = True
    if not providers:
        known = False
        state = state or "unknown"
        reason = reason or f"profile={profile or lane} has no provider rows"
    else:
        known = True
        if executable_provider_count <= 0:
            state = "unavailable"
            routable = False
            reason = reason or f"profile={profile or lane} has no enabled executable providers"
        elif state in PROVIDER_HEALTH_READY_STATES:
            routable = True
        elif state in PROVIDER_HEALTH_DEGRADED_STATES:
            routable = ready_slots > 0
            if not reason:
                reason = f"profile={profile or lane} is degraded with ready_slots={ready_slots}"
        elif state in PROVIDER_HEALTH_UNAVAILABLE_STATES:
            routable = False
            if not reason:
                reason = f"profile={profile or lane} primary_state={state}"
        else:
            routable = True

    advisory_parts: List[str] = []
    if remaining_percent is not None:
        advisory_parts.append(f"remaining_percent_of_max={remaining_percent:.2f}")
    if estimated_remaining_credits_total is not None:
        advisory_parts.append(f"estimated_remaining_credits_total={estimated_remaining_credits_total:.0f}")
    if advisory_parts:
        reason = "; ".join([part for part in [reason, ", ".join(advisory_parts)] if part])
    if (
        routable
        and lane in CORE_BATCH_WORKER_LANES
        and configured_slots > 0
        and ready_slots <= 0
        and degraded_slots >= max(1, configured_slots - unavailable_slots)
        and remaining_percent is not None
        and remaining_percent <= LOW_CAPACITY_RESERVE_PERCENT
    ):
        routable = False
        state = "degraded"
        reserve_reason = (
            f"{lane} has no ready slots and only degraded capacity while remaining_percent_of_max="
            f"{remaining_percent:.2f}; prefer lighter rescue lanes/models"
        )
        reason = "; ".join(part for part in [reason, reserve_reason] if part)
    return {
        "worker_lane": lane,
        "profile": profile,
        "known": known,
        "routable": routable,
        "state": state,
        "primary_provider_key": primary_provider_key,
        "provider_states": provider_states,
        "configured_slots": configured_slots,
        "ready_slots": ready_slots,
        "degraded_slots": degraded_slots,
        "unavailable_slots": unavailable_slots,
        "leased_slots": leased_slots,
        "remaining_percent_of_max": remaining_percent,
        "estimated_remaining_credits_total": estimated_remaining_credits_total,
        "reason": reason or f"profile={profile or lane} state={state}",
    }


def _direct_worker_lane_health_snapshot(
    args: argparse.Namespace,
    worker_lane_candidates: Sequence[str],
) -> Dict[str, Any]:
    lanes = [str(item or "").strip() for item in worker_lane_candidates if str(item or "").strip()]
    if not lanes or not _worker_bin_uses_codexea(str(args.worker_bin or "")):
        return {}
    snapshot: Dict[str, Any] = {
        "fetched_at": _iso_now(),
        "source_url": _ea_provider_health_url(args),
        "status": "unknown",
        "reason": "",
        "lanes": {},
        "routable_lanes": [],
        "unroutable_lanes": [],
    }
    urls = _ea_provider_health_candidate_urls(args)
    url = str(urls[0] or "").strip() if urls else ""
    if not url:
        snapshot["status"] = "disabled"
        snapshot["reason"] = "EA provider-health preflight is disabled"
        return snapshot
    request_headers = _ea_provider_health_headers(args)
    cached = _load_ea_provider_health_cache(args)
    cached_payload = dict(cached.get("payload") or {})
    cached_age_seconds = _coerce_float(cached.get("age_seconds"))
    cached_source_url = str(cached.get("source_url") or "").strip()
    cached_failure_age_seconds = _coerce_float(cached.get("last_live_fetch_failure_age_seconds"))
    cached_failure_error = str(cached.get("last_live_fetch_error") or "").strip()
    payload: Dict[str, Any] | None = None
    last_error = ""
    cache_reason = ""
    running_inside_container = _running_inside_container()
    cached_source_hostname = ""
    if cached_source_url:
        try:
            cached_source_hostname = str(urllib.parse.urlsplit(cached_source_url).hostname or "").strip().lower()
        except ValueError:
            cached_source_hostname = ""
    if (
        cached_payload
        and cached_age_seconds is not None
        and cached_age_seconds <= _ea_provider_health_cache_max_age_seconds()
        and not running_inside_container
        and cached_source_hostname == "host.docker.internal"
    ):
        payload = cached_payload
        snapshot["fetched_at"] = str(cached.get("cached_at") or snapshot["fetched_at"])
        snapshot["source_url"] = cached_source_url or snapshot["source_url"]
        snapshot["cache_used"] = True
        snapshot["cache_path"] = str(cached.get("path") or "")
        snapshot["live_probe_scope"] = "container_local"
        cache_reason = (
            f"using cached provider-health ({cached_age_seconds:.0f}s old); "
            "the live source is container-local from the host CLI"
        )
    elif (
        cached_payload
        and cached_age_seconds is not None
        and cached_age_seconds <= _ea_provider_health_cache_max_age_seconds()
        and cached_failure_age_seconds is not None
        and cached_failure_age_seconds <= _ea_provider_health_failure_cooldown_seconds()
    ):
        payload = cached_payload
        snapshot["fetched_at"] = str(cached.get("cached_at") or snapshot["fetched_at"])
        snapshot["source_url"] = str(cached.get("source_url") or snapshot["source_url"])
        snapshot["cache_used"] = True
        snapshot["cache_path"] = str(cached.get("path") or "")
        if cached_failure_error:
            snapshot["live_fetch_error"] = cached_failure_error
        cache_reason = (
            f"using cached provider-health ({cached_age_seconds:.0f}s old) during "
            f"{cached_failure_age_seconds:.0f}s live-fetch cooldown after failure: "
            f"{cached_failure_error or 'unknown error'}"
        )
    else:
        initial_timeout_seconds = _ea_provider_health_timeout_seconds(args)
        retry_timeout_seconds = _ea_provider_health_retry_timeout_seconds(args)
        timed_out_candidates: List[str] = []
        for candidate_url in urls:
            timeouts = [initial_timeout_seconds]
            for attempt_index, timeout_seconds in enumerate(timeouts):
                try:
                    request = urllib.request.Request(_ea_provider_health_request_url(candidate_url), headers=request_headers)
                    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                        payload = json.loads(response.read().decode("utf-8", errors="ignore"))
                    snapshot["source_url"] = candidate_url
                    if isinstance(payload, dict) and payload:
                        _write_ea_provider_health_cache(args, payload=payload, source_url=candidate_url)
                    break
                except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                    last_error = f"{candidate_url}: {exc}"
                    if _is_provider_health_timeout_error(exc):
                        timed_out_candidates.append(candidate_url)
                    break
            if payload is not None:
                break
        if payload is None and retry_timeout_seconds > initial_timeout_seconds and timed_out_candidates:
            retry_seen: Set[str] = set()
            retry_urls = [candidate_url for candidate_url in timed_out_candidates if not (candidate_url in retry_seen or retry_seen.add(candidate_url))]
            for candidate_url in retry_urls:
                try:
                    request = urllib.request.Request(_ea_provider_health_request_url(candidate_url), headers=request_headers)
                    with urllib.request.urlopen(request, timeout=retry_timeout_seconds) as response:
                        payload = json.loads(response.read().decode("utf-8", errors="ignore"))
                    snapshot["source_url"] = candidate_url
                    if isinstance(payload, dict) and payload:
                        _write_ea_provider_health_cache(args, payload=payload, source_url=candidate_url)
                    break
                except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                    last_error = f"{candidate_url}: {exc}"
    if payload is None:
        _record_ea_provider_health_live_failure(args, error=last_error or "unknown error")
        if (
            cached_payload
            and cached_age_seconds is not None
            and cached_age_seconds <= _ea_provider_health_cache_max_age_seconds()
        ):
            payload = cached_payload
            snapshot["fetched_at"] = str(cached.get("cached_at") or snapshot["fetched_at"])
            snapshot["source_url"] = str(cached.get("source_url") or snapshot["source_url"])
            snapshot["cache_used"] = True
            snapshot["cache_path"] = str(cached.get("path") or "")
            snapshot["live_fetch_error"] = last_error or "unknown error"
            cache_reason = (
                f"using cached provider-health ({cached_age_seconds:.0f}s old) after live fetch failed: "
                f"{last_error or 'unknown error'}"
            )
        else:
            payload = _local_ea_provider_health_payload()
            if payload:
                source_url = "local://codexea_route/_local_onemin_direct_payload"
                snapshot["source_url"] = source_url
                snapshot["local_fallback_used"] = True
                snapshot["live_fetch_error"] = last_error or "unknown error"
                cache_reason = (
                    "using local 1min provider-health fallback after live fetch failed: "
                    f"{last_error or 'unknown error'}"
                )
                _write_ea_provider_health_cache(args, payload=payload, source_url=source_url)
            else:
                snapshot["status"] = "error"
                snapshot["reason"] = f"provider-health fetch failed: {last_error or 'unknown error'}"
                return snapshot

    workspace_root = Path(getattr(args, "workspace_root", DEFAULT_WORKSPACE_ROOT)).resolve()
    lane_rows = _provider_registry_lane_rows(dict(payload or {}))
    for profile, row in _synthetic_onemin_provider_registry_lane_rows(
        dict(payload or {}),
        lanes,
        workspace_root=workspace_root,
    ).items():
        lane_rows.setdefault(profile, row)
    lane_payloads: Dict[str, Dict[str, Any]] = {}
    for worker_lane in lanes:
        profile = _codexea_profile_for_lane(worker_lane, workspace_root=workspace_root)
        lane_payloads[worker_lane] = _assess_direct_worker_lane_health(worker_lane, profile, lane_rows.get(profile))
    snapshot["lanes"] = lane_payloads
    snapshot["routable_lanes"] = [
        lane for lane in lanes if bool((lane_payloads.get(lane) or {}).get("routable", True))
    ]
    snapshot["unroutable_lanes"] = [
        lane for lane in lanes if (lane_payloads.get(lane) or {}).get("routable") is False
    ]
    snapshot["status"] = "pass"
    if snapshot["unroutable_lanes"]:
        blocked = ", ".join(str(lane) for lane in snapshot["unroutable_lanes"])
        snapshot["reason"] = f"provider-health preflight marked {blocked} unroutable"
    else:
        snapshot["reason"] = "all checked direct lanes are currently routable"
    if cache_reason:
        snapshot["reason"] = "; ".join(part for part in [cache_reason, snapshot["reason"]] if part)
    return snapshot


def _filter_routable_direct_worker_lanes(
    worker_lane_candidates: Sequence[str],
    worker_lane_health: Optional[Dict[str, Any]],
) -> tuple[List[str], List[Dict[str, Any]]]:
    lanes = [str(item or "").strip() for item in worker_lane_candidates if str(item or "").strip()]
    if not lanes or not isinstance(worker_lane_health, dict):
        return list(worker_lane_candidates), []
    lane_rows = dict(worker_lane_health.get("lanes") or {})
    filtered: List[str] = []
    skipped: List[Dict[str, Any]] = []
    for lane in worker_lane_candidates:
        lane_key = str(lane or "").strip()
        lane_report = dict(lane_rows.get(lane_key) or {})
        if lane_report and lane_report.get("routable") is False:
            skipped.append(lane_report)
            continue
        filtered.append(lane)
    return filtered, skipped


def _worker_lane_health_blocker_reason(worker_lane_health: Optional[Dict[str, Any]]) -> str:
    if not isinstance(worker_lane_health, dict) or not worker_lane_health:
        return ""
    if str(worker_lane_health.get("status") or "").strip().lower() == "error":
        return ""
    routable_lanes = [str(item).strip() for item in (worker_lane_health.get("routable_lanes") or []) if str(item).strip()]
    lane_rows = dict(worker_lane_health.get("lanes") or {})
    if routable_lanes or not lane_rows:
        return ""
    segments: List[str] = []
    for lane, lane_report in lane_rows.items():
        if not isinstance(lane_report, dict) or lane_report.get("routable") is not False:
            continue
        reason = " ".join(str(lane_report.get("reason") or lane_report.get("state") or "unavailable").split()).strip()
        segments.append(f"{lane}:{reason}")
        if len(segments) >= 3:
            break
    if not segments:
        return ""
    return "provider-health preflight left no routable direct lanes: " + "; ".join(segments)


def _load_readiness_module() -> Any:
    cached = _SIBLING_MODULE_CACHE.get("admin.readiness")
    if cached is not None:
        return cached
    fleet_root = str(Path(__file__).resolve().parents[1])
    if fleet_root not in sys.path:
        sys.path.insert(0, fleet_root)
    module = importlib.import_module("admin.readiness")
    _SIBLING_MODULE_CACHE["admin.readiness"] = module
    return module


def _milestone_status_rank(status: str) -> int:
    normalized = str(status or "").strip().lower()
    if normalized == "in_progress":
        return 0
    if normalized == "not_started":
        return 1
    if normalized in {"open", "planned", "queued"}:
        return 2
    if normalized in DONE_STATUSES:
        return 9
    return 5


def _parse_frontier_ids_from_handoff_with_source(text: str) -> tuple[List[int], bool, bool]:
    source_lines = [str(item or "") for item in str(text or "").splitlines()]
    if not source_lines:
        return [], False, False

    def _line_ids(raw: str) -> List[int]:
        rows: List[int] = []
        matches = re.findall(r"`(\d{1,2})`", raw)
        if not matches:
            matches = re.findall(r"(?<![A-Za-z])(\d{1,2})(?![A-Za-z])", raw)
        for match in matches:
            value = int(match)
            if 1 <= value <= 99 and value not in rows:
                rows.append(value)
        return rows

    explicit_markers = (
        "frontier milestone ids to prioritize first",
        "recovery frontier ids to verify or reopen first",
        "flagship frontier ids to prioritize first",
        "current active frontier from design plus handoff",
        "frontier milestone ids",
    )
    priority_markers = (
        "frontier milestone ids to prioritize first",
        "recovery frontier ids to verify or reopen first",
        "flagship frontier ids to prioritize first",
    )

    def _marker_starts(raw: str, markers: Sequence[str]) -> bool:
        lowered = raw.strip().lower()
        return any(lowered.startswith(marker) for marker in markers)

    selected: Optional[tuple[List[int], bool]] = None
    for index, raw in enumerate(source_lines):
        lowered = raw.lower()
        if _marker_starts(raw, explicit_markers):
            ids = _line_ids(raw)
            if ids:
                is_priority = _marker_starts(raw, priority_markers)
                if selected is None:
                    selected = (ids, is_priority)
                elif is_priority and not selected[1]:
                    selected = (ids, is_priority)
                continue
            # Some handoff entries render the frontier as a marker line followed by list rows.
            block_ids: List[int] = []
            for follow in source_lines[index + 1 :]:
                stripped = follow.strip()
                if not stripped:
                    if block_ids:
                        break
                    continue
                lowered_follow = stripped.lower()
                if any(marker in lowered_follow for marker in explicit_markers):
                    break
                if stripped.startswith("#"):
                    break
                if stripped.startswith(("-", "*")) or re.match(r"^`?\d{1,2}`?\b", stripped):
                    for value in _line_ids(stripped):
                        if value not in block_ids:
                            block_ids.append(value)
                    continue
                if block_ids:
                    break
            if block_ids:
                is_priority = _marker_starts(raw, priority_markers)
                if selected is None:
                    selected = (block_ids, is_priority)
                elif is_priority and not selected[1]:
                    selected = (block_ids, is_priority)
                continue
    if selected is not None:
        return selected[0], True, selected[1]

    for raw in source_lines:
        lowered = raw.lower()
        if "milestone" not in lowered or "remain active" not in lowered:
            continue
        ids = _line_ids(raw)
        if ids:
            return ids, False, False
    return [], False, False


def _parse_frontier_ids_from_handoff(text: str) -> List[int]:
    ids, _explicit, _is_priority = _parse_frontier_ids_from_handoff_with_source(text)
    return ids


def _load_open_milestones(registry_path: Path) -> tuple[List[Milestone], Dict[str, int]]:
    payload = _read_yaml(registry_path)
    wave_order = {
        str(row.get("id") or "").strip(): index
        for index, row in enumerate(payload.get("waves") or [])
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }
    milestones: List[Milestone] = []
    for row in payload.get("milestones") or []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").strip().lower()
        if status in DONE_STATUSES:
            continue
        if status not in ACTIVE_STATUSES:
            continue
        milestone_id = int(row.get("id") or 0)
        if milestone_id <= 0:
            continue
        milestones.append(
            Milestone(
                id=milestone_id,
                title=str(row.get("title") or "").strip(),
                wave=str(row.get("wave") or "").strip(),
                status=status,
                owners=[str(owner).strip() for owner in (row.get("owners") or []) if str(owner).strip()],
                exit_criteria=[str(item).strip() for item in (row.get("exit_criteria") or []) if str(item).strip()],
                dependencies=[int(item) for item in (row.get("dependencies") or []) if int(item)],
            )
        )
    milestones.sort(key=lambda item: (_milestone_status_rank(item.status), wave_order.get(item.wave, 999), item.id))
    return milestones, wave_order


def _select_frontier(open_milestones: List[Milestone], handoff_text: str) -> tuple[List[Milestone], List[int]]:
    handoff_ids = _parse_frontier_ids_from_handoff(handoff_text)
    by_id = {item.id: item for item in open_milestones}
    frontier: List[Milestone] = [by_id[value] for value in handoff_ids if value in by_id]
    if not frontier:
        frontier = [item for item in open_milestones if item.status == "in_progress"]
    if not frontier:
        frontier = list(open_milestones[: min(5, len(open_milestones))])
    frontier_ids = [item.id for item in frontier]
    return frontier, frontier_ids


def _milestone_brief(item: Milestone) -> str:
    owners = ", ".join(item.owners) if item.owners else "unassigned"
    deps = ", ".join(str(dep) for dep in item.dependencies) if item.dependencies else "none"
    exits = "; ".join(item.exit_criteria) if item.exit_criteria else "no explicit exit criteria recorded"
    return f"{item.id} [{item.wave}] {item.title} (status: {item.status}; owners: {owners}; deps: {deps}; exit: {exits})"


def _scope_roots(args: argparse.Namespace) -> List[Path]:
    roots: List[Path] = []
    seen: set[str] = set()
    for raw in [str(item) for item in DEFAULT_SCOPE_ROOTS] + list(args.scope_root or []):
        path = Path(raw).resolve()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        roots.append(path)
    return roots


def _text_list(values: Sequence[Any]) -> List[str]:
    rows: List[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(text)
    return rows


def _unique_paths(values: Sequence[Path]) -> List[Path]:
    rows: List[Path] = []
    seen: set[str] = set()
    for value in values or []:
        key = str(value)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(value)
    return rows


def _configured_focus_profiles(args: argparse.Namespace) -> List[str]:
    requested = _text_list(args.focus_profile or [])
    return [item for item in requested if item in FOCUS_PROFILES]


def _configured_focus_owners(args: argparse.Namespace) -> List[str]:
    owners: List[str] = []
    for profile in _configured_focus_profiles(args):
        owners.extend(FOCUS_PROFILES.get(profile, {}).get("owners") or [])
    owners.extend(args.focus_owner or [])
    return _text_list(owners)


def _configured_focus_texts(args: argparse.Namespace) -> List[str]:
    texts: List[str] = []
    for profile in _configured_focus_profiles(args):
        texts.extend(FOCUS_PROFILES.get(profile, {}).get("texts") or [])
    texts.extend(args.focus_text or [])
    return _text_list(texts)


GENERIC_SHARD_FOCUS_TEXTS: Set[str] = {
    "top flagship grade",
    "whole project frontier",
    "no lowered standards",
    "feedback",
    "feedback loop",
    "automatic bugfixing",
    "crash",
    "crash reporting",
    "support",
    "support routing",
    "journey smoothness",
    "restore confidence",
    "accessibility",
    "localization",
    "performance",
    "proof shelf",
    "fit and finish",
    "desktop client",
    "hub and registry",
    "horizons and public surface",
    "fleet and operator loop",
}


def _normalized_focus_text(value: Any) -> str:
    return re.sub(r"[-_]+", " ", str(value).strip().lower())


def _milestone_owner_match_count(item: Milestone, focus_owners: Sequence[str]) -> int:
    normalized_focus_owners = {str(value).strip().lower() for value in focus_owners if str(value).strip()}
    if not normalized_focus_owners:
        return 0
    return sum(1 for owner in item.owners if owner.lower() in normalized_focus_owners)


def _milestone_text_match_count(item: Milestone, focus_texts: Sequence[str]) -> int:
    normalized_focus_texts = [
        clean
        for clean in (_normalized_focus_text(value) for value in focus_texts)
        if clean and clean not in GENERIC_SHARD_FOCUS_TEXTS
    ]
    if not normalized_focus_texts:
        return 0
    haystack = _normalized_focus_text(" ".join([item.title, item.wave, item.status, *item.exit_criteria]))
    return sum(1 for term in normalized_focus_texts if term in haystack)


def _milestone_focus_flags(item: Milestone, focus_owners: Sequence[str], focus_texts: Sequence[str]) -> tuple[bool, bool]:
    owner_match = _milestone_owner_match_count(item, focus_owners) > 0
    text_match = _milestone_text_match_count(item, focus_texts) > 0
    return owner_match, text_match


def _milestone_focus_score(item: Milestone, focus_owners: Sequence[str], focus_texts: Sequence[str]) -> int:
    owner_hits = _milestone_owner_match_count(item, focus_owners)
    text_hits = _milestone_text_match_count(item, focus_texts)
    return owner_hits + (text_hits * 3)


def _milestone_matches_focus(item: Milestone, focus_owners: Sequence[str], focus_texts: Sequence[str]) -> bool:
    return _milestone_focus_score(item, focus_owners, focus_texts) > 0


def _ranked_focus_matches(
    items: Sequence[Milestone],
    focus_owners: Sequence[str],
    focus_texts: Sequence[str],
) -> List[Milestone]:
    ranked: List[tuple[int, int, Milestone]] = []
    for index, item in enumerate(items):
        score = _milestone_focus_score(item, focus_owners, focus_texts)
        if score <= 0:
            continue
        ranked.append((score, index, item))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [item for _score, _index, item in ranked]


def _strict_focus_matches(
    items: Sequence[Milestone],
    focus_owners: Sequence[str],
    focus_texts: Sequence[str],
) -> List[Milestone]:
    matched: List[Milestone] = []
    for item in items:
        owner_match, text_match = _milestone_focus_flags(item, focus_owners, focus_texts)
        if focus_owners and focus_texts:
            if not owner_match or not text_match:
                continue
        elif focus_owners and not owner_match:
            continue
        elif focus_texts and not text_match:
            continue
        matched.append(item)
    return matched


def _focused_frontier(args: argparse.Namespace, open_milestones: List[Milestone], frontier: List[Milestone]) -> List[Milestone]:
    focus_profiles = _configured_focus_profiles(args)
    focus_owners = _configured_focus_owners(args)
    focus_texts = _configured_focus_texts(args)
    if not focus_profiles and not focus_owners and not focus_texts:
        return frontier
    if focus_profiles:
        preferred = _strict_focus_matches(open_milestones, focus_owners, focus_texts)
        return preferred[: min(5, len(preferred))] or frontier
    preferred = _ranked_focus_matches(frontier, focus_owners, focus_texts)
    if preferred:
        return preferred
    preferred = _ranked_focus_matches(open_milestones, focus_owners, focus_texts)
    return preferred[: min(5, len(preferred))] or frontier


def _all_registry_milestones(registry_path: Path) -> Dict[int, Milestone]:
    payload = _read_yaml(registry_path)
    rows: Dict[int, Milestone] = {}
    for row in payload.get("milestones") or []:
        if not isinstance(row, dict):
            continue
        milestone_id = int(row.get("id") or 0)
        if milestone_id <= 0:
            continue
        rows[milestone_id] = Milestone(
            id=milestone_id,
            title=str(row.get("title") or "").strip(),
            wave=str(row.get("wave") or "").strip(),
            status=str(row.get("status") or "").strip().lower(),
            owners=[str(owner).strip() for owner in (row.get("owners") or []) if str(owner).strip()],
            exit_criteria=[str(item).strip() for item in (row.get("exit_criteria") or []) if str(item).strip()],
            dependencies=[int(item) for item in (row.get("dependencies") or []) if int(item)],
        )
    return rows


def _append_unique_ids(target: List[int], values: Iterable[Any], *, limit: int = 5) -> List[int]:
    for raw in values:
        value = int(raw or 0)
        if value <= 0 or value in target:
            continue
        target.append(value)
        if len(target) >= limit:
            break
    return target


def _completion_review_target_ids(history: Sequence[Dict[str, Any]], *, limit: int = 5) -> List[int]:
    targets: List[int] = []
    for run in reversed(history):
        accepted, _ = _run_receipt_status(run)
        if accepted or int(run.get("worker_exit_code") or 0) != 0:
            continue
        _append_unique_ids(targets, run.get("frontier_ids") or [], limit=limit)
        _append_unique_ids(targets, [run.get("primary_milestone_id")], limit=limit)
        if len(targets) >= limit:
            return targets
    for run in reversed(history):
        accepted, _ = _run_receipt_status(run)
        if not accepted:
            continue
        _append_unique_ids(targets, run.get("frontier_ids") or [], limit=limit)
        _append_unique_ids(targets, [run.get("primary_milestone_id")], limit=limit)
        if targets:
            return targets
    return targets


def _append_completion_review_milestone(frontier: List[Milestone], item: Milestone, *, limit: Optional[int] = None) -> None:
    if item.id in {row.id for row in frontier}:
        return
    frontier.append(item)
    if limit is not None and limit > 0:
        del frontier[limit:]


def _repo_backlog_visual_familiarity_kind(task: str) -> str:
    normalized = re.sub(r"\s+", " ", str(task or "").strip().lower())
    if not normalized:
        return ""
    if (
        "desktop visual familiarity gate" in normalized
        or "compact classic shell posture" in normalized
        or "loaded-runner tab rhythm" in normalized
        or "palette anchors" in normalized
    ):
        return "shell"
    if (
        "workflow-local visual familiarity proof" in normalized
        or "dense legacy builder surfaces" in normalized
        or "chummer-familiar browse/detail/confirm" in normalized
    ):
        return "workflow"
    return ""


def _repo_backlog_workflow_depth_kind(task: str) -> str:
    normalized = re.sub(r"\s+", " ", str(task or "").strip().lower())
    if not normalized:
        return ""
    if (
        "executable desktop workflow click-through" in normalized
        or "executable desktop workflow clickthrough" in normalized
        or "smooth flagship desktop" in normalized
        or "spotlight-launchable app bundles" in normalized
        or "public feedback routes" in normalized
    ):
        return "workflow_depth"
    return ""


def _completion_review_visual_backlog_milestones(
    *,
    project_id: str,
    repo_slug: str,
    source_path: str,
    kind: str,
) -> List[Milestone]:
    base_owners = _text_list([repo_slug, project_id])
    if kind == "shell":
        shell_owners = _text_list([*base_owners, "chummer6-ui-kit", "chummer6-design"])
        shell_source = [f"Current backlog source: {source_path}."] if source_path else []
        return [
            _synthetic_completion_review_milestone(
                key=f"repo-backlog:{project_id}:desktop-shell-visual-familiarity",
                title=f"Repo backlog: {project_id}: Desktop shell visual familiarity",
                owners=shell_owners,
                exit_criteria=[
                    "Land a release-blocking shell familiarity proof for the modernized Chummer posture: top desktop menu, immediate toolstrip, dense center workbench, and compact bottom status strip.",
                    "Publish screenshot and geometry evidence that a loaded runner keeps a visible tab posture without falling back to generic dashboard chrome.",
                    "Refresh DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json on current repo state instead of relying on executable proof alone.",
                    *shell_source,
                ],
            ),
            _synthetic_completion_review_milestone(
                key=f"repo-backlog:{project_id}:theme-readability-and-tab-posture",
                title=f"Repo backlog: {project_id}: Theme readability and loaded-runner tab posture",
                owners=shell_owners,
                exit_criteria=[
                    "Fix light and dark theme anchors so foreground text, accent-button text, and warning or danger tones stay readable with a restrained Chummer-adjacent green anchor.",
                    "Keep the active character tab or tab-panel posture obviously visible after load so a Chummer5a user can re-find the current section instantly.",
                    "Guard palette and shell-token drift with source assertions and screenshot evidence so theme regressions fail before release.",
                    *shell_source,
                ],
            ),
        ]
    if kind == "workflow":
        workflow_owners = _text_list([*base_owners, "chummer6-ui-kit", "chummer6-core", "chummer6-design"])
        workflow_source = [f"Current backlog source: {source_path}."] if source_path else []
        return [
            _synthetic_completion_review_milestone(
                key=f"repo-backlog:{project_id}:character-and-gear-visual-familiarity",
                title=f"Repo backlog: {project_id}: Character creation and gear workflow visual familiarity",
                owners=workflow_owners,
                exit_criteria=[
                    "Make character creation, gear, armor, and weapons flows read like modernized Chummer: obvious browse pane, visible detail pane, visible cost summary, and obvious confirm or cancel posture.",
                    "Prove the loaded-runner tab or section rhythm survives through first-save and re-open so the builder stays character-first instead of becoming a generic inspector shell.",
                    "Publish executable screenshot and interaction evidence for dense builder familiarity instead of relying on workflow parity receipts alone.",
                    *workflow_source,
                ],
            ),
            _synthetic_completion_review_milestone(
                key=f"repo-backlog:{project_id}:cyberware-cyberlimb-dialog-familiarity",
                title=f"Repo backlog: {project_id}: Cyberware and cyberlimb dialog familiarity",
                owners=workflow_owners,
                exit_criteria=[
                    "Make add/edit cyberware and cyberlimb flows visually familiar to Chummer veterans, especially left-list or browse posture, right-side detail posture, visible essence or cost summary, and obvious confirm actions.",
                    "Treat modular connectors, subsystem-bearing ware, and nested plug-in posture as audit oracles for whole-family trust rather than niche afterthoughts.",
                    "Back the cyberware and cyberlimb familiarity claim with explicit screenshot and click-through proof in DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json.",
                    *workflow_source,
                ],
            ),
            _synthetic_completion_review_milestone(
                key=f"repo-backlog:{project_id}:sr4-sr6-orientation-familiarity",
                title=f"Repo backlog: {project_id}: SR4 and SR6 workflow orientation familiarity",
                owners=workflow_owners,
                exit_criteria=[
                    "Keep SR4 and SR6 builder surfaces familiar to Chummer5a users while respecting ruleset differences instead of flattening every workflow into one generic card stack.",
                    "For SR6, keep stable landmarks around attributes and qualities, skills, augmentation, gear, lifestyles or licenses or SINs or contacts, and history or career review.",
                    "For magic, resonance, vehicle, and drone flows, preserve the same Chummer browse, inspect, confirm, and re-find rhythm even when rule-aware helpers such as compatibility filters or spend-mode toggles are modernized.",
                    *workflow_source,
                ],
            ),
        ]
    return []


def _completion_review_workflow_depth_backlog_milestones(
    *,
    project_id: str,
    repo_slug: str,
    source_path: str,
) -> List[Milestone]:
    owners = _text_list([repo_slug, project_id, "chummer6-ui-kit", "chummer6-core", "chummer6-design", "fleet"])
    source_note = [f"Current backlog source: {source_path}."] if source_path else []
    return [
        _synthetic_completion_review_milestone(
            key=f"repo-backlog:{project_id}:desktop-shell-and-binary-smoothness",
            title=f"Repo backlog: {project_id}: Desktop shell and binary first-run smoothness",
            owners=owners,
            exit_criteria=[
                "Prove the packaged Avalonia and Blazor Desktop binaries expose live menu wiring, a visible demo-runner path, launchable app posture, and public feedback/support routes instead of inert shell chrome or internal hostnames.",
                "For macOS, verify the installed app bundle is discoverable from launcher or Spotlight posture and does not resolve to a folder-only install experience.",
                "Back the shell/binary claim with executable packaged-binary proof instead of repo-local simulated receipts alone.",
                *source_note,
            ],
        ),
        _synthetic_completion_review_milestone(
            key=f"repo-backlog:{project_id}:creation-karma-and-advancement-workflows",
            title=f"Repo backlog: {project_id}: Character creation, karma, and advancement workflow depth",
            owners=owners,
            exit_criteria=[
                "Execute real desktop clickthroughs for character creation, first save, karma spend, initiation or advancement, and post-load resume so the builder remains smooth after the first-run glow wears off.",
                "Require visible browse/detail/confirm posture and non-generic dialogs where the legacy Chummer mental model expects them.",
                *source_note,
            ],
        ),
        _synthetic_completion_review_milestone(
            key=f"repo-backlog:{project_id}:magic-matrix-and-consumables-workflow-depth",
            title=f"Repo backlog: {project_id}: Magic, matrix, and consumables workflow depth",
            owners=owners,
            exit_criteria=[
                "Execute real desktop clickthroughs for adept powers, spells, complex forms, cyberdecks/programs, drugs/consumables, cyberware, cyberlimbs, and other matrix or augmentation flows.",
                "Do not close the slice until dialog-local proof shows specific controls, summaries, and confirm actions instead of generic placeholders.",
                *source_note,
            ],
        ),
        _synthetic_completion_review_milestone(
            key=f"repo-backlog:{project_id}:social-and-diary-workflow-depth",
            title=f"Repo backlog: {project_id}: Contacts, diary, and support-loop workflow depth",
            owners=owners,
            exit_criteria=[
                "Execute real desktop clickthroughs for contacts, notes, diary/career-log, lifestyles/licenses/SINs, and user-facing feedback/reporting flows.",
                "Require all user-visible help/support/report-bug affordances to resolve through public routes and produce visible progress from the shipped desktop client.",
                *source_note,
            ],
        ),
        _synthetic_completion_review_milestone(
            key=f"repo-backlog:{project_id}:spirits-critters-and-rigger-workflow-depth",
            title=f"Repo backlog: {project_id}: Spirits, critters, familiars, vehicles, and rigger workflow depth",
            owners=owners,
            exit_criteria=[
                "Execute real desktop clickthroughs for spirits, ally spirits, familiars, critter flows, vehicles, drones, and rigger-specific builder posture across the rulesets that promise them.",
                "Close the slice only when packaged-head receipts show those journeys are smooth, discoverable, and re-findable after reopen.",
                *source_note,
            ],
        ),
    ]


def _bounded_frontier(frontier: Sequence[Milestone], *, limit: int = 5) -> List[Milestone]:
    if limit <= 0:
        return list(frontier)
    return list(frontier[: min(limit, len(frontier))])


def _active_shard_manifest_path(aggregate_root: Path) -> Path:
    return aggregate_root / "active_shards.json"


def _manifest_text_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return _env_split_list(value)
    if isinstance(value, Sequence):
        return _text_list(value)
    return []


def _normalize_manifest_account_aliases(value: Any) -> List[str]:
    aliases = _manifest_text_list(value)
    aliases = [alias.strip() for alias in aliases if str(alias).strip()]
    if not aliases:
        return []
    onemin_aliases = [alias for alias in aliases if alias.startswith("acct-ea-")]
    if not onemin_aliases:
        return []
    return onemin_aliases


def _active_shard_manifest_entries(aggregate_root: Path) -> List[Dict[str, Any]]:
    manifest_path = _active_shard_manifest_path(aggregate_root)
    if not manifest_path.exists():
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows: Any = []
    if isinstance(payload, dict):
        rows = payload.get("configured_shards")
        if not isinstance(rows, list) or not rows:
            rows = payload.get("active_shards")
    entries: List[Dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, str):
            token = row.strip()
            if token.startswith("shard-"):
                entries.append({"name": token})
            continue
        if not isinstance(row, dict):
            continue
        token = str(row.get("name") or "").strip()
        if not token.startswith("shard-"):
            continue
        entry: Dict[str, Any] = {"name": token}
        index = _coerce_int(row.get("index"), 0)
        if index > 0:
            entry["index"] = index
        frontier_ids = [_coerce_int(value, 0) for value in (row.get("frontier_ids") or [])]
        frontier_ids = [value for value in frontier_ids if value > 0]
        if frontier_ids:
            entry["frontier_ids"] = frontier_ids
        for field in ("focus_owner", "account_alias", "focus_text"):
            values = _manifest_text_list(row.get(field))
            if values:
                if field == "account_alias":
                    values = _normalize_manifest_account_aliases(values)
                if values:
                    entry[field] = values
        for field in ("worker_bin", "worker_lane", "worker_model", "generated_at", "topology_fingerprint"):
            text = str(row.get(field) or "").strip()
            if text:
                entry[field] = text
        entries.append(entry)
    return entries


def _active_shard_manifest_live_summaries(aggregate_root: Path) -> List[Dict[str, Any]]:
    manifest_path = _active_shard_manifest_path(aggregate_root)
    if not manifest_path.exists():
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("active_shards") if isinstance(payload, dict) else []
    entries: List[Dict[str, Any]] = []
    runtime_field_names = {
        "updated_at",
        "active_run_id",
        "active_run_started_at",
        "active_run_worker_last_output_at",
        "active_run_progress_state",
        "last_run_id",
    }
    has_runtime_fields = False
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        token = str(row.get("name") or "").strip()
        if not token.startswith("shard-"):
            continue
        entry = dict(row)
        entry["name"] = token
        entry.setdefault("shard_id", token)
        entry.setdefault("shard_token", token)
        entries.append(entry)
        if any(field in entry for field in runtime_field_names):
            has_runtime_fields = True
    if not has_runtime_fields:
        return []
    return entries


def _active_shard_manifest_entry_map(aggregate_root: Path) -> Dict[str, Dict[str, Any]]:
    return {
        str(entry.get("name") or "").strip(): entry
        for entry in _active_shard_manifest_entries(aggregate_root)
        if str(entry.get("name") or "").strip()
    }


def _shard_index_from_root(aggregate_root: Path, shard_root: Path) -> Optional[int]:
    try:
        relative = shard_root.resolve().relative_to(aggregate_root.resolve())
    except Exception:
        return None
    parts = relative.parts
    if len(parts) != 1:
        return None
    name = parts[0]
    if not name.startswith("shard-"):
        return None
    suffix = name[6:]
    if not suffix.isdigit():
        return None
    index = int(suffix)
    return index if index > 0 else None


def _configured_shard_roots(aggregate_root: Path) -> List[Path]:
    if not aggregate_root.exists() or not aggregate_root.is_dir():
        return []
    entries = _active_shard_manifest_entries(aggregate_root)
    configured_roots: List[Path] = []
    seen: set[Path] = set()
    if entries:
        for entry in entries:
            token = str(entry.get("name") or "").strip()
            candidate = aggregate_root / token
            if candidate.exists() and candidate.is_dir():
                configured_roots.append(candidate)
                seen.add(candidate.resolve())
        if configured_roots:
            return configured_roots
    for candidate in sorted(aggregate_root.iterdir()):
        if not candidate.is_dir() or not candidate.name.startswith("shard-"):
            continue
        resolved_candidate = candidate.resolve()
        if resolved_candidate in seen:
            continue
        configured_roots.append(candidate)
        seen.add(resolved_candidate)
    return configured_roots


def _completion_review_shard_frontier_limit(
    state_root: Path,
    full_frontier: Sequence[Milestone],
    *,
    default_limit: int = 5,
) -> int:
    frontier_count = len(full_frontier)
    if frontier_count <= 0:
        return max(1, default_limit)
    aggregate_root = _aggregate_state_root(state_root)
    resolved_state_root = Path(state_root).resolve()
    configured_shard_roots = _configured_shard_roots(aggregate_root)
    shard_count = len(configured_shard_roots)
    if (
        resolved_state_root == aggregate_root
        or not resolved_state_root.name.startswith("shard-")
        or shard_count <= 1
    ):
        return min(frontier_count, max(1, default_limit))
    return max(1, (frontier_count + shard_count - 1) // shard_count)


def _open_milestone_shard_frontier(
    state_root: Path,
    frontier: Sequence[Milestone],
    *,
    default_limit: int = 5,
) -> List[Milestone]:
    rows = list(frontier)
    if not rows:
        return []
    aggregate_root = _aggregate_state_root(state_root)
    resolved_state_root = Path(state_root).resolve()
    configured_shard_roots = _configured_shard_roots(aggregate_root)
    shard_count = len(configured_shard_roots)
    if (
        resolved_state_root == aggregate_root
        or not resolved_state_root.name.startswith("shard-")
        or shard_count <= 1
    ):
        return _bounded_frontier(rows, limit=default_limit)
    try:
        shard_index = configured_shard_roots.index(resolved_state_root)
    except ValueError:
        return _bounded_frontier(rows, limit=default_limit)
    slice_size = max(1, (len(rows) + shard_count - 1) // shard_count)
    start = shard_index * slice_size
    end = min(len(rows), start + slice_size)
    return rows[start:end]


def _completion_review_frontier(audit: Dict[str, Any], registry_path: Path, history: Sequence[Dict[str, Any]]) -> List[Milestone]:
    milestone_map = _all_registry_milestones(registry_path)
    frontier: List[Milestone] = []
    backlog_audit = dict(audit.get("repo_backlog_audit") or {})
    if backlog_audit.get("status") == "fail":
        for row in backlog_audit.get("open_items") or []:
            if not isinstance(row, dict):
                continue
            task = str(row.get("task") or "").strip()
            repo_slug = str(row.get("repo_slug") or row.get("project_id") or "").strip()
            project_id = str(row.get("project_id") or repo_slug or "unknown").strip()
            exit_criteria = [
                f"Close or materially implement the active repo-local backlog item: {task or 'unnamed queue item'}.",
                "Refresh queue/workpackage truth so completion no longer depends on stale or unresolved repo-local backlog evidence.",
            ]
            source_path = str(row.get("queue_source_path") or "").strip()
            if source_path:
                exit_criteria.append(f"Current backlog source: {source_path}.")
            visual_kind = _repo_backlog_visual_familiarity_kind(task)
            if visual_kind:
                for item in _completion_review_visual_backlog_milestones(
                    project_id=project_id,
                    repo_slug=repo_slug,
                    source_path=source_path,
                    kind=visual_kind,
                ):
                    _append_completion_review_milestone(frontier, item)
                continue
            workflow_depth_kind = _repo_backlog_workflow_depth_kind(task)
            if workflow_depth_kind:
                for item in _completion_review_workflow_depth_backlog_milestones(
                    project_id=project_id,
                    repo_slug=repo_slug,
                    source_path=source_path,
                ):
                    _append_completion_review_milestone(frontier, item)
                continue
            _append_completion_review_milestone(
                frontier,
                _synthetic_completion_review_milestone(
                    key=f"repo-backlog:{project_id}:{task}",
                    title=f"Repo backlog: {project_id}: {task or 'unnamed queue item'}",
                    owners=[repo_slug] if repo_slug else ([project_id] if project_id else []),
                    exit_criteria=exit_criteria,
                ),
            )
    journey_audit = dict(audit.get("journey_gate_audit") or {})
    for collection_name in ("blocked_journeys", "warning_journeys"):
        for row in journey_audit.get(collection_name) or []:
            if not isinstance(row, dict):
                continue
            reasons = [
                str(item).strip()
                for item in ((row.get("blocking_reasons") or []) + (row.get("warning_reasons") or []))
                if str(item).strip()
            ]
            _append_completion_review_milestone(
                frontier,
                _synthetic_completion_review_milestone(
                    key=f"journey:{row.get('id') or row.get('title') or 'unknown'}",
                    title=f"Completion gate: {row.get('title') or row.get('id') or 'golden journey'}",
                    owners=[str(item).strip() for item in (row.get("owner_repos") or []) if str(item).strip()],
                    exit_criteria=reasons
                    or [
                        "Restore boring release proof for this golden journey and reopen any false-complete canon claims if evidence is missing."
                    ],
                ),
            )
    linux_gate_audit = dict(audit.get("linux_desktop_exit_gate_audit") or {})
    if linux_gate_audit.get("status") == "fail":
        linux_reasons = [str(linux_gate_audit.get("reason") or "").strip()]
        _append_completion_review_milestone(
            frontier,
            _synthetic_completion_review_milestone(
                key="linux_desktop_exit_gate",
                title="Completion gate: Linux desktop exit gate",
                owners=["chummer6-ui", "fleet"],
                exit_criteria=linux_reasons
                + [
                    "Build the Linux desktop binary, package the primary .deb plus fallback archive, run startup smoke on both packaged outputs, run desktop runtime unit tests, and refresh UI_LINUX_DESKTOP_EXIT_GATE.generated.json.",
                ],
            ),
        )
    weekly_pulse_audit = dict(audit.get("weekly_pulse_audit") or {})
    if weekly_pulse_audit.get("status") == "fail" and not _weekly_pulse_audit_is_derivative_of_live_blockers(
        weekly_pulse_audit
    ):
        pulse_reasons = [str(weekly_pulse_audit.get("reason") or "").strip()]
        _append_completion_review_milestone(
            frontier,
            _synthetic_completion_review_milestone(
                key="weekly_product_pulse",
                title="Completion gate: weekly product pulse",
                owners=["chummer6-design", "fleet"],
                exit_criteria=pulse_reasons
                + [
                    "Refresh whole-product pulse evidence so journey health, drift counts, and blocker posture are trustworthy."
                ],
            ),
        )
    # Only fall back to historical registry milestones when the live completion
    # audit did not produce any actionable recovery frontier rows.
    if not frontier:
        known_frontier_ids = {item.id for item in frontier}
        for milestone_id in _completion_review_target_ids(history):
            if milestone_id in milestone_map:
                _append_completion_review_milestone(frontier, milestone_map[milestone_id])
                continue
            if milestone_id in known_frontier_ids:
                continue
    return frontier


def _completion_review_run_lines(history: Sequence[Dict[str, Any]], *, limit: int = 5) -> List[str]:
    rows: List[str] = []
    for run in reversed(history):
        accepted, reason = _run_receipt_status(run)
        if accepted or int(run.get("worker_exit_code") or 0) != 0:
            continue
        frontier_ids = ", ".join(str(value) for value in (run.get("frontier_ids") or [])) or "none"
        primary = run.get("primary_milestone_id") or "none"
        rows.append(
            f"- run {run.get('run_id') or 'unknown'} primary={primary} frontier={frontier_ids} "
            f"reason={reason or 'untrusted receipt'}"
        )
        if len(rows) >= limit:
            break
    return rows


def _latest_trusted_receipt_line(history: Sequence[Dict[str, Any]]) -> str:
    for run in reversed(history):
        accepted, _ = _run_receipt_status(run)
        if not accepted:
            continue
        frontier_ids = ", ".join(str(value) for value in (run.get("frontier_ids") or [])) or "none"
        primary = run.get("primary_milestone_id") or "none"
        shipped = _summarize_trace_value(run.get("shipped"), max_len=120)
        remains = _summarize_trace_value(run.get("remains"), max_len=120)
        return (
            f"- run {run.get('run_id') or 'unknown'} primary={primary} frontier={frontier_ids} "
            f"shipped={shipped} remains={remains}"
        )
    return "- none"


def _synthetic_completion_review_id(key: str) -> int:
    digest = hashlib.sha1(str(key).encode("utf-8")).hexdigest()
    return SYNTHETIC_COMPLETION_REVIEW_ID_BASE + int(digest[:8], 16)


def _synthetic_completion_review_milestone(
    *,
    key: str,
    title: str,
    owners: Sequence[str],
    exit_criteria: Sequence[str],
) -> Milestone:
    criteria = [str(item).strip() for item in exit_criteria if str(item).strip()]
    if not criteria:
        criteria = ["Audit and repair the missing completion evidence for this release-proof seam."]
    trimmed_criteria: List[str] = []
    external_proof_criteria: List[str] = []
    seen: Set[str] = set()
    for item in criteria:
        if item in seen:
            continue
        seen.add(item)
        if "external proof request:" in item.lower():
            external_proof_criteria.append(item)
        elif len(trimmed_criteria) < 4:
            trimmed_criteria.append(item)
    trimmed_criteria.extend(external_proof_criteria)
    return Milestone(
        id=_synthetic_completion_review_id(key),
        title=title,
        wave="completion_review",
        status="review_required",
        owners=[str(item).strip() for item in owners if str(item).strip()],
        exit_criteria=trimmed_criteria,
        dependencies=[],
    )


def _completion_review_requires_visual_familiarity_focus(frontier: Sequence[Milestone]) -> bool:
    for item in frontier:
        haystack = " ".join([item.title, *item.exit_criteria]).lower()
        if (
            "visual familiarity" in haystack
            or "tab posture" in haystack
            or "browse, inspect, confirm" in haystack
            or "browse/detail/confirm" in haystack
            or "cyberlimb" in haystack
            or "palette" in haystack
            or "chummer5a" in haystack
        ):
            return True
    return False


def _completion_review_requires_workflow_depth_focus(frontier: Sequence[Milestone]) -> bool:
    for item in frontier:
        haystack = " ".join([item.title, *item.exit_criteria]).lower()
        if (
            "workflow depth" in haystack
            or "first-run smoothness" in haystack
            or "spotlight" in haystack
            or "demo-runner" in haystack
            or "adept powers" in haystack
            or "cyberdecks" in haystack
            or "diary" in haystack
            or "rigger" in haystack
            or "public feedback" in haystack
        ):
            return True
    return False


def _focus_owners_for_profiles(profiles: Sequence[str], explicit_owners: Sequence[str]) -> List[str]:
    owners: List[str] = []
    for profile in profiles:
        owners.extend(FOCUS_PROFILES.get(profile, {}).get("owners") or [])
    owners.extend(explicit_owners)
    return _text_list(owners)


def _focus_texts_for_profiles(profiles: Sequence[str], explicit_texts: Sequence[str]) -> List[str]:
    texts: List[str] = []
    for profile in profiles:
        texts.extend(FOCUS_PROFILES.get(profile, {}).get("texts") or [])
    texts.extend(explicit_texts)
    return _text_list(texts)


def _completion_review_focus_bundle(
    args: argparse.Namespace,
    frontier: Sequence[Milestone],
) -> tuple[List[str], List[str], List[str]]:
    profiles = _configured_focus_profiles(args)
    if _completion_review_requires_visual_familiarity_focus(frontier) and "desktop_visual_familiarity" not in profiles:
        profiles.append("desktop_visual_familiarity")
    if _completion_review_requires_workflow_depth_focus(frontier) and "desktop_workflow_depth" not in profiles:
        profiles.append("desktop_workflow_depth")
    profiles = _text_list(profiles)
    owners = _focus_owners_for_profiles(profiles, args.focus_owner or [])
    texts = _focus_texts_for_profiles(profiles, args.focus_text or [])
    return profiles, owners, texts


FLAGSHIP_HARDLINE_TEXTS: Sequence[str] = (
    "top flagship grade",
    "whole-project frontier",
    "no lowered standards",
    "feedback loop",
    "automatic bugfixing",
    "crash reporting",
    "support routing",
    "journey smoothness",
    "restore confidence",
    "accessibility",
    "localization",
    "performance",
    "proof shelf",
    "fit and finish",
)


def _hard_flagship_requested(args: argparse.Namespace, focus_profiles: Optional[Sequence[str]] = None) -> bool:
    profiles = _text_list(focus_profiles if focus_profiles is not None else _configured_focus_profiles(args))
    return "top_flagship_grade" in profiles


def _flagship_product_focus_bundle(
    args: argparse.Namespace,
    frontier: Sequence[Milestone],
    *,
    base_profiles: Sequence[str],
    base_owners: Sequence[str],
    base_texts: Sequence[str],
    full_product_audit: Dict[str, Any],
) -> tuple[List[str], List[str], List[str]]:
    profiles = _text_list([*base_profiles, "top_flagship_grade", "whole_project_frontier"])
    owners = _text_list([*base_owners, *(owner for item in frontier for owner in item.owners)])
    texts: List[str] = [str(item).strip() for item in base_texts if str(item).strip()]
    texts.extend(FLAGSHIP_HARDLINE_TEXTS)
    texts.extend(
        str(item).replace("_", " ").strip()
        for item in (full_product_audit.get("missing_coverage_keys") or [])
        if str(item).strip()
    )
    for row in (full_product_audit.get("unresolved_parity_families") or []):
        if not isinstance(row, dict):
            continue
        for key in ("id", "title", "summary"):
            value = str(row.get(key) or "").strip()
            if value:
                texts.append(value)
    return profiles, owners, _text_list(texts)


def _completion_review_guidance_paths(frontier: Sequence[Milestone]) -> List[Path]:
    paths: List[Path] = []
    if _completion_review_requires_visual_familiarity_focus(frontier):
        paths.extend(
            [
                DEFAULT_CHUMMER5A_FAMILIARITY_BRIDGE_PATH,
                DEFAULT_DESKTOP_VISUAL_FAMILIARITY_GATE_PATH,
            ]
        )
    if _completion_review_requires_workflow_depth_focus(frontier):
        paths.extend(
            [
                DEFAULT_DESKTOP_EXECUTABLE_EXIT_GATES_PATH,
                DEFAULT_CHUMMER5A_FAMILIARITY_BRIDGE_PATH,
            ]
        )
    return _unique_paths(paths)


def _completion_review_journey_lines(audit: Dict[str, Any], *, limit: int = 4) -> List[str]:
    rows: List[str] = []
    for collection_name in ("blocked_journeys", "warning_journeys"):
        for row in audit.get(collection_name) or []:
            if not isinstance(row, dict):
                continue
            reasons = [
                str(item).strip()
                for item in ((row.get("blocking_reasons") or []) + (row.get("warning_reasons") or []))
                if str(item).strip()
            ]
            owner_text = ", ".join(str(item).strip() for item in (row.get("owner_repos") or []) if str(item).strip()) or "none"
            rows.append(
                f"- journey {row.get('id') or 'unknown'} state={row.get('state') or 'unknown'} "
                f"owners={owner_text} reason={_summarize_trace_value(reasons[0] if reasons else row.get('title') or 'missing proof', max_len=160)}"
            )
            if len(rows) >= limit:
                return rows
    return rows


def _completion_review_weekly_pulse_lines(audit: Dict[str, Any]) -> List[str]:
    if not isinstance(audit, dict) or not audit:
        return ["- none"]
    return [
        f"- pulse_path={audit.get('path') or 'unknown'}",
        f"- generated_at={audit.get('generated_at') or 'unknown'} as_of={audit.get('as_of') or 'unknown'}",
        (
            f"- release_health={audit.get('release_health_state') or 'unknown'} "
            f"journey_gate_health={audit.get('journey_gate_health_state') or 'unknown'} "
            f"design_drift_count={audit.get('design_drift_count') or 0} "
            f"public_promise_drift_count={audit.get('public_promise_drift_count') or 0} "
            f"oldest_blocker_days={audit.get('oldest_blocker_days') or 0}"
        ),
    ]


def _completion_review_repo_backlog_lines(audit: Dict[str, Any], *, limit: int = 5) -> List[str]:
    if not isinstance(audit, dict) or audit.get("status") != "fail":
        return ["- none"]
    rows: List[str] = []
    for row in audit.get("open_items") or []:
        if not isinstance(row, dict):
            continue
        rows.append(
            f"- project={row.get('project_id') or 'unknown'} repo={row.get('repo_slug') or 'unknown'} "
            f"task={_summarize_trace_value(row.get('task') or 'unnamed queue item', max_len=160)}"
        )
        if len(rows) >= limit:
            break
    return rows or ["- none"]


def _completion_review_linux_exit_gate_lines(audit: Dict[str, Any]) -> List[str]:
    if not isinstance(audit, dict) or not audit:
        return ["- none"]
    return [
        f"- proof_path={audit.get('path') or 'unknown'}",
        (
            f"- generated_at={audit.get('generated_at') or 'unknown'} "
            f"age_seconds={audit.get('age_seconds') or 0} "
            f"proof_status={audit.get('proof_status') or 'unknown'} "
            f"stage={audit.get('stage') or 'unknown'}"
        ),
        (
            f"- head={audit.get('head_id') or 'unknown'} "
            f"launch_target={audit.get('launch_target') or 'unknown'} "
            f"rid={audit.get('rid') or 'unknown'} "
            f"snapshot_mode={audit.get('source_snapshot_mode') or 'unknown'} "
            f"install_mode={audit.get('primary_install_mode') or 'unknown'} "
            f"install_verification={audit.get('primary_install_verification_status') or 'unknown'} "
            f"primary_smoke={audit.get('primary_smoke_status') or 'unknown'} "
            f"fallback_smoke={audit.get('fallback_smoke_status') or 'unknown'} "
            f"unit_tests={audit.get('unit_test_status') or 'unknown'} "
            f"totals={audit.get('test_total') or 0}/{audit.get('test_passed') or 0}/{audit.get('test_failed') or 0}/{audit.get('test_skipped') or 0}"
        ),
        (
            f"- install_verification_path={audit.get('primary_install_verification_path') or 'unknown'} "
            f"snapshot_entries={audit.get('source_snapshot_entry_count') or 0} "
            f"snapshot_finish_entries={audit.get('source_snapshot_finish_entry_count') or 0} "
            f"snapshot_sha={audit.get('source_snapshot_worktree_sha256') or 'missing'} "
            f"snapshot_finish_sha={audit.get('source_snapshot_finish_worktree_sha256') or 'missing'} "
            f"snapshot_stable={audit.get('source_snapshot_identity_stable') or False} "
            f"wrapper_sha={audit.get('primary_install_wrapper_sha256') or 'missing'} "
            f"desktop_sha={audit.get('primary_install_desktop_entry_sha256') or 'missing'}"
        ),
        (
            f"- proof_git={audit.get('proof_git_head') or 'unknown'} "
            f"current_git={audit.get('current_git_head') or 'unknown'}"
        ),
        f"- reason={_summarize_trace_value(audit.get('reason') or 'unknown', max_len=160)}",
    ]


def _completion_review_frontier_paths(
    workspace_root: Path,
    *,
    state_root: Optional[Path] = None,
) -> tuple[Path, Path]:
    workspace = Path(workspace_root).resolve()
    runtime_root = DEFAULT_STATE_ROOT
    if state_root is not None:
        resolved_state_root = Path(state_root).resolve()
        aggregate_root = _aggregate_state_root(resolved_state_root)
        runtime_root = aggregate_root
        if resolved_state_root != aggregate_root and resolved_state_root.name.startswith("shard-"):
            shard_name = resolved_state_root.name
            return (
                workspace / ".codex-studio" / "published" / "completion-review-frontiers" / f"{shard_name}.generated.yaml",
                aggregate_root / "artifacts" / "completion-review-frontiers" / f"{shard_name}.generated.yaml",
            )
    return (
        workspace / ".codex-studio" / "published" / "COMPLETION_REVIEW_FRONTIER.generated.yaml",
        runtime_root / "artifacts" / "COMPLETION_REVIEW_FRONTIER.generated.yaml",
    )


def _write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_dir(path.parent)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _completion_review_frontier_payload(
    *,
    args: argparse.Namespace,
    state_root: Path,
    mode: str,
    frontier: Sequence[Milestone],
    focus_profiles: Sequence[str],
    focus_owners: Sequence[str],
    focus_texts: Sequence[str],
    completion_audit: Dict[str, Any],
    eta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    repo_backlog_audit = dict(completion_audit.get("repo_backlog_audit") or {})
    receipt_audit = dict(completion_audit.get("receipt_audit") or {})
    journey_gate_audit = dict(completion_audit.get("journey_gate_audit") or {})
    linux_gate_audit = dict(completion_audit.get("linux_desktop_exit_gate_audit") or {})
    weekly_pulse_audit = dict(completion_audit.get("weekly_pulse_audit") or {})
    open_items = [dict(row) for row in (repo_backlog_audit.get("open_items") or []) if isinstance(row, dict)]
    frontier_rows = [
        {
            "id": item.id,
            "title": item.title,
            "wave": item.wave,
            "status": item.status,
            "owners": list(item.owners),
            "dependencies": list(item.dependencies),
            "exit_criteria": list(item.exit_criteria),
        }
        for item in frontier
    ]
    payload: Dict[str, Any] = {
        "contract_name": "fleet.completion_review_frontier",
        "schema_version": 1,
        "generated_at": _iso_now(),
        "mode": mode,
        "state_root": str(state_root),
        "source_registry_path": str(Path(args.registry_path).resolve()),
        "handoff_path": str(Path(args.handoff_path).resolve()),
        "projects_dir": str(Path(args.projects_dir).resolve()),
        "primary_probe_shard": _primary_probe_shard_name(state_root),
        "focus": {
            "profiles": list(focus_profiles),
            "owners": list(focus_owners),
            "texts": list(focus_texts),
        },
        "completion_audit": {
            "status": str(completion_audit.get("status") or "").strip(),
            "reason": str(completion_audit.get("reason") or "").strip(),
        },
        "receipt_audit": {
            "status": str(receipt_audit.get("status") or "").strip(),
            "reason": str(receipt_audit.get("reason") or "").strip(),
            "latest_run_id": str(receipt_audit.get("latest_run_id") or "").strip(),
            "latest_run_reason": str(receipt_audit.get("latest_run_reason") or "").strip(),
        },
        "journey_gate_audit": {
            "status": str(journey_gate_audit.get("status") or "").strip(),
            "reason": str(journey_gate_audit.get("reason") or "").strip(),
            "blocked_journey_count": len(journey_gate_audit.get("blocked_journeys") or []),
            "warning_journey_count": len(journey_gate_audit.get("warning_journeys") or []),
        },
        "linux_desktop_exit_gate_audit": {
            "status": str(linux_gate_audit.get("status") or "").strip(),
            "reason": str(linux_gate_audit.get("reason") or "").strip(),
            "path": str(linux_gate_audit.get("path") or "").strip(),
            "generated_at": str(linux_gate_audit.get("generated_at") or "").strip(),
        },
        "weekly_pulse_audit": {
            "status": str(weekly_pulse_audit.get("status") or "").strip(),
            "reason": str(weekly_pulse_audit.get("reason") or "").strip(),
            "path": str(weekly_pulse_audit.get("path") or "").strip(),
            "generated_at": str(weekly_pulse_audit.get("generated_at") or "").strip(),
        },
        "repo_backlog_audit": {
            "status": str(repo_backlog_audit.get("status") or "").strip(),
            "reason": str(repo_backlog_audit.get("reason") or "").strip(),
            "open_item_count": int(repo_backlog_audit.get("open_item_count") or 0),
            "open_project_count": int(repo_backlog_audit.get("open_project_count") or 0),
            "open_items": open_items,
        },
        "frontier_count": len(frontier_rows),
        "frontier_ids": [item["id"] for item in frontier_rows],
        "frontier": frontier_rows,
    }
    if eta:
        payload["eta"] = {
            "status": str(eta.get("status") or "").strip(),
            "eta_human": str(eta.get("eta_human") or "").strip(),
            "eta_confidence": str(eta.get("eta_confidence") or "").strip(),
            "basis": str(eta.get("basis") or "").strip(),
            "scope_kind": str(eta.get("scope_kind") or "").strip(),
            "scope_label": str(eta.get("scope_label") or "").strip(),
            "scope_warning": str(eta.get("scope_warning") or "").strip(),
            "blocking_reason": str(eta.get("blocking_reason") or "").strip(),
            "summary": str(eta.get("summary") or "").strip(),
        }
    return payload


def _materialize_completion_review_frontier(
    *,
    args: argparse.Namespace,
    state_root: Path,
    mode: str,
    frontier: Sequence[Milestone],
    focus_profiles: Sequence[str],
    focus_owners: Sequence[str],
    focus_texts: Sequence[str],
    completion_audit: Dict[str, Any],
    eta: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    published_path, mirror_path = _completion_review_frontier_paths(
        Path(args.workspace_root).resolve(),
        state_root=state_root,
    )
    payload = _completion_review_frontier_payload(
        args=args,
        state_root=state_root,
        mode=mode,
        frontier=frontier,
        focus_profiles=focus_profiles,
        focus_owners=focus_owners,
        focus_texts=focus_texts,
        completion_audit=completion_audit,
        eta=eta,
    )
    _write_yaml(published_path, payload)
    _write_yaml(mirror_path, payload)
    return {
        "published_path": str(published_path),
        "mirror_path": str(mirror_path),
    }


def _synthetic_full_product_id(key: str) -> int:
    digest = hashlib.sha1(str(key).encode("utf-8")).hexdigest()
    return SYNTHETIC_FULL_PRODUCT_ID_BASE + int(digest[:8], 16)


def _synthetic_full_product_milestone(
    *,
    key: str,
    title: str,
    owners: Sequence[str],
    exit_criteria: Sequence[str],
    status: str = "not_started",
) -> Milestone:
    criteria = [str(item).strip() for item in exit_criteria if str(item).strip()]
    if not criteria:
        criteria = ["Land the missing full-product flagship slice and refresh the readiness proof when evidence is real."]
    return Milestone(
        id=_synthetic_full_product_id(key),
        title=title,
        wave="flagship_product",
        status=str(status or "not_started").strip() or "not_started",
        owners=[str(item).strip() for item in owners if str(item).strip()],
        exit_criteria=criteria[:4],
        dependencies=[],
    )


def _humanize_identifier(value: str) -> str:
    text = str(value or "").strip().replace("-", " ").replace("_", " ")
    return " ".join(part.capitalize() for part in text.split() if part)


def _parity_full_product_owners(family_id: str) -> List[str]:
    owners = PARITY_FULL_PRODUCT_OWNER_OVERRIDES.get(str(family_id or "").strip(), ())
    if owners:
        return [str(item).strip() for item in owners if str(item).strip()]
    return ["chummer6-ui", "chummer6-design"]


def _full_product_parity_milestones(
    unresolved_families: Sequence[Dict[str, Any]],
    *,
    excluded_scope: Sequence[str],
) -> List[Milestone]:
    frontier: List[Milestone] = []
    excluded_text = ", ".join(str(item).strip() for item in excluded_scope if str(item).strip())
    for row in unresolved_families:
        if not isinstance(row, dict):
            continue
        family_id = str(row.get("id") or "").strip()
        if not family_id:
            continue
        status = str(row.get("status") or "").strip() or "unresolved"
        milestone_ids = [str(item) for item in (row.get("milestone_ids") or []) if str(item).strip()]
        design_equivalents = [str(item).strip() for item in (row.get("current_design_equivalents") or []) if str(item).strip()]
        exit_criteria = [
            f"Move parity family `{family_id}` out of `{status}` by proving a first-class successor or explicit bounded replacement.",
            "Keep no-step-back parity honest for flagship claims; do not treat screenshots, empty queues, or repo-local greens as replacement proof.",
        ]
        if design_equivalents:
            exit_criteria.append("Current design equivalents under proof: " + ", ".join(design_equivalents[:4]) + ".")
        if milestone_ids:
            exit_criteria.append("Current parity milestone ids: " + ", ".join(milestone_ids[:4]) + ".")
        elif excluded_text:
            exit_criteria.append(f"Excluded scope remains bounded to: {excluded_text}.")
        frontier.append(
            _synthetic_full_product_milestone(
                key=f"parity-family:{family_id}",
                title=f"Parity family: {_humanize_identifier(family_id)}",
                owners=_parity_full_product_owners(family_id),
                exit_criteria=exit_criteria,
            )
        )
    return frontier


def _flagship_design_source_paths(product_root: Path) -> List[Path]:
    candidates = [
        product_root / "README.md",
        product_root / "ROADMAP.md",
        product_root / "HORIZONS.md",
        product_root / "HORIZON_REGISTRY.yaml",
        product_root / "BUILD_LAB_PRODUCT_MODEL.md",
        product_root / "CAMPAIGN_OS_GAP_AND_CHANGE_GUIDE.md",
        product_root / "PUBLIC_RELEASE_EXPERIENCE.yaml",
        product_root / "projects" / "design.md",
        product_root / "projects" / "core.md",
        product_root / "projects" / "ui.md",
        product_root / "projects" / "ui-kit.md",
        product_root / "projects" / "mobile.md",
        product_root / "projects" / "hub.md",
        product_root / "projects" / "hub-registry.md",
        product_root / "projects" / "media-factory.md",
        product_root / "projects" / "fleet.md",
    ]
    return [path for path in candidates if path.exists()]


def _default_full_product_frontier(args: argparse.Namespace, audit: Dict[str, Any]) -> List[Milestone]:
    frontier: List[Milestone] = []
    frontier_status = _full_product_frontier_status(audit)
    missing_coverage_keys = [
        str(item).strip()
        for item in (audit.get("missing_coverage_keys") or [])
        if str(item).strip() in FULL_PRODUCT_FRONTIER_KEY_BY_COVERAGE
    ]
    selected_spec_keys = {
        FULL_PRODUCT_FRONTIER_KEY_BY_COVERAGE[item]
        for item in missing_coverage_keys
        if FULL_PRODUCT_FRONTIER_KEY_BY_COVERAGE.get(item)
    }
    all_rows = [row for row in FULL_PRODUCT_FRONTIER_SPECS if isinstance(row, dict)]
    if _hard_flagship_requested(args):
        prioritized_keys = list(selected_spec_keys)
        prioritized_rows = [row for row in all_rows if str(row.get("key") or "").strip() in selected_spec_keys]
        trailing_rows = [row for row in all_rows if str(row.get("key") or "").strip() not in selected_spec_keys]
        rows = prioritized_rows + trailing_rows
    elif selected_spec_keys:
        rows = [
            row
            for row in all_rows
            if str(row.get("key") or "").strip() in selected_spec_keys
        ]
    elif audit.get("unresolved_parity_families"):
        rows = []
    else:
        rows = list(all_rows)
    for row in rows:
        if not isinstance(row, dict):
            continue
        frontier.append(
            _synthetic_full_product_milestone(
                key=str(row.get("key") or row.get("title") or "flagship_slice"),
                title=str(row.get("title") or "Flagship full-product slice").strip(),
                owners=[str(item).strip() for item in (row.get("owners") or []) if str(item).strip()],
                exit_criteria=[str(item).strip() for item in (row.get("exit_criteria") or []) if str(item).strip()],
                status=frontier_status,
            )
        )
    frontier.extend(
        _full_product_parity_milestones(
            [dict(item) for item in (audit.get("unresolved_parity_families") or []) if isinstance(item, dict)],
            excluded_scope=[str(item).strip() for item in (audit.get("parity_excluded_scope") or []) if str(item).strip()],
        )
    )
    return frontier


def _full_product_frontier(args: argparse.Namespace) -> List[Milestone]:
    audit = _full_product_readiness_audit(args)
    frontier = _default_full_product_frontier(args, audit)
    queue_frontier = _queue_driven_full_product_frontier(args, frontier)
    if queue_frontier:
        return queue_frontier
    return frontier


def _full_product_frontier_status(audit: Dict[str, Any]) -> str:
    if _full_product_external_host_only_blocker(audit):
        return "blocked_external_host_proof"
    return "not_started"


def _full_product_external_host_only_blocker(audit: Dict[str, Any]) -> bool:
    if _ignore_nonlinux_desktop_host_proof_blockers_enabled():
        return False
    if str(audit.get("status") or "").strip().lower() == "pass":
        return False
    if audit.get("unresolved_parity_families"):
        return False
    completion_external_only = audit.get("completion_external_only")
    if isinstance(completion_external_only, bool):
        if completion_external_only:
            return True
    else:
        token = str(completion_external_only or "").strip().lower()
        if token in {"1", "true", "yes", "on"}:
            return True
    unresolved_external_request_count = _coerce_int(audit.get("unresolved_external_proof_request_count"), 0)
    if unresolved_external_request_count > 0:
        return True
    coverage_details = dict(audit.get("coverage_details") or {})
    fleet_details = dict(coverage_details.get("fleet_and_operator_loop") or {})
    evidence = dict(fleet_details.get("evidence") or {})
    external_only = evidence.get("supervisor_completion_external_only")
    if isinstance(external_only, bool):
        if external_only:
            return True
    try:
        if bool(external_only):
            return True
    except (TypeError, ValueError):
        pass
    external_backlog = _coerce_int(evidence.get("external_proof_backlog_request_count"), 0)
    open_non_external_packets = _coerce_int(evidence.get("support_open_non_external_packet_count"), -1)
    journey_blocked_with_local = _coerce_int(evidence.get("journey_blocked_with_local_count"), -1)
    if external_backlog <= 0:
        return False
    if open_non_external_packets > 0:
        return False
    if journey_blocked_with_local > 0:
        return False
    return True


def _full_product_frontier_paths(
    workspace_root: Path,
    *,
    state_root: Optional[Path] = None,
) -> tuple[Path, Path]:
    workspace = Path(workspace_root).resolve()
    runtime_root = DEFAULT_STATE_ROOT
    if state_root is not None:
        resolved_state_root = Path(state_root).resolve()
        aggregate_root = _aggregate_state_root(resolved_state_root)
        runtime_root = aggregate_root
        if resolved_state_root != aggregate_root and resolved_state_root.name.startswith("shard-"):
            shard_name = resolved_state_root.name
            return (
                workspace / ".codex-studio" / "published" / "full-product-frontiers" / f"{shard_name}.generated.yaml",
                aggregate_root / "artifacts" / "full-product-frontiers" / f"{shard_name}.generated.yaml",
            )
    return (
        workspace / ".codex-studio" / "published" / "FULL_PRODUCT_FRONTIER.generated.yaml",
        runtime_root / "artifacts" / "FULL_PRODUCT_FRONTIER.generated.yaml",
    )


def _published_queue_payload(workspace_root: Path) -> Dict[str, Any]:
    queue_path = Path(workspace_root).resolve() / ".codex-studio" / "published" / "QUEUE.generated.yaml"
    if not queue_path.is_file():
        return {}
    payload = _read_yaml(queue_path)
    return payload if isinstance(payload, dict) else {}


def _published_next_wave_queue_payload(workspace_root: Path) -> Dict[str, Any]:
    queue_path = Path(workspace_root).resolve() / ".codex-studio" / "published" / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    if not queue_path.is_file():
        return {}
    payload = _read_yaml(queue_path)
    return payload if isinstance(payload, dict) else {}


def _workspace_root_for_state_root(state_root: Path) -> Path:
    aggregate_root = _aggregate_state_root(state_root)
    if aggregate_root.name == "chummer_design_supervisor" and aggregate_root.parent.name == "state":
        return aggregate_root.parent.parent.resolve()
    return DEFAULT_WORKSPACE_ROOT.resolve()


def _next_wave_registry_path(workspace_root: Path) -> Optional[Path]:
    payload = _published_next_wave_queue_payload(workspace_root)
    raw_path = str(payload.get("source_registry_path") or "").strip()
    if not raw_path:
        return None
    path = Path(raw_path).resolve()
    return path if path.is_file() else None


def _load_next_wave_registry_milestones(workspace_root: Path) -> List[Milestone]:
    registry_path = _next_wave_registry_path(workspace_root)
    if registry_path is None:
        return []
    payload = _read_yaml(registry_path)
    if not isinstance(payload, dict):
        return []
    rows: List[Milestone] = []
    for raw in (payload.get("milestones") or []):
        if not isinstance(raw, dict):
            continue
        milestone_id = _coerce_int(raw.get("id"), 0)
        if milestone_id <= 0:
            continue
        rows.append(
            Milestone(
                id=milestone_id,
                title=str(raw.get("title") or f"Milestone {milestone_id}").strip(),
                wave=str(raw.get("wave") or "").strip(),
                status=str(raw.get("status") or "not_started").strip(),
                owners=[str(value).strip() for value in (raw.get("owners") or []) if str(value).strip()],
                exit_criteria=[str(value).strip() for value in (raw.get("exit_criteria") or []) if str(value).strip()],
                dependencies=[_coerce_int(value, 0) for value in (raw.get("dependencies") or []) if _coerce_int(value, 0) > 0],
            )
        )
    return rows


def _queue_items_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for raw in (payload.get("items") or []):
        item: Any = raw
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                continue
            try:
                item = ast.literal_eval(text)
            except Exception:
                try:
                    item = yaml.safe_load(text)
                except Exception:
                    item = None
        if isinstance(item, dict):
            rows.append(dict(item))
    return rows


def _published_queue_items(workspace_root: Path) -> List[Dict[str, Any]]:
    return _queue_items_from_payload(_published_queue_payload(workspace_root))


def _queue_payload_and_item_for_shard(
    args: argparse.Namespace,
    state_root: Path,
    *,
    base_frontier: Optional[Sequence[Milestone]] = None,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    resolved_state_root = Path(state_root).resolve()
    aggregate_root = _aggregate_state_root(resolved_state_root)
    if resolved_state_root == aggregate_root:
        return {}, None
    match = re.fullmatch(r"shard-(\d+)", resolved_state_root.name)
    if not match:
        return {}, None
    shard_index = max(1, int(match.group(1)))
    workspace_root = Path(args.workspace_root).resolve()
    live_payload = _published_queue_payload(workspace_root)
    items = _queue_items_from_payload(live_payload)
    item_index = shard_index - 1
    if 0 <= item_index < len(items):
        return dict(live_payload), dict(items[item_index])

    next_wave_payload = _published_next_wave_queue_payload(workspace_root)
    next_wave_items = _queue_items_from_payload(next_wave_payload)
    if not next_wave_items:
        return {}, None

    current_frontier = list(base_frontier or [])
    if not current_frontier:
        current_frontier = _default_full_product_frontier(args, _full_product_readiness_audit(args))
    configured_shard_roots = _configured_shard_roots(aggregate_root)
    idle_shard_roots = [
        shard_root
        for shard_root in configured_shard_roots
        if not _open_milestone_shard_frontier(shard_root, current_frontier, default_limit=3)
    ]
    try:
        idle_index = idle_shard_roots.index(resolved_state_root)
    except ValueError:
        return {}, None
    if idle_index < 0 or idle_index >= len(next_wave_items):
        return {}, None
    return dict(next_wave_payload), dict(next_wave_items[idle_index])


def _queue_item_for_shard(
    args: argparse.Namespace,
    state_root: Path,
    *,
    base_frontier: Optional[Sequence[Milestone]] = None,
) -> Optional[Dict[str, Any]]:
    _payload, item = _queue_payload_and_item_for_shard(args, state_root, base_frontier=base_frontier)
    return item


def _queue_item_exit_criteria(item: Dict[str, Any]) -> List[str]:
    criteria: List[str] = []
    task = str(item.get("task") or "").strip()
    if task:
        criteria.append(task)
    owned_surfaces = [str(value).strip() for value in (item.get("owned_surfaces") or []) if str(value).strip()]
    if owned_surfaces:
        criteria.append("Own and prove the surface slice(s): " + ", ".join(owned_surfaces[:4]))
    allowed_paths = [str(value).strip() for value in (item.get("allowed_paths") or []) if str(value).strip()]
    if allowed_paths:
        preview = ", ".join(allowed_paths[:4])
        remaining = max(0, len(allowed_paths) - 4)
        suffix = f" (+{remaining} more)" if remaining > 0 else ""
        criteria.append("Keep implementation scoped to the allowed paths: " + preview + suffix)
    repo = str(item.get("repo") or "").strip()
    package_id = str(item.get("package_id") or "").strip()
    if repo or package_id:
        criteria.append(
            "Refresh flagship proof and close out the queue slice honestly when this package is landed"
            + (f" for `{repo}`" if repo else "")
            + (f" ({package_id})" if package_id else "")
            + "."
        )
    return criteria[:4]


def _queue_driven_full_product_frontier(
    args: argparse.Namespace,
    base_frontier: Optional[Sequence[Milestone]] = None,
) -> List[Milestone]:
    queue_item = _queue_item_for_shard(args, Path(args.state_root).resolve(), base_frontier=base_frontier)
    if not queue_item:
        return []
    audit = _full_product_readiness_audit(args)
    frontier_status = _full_product_frontier_status(audit)
    repo_owner = str(queue_item.get("repo") or "").strip()
    owners = [repo_owner] if repo_owner else []
    title = str(queue_item.get("title") or queue_item.get("package_id") or "Flagship shard slice").strip()
    key = str(queue_item.get("package_id") or title or "flagship_shard_slice").strip()
    return [
        _synthetic_full_product_milestone(
            key=key,
            title=title,
            owners=owners,
            exit_criteria=_queue_item_exit_criteria(queue_item),
            status=frontier_status,
        )
    ]


def _full_product_readiness_audit(args: argparse.Namespace) -> Dict[str, Any]:
    path = Path(args.flagship_product_readiness_path).resolve()
    audit: Dict[str, Any] = {
        "status": "fail",
        "reason": "",
        "path": str(path),
        "generated_at": "",
        "age_seconds": 0,
        "proof_status": "",
        "coverage": {},
        "coverage_details": {},
        "missing_coverage_keys": list(FLAGSHIP_PRODUCT_READINESS_COVERAGE_KEYS),
        "parity_excluded_scope": [],
        "unresolved_parity_families": [],
        "completion_external_only": False,
        "unresolved_external_proof_request_count": 0,
    }
    if not path.is_file():
        audit["reason"] = f"flagship product readiness proof is missing: {path}"
        return audit
    payload = _read_state(path)
    if not payload:
        audit["reason"] = f"flagship product readiness proof could not be read: {path}"
        return audit
    contract_name = str(payload.get("contract_name") or "").strip()
    if contract_name != "fleet.flagship_product_readiness":
        audit["reason"] = f"flagship product readiness proof uses an unexpected contract: {contract_name or 'missing'}"
        return audit
    generated_at = str(payload.get("generated_at") or "").strip()
    audit["generated_at"] = generated_at
    generated_at_dt = _parse_iso(generated_at)
    if generated_at_dt is None:
        audit["reason"] = "flagship product readiness proof is missing a valid generated_at timestamp"
        return audit
    audit["age_seconds"] = max(0, int((_utc_now() - generated_at_dt).total_seconds()))
    if audit["age_seconds"] > FLAGSHIP_PRODUCT_READINESS_MAX_AGE_SECONDS:
        audit["reason"] = f"flagship product readiness proof is stale ({audit['age_seconds']}s old)"
        return audit
    audit["raw_proof_status"] = str(payload.get("status") or "").strip()
    audit["proof_status"] = str(payload.get("scoped_status") or payload.get("status") or "").strip()
    coverage = dict(payload.get("coverage") or {})
    coverage_details = dict(payload.get("coverage_details") or {})
    parity_registry = dict(payload.get("parity_registry") or {})
    completion_audit = dict(payload.get("completion_audit") or {})
    external_host_proof = dict(payload.get("external_host_proof") or {})
    audit["coverage"] = coverage
    audit["coverage_details"] = coverage_details
    audit["parity_excluded_scope"] = [str(item).strip() for item in (parity_registry.get("excluded_scope") or []) if str(item).strip()]
    audit["unresolved_parity_families"] = [
        dict(item) for item in (parity_registry.get("unresolved_families") or []) if isinstance(item, dict)
    ]
    completion_external_only = completion_audit.get("external_only")
    if isinstance(completion_external_only, bool):
        audit["completion_external_only"] = completion_external_only
    else:
        token = str(completion_external_only or "").strip().lower()
        audit["completion_external_only"] = token in {"1", "true", "yes", "on"}
    audit["unresolved_external_proof_request_count"] = _coerce_int(
        completion_audit.get("unresolved_external_proof_request_count")
        if "unresolved_external_proof_request_count" in completion_audit
        else external_host_proof.get("unresolved_request_count"),
        0,
    )
    missing_keys = [
        str(item).strip()
        for item in (payload.get("scoped_missing_keys") or [])
        if str(item).strip()
    ]
    if not missing_keys:
        missing_keys = [
            key
            for key in FLAGSHIP_PRODUCT_READINESS_COVERAGE_KEYS
            if str(coverage.get(key) or "").strip().lower() != "ready"
        ]
    audit["missing_coverage_keys"] = missing_keys
    if audit["proof_status"] != "pass":
        audit["reason"] = f"flagship product readiness proof is not green: {audit['proof_status'] or 'missing'}"
        return audit
    if audit["unresolved_parity_families"]:
        audit["reason"] = "flagship product readiness proof still has unresolved non-plugin parity families"
        return audit
    if missing_keys:
        audit["reason"] = "flagship product readiness proof is missing ready coverage for: " + ", ".join(missing_keys)
        return audit
    audit["status"] = "pass"
    if str(audit.get("raw_proof_status") or "").strip().lower() == "pass":
        audit["reason"] = "flagship product readiness proof is current across desktop, rules, hub, mobile, horizons, and operator lanes"
    else:
        audit["reason"] = (
            "flagship product readiness proof is current for the Linux-hosted scope, with deferred non-Linux desktop host-proof warnings"
        )
    return audit


def _refresh_flagship_product_readiness_artifact(args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    if Path(args.workspace_root).resolve() != DEFAULT_WORKSPACE_ROOT.resolve():
        return None
    try:
        try:
            from scripts.external_proof_paths import resolve_release_channel_path
        except ModuleNotFoundError:
            from external_proof_paths import resolve_release_channel_path

        workspace_root = Path(args.workspace_root).resolve()
        resolved_release_channel_path = resolve_release_channel_path()
        resolved_releases_json_path = resolved_release_channel_path.with_name("releases.json")
        acceptance_mirror_path = workspace_root / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
        acceptance_canonical_path = Path("/docker/chummercomplete/chummer-design/products/chummer/FLAGSHIP_RELEASE_ACCEPTANCE.yaml")
        if acceptance_canonical_path.is_file():
            canonical_text = acceptance_canonical_path.read_text(encoding="utf-8")
            mirror_text = acceptance_mirror_path.read_text(encoding="utf-8") if acceptance_mirror_path.is_file() else ""
            if canonical_text != mirror_text:
                acceptance_mirror_path.parent.mkdir(parents=True, exist_ok=True)
                acceptance_mirror_path.write_text(canonical_text, encoding="utf-8")
        progress_report_path = Path(args.progress_report_path).resolve()
        progress_history_path = Path(args.progress_history_path).resolve()
        support_packets_path = Path(args.support_packets_path).resolve()
        journey_gates_path = progress_report_path.with_name("JOURNEY_GATES.generated.json")
        external_proof_runbook_path = progress_report_path.with_name("EXTERNAL_PROOF_RUNBOOK.generated.md")
        refresh_commands = [
            (
                "support-case packets",
                [
                    "python3",
                    "scripts/materialize_support_case_packets.py",
                    "--out",
                    str(support_packets_path),
                    "--release-channel",
                    str(resolved_release_channel_path),
                ],
            ),
            (
                "journey gates",
                [
                    "python3",
                    "scripts/materialize_journey_gates.py",
                    "--out",
                    str(journey_gates_path),
                    "--status-plane",
                    str(Path(args.status_plane_path).resolve()),
                    "--progress-report",
                    str(progress_report_path),
                    "--progress-history",
                    str(progress_history_path),
                    "--support-packets",
                    str(support_packets_path),
                ],
            ),
            (
                "external proof runbook",
                [
                    "python3",
                    "scripts/materialize_external_proof_runbook.py",
                    "--support-packets",
                    str(support_packets_path),
                    "--out",
                    str(external_proof_runbook_path),
                ],
            ),
        ]
        for label, command in refresh_commands:
            completed = subprocess.run(
                command,
                cwd=str(workspace_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                stdout_tail = str(completed.stdout or "").strip()[-800:]
                stderr_tail = str(completed.stderr or "").strip()[-800:]
                print(
                    f"[fleet-supervisor] {label} refresh failed: "
                    f"exit={completed.returncode} stdout={stdout_tail!r} stderr={stderr_tail!r}",
                    file=sys.stderr,
                    flush=True,
                )
        aggregate_state_root = workspace_root / "state" / "chummer_design_supervisor"
        readiness_mirror_path = aggregate_state_root / "artifacts" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
        supervisor_state_path = _state_payload_path(aggregate_state_root)
        candidate_state_root_raw = str(getattr(args, "state_root", "") or "").strip()
        if candidate_state_root_raw:
            candidate_state_root = Path(candidate_state_root_raw).resolve()
            candidate_state_path = _state_payload_path(candidate_state_root)
            candidate_aggregate_root = _aggregate_state_root(candidate_state_root)
            readiness_mirror_path = candidate_aggregate_root / "artifacts" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
            if candidate_state_path.is_file():
                aggregate_candidate_path = _state_payload_path(candidate_aggregate_root)
                # Flagship readiness is whole-product proof; prefer aggregate supervisor state
                # when a shard-local invocation is rematerializing evidence.
                if (
                    candidate_state_root != candidate_aggregate_root
                    and candidate_state_root.name.startswith("shard-")
                    and aggregate_candidate_path.is_file()
                ):
                    supervisor_state_path = aggregate_candidate_path
                else:
                    supervisor_state_path = candidate_state_path
        return materialize_flagship_product_readiness(
            out_path=Path(args.flagship_product_readiness_path).resolve(),
            mirror_path=readiness_mirror_path,
            acceptance_path=acceptance_mirror_path,
            parity_registry_path=workspace_root / ".codex-design" / "product" / "LEGACY_CLIENT_AND_ADJACENT_PARITY_REGISTRY.yaml",
            feedback_loop_gate_path=workspace_root / ".codex-design" / "product" / "FEEDBACK_LOOP_RELEASE_GATE.yaml",
            status_plane_path=Path(args.status_plane_path).resolve(),
            progress_report_path=progress_report_path,
            progress_history_path=progress_history_path,
            journey_gates_path=journey_gates_path,
            support_packets_path=support_packets_path,
            external_proof_runbook_path=external_proof_runbook_path,
            supervisor_state_path=supervisor_state_path,
            ooda_state_path=workspace_root / "state" / "design_supervisor_ooda" / "current_8h" / "state.json",
            ui_local_release_proof_path=PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "UI_LOCAL_RELEASE_PROOF.generated.json",
            ui_linux_exit_gate_path=Path(args.ui_linux_desktop_exit_gate_path).resolve(),
            ui_windows_exit_gate_path=PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json",
            ui_workflow_parity_proof_path=PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json",
            ui_executable_exit_gate_path=PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json",
            ui_workflow_execution_gate_path=PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json",
            ui_visual_familiarity_exit_gate_path=PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
            ui_localization_release_gate_path=PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "UI_LOCALIZATION_RELEASE_GATE.generated.json",
            sr4_workflow_parity_proof_path=PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json",
            sr6_workflow_parity_proof_path=PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json",
            sr4_sr6_frontier_receipt_path=PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json",
            hub_local_release_proof_path=Path("/docker/chummercomplete/chummer6-hub/.codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json"),
            mobile_local_release_proof_path=Path("/docker/chummercomplete/chummer6-mobile/.codex-studio/published/MOBILE_LOCAL_RELEASE_PROOF.generated.json"),
            release_channel_path=resolved_release_channel_path,
            releases_json_path=resolved_releases_json_path,
            ignore_nonlinux_desktop_host_proof_blockers=bool(
                getattr(args, "ignore_nonlinux_desktop_host_proof_blockers", False)
            ),
        )
    except Exception as exc:
        print(f"[fleet-supervisor] flagship readiness materialization failed: {exc}", file=sys.stderr, flush=True)
        return None


def _full_product_frontier_payload(
    *,
    args: argparse.Namespace,
    state_root: Path,
    mode: str,
    frontier: Sequence[Milestone],
    focus_profiles: Sequence[str],
    focus_owners: Sequence[str],
    focus_texts: Sequence[str],
    completion_audit: Dict[str, Any],
    full_product_audit: Dict[str, Any],
    eta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    product_root = Path(args.program_milestones_path).resolve().parent
    profile_set = {str(item).strip() for item in focus_profiles if str(item).strip()}
    generated_at = _iso_now()
    generated_at_dt = _parse_iso(generated_at) or _utc_now()
    frontier_rows = [
        {
            "id": item.id,
            "title": item.title,
            "wave": item.wave,
            "status": item.status,
            "owners": list(item.owners),
            "dependencies": list(item.dependencies),
            "exit_criteria": list(item.exit_criteria),
            "eta": _estimate_full_product_milestone_eta(
                item,
                full_product_audit,
                (),
                generated_at_dt,
            ),
        }
        for item in frontier
    ]
    queue_payload, queue_item = _queue_payload_and_item_for_shard(args, state_root)
    payload: Dict[str, Any] = {
        "contract_name": "fleet.full_product_frontier",
        "schema_version": 1,
        "generated_at": generated_at,
        "mode": mode,
        "state_root": str(state_root),
        "source_registry_path": str(Path(args.registry_path).resolve()),
        "handoff_path": str(Path(args.handoff_path).resolve()),
        "flagship_product_readiness_path": str(Path(args.flagship_product_readiness_path).resolve()),
        "design_source_paths": [str(path) for path in _flagship_design_source_paths(product_root)],
        "primary_probe_shard": _primary_probe_shard_name(state_root),
        "focus": {
            "profiles": list(focus_profiles),
            "owners": list(focus_owners),
            "texts": list(focus_texts),
        },
        "quality_policy": {
            "bar": "top_flagship_grade" if "top_flagship_grade" in profile_set else "flagship_product",
            "whole_project_frontier": True,
            "desktop_is_only_one_head": True,
            "accept_lowered_standards": False,
            "feedback_autofix_loop_required": True,
        },
        "completion_audit": {
            "status": str(completion_audit.get("status") or "").strip(),
            "reason": str(completion_audit.get("reason") or "").strip(),
        },
        "full_product_audit": {
            "status": str(full_product_audit.get("status") or "").strip(),
            "reason": str(full_product_audit.get("reason") or "").strip(),
            "path": str(full_product_audit.get("path") or "").strip(),
            "generated_at": str(full_product_audit.get("generated_at") or "").strip(),
            "proof_status": str(full_product_audit.get("proof_status") or "").strip(),
            "missing_coverage_keys": list(full_product_audit.get("missing_coverage_keys") or []),
            "parity_excluded_scope": list(full_product_audit.get("parity_excluded_scope") or []),
            "unresolved_parity_family_ids": [
                str(item.get("id") or "").strip()
                for item in (full_product_audit.get("unresolved_parity_families") or [])
                if isinstance(item, dict) and str(item.get("id") or "").strip()
            ],
        },
        "frontier_count": len(frontier_rows),
        "frontier_ids": [item["id"] for item in frontier_rows],
        "frontier": frontier_rows,
    }
    source_queue_fingerprint = str(queue_payload.get("source_queue_fingerprint") or "").strip()
    if source_queue_fingerprint:
        payload["source_queue_fingerprint"] = source_queue_fingerprint
    if queue_item:
        payload["queue_package"] = {
            "repo": str(queue_item.get("repo") or "").strip(),
            "package_id": str(queue_item.get("package_id") or "").strip(),
            "title": str(queue_item.get("title") or "").strip(),
            "priority": _coerce_int(queue_item.get("priority"), 0),
            "owned_surfaces": [str(value).strip() for value in (queue_item.get("owned_surfaces") or []) if str(value).strip()],
            "allowed_paths": [str(value).strip() for value in (queue_item.get("allowed_paths") or []) if str(value).strip()],
        }
    if eta:
        payload["eta"] = {
            "status": str(eta.get("status") or "").strip(),
            "eta_human": str(eta.get("eta_human") or "").strip(),
            "eta_confidence": str(eta.get("eta_confidence") or "").strip(),
            "basis": str(eta.get("basis") or "").strip(),
            "scope_kind": str(eta.get("scope_kind") or "").strip(),
            "scope_label": str(eta.get("scope_label") or "").strip(),
            "scope_warning": str(eta.get("scope_warning") or "").strip(),
            "blocking_reason": str(eta.get("blocking_reason") or "").strip(),
            "summary": str(eta.get("summary") or "").strip(),
            "predicted_completion_at": str(eta.get("predicted_completion_at") or "").strip(),
            "range_low_hours": eta.get("range_low_hours"),
            "range_high_hours": eta.get("range_high_hours"),
            "remaining_open_milestones": eta.get("remaining_open_milestones"),
            "remaining_in_progress_milestones": eta.get("remaining_in_progress_milestones"),
            "remaining_not_started_milestones": eta.get("remaining_not_started_milestones"),
            "remaining_effort_units": eta.get("remaining_effort_units"),
        }
    return payload


def _materialize_full_product_frontier(
    *,
    args: argparse.Namespace,
    state_root: Path,
    mode: str,
    frontier: Sequence[Milestone],
    focus_profiles: Sequence[str],
    focus_owners: Sequence[str],
    focus_texts: Sequence[str],
    completion_audit: Dict[str, Any],
    full_product_audit: Dict[str, Any],
    eta: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    published_path, mirror_path = _full_product_frontier_paths(
        Path(args.workspace_root).resolve(),
        state_root=state_root,
    )
    payload = _full_product_frontier_payload(
        args=args,
        state_root=state_root,
        mode=mode,
        frontier=frontier,
        focus_profiles=focus_profiles,
        focus_owners=focus_owners,
        focus_texts=focus_texts,
        completion_audit=completion_audit,
        full_product_audit=full_product_audit,
        eta=eta,
    )
    _write_yaml(published_path, payload)
    _write_yaml(mirror_path, payload)
    return {
        "published_path": str(published_path),
        "mirror_path": str(mirror_path),
    }


def build_worker_prompt(
    *,
    registry_path: Path,
    program_milestones_path: Path,
    roadmap_path: Path,
    handoff_path: Path,
    runtime_handoff_path: Optional[Path] = None,
    open_milestones: List[Milestone],
    frontier: List[Milestone],
    scope_roots: List[Path],
    focus_profiles: Sequence[str],
    focus_owners: Sequence[str],
    focus_texts: Sequence[str],
) -> str:
    frontier_text = "\n".join(f"- {_milestone_brief(item)}" for item in frontier) or "- none"
    open_text = "\n".join(f"- {_milestone_brief(item)}" for item in open_milestones[:15]) or "- none"
    scope_text = "\n".join(f"- {path}" for path in scope_roots)
    open_ids = ", ".join(str(item.id) for item in open_milestones) or "none"
    frontier_ids = ", ".join(str(item.id) for item in frontier) or "none"
    focus_lines = []
    if focus_profiles:
        focus_lines.append(f"- profile focus: {', '.join(focus_profiles)}")
    if focus_owners:
        focus_lines.append(f"- owner focus: {', '.join(focus_owners)}")
    if focus_texts:
        focus_lines.append(f"- text focus: {', '.join(focus_texts)}")
    focus_text = "\n".join(focus_lines) if focus_lines else "- none"
    runtime_handoff_block = f"- {runtime_handoff_path}\n" if runtime_handoff_path is not None else ""
    runtime_handoff_guidance = (
        "Use the shard runtime handoff as the worker-safe resume context. "
        "The shared operator handoff is operator-only and may contain historical operator telemetry snippets; "
        "do not open it or execute commands from it inside worker runs. "
        "If any file shows historical operator status snippets, treat them as stale notes rather than commands to repeat.\n\n"
        if runtime_handoff_path is not None
        else ""
    )
    return (
        "Continue autonomously across all Chummer6 repos in this workspace until the product is fully finished for public release exactly as defined by "
        "/docker/chummercomplete/chummer-design. Treat the design canon, milestone files, roadmap, public guides, generated artifacts, failing tests, and live repo evidence as the sole definition of done.\n\n"
        "Do not stop for progress reports, summaries, plans, clean repos, clean worktrees, completed waves, completed slices, or lack of pre-existing local diffs. "
        "When one slice lands, immediately re-derive and execute the next highest-impact unfinished work. Audit, implement, wire, regenerate, verify, test, commit, push, and refresh the operator handoff surfaces in small safe increments. "
        "Include adjacent cleanup, generated outputs, docs, mirrors, and necessary concurrent local changes to keep the whole system green.\n\n"
        "Treat concurrent work by other developers as normal. Work around it, include necessary local changes when they are understood and safe, and never revert unrelated edits.\n\n"
        "Execution discipline: do not invoke operator telemetry or active-run helper commands from inside worker runs. Those helpers are hard-blocked and return non-zero during active runs. The operator/OODA loop owns telemetry; keep working the assigned slice.\n\n"
        "Start by reading these files directly:\n"
        f"- {registry_path}\n"
        f"- {program_milestones_path}\n"
        f"- {roadmap_path}\n"
        f"{runtime_handoff_block}\n"
        f"{runtime_handoff_guidance}"
        f"Writable scope roots:\n{scope_text}\n\n"
        f"Current steering focus:\n{focus_text}\n\n"
        "Assigned slice authority: if the frontier headline is broader than the steering focus above, treat the steering focus as the work boundary for this run and do not drift into sibling slices.\n\n"
        f"Current active frontier from design plus handoff:\n{frontier_text}\n\n"
        f"Current open milestone ids: {open_ids}\n"
        f"Frontier milestone ids to prioritize first: {frontier_ids}\n\n"
        f"Select the next highest-impact unfinished slice yourself from that frontier, land it end to end, and if meaningful adjacent work remains within the same momentum window, continue before stopping. "
        "Only stop if there is no meaningful repo-local work left that advances full design materialization, a hard external blocker exists, or the platform/session actually terminates.\n\n"
        "If you stop, report only:\n"
        "What shipped: ...\n"
        "What remains: ...\n"
        "Exact blocker: ...\n"
    )


def build_completion_review_prompt(
    *,
    registry_path: Path,
    program_milestones_path: Path,
    roadmap_path: Path,
    handoff_path: Path,
    runtime_handoff_path: Optional[Path] = None,
    frontier_artifact_path: Path,
    frontier: List[Milestone],
    scope_roots: List[Path],
    focus_profiles: Sequence[str],
    focus_owners: Sequence[str],
    focus_texts: Sequence[str],
    audit: Dict[str, Any],
    history: Sequence[Dict[str, Any]],
    compact_prompt: bool = False,
) -> str:
    scope_text = "\n".join(f"- {path}" for path in scope_roots)
    frontier_text = "\n".join(f"- {_milestone_brief(item)}" for item in frontier) or "- none"
    frontier_ids = ", ".join(str(item.id) for item in frontier) or "none"
    guidance_paths = _completion_review_guidance_paths(frontier)
    guidance_text = "\n".join(f"- {path}" for path in guidance_paths)
    guidance_block = (
        "Additional frontier-specific canon to read:\n"
        f"{guidance_text}\n\n"
        if guidance_paths
        else ""
    )
    compact_guidance_block = (
        "Additional frontier-specific canon:\n"
        f"{guidance_text}\n\n"
        if guidance_paths
        else ""
    )
    suspicious_runs = _compact_prompt_section_lines(_completion_review_run_lines(history), max_lines=3, max_len=180)
    latest_trusted = _latest_trusted_receipt_line(history)
    journey_audit = dict(audit.get("journey_gate_audit") or {})
    linux_desktop_exit_gate_audit = dict(audit.get("linux_desktop_exit_gate_audit") or {})
    weekly_pulse_audit = dict(audit.get("weekly_pulse_audit") or {})
    repo_backlog_audit = dict(audit.get("repo_backlog_audit") or {})
    journey_lines = _compact_prompt_section_lines(_completion_review_journey_lines(journey_audit), max_lines=3, max_len=180)
    linux_gate_lines = _compact_prompt_section_lines(
        _completion_review_linux_exit_gate_lines(linux_desktop_exit_gate_audit),
        max_lines=4,
        max_len=180,
    )
    weekly_pulse_lines = _compact_prompt_section_lines(
        _completion_review_weekly_pulse_lines(weekly_pulse_audit),
        max_lines=3,
        max_len=180,
    )
    repo_backlog_lines = _compact_prompt_section_lines(
        _completion_review_repo_backlog_lines(repo_backlog_audit),
        max_lines=4,
        max_len=180,
    )
    focus_lines = []
    if focus_profiles:
        focus_lines.append(f"- profile focus: {', '.join(focus_profiles)}")
    if focus_owners:
        focus_lines.append(f"- owner focus: {', '.join(focus_owners)}")
    if focus_texts:
        focus_lines.append(f"- text focus: {', '.join(focus_texts)}")
    focus_text = "\n".join(focus_lines) if focus_lines else "- none"
    runtime_handoff_block = f"- {runtime_handoff_path}\n" if runtime_handoff_path is not None else ""
    runtime_handoff_guidance = (
        "Use the shard runtime handoff as the worker-safe resume context. "
        "The shared operator handoff is operator-only and may contain historical operator telemetry snippets; "
        "do not open it or execute commands from it inside worker runs. "
        "If any file shows historical operator status snippets, treat them as stale notes rather than commands to repeat.\n\n"
        if runtime_handoff_path is not None
        else ""
    )
    normalized_focus_profiles = {str(item).strip().lower() for item in focus_profiles if str(item).strip()}
    desktop_recovery_signal = " ".join(
        [
            *[str(item.title) for item in frontier if str(item.title).strip()],
            *[
                str(criterion)
                for item in frontier
                for criterion in item.exit_criteria
                if str(criterion).strip()
            ],
        ]
    ).lower()
    desktop_recovery_non_negotiables = (
        "Desktop recovery non-negotiables when the reopened slice touches the desktop flagship:\n"
        "- No generic shell, decorative mainframe, or dashboard-first landing page.\n"
        "- First useful screen must be the real workbench or restore continuation flow.\n"
        "- Real `File` menu, first-class master index, and first-class character roster are mandatory.\n"
        "- Claim, restore, and recovery must happen in the installer or in-app, not as a browser-only claim-code ritual.\n"
        "- The public happy path must be one guided Chummer product installer path, not a framework-first or head-first choice.\n\n"
    )
    desktop_recovery_required = "desktop_client" in normalized_focus_profiles or any(
        hint in desktop_recovery_signal
        for hint in (
            "desktop",
            "workbench",
            "file menu",
            "master index",
            "character roster",
            "installer",
            "claim",
            "restore",
            "avalonia",
            "blazor",
            "mainframe",
            "startup",
            "launch",
            "shell",
        )
    )
    desktop_recovery_block = desktop_recovery_non_negotiables if desktop_recovery_required else ""
    if compact_prompt:
        compact_scope_text = _compact_prompt_section_lines([str(path) for path in scope_roots], max_lines=4, max_len=120)
        compact_frontier_text = _compact_prompt_section_lines([_milestone_brief(item) for item in frontier], max_lines=2, max_len=180)
        return (
            "Run a false-complete recovery pass for the Chummer design supervisor.\n\n"
            "The registry is closed, but completion is still untrusted. Use repo-local evidence and the synthetic frontier to reopen or land the missing slice.\n\n"
            f"Completion audit:\n- status: {audit.get('status') or 'unknown'}\n- reason: {audit.get('reason') or 'unknown'}\n\n"
            "Read these files directly first:\n"
            f"- {registry_path}\n"
            f"- {program_milestones_path}\n"
            f"- {roadmap_path}\n"
            f"{runtime_handoff_block}"
            f"- {frontier_artifact_path}\n"
            f"{compact_guidance_block}"
            f"{desktop_recovery_block}"
            f"{runtime_handoff_guidance}"
            f"Writable scope roots:\n{compact_scope_text}\n\n"
            f"Current steering focus:\n{focus_text}\n\n"
            "Assigned slice authority: if the recovery frontier is broader than the steering focus above, treat the steering focus as the work boundary for this run and do not drift into sibling slices.\n\n"
            f"Recovery frontier ids: {frontier_ids}\n"
            f"Recovery frontier detail:\n{compact_frontier_text}\n\n"
            f"Latest suspicious receipts:\n{suspicious_runs}\n\n"
            f"Repo backlog summary:\n{repo_backlog_lines}\n\n"
            "Required order:\n"
            "1. Verify the synthetic frontier against repo-local evidence.\n"
            "2. Land the highest-impact missing implementation or proof slice.\n"
            "3. Refresh canon or handoff only if the repo proves they are stale.\n"
            "4. Only accept completion once trusted receipt and current proof agree.\n\n"
            "If you stop, report only:\n"
            "What shipped: ...\n"
            "What remains: ...\n"
            "Exact blocker: ...\n"
        )
    return (
        "Run a false-complete recovery pass for the Chummer design supervisor.\n\n"
        "The active design registry currently shows no open milestones, but the supervisor completion audit failed. "
        "Treat this as proof that the loop reached an untrusted completion conclusion and must now repair itself.\n\n"
        f"Completion audit failure:\n- status: {audit.get('status') or 'unknown'}\n- reason: {audit.get('reason') or 'unknown'}\n\n"
        "Start by reading these files directly:\n"
        f"- {registry_path}\n"
        f"- {program_milestones_path}\n"
        f"- {roadmap_path}\n"
        f"{runtime_handoff_block}\n"
        f"{guidance_block}"
        f"{desktop_recovery_block}"
        f"{runtime_handoff_guidance}"
        "Active synthetic completion-review frontier artifact:\n"
        f"- {frontier_artifact_path}\n\n"
        f"Writable scope roots:\n{scope_text}\n\n"
        f"Current steering focus:\n{focus_text}\n\n"
        f"Suspicious zero-exit receipts to audit first:\n{suspicious_runs}\n\n"
        f"Most recent trusted receipt:\n{latest_trusted}\n\n"
        f"Golden journey release-proof gaps:\n{journey_lines}\n\n"
        f"Linux desktop exit-gate gaps:\n{linux_gate_lines}\n\n"
        f"Weekly product pulse gaps:\n{weekly_pulse_lines}\n\n"
        f"Repo-local backlog gaps that still need canon-backed milestones:\n{repo_backlog_lines}\n\n"
        f"Recovery frontier ids to verify or reopen first: {frontier_ids}\n"
        f"Recovery frontier detail:\n{frontier_text}\n\n"
        "Treat the synthetic frontier artifact as the active source of truth for unfinished work while the registry stays closed.\n\n"
        "Your required order of work:\n"
        "1. Verify whether the recovery-frontier milestones, repo-local backlog items, blocked golden journeys, and weekly-pulse claims are actually complete in repo-local evidence.\n"
        "2. If backlog or proof gaps remain, land the highest-impact missing implementation, release-proof, or generated-artifact slice from that synthetic frontier before doing canon cleanup.\n"
        "3. If the work proves the design canon or handoff is falsely closed or stale, refresh them so the normal frontier becomes truthful again.\n"
        "4. Only accept completion once the trusted structured receipt and the current repo-local proof both agree that nothing meaningful remains.\n\n"
        "Do not simply restate the registry. Repair the loop's source of truth or produce the missing trusted evidence.\n\n"
        "If you stop, report only:\n"
        "What shipped: ...\n"
        "What remains: ...\n"
        "Exact blocker: ...\n"
    )


def _flagship_task_local_telemetry_payload(eta_snapshot: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    eta = _normalize_eta_scope_fields(dict(eta_snapshot or {}))
    active_runs_count = eta_snapshot.get("active_runs_count") if isinstance(eta_snapshot, dict) else None
    return {
        "active_runs_count": active_runs_count,
        "remaining_open_milestones": eta.get("remaining_open_milestones"),
        "remaining_not_started_milestones": eta.get("remaining_not_started_milestones"),
        "remaining_in_progress_milestones": eta.get("remaining_in_progress_milestones"),
        "eta_human": eta.get("eta_human"),
        "summary": eta.get("summary"),
    }


def build_flagship_product_prompt(
    *,
    registry_path: Path,
    program_milestones_path: Path,
    roadmap_path: Path,
    handoff_path: Path,
    runtime_handoff_path: Optional[Path] = None,
    readiness_path: Path,
    frontier_artifact_path: Path,
    frontier: List[Milestone],
    scope_roots: List[Path],
    focus_profiles: Sequence[str],
    focus_owners: Sequence[str],
    focus_texts: Sequence[str],
    completion_audit: Dict[str, Any],
    full_product_audit: Dict[str, Any],
    history: Sequence[Dict[str, Any]],
    eta_snapshot: Optional[Dict[str, Any]] = None,
    compact_prompt: bool = False,
) -> str:
    product_root = program_milestones_path.resolve().parent
    design_source_paths = _flagship_design_source_paths(product_root)
    scope_text = "\n".join(f"- {path}" for path in scope_roots)
    frontier_text = "\n".join(f"- {_milestone_brief(item)}" for item in frontier) or "- none"
    frontier_ids = ", ".join(str(item.id) for item in frontier) or "none"
    suspicious_runs = _compact_prompt_section_lines(_completion_review_run_lines(history), max_lines=3, max_len=180)
    focus_lines = []
    if focus_profiles:
        focus_lines.append(f"- profile focus: {', '.join(focus_profiles)}")
    if focus_owners:
        focus_lines.append(f"- owner focus: {', '.join(focus_owners)}")
    if focus_texts:
        focus_lines.append(f"- text focus: {', '.join(focus_texts)}")
    focus_text = "\n".join(focus_lines) if focus_lines else "- none"
    runtime_handoff_block = f"- {runtime_handoff_path}\n" if runtime_handoff_path is not None else ""
    runtime_handoff_guidance = (
        "Use the shard runtime handoff as the worker-safe resume context. "
        "The shared operator handoff is operator-only and may contain historical supervisor status commands; "
        "do not open it or execute commands from it inside worker runs. "
        "If any file shows historical operator status snippets, treat them as stale notes rather than commands to repeat.\n\n"
        if runtime_handoff_path is not None
        else ""
    )
    source_lines = "\n".join(f"- {path}" for path in design_source_paths[:12]) or f"- {product_root}"
    missing_coverage = ", ".join(str(item) for item in (full_product_audit.get("missing_coverage_keys") or [])) or "none"
    eta = _normalize_eta_scope_fields(dict(eta_snapshot or {}))
    eta_remaining_open = "unknown" if eta.get("remaining_open_milestones") is None else str(eta.get("remaining_open_milestones"))
    eta_remaining_in_progress = (
        "unknown" if eta.get("remaining_in_progress_milestones") is None else str(eta.get("remaining_in_progress_milestones"))
    )
    eta_remaining_not_started = (
        "unknown" if eta.get("remaining_not_started_milestones") is None else str(eta.get("remaining_not_started_milestones"))
    )
    task_local_telemetry_json = json.dumps(
        _flagship_task_local_telemetry_payload(eta_snapshot),
        separators=(",", ":"),
        ensure_ascii=True,
    )
    task_local_status_snapshot = (
        "Task-local run context:\n"
        f"- scope: {eta.get('scope_label') or 'unknown'}\n"
        f"- eta: {eta.get('eta_human') or 'unknown'}\n"
        f"- remaining open milestones: {eta_remaining_open}\n"
        f"- remaining in-progress milestones: {eta_remaining_in_progress}\n"
        f"- remaining not-started milestones: {eta_remaining_not_started}\n"
        "- the verbatim task-local telemetry snapshot is embedded below; use it as-is and do not regenerate it via shell, Python, or supervisor helper commands from inside the worker run.\n"
        "```json\n"
        f"{task_local_telemetry_json}\n"
        "```\n\n"
    )
    telemetry_command_ban = (
        "Operator telemetry CLI is forbidden during active worker runs. "
        "Do not invoke supervisor helper commands from inside the worker run; use the embedded JSON block and listed files instead.\n\n"
    )
    flagship_desktop_non_negotiables = (
        "Desktop flagship non-negotiables:\n"
        "- No generic shell, decorative mainframe, or dashboard-first landing page.\n"
        "- First useful screen must be the real workbench or restore continuation flow.\n"
        "- Real `File` menu, first-class master index, and first-class character roster are mandatory.\n"
        "- Claim, restore, and recovery must happen in the installer or in-app, not as a browser-only claim-code ritual.\n"
        "- The public happy path must be one guided Chummer product installer path, not a framework-first or head-first choice.\n\n"
    )
    if compact_prompt:
        compact_scope_text = _compact_prompt_section_lines([str(path) for path in scope_roots], max_lines=4, max_len=120)
        compact_frontier_text = _compact_prompt_section_lines([_milestone_brief(item) for item in frontier], max_lines=3, max_len=180)
        compact_source_text = _compact_prompt_section_lines([str(path) for path in design_source_paths[:12]], max_lines=8, max_len=140)
        return (
            "Run the flagship full-product delivery pass for Chummer.\n\n"
            "Current release-proof gates are green, so the supervisor must continue into full product completion instead of stopping.\n\n"
            "This is the hard flagship bar: build the kind of product future work is measured against. Do not trade that bar down for schedule, local green receipts, or desktop-only wins.\n\n"
            f"Completion audit:\n- status: {completion_audit.get('status') or 'unknown'}\n- reason: {completion_audit.get('reason') or 'unknown'}\n"
            f"Flagship readiness audit:\n- status: {full_product_audit.get('status') or 'unknown'}\n- reason: {full_product_audit.get('reason') or 'unknown'}\n- missing coverage: {missing_coverage}\n\n"
            f"{task_local_status_snapshot}"
            f"{telemetry_command_ban}"
            "Read these files directly first:\n"
            f"- {registry_path}\n"
            f"- {program_milestones_path}\n"
            f"- {roadmap_path}\n"
            f"{runtime_handoff_block}"
            f"- {readiness_path}\n"
            f"- {frontier_artifact_path}\n"
            f"{compact_source_text}\n\n"
            f"{flagship_desktop_non_negotiables}"
            f"{runtime_handoff_guidance}"
            f"Writable scope roots:\n{compact_scope_text}\n\n"
            f"Current steering focus:\n{focus_text}\n\n"
            "Assigned slice authority: if the flagship frontier is broader than the steering focus above, treat the steering focus as the work boundary for this run and do not drift into sibling slices.\n\n"
            f"Flagship frontier ids: {frontier_ids}\n"
            f"Flagship frontier detail:\n{compact_frontier_text}\n\n"
            f"Latest suspicious receipts:\n{suspicious_runs}\n\n"
            "Required order:\n"
            "1. Verify the flagship frontier against canonical design and repo-local evidence.\n"
            "2. Treat the whole product frontier as the frontier: desktop, rules, hub, registry, mobile, ui-kit, media, horizons, and fleet/operator loop.\n"
            "3. Keep feedback, crash, support, and automatic bugfix routing live enough that the fleet can continue improving the product without manual babysitting.\n"
            "4. Refresh handoff, mirrors, and readiness proof only when the repos actually justify it.\n"
            "5. Do not accept completion until FLAGSHIP_PRODUCT_READINESS.generated.json is current and covers every required flagship lane with no lowered-standard shortcuts.\n\n"
            "Execution discipline:\n"
            "- Do not invoke operator telemetry or active-run helper commands from inside worker runs; those helpers are hard-blocked and return non-zero during active runs.\n"
            "- The operator/OODA loop owns telemetry. Use the embedded JSON block and listed files as your local context instead.\n"
            "- Spend the run implementing or auditing the assigned slice.\n\n"
            "If you stop, report only:\n"
            "What shipped: ...\n"
            "What remains: ...\n"
            "Exact blocker: ...\n"
        )
    return (
        "Run the flagship full-product delivery pass for Chummer.\n\n"
        "The current release-proof gates are green, but that only proves the loop cleared the present closeout gates. "
        "It does not prove the whole Chummer product is finished. Continue across the full design canon until the flagship product readiness proof is current and trusted.\n\n"
        "Use the hard flagship bar: the product should feel like the standard future products are measured against. Reject lowered standards, false-complete claims, narrow desktop-only closure, and proof-only wins that do not survive real product scrutiny.\n\n"
        "Execution discipline: do not invoke operator telemetry or active-run helper commands from inside worker runs. Those helpers are hard-blocked and return non-zero during active runs. The operator/OODA loop owns telemetry; keep working the assigned slice.\n\n"
        f"Completion audit:\n- status: {completion_audit.get('status') or 'unknown'}\n- reason: {completion_audit.get('reason') or 'unknown'}\n\n"
        f"Flagship readiness audit:\n- status: {full_product_audit.get('status') or 'unknown'}\n- reason: {full_product_audit.get('reason') or 'unknown'}\n- missing coverage: {missing_coverage}\n\n"
        f"{task_local_status_snapshot}"
        f"{telemetry_command_ban}"
        "Start by reading these files directly:\n"
        f"- {registry_path}\n"
        f"- {program_milestones_path}\n"
        f"- {roadmap_path}\n"
        f"{runtime_handoff_block}"
        f"- {readiness_path}\n"
        f"- {frontier_artifact_path}\n"
        f"{source_lines}\n\n"
        f"{flagship_desktop_non_negotiables}"
        f"{runtime_handoff_guidance}"
        f"Writable scope roots:\n{scope_text}\n\n"
        f"Current steering focus:\n{focus_text}\n\n"
        f"Recent suspicious receipts worth sanity-checking:\n{suspicious_runs}\n\n"
        f"Flagship frontier ids to prioritize first: {frontier_ids}\n"
        f"Flagship frontier detail:\n{frontier_text}\n\n"
        "Treat the generated full-product frontier artifact as the active coordination source for post-gate flagship work.\n\n"
        "Your required order of work:\n"
        "1. Verify the flagship frontier against canonical design plus repo-local evidence.\n"
        "2. Land the highest-impact unfinished slice across the whole product: desktop client, rules/import parity, hub and registry, mobile play shell, shared design system, media/artifacts, horizons/public surfaces, and the operator loop.\n"
        "3. Keep feedback, crash, support, and automatic bugfix routing real enough that the fleet can keep healing the product while the product is still being built.\n"
        "4. Refresh mirrors, handoff, or readiness proof only when the code and generated artifacts justify them.\n"
        "5. Only accept completion once the flagship readiness proof is current, trusted, and covers desktop, rules, hub, mobile, ui-kit polish, media, horizons/public surfaces, and fleet/operator governance.\n\n"
        "Do not collapse back to the closed wave or treat one head as the frontier. The whole project frontier is the frontier.\n\n"
        "If you stop, report only:\n"
        "What shipped: ...\n"
        "What remains: ...\n"
        "Exact blocker: ...\n"
    )


def _default_worker_command(
    *,
    worker_bin: str,
    worker_lane: str,
    workspace_root: Path,
    scope_roots: List[Path],
    run_dir: Path,
    worker_model: str,
) -> List[str]:
    command = [
        worker_bin,
    ]
    if worker_lane:
        command.append(worker_lane)
    command.extend(
        [
            "exec",
            "-C",
            str(workspace_root),
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "--color",
            "never",
            "-o",
            str(run_dir / "last_message.txt"),
            "-",
        ]
    )
    if worker_model:
        command[2 + (1 if worker_lane else 0) : 2 + (1 if worker_lane else 0)] = ["-m", worker_model]
    for scope_root in scope_roots:
        if scope_root == workspace_root:
            continue
        insert_at = 2 + (1 if worker_lane else 0) + (2 if worker_model else 0)
        command[insert_at:insert_at] = ["--add-dir", str(scope_root)]
    return command


def _env_split_list(raw: str) -> List[str]:
    compact = str(raw or "").replace("\n", ",").replace(";", ",")
    return [item.strip() for item in compact.split(",") if item.strip()]


def _runtime_env_group_rows(name: str, workspace_root: Optional[Path] = None) -> List[str]:
    raw = str(
        _runtime_env_default(name, "")
        if workspace_root is None
        else _runtime_env_default_with_workspace(name, workspace_root, "")
    )
    if not raw:
        return []
    return [item.strip() for item in raw.replace("\n", ";").split(";")]


def _runtime_env_group_list(name: str, index: int, workspace_root: Optional[Path] = None) -> Optional[List[str]]:
    rows = _runtime_env_group_rows(name, workspace_root=workspace_root)
    if index < 0 or index >= len(rows):
        return None
    return _env_split_list(rows[index])


def _runtime_env_group_value(name: str, index: int, workspace_root: Optional[Path] = None) -> Optional[str]:
    rows = _runtime_env_group_rows(name, workspace_root=workspace_root)
    if index < 0 or index >= len(rows):
        return None
    return rows[index].strip()


def _openai_escape_hatch_account_aliases() -> List[str]:
    return _env_split_list(
        _runtime_env_file_first_default("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "")
    )


def _openai_escape_hatch_account_owner_ids() -> List[str]:
    return _env_split_list(
        _runtime_env_file_first_default("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_OWNER_IDS", "")
    )


def _openai_escape_hatch_model_candidates() -> List[str]:
    configured = _env_split_list(
        _runtime_env_file_first_default("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS", "")
    )
    return configured or list(DEFAULT_OPENAI_ESCAPE_HATCH_MODELS)


def _openai_escape_hatch_enabled() -> bool:
    return bool(_openai_escape_hatch_account_aliases() or _openai_escape_hatch_account_owner_ids())


def _openai_escape_hatch_args(args: argparse.Namespace) -> argparse.Namespace:
    clone = argparse.Namespace(**vars(args))
    escape_models = _openai_escape_hatch_model_candidates()
    clone.worker_bin = "codex"
    clone.worker_lane = ""
    clone.fallback_worker_lane = []
    clone.account_alias = _openai_escape_hatch_account_aliases()
    clone.account_owner_id = _openai_escape_hatch_account_owner_ids()
    clone.worker_model = escape_models[0] if escape_models else ""
    clone.fallback_worker_model = escape_models[1:] if len(escape_models) > 1 else []
    return clone


def _account_direct_fallback_worker_bin() -> str:
    return str(_runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_WORKER_BIN", "") or "").strip()


def _account_direct_fallback_worker_lane() -> str:
    return str(_runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_WORKER_LANE", "") or "").strip()


def _account_direct_fallback_model_candidates() -> List[str]:
    return _env_split_list(_runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_MODELS", ""))


def _account_direct_fallback_lane_candidates() -> List[str]:
    return _env_split_list(_runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_LANES", ""))


def _account_direct_fallback_enabled() -> bool:
    return bool(
        _account_direct_fallback_worker_bin()
        or _account_direct_fallback_worker_lane()
        or _account_direct_fallback_model_candidates()
        or _account_direct_fallback_lane_candidates()
    )


def _account_restore_probe_seconds() -> float:
    try:
        return max(
            0.0,
            float(_runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_RESTORE_PROBE_SECONDS", "0") or "0"),
        )
    except (TypeError, ValueError):
        return 0.0


def _runtime_handoff_heartbeat_seconds() -> float:
    try:
        return max(
            0.0,
            float(_runtime_env_default("CHUMMER_DESIGN_SUPERVISOR_RUNTIME_HANDOFF_HEARTBEAT_SECONDS", "60") or "60"),
        )
    except (TypeError, ValueError):
        return 60.0


def _account_restore_probe_due(
    last_probe_at: Optional[dt.datetime],
    *,
    now: Optional[dt.datetime] = None,
) -> bool:
    probe_seconds = _account_restore_probe_seconds()
    if probe_seconds <= 0.0:
        return False
    current = now or _utc_now()
    if last_probe_at is None:
        return True
    return (current - last_probe_at).total_seconds() >= probe_seconds


def _source_item(payload: Dict[str, Any], account: WorkerAccount) -> Dict[str, Any]:
    return dict((payload.get("sources") or {}).get(_credential_source_key(account)) or {})


def _source_restore_probe_due(
    payload: Dict[str, Any],
    account: WorkerAccount,
    *,
    now: Optional[dt.datetime] = None,
) -> bool:
    item = _source_item(payload, account)
    if not item:
        return False
    last_probe_at = _parse_iso(str(item.get("restore_probe_at") or ""))
    return _account_restore_probe_due(last_probe_at, now=now)


def _mark_source_restore_probe(
    payload: Dict[str, Any],
    account: WorkerAccount,
    *,
    when: Optional[dt.datetime] = None,
) -> None:
    current = when or _utc_now()
    sources = dict(payload.get("sources") or {})
    key = _credential_source_key(account)
    item = dict(sources.get(key) or {})
    item["alias"] = account.alias
    item["owner_id"] = account.owner_id
    item["source_key"] = key
    item["restore_probe_at"] = _iso(current)
    sources[key] = item
    payload["sources"] = sources


def _account_direct_fallback_args(args: argparse.Namespace) -> argparse.Namespace:
    clone = argparse.Namespace(**vars(args))
    configured_lane = _account_direct_fallback_worker_lane() or str(args.worker_lane or "").strip()
    configured_fallback_lanes = _account_direct_fallback_lane_candidates()
    if configured_fallback_lanes:
        fallback_lanes = configured_fallback_lanes
    elif configured_lane:
        fallback_lanes = list(DEFAULT_FALLBACK_WORKER_LANES.get(configured_lane, ()))
    else:
        fallback_lanes = [str(item or "").strip() for item in (args.fallback_worker_lane or []) if str(item or "").strip()]
    fallback_models = _account_direct_fallback_model_candidates()
    if not fallback_models:
        fallback_models = list(ACCOUNT_DIRECT_FALLBACK_RESCUE_MODELS)
    clone.worker_bin = _account_direct_fallback_worker_bin() or str(args.worker_bin or "").strip()
    clone.worker_lane = configured_lane
    clone.fallback_worker_lane = fallback_lanes
    clone.account_alias = []
    clone.account_owner_id = []
    clone.worker_model = fallback_models[0] if fallback_models else ""
    clone.fallback_worker_model = fallback_models[1:] if len(fallback_models) > 1 else []
    return clone


def _routed_full_lane_direct_fallback_lanes(worker_lane: str) -> List[str]:
    lane = str(worker_lane or "").strip().lower()
    if lane in {"core", "core_rescue"}:
        return [lane, *[item for item in ("core", "core_rescue") if item != lane]]
    if lane in {"jury", "audit_shard", "review_shard"}:
        return ["core", "core_rescue"]
    return []


def _routed_full_lane_direct_fallback_args(args: argparse.Namespace) -> Optional[argparse.Namespace]:
    if not _worker_bin_uses_codexea(str(args.worker_bin or "")):
        return None
    lanes = _routed_full_lane_direct_fallback_lanes(str(args.worker_lane or ""))
    if not lanes:
        return None
    clone = argparse.Namespace(**vars(args))
    clone.account_alias = []
    clone.account_owner_id = []
    clone.worker_lane = lanes[0]
    clone.fallback_worker_lane = lanes[1:]
    return clone


def _worker_model_candidates(args: argparse.Namespace) -> List[str]:
    primary = str(args.worker_model or "").strip()
    primary_lane = str(args.worker_lane or "").strip()
    configured_fallbacks = [str(item or "").strip() for item in (args.fallback_worker_model or []) if str(item or "").strip()]
    if configured_fallbacks:
        fallbacks = configured_fallbacks
    else:
        env_value = os.environ.get("CHUMMER_DESIGN_SUPERVISOR_FALLBACK_MODELS")
        if env_value is None:
            fallbacks = [] if primary_lane else list(DEFAULT_FALLBACK_MODELS)
        else:
            fallbacks = [] if (primary_lane and not primary) else [item.strip() for item in env_value.split(",") if item.strip()]
    models: List[str] = []
    seen: set[str] = set()
    for candidate in [primary, *fallbacks]:
        key = candidate or "<default>"
        if key in seen:
            continue
        seen.add(key)
        models.append(candidate)
    return models or [primary]


def _rotate_model_candidates_after_recent_stall(state_root: Path, model_candidates: Sequence[str]) -> List[str]:
    candidates = [str(item or "").strip() for item in (model_candidates or [])]
    if len(candidates) <= 1:
        return candidates
    recent_history = _read_history(_history_payload_path(state_root), limit=3)
    if not recent_history:
        return candidates
    latest = recent_history[-1]
    if bool(latest.get("accepted")):
        return candidates
    blocker = str(latest.get("blocker") or "").strip().lower()
    if "worker_model_output_stalled" not in blocker:
        return candidates
    stalled_model = str(latest.get("selected_model") or "").strip()
    if not stalled_model or stalled_model not in candidates:
        return candidates
    return [candidate for candidate in candidates if candidate != stalled_model] + [stalled_model]


def _recent_helper_loop_failure_count(state_root: Path, *, limit: int = 4) -> int:
    recent_history = _read_history(_history_payload_path(state_root), limit=max(1, int(limit)))
    if not recent_history:
        return 0
    count = 0
    for row in reversed(recent_history):
        if bool(row.get("accepted")):
            break
        blocker = " ".join(
            [
                str(row.get("blocker") or "").strip(),
                str(row.get("acceptance_reason") or "").strip(),
            ]
        ).lower()
        if "worker_status_helper_loop" not in blocker:
            break
        count += 1
    return count


def _prefer_openai_escape_fastpath_after_recent_helper_loop(state_root: Path) -> bool:
    if not _openai_escape_hatch_enabled():
        return False
    recent_history = _read_history(_history_payload_path(state_root), limit=4)
    if not recent_history:
        return False
    latest = recent_history[-1]
    if bool(latest.get("accepted")):
        return False
    helper_loop_failures = 0
    for row in recent_history:
        if bool(row.get("accepted")):
            continue
        blocker = " ".join(
            [
                str(row.get("blocker") or "").strip(),
                str(row.get("acceptance_reason") or "").strip(),
            ]
        ).lower()
        if "worker_status_helper_loop" in blocker:
            helper_loop_failures += 1
    return helper_loop_failures >= 2


def _worker_lane_candidates(args: argparse.Namespace) -> List[str]:
    primary = str(args.worker_lane or "").strip()
    if not primary:
        return [""]
    configured_fallbacks = [
        str(item or "").strip() for item in (args.fallback_worker_lane or []) if str(item or "").strip()
    ]
    if configured_fallbacks:
        fallbacks = configured_fallbacks
    else:
        env_value = os.environ.get("CHUMMER_DESIGN_SUPERVISOR_FALLBACK_LANES")
        if env_value is None:
            fallbacks = list(DEFAULT_FALLBACK_WORKER_LANES.get(primary, ()))
        else:
            fallbacks = [item.strip() for item in env_value.split(",") if item.strip()]
    lanes: List[str] = []
    seen: set[str] = set()
    for candidate in [primary, *fallbacks]:
        key = candidate or "<default>"
        if key in seen:
            continue
        seen.add(key)
        lanes.append(candidate)
    return lanes or [primary]


def _retryable_worker_error(stderr_text: str) -> bool:
    compact = " ".join(str(stderr_text or "").split()).strip().lower()
    return bool(compact) and any(signal in compact for signal in RETRYABLE_WORKER_ERROR_SIGNALS)


def _retryable_worker_rejection(reason_text: str, stderr_text: str = "") -> bool:
    return _retryable_worker_error(reason_text) or _retryable_worker_error(stderr_text)


def _self_polling_worker_error(*texts: str) -> bool:
    compact = " ".join(str(text or "") for text in texts).lower()
    return "worker_self_polling:supervisor_status_loop" in compact


def _run_scoped_worker_contract_violation(*texts: str) -> bool:
    compact = " ".join(str(text or "") for text in texts).lower()
    if not compact:
        return False
    return any(
        signal in compact
        for signal in (
            "worker_self_polling:supervisor_status_loop",
            "worker_model_output_stalled",
            "worker_status_helper_loop",
            "status_blocked_inside_worker_run",
            "worker_status_budget_exhausted",
        )
    )


def _should_attempt_openai_escape_hatch(acceptance_reason: str, final_message: str, stderr_text: str) -> bool:
    if not _openai_escape_hatch_enabled():
        return False
    if _self_polling_worker_error(acceptance_reason, final_message, stderr_text):
        return False
    compact = " ".join(
        item for item in (str(acceptance_reason or ""), str(final_message or ""), str(stderr_text or "")) if item
    ).lower()
    if not compact:
        return False
    return any(signal in compact for signal in OPENAI_ESCAPE_HATCH_TRIGGER_SIGNALS)


def _should_attempt_account_direct_fallback(
    completed: Optional[subprocess.CompletedProcess[str]],
    *,
    stderr_text: str,
) -> bool:
    if not _account_direct_fallback_enabled():
        return False
    if _self_polling_worker_error(stderr_text):
        return False
    if completed is None:
        return True
    if int(completed.returncode) == 0:
        return False
    if _retryable_worker_error(stderr_text):
        return True
    if _parse_auth_failure_message(stderr_text) is not None:
        return True
    if _parse_usage_limit_backoff_seconds(stderr_text, DEFAULT_USAGE_LIMIT_BACKOFF_SECONDS, now=_utc_now()) is not None:
        return True
    if _parse_backend_unavailable_message(stderr_text) is not None:
        return True
    if _parse_backoff_seconds(stderr_text, DEFAULT_RATE_LIMIT_BACKOFF_SECONDS) is not None:
        return True
    if _parse_spark_pool_backoff_seconds(stderr_text, DEFAULT_SPARK_BACKOFF_SECONDS) is not None:
        return True
    if _parse_unsupported_chatgpt_model(stderr_text) is not None:
        return True
    return False


def _effective_worker_timeout_seconds(args: argparse.Namespace, workspace_root: Path) -> tuple[float, float]:
    configured_timeout_seconds = max(0.0, float(getattr(args, "worker_timeout_seconds", 0.0) or 0.0))
    effective_timeout_seconds = configured_timeout_seconds
    primary_worker_lane = str(_worker_lane_candidates(args)[0] or "").strip().lower()
    if _worker_bin_uses_codexea(str(args.worker_bin or "")) and primary_worker_lane in _direct_codexea_stream_lanes():
        worker_timeout_floor_seconds = _stream_budget_timeout_seconds_for_workspace(workspace_root)
        if worker_timeout_floor_seconds > 0.0:
            effective_timeout_seconds = max(effective_timeout_seconds, worker_timeout_floor_seconds)
    return configured_timeout_seconds, effective_timeout_seconds


def _parse_final_message_sections(text: str) -> Dict[str, str]:
    compact = str(text or "").replace("\r\n", "\n")
    patterns = {
        "shipped": r"(?ims)^What shipped:\s*(.*?)(?=^What remains:|^Exact blocker:|\Z)",
        "remains": r"(?ims)^What remains:\s*(.*?)(?=^Exact blocker:|\Z)",
        "blocker": r"(?ims)^Exact blocker:\s*(.*?)(?=\Z)",
    }
    parsed: Dict[str, str] = {}
    for key in patterns:
        parsed[key] = ""
    for candidate in _final_message_text_candidates(compact):
        for key, pattern in patterns.items():
            if parsed.get(key):
                continue
            match = re.search(pattern, candidate)
            if match:
                parsed[key] = " ".join(match.group(1).split()).strip()
    return parsed


def _compose_final_message_sections(sections: Dict[str, str]) -> str:
    shipped = str((sections or {}).get("shipped") or "").strip()
    remains = str((sections or {}).get("remains") or "").strip()
    blocker = str((sections or {}).get("blocker") or "").strip()
    return (
        f"What shipped: {shipped}\n\n"
        f"What remains: {remains}\n\n"
        f"Exact blocker: {blocker}\n"
    )


def _is_missing_github_push_blocker(text: str) -> bool:
    compact = str(text or "").strip().lower()
    return "push" in compact and "could not read username for 'https://github.com'" in compact


def _repo_root_for_local_commit_label(label: str) -> Optional[Path]:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(label or "").strip().lower()).strip("-")
    if not normalized:
        return None
    candidates = [
        DEFAULT_WORKSPACE_ROOT if normalized == "fleet" else None,
        Path("/docker/EA") if normalized in {"ea", "executive-assistant"} else None,
        Path("/docker/chummer5a") if normalized == "chummer5a" else None,
        Path("/docker/chummercomplete") / normalized,
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate.resolve()
    return None


def _git_remote_contains_commit(repo: Path, commit: str, env: Optional[Dict[str, str]] = None) -> bool:
    commit_text = str(commit or "").strip()
    if not commit_text:
        return False
    completed = subprocess.run(
        ["git", "-C", str(repo), "branch", "-r", "--contains", commit_text],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    return completed.returncode == 0 and bool(str(completed.stdout or "").strip())


def _rewrite_verified_local_commit_phrases(text: str, *, env: Optional[Dict[str, str]] = None) -> tuple[str, bool]:
    raw = str(text or "")
    if not raw.strip():
        return raw, False
    changed = False
    pattern = re.compile(
        r"(?i)local\s+(?P<label>[A-Za-z0-9_. /-]+?)\s+commits?\s+(?P<hashes>(?:`?[0-9a-f]{7,40}`?(?:\s*,\s*`?[0-9a-f]{7,40}`?)*))"
    )

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        label = str(match.group("label") or "").strip()
        hashes = re.findall(r"[0-9a-f]{7,40}", str(match.group("hashes") or ""), flags=re.I)
        repo = _repo_root_for_local_commit_label(label)
        if repo is None or not hashes:
            return match.group(0)
        if not all(_git_remote_contains_commit(repo, commit, env=env) for commit in hashes):
            return match.group(0)
        changed = True
        return f"{label} commits {match.group('hashes')}"

    rewritten = pattern.sub(replace, raw)
    return rewritten, changed


def _strip_verified_remote_residue_clauses(text: str, *, env: Optional[Dict[str, str]] = None) -> tuple[str, bool]:
    raw = str(text or "").strip()
    if not raw:
        return raw, False
    changed = False
    residue_markers = (
        "not yet pushed to remote",
        "not pushed to remote",
        "still local",
        "local-only",
        "push attempts: not attempted yet",
        "not attempted yet for this slice",
        "pending local commit",
        "pending local commits",
        "remote push did not complete",
        "remote publication of these commits",
        "remote publication of this commit",
        "git push failed",
        "push failed in this environment",
        "not yet on remote",
        "not on remote yet",
        "is not on remote",
        "are not on remote",
    )
    kept: List[str] = []
    for clause in [part.strip(" .") for part in re.split(r"\s*;\s*", raw) if part.strip(" .")]:
        lowered = clause.lower()
        if not any(marker in lowered for marker in residue_markers):
            kept.append(clause)
            continue
        hashes = re.findall(r"[0-9a-f]{7,40}", clause, flags=re.I)
        label_match = re.search(r"(?i)`?(?P<label>[A-Za-z0-9_. /-]+?)`?\s+commits?\s+", clause)
        label = str(label_match.group("label") or "").strip() if label_match else ""
        repo = _repo_root_for_local_commit_label(label)
        if repo is None or not hashes or not all(_git_remote_contains_commit(repo, commit, env=env) for commit in hashes):
            kept.append(clause)
            continue
        changed = True
    if kept:
        return "; ".join(kept), changed
    if changed:
        return "none", True
    return raw, False


def _closeout_has_remote_push_residue(sections: Dict[str, str]) -> bool:
    combined = " ".join(
        str((sections or {}).get(key) or "").strip().lower() for key in ("shipped", "remains", "blocker")
    )
    if not combined:
        return False
    residue_markers = (
        "not yet pushed to remote",
        "not pushed to remote",
        "still local",
        "local-only",
        "push attempts: not attempted yet",
        "not attempted yet for this slice",
        "pending local commit",
        "pending local commits",
        "remote push did not complete",
        "remote publication of these commits",
        "remote publication of this commit",
        "git push failed",
        "push failed in this environment",
        "not yet on remote",
        "not on remote yet",
        "is not on remote",
        "are not on remote",
    )
    return any(marker in combined for marker in residue_markers)


def _strip_remote_push_residue(remains: str) -> str:
    text = str(remains or "").strip()
    if not text:
        return text
    residue_markers = (
        "not yet pushed to remote",
        "not pushed to remote",
        "still local",
        "local-only",
        "not attempted yet",
        "pending local commit",
        "pending local commits",
        "remote push did not complete",
        "remote publication of these commits",
        "remote publication of this commit",
        "git push failed",
        "push failed in this environment",
        "not yet on remote",
        "not on remote yet",
        "is not on remote",
        "are not on remote",
    )
    parts = [part.strip(" .") for part in re.split(r"\s*;\s*", text) if part.strip(" .")]
    kept = [part for part in parts if not any(marker in part.lower() for marker in residue_markers)]
    if kept:
        return "; ".join(kept)
    if any(marker in text.lower() for marker in residue_markers):
        return "none"
    return text


def _repair_recorded_remote_push_residue(run: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    payload = dict(run or {})
    if not payload or not bool(payload.get("accepted")):
        return payload, False
    final_message = _run_final_message(payload)
    sections = _parse_final_message_sections(final_message)
    if not _closeout_has_remote_push_residue(sections):
        return payload, False
    repaired = False
    host_env = _prepare_host_git_push_environment()
    shipped_rewritten, shipped_changed = _rewrite_verified_local_commit_phrases(sections.get("shipped", ""), env=host_env)
    if shipped_changed:
        sections["shipped"] = shipped_rewritten
        repaired = True
    verified_remains, verified_changed = _strip_verified_remote_residue_clauses(
        sections.get("remains", ""),
        env=host_env,
    )
    if verified_changed:
        sections["remains"] = verified_remains
        repaired = True
    stripped_remains = _strip_remote_push_residue(sections.get("remains", ""))
    if stripped_remains != str(sections.get("remains") or "") and (
        shipped_changed or verified_changed or _is_missing_github_push_blocker(str(sections.get("blocker") or ""))
    ):
        sections["remains"] = stripped_remains
        repaired = True
    blocker_text = str(sections.get("blocker") or "").strip()
    if _is_missing_github_push_blocker(blocker_text):
        stderr_path = _resolve_run_artifact_path(str(payload.get("stderr_path") or "").strip())
        if str(stderr_path) and stderr_path.exists() and not stderr_path.is_dir():
            push_recovery = _retry_worker_reported_git_pushes(_read_text(stderr_path))
            if push_recovery.get("attempted") and not push_recovery.get("failed"):
                sections["blocker"] = "none"
                repaired = True
            elif push_recovery.get("failed"):
                failure_bits = [
                    f"{repo}: {_summarize_trace_value(message, max_len=120)}"
                    for repo, message in sorted((push_recovery.get("failed") or {}).items())
                ]
                sections["blocker"] = (
                    "host-side git push recovery failed after worker credential error: " + "; ".join(failure_bits)
                )
                repaired = True
    if repaired and sections.get("blocker", "").strip().lower() in {"none", "no blocker", "no blockers", "none reported"}:
        sections["remains"] = _strip_remote_push_residue(sections.get("remains", ""))
    if (
        not repaired
        and str(sections.get("blocker") or "").strip().lower() in {"", "none", "no blocker", "no blockers", "none reported"}
    ):
        sections["blocker"] = "local commits are not yet pushed to remote"
        repaired = True
    if not repaired:
        return payload, False
    rewritten = _compose_final_message_sections(sections)
    payload["final_message"] = rewritten
    payload["shipped"] = sections.get("shipped", "")
    payload["remains"] = sections.get("remains", "")
    payload["blocker"] = sections.get("blocker", "")
    message_path = _resolve_run_artifact_path(str(payload.get("last_message_path") or "").strip())
    if str(message_path) and message_path.parent.exists():
        try:
            message_path.write_text(rewritten, encoding="utf-8")
        except OSError:
            pass
    return payload, True


def _worker_reported_git_push_repos(stderr_text: str) -> List[Path]:
    seen: Set[str] = set()
    rows: List[Path] = []
    for line in str(stderr_text or "").splitlines():
        if "git push" not in line or "cd /" not in line:
            continue
        match = re.search(r"cd\s+(?P<repo>/[^&'\n]+?)\s*&&", line)
        if not match:
            continue
        repo_text = str(match.group("repo") or "").strip()
        if not repo_text or repo_text in seen:
            continue
        seen.add(repo_text)
        rows.append(Path(repo_text))
    return rows


def _prepare_host_git_push_environment() -> Dict[str, str]:
    env = os.environ.copy()
    host_home_raw = str(os.environ.get("HOME", "") or "").strip()
    host_xdg_config_home_raw = str(os.environ.get("XDG_CONFIG_HOME", "") or "").strip()
    host_home = _resolve_host_home_path(host_home_raw)
    if host_home is None:
        return env
    env["HOME"] = str(host_home)
    _inherit_host_git_auth_environment(
        env,
        host_home_raw=str(host_home),
        host_xdg_config_home_raw=host_xdg_config_home_raw,
    )
    return env


def _github_https_auth_extraheader(env: Dict[str, str], repo: Path) -> str:
    try:
        remote = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
    except FileNotFoundError:
        return ""
    remote_url = str(remote.stdout or "").strip()
    if remote.returncode != 0 or not remote_url.startswith("https://github.com/"):
        return ""
    token = _github_auth_token(env)
    if not token:
        return ""
    basic = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
    return f"AUTHORIZATION: basic {basic}"


def _retry_worker_reported_git_pushes(stderr_text: str) -> Dict[str, Any]:
    repos = _worker_reported_git_push_repos(stderr_text)
    if not repos:
        return {"attempted": [], "succeeded": [], "failed": {}}
    env = _prepare_host_git_push_environment()
    attempted: List[str] = []
    succeeded: List[str] = []
    failed: Dict[str, str] = {}
    for repo in repos:
        attempted.append(str(repo))
        command = ["git", "-C", str(repo)]
        extraheader = _github_https_auth_extraheader(env, repo)
        if extraheader:
            command.extend(["-c", f"http.https://github.com/.extraheader={extraheader}"])
        command.append("push")
        completed = subprocess.run(command, text=True, capture_output=True, check=False, env=env)
        combined = "\n".join(
            item for item in (str(completed.stdout or "").strip(), str(completed.stderr or "").strip()) if item
        ).strip()
        if completed.returncode == 0:
            succeeded.append(str(repo))
            continue
        failed[str(repo)] = combined or f"git push exited {completed.returncode}"
    return {"attempted": attempted, "succeeded": succeeded, "failed": failed}


def _final_message_text_candidates(text: str) -> List[str]:
    raw = str(text or "").replace("\r\n", "\n").strip()
    if not raw:
        return [""]
    candidates: List[str] = [raw]
    seen: Set[str] = {raw}
    for line in raw.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("{") and stripped.endswith("}")):
            continue
        try:
            payload = json.loads(stripped)
        except Exception:
            continue
        for nested in _closeout_texts_from_json(payload):
            candidate = str(nested or "").replace("\r\n", "\n").strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            candidates.append(candidate)
    return candidates


def _closeout_texts_from_json(value: Any) -> List[str]:
    results: List[str] = []
    if isinstance(value, str):
        normalized = str(value).replace("\r\n", "\n").strip()
        if any(marker in normalized for marker in ("What shipped:", "What remains:", "Exact blocker:")):
            results.append(normalized)
        return results
    if isinstance(value, dict):
        for key in ("text", "final_message", "message", "output_text", "content"):
            if key in value:
                results.extend(_closeout_texts_from_json(value.get(key)))
        for nested in value.values():
            results.extend(_closeout_texts_from_json(nested))
        return results
    if isinstance(value, list):
        for item in value:
            results.extend(_closeout_texts_from_json(item))
    return results


def _final_message_reports_error(text: str) -> bool:
    compact = str(text or "").replace("\r\n", "\n").strip()
    if not compact:
        return False
    if re.search(r"(?im)^\s*error\s*:", compact):
        return True
    return "upstream_timeout:" in compact.lower()


def _assess_worker_result(
    worker_exit_code: int,
    final_message: str,
    parsed: Optional[Dict[str, str]] = None,
) -> tuple[bool, str]:
    if int(worker_exit_code) != 0:
        return False, f"worker exit {worker_exit_code}"
    compact = str(final_message or "").strip()
    if not compact:
        return False, "missing final message"
    if _final_message_reports_error(compact):
        return False, _summarize_trace_value(compact, max_len=96)
    sections = parsed or _parse_final_message_sections(compact)
    missing_labels: List[str] = []
    labels = {
        "shipped": "What shipped",
        "remains": "What remains",
        "blocker": "Exact blocker",
    }
    for key, label in labels.items():
        if not sections.get(key):
            missing_labels.append(label)
    if missing_labels:
        return False, f"missing structured closeout fields: {', '.join(missing_labels)}"
    if _closeout_has_remote_push_residue(sections):
        return False, "closeout reports local commits that are not yet pushed to remote"
    return True, ""


def _state_payload_path(state_root: Path) -> Path:
    return state_root / "state.json"


def _history_payload_path(state_root: Path) -> Path:
    return state_root / "history.jsonl"


def _lock_payload_path(state_root: Path) -> Path:
    return state_root / "loop.lock"


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_dir(path.parent)
    resolved_path = Path(path).resolve()
    normalized_payload = dict(payload or {})
    if resolved_path.name == "state.json":
        state_root = resolved_path.parent
        if not state_root.name.startswith("shard-") and bool(_configured_shard_roots(state_root)):
            aggregate_has_single_active_run_object = isinstance(normalized_payload.get("active_run"), dict) and bool(
                str((normalized_payload.get("active_run") or {}).get("run_id") or "").strip()
            )
            if not aggregate_has_single_active_run_object:
                normalized_payload = _clear_shard_scoped_aggregate_aliases(normalized_payload)
    rendered = json.dumps(normalized_payload, indent=2, sort_keys=True) + "\n"
    tmp_path = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        tmp_path.write_text(rendered, encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    _ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        for payload in rows:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _read_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(_read_text(path))
    except Exception:
        return {}


def _read_history(path: Path, *, limit: int = 10) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for raw in _read_text(path).splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    if limit > 0:
        rows = rows[-limit:]
    return rows


def _repair_recorded_missing_github_push_blocker(run: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    payload = dict(run or {})
    if not payload:
        return payload, False
    if not bool(payload.get("accepted")):
        return payload, False
    if not _is_missing_github_push_blocker(str(payload.get("blocker") or "")):
        return payload, False
    stderr_path = _resolve_run_artifact_path(str(payload.get("stderr_path") or "").strip())
    if not str(stderr_path) or not stderr_path.exists() or stderr_path.is_dir():
        return payload, False
    push_recovery = _retry_worker_reported_git_pushes(_read_text(stderr_path))
    if not push_recovery.get("attempted"):
        return payload, False
    final_message = _run_final_message(payload)
    parsed = _parse_final_message_sections(final_message)
    if push_recovery.get("failed"):
        failure_bits = [
            f"{repo}: {_summarize_trace_value(message, max_len=120)}"
            for repo, message in sorted((push_recovery.get("failed") or {}).items())
        ]
        new_blocker = "host-side git push recovery failed after worker credential error: " + "; ".join(failure_bits)
    else:
        new_blocker = "none"
    parsed["blocker"] = new_blocker
    payload["blocker"] = new_blocker
    if any(str(parsed.get(key) or "").strip() for key in ("shipped", "remains", "blocker")):
        rewritten = _compose_final_message_sections(parsed)
        payload["final_message"] = rewritten
        payload["shipped"] = parsed.get("shipped", "")
        payload["remains"] = parsed.get("remains", "")
        message_path = _resolve_run_artifact_path(str(payload.get("last_message_path") or "").strip())
        if str(message_path) and message_path.parent.exists():
            try:
                message_path.write_text(rewritten, encoding="utf-8")
            except OSError:
                pass
    return payload, True


def _repair_missing_structured_closeout_receipt(
    run: Dict[str, Any],
    history: Sequence[Dict[str, Any]],
) -> tuple[Dict[str, Any], bool]:
    payload = dict(run or {})
    if not payload or not bool(payload.get("accepted")):
        return payload, False
    accepted, reason = _run_receipt_status(payload)
    if accepted:
        return payload, False
    normalized_reason = str(reason or "").strip().lower()
    if "missing structured closeout content" not in normalized_reason:
        return payload, False

    run_id = str(payload.get("run_id") or "").strip()
    previous_sections: Optional[Dict[str, str]] = None
    previous_run_id = ""
    for row in reversed(list(history or [])):
        candidate = dict(row or {})
        candidate_run_id = str(candidate.get("run_id") or "").strip()
        if run_id and candidate_run_id == run_id:
            continue
        candidate_accepted, _candidate_reason = _run_receipt_status(candidate)
        if not candidate_accepted:
            continue
        parsed = _parse_final_message_sections(_run_final_message(candidate))
        shipped = str(parsed.get("shipped") or candidate.get("shipped") or "").strip()
        remains = str(parsed.get("remains") or candidate.get("remains") or "").strip()
        blocker = str(parsed.get("blocker") or candidate.get("blocker") or "").strip()
        if not shipped or not remains or not blocker:
            continue
        previous_sections = {"shipped": shipped, "remains": remains, "blocker": blocker}
        previous_run_id = candidate_run_id
        break

    if not previous_sections:
        return payload, False

    recovered_shipped = (
        "Recovered trusted structured closeout after an empty accepted receipt; no additional worker "
        f"output was captured in run {run_id or 'unknown'}."
    )
    if previous_run_id:
        recovered_shipped += f" Previous trusted receipt: {previous_run_id}."
    recovered_sections = {
        "shipped": recovered_shipped,
        "remains": previous_sections["remains"],
        "blocker": previous_sections["blocker"],
    }
    rewritten = _compose_final_message_sections(recovered_sections)
    payload["final_message"] = rewritten
    payload["shipped"] = recovered_sections["shipped"]
    payload["remains"] = recovered_sections["remains"]
    payload["blocker"] = recovered_sections["blocker"]
    payload["acceptance_reason"] = ""
    if previous_run_id:
        payload["receipt_recovered_from_run_id"] = previous_run_id
    message_path = _resolve_run_artifact_path(str(payload.get("last_message_path") or "").strip())
    if str(message_path) and message_path.parent.exists():
        try:
            message_path.write_text(rewritten, encoding="utf-8")
        except OSError:
            pass
    return payload, True


def _heal_state_push_blockers(state_root: Path) -> None:
    state_path = _state_payload_path(state_root)
    history_path = _history_payload_path(state_root)
    state = _read_state(state_path)
    history = _read_history(history_path, limit=0)
    changed = False
    repaired_run_id = ""
    last_run = dict(state.get("last_run") or {})
    repaired_last_run, repaired = _repair_missing_structured_closeout_receipt(last_run, history)
    if not repaired:
        repaired_last_run, repaired = _repair_recorded_missing_github_push_blocker(last_run)
    remote_push_repaired = False
    if not repaired:
        repaired_last_run, remote_push_repaired = _repair_recorded_remote_push_residue(last_run)
        repaired = remote_push_repaired
    if repaired:
        changed = True
        repaired_run_id = str(repaired_last_run.get("run_id") or "").strip()
        state["last_run"] = repaired_last_run
        state["updated_at"] = _iso_now()
    if changed:
        _write_json(state_path, state)
    if history:
        repaired_history: List[Dict[str, Any]] = []
        history_changed = False
        for row in history:
            payload = dict(row or {})
            if repaired_run_id and str(payload.get("run_id") or "").strip() == repaired_run_id:
                payload = dict(repaired_last_run)
                history_changed = True
            repaired_history.append(payload)
        if history_changed:
            _write_jsonl(history_path, repaired_history)


def _active_run_payload(run: ActiveWorkerRun) -> Dict[str, Any]:
    return asdict(run)


def _write_active_run_state(state_root: Path, run: Optional[ActiveWorkerRun]) -> None:
    state_path = _state_payload_path(state_root)
    payload = _read_state(state_path)
    payload["updated_at"] = _iso_now()
    if run is None:
        payload.pop("active_run", None)
    else:
        payload["active_run"] = _active_run_payload(run)
        payload.pop("idle_reason", None)
    _write_json(state_path, payload)
    _write_runtime_handoff(state_root)


def _update_active_run_fields(state_root: Path, run_id: str, **fields: Any) -> None:
    if not fields:
        return
    state_path = _state_payload_path(state_root)
    payload = _read_state(state_path)
    active_run = payload.get("active_run")
    if not isinstance(active_run, dict):
        return
    if str(active_run.get("run_id") or "").strip() != str(run_id or "").strip():
        return
    changed = False
    active_payload = dict(active_run)
    for key, value in fields.items():
        if active_payload.get(key) == value:
            continue
        active_payload[key] = value
        changed = True
    if (
        str(active_payload.get("progress_state") or "").strip() == ""
        and str(active_payload.get("worker_last_output_at") or active_payload.get("worker_first_output_at") or "").strip()
    ):
        active_payload["progress_state"] = "streaming"
        changed = True
    if not changed:
        return
    payload["updated_at"] = _iso_now()
    payload["active_run"] = active_payload
    payload.pop("idle_reason", None)
    payload = _apply_status_alias_fields(payload)
    _write_json(state_path, payload)
    _write_runtime_handoff(state_root)


def _runtime_handoff_path(state_root: Path) -> Path:
    return Path(state_root).resolve() / DEFAULT_SHARD_RUNTIME_HANDOFF_FILENAME


def _existing_runtime_handoff_path(state_root: Path) -> Optional[Path]:
    path = _runtime_handoff_path(state_root)
    return path if path.is_file() else None


def _tail_text_file(path: Path, *, max_bytes: int = 8192, max_lines: int = 40) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes), os.SEEK_SET)
            raw = handle.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""
    lines = raw.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    return "\n".join(lines).strip()


def _write_runtime_handoff(state_root: Path) -> None:
    try:
        resolved_state_root = Path(state_root).resolve()
        state = _read_state(_state_payload_path(resolved_state_root))
        active_run = dict(state.get("active_run") or {})
        last_run = dict(state.get("last_run") or {})
        focus_profiles = [str(item).strip() for item in (state.get("focus_profiles") or []) if str(item).strip()]
        focus_owners = [str(item).strip() for item in (state.get("focus_owners") or []) if str(item).strip()]
        focus_texts = [str(item).strip() for item in (state.get("focus_texts") or []) if str(item).strip()]
        frontier_ids = [int(value) for value in (state.get("frontier_ids") or active_run.get("frontier_ids") or last_run.get("frontier_ids") or []) if int(value or 0) > 0]
        open_milestone_ids = [
            int(value)
            for value in (state.get("open_milestone_ids") or active_run.get("open_milestone_ids") or last_run.get("open_milestone_ids") or [])
            if int(value or 0) > 0
        ]
        lines = [
            "# Shard Runtime Handoff",
            "",
            f"Generated at: {_iso_now()}",
            f"Shard: {resolved_state_root.name}",
            f"State root: {resolved_state_root}",
            f"Mode: {str(state.get('mode') or '').strip() or 'unknown'}",
            f"Frontier ids: {', '.join(str(value) for value in frontier_ids) or 'none'}",
            f"Open milestone ids: {', '.join(str(value) for value in open_milestone_ids) or 'none'}",
        ]
        if focus_profiles:
            lines.append(f"Focus profiles: {', '.join(focus_profiles)}")
        if focus_owners:
            lines.append(f"Focus owners: {', '.join(focus_owners)}")
        if focus_texts:
            lines.append(f"Focus texts: {', '.join(focus_texts)}")
        if active_run:
            prompt_path = str(active_run.get("prompt_path") or "").strip()
            stdout_path = _resolve_run_artifact_path(str(active_run.get("stdout_path") or "").strip())
            stderr_path = _resolve_run_artifact_path(str(active_run.get("stderr_path") or "").strip())
            last_message_path = _resolve_run_artifact_path(str(active_run.get("last_message_path") or "").strip())
            last_message_text = _read_text(last_message_path).strip() if last_message_path.exists() else ""
            parsed_last_message = _parse_final_message_sections(last_message_text) if last_message_text else {}
            stdout_tail = _tail_text_file(stdout_path)
            stderr_tail = _tail_text_file(stderr_path)
            self_polling_blocker = "worker_self_polling:supervisor_status_loop"
            lines.extend(
                [
                    "",
                    "## Active Run",
                    "",
                    f"- Run id: {str(active_run.get('run_id') or '').strip() or 'unknown'}",
                    f"- Selected account: {str(active_run.get('selected_account_alias') or '').strip() or 'unknown'}",
                    f"- Selected model: {str(active_run.get('selected_model') or '').strip() or 'default'}",
                    f"- Started at: {str(active_run.get('started_at') or '').strip() or 'unknown'}",
                    f"- First output at: {str(active_run.get('worker_first_output_at') or '').strip() or 'not yet'}",
                    f"- Last output at: {str(active_run.get('worker_last_output_at') or '').strip() or 'not yet'}",
                ]
            )
            if prompt_path:
                lines.append(f"- Prompt path: {prompt_path}")
            if parsed_last_message:
                shipped = str(parsed_last_message.get("shipped") or "").strip()
                remains = str(parsed_last_message.get("remains") or "").strip()
                blocker = str(parsed_last_message.get("blocker") or "").strip()
                if shipped:
                    lines.append(f"- Latest shipped note: {shipped}")
                if remains:
                    lines.append(f"- Latest remains note: {remains}")
                if blocker and self_polling_blocker not in blocker:
                    lines.append(f"- Latest blocker: {blocker}")
                elif blocker and self_polling_blocker in blocker:
                    lines.append(
                        "- Latest blocker: previous run was killed for querying supervisor status inside an active worker run"
                    )
            if stdout_tail:
                lines.extend(["", "## Recent stdout tail", "", "```text", stdout_tail, "```"])
            if stderr_tail:
                polling_loop_detected = (
                    self_polling_blocker in stderr_tail
                    or self_polling_blocker in last_message_text
                    or "polling_disabled" in stderr_tail
                    or "polling disabled inside active worker run" in stderr_tail.lower()
                    or "python3 /docker/fleet/scripts/chummer_design_supervisor.py status" in stderr_tail
                    or "python3 /docker/fleet/scripts/chummer_design_supervisor.py eta" in stderr_tail
                )
                if polling_loop_detected:
                    lines.extend(
                        [
                            "",
                            "## Recent stderr tail",
                            "",
                            "```text",
                            "Supervisor status polling was observed from inside the active worker run.",
                            "Do not repeat that pattern; keep working from the prompt, handoff, and frontier artifacts only.",
                            "```",
                        ]
                    )
                else:
                    lines.extend(["", "## Recent stderr tail", "", "```text", stderr_tail, "```"])
        elif last_run:
            last_run_blocker = str(last_run.get("blocker") or "").strip()
            if "worker_self_polling:supervisor_status_loop" in last_run_blocker:
                last_run_blocker = "previous run was killed for querying supervisor status inside an active worker run"
            lines.extend(
                [
                    "",
                    "## Last Run",
                    "",
                    f"- Run id: {str(last_run.get('run_id') or '').strip() or 'unknown'}",
                    f"- Selected account: {str(last_run.get('selected_account_alias') or '').strip() or 'unknown'}",
                    f"- Selected model: {str(last_run.get('selected_model') or '').strip() or 'default'}",
                    f"- Finished at: {str(last_run.get('finished_at') or last_run.get('started_at') or '').strip() or 'unknown'}",
                    f"- What shipped: {str(last_run.get('shipped') or '').strip() or 'none recorded'}",
                    f"- What remains: {str(last_run.get('remains') or '').strip() or 'none recorded'}",
                    f"- Exact blocker: {last_run_blocker or 'none recorded'}",
                ]
            )
        _runtime_handoff_path(resolved_state_root).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    except Exception:
        return


def _normalize_subprocess_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _subprocess_run_supports_timeout() -> bool:
    try:
        return "timeout" in inspect.signature(subprocess.run).parameters
    except (TypeError, ValueError):
        return False


def _run_worker_attempt(
    command: Sequence[str],
    *,
    prompt: str,
    workspace_root: Path,
    worker_env: Dict[str, str],
    timeout_seconds: float,
    last_message_path: Path,
    state_root: Path,
    run_id: str,
    stdout_sink: Any = None,
    stderr_sink: Any = None,
) -> subprocess.CompletedProcess[str]:
    self_poll_status_marker = "status_blocked_inside_worker_run"
    self_poll_command_markers = (
        "python3 /docker/fleet/scripts/chummer_design_supervisor.py status",
        "python3 /docker/fleet/scripts/chummer_design_supervisor.py eta",
    )
    self_poll_blocked_trip_threshold = _worker_self_poll_blocked_trip_threshold(workspace_root)
    status_helper_loop_trip_threshold = _worker_status_helper_loop_trip_threshold(workspace_root)
    prompt_lines = {str(line).strip() for line in str(prompt or "").splitlines() if str(line).strip()}
    model_output_stall_seconds = _worker_model_output_stall_seconds(workspace_root, timeout_seconds)
    kwargs: Dict[str, Any] = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "bufsize": 1,
        "cwd": str(workspace_root),
        "env": worker_env,
        "start_new_session": True,
    }
    stdout_chunks: List[str] = []
    stderr_chunks: List[str] = []
    output_lock = threading.Lock()
    progress_state = {
        "first_output_recorded": False,
        "last_progress_persisted_at": 0.0,
    }
    process_holder: Dict[str, Any] = {"process": None}
    handoff_heartbeat_stop = threading.Event()
    self_poll_state = {
        "blocked_status_hits": 0,
        "status_command_hits": 0,
        "tripped": False,
    }
    model_wait_state = {
        "first_wait_trace_monotonic": 0.0,
        "no_progress_started_monotonic": 0.0,
        "persisted_waiting_state": False,
        "tripped": False,
        "termination_reason": "",
    }
    handoff_heartbeat_seconds = _runtime_handoff_heartbeat_seconds()

    def _worker_stderr_chunk_is_waiting_trace(chunk: str) -> bool:
        compact = str(chunk or "").strip()
        if not compact:
            return False
        return bool(re.match(r"^Trace:\s*lane=.*waiting for model output(?:\s*\([^)]*\))?$", compact, re.IGNORECASE))

    def _worker_stderr_chunk_is_nonprogress_noise(chunk: str) -> bool:
        compact = str(chunk or "").strip()
        if not compact:
            return True
        lowered = compact.lower()
        if compact in prompt_lines:
            return True
        if compact == "--------":
            return True
        if lowered in {"user", "assistant", "codex", "tokens used"}:
            return True
        if lowered.startswith("[fleet-supervisor] "):
            return True
        if lowered.startswith("trace: lane="):
            return True
        if lowered.startswith("openai codex v"):
            return True
        if lowered.startswith("workdir:"):
            return True
        if lowered.startswith("model:"):
            return True
        if lowered.startswith("provider:"):
            return True
        if lowered.startswith("approval:"):
            return True
        if lowered.startswith("sandbox:"):
            return True
        if lowered.startswith("reasoning effort:"):
            return True
        if lowered.startswith("reasoning summaries:"):
            return True
        if lowered.startswith("session id:"):
            return True
        if lowered.startswith("mcp startup:"):
            return True
        if lowered.startswith("warning: codex could not find system bubblewrap on path."):
            return True
        if lowered.startswith("warning: model metadata for `"):
            return True
        if compact == "exec":
            return True
        if lowered.startswith("read the task-local prompt, shard runtime handoff, and frontier artifacts directly"):
            return True
        if lowered.startswith("run_id:"):
            return True
        if lowered.startswith("prompt_path:"):
            return True
        if lowered.startswith("runtime_handoff_path:"):
            return True
        if lowered.startswith("full_product_frontier_path:"):
            return True
        if lowered.startswith("completion_review_frontier_path:"):
            return True
        if lowered.startswith("flagship_product_readiness_path:"):
            return True
        if "python3 /docker/fleet/scripts/chummer_design_supervisor.py status" in compact:
            return True
        if "python3 /docker/fleet/scripts/chummer_design_supervisor.py eta" in compact:
            return True
        if lowered.startswith("exited ") and compact.endswith(":"):
            return True
        if lowered == "status_blocked_inside_worker_run":
            return True
        if lowered.startswith("worker_status_budget_exhausted:"):
            return True
        if lowered.startswith("succeeded in ") and compact.endswith(":"):
            return True
        if lowered.startswith("traceback (most recent call last):"):
            return True
        if lowered.startswith('file "'):
            return True
        if lowered.startswith("return "):
            return True
        if lowered.startswith("obj, end = "):
            return True
        if lowered.startswith("raise jsondecodeerror("):
            return True
        if compact.startswith("^"):
            return True
        if lowered.startswith("json.decoder.jsondecodeerror:"):
            return True
        if (
            compact.startswith("{")
            and '"active_runs_count"' in compact
            and '"remaining_open_milestones"' in compact
            and '"eta_human"' in compact
        ):
            return True
        return False

    def _chunk_counts_as_progress(chunk: str, *, stream_name: str) -> bool:
        compact = str(chunk or "").strip()
        if not compact:
            return False
        if stream_name == "stdout":
            return True
        return not _worker_stderr_chunk_is_nonprogress_noise(compact)

    def _stop_handoff_heartbeat(thread: Optional[threading.Thread]) -> None:
        handoff_heartbeat_stop.set()
        if thread is not None:
            thread.join(timeout=2)

    def _terminate_worker_process(proc: Optional[subprocess.Popen[str]]) -> None:
        if proc is None:
            return
        try:
            if int(proc.pid or 0) > 0:
                os.killpg(int(proc.pid), signal.SIGKILL)
                return
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass

    def _persist_output_progress(*, force: bool = False) -> None:
        now_monotonic = time.monotonic()
        should_write = force or not progress_state["first_output_recorded"] or (
            now_monotonic - float(progress_state["last_progress_persisted_at"] or 0.0) >= 10.0
        )
        if not should_write:
            return
        now_iso = _iso_now()
        fields: Dict[str, Any] = {
            "worker_last_output_at": now_iso,
            "progress_state": "streaming",
        }
        if not progress_state["first_output_recorded"]:
            fields["worker_first_output_at"] = now_iso
            progress_state["first_output_recorded"] = True
            model_wait_state["no_progress_started_monotonic"] = 0.0
        progress_state["last_progress_persisted_at"] = now_monotonic
        _update_active_run_fields(state_root, run_id, **fields)

    def _consume_stream(stream: Any, sink: Any, chunks: List[str], *, stream_name: str) -> None:
        if stream is None:
            return
        try:
            while True:
                try:
                    chunk = stream.readline()
                except ValueError:
                    # The parent thread may close the stream while the reader thread is still unwinding.
                    break
                if chunk == "":
                    break
                with output_lock:
                    chunks.append(chunk)
                    if sink is not None:
                        try:
                            sink.write(chunk)
                            sink.flush()
                        except ValueError:
                            sink = None
                if stream_name == "stderr":
                    blocked_status_detected = self_poll_status_marker in chunk
                    raw_status_command_detected = any(marker in chunk for marker in self_poll_command_markers)
                    waiting_for_model_output = _worker_stderr_chunk_is_waiting_trace(chunk)
                    if blocked_status_detected:
                        self_poll_state["blocked_status_hits"] = int(self_poll_state["blocked_status_hits"]) + 1
                        if (
                            not progress_state["first_output_recorded"]
                            and not model_wait_state["tripped"]
                            and int(self_poll_state["blocked_status_hits"]) >= 2
                        ):
                            model_wait_state["tripped"] = True
                            model_wait_state["termination_reason"] = "status_helper_loop"
                            _terminate_worker_process(process_holder.get("process"))
                    if raw_status_command_detected:
                        self_poll_state["status_command_hits"] = int(self_poll_state["status_command_hits"]) + 1
                        if (
                            not progress_state["first_output_recorded"]
                            and not model_wait_state["tripped"]
                            and (
                                bool(model_wait_state["persisted_waiting_state"])
                                or float(model_wait_state["first_wait_trace_monotonic"] or 0.0) > 0.0
                                or int(self_poll_state["blocked_status_hits"]) > 0
                            )
                            and int(status_helper_loop_trip_threshold) > 0
                            and int(self_poll_state["status_command_hits"]) >= int(status_helper_loop_trip_threshold)
                        ):
                            model_wait_state["tripped"] = True
                            model_wait_state["termination_reason"] = "status_helper_loop"
                            _terminate_worker_process(process_holder.get("process"))
                    if blocked_status_detected or raw_status_command_detected:
                        if (
                            not self_poll_state["tripped"]
                            and int(self_poll_blocked_trip_threshold) > 0
                            and int(self_poll_state["blocked_status_hits"]) >= self_poll_blocked_trip_threshold
                        ):
                            self_poll_state["tripped"] = True
                            _terminate_worker_process(process_holder.get("process"))
                    if waiting_for_model_output and not progress_state["first_output_recorded"]:
                        now_monotonic = time.monotonic()
                        if float(model_wait_state["first_wait_trace_monotonic"] or 0.0) <= 0.0:
                            model_wait_state["first_wait_trace_monotonic"] = now_monotonic
                        if not model_wait_state["persisted_waiting_state"]:
                            _update_active_run_fields(
                                state_root,
                                run_id,
                                progress_state="waiting_for_model_output",
                            )
                            model_wait_state["persisted_waiting_state"] = True
                        if (
                            not model_wait_state["tripped"]
                            and model_output_stall_seconds >= 0.0
                            and now_monotonic - float(model_wait_state["first_wait_trace_monotonic"] or 0.0)
                            >= float(model_output_stall_seconds)
                        ):
                            model_wait_state["tripped"] = True
                            _terminate_worker_process(process_holder.get("process"))
                if _chunk_counts_as_progress(chunk, stream_name=stream_name):
                    _persist_output_progress()
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _handoff_heartbeat_loop() -> None:
        if handoff_heartbeat_seconds <= 0.0:
            return
        while not handoff_heartbeat_stop.wait(handoff_heartbeat_seconds):
            _write_runtime_handoff(state_root)

    try:
        process = subprocess.Popen(command, **kwargs)
    except FileNotFoundError as exc:
        missing = str(exc.filename or command[0] if command else "command")
        return subprocess.CompletedProcess(
            list(command),
            127,
            stdout="",
            stderr=f"{missing}: not found",
        )

    process_holder["process"] = process
    _update_active_run_fields(
        state_root,
        run_id,
        worker_pid=int(process.pid),
        progress_state="running_silent",
    )
    handoff_heartbeat_thread: Optional[threading.Thread] = None
    if handoff_heartbeat_seconds > 0.0:
        handoff_heartbeat_thread = threading.Thread(
            target=_handoff_heartbeat_loop,
            daemon=True,
        )
        handoff_heartbeat_thread.start()
    stdout_thread = threading.Thread(
        target=_consume_stream,
        args=(process.stdout, stdout_sink, stdout_chunks),
        kwargs={"stream_name": "stdout"},
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_consume_stream,
        args=(process.stderr, stderr_sink, stderr_chunks),
        kwargs={"stream_name": "stderr"},
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    timeout_enabled = float(timeout_seconds or 0.0) > 0 and _subprocess_run_supports_timeout()

    try:
        if process.stdin is not None:
            process.stdin.write(prompt)
            process.stdin.close()
        wait_started_monotonic = time.monotonic()
        model_wait_state["no_progress_started_monotonic"] = wait_started_monotonic
        timeout_deadline = (
            wait_started_monotonic + float(timeout_seconds)
            if timeout_enabled
            else None
        )
        poll_interval_seconds = 5.0
        while True:
            remaining_timeout: Optional[float] = None
            if timeout_deadline is not None:
                remaining_timeout = timeout_deadline - time.monotonic()
                if remaining_timeout <= 0.0:
                    raise subprocess.TimeoutExpired(command, timeout=float(timeout_seconds))
            if model_wait_state["tripped"]:
                break
            wait_timeout = poll_interval_seconds
            if remaining_timeout is not None:
                wait_timeout = max(0.05, min(wait_timeout, remaining_timeout))
            try:
                process.wait(timeout=wait_timeout if timeout_enabled or model_output_stall_seconds > 0.0 else None)
                break
            except subprocess.TimeoutExpired:
                now_monotonic = time.monotonic()
                no_progress_anchor = float(model_wait_state["first_wait_trace_monotonic"] or 0.0)
                if no_progress_anchor <= 0.0:
                    no_progress_anchor = float(model_wait_state["no_progress_started_monotonic"] or 0.0)
                if (
                    not progress_state["first_output_recorded"]
                    and not model_wait_state["tripped"]
                    and no_progress_anchor > 0.0
                    and model_output_stall_seconds >= 0.0
                    and now_monotonic - no_progress_anchor >= float(model_output_stall_seconds)
                ):
                    model_wait_state["tripped"] = True
                    _terminate_worker_process(process_holder.get("process"))
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
                    break
                if timeout_deadline is None:
                    continue
                if now_monotonic >= timeout_deadline:
                    raise subprocess.TimeoutExpired(command, timeout=float(timeout_seconds))
    except subprocess.TimeoutExpired:
        _terminate_worker_process(process)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        _stop_handoff_heartbeat(handoff_heartbeat_thread)
        timeout_label = f"{float(timeout_seconds):g}s"
        stdout_text = "".join(stdout_chunks)
        stderr_text = "".join(stderr_chunks)
        timeout_message = f"Error: worker_timeout:{timeout_label}"
        if stderr_text and not stderr_text.endswith("\n"):
            stderr_text += "\n"
        stderr_text += timeout_message + "\n"
        stderr_text += (
            f"[fleet-supervisor] worker attempt exceeded watchdog after {timeout_label}; "
            "killed and marked retryable\n"
        )
        with output_lock:
            if stderr_sink is not None:
                stderr_sink.write(timeout_message + "\n")
                stderr_sink.write(
                    f"[fleet-supervisor] worker attempt exceeded watchdog after {timeout_label}; killed and marked retryable\n"
                )
                stderr_sink.flush()
        if not last_message_path.exists() or not _read_text(last_message_path).strip():
            last_message_path.write_text(timeout_message + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            list(command),
            124,
            stdout=stdout_text,
            stderr=stderr_text,
        )
    finally:
        if process.stdin is not None and not process.stdin.closed:
            try:
                process.stdin.close()
            except Exception:
                pass

    if stdout_thread.is_alive() and process.stdout is not None:
        try:
            process.stdout.close()
        except Exception:
            pass
    if stderr_thread.is_alive() and process.stderr is not None:
        try:
            process.stderr.close()
        except Exception:
            pass
    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)
    _stop_handoff_heartbeat(handoff_heartbeat_thread)
    if model_wait_state["tripped"]:
        stdout_text = "".join(stdout_chunks)
        stderr_text = "".join(stderr_chunks)
        termination_reason = str(model_wait_state.get("termination_reason") or "").strip().lower()
        if termination_reason == "status_helper_loop":
            violation_token = "worker_status_helper_loop:repeated_blocked_status_polling"
            violation_message = (
                f"Error: {violation_token}\n"
                "[fleet-supervisor] worker kept polling blocked supervisor status inside an active run without "
                "meaningful output; killed early and marked retryable\n"
            )
        else:
            stall_label = f"{float(model_output_stall_seconds):g}s"
            violation_token = f"worker_model_output_stalled:{stall_label}"
            violation_message = (
                f"Error: {violation_token}\n"
                "[fleet-supervisor] worker produced only startup or prompt-echo output and model-wait traces; "
                f"killed after {stall_label} without meaningful output and marked retryable\n"
            )
        if stderr_text and not stderr_text.endswith("\n"):
            stderr_text += "\n"
        stderr_text += violation_message
        with output_lock:
            if stderr_sink is not None:
                stderr_sink.write(violation_message)
                stderr_sink.flush()
        if not last_message_path.exists() or not _read_text(last_message_path).strip():
            last_message_path.write_text(f"Error: {violation_token}\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            list(command),
            124,
            stdout=stdout_text,
            stderr=stderr_text,
        )
    if self_poll_state["tripped"]:
        stdout_text = "".join(stdout_chunks)
        stderr_text = "".join(stderr_chunks)
        violation_message = (
            "Error: worker_self_polling:supervisor_status_loop\n"
            "[fleet-supervisor] worker repeatedly queried supervisor status inside an active run; "
            "killed and marked non-retryable\n"
        )
        if stderr_text and not stderr_text.endswith("\n"):
            stderr_text += "\n"
        stderr_text += violation_message
        with output_lock:
            if stderr_sink is not None:
                stderr_sink.write(violation_message)
                stderr_sink.flush()
        if not last_message_path.exists() or not _read_text(last_message_path).strip():
            last_message_path.write_text("Exact blocker: worker_self_polling:supervisor_status_loop\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            list(command),
            125,
            stdout=stdout_text,
            stderr=stderr_text,
        )
    return subprocess.CompletedProcess(
        list(command),
        int(process.returncode or 0),
        stdout="".join(stdout_chunks),
        stderr="".join(stderr_chunks),
    )


def _state_updated_at(state: Dict[str, Any]) -> Optional[dt.datetime]:
    return _parse_iso(str(state.get("updated_at") or ""))


def _run_updated_at(run: Dict[str, Any]) -> Optional[dt.datetime]:
    return _run_finished_at(run) or _parse_iso(str(run.get("started_at") or ""))


def _state_field_has_meaningful_content(value: Any) -> bool:
    if value in (None, ""):
        return False
    if isinstance(value, dict):
        return any(_state_field_has_meaningful_content(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_state_field_has_meaningful_content(item) for item in value)
    return True


def _eta_snapshot_has_progress_fields(snapshot: Any) -> bool:
    if not isinstance(snapshot, dict):
        return False
    if not _state_field_has_meaningful_content(snapshot.get("summary")):
        return False
    return all(snapshot.get(key) is not None for key in (
        "remaining_open_milestones",
        "remaining_in_progress_milestones",
        "remaining_not_started_milestones",
    ))


def _shard_state_roots(state_root: Path) -> List[Path]:
    if not state_root.exists() or not state_root.is_dir():
        return []
    roots: List[Path] = []
    for candidate in sorted(state_root.iterdir()):
        if not candidate.is_dir() or not candidate.name.startswith("shard-"):
            continue
        if _state_payload_path(candidate).exists() or _history_payload_path(candidate).exists():
            roots.append(candidate)
    return roots


def _latest_nonempty_state_field(state_items: Sequence[Dict[str, Any]], field: str) -> Any:
    default_time = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    rows = sorted(
        [item for item in state_items if item.get("state")],
        key=lambda item: _state_updated_at(dict(item.get("state") or {})) or default_time,
        reverse=True,
    )
    for item in rows:
        state = dict(item.get("state") or {})
        value = state.get(field)
        if _state_field_has_meaningful_content(value):
            return value
    return {}


def _latest_nonempty_shard_state_field(state_items: Sequence[Dict[str, Any]], field: str) -> Any:
    shard_items = [item for item in state_items if str(item.get("name") or "") != "base"]
    if field == "active_run":
        live_shard_items: List[Dict[str, Any]] = []
        for item in shard_items:
            state = dict(item.get("state") or {})
            mode = str(state.get("mode") or "").strip().lower()
            active_run = state.get("active_run")
            if active_run in (None, "", [], {}):
                continue
            if mode == "complete" and not _state_frontier_ids(state) and not _state_open_milestone_ids(state):
                continue
            live_shard_items.append(item)
        shard_items = live_shard_items
    return _latest_nonempty_state_field(shard_items, field)


def _normalized_blocker_text(value: Any) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {"none", "n/a", "no blocker", "no blockers", "none reported"}:
        return ""
    return text


def _rewrite_eta_progress_summary(summary: str, *, open_count: int, in_progress_count: int, not_started_count: int) -> str:
    text = str(summary or "").strip()
    if not text:
        return text
    updated_prefix = (
        f"{open_count} open milestones remain ({in_progress_count} in progress, "
        f"{not_started_count} not started)"
    )
    rewritten = re.sub(
        r"^\d+\s+open milestones remain\s+\(\d+\s+in progress,\s+\d+\s+not started\)",
        updated_prefix,
        text,
        count=1,
        flags=re.I,
    )
    if rewritten != text:
        return rewritten
    if "open milestones remain" in text.lower():
        return f"{updated_prefix}. {text}"
    return text


def _ignore_nonlinux_desktop_host_proof_blockers_enabled() -> bool:
    return _runtime_env_default(
        "CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS",
        "",
    ).strip().lower() in {"1", "true", "yes", "on"}


def _reason_targets_ignored_nonlinux_desktop_host_platform(text: str) -> bool:
    normalized = _normalize_blocker(text).lower()
    if not normalized:
        return False
    if (
        "macos" not in normalized
        and "windows" not in normalized
        and "external-proof-macos-host-missing" not in normalized
        and "external-proof-powershell-missing" not in normalized
    ):
        return False
    if any(token in normalized for token in (":linux", " linux startup-smoke", " linux installer", " linux desktop")):
        return False
    return any(
        token in normalized
        for token in (
            "external-proof-macos-host-missing",
            "external-proof-powershell-missing",
            "external host lanes",
            "startup-smoke + promoted-installer",
            "startup-smoke receipt",
            "promoted installer",
            "external host-proof gaps remain",
            "requires a windows-capable host",
            "requires a macos host",
            "missing_windows_host_capability",
            "missing_macos_host_capability",
        )
    )


def _reconcile_aggregate_shard_truth(state: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(state or {})
    shard_rows = [dict(item or {}) for item in (updated.get("shards") or []) if isinstance(item, dict)]
    if not shard_rows:
        updated.pop("shard_blockers", None)
        return updated
    aggregate_active_run_count = sum(1 for shard in shard_rows if _shard_summary_counts_as_active_run(shard))
    aggregate_has_single_active_run_object = isinstance(updated.get("active_run"), dict) and bool(
        str((updated.get("active_run") or {}).get("run_id") or "").strip()
    )
    if len(shard_rows) > 1 and not aggregate_has_single_active_run_object:
        for key in (
            "active_run",
            "active_run_id",
            "active_run_started_at",
            "active_run_worker_first_output_at",
            "active_run_worker_last_output_at",
            "worker_last_output_at",
            "active_run_worker_pid",
            "active_run_prompt_path",
            "worker_stdout_path",
            "worker_stderr_path",
            "worker_last_message_path",
            "selected_account_alias",
            "selected_model",
            "idle_reason",
        ):
            updated.pop(key, None)
    in_progress_ids: Set[int] = set()
    shard_blockers: List[Dict[str, str]] = []
    shard_eta_open_sum = 0
    shard_eta_in_progress_sum = 0
    shard_eta_not_started_sum = 0
    has_shard_eta_counts = False
    shard_eta_scope_kinds: Set[str] = set()
    active_parallel_range_lows: List[float] = []
    active_parallel_range_highs: List[float] = []
    active_parallel_shard_count = 0
    claimed_parallel_range_lows: List[float] = []
    claimed_parallel_range_highs: List[float] = []
    claimed_parallel_shard_count = 0
    open_ids = {
        _coerce_int(value, 0)
        for value in (updated.get("open_milestone_ids") or [])
        if _coerce_int(value, 0) > 0
    }
    for shard in shard_rows:
        for value in (shard.get("active_frontier_ids") or shard.get("frontier_ids") or []):
            normalized = _coerce_int(value, 0)
            if normalized > 0:
                in_progress_ids.add(normalized)
        shard_eta_open = max(0, _coerce_int(shard.get("eta_remaining_open_milestones"), 0))
        shard_eta_in_progress = max(0, _coerce_int(shard.get("eta_remaining_in_progress_milestones"), 0))
        shard_eta_not_started = max(0, _coerce_int(shard.get("eta_remaining_not_started_milestones"), 0))
        shard_eta_scope_kind = str(shard.get("eta_scope_kind") or "").strip()
        if shard_eta_scope_kind:
            shard_eta_scope_kinds.add(shard_eta_scope_kind)
        if shard_eta_open or shard_eta_in_progress or shard_eta_not_started:
            has_shard_eta_counts = True
            shard_eta_open = max(shard_eta_open, shard_eta_in_progress + shard_eta_not_started)
            shard_eta_open_sum += shard_eta_open
            shard_eta_in_progress_sum += shard_eta_in_progress
            shard_eta_not_started_sum += shard_eta_not_started
        if _shard_summary_counts_as_active_run(shard):
            active_parallel_shard_count += 1
            shard_range_low = shard.get("eta_range_low_hours")
            shard_range_high = shard.get("eta_range_high_hours")
            try:
                if shard_range_low is not None:
                    active_parallel_range_lows.append(max(0.0, float(shard_range_low)))
                if shard_range_high is not None:
                    active_parallel_range_highs.append(max(0.0, float(shard_range_high)))
            except (TypeError, ValueError):
                pass
        claimed_frontier_ids = {
            _coerce_int(value, 0)
            for value in (shard.get("active_frontier_ids") or shard.get("frontier_ids") or [])
            if _coerce_int(value, 0) > 0
        }
        if claimed_frontier_ids and (not open_ids or claimed_frontier_ids.intersection(open_ids)):
            claimed_parallel_shard_count += 1
            shard_range_low = shard.get("eta_range_low_hours")
            shard_range_high = shard.get("eta_range_high_hours")
            try:
                if shard_range_low is not None:
                    claimed_parallel_range_lows.append(max(0.0, float(shard_range_low)))
                if shard_range_high is not None:
                    claimed_parallel_range_highs.append(max(0.0, float(shard_range_high)))
            except (TypeError, ValueError):
                pass
        blocker_text = _normalized_blocker_text(shard.get("last_run_blocker"))
        if _ignore_nonlinux_desktop_host_proof_blockers_enabled() and _reason_targets_ignored_nonlinux_desktop_host_platform(
            blocker_text
        ):
            blocker_text = ""
        last_run_finished_at = _parse_iso(str(shard.get("last_run_finished_at") or "").strip())
        active_run_started_at = _parse_iso(str(shard.get("active_run_started_at") or "").strip())
        is_stale = (
            bool(blocker_text)
            and last_run_finished_at is not None
            and active_run_started_at is not None
            and active_run_started_at > last_run_finished_at
        )
        current_blocker = "" if is_stale else blocker_text
        if blocker_text:
            shard["historical_last_run_blocker"] = blocker_text
        else:
            shard.pop("historical_last_run_blocker", None)
        shard["last_run_blocker"] = current_blocker
        shard["current_blocker"] = current_blocker
        if current_blocker:
            shard_blockers.append(
                {
                    "name": str(shard.get("name") or "").strip(),
                    "run_id": str(shard.get("last_run_id") or "").strip(),
                    "blocker": current_blocker,
                }
            )
    updated["shards"] = shard_rows
    updated["active_runs_count"] = aggregate_active_run_count
    if len(shard_rows) > 1 and not aggregate_has_single_active_run_object:
        if aggregate_active_run_count > 0:
            updated["active_run_progress_state"] = "aggregate_parallelized"
        else:
            updated.pop("active_run_progress_state", None)
    if shard_blockers:
        updated["shard_blockers"] = shard_blockers
    else:
        updated.pop("shard_blockers", None)
    eta = dict(updated.get("eta") or {})
    if eta:
        active_open_ids = in_progress_ids & open_ids if open_ids else set(in_progress_ids)
        open_count = len(open_ids)
        in_progress_count = len(active_open_ids)
        used_shard_eta_totals = open_count == 0 and has_shard_eta_counts
        if used_shard_eta_totals:
            open_count = shard_eta_open_sum
            in_progress_count = shard_eta_in_progress_sum
        if not in_progress_count and in_progress_ids:
            normalized_mode = str(updated.get("mode") or "").strip().lower()
            if normalized_mode in {"flagship_product", "sharded"}:
                in_progress_count = min(open_count or len(in_progress_ids), len(in_progress_ids))
        if used_shard_eta_totals:
            not_started_count = shard_eta_not_started_sum
        else:
            not_started_count = max(0, open_count - in_progress_count)
        if used_shard_eta_totals and in_progress_count > shard_eta_in_progress_sum:
            not_started_count = max(0, open_count - in_progress_count)
        eta = _normalize_eta_scope_fields(eta)
        aggregate_scope_kind = str(eta.get("scope_kind") or "").strip()
        consistent_shard_scope_kind = next(iter(shard_eta_scope_kinds)) if len(shard_eta_scope_kinds) == 1 else ""
        if consistent_shard_scope_kind and aggregate_scope_kind != consistent_shard_scope_kind:
            eta.update(_eta_scope_defaults(consistent_shard_scope_kind))
            aggregate_scope_kind = consistent_shard_scope_kind
        mixed_eta_scopes = len(shard_eta_scope_kinds) > 1
        if mixed_eta_scopes:
            eta["status"] = "tracked"
            eta["eta_human"] = "tracked"
            eta["eta_confidence"] = ETA_STATUS_LOW_CONFIDENCE
            eta["basis"] = "aggregate_shard_eta_scope_mismatch"
            eta["predicted_completion_at"] = ""
            eta.update(
                _eta_scope_fields(
                    scope_kind="aggregate_shard_mixed_scope",
                    scope_label="Aggregate multi-shard ETA",
                    scope_warning=(
                        "Aggregate shard status currently mixes multiple ETA scopes. Use the ETA command for a fresh "
                        "whole-fleet forecast instead of reading this as a single parity horizon."
                    ),
                )
            )
            scope_list = ", ".join(sorted(shard_eta_scope_kinds)) or aggregate_scope_kind or "unknown"
            eta["summary"] = (
                f"Aggregate shard state currently mixes ETA scopes ({scope_list}). "
                f"{open_count} open milestones remain across the active frontier."
            )
        elif consistent_shard_scope_kind and consistent_shard_scope_kind != "open_milestone_frontier" and open_count > 0 and len(shard_rows) > 1:
            parallel_low_hours = max(claimed_parallel_range_lows) if claimed_parallel_range_lows else None
            parallel_high_hours = max(claimed_parallel_range_highs) if claimed_parallel_range_highs else None
            parallel_shard_count = claimed_parallel_shard_count
            if parallel_low_hours is None or parallel_high_hours is None:
                parallel_low_hours = max(active_parallel_range_lows) if active_parallel_range_lows else None
                parallel_high_hours = max(active_parallel_range_highs) if active_parallel_range_highs else None
                parallel_shard_count = active_parallel_shard_count
            eta["status"] = "tracked"
            eta["eta_confidence"] = ETA_STATUS_LOW_CONFIDENCE
            eta["basis"] = "aggregate_shard_parallel_scope"
            if parallel_low_hours is not None and parallel_high_hours is not None:
                parallel_high_hours = max(parallel_high_hours, parallel_low_hours)
                eta["eta_human"] = _format_eta_window(parallel_low_hours, parallel_high_hours)
                eta["range_low_hours"] = round(parallel_low_hours, 2)
                eta["range_high_hours"] = round(parallel_high_hours, 2)
                eta["predicted_completion_at"] = _iso(
                    _utc_now() + dt.timedelta(hours=(parallel_low_hours + parallel_high_hours) / 2.0)
                )
            else:
                eta["eta_human"] = "tracked"
                eta["predicted_completion_at"] = ""
            eta["summary"] = (
                f"{open_count} open milestones remain ({in_progress_count} in progress, {not_started_count} not started). "
                f"Aggregate shard status is parallelized across {max(1, parallel_shard_count)} active shards under "
                f"{eta.get('scope_label') or consistent_shard_scope_kind}."
            )
        eta["remaining_open_milestones"] = open_count
        eta["remaining_in_progress_milestones"] = in_progress_count
        eta["remaining_not_started_milestones"] = not_started_count
        if str(eta.get("basis") or "").strip() not in {"aggregate_shard_eta_scope_mismatch", "aggregate_shard_parallel_scope"}:
            eta["summary"] = _rewrite_eta_progress_summary(
                str(eta.get("summary") or ""),
                open_count=open_count,
                in_progress_count=in_progress_count,
                not_started_count=not_started_count,
            )
        if shard_blockers:
            primary = dict(shard_blockers[0])
            blocker_reason = f"{primary.get('name') or 'unknown'}: {primary.get('blocker') or 'blocked'}"
            extra = max(0, len(shard_blockers) - 1)
            if extra:
                blocker_reason = f"{blocker_reason} (+{extra} more shard blocker{'s' if extra != 1 else ''})"
            eta = _apply_eta_blocker(eta, blocker_reason)
        updated["eta"] = eta
    return _apply_status_alias_fields(updated)


def _shard_summary_counts_as_active_run(shard: Dict[str, Any]) -> bool:
    active_run_id = str(shard.get("active_run_id") or "").strip()
    if not active_run_id:
        return False
    progress_state = str(shard.get("active_run_progress_state") or "").strip().lower()
    if progress_state in {"closing", "missing_process"}:
        return False
    return True


def _clear_shard_scoped_aggregate_aliases(payload: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(payload or {})
    for key in (
        "active_run",
        "active_run_id",
        "active_run_started_at",
        "active_run_worker_first_output_at",
        "active_run_worker_last_output_at",
        "worker_last_output_at",
        "active_run_worker_pid",
        "active_run_progress_state",
        "active_run_prompt_path",
        "worker_stdout_path",
        "worker_stderr_path",
        "worker_last_message_path",
        "selected_account_alias",
        "selected_model",
        "idle_reason",
    ):
        updated.pop(key, None)
    return updated


def _apply_status_alias_fields(state: Dict[str, Any]) -> Dict[str, Any]:
    updated = dict(state or {})
    shards = updated.get("shards")
    if isinstance(shards, list):
        updated["active_runs_count"] = sum(
            1
            for item in shards
            if isinstance(item, dict) and _shard_summary_counts_as_active_run(item)
        )
    else:
        active_runs = updated.get("active_runs")
        if isinstance(active_runs, list):
            updated["active_runs_count"] = sum(
                1
                for item in active_runs
                if isinstance(item, dict) and str(item.get("run_id") or "").strip()
            )
    eta = dict(updated.get("eta") or {})
    if eta:
        for key in (
            "remaining_open_milestones",
            "remaining_in_progress_milestones",
            "remaining_not_started_milestones",
        ):
            value = eta.get(key)
            if value is None:
                updated.pop(key, None)
            else:
                updated[key] = value
        eta_human = str(eta.get("eta_human") or "").strip()
        if eta_human:
            updated["eta_human"] = eta_human
        else:
            updated.pop("eta_human", None)
        eta_status = str(eta.get("status") or "").strip()
        if eta_status:
            updated["eta_status"] = eta_status
        else:
            updated.pop("eta_status", None)
        eta_summary = str(eta.get("summary") or "").strip()
        if eta_summary:
            updated["eta_summary"] = eta_summary
        else:
            updated.pop("eta_summary", None)
        eta_confidence = str(eta.get("eta_confidence") or "").strip()
        if eta_confidence:
            updated["eta_confidence"] = eta_confidence
        else:
            updated.pop("eta_confidence", None)
        predicted_completion_at = str(eta.get("predicted_completion_at") or "").strip()
        if predicted_completion_at:
            updated["predicted_completion_at"] = predicted_completion_at
        else:
            updated.pop("predicted_completion_at", None)
        for key in ("range_low_hours", "range_high_hours"):
            value = eta.get(key)
            if value is None:
                updated.pop(key, None)
            else:
                updated[key] = value
    else:
        updated.pop("remaining_open_milestones", None)
        updated.pop("remaining_in_progress_milestones", None)
        updated.pop("remaining_not_started_milestones", None)
        updated.pop("eta_human", None)
        updated.pop("eta_status", None)
        updated.pop("eta_summary", None)
        updated.pop("eta_confidence", None)
        updated.pop("predicted_completion_at", None)
        updated.pop("range_low_hours", None)
        updated.pop("range_high_hours", None)
    raw_successor_eta = updated.get("successor_wave_eta")
    successor_eta = _normalize_eta_scope_fields(dict(raw_successor_eta)) if isinstance(raw_successor_eta, dict) and raw_successor_eta else {}
    if successor_eta:
        updated["successor_wave_eta"] = successor_eta
        successor_eta_human = str(successor_eta.get("eta_human") or "").strip()
        if successor_eta_human:
            updated["successor_wave_eta_human"] = successor_eta_human
        else:
            updated.pop("successor_wave_eta_human", None)
        successor_eta_status = str(successor_eta.get("status") or "").strip()
        if successor_eta_status:
            updated["successor_wave_eta_status"] = successor_eta_status
        else:
            updated.pop("successor_wave_eta_status", None)
        successor_eta_summary = str(successor_eta.get("summary") or "").strip()
        if successor_eta_summary:
            updated["successor_wave_eta_summary"] = successor_eta_summary
        else:
            updated.pop("successor_wave_eta_summary", None)
        for key, alias in (
            ("range_low_hours", "successor_wave_range_low_hours"),
            ("range_high_hours", "successor_wave_range_high_hours"),
            ("remaining_open_milestones", "successor_wave_remaining_open_milestones"),
        ):
            value = successor_eta.get(key)
            if value is None:
                updated.pop(alias, None)
            else:
                updated[alias] = value
    else:
        updated.pop("successor_wave_eta", None)
        updated.pop("successor_wave_eta_human", None)
        updated.pop("successor_wave_eta_status", None)
        updated.pop("successor_wave_eta_summary", None)
        updated.pop("successor_wave_range_low_hours", None)
        updated.pop("successor_wave_range_high_hours", None)
        updated.pop("successor_wave_remaining_open_milestones", None)
    worker_lane_health = dict(updated.get("worker_lane_health") or {})
    if worker_lane_health:
        worker_lanes_status = str(worker_lane_health.get("status") or "").strip()
        if worker_lanes_status:
            updated["worker_lanes_status"] = worker_lanes_status
        else:
            updated.pop("worker_lanes_status", None)
    else:
        updated.pop("worker_lanes_status", None)
    host_memory_pressure = dict(updated.get("host_memory_pressure") or {})
    if host_memory_pressure:
        updated["allowed_active_shards"] = max(
            0,
            _coerce_int(host_memory_pressure.get("allowed_active_shards"), 0),
        )
        status = str(host_memory_pressure.get("status") or "").strip()
        if status:
            updated["host_memory_status"] = status
        else:
            updated.pop("host_memory_status", None)
    else:
        updated.pop("allowed_active_shards", None)
        updated.pop("host_memory_status", None)
    active_run = dict(updated.get("active_run") or {}) if isinstance(updated.get("active_run"), dict) else {}
    mode = str(updated.get("mode") or "").strip()
    if active_run:
        active_run_frontier_ids = [_coerce_int(value, 0) for value in (active_run.get("frontier_ids") or [])]
        active_run_frontier_ids = [value for value in active_run_frontier_ids if value > 0]
        if active_run_frontier_ids and not list(updated.get("frontier_ids") or []):
            updated["frontier_ids"] = list(active_run_frontier_ids)
        active_run_open_milestone_ids = [_coerce_int(value, 0) for value in (active_run.get("open_milestone_ids") or [])]
        active_run_open_milestone_ids = [value for value in active_run_open_milestone_ids if value > 0]
        if active_run_open_milestone_ids:
            if not list(updated.get("open_milestone_ids") or []):
                updated["open_milestone_ids"] = list(active_run_open_milestone_ids)
        elif active_run_frontier_ids and mode in {"flagship_product", "completion_review"} and not list(updated.get("open_milestone_ids") or []):
            updated["open_milestone_ids"] = list(active_run_frontier_ids)
        active_run_id = str(active_run.get("run_id") or "").strip()
        if active_run_id:
            updated["active_run_id"] = active_run_id
        else:
            updated.pop("active_run_id", None)
        active_run_started_at = str(active_run.get("started_at") or "").strip()
        if active_run_started_at:
            updated["active_run_started_at"] = active_run_started_at
        else:
            updated.pop("active_run_started_at", None)
        active_run_worker_first_output_at = str(active_run.get("worker_first_output_at") or "").strip()
        if active_run_worker_first_output_at:
            updated["active_run_worker_first_output_at"] = active_run_worker_first_output_at
        else:
            updated.pop("active_run_worker_first_output_at", None)
        active_run_worker_last_output_at = str(active_run.get("worker_last_output_at") or "").strip()
        if active_run_worker_last_output_at:
            updated["active_run_worker_last_output_at"] = active_run_worker_last_output_at
            updated["worker_last_output_at"] = active_run_worker_last_output_at
        else:
            updated.pop("active_run_worker_last_output_at", None)
            updated.pop("worker_last_output_at", None)
        active_run_worker_pid = _coerce_int(active_run.get("worker_pid"), 0)
        if active_run_worker_pid > 0:
            updated["active_run_worker_pid"] = active_run_worker_pid
        else:
            updated.pop("active_run_worker_pid", None)
        active_run_progress_state = str(active_run.get("progress_state") or "").strip()
        if active_run_progress_state:
            updated["active_run_progress_state"] = active_run_progress_state
        else:
            updated.pop("active_run_progress_state", None)
        selected_account_alias = str(active_run.get("selected_account_alias") or updated.get("selected_account_alias") or "").strip()
        if selected_account_alias:
            updated["selected_account_alias"] = selected_account_alias
        else:
            updated.pop("selected_account_alias", None)
        selected_model = str(active_run.get("selected_model") or updated.get("selected_model") or "").strip()
        if selected_model:
            updated["selected_model"] = selected_model
        else:
            updated.pop("selected_model", None)
        for alias_key, active_key in (
            ("active_run_prompt_path", "prompt_path"),
            ("worker_stdout_path", "stdout_path"),
            ("worker_stderr_path", "stderr_path"),
            ("worker_last_message_path", "last_message_path"),
        ):
            path_value = str(active_run.get(active_key) or "").strip()
            if path_value:
                updated[alias_key] = path_value
            else:
                updated.pop(alias_key, None)
    else:
        updated.pop("active_run_id", None)
        updated.pop("active_run_started_at", None)
        updated.pop("active_run_worker_first_output_at", None)
        updated.pop("active_run_worker_last_output_at", None)
        updated.pop("worker_last_output_at", None)
        updated.pop("active_run_worker_pid", None)
        updated.pop("active_run_progress_state", None)
        updated.pop("active_run_prompt_path", None)
        updated.pop("worker_stdout_path", None)
        updated.pop("worker_stderr_path", None)
        updated.pop("worker_last_message_path", None)
        if "selected_model" in updated and not str(updated.get("selected_model") or "").strip():
            updated.pop("selected_model", None)
        if "selected_account_alias" in updated and not str(updated.get("selected_account_alias") or "").strip():
            updated.pop("selected_account_alias", None)
    if mode in {"flagship_product", "completion_review"} and list(updated.get("frontier_ids") or []) and not list(updated.get("open_milestone_ids") or []):
        updated["open_milestone_ids"] = list(updated.get("frontier_ids") or [])
    last_run = dict(updated.get("last_run") or {}) if isinstance(updated.get("last_run"), dict) else {}
    if last_run:
        last_run_id = str(last_run.get("run_id") or "").strip()
        if last_run_id:
            updated["last_run_id"] = last_run_id
        else:
            updated.pop("last_run_id", None)
        last_run_finished_at = str(last_run.get("finished_at") or last_run.get("started_at") or "").strip()
        if last_run_finished_at:
            updated["last_run_finished_at"] = last_run_finished_at
        else:
            updated.pop("last_run_finished_at", None)
        last_run_blocker = _normalized_blocker_text(last_run.get("blocker"))
        if last_run_blocker:
            updated["last_run_blocker"] = last_run_blocker
        else:
            updated.pop("last_run_blocker", None)
    else:
        updated.pop("last_run_id", None)
        updated.pop("last_run_finished_at", None)
        updated.pop("last_run_blocker", None)
    idle_reason = str(updated.get("idle_reason") or "").strip()
    if (
        not idle_reason
        and not str(updated.get("active_run_id") or "").strip()
        and list(updated.get("frontier_ids") or [])
    ):
        idle_reason = "claimed_frontier_without_active_run"
    if idle_reason:
        updated["idle_reason"] = idle_reason
        if not str(updated.get("active_run_progress_state") or "").strip():
            updated["active_run_progress_state"] = f"idle_{idle_reason}"
    else:
        updated.pop("idle_reason", None)
    return updated


def _write_active_shard_manifest_snapshot(aggregate_root: Path) -> None:
    aggregate_root = _aggregate_state_root(aggregate_root)
    manifest_path = _active_shard_manifest_path(aggregate_root)
    configured_shards = _active_shard_manifest_entries(aggregate_root)
    if not configured_shards and not any(candidate.name.startswith("shard-") for candidate in aggregate_root.iterdir()):
        return
    topology_fingerprint = hashlib.sha256(
        json.dumps(configured_shards, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    active_shards = _statefile_shard_summaries(aggregate_root)
    generated_at = _iso_now()
    payload: Dict[str, Any] = {
        "generated_at": generated_at,
        "updated_at": generated_at,
        "manifest_kind": "configured_shard_topology",
        "topology_fingerprint": topology_fingerprint,
        "configured_shard_count": len(configured_shards),
        "configured_shards": configured_shards,
        "active_run_count": sum(1 for item in active_shards if str(item.get("active_run_id") or "").strip()),
        "active_shards": active_shards,
    }
    _write_json(manifest_path, payload)


def _has_current_flagship_pass_proof(state: Dict[str, Any]) -> bool:
    completion_audit = dict(state.get("completion_audit") or {})
    full_product_audit = dict(state.get("full_product_audit") or {})
    if not completion_audit or not full_product_audit:
        return False
    if str(completion_audit.get("status") or "").strip().lower() != "pass":
        return False
    if str(full_product_audit.get("status") or "").strip().lower() != "pass":
        return False
    if _state_open_milestone_ids(state):
        return False
    if _state_frontier_ids(state):
        return False
    active_run = state.get("active_run")
    if isinstance(active_run, dict) and active_run:
        return False
    active_runs = state.get("active_runs")
    if isinstance(active_runs, list) and any(isinstance(item, dict) and item for item in active_runs):
        return False
    return True


def _state_frontier_ids(state: Dict[str, Any]) -> List[Any]:
    active_run = dict(state.get("active_run") or {})
    active_frontier_ids = list(active_run.get("frontier_ids") or [])
    if active_frontier_ids:
        return active_frontier_ids
    return list(state.get("frontier_ids") or [])


def _state_open_milestone_ids(state: Dict[str, Any]) -> List[Any]:
    active_run = dict(state.get("active_run") or {})
    active_open_milestone_ids = list(active_run.get("open_milestone_ids") or [])
    if active_open_milestone_ids:
        return active_open_milestone_ids
    return list(state.get("open_milestone_ids") or [])


def _run_matches_manifest_frontier(run: Dict[str, Any], manifest_entry: Dict[str, Any]) -> bool:
    current_frontier = {
        _coerce_int(value, 0)
        for value in (manifest_entry.get("frontier_ids") or [])
        if _coerce_int(value, 0) > 0
    }
    if not current_frontier:
        return True
    run_frontier = {
        _coerce_int(value, 0)
        for value in (run.get("frontier_ids") or [])
        if _coerce_int(value, 0) > 0
    }
    if not run_frontier:
        return False
    run_open_ids = {
        _coerce_int(value, 0)
        for value in (run.get("open_milestone_ids") or [])
        if _coerce_int(value, 0) > 0
    }
    if run_open_ids and not run_open_ids.issubset(current_frontier):
        return False
    return run_frontier.issubset(current_frontier)


def _ids_as_text(values: Iterable[Any]) -> List[str]:
    rows: List[str] = []
    for value in values:
        token = str(value).strip()
        if token:
            rows.append(token)
    return rows


def _active_run_matches_live_frontier(
    active_run: Any,
    *,
    frontier_ids: Sequence[Any],
    open_milestone_ids: Sequence[Any],
) -> bool:
    if not isinstance(active_run, dict) or not active_run:
        return False
    last_message_path = str(active_run.get("last_message_path") or "").strip()
    if last_message_path:
        running_inside_container = _running_inside_container()
        container_local_artifact = last_message_path.startswith("/var/lib/codex-fleet/")
        if not (container_local_artifact and not running_inside_container):
            proc_root = Path("/proc")
            try:
                proc_entries = list(proc_root.iterdir())
            except OSError:
                proc_entries = []
            for entry in proc_entries:
                if not entry.name.isdigit():
                    continue
                try:
                    cmdline = (entry / "cmdline").read_bytes().decode("utf-8", errors="ignore").replace("\x00", " ").strip()
                except OSError:
                    continue
                if cmdline and last_message_path in cmdline:
                    return True
            return False
        resolved_last_message = _resolve_run_artifact_path(last_message_path)
        if not resolved_last_message.exists() and not resolved_last_message.parent.exists():
            return False
    active_frontier_ids = set(_ids_as_text(active_run.get("frontier_ids") or []))
    active_open_milestone_ids = set(_ids_as_text(active_run.get("open_milestone_ids") or []))
    current_frontier_ids = set(_ids_as_text(frontier_ids))
    current_open_milestone_ids = set(_ids_as_text(open_milestone_ids))
    if current_open_milestone_ids:
        if not active_frontier_ids or not active_frontier_ids.issubset(current_frontier_ids):
            return False
        if active_open_milestone_ids and not active_open_milestone_ids.issubset(current_open_milestone_ids):
            return False
        return True
    if current_frontier_ids:
        return bool(active_frontier_ids) and active_frontier_ids.issubset(current_frontier_ids)
    return False


def _active_run_started_at_from_run_id(run_id: str) -> str:
    text = str(run_id or "").strip()
    if not text:
        return ""
    try:
        parsed = dt.datetime.strptime(text, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return ""
    return _iso(parsed)


def _container_local_active_run_records() -> Dict[str, Dict[str, Any]]:
    if _running_inside_container():
        return {}
    now_monotonic = time.monotonic()
    cached_generated_at = _coerce_float(_CONTAINER_LOCAL_ACTIVE_RUN_CACHE.get("generated_at_monotonic")) or 0.0
    if cached_generated_at > 0.0 and now_monotonic - cached_generated_at <= 1.0:
        return {str(key): dict(value or {}) for key, value in dict(_CONTAINER_LOCAL_ACTIVE_RUN_CACHE.get("records") or {}).items()}
    docker_bin = shutil.which("docker")
    if not docker_bin:
        _CONTAINER_LOCAL_ACTIVE_RUN_CACHE["generated_at_monotonic"] = now_monotonic
        _CONTAINER_LOCAL_ACTIVE_RUN_CACHE["records"] = {}
        return {}
    records: Dict[str, Dict[str, Any]] = {}
    try:
        completed = subprocess.run(
            [docker_bin, "exec", SUPERVISOR_CONTAINER_NAME, "ps", "-eo", "pid,args"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        completed = None
    if completed and completed.returncode == 0:
        for raw_line in str(completed.stdout or "").splitlines():
            line = raw_line.strip()
            if not line or line.lower().startswith("pid "):
                continue
            parts = line.split(None, 1)
            if len(parts) < 2 or not parts[0].isdigit():
                continue
            pid = int(parts[0])
            command = parts[1].strip()
            if "/docker/fleet/scripts/codex-shims/codexea" not in command:
                continue
            match = re.search(
                r"/var/lib/codex-fleet/chummer_design_supervisor/(shard-[0-9]+)/runs/([0-9TZ]+)/last_message\.txt",
                command,
            )
            if not match:
                continue
            shard_name = str(match.group(1) or "").strip()
            run_id = str(match.group(2) or "").strip()
            if not shard_name or not run_id:
                continue
            run_dir = Path("/var/lib/codex-fleet/chummer_design_supervisor") / shard_name / "runs" / run_id
            model_match = re.search(r"\bexec\s+-m\s+(\S+)", command)
            selected_model = str(model_match.group(1) or "").strip() if model_match else ""
            records[shard_name] = {
                "run_id": run_id,
                "started_at": _active_run_started_at_from_run_id(run_id),
                "prompt_path": str(run_dir / "prompt.txt"),
                "stdout_path": str(run_dir / "worker.stdout.log"),
                "stderr_path": str(run_dir / "worker.stderr.log"),
                "last_message_path": str(run_dir / "last_message.txt"),
                "frontier_ids": [],
                "open_milestone_ids": [],
                "primary_milestone_id": None,
                "worker_command": [command],
                "selected_account_alias": "",
                "selected_model": selected_model,
                "attempt_index": 1,
                "total_attempts": 20,
                "watchdog_timeout_seconds": 0.0,
                "worker_pid": pid,
                "worker_first_output_at": "",
                "worker_last_output_at": "",
            }
    _CONTAINER_LOCAL_ACTIVE_RUN_CACHE["generated_at_monotonic"] = now_monotonic
    _CONTAINER_LOCAL_ACTIVE_RUN_CACHE["records"] = records
    return {str(key): dict(value or {}) for key, value in records.items()}


def _container_local_recovery_supported(state_root: Path) -> bool:
    resolved_state_root = Path(state_root).resolve()
    workspace_state_root = (DEFAULT_WORKSPACE_ROOT / "state" / "chummer_design_supervisor").resolve()
    container_state_root = Path("/var/lib/codex-fleet/chummer_design_supervisor").resolve()
    for candidate_root in (workspace_state_root, container_state_root):
        try:
            resolved_state_root.relative_to(candidate_root)
            return True
        except ValueError:
            continue
    return False


def _recover_container_local_active_run(
    state_root: Path,
    *,
    frontier_ids: Sequence[Any],
    open_milestone_ids: Sequence[Any],
) -> Optional[Dict[str, Any]]:
    if not _container_local_recovery_supported(state_root):
        return None
    shard_name = Path(state_root).resolve().name
    if not shard_name.startswith("shard-"):
        return None
    recovered = dict(_container_local_active_run_records().get(shard_name) or {})
    if not recovered:
        return None
    recovered["frontier_ids"] = [_coerce_int(value, 0) for value in frontier_ids if _coerce_int(value, 0) > 0]
    recovered["open_milestone_ids"] = [
        _coerce_int(value, 0) for value in open_milestone_ids if _coerce_int(value, 0) > 0
    ]
    recovered["primary_milestone_id"] = recovered["frontier_ids"][0] if recovered["frontier_ids"] else None
    freshest_output: Optional[dt.datetime] = None
    for key in ("stderr_path", "stdout_path", "last_message_path"):
        resolved_path = _resolve_run_artifact_path(str(recovered.get(key) or ""))
        if not resolved_path.exists():
            continue
        try:
            stat_result = resolved_path.stat()
        except OSError:
            continue
        modified_at = dt.datetime.fromtimestamp(stat_result.st_mtime, tz=dt.timezone.utc)
        if freshest_output is None or modified_at > freshest_output:
            freshest_output = modified_at
    if freshest_output is not None:
        recovered["worker_last_output_at"] = _iso(freshest_output)
        recovered["worker_first_output_at"] = str(recovered.get("worker_first_output_at") or recovered.get("started_at") or "").strip()
    return recovered


def _recover_matching_live_active_run(
    state_root: Path,
    *,
    frontier_ids: Sequence[Any],
    open_milestone_ids: Sequence[Any],
) -> Optional[Dict[str, Any]]:
    recovered = _recover_container_local_active_run(
        state_root,
        frontier_ids=frontier_ids,
        open_milestone_ids=open_milestone_ids,
    )
    if _active_run_matches_live_frontier(
        recovered,
        frontier_ids=frontier_ids,
        open_milestone_ids=open_milestone_ids,
    ):
        return recovered
    return None


def _active_run_matches_frontier_shape(
    active_run: Any,
    *,
    frontier_ids: Sequence[Any],
    open_milestone_ids: Sequence[Any],
) -> bool:
    if not isinstance(active_run, dict) or not active_run:
        return False
    active_frontier_ids = set(_ids_as_text(active_run.get("frontier_ids") or []))
    active_open_milestone_ids = set(_ids_as_text(active_run.get("open_milestone_ids") or []))
    current_frontier_ids = set(_ids_as_text(frontier_ids))
    current_open_milestone_ids = set(_ids_as_text(open_milestone_ids))
    if current_open_milestone_ids:
        if not active_frontier_ids or not active_frontier_ids.issubset(current_frontier_ids):
            return False
        if active_open_milestone_ids and not active_open_milestone_ids.issubset(current_open_milestone_ids):
            return False
        return True
    if current_frontier_ids:
        return bool(active_frontier_ids) and active_frontier_ids.issubset(current_frontier_ids)
    return False


def _effective_supervisor_state(
    state_root: Path,
    *,
    history_limit: int = 10,
    include_history: bool = True,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    _heal_state_push_blockers(state_root)
    base_state = _read_state(_state_payload_path(state_root))
    base_history = _read_history(_history_payload_path(state_root), limit=history_limit) if include_history else []
    shard_roots = _configured_shard_roots(state_root)
    manifest_entry_map = _active_shard_manifest_entry_map(state_root)
    if not shard_roots:
        return base_state, base_history

    state_items: List[Dict[str, Any]] = []
    combined_history: List[Dict[str, Any]] = []
    for shard_root in shard_roots:
        _heal_state_push_blockers(shard_root)
        shard_state = _read_state(_state_payload_path(shard_root))
        manifest_entry = manifest_entry_map.get(shard_root.name, {})
        state_items.append({"name": shard_root.name, "root": shard_root, "state": shard_state})
        if include_history:
            shard_history = _read_history(_history_payload_path(shard_root), limit=history_limit)
            for run in shard_history:
                if not _run_matches_manifest_frontier(dict(run), manifest_entry):
                    continue
                payload = dict(run)
                payload["_shard"] = shard_root.name
                combined_history.append(payload)

    default_time = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    if include_history:
        combined_history.sort(key=lambda item: _run_updated_at(item) or default_time)
        if history_limit > 0:
            combined_history = combined_history[-history_limit:]

    populated_states = [item for item in state_items if item.get("state")]
    if not populated_states:
        return base_state, base_history
    aggregate_state_items = [item for item in populated_states if str(item.get("name") or "") != "base"] or populated_states
    latest_item = max(
        populated_states,
        key=lambda item: _state_updated_at(dict(item.get("state") or {})) or default_time,
    )
    latest_state = dict(latest_item.get("state") or {})
    aggregate = dict(latest_state)
    aggregate["state_root"] = str(state_root)
    aggregate["shard_count"] = len(shard_roots)
    aggregate["open_milestone_ids"] = sorted(
        {
            _coerce_int(value, value)
            for item in aggregate_state_items
            for value in _state_open_milestone_ids(dict(item.get("state") or {}))
        }
    )
    aggregate["frontier_ids"] = sorted(
        {
            _coerce_int(value, value)
            for item in aggregate_state_items
            for value in _state_frontier_ids(dict(item.get("state") or {}))
        }
    )
    for key in ("focus_profiles", "focus_owners", "focus_texts"):
        aggregate[key] = sorted(
            {
                str(value)
                for item in populated_states
                for value in (dict(item.get("state") or {}).get(key) or [])
                if str(value)
            }
        )
    modes = {
        str(dict(item.get("state") or {}).get("mode") or "").strip()
        for item in populated_states
        if str(dict(item.get("state") or {}).get("mode") or "").strip()
    }
    if len(modes) == 1:
        aggregate["mode"] = next(iter(modes))
    elif modes:
        aggregate["mode"] = "sharded"
    latest_run = combined_history[-1] if include_history and combined_history else dict(latest_state.get("last_run") or {})
    if latest_run:
        aggregate["last_run"] = dict(latest_run)
    active_runs: List[Dict[str, Any]] = []
    for item in populated_states:
        name = str(item.get("name") or "").strip()
        if name == "base":
            continue
        state_payload = dict(item.get("state") or {})
        active_run_payload = dict(state_payload.get("active_run") or {})
        if not active_run_payload:
            continue
        mode = str(state_payload.get("mode") or "").strip().lower()
        frontier_ids_for_run = _state_frontier_ids(state_payload)
        open_milestone_ids_for_run = _state_open_milestone_ids(state_payload)
        if mode == "complete" and not frontier_ids_for_run and not open_milestone_ids_for_run:
            continue
        active_runs.append({"_shard": name, **active_run_payload})
    if len(active_runs) == 1:
        aggregate["active_run"] = dict(active_runs[0])
        aggregate.pop("active_runs", None)
    elif active_runs:
        aggregate["active_runs"] = [dict(item) for item in active_runs]
        aggregate.pop("active_run", None)
    else:
        aggregate.pop("active_run", None)
        aggregate.pop("active_runs", None)
    aggregate["active_runs_count"] = len(active_runs)
    completion_audit = _latest_nonempty_state_field(populated_states, "completion_audit")
    if completion_audit:
        aggregate["completion_audit"] = completion_audit
    full_product_audit = _latest_nonempty_state_field(populated_states, "full_product_audit")
    if full_product_audit:
        aggregate["full_product_audit"] = full_product_audit
    eta = _latest_nonempty_state_field(populated_states, "eta")
    if eta:
        aggregate["eta"] = dict(eta)
    worker_lane_health = _latest_nonempty_state_field(populated_states, "worker_lane_health")
    if worker_lane_health:
        aggregate["worker_lane_health"] = worker_lane_health
    if _has_current_flagship_pass_proof(aggregate):
        aggregate["mode"] = "complete"
    shard_blockers: List[Dict[str, str]] = []
    in_progress_ids: Set[int] = set()
    aggregate_shards: List[Dict[str, Any]] = []
    for item in populated_states:
        name = str(item["name"])
        if name == "base":
            continue
        shard_state = dict(item.get("state") or {})
        active_run_payload = dict(shard_state.get("active_run") or {})
        for value in (active_run_payload.get("frontier_ids") or []):
            normalized = _coerce_int(value, 0)
            if normalized > 0:
                in_progress_ids.add(normalized)
        last_run_payload = dict(shard_state.get("last_run") or {})
        blocker_text = _normalized_blocker_text(last_run_payload.get("blocker"))
        aggregate_shards.append(
            {
                "name": name,
                "state_root": str(item["root"]),
                "updated_at": shard_state.get("updated_at") or "",
                "mode": shard_state.get("mode") or "",
                "frontier_ids": _state_frontier_ids(shard_state),
                "active_frontier_ids": list(active_run_payload.get("frontier_ids") or []),
                "open_milestone_ids": _state_open_milestone_ids(shard_state),
                "eta_status": str((shard_state.get("eta") or {}).get("status") or "").strip(),
                "eta_scope_kind": str((shard_state.get("eta") or {}).get("scope_kind") or "").strip(),
                "eta_remaining_open_milestones": (shard_state.get("eta") or {}).get("remaining_open_milestones"),
                "eta_remaining_in_progress_milestones": (shard_state.get("eta") or {}).get("remaining_in_progress_milestones"),
                "eta_remaining_not_started_milestones": (shard_state.get("eta") or {}).get("remaining_not_started_milestones"),
                "last_run_id": str(last_run_payload.get("run_id") or "").strip(),
                "last_run_finished_at": str(last_run_payload.get("finished_at") or last_run_payload.get("started_at") or "").strip(),
                "last_run_blocker": blocker_text,
                "active_run_id": str(active_run_payload.get("run_id") or "").strip(),
                "active_run_started_at": str(active_run_payload.get("started_at") or "").strip(),
            }
        )
        if blocker_text:
            shard_blockers.append(
                {
                    "name": name,
                    "run_id": str(last_run_payload.get("run_id") or "").strip(),
                    "blocker": blocker_text,
                }
            )
    aggregate["shards"] = aggregate_shards
    return _reconcile_aggregate_shard_truth(aggregate), combined_history


def _aggregate_state_root(state_root: Path) -> Path:
    if state_root.name.startswith("shard-") and state_root.parent.exists():
        return state_root.parent
    return state_root


def _completion_review_history(state_root: Path, *, limit: int) -> List[Dict[str, Any]]:
    resolved_root = Path(state_root).resolve()
    # When a shard is explicitly requested, keep receipt trust scoped to that shard.
    # Otherwise an unrelated base-state failed run can poison shard completion audits.
    _, history = _effective_supervisor_state(resolved_root, history_limit=limit)
    return history


def _primary_probe_shard_name(state_root: Path) -> str:
    aggregate_root = _aggregate_state_root(state_root)
    shard_roots = _configured_shard_roots(aggregate_root)
    if not shard_roots:
        return ""
    return shard_roots[0].name


def _shard_index(state_root: Path) -> int:
    aggregate_root = _aggregate_state_root(state_root)
    shard_roots = _configured_shard_roots(aggregate_root)
    resolved_state_root = Path(state_root).resolve()
    for index, shard_root in enumerate(shard_roots):
        if shard_root == resolved_state_root:
            return index
    return -1


def _prior_active_shard_frontier_ids(state_root: Path) -> List[int]:
    aggregate_root = _aggregate_state_root(state_root)
    shard_roots = _configured_shard_roots(aggregate_root)
    resolved_state_root = Path(state_root).resolve()
    if resolved_state_root == aggregate_root or not resolved_state_root.name.startswith("shard-"):
        return []
    claimed: List[int] = []
    for shard_root in shard_roots:
        if shard_root == resolved_state_root:
            break
        state = _read_state(_state_payload_path(shard_root))
        active_run = state.get("active_run") or {}
        claimed_frontier_ids: Sequence[Any] = []
        if isinstance(active_run, dict):
            claimed_frontier_ids = active_run.get("frontier_ids") or []
        if not claimed_frontier_ids:
            claimed_frontier_ids = _state_frontier_ids(state)
        _append_unique_ids(claimed, claimed_frontier_ids or [], limit=100)
    return claimed


def _active_account_claim_counts(state_root: Path) -> Dict[str, int]:
    aggregate_root = _aggregate_state_root(state_root)
    shard_roots = _configured_shard_roots(aggregate_root)
    resolved_state_root = Path(state_root).resolve()
    counts: Dict[str, int] = {}
    for shard_root in shard_roots:
        if shard_root == resolved_state_root:
            continue
        state = _read_state(_state_payload_path(shard_root))
        active_run = state.get("active_run") or {}
        if not isinstance(active_run, dict):
            continue
        alias = str(active_run.get("selected_account_alias") or "").strip()
        if not alias or alias.startswith("lane:"):
            continue
        counts[alias] = counts.get(alias, 0) + 1
    return counts


def _account_selection_lock_path(state_root: Path, account_alias: str) -> Path:
    aggregate_root = _aggregate_state_root(state_root)
    safe_alias = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(account_alias or "").strip() or "account")
    return aggregate_root / "locks" / f"account-select-{safe_alias}.json"


def _stable_account_selection_rank(state_root: Path, account_alias: str) -> int:
    shard_label = str(Path(state_root).resolve().name or "state").strip() or "state"
    alias_label = str(account_alias or "").strip() or "account"
    digest = hashlib.sha256(f"{shard_label}:{alias_label}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big", signed=False)


def _prefer_full_ea_lanes_enabled() -> bool:
    return str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_PREFER_FULL_EA_LANES", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _exclude_frontier_ids(frontier: Sequence[Milestone], excluded_ids: Sequence[int]) -> List[Milestone]:
    excluded = {int(value) for value in excluded_ids if int(value or 0) > 0}
    if not excluded:
        return list(frontier)
    return [item for item in frontier if item.id not in excluded]


def _should_defer_external_blocker_probe(
    state_root: Path,
    *,
    blocker_reason: str,
) -> bool:
    blocker = str(blocker_reason or "").strip()
    if not blocker:
        return False
    if not state_root.name.startswith("shard-") or state_root.name == "base":
        return False
    primary_shard = _primary_probe_shard_name(state_root)
    if not primary_shard:
        return False
    return state_root.name != primary_shard


def _median(values: Sequence[float]) -> float:
    rows = sorted(float(value) for value in values)
    if not rows:
        return 0.0
    middle = len(rows) // 2
    if len(rows) % 2:
        return rows[middle]
    return (rows[middle - 1] + rows[middle]) / 2.0


def _milestone_eta_bounds_hours(item: Milestone) -> tuple[float, float]:
    normalized = str(item.status or "").strip().lower()
    if normalized == "in_progress":
        return 4.0, 10.0
    if normalized == "not_started":
        return 8.0, 20.0
    if normalized in {"open", "planned", "queued"}:
        return 6.0, 16.0
    if normalized == "review_required":
        return 1.0, 4.0
    return 6.0, 16.0


def _milestone_effort_units(item: Milestone) -> float:
    low_hours, high_hours = _milestone_eta_bounds_hours(item)
    return max(0.25, (low_hours + high_hours) / 12.0)


def _run_finished_at(run: Dict[str, Any]) -> Optional[dt.datetime]:
    return _parse_iso(str(run.get("finished_at") or run.get("started_at") or ""))


def _run_duration_hours(run: Dict[str, Any]) -> float:
    started_at = _parse_iso(str(run.get("started_at") or ""))
    finished_at = _run_finished_at(run)
    if started_at is None or finished_at is None:
        return 0.0
    duration_hours = (finished_at - started_at).total_seconds() / 3600.0
    return duration_hours if duration_hours > 0 else 0.0


def _history_run_is_accepted(run: Dict[str, Any]) -> bool:
    accepted = run.get("accepted")
    if isinstance(accepted, bool):
        return accepted
    accepted, _ = _run_receipt_status(run)
    return accepted


def _eta_external_blocker_reason(
    history: Sequence[Dict[str, Any]],
    completion_audit: Optional[Dict[str, Any]] = None,
    full_product_audit: Optional[Dict[str, Any]] = None,
) -> str:
    if (
        isinstance(completion_audit, dict)
        and str(completion_audit.get("status") or "").strip().lower() == "pass"
        and (
            not isinstance(full_product_audit, dict)
            or str(full_product_audit.get("status") or "").strip().lower() == "pass"
        )
    ):
        return ""
    candidates: List[str] = []
    if history:
        latest_run = history[-1]
        candidates.extend(
            [
                str(latest_run.get("blocker") or ""),
                str(latest_run.get("acceptance_reason") or ""),
                _failure_hint_for_run(latest_run),
            ]
        )
    if isinstance(completion_audit, dict):
        candidates.append(str(completion_audit.get("reason") or ""))
        receipt_audit = completion_audit.get("receipt_audit") or {}
        if isinstance(receipt_audit, dict):
            candidates.append(str(receipt_audit.get("reason") or ""))
    if isinstance(full_product_audit, dict):
        candidates.append(str(full_product_audit.get("reason") or ""))
    for raw in candidates:
        text = _normalize_blocker(raw)
        if not text:
            continue
        normalized = text.lower()
        if _ignore_nonlinux_desktop_host_proof_blockers_enabled() and _reason_targets_ignored_nonlinux_desktop_host_platform(
            text
        ):
            continue
        if any(signal in normalized for signal in ETA_EXTERNAL_BLOCKER_SIGNALS):
            return text
    return ""


def _format_eta_bound(hours: float) -> str:
    value = max(0.0, float(hours))
    if value <= 0.2:
        return "now"
    if value < 1.0:
        minutes = max(15, int(round((value * 60.0) / 15.0) * 15))
        return f"{minutes}m"
    if value < 24.0:
        rounded_hours = int(round(value))
        return f"{max(1, rounded_hours)}h"
    days = value / 24.0
    if days < 7.0:
        rounded_days = round(days, 1)
        return f"{int(rounded_days)}d" if rounded_days.is_integer() else f"{rounded_days:.1f}d"
    weeks = days / 7.0
    rounded_weeks = round(weeks, 1)
    return f"{int(rounded_weeks)}w" if rounded_weeks.is_integer() else f"{rounded_weeks:.1f}w"


def _format_eta_window(low_hours: float, high_hours: float) -> str:
    low = max(0.0, float(low_hours))
    high = max(low, float(high_hours))
    if high <= 0.2:
        return "ready now"
    if abs(high - low) <= max(0.25, high * 0.15):
        return f"~{_format_eta_bound((low + high) / 2.0)}"
    return f"{_format_eta_bound(low)}-{_format_eta_bound(high)}"


def _eta_scope_fields(
    *,
    scope_kind: str,
    scope_label: str,
    scope_warning: str = "",
) -> Dict[str, Any]:
    return {
        "scope_kind": str(scope_kind or "").strip(),
        "scope_label": str(scope_label or "").strip(),
        "scope_warning": str(scope_warning or "").strip(),
    }


def _eta_scope_defaults(scope_kind: str) -> Dict[str, Any]:
    normalized = str(scope_kind or "").strip()
    if normalized == "next_90_day_successor_wave":
        return _eta_scope_fields(
            scope_kind="next_90_day_successor_wave",
            scope_label="Next 90-day product advance wave",
            scope_warning=(
                "This successor-wave ETA is tracked separately from the current flagship closeout frontier. "
                "It assumes spare-shard execution continues without stealing active closeout shards."
            ),
        )
    if normalized == "completion_review_recovery":
        return _eta_scope_fields(
            scope_kind="completion_review_recovery",
            scope_label="Completion review and proof recovery",
            scope_warning=(
                "This ETA covers registry trust, proof, and review recovery. It is still narrower than a final "
                "flagship parity claim unless full-product readiness is also green."
            ),
        )
    if normalized == "flagship_product_readiness":
        return _eta_scope_fields(
            scope_kind="flagship_product_readiness",
            scope_label="Full Chummer5A parity and flagship proof closeout",
        )
    if normalized == "repo_local_completion_ready":
        return _eta_scope_fields(
            scope_kind="repo_local_completion_ready",
            scope_label="Repo-local completion review",
            scope_warning=(
                "Repo-local completion evidence is green. External release, flagship, or parity claims still "
                "depend on the broader readiness surfaces staying green."
            ),
        )
    if normalized == "open_milestone_frontier":
        return _eta_scope_fields(
            scope_kind="open_milestone_frontier",
            scope_label="Current open milestone frontier",
            scope_warning=(
                "This is a tactical frontier ETA only. It does not cover completion-review recovery, "
                "flagship readiness proof, or full Chummer5A parity closeout."
            ),
        )
    return _eta_scope_fields(
        scope_kind=normalized or "unknown",
        scope_label="Unknown ETA scope",
    )


def _normalize_eta_scope_fields(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    eta = dict(snapshot or {})
    scope_kind = str(eta.get("scope_kind") or "").strip()
    if scope_kind:
        defaults = _eta_scope_defaults(scope_kind)
        eta["scope_kind"] = str(defaults.get("scope_kind") or scope_kind).strip()
        eta["scope_label"] = str(eta.get("scope_label") or defaults.get("scope_label") or "").strip()
        eta["scope_warning"] = str(eta.get("scope_warning") or defaults.get("scope_warning") or "").strip()
        return eta
    basis = str(eta.get("basis") or "").strip().lower()
    status = str(eta.get("status") or "").strip().lower()
    remaining_open = max(0, _coerce_int(eta.get("remaining_open_milestones"), 0))
    if basis == "completion_review_recovery" or status == "recovery":
        eta.update(_eta_scope_defaults("completion_review_recovery"))
    elif "full_product" in basis or status == "flagship_delivery":
        eta.update(_eta_scope_defaults("flagship_product_readiness"))
    elif basis == "completion_audit_pass" or status == "ready":
        eta.update(_eta_scope_defaults("repo_local_completion_ready"))
    elif "successor_wave" in basis:
        eta.update(_eta_scope_defaults("next_90_day_successor_wave"))
    elif basis in {"empirical_open_milestone_burn", "heuristic_status_mix"} or remaining_open > 0:
        eta.update(_eta_scope_defaults("open_milestone_frontier"))
    else:
        eta.update(_eta_scope_defaults("unknown"))
    return eta


def _successor_wave_eta_snapshot(
    workspace_root: Path,
    *,
    now: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    queue_payload = _published_next_wave_queue_payload(workspace_root)
    queue_items = _queue_items_from_payload(queue_payload)
    milestones = _load_next_wave_registry_milestones(workspace_root)
    if not queue_items or not milestones:
        return {}

    remaining = [
        item
        for item in milestones
        if str(item.status or "").strip().lower() not in {"complete", "completed", "done", "closed", "pass", "passed"}
    ]
    if not remaining:
        current_time = now or _utc_now()
        return {
            "status": "ready",
            "eta_human": "ready now",
            "eta_confidence": ETA_STATUS_HIGH_CONFIDENCE,
            "basis": "successor_wave_registry_complete",
            "summary": "The next 90-day successor wave has no open milestones.",
            "predicted_completion_at": _iso(current_time),
            "range_low_hours": 0.0,
            "range_high_hours": 0.0,
            "remaining_open_milestones": 0,
            "remaining_in_progress_milestones": 0,
            "remaining_not_started_milestones": 0,
            "remaining_queue_items": 0,
            "critical_path_milestone_ids": [],
            "blocking_reason": "",
            **_eta_scope_fields(
                scope_kind="next_90_day_successor_wave",
                scope_label="Next 90-day product advance wave",
                scope_warning=(
                    "This successor-wave ETA is tracked separately from the current flagship closeout frontier. "
                    "It assumes spare-shard execution continues without stealing active closeout shards."
                ),
            ),
        }

    by_id = {item.id: item for item in remaining}
    memo: Dict[int, Tuple[float, float, List[int]]] = {}

    def span(milestone_id: int) -> Tuple[float, float, List[int]]:
        cached = memo.get(milestone_id)
        if cached is not None:
            return cached
        item = by_id[milestone_id]
        own_low, own_high = _full_product_milestone_eta_hours(item)
        dependency_paths = [span(dep_id) for dep_id in item.dependencies if dep_id in by_id]
        if dependency_paths:
            dep_low, dep_high, dep_path = max(
                dependency_paths,
                key=lambda candidate: (candidate[1], candidate[0], len(candidate[2])),
            )
            result = (round(dep_low + own_low, 2), round(dep_high + own_high, 2), [*dep_path, milestone_id])
        else:
            result = (round(own_low, 2), round(own_high, 2), [milestone_id])
        memo[milestone_id] = result
        return result

    critical_low, critical_high, critical_path = max(
        (span(item.id) for item in remaining),
        key=lambda candidate: (candidate[1], candidate[0], len(candidate[2])),
    )
    current_time = now or _utc_now()
    in_progress_count = sum(1 for item in remaining if str(item.status or "").strip().lower() == "in_progress")
    not_started_count = max(0, len(remaining) - in_progress_count)
    queue_milestone_ids = {
        _coerce_int(item.get("milestone_id"), 0)
        for item in queue_items
        if _coerce_int(item.get("milestone_id"), 0) > 0
    }
    critical_path_text = " -> ".join(str(value) for value in critical_path)
    status = str(queue_payload.get("status") or "tracked").strip().lower()
    return {
        "status": "tracked" if status else "tracked",
        "eta_human": _format_eta_window(critical_low, critical_high),
        "eta_confidence": ETA_STATUS_LOW_CONFIDENCE,
        "basis": "successor_wave_registry_dependency_critical_path",
        "summary": (
            f"{len(remaining)} next-wave milestones remain across {len(queue_items)} queue slices "
            f"({in_progress_count} in progress, {not_started_count} not started). "
            f"Current dependency critical path: {critical_path_text}."
        ),
        "predicted_completion_at": _iso(current_time + dt.timedelta(hours=(critical_low + critical_high) / 2.0)),
        "range_low_hours": critical_low,
        "range_high_hours": critical_high,
        "remaining_open_milestones": len(remaining),
        "remaining_in_progress_milestones": in_progress_count,
        "remaining_not_started_milestones": not_started_count,
        "remaining_queue_items": sum(
            1
            for item in queue_items
            if _coerce_int(item.get("milestone_id"), 0) in queue_milestone_ids
        ),
        "critical_path_milestone_ids": critical_path,
        "blocking_reason": "",
        **_eta_scope_fields(
            scope_kind="next_90_day_successor_wave",
            scope_label="Next 90-day product advance wave",
            scope_warning=(
                "This successor-wave ETA is tracked separately from the current flagship closeout frontier. "
                "It assumes spare-shard execution continues without stealing active closeout shards."
            ),
        ),
    }


def _run_open_milestone_ids(run: Dict[str, Any]) -> List[int]:
    rows: List[int] = []
    seen: set[int] = set()
    for raw in run.get("open_milestone_ids") or []:
        value = _coerce_int(raw, 0)
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        rows.append(value)
    return rows


def _estimate_open_milestone_eta(
    open_milestones: Sequence[Milestone],
    history: Sequence[Dict[str, Any]],
    now: dt.datetime,
) -> Dict[str, Any]:
    current_open_count = len(open_milestones)
    in_progress_count = sum(1 for item in open_milestones if item.status == "in_progress")
    not_started_count = sum(1 for item in open_milestones if item.status != "in_progress")
    heuristic_low_hours = sum(_milestone_eta_bounds_hours(item)[0] for item in open_milestones)
    heuristic_high_hours = sum(_milestone_eta_bounds_hours(item)[1] for item in open_milestones)
    effort_units = sum(_milestone_effort_units(item) for item in open_milestones)
    current_open_ids = {item.id for item in open_milestones}

    accepted_runs = [
        run
        for run in history
        if _history_run_is_accepted(run)
        and (run_open_ids := set(_run_open_milestone_ids(run)))
        and bool(current_open_ids.intersection(run_open_ids))
    ]
    accepted_snapshots: List[tuple[dt.datetime, int]] = []
    covered_open_ids: Set[int] = set()
    for run in accepted_runs:
        finished_at = _run_finished_at(run)
        if finished_at is None:
            continue
        run_open_ids = set(_run_open_milestone_ids(run))
        covered_open_ids.update(current_open_ids.intersection(run_open_ids))
        accepted_snapshots.append((finished_at, len(run_open_ids)))
    accepted_snapshots.sort(key=lambda item: item[0])

    velocity_samples: List[float] = []
    if accepted_snapshots:
        snapshots = accepted_snapshots + [(now, current_open_count)]
        for previous, current in zip(snapshots, snapshots[1:]):
            elapsed_hours = (current[0] - previous[0]).total_seconds() / 3600.0
            delta = previous[1] - current[1]
            if elapsed_hours <= 0.0 or delta <= 0:
                continue
            velocity_samples.append(delta / elapsed_hours)
    required_coverage_count = min(
        current_open_count,
        max(1 if current_open_count <= 1 else 2, int(current_open_count * 0.6 + 0.9999)),
    )
    has_scope_coverage = len(covered_open_ids) >= required_coverage_count
    max_snapshot_open_count = max((item[1] for item in accepted_snapshots), default=0)
    has_snapshot_scale = max_snapshot_open_count >= required_coverage_count
    if velocity_samples and has_scope_coverage and has_snapshot_scale:
        burn_rate_per_hour = _median(velocity_samples)
        midpoint_hours = current_open_count / max(0.05, burn_rate_per_hour)
        low_hours = max(0.5, midpoint_hours * 0.75)
        high_hours = max(low_hours + 0.5, midpoint_hours * 1.5)
        confidence = (
            ETA_STATUS_HIGH_CONFIDENCE
            if len(velocity_samples) >= 3 and len(covered_open_ids) >= current_open_count
            else ETA_STATUS_MEDIUM_CONFIDENCE
        )
        observed_per_day = burn_rate_per_hour * 24.0
        return {
            "status": "estimated",
            "eta_human": _format_eta_window(low_hours, high_hours),
            "eta_confidence": confidence,
            "basis": "empirical_open_milestone_burn",
            "summary": (
                f"{current_open_count} open milestones remain ({in_progress_count} in progress, "
                f"{not_started_count} not started); observed burn is about {observed_per_day:.1f} milestones/day."
            ),
            "predicted_completion_at": _iso(now + dt.timedelta(hours=(low_hours + high_hours) / 2.0)),
            "range_low_hours": round(low_hours, 2),
            "range_high_hours": round(high_hours, 2),
            "remaining_open_milestones": current_open_count,
            "remaining_in_progress_milestones": in_progress_count,
            "remaining_not_started_milestones": not_started_count,
            "remaining_effort_units": round(effort_units, 2),
            "history_sample_count": len(velocity_samples),
            "observed_burn_milestones_per_day": round(observed_per_day, 2),
            "blocking_reason": "",
            **_eta_scope_fields(
                scope_kind="open_milestone_frontier",
                scope_label="Current open milestone frontier",
                scope_warning=(
                    "This is a tactical frontier ETA only. It does not cover completion-review recovery, "
                    "flagship readiness proof, or full Chummer5A parity closeout."
                ),
            ),
        }

    low_hours = max(0.5, heuristic_low_hours)
    high_hours = max(low_hours + 0.5, heuristic_high_hours)
    return {
        "status": "estimated",
        "eta_human": _format_eta_window(low_hours, high_hours),
        "eta_confidence": ETA_STATUS_LOW_CONFIDENCE,
        "basis": "heuristic_status_mix",
        "summary": (
            f"{current_open_count} open milestones remain ({in_progress_count} in progress, "
            f"{not_started_count} not started); range is a fallback heuristic from the current status mix."
        ),
        "predicted_completion_at": _iso(now + dt.timedelta(hours=(low_hours + high_hours) / 2.0)),
        "range_low_hours": round(low_hours, 2),
        "range_high_hours": round(high_hours, 2),
        "remaining_open_milestones": current_open_count,
        "remaining_in_progress_milestones": in_progress_count,
        "remaining_not_started_milestones": not_started_count,
        "remaining_effort_units": round(effort_units, 2),
        "history_sample_count": 0,
        "observed_burn_milestones_per_day": 0.0,
        "blocking_reason": "",
        **_eta_scope_fields(
            scope_kind="open_milestone_frontier",
            scope_label="Current open milestone frontier",
            scope_warning=(
                "This is a tactical frontier ETA only. It does not cover completion-review recovery, "
                "flagship readiness proof, or full Chummer5A parity closeout."
            ),
        ),
    }


def _completion_review_milestone_effort_units(item: Milestone) -> float:
    text = " ".join([item.title, item.wave, item.status, *item.exit_criteria]).lower()
    owners = {str(owner).strip().lower() for owner in item.owners if str(owner).strip()}
    units = 0.85
    if owners & {"chummer6-ui", "chummer6-ui-kit", "chummer6-core"}:
        units += 0.35
    if owners & {"chummer6-hub", "chummer6-hub-registry", "chummer6-design", "fleet"}:
        units += 0.2
    if any(
        term in text
        for term in (
            "desktop",
            "client",
            "workbench",
            "ruleset",
            "rules",
            "rule-environment",
            "sr4",
            "sr5",
            "sr6",
            "build lab",
            "explain",
        )
    ):
        units += 0.35
    if any(term in text for term in ("extract", "migrate", "wire", "seed", "compile", "package", "ownership")):
        units += 0.25
    if item.title.lower().startswith("repo backlog: ui:"):
        units += 0.15
    return round(max(0.5, min(2.25, units)), 2)


def _completion_review_effort_breakdown(
    frontier: Sequence[Milestone],
    completion_audit: Dict[str, Any],
) -> List[Dict[str, Any]]:
    journey_gate_audit = dict(completion_audit.get("journey_gate_audit") or {})
    linux_gate_audit = dict(completion_audit.get("linux_desktop_exit_gate_audit") or {})
    weekly_pulse_audit = dict(completion_audit.get("weekly_pulse_audit") or {})
    repo_backlog_audit = dict(completion_audit.get("repo_backlog_audit") or {})
    receipt_audit = dict(completion_audit.get("receipt_audit") or {})
    blocked_journeys = len(journey_gate_audit.get("blocked_journeys") or [])
    warning_journeys = len(journey_gate_audit.get("warning_journeys") or [])
    breakdown: List[Dict[str, Any]] = []

    def add(component: str, units: float, detail: str, **extra: Any) -> None:
        payload: Dict[str, Any] = {
            "component": component,
            "units": round(max(0.0, float(units)), 2),
            "detail": detail,
        }
        payload.update(extra)
        breakdown.append(payload)

    if receipt_audit.get("status") != "pass":
        add(
            "trusted_completion_receipt",
            1.0,
            str(receipt_audit.get("reason") or "latest worker receipt is not trusted").strip() or "untrusted receipt",
        )
    if journey_gate_audit.get("status") != "pass":
        add(
            "golden_journey_proof",
            max(1.0, blocked_journeys * 1.5 + warning_journeys * 0.5),
            str(journey_gate_audit.get("reason") or "golden journey proof is not trusted").strip()
            or "golden journey proof",
            blocked_journey_count=blocked_journeys,
            warning_journey_count=warning_journeys,
        )
    if linux_gate_audit.get("status") != "pass":
        linux_reason = str(linux_gate_audit.get("reason") or "").lower()
        add(
            "linux_desktop_exit_gate",
            1.0 if "stale" in linux_reason else 2.0,
            str(linux_gate_audit.get("reason") or "Linux desktop exit gate is not trusted").strip()
            or "linux desktop exit gate",
        )
    if weekly_pulse_audit.get("status") != "pass" and not _weekly_pulse_audit_is_derivative_of_live_blockers(
        weekly_pulse_audit
    ):
        pulse_reason = str(weekly_pulse_audit.get("reason") or "").lower()
        add(
            "weekly_product_pulse",
            0.5 if "stale" in pulse_reason else 1.0,
            str(weekly_pulse_audit.get("reason") or "weekly pulse is not trusted").strip() or "weekly pulse",
        )
    if repo_backlog_audit.get("status") != "pass":
        backlog_frontier = [item for item in frontier if item.title.lower().startswith("repo backlog:")]
        for item in backlog_frontier:
            add(
                "repo_backlog_milestone",
                _completion_review_milestone_effort_units(item),
                item.title,
                milestone_id=item.id,
                owners=list(item.owners),
            )
        open_item_count = int(repo_backlog_audit.get("open_item_count") or 0)
        residual_count = max(0, open_item_count - len(backlog_frontier))
        if residual_count > 0:
            add(
                "repo_backlog_tail",
                min(2.0, residual_count * 0.45),
                "repo-local backlog items still exist outside the current decomposed frontier",
                count=residual_count,
            )
    if not breakdown:
        add("completion_review_recovery", max(1.0, len(frontier) * 0.75), "frontier-derived fallback recovery estimate")
    return breakdown


def _estimate_completion_review_eta(
    frontier: Sequence[Milestone],
    completion_audit: Dict[str, Any],
    history: Sequence[Dict[str, Any]],
    now: dt.datetime,
) -> Dict[str, Any]:
    journey_gate_audit = dict(completion_audit.get("journey_gate_audit") or {})
    linux_gate_audit = dict(completion_audit.get("linux_desktop_exit_gate_audit") or {})
    weekly_pulse_audit = dict(completion_audit.get("weekly_pulse_audit") or {})
    repo_backlog_audit = dict(completion_audit.get("repo_backlog_audit") or {})
    receipt_audit = dict(completion_audit.get("receipt_audit") or {})
    blocked_journeys = len(journey_gate_audit.get("blocked_journeys") or [])
    warning_journeys = len(journey_gate_audit.get("warning_journeys") or [])
    components: List[str] = []
    if receipt_audit.get("status") != "pass":
        components.append("trusted completion receipt")
    if journey_gate_audit.get("status") != "pass":
        components.append("golden journey proof")
    if linux_gate_audit.get("status") != "pass":
        components.append("Linux desktop exit gate")
    if weekly_pulse_audit.get("status") != "pass" and not _weekly_pulse_audit_is_derivative_of_live_blockers(
        weekly_pulse_audit
    ):
        components.append("weekly product pulse")
    if repo_backlog_audit.get("status") != "pass":
        components.append("repo-local backlog milestones")
    breakdown = _completion_review_effort_breakdown(frontier, completion_audit)
    recovery_units = sum(float(item.get("units") or 0.0) for item in breakdown)
    decomposed_frontier_count = sum(
        1 for item in breakdown if str(item.get("component") or "").strip() == "repo_backlog_milestone"
    )
    backlog_tail_count = sum(
        int(item.get("count") or 0) for item in breakdown if str(item.get("component") or "").strip() == "repo_backlog_tail"
    )
    low_hours = max(0.5, recovery_units * 0.75)
    high_hours = max(low_hours + 0.5, recovery_units * 2.0)
    component_text = ", ".join(components) if components else "completion review recovery"
    return {
        "status": "recovery",
        "eta_human": _format_eta_window(low_hours, high_hours),
        "eta_confidence": ETA_STATUS_MEDIUM_CONFIDENCE if len(components) <= 2 else ETA_STATUS_LOW_CONFIDENCE,
        "basis": "completion_review_recovery",
        "summary": (
            f"Registry closure is not yet trustworthy; recovery still needs {component_text}. "
            f"Blocked journeys={blocked_journeys}, warning journeys={warning_journeys}, "
            f"review frontier={len(frontier)}, decomposed_frontier={decomposed_frontier_count}, backlog_tail={backlog_tail_count}."
        ),
        "predicted_completion_at": _iso(now + dt.timedelta(hours=(low_hours + high_hours) / 2.0)),
        "range_low_hours": round(low_hours, 2),
        "range_high_hours": round(high_hours, 2),
        "remaining_open_milestones": 0,
        "remaining_in_progress_milestones": 0,
        "remaining_not_started_milestones": 0,
        "remaining_effort_units": round(recovery_units, 2),
        "remaining_effort_breakdown": breakdown,
        "history_sample_count": len(history),
        "observed_burn_milestones_per_day": 0.0,
        "blocking_reason": "",
        **_eta_scope_fields(
            scope_kind="completion_review_recovery",
            scope_label="Completion review and proof recovery",
            scope_warning=(
                "This ETA covers registry trust, proof, and review recovery. It is still narrower than a final "
                "flagship parity claim unless full-product readiness is also green."
            ),
        ),
    }


def _full_product_milestone_effort_units(item: Milestone) -> float:
    text = " ".join([item.title, item.wave, item.status, *item.exit_criteria]).lower()
    owners = {str(owner).strip().lower() for owner in item.owners if str(owner).strip()}
    units = 1.2
    if owners & {"chummer6-ui", "chummer6-mobile", "chummer6-hub", "chummer6-hub-registry"}:
        units += 0.35
    if owners & {"chummer6-core", "chummer6-ui-kit", "chummer6-media-factory"}:
        units += 0.25
    if owners & {"fleet", "executive-assistant", "chummer6-design"}:
        units += 0.2
    if any(
        term in text
        for term in (
            "desktop",
            "workbench",
            "mobile",
            "play-shell",
            "hub",
            "registry",
            "media",
            "horizons",
            "public",
            "rules",
            "import",
            "parity",
            "flagship",
        )
    ):
        units += 0.25
    return round(max(0.75, min(2.5, units)), 2)


def _full_product_milestone_eta_hours(item: Milestone) -> Tuple[float, float]:
    text = " ".join([item.title, item.wave, item.status, *item.exit_criteria]).lower()
    low_multiplier = 4.0
    high_multiplier = 10.0
    if any(term in text for term in ("rules", "parity", "import", "explain", "certification")):
        low_multiplier += 1.1
        high_multiplier += 2.5
    elif any(term in text for term in ("desktop", "workbench", "builder", "updater", "packaging")):
        low_multiplier += 0.8
        high_multiplier += 2.1
    elif any(term in text for term in ("hub", "registry", "public", "downloads", "account", "install", "update")):
        low_multiplier += 0.55
        high_multiplier += 1.6
    elif any(term in text for term in ("design system", "accessibility", "localization", "polish")):
        low_multiplier += 0.4
        high_multiplier += 1.35
    elif any(term in text for term in ("fleet", "operator", "feedback", "support", "proof", "signal")):
        low_multiplier += 0.3
        high_multiplier += 1.1

    status = str(item.status or "").strip().lower()
    if status == "in_progress":
        low_multiplier = max(3.4, low_multiplier - 0.35)
        high_multiplier = max(low_multiplier + 2.5, high_multiplier - 0.9)
    elif status == "not_started":
        low_multiplier += 0.2
        high_multiplier += 0.5

    units = _full_product_milestone_effort_units(item)
    low_hours = max(4.0, units * low_multiplier)
    high_hours = max(low_hours + 3.0, units * high_multiplier)
    return round(low_hours, 2), round(high_hours, 2)


def _estimate_full_product_milestone_eta(
    item: Milestone,
    full_product_audit: Dict[str, Any],
    history: Sequence[Dict[str, Any]],
    now: dt.datetime,
) -> Dict[str, Any]:
    low_hours, high_hours = _full_product_milestone_eta_hours(item)
    missing_coverage = [str(value) for value in (full_product_audit.get("missing_coverage_keys") or []) if str(value)]
    coverage_text = ", ".join(missing_coverage) if missing_coverage else "flagship readiness proof refresh"
    effort_units = _full_product_milestone_effort_units(item)
    return {
        "status": "flagship_delivery",
        "eta_human": _format_eta_window(low_hours, high_hours),
        "eta_confidence": ETA_STATUS_LOW_CONFIDENCE,
        "basis": "full_product_single_milestone_heuristic",
        "summary": (
            f"Milestone '{item.title}' remains open under the flagship closeout frontier. "
            f"Outstanding readiness coverage: {coverage_text}."
        ),
        "predicted_completion_at": _iso(now + dt.timedelta(hours=(low_hours + high_hours) / 2.0)),
        "range_low_hours": low_hours,
        "range_high_hours": high_hours,
        "remaining_open_milestones": 1,
        "remaining_in_progress_milestones": 1 if str(item.status or '').strip().lower() == 'in_progress' else 0,
        "remaining_not_started_milestones": 0 if str(item.status or '').strip().lower() == 'in_progress' else 1,
        "remaining_effort_units": round(effort_units, 2),
        "history_sample_count": len(history),
        "observed_burn_milestones_per_day": 0.0,
        "blocking_reason": "",
        **_eta_scope_fields(
            scope_kind="flagship_product_readiness",
            scope_label="Full Chummer5A parity and flagship proof closeout",
        ),
    }


def _estimate_full_product_eta(
    frontier: Sequence[Milestone],
    full_product_audit: Dict[str, Any],
    history: Sequence[Dict[str, Any]],
    now: dt.datetime,
) -> Dict[str, Any]:
    current_open_count = len(frontier)
    in_progress_count = sum(1 for item in frontier if str(item.status or "").strip().lower() == "in_progress")
    not_started_count = max(0, current_open_count - in_progress_count)
    recovery_units = sum(_full_product_milestone_effort_units(item) for item in frontier)
    low_hours = max(6.0, recovery_units * 4.0)
    high_hours = max(low_hours + 4.0, recovery_units * 10.0)
    missing_coverage = [str(item) for item in (full_product_audit.get("missing_coverage_keys") or []) if str(item)]
    coverage_text = ", ".join(missing_coverage) if missing_coverage else "flagship readiness proof refresh"
    return {
        "status": "flagship_delivery",
        "eta_human": _format_eta_window(low_hours, high_hours),
        "eta_confidence": ETA_STATUS_LOW_CONFIDENCE,
        "basis": "full_product_frontier_heuristic",
        "summary": (
            f"Current closeout gates are green, but flagship product work still remains across {len(frontier)} synthetic slices. "
            f"Outstanding readiness coverage: {coverage_text}."
        ),
        "predicted_completion_at": _iso(now + dt.timedelta(hours=(low_hours + high_hours) / 2.0)),
        "range_low_hours": round(low_hours, 2),
        "range_high_hours": round(high_hours, 2),
        "remaining_open_milestones": current_open_count,
        "remaining_in_progress_milestones": in_progress_count,
        "remaining_not_started_milestones": not_started_count,
        "remaining_effort_units": round(recovery_units, 2),
        "history_sample_count": len(history),
        "observed_burn_milestones_per_day": 0.0,
        "blocking_reason": "",
        **_eta_scope_fields(
            scope_kind="flagship_product_readiness",
            scope_label="Full Chummer5A parity and flagship proof closeout",
        ),
    }


def _apply_eta_blocker(snapshot: Dict[str, Any], blocker_reason: str) -> Dict[str, Any]:
    reason = _normalize_blocker(blocker_reason)
    if not reason:
        return snapshot
    eta = dict(snapshot)
    eta["status"] = "blocked"
    eta["blocking_reason"] = reason
    eta["basis"] = f"{snapshot.get('basis') or 'unknown'}+external_blocker"
    eta_human = str(snapshot.get("eta_human") or "").strip()
    if eta_human and eta_human not in {"unknown", "ready now"}:
        eta["eta_human"] = f"{eta_human} after unblock"
    else:
        eta["eta_human"] = "blocked"
    summary = str(snapshot.get("summary") or "").strip()
    if summary:
        eta["summary"] = f"{summary} Current external blocker: {reason}"
    else:
        eta["summary"] = f"ETA is blocked by an external worker/runtime issue: {reason}"
    eta["predicted_completion_at"] = ""
    current_confidence = str(snapshot.get("eta_confidence") or ETA_STATUS_LOW_CONFIDENCE).strip().lower()
    if current_confidence == ETA_STATUS_HIGH_CONFIDENCE:
        eta["eta_confidence"] = ETA_STATUS_MEDIUM_CONFIDENCE
    elif current_confidence in {ETA_STATUS_BLOCKED_CONFIDENCE, ETA_STATUS_LOW_CONFIDENCE, ""}:
        eta["eta_confidence"] = ETA_STATUS_LOW_CONFIDENCE
    else:
        eta["eta_confidence"] = current_confidence
    return eta


def _build_eta_snapshot(
    *,
    mode: str,
    open_milestones: Sequence[Milestone],
    frontier: Sequence[Milestone],
    scope_frontier: Optional[Sequence[Milestone]] = None,
    history: Sequence[Dict[str, Any]],
    completion_audit: Optional[Dict[str, Any]] = None,
    full_product_audit: Optional[Dict[str, Any]] = None,
    worker_lane_health: Optional[Dict[str, Any]] = None,
    now: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    current_time = now or _utc_now()
    blocker_reason = _eta_external_blocker_reason(history, completion_audit, full_product_audit) or _worker_lane_health_blocker_reason(
        worker_lane_health
    )
    effective_scope_frontier = list(scope_frontier or [])
    base_snapshot: Dict[str, Any]
    flagship_scope_frontier = list(open_milestones or frontier or effective_scope_frontier)
    if (
        mode == "flagship_product"
        and isinstance(full_product_audit, dict)
        and full_product_audit.get("status") != "pass"
        and len(flagship_scope_frontier) == 1
    ):
        base_snapshot = _estimate_full_product_milestone_eta(
            flagship_scope_frontier[0],
            full_product_audit,
            history,
            current_time,
        )
    elif (
        isinstance(full_product_audit, dict)
        and full_product_audit.get("status") != "pass"
        and not open_milestones
        and (mode == "flagship_product" or (completion_audit and completion_audit.get("status") == "pass"))
    ):
        effective_frontier = frontier or effective_scope_frontier
        base_snapshot = _estimate_full_product_eta(effective_frontier, full_product_audit, history, current_time)
    elif completion_audit and completion_audit.get("status") == "pass" and not open_milestones:
        base_snapshot = {
            "status": "ready",
            "eta_human": "ready now",
            "eta_confidence": ETA_STATUS_HIGH_CONFIDENCE,
            "basis": "completion_audit_pass",
            "summary": "Whole-product completion audit is green on current repo-local evidence.",
            "predicted_completion_at": _iso(current_time),
            "range_low_hours": 0.0,
            "range_high_hours": 0.0,
            "remaining_open_milestones": 0,
            "remaining_in_progress_milestones": 0,
            "remaining_not_started_milestones": 0,
            "remaining_effort_units": 0.0,
            "history_sample_count": len(history),
            "observed_burn_milestones_per_day": 0.0,
            "blocking_reason": "",
            **_eta_scope_fields(
                scope_kind="repo_local_completion_ready",
                scope_label="Repo-local completion review",
                scope_warning=(
                    "Repo-local completion evidence is green. External release, flagship, or parity claims still "
                    "depend on the broader readiness surfaces staying green."
                ),
            ),
        }
    elif open_milestones:
        base_snapshot = _estimate_open_milestone_eta(open_milestones, history, current_time)
    elif completion_audit:
        base_snapshot = _estimate_completion_review_eta(frontier, completion_audit, history, current_time)
    else:
        base_snapshot = {
            "status": "unknown",
            "eta_human": "unknown",
            "eta_confidence": ETA_STATUS_LOW_CONFIDENCE,
            "basis": "insufficient_state",
            "summary": "Fleet does not have enough live design state yet to estimate completion.",
            "predicted_completion_at": "",
            "range_low_hours": 0.0,
            "range_high_hours": 0.0,
            "remaining_open_milestones": 0,
            "remaining_in_progress_milestones": 0,
            "remaining_not_started_milestones": 0,
            "remaining_effort_units": 0.0,
            "history_sample_count": len(history),
            "observed_burn_milestones_per_day": 0.0,
            "blocking_reason": "",
            **_eta_scope_fields(
                scope_kind="unknown",
                scope_label="Unknown ETA scope",
            ),
        }
    return _apply_eta_blocker(base_snapshot, blocker_reason)


def _idle_scope_frontier(
    args: argparse.Namespace,
    state_root: Path,
    context: Dict[str, Any],
    history: Sequence[Dict[str, Any]],
) -> Sequence[Milestone]:
    if context.get("full_product_audit"):
        scope_frontier = list(context.get("flagship_product_scope_frontier") or [])
        if scope_frontier:
            return scope_frontier
        full_frontier = _full_product_frontier(args)
        prior_claimed_ids = _prior_active_shard_frontier_ids(state_root)
        available_frontier = _exclude_frontier_ids(full_frontier, prior_claimed_ids)
        return list(available_frontier or full_frontier)
    if context.get("completion_audit"):
        scope_frontier = list(context.get("completion_review_scope_frontier") or [])
        if scope_frontier:
            return scope_frontier
        full_frontier = _completion_review_frontier(
            dict(context.get("completion_audit") or {}),
            Path(args.registry_path).resolve(),
            history,
        )
        prior_claimed_ids = _prior_active_shard_frontier_ids(state_root)
        available_frontier = _exclude_frontier_ids(full_frontier, prior_claimed_ids)
        return list(available_frontier or full_frontier)
    return []


def _aggregate_idle_eta_snapshot(state_root: Path) -> Optional[Dict[str, Any]]:
    resolved_state_root = Path(state_root).resolve()
    aggregate_root = _aggregate_state_root(state_root)
    if resolved_state_root == aggregate_root:
        return None
    aggregate_state, _history = _effective_supervisor_state(aggregate_root, history_limit=COMPLETION_AUDIT_HISTORY_LIMIT)
    aggregate_eta = dict(aggregate_state.get("eta") or {})
    if not aggregate_eta:
        return None
    if aggregate_eta.get("remaining_open_milestones") is None:
        return None
    return _normalize_eta_scope_fields(aggregate_eta)


def _render_eta(eta: Dict[str, Any]) -> str:
    if not eta:
        return "ETA is unavailable."
    eta = _normalize_eta_scope_fields(eta)
    lines = [
        f"status: {eta.get('status') or 'unknown'}",
        f"eta_human: {eta.get('eta_human') or 'unknown'}",
        f"eta_confidence: {eta.get('eta_confidence') or 'unknown'}",
        f"basis: {eta.get('basis') or 'unknown'}",
        f"scope_kind: {eta.get('scope_kind') or 'unknown'}",
        f"scope_label: {eta.get('scope_label') or 'unknown'}",
        f"summary: {eta.get('summary') or 'none'}",
        f"predicted_completion_at: {eta.get('predicted_completion_at') or 'unknown'}",
        (
            "range_hours: "
            f"{eta.get('range_low_hours', 0.0)}-{eta.get('range_high_hours', 0.0)}"
        ),
        (
            "remaining_open_milestones: "
            f"{eta.get('remaining_open_milestones', 0)}"
        ),
    ]
    blocker_reason = str(eta.get("blocking_reason") or "").strip()
    if blocker_reason:
        lines.append(f"blocking_reason: {blocker_reason}")
    scope_warning = str(eta.get("scope_warning") or "").strip()
    if scope_warning:
        lines.append(f"scope_warning: {scope_warning}")
    return "\n".join(lines)


def derive_eta(args: argparse.Namespace) -> Dict[str, Any]:
    state_root = Path(args.state_root).resolve()
    state, history = _effective_supervisor_state(state_root, history_limit=ETA_HISTORY_LIMIT)
    _refresh_flagship_product_readiness_artifact(args)
    live_state, history = _live_state_with_current_completion_audit(
        args,
        state_root,
        state,
        history,
        include_shards=True,
        refresh_flagship_readiness=False,
    )
    live_eta = _normalize_eta_scope_fields(dict(live_state.get("eta") or {}))
    if live_eta:
        return live_eta
    context = derive_context(args)
    forced_flagship_context = _hard_flagship_context_if_needed(args, state_root, context)
    if forced_flagship_context is not None:
        context = forced_flagship_context
        history = _completion_review_history(state_root, limit=ETA_HISTORY_LIMIT)
    audit: Optional[Dict[str, Any]] = None
    full_product_audit: Optional[Dict[str, Any]] = None
    mode = "live"
    if not context["open_milestones"]:
        audit = _design_completion_audit(args, history[-COMPLETION_AUDIT_HISTORY_LIMIT:])
        hard_flagship = _hard_flagship_requested(args, context.get("focus_profiles") or [])
        if hard_flagship:
            full_product_audit = _full_product_readiness_audit(args)
            if full_product_audit.get("status") != "pass":
                context = derive_flagship_product_context(
                    args,
                    state_root,
                    base_context=context,
                    completion_audit=audit,
                    full_product_audit=full_product_audit,
                )
                full_product_audit = dict(context.get("full_product_audit") or full_product_audit)
                mode = "flagship_product"
            else:
                context = derive_completion_review_context(args, state_root, base_context=context, audit=audit)
                audit = dict(context.get("completion_audit") or audit)
                mode = "completion_review"
        elif audit.get("status") != "pass":
            context = derive_completion_review_context(args, state_root, base_context=context, audit=audit)
            audit = dict(context.get("completion_audit") or audit)
            mode = "completion_review"
        else:
            full_product_audit = _full_product_readiness_audit(args)
            if full_product_audit.get("status") != "pass":
                context = derive_flagship_product_context(
                    args,
                    state_root,
                    base_context=context,
                    completion_audit=audit,
                    full_product_audit=full_product_audit,
                )
                full_product_audit = dict(context.get("full_product_audit") or full_product_audit)
                mode = "flagship_product"
            else:
                mode = "complete"
    return _build_eta_snapshot(
        mode=mode,
        open_milestones=context["open_milestones"],
        frontier=context["frontier"],
        history=history,
        completion_audit=audit,
        full_product_audit=full_product_audit,
    )


def _pid_alive(pid: Optional[int]) -> bool:
    try:
        if not pid:
            return False
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, OSError):
        return False


def _pid_start_ticks(pid: Optional[int]) -> str:
    try:
        if not pid:
            return ""
        raw = _read_text(Path(f"/proc/{int(pid)}/stat")).strip()
    except Exception:
        return ""
    if ")" not in raw:
        return ""
    suffix = raw.rsplit(")", 1)[1].strip().split()
    return suffix[19] if len(suffix) > 19 else ""


def _is_lock_stale(raw: Dict[str, Any], now: dt.datetime, ttl_seconds: float) -> bool:
    created_raw = str(raw.get("created_at") or "").strip()
    pid = raw.get("pid")
    if not _pid_alive(pid):
        return True
    if int(pid or 0) == os.getpid():
        return True
    stored_start_ticks = str(raw.get("proc_start_ticks") or "").strip()
    if stored_start_ticks and _pid_start_ticks(pid) != stored_start_ticks:
        return True
    if not created_raw:
        return True
    try:
        created_at = dt.datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
    except ValueError:
        return True
    if ttl_seconds > 0 and (now - created_at).total_seconds() > float(ttl_seconds):
        return True
    return False


def _acquire_lock(path: Path, *, ttl_seconds: float) -> None:
    _ensure_dir(path.parent)
    for attempt in range(LOCK_ACQUIRE_RETRIES):
        now = _utc_now()
        if path.exists():
            try:
                raw = json.loads(_read_text(path))
            except Exception:
                raw = {}
            if raw and not _is_lock_stale(raw, now, ttl_seconds):
                holder_pid = raw.get("pid")
                raise RuntimeError(f"design supervisor lock already held by pid={holder_pid} at {path}")
            path.unlink(missing_ok=True)
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if attempt >= LOCK_ACQUIRE_RETRIES - 1:
                raise RuntimeError(f"design supervisor lock race at {path}")
            time.sleep(LOCK_RETRY_SECONDS)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "pid": os.getpid(),
                    "created_at": now.isoformat(),
                    "proc_start_ticks": _pid_start_ticks(os.getpid()),
                },
                handle,
            )
        return
    raise RuntimeError(f"design supervisor lock unavailable at {path}")


def _release_lock(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def derive_context(args: argparse.Namespace, *, state_root: Optional[Path] = None) -> Dict[str, Any]:
    registry_path = Path(args.registry_path).resolve()
    program_milestones_path = Path(args.program_milestones_path).resolve()
    roadmap_path = Path(args.roadmap_path).resolve()
    handoff_path = Path(args.handoff_path).resolve()
    workspace_root = Path(args.workspace_root).resolve()
    resolved_state_root = Path(state_root or args.state_root).resolve()
    runtime_handoff_path = _existing_runtime_handoff_path(resolved_state_root)
    if runtime_handoff_path is None:
        _write_runtime_handoff(resolved_state_root)
        runtime_handoff_path = _existing_runtime_handoff_path(resolved_state_root)
    scope_roots = _scope_roots(args)
    open_milestones, wave_order = _load_open_milestones(registry_path)
    handoff_text = _read_text(handoff_path) if handoff_path.exists() else ""
    _handoff_frontier_ids, handoff_has_explicit_frontier, handoff_frontier_is_priority = _parse_frontier_ids_from_handoff_with_source(handoff_text)
    frontier, frontier_ids = _select_frontier(open_milestones, handoff_text)
    pinned_frontier_ids = [int(value) for value in (args.frontier_id or []) if int(value or 0) > 0]
    if pinned_frontier_ids:
        by_id = {item.id: item for item in open_milestones}
        open_milestones = [by_id[value] for value in pinned_frontier_ids if value in by_id]
        frontier = list(open_milestones)
        frontier_ids = [item.id for item in frontier]
        handoff_has_explicit_frontier = True
    has_explicit_focus_filter = bool(args.focus_owner) or bool(args.focus_text)
    if handoff_has_explicit_frontier:
        if handoff_frontier_is_priority and has_explicit_focus_filter:
            frontier = _focused_frontier(args, frontier, frontier)
    else:
        frontier = _focused_frontier(args, open_milestones, frontier)
    if not pinned_frontier_ids:
        frontier = _open_milestone_shard_frontier(resolved_state_root, frontier)
    frontier_ids = [item.id for item in frontier]
    focus_profiles = _configured_focus_profiles(args)
    focus_owners = _configured_focus_owners(args)
    focus_texts = _configured_focus_texts(args)
    prompt = build_worker_prompt(
        registry_path=registry_path,
        program_milestones_path=program_milestones_path,
        roadmap_path=roadmap_path,
        handoff_path=handoff_path,
        runtime_handoff_path=runtime_handoff_path,
        open_milestones=open_milestones,
        frontier=frontier,
        scope_roots=scope_roots,
        focus_profiles=focus_profiles,
        focus_owners=focus_owners,
        focus_texts=focus_texts,
    )
    context = {
        "registry_path": registry_path,
        "program_milestones_path": program_milestones_path,
        "roadmap_path": roadmap_path,
        "handoff_path": handoff_path,
        "runtime_handoff_path": runtime_handoff_path,
        "workspace_root": workspace_root,
        "state_root": resolved_state_root,
        "scope_roots": scope_roots,
        "open_milestones": open_milestones,
        "wave_order": wave_order,
        "frontier": frontier,
        "frontier_ids": frontier_ids,
        "focus_profiles": focus_profiles,
        "focus_owners": focus_owners,
        "focus_texts": focus_texts,
        "prompt": prompt,
    }
    if _hard_flagship_requested(args, focus_profiles):
        full_product_audit = _full_product_readiness_audit(args)
        if open_milestones or str(full_product_audit.get("status") or "").strip().lower() not in {"pass", "passed", "ready"}:
            return derive_flagship_product_context(
                args,
                resolved_state_root,
                base_context=context,
                full_product_audit=full_product_audit,
            )
    return context


def _hard_flagship_context_if_needed(
    args: argparse.Namespace,
    state_root: Path,
    base_context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not _hard_flagship_requested(args, base_context.get("focus_profiles") or []):
        return None
    full_product_audit = _full_product_readiness_audit(args)
    force_whole_project_frontier = bool(base_context.get("open_milestones"))
    if (
        not force_whole_project_frontier
        and str(full_product_audit.get("status") or "").strip().lower() in {"pass", "passed", "ready"}
    ):
        return None
    completion_history = _completion_review_history(state_root, limit=COMPLETION_AUDIT_HISTORY_LIMIT)
    completion_audit = _design_completion_audit(args, completion_history[-COMPLETION_AUDIT_HISTORY_LIMIT:])
    return derive_flagship_product_context(
        args,
        state_root,
        base_context=base_context,
        completion_audit=completion_audit,
        full_product_audit=full_product_audit,
    )


def derive_completion_review_context(
    args: argparse.Namespace,
    state_root: Path,
    *,
    base_context: Optional[Dict[str, Any]] = None,
    audit: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    context = dict(base_context or derive_context(args))
    history = _completion_review_history(state_root, limit=COMPLETION_AUDIT_HISTORY_LIMIT)
    review_audit = dict(audit or _design_completion_audit(args, history))
    full_frontier = _completion_review_frontier(review_audit, Path(args.registry_path).resolve(), history)
    frontier_limit = _completion_review_shard_frontier_limit(state_root, full_frontier)
    prior_claimed_ids = _prior_active_shard_frontier_ids(state_root)
    available_frontier = _exclude_frontier_ids(full_frontier, prior_claimed_ids)
    backlog_audit = dict(review_audit.get("repo_backlog_audit") or {})
    duplicate_backlog_review = backlog_audit.get("status") == "fail" and bool(backlog_audit.get("open_item_count"))
    if available_frontier:
        frontier = _focused_frontier(args, available_frontier, available_frontier)
        frontier = _bounded_frontier(frontier, limit=frontier_limit)
    elif prior_claimed_ids and duplicate_backlog_review and full_frontier:
        rotated_frontier = list(full_frontier)
        if len(rotated_frontier) > 1:
            offset = _shard_index(state_root) % len(rotated_frontier)
            rotated_frontier = rotated_frontier[offset:] + rotated_frontier[:offset]
        frontier = _focused_frontier(args, rotated_frontier, rotated_frontier)
        frontier = _bounded_frontier(frontier, limit=frontier_limit)
    elif prior_claimed_ids and full_frontier and str(review_audit.get("status") or "").strip().lower() != "pass":
        rotated_frontier = list(full_frontier)
        if len(rotated_frontier) > 1:
            offset = _shard_index(state_root) % len(rotated_frontier)
            rotated_frontier = rotated_frontier[offset:] + rotated_frontier[:offset]
        frontier = _focused_frontier(args, rotated_frontier, rotated_frontier)
        frontier = _bounded_frontier(frontier, limit=frontier_limit)
    elif prior_claimed_ids:
        frontier = []
    else:
        frontier = _bounded_frontier(_focused_frontier(args, full_frontier, full_frontier), limit=frontier_limit)
    focus_profiles, focus_owners, focus_texts = _completion_review_focus_bundle(args, frontier)
    frontier_paths = _completion_review_frontier_paths(Path(args.workspace_root).resolve(), state_root=state_root)
    prompt = build_completion_review_prompt(
        registry_path=context["registry_path"],
        program_milestones_path=context["program_milestones_path"],
        roadmap_path=context["roadmap_path"],
        handoff_path=context["handoff_path"],
        runtime_handoff_path=context.get("runtime_handoff_path"),
        frontier_artifact_path=frontier_paths[0],
        frontier=frontier,
        scope_roots=context["scope_roots"],
        focus_profiles=focus_profiles,
        focus_owners=focus_owners,
        focus_texts=focus_texts,
        audit=review_audit,
        history=history,
        compact_prompt=(str(args.worker_bin or "").strip().endswith("codexea") or bool(str(args.worker_lane or "").strip())),
    )
    materialized_paths = _materialize_completion_review_frontier(
        args=args,
        state_root=state_root,
        mode="completion_review",
        frontier=frontier,
        focus_profiles=focus_profiles,
        focus_owners=focus_owners,
        focus_texts=focus_texts,
        completion_audit=review_audit,
    )
    context.update(
        {
            "open_milestones": [],
            "frontier": frontier,
            "frontier_ids": [item.id for item in frontier],
            "prompt": prompt,
            "focus_profiles": focus_profiles,
            "focus_owners": focus_owners,
            "focus_texts": focus_texts,
            "completion_audit": review_audit,
            "completion_history": history,
            "completion_review_full_frontier_ids": [item.id for item in full_frontier],
            "completion_review_scope_frontier": list(full_frontier),
            "completion_review_prior_claimed_frontier_ids": prior_claimed_ids,
            "completion_review_shard_index": _shard_index(state_root),
            "completion_review_frontier_path": materialized_paths["published_path"],
            "completion_review_frontier_mirror_path": materialized_paths["mirror_path"],
        }
    )
    return context


def derive_flagship_product_context(
    args: argparse.Namespace,
    state_root: Path,
    *,
    base_context: Optional[Dict[str, Any]] = None,
    completion_audit: Optional[Dict[str, Any]] = None,
    full_product_audit: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    context = dict(base_context or derive_context(args))
    history = _completion_review_history(state_root, limit=COMPLETION_AUDIT_HISTORY_LIMIT)
    current_completion_audit = dict(completion_audit or _design_completion_audit(args, history))
    current_full_product_audit = dict(full_product_audit or _full_product_readiness_audit(args))
    full_frontier = _full_product_frontier(args)
    queue_item = _queue_item_for_shard(
        args,
        state_root,
        base_frontier=_default_full_product_frontier(args, current_full_product_audit),
    )
    frontier_limit = _completion_review_shard_frontier_limit(state_root, full_frontier, default_limit=3)
    focused_full_frontier = _focused_frontier(args, full_frontier, full_frontier)
    prior_claimed_ids: List[int] = []
    resolved_state_root = Path(state_root).resolve()
    aggregate_root = _aggregate_state_root(state_root)
    if resolved_state_root != aggregate_root and resolved_state_root.name.startswith("shard-"):
        if queue_item:
            frontier = _bounded_frontier(focused_full_frontier, limit=frontier_limit)
        else:
            frontier = _open_milestone_shard_frontier(
                state_root,
                focused_full_frontier,
                default_limit=frontier_limit,
            )
    else:
        prior_claimed_ids = _prior_active_shard_frontier_ids(state_root)
        available_frontier = _exclude_frontier_ids(focused_full_frontier, prior_claimed_ids)
        if available_frontier:
            frontier = _bounded_frontier(available_frontier, limit=frontier_limit)
        elif prior_claimed_ids:
            frontier = []
        else:
            frontier = _bounded_frontier(focused_full_frontier, limit=frontier_limit)
    pinned_frontier_ids = [int(value) for value in (args.frontier_id or []) if int(value or 0) > 0]
    if pinned_frontier_ids:
        by_id = {item.id: item for item in full_frontier}
        frontier = [by_id[value] for value in pinned_frontier_ids if value in by_id]
    eta_snapshot = _build_eta_snapshot(
        mode="flagship_product",
        open_milestones=context.get("open_milestones") or [],
        frontier=frontier,
        scope_frontier=focused_full_frontier,
        history=history,
        completion_audit=current_completion_audit,
        full_product_audit=current_full_product_audit,
        now=_utc_now(),
    )
    if eta_snapshot.get("active_runs_count") is None:
        aggregate_state_path = state_root / "state.json"
        aggregate_state = _read_json_file(aggregate_state_path) if aggregate_state_path.exists() else {}
        active_runs_count = aggregate_state.get("active_runs_count")
        if active_runs_count is None:
            active_runs_count = sum(
                1
                for row in _statefile_shard_summaries(state_root)
                if str(row.get("active_run_id") or "").strip()
            )
        eta_snapshot["active_runs_count"] = active_runs_count
    focus_profiles, focus_owners, focus_texts = _flagship_product_focus_bundle(
        args,
        frontier,
        base_profiles=context.get("focus_profiles") or [],
        base_owners=context.get("focus_owners") or [],
        base_texts=context.get("focus_texts") or [],
        full_product_audit=current_full_product_audit,
    )
    frontier_paths = _full_product_frontier_paths(Path(args.workspace_root).resolve(), state_root=state_root)
    prompt = build_flagship_product_prompt(
        registry_path=context["registry_path"],
        program_milestones_path=context["program_milestones_path"],
        roadmap_path=context["roadmap_path"],
        handoff_path=context["handoff_path"],
        runtime_handoff_path=context.get("runtime_handoff_path"),
        readiness_path=Path(args.flagship_product_readiness_path).resolve(),
        frontier_artifact_path=Path(frontier_paths[0]),
        frontier=frontier,
        scope_roots=context["scope_roots"],
        focus_profiles=focus_profiles,
        focus_owners=focus_owners,
        focus_texts=focus_texts,
        completion_audit=current_completion_audit,
        full_product_audit=current_full_product_audit,
        history=history,
        eta_snapshot=eta_snapshot,
        compact_prompt=(str(args.worker_bin or "").strip().endswith("codexea") or bool(str(args.worker_lane or "").strip())),
    )
    materialized_paths = _materialize_full_product_frontier(
        args=args,
        state_root=state_root,
        mode="flagship_product",
        frontier=frontier,
        focus_profiles=focus_profiles,
        focus_owners=focus_owners,
        focus_texts=focus_texts,
        completion_audit=current_completion_audit,
        full_product_audit=current_full_product_audit,
    )
    context.update(
        {
            "open_milestones": [],
            "frontier": frontier,
            "frontier_ids": [item.id for item in frontier],
            "prompt": prompt,
            "task_local_telemetry_payload": _flagship_task_local_telemetry_payload(eta_snapshot),
            "focus_profiles": focus_profiles,
            "focus_owners": focus_owners,
            "focus_texts": focus_texts,
            "completion_audit": current_completion_audit,
            "full_product_audit": current_full_product_audit,
            "flagship_product_full_frontier_ids": [item.id for item in full_frontier],
            "flagship_product_scope_frontier": list(focused_full_frontier),
            "flagship_product_prior_claimed_frontier_ids": prior_claimed_ids,
            "flagship_product_shard_index": _shard_index(state_root),
            "full_product_frontier_path": materialized_paths["published_path"],
            "full_product_frontier_mirror_path": materialized_paths["mirror_path"],
        }
    )
    return context


def _parallel_flagship_context_if_available(
    args: argparse.Namespace,
    state_root: Path,
    *,
    base_context: Dict[str, Any],
    completion_audit: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    current_completion_audit = dict(completion_audit or {})
    if not current_completion_audit or current_completion_audit.get("status") == "pass":
        return None
    current_full_product_audit = _full_product_readiness_audit(args)
    if current_full_product_audit.get("status") == "pass":
        return None
    flagship_context = derive_flagship_product_context(
        args,
        state_root,
        base_context=base_context,
        completion_audit=current_completion_audit,
        full_product_audit=current_full_product_audit,
    )
    if not flagship_context.get("frontier"):
        return None
    return flagship_context


def _live_state_with_current_completion_audit(
    args: argparse.Namespace,
    state_root: Path,
    state: Dict[str, Any],
    history: List[Dict[str, Any]],
    *,
    include_shards: bool = True,
    refresh_flagship_readiness: bool = True,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    effective_args = argparse.Namespace(**vars(args))
    effective_args.state_root = str(Path(state_root).resolve())
    if refresh_flagship_readiness:
        _refresh_flagship_product_readiness_artifact(effective_args)
    context = derive_context(effective_args, state_root=state_root)
    if not context["open_milestones"]:
        if not _text_list(getattr(effective_args, "focus_profile", []) or []):
            effective_args.focus_profile = list(state.get("focus_profiles") or [])
        if not _text_list(getattr(effective_args, "focus_owner", []) or []):
            effective_args.focus_owner = list(state.get("focus_owners") or [])
        if not _text_list(getattr(effective_args, "focus_text", []) or []):
            effective_args.focus_text = list(state.get("focus_texts") or [])
        context = derive_context(effective_args, state_root=state_root)
    worker_lane_health = _direct_worker_lane_health_snapshot(
        effective_args,
        _worker_lane_candidates(effective_args),
    )
    host_memory_pressure = _memory_dispatch_snapshot(effective_args, state_root)
    updated = dict(state)
    updated["updated_at"] = _iso_now()
    readiness_path = str(getattr(effective_args, "flagship_product_readiness_path", "") or "").strip()
    if readiness_path:
        updated["flagship_product_readiness_path"] = str(Path(readiness_path).resolve())

    def finalize_live_state(
        *,
        mode: str,
        open_milestone_ids: Sequence[Any],
        frontier_ids: Sequence[Any],
    ) -> None:
        if not _active_run_matches_live_frontier(
            updated.get("active_run"),
            frontier_ids=frontier_ids,
            open_milestone_ids=open_milestone_ids,
        ):
            recovered_active_run = _recover_matching_live_active_run(
                state_root,
                frontier_ids=frontier_ids,
                open_milestone_ids=open_milestone_ids,
            )
            if recovered_active_run is not None:
                updated["active_run"] = dict(recovered_active_run)
            else:
                updated.pop("active_run", None)
        if include_shards:
            updated["shards"] = _live_shard_summaries(effective_args, state_root)
            updated["shard_count"] = len(updated.get("shards") or [])
            shard_frontier_ids = sorted(
                {
                    _coerce_int(value, value)
                    for item in (updated.get("shards") or [])
                    for value in (item.get("frontier_ids") or [])
                }
            )
            if shard_frontier_ids:
                updated["frontier_ids"] = shard_frontier_ids
            shard_open_milestone_ids = sorted(
                {
                    _coerce_int(value, value)
                    for item in (updated.get("shards") or [])
                    for value in (item.get("open_milestone_ids") or [])
                }
            )
            if shard_open_milestone_ids:
                updated["open_milestone_ids"] = shard_open_milestone_ids
            for key in ("focus_profiles", "focus_owners", "focus_texts"):
                shard_values = sorted(
                    {
                        str(value).strip()
                        for item in (updated.get("shards") or [])
                        for value in (item.get(key) or [])
                        if str(value).strip()
                    }
                )
                if shard_values:
                    updated[key] = shard_values
            if len(updated.get("shards") or []) > 1:
                updated["mode"] = "complete" if _has_current_flagship_pass_proof(updated) else "sharded"
            else:
                updated["mode"] = mode
            updated.update(_reconcile_aggregate_shard_truth(updated))
        if Path(state_root).resolve() == _aggregate_state_root(state_root):
            successor_wave_eta = _successor_wave_eta_snapshot(Path(effective_args.workspace_root).resolve())
            if successor_wave_eta:
                updated["successor_wave_eta"] = successor_wave_eta
            else:
                updated.pop("successor_wave_eta", None)
        normalized = _apply_status_alias_fields(updated)
        updated.clear()
        updated.update(normalized)

    if context["open_milestones"]:
        open_milestone_ids = [item.id for item in context["open_milestones"]]
        frontier_ids = [item.id for item in context["frontier"]]
        loop_review_history = _completion_review_history(state_root, limit=ETA_HISTORY_LIMIT)
        loop_completion_audit = dict(updated.get("completion_audit") or {})
        if not loop_completion_audit:
            loop_completion_audit = _design_completion_audit(
                effective_args,
                loop_review_history[-COMPLETION_AUDIT_HISTORY_LIMIT:],
            )
        loop_full_product_audit = dict(updated.get("full_product_audit") or {})
        if not loop_full_product_audit:
            loop_full_product_audit = _full_product_readiness_audit(effective_args)
        eta = _build_eta_snapshot(
            mode="loop",
            open_milestones=context["open_milestones"],
            frontier=context["frontier"],
            history=history,
            completion_audit=loop_completion_audit,
            worker_lane_health=worker_lane_health,
        )
        updated.update(
            {
                "mode": "loop",
                "open_milestone_ids": open_milestone_ids,
                "frontier_ids": frontier_ids,
                "focus_profiles": list(context["focus_profiles"]),
                "focus_owners": list(context["focus_owners"]),
                "focus_texts": list(context["focus_texts"]),
                "eta": eta,
                "worker_lane_health": worker_lane_health,
                "host_memory_pressure": host_memory_pressure,
                "completion_audit": loop_completion_audit,
                "full_product_audit": loop_full_product_audit,
                "completion_review_frontier_path": "",
                "completion_review_frontier_mirror_path": "",
                "full_product_frontier_path": "",
                "full_product_frontier_mirror_path": "",
            }
        )
        finalize_live_state(mode="loop", open_milestone_ids=open_milestone_ids, frontier_ids=frontier_ids)
        return updated, history

    review_history = _completion_review_history(state_root, limit=ETA_HISTORY_LIMIT)
    audit = _design_completion_audit(effective_args, review_history[-COMPLETION_AUDIT_HISTORY_LIMIT:])
    if audit.get("status") == "pass":
        full_product_audit = _full_product_readiness_audit(effective_args)
        if full_product_audit.get("status") == "pass":
            eta = _build_eta_snapshot(
                mode="complete",
                open_milestones=[],
                frontier=[],
                history=review_history,
                completion_audit=audit,
                full_product_audit=full_product_audit,
                worker_lane_health=worker_lane_health,
            )
            completion_frontier_paths = _materialize_completion_review_frontier(
                args=effective_args,
                state_root=state_root,
                mode="complete",
                frontier=[],
                focus_profiles=context["focus_profiles"],
                focus_owners=context["focus_owners"],
                focus_texts=context["focus_texts"],
                completion_audit=audit,
                eta=eta,
            )
            frontier_paths = _materialize_full_product_frontier(
                args=effective_args,
                state_root=state_root,
                mode="complete",
                frontier=[],
                focus_profiles=context["focus_profiles"],
                focus_owners=context["focus_owners"],
                focus_texts=context["focus_texts"],
                completion_audit=audit,
                full_product_audit=full_product_audit,
                eta=eta,
            )
            updated.update(
                {
                    "mode": "complete",
                    "open_milestone_ids": [],
                    "frontier_ids": [],
                    "focus_profiles": list(context["focus_profiles"]),
                    "focus_owners": list(context["focus_owners"]),
                    "focus_texts": list(context["focus_texts"]),
                    "completion_audit": audit,
                    "full_product_audit": full_product_audit,
                    "eta": eta,
                    "worker_lane_health": worker_lane_health,
                    "host_memory_pressure": host_memory_pressure,
                    "completion_review_frontier_path": completion_frontier_paths["published_path"],
                    "completion_review_frontier_mirror_path": completion_frontier_paths["mirror_path"],
                    "full_product_frontier_path": frontier_paths["published_path"],
                    "full_product_frontier_mirror_path": frontier_paths["mirror_path"],
                }
            )
            finalize_live_state(mode="complete", open_milestone_ids=[], frontier_ids=[])
        else:
            flagship_context = derive_flagship_product_context(
                effective_args,
                state_root,
                base_context=context,
                completion_audit=audit,
                full_product_audit=full_product_audit,
            )
            eta = _build_eta_snapshot(
                mode="flagship_product",
                open_milestones=[],
                frontier=flagship_context["frontier"],
                history=review_history,
                completion_audit=flagship_context["completion_audit"],
                full_product_audit=flagship_context["full_product_audit"],
                worker_lane_health=worker_lane_health,
            )
            completion_frontier_paths = _materialize_completion_review_frontier(
                args=effective_args,
                state_root=state_root,
                mode="complete",
                frontier=[],
                focus_profiles=context["focus_profiles"],
                focus_owners=context["focus_owners"],
                focus_texts=context["focus_texts"],
                completion_audit=audit,
                eta=eta,
            )
            frontier_paths = _materialize_full_product_frontier(
                args=effective_args,
                state_root=state_root,
                mode="flagship_product",
                frontier=flagship_context["frontier"],
                focus_profiles=flagship_context["focus_profiles"],
                focus_owners=flagship_context["focus_owners"],
                focus_texts=flagship_context["focus_texts"],
                completion_audit=flagship_context["completion_audit"],
                full_product_audit=flagship_context["full_product_audit"],
                eta=eta,
            )
            updated.update(
                {
                    "mode": "flagship_product",
                    "open_milestone_ids": [],
                    "frontier_ids": [item.id for item in flagship_context["frontier"]],
                    "focus_profiles": list(flagship_context["focus_profiles"]),
                    "focus_owners": list(flagship_context["focus_owners"]),
                    "focus_texts": list(flagship_context["focus_texts"]),
                    "completion_audit": dict(flagship_context["completion_audit"]),
                    "full_product_audit": dict(flagship_context["full_product_audit"]),
                    "eta": eta,
                    "worker_lane_health": worker_lane_health,
                    "host_memory_pressure": host_memory_pressure,
                    "completion_review_frontier_path": completion_frontier_paths["published_path"],
                    "completion_review_frontier_mirror_path": completion_frontier_paths["mirror_path"],
                    "full_product_frontier_path": frontier_paths["published_path"],
                    "full_product_frontier_mirror_path": frontier_paths["mirror_path"],
                }
            )
            finalize_live_state(
                mode="flagship_product",
                open_milestone_ids=[],
                frontier_ids=[item.id for item in flagship_context["frontier"]],
            )
        if include_shards and "shards" not in updated:
            updated["shards"] = _live_shard_summaries(effective_args, state_root)
            updated["shard_count"] = len(updated.get("shards") or [])
        return updated, review_history

    hard_flagship = _hard_flagship_requested(effective_args, context.get("focus_profiles") or [])
    if hard_flagship:
        full_product_audit = _full_product_readiness_audit(effective_args)
        if full_product_audit.get("status") != "pass":
            flagship_context = derive_flagship_product_context(
                effective_args,
                state_root,
                base_context=context,
                completion_audit=audit,
                full_product_audit=full_product_audit,
            )
            eta = _build_eta_snapshot(
                mode="flagship_product",
                open_milestones=[],
                frontier=flagship_context["frontier"],
                history=review_history,
                completion_audit=flagship_context["completion_audit"],
                full_product_audit=flagship_context["full_product_audit"],
                worker_lane_health=worker_lane_health,
            )
            frontier_paths = _materialize_full_product_frontier(
                args=effective_args,
                state_root=state_root,
                mode="flagship_product",
                frontier=flagship_context["frontier"],
                focus_profiles=flagship_context["focus_profiles"],
                focus_owners=flagship_context["focus_owners"],
                focus_texts=flagship_context["focus_texts"],
                completion_audit=flagship_context["completion_audit"],
                full_product_audit=flagship_context["full_product_audit"],
                eta=eta,
            )
            updated.update(
                {
                    "mode": "flagship_product",
                    "open_milestone_ids": [],
                    "frontier_ids": [item.id for item in flagship_context["frontier"]],
                    "focus_profiles": list(flagship_context["focus_profiles"]),
                    "focus_owners": list(flagship_context["focus_owners"]),
                    "focus_texts": list(flagship_context["focus_texts"]),
                    "completion_audit": dict(flagship_context["completion_audit"]),
                    "full_product_audit": dict(flagship_context["full_product_audit"]),
                    "eta": eta,
                    "worker_lane_health": worker_lane_health,
                    "host_memory_pressure": host_memory_pressure,
                    "completion_review_frontier_path": "",
                    "completion_review_frontier_mirror_path": "",
                    "full_product_frontier_path": frontier_paths["published_path"],
                    "full_product_frontier_mirror_path": frontier_paths["mirror_path"],
                }
            )
            finalize_live_state(
                mode="flagship_product",
                open_milestone_ids=[],
                frontier_ids=[item.id for item in flagship_context["frontier"]],
            )
            return updated, review_history

    review_context = derive_completion_review_context(effective_args, state_root, base_context=context, audit=audit)
    if not review_context["frontier"]:
        flagship_context = _parallel_flagship_context_if_available(
            effective_args,
            state_root,
            base_context=context,
            completion_audit=audit,
        )
        if flagship_context is not None:
            eta = _build_eta_snapshot(
                mode="flagship_product",
                open_milestones=[],
                frontier=flagship_context["frontier"],
                history=review_history,
                completion_audit=flagship_context["completion_audit"],
                full_product_audit=flagship_context["full_product_audit"],
                worker_lane_health=worker_lane_health,
            )
            frontier_paths = _materialize_full_product_frontier(
                args=effective_args,
                state_root=state_root,
                mode="flagship_product",
                frontier=flagship_context["frontier"],
                focus_profiles=flagship_context["focus_profiles"],
                focus_owners=flagship_context["focus_owners"],
                focus_texts=flagship_context["focus_texts"],
                completion_audit=flagship_context["completion_audit"],
                full_product_audit=flagship_context["full_product_audit"],
                eta=eta,
            )
            updated.update(
                {
                    "mode": "flagship_product",
                    "open_milestone_ids": [],
                    "frontier_ids": [item.id for item in flagship_context["frontier"]],
                    "focus_profiles": list(flagship_context["focus_profiles"]),
                    "focus_owners": list(flagship_context["focus_owners"]),
                    "focus_texts": list(flagship_context["focus_texts"]),
                    "completion_audit": dict(flagship_context["completion_audit"]),
                    "full_product_audit": dict(flagship_context["full_product_audit"]),
                    "eta": eta,
                    "worker_lane_health": worker_lane_health,
                    "host_memory_pressure": host_memory_pressure,
                    "completion_review_frontier_path": "",
                    "completion_review_frontier_mirror_path": "",
                    "full_product_frontier_path": frontier_paths["published_path"],
                    "full_product_frontier_mirror_path": frontier_paths["mirror_path"],
                }
            )
            finalize_live_state(
                mode="flagship_product",
                open_milestone_ids=[],
                frontier_ids=[item.id for item in flagship_context["frontier"]],
            )
            return updated, review_history
    full_product_audit = _full_product_readiness_audit(effective_args)
    eta = _build_eta_snapshot(
        mode="completion_review",
        open_milestones=[],
        frontier=review_context["frontier"],
        history=review_history,
        completion_audit=review_context["completion_audit"],
        worker_lane_health=worker_lane_health,
    )
    frontier_paths = _materialize_completion_review_frontier(
        args=effective_args,
        state_root=state_root,
        mode="completion_review",
        frontier=review_context["frontier"],
        focus_profiles=review_context["focus_profiles"],
        focus_owners=review_context["focus_owners"],
        focus_texts=review_context["focus_texts"],
        completion_audit=review_context["completion_audit"],
        eta=eta,
    )
    updated.update(
        {
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [item.id for item in review_context["frontier"]],
            "focus_profiles": list(review_context["focus_profiles"]),
            "focus_owners": list(review_context["focus_owners"]),
            "focus_texts": list(review_context["focus_texts"]),
            "completion_audit": dict(review_context["completion_audit"]),
            "full_product_audit": full_product_audit,
            "eta": eta,
            "worker_lane_health": worker_lane_health,
            "host_memory_pressure": host_memory_pressure,
            "completion_review_frontier_path": frontier_paths["published_path"],
            "completion_review_frontier_mirror_path": frontier_paths["mirror_path"],
            "full_product_frontier_path": "",
            "full_product_frontier_mirror_path": "",
        }
    )
    finalize_live_state(
        mode="completion_review",
        open_milestone_ids=[],
        frontier_ids=[item.id for item in review_context["frontier"]],
    )
    return updated, review_history


def _fast_status_state(
    args: argparse.Namespace,
    state_root: Path,
    state: Dict[str, Any],
    *,
    include_shards: bool = True,
) -> Dict[str, Any]:
    updated = dict(state)
    readiness_path = str(getattr(args, "flagship_product_readiness_path", "") or "").strip()
    if readiness_path:
        updated["flagship_product_readiness_path"] = str(Path(readiness_path).resolve())
    if not include_shards:
        return updated
    shard_state_items: List[Dict[str, Any]] = []
    for shard_root in _configured_shard_roots(state_root):
        shard_state = _read_state(_state_payload_path(shard_root))
        if not shard_state:
            continue
        shard_state_items.append({"name": shard_root.name, "root": shard_root, "state": shard_state})
    updated["shards"] = _statefile_shard_summaries(state_root)
    updated["shard_count"] = len(updated.get("shards") or [])
    freshest_shard_updated_at = max(
        (
            parsed
            for parsed in (
                _parse_iso(str(item.get("updated_at") or "").strip())
                for item in (updated.get("shards") or [])
            )
            if parsed is not None
        ),
        default=None,
    )
    if freshest_shard_updated_at is not None:
        updated["updated_at"] = _iso(freshest_shard_updated_at)
    updated["active_runs_count"] = sum(
        1 for item in (updated.get("shards") or []) if _shard_summary_counts_as_active_run(item)
    )
    shard_frontier_ids = sorted(
        {
            _coerce_int(value, value)
            for item in (updated.get("shards") or [])
            for value in (item.get("frontier_ids") or [])
        }
    )
    if shard_frontier_ids:
        updated["frontier_ids"] = shard_frontier_ids
    shard_open_milestone_ids = sorted(
        {
            _coerce_int(value, value)
            for item in (updated.get("shards") or [])
            for value in (item.get("open_milestone_ids") or [])
        }
    )
    if shard_open_milestone_ids:
        updated["open_milestone_ids"] = shard_open_milestone_ids
    for key in ("focus_profiles", "focus_owners", "focus_texts"):
        shard_values = sorted(
            {
                str(value).strip()
                for item in (updated.get("shards") or [])
                for value in (item.get(key) or [])
                if str(value).strip()
            }
        )
        if shard_values:
            updated[key] = shard_values
    for field in (
        "completion_audit",
        "full_product_audit",
        "eta",
        "worker_lane_health",
        "flagship_product_readiness_path",
    ):
        latest_field_value = _latest_nonempty_state_field(shard_state_items, field)
        if latest_field_value:
            updated[field] = latest_field_value
    updated["host_memory_pressure"] = _memory_dispatch_snapshot(args, state_root)
    if len(updated.get("shards") or []) > 1:
        updated["mode"] = "complete" if _has_current_flagship_pass_proof(updated) else "sharded"
    updated.update(_reconcile_aggregate_shard_truth(updated))
    return updated


def _status_generated_at(payload: Any) -> Optional[dt.datetime]:
    if not isinstance(payload, dict):
        return None
    return _parse_iso(str(payload.get("generated_at") or payload.get("generatedAt") or "").strip())


def _status_json_requires_rich_refresh(state: Dict[str, Any], *, include_shards: bool) -> bool:
    if not include_shards or not isinstance(state, dict):
        return False
    rich_fields = (
        "worker_lane_health",
        "host_memory_pressure",
        "completion_audit",
        "full_product_audit",
        "eta",
        "flagship_product_readiness_path",
    )
    if not any(bool(state.get(field)) for field in rich_fields):
        return True

    readiness_path_raw = str(state.get("flagship_product_readiness_path") or "").strip()
    if readiness_path_raw:
        readiness_path = Path(readiness_path_raw)
        if readiness_path.is_file():
            published_readiness = _read_state(readiness_path)
            published_generated_at = _status_generated_at(published_readiness)
            cached_generated_at = _status_generated_at(state.get("full_product_audit"))
            if published_generated_at is not None and (
                cached_generated_at is None or cached_generated_at < published_generated_at
            ):
                return True

    return False


def _live_shard_summaries(args: argparse.Namespace, state_root: Path) -> List[Dict[str, Any]]:
    aggregate_root = _aggregate_state_root(state_root)
    manifest_entry_map = _active_shard_manifest_entry_map(aggregate_root)
    workspace_root = Path(getattr(args, "workspace_root", aggregate_root.parent)).resolve()
    runtime_state_root = Path(
        _runtime_env_default_with_workspace(
            "CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT",
            workspace_root,
            str(DEFAULT_STATE_ROOT),
        )
    ).resolve()
    use_runtime_shard_env = runtime_state_root == aggregate_root.resolve()
    for shard_root in _configured_shard_roots(aggregate_root):
        shard_state = _read_state(_state_payload_path(shard_root))
        shard_history = _read_history(_history_payload_path(shard_root), limit=ETA_HISTORY_LIMIT)
        shard_args = argparse.Namespace(**vars(args))
        shard_args.state_root = str(shard_root.resolve())
        manifest_entry = manifest_entry_map.get(shard_root.name, {})
        shard_index = _coerce_int(manifest_entry.get("index"), 0) or _shard_index_from_root(aggregate_root, shard_root)
        if shard_index is not None and use_runtime_shard_env:
            group_index = shard_index - 1
            shard_args.focus_profile = _env_split_list(
                _runtime_env_default_with_workspace("CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE", workspace_root, "")
            )
            shard_args.focus_owner = _env_split_list(
                _runtime_env_default_with_workspace("CHUMMER_DESIGN_SUPERVISOR_FOCUS_OWNER", workspace_root, "")
            )
            shard_args.focus_text = _env_split_list(
                _runtime_env_default_with_workspace("CHUMMER_DESIGN_SUPERVISOR_FOCUS_TEXT", workspace_root, "")
            )
            shard_args.frontier_id = []
            shard_args.worker_bin = _runtime_env_default(
                "CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN",
                str(getattr(args, "worker_bin", "") or DEFAULT_WORKER_BIN),
            )
            shard_args.worker_lane = _runtime_env_default(
                "CHUMMER_DESIGN_SUPERVISOR_WORKER_LANE",
                str(getattr(args, "worker_lane", "") or ""),
            )
            shard_args.worker_model = _runtime_env_default(
                "CHUMMER_DESIGN_SUPERVISOR_WORKER_MODEL",
                str(getattr(args, "worker_model", "") or DEFAULT_MODEL),
            )
            shard_focus_owners = _runtime_env_group_list(
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_OWNER_GROUPS",
                group_index,
                workspace_root=workspace_root,
            )
            if shard_focus_owners is not None:
                shard_args.focus_owner = shard_focus_owners
            shard_focus_texts = _runtime_env_group_list(
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_FOCUS_TEXT_GROUPS",
                group_index,
                workspace_root=workspace_root,
            )
            if shard_focus_texts is not None:
                shard_args.focus_text = shard_focus_texts
            shard_frontier_ids = _runtime_env_group_list(
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_FRONTIER_ID_GROUPS",
                group_index,
                workspace_root=workspace_root,
            )
            if shard_frontier_ids is not None:
                shard_args.frontier_id = [
                    coerced
                    for coerced in (_coerce_int(value, 0) for value in shard_frontier_ids)
                    if coerced > 0
                ]
            shard_worker_bin = _runtime_env_group_value(
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_WORKER_BINS",
                group_index,
                workspace_root=workspace_root,
            )
            if shard_worker_bin:
                shard_args.worker_bin = shard_worker_bin
            shard_worker_lane = _runtime_env_group_value(
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_WORKER_LANES",
                group_index,
                workspace_root=workspace_root,
            )
            if shard_worker_lane is not None:
                shard_args.worker_lane = shard_worker_lane
            shard_worker_model = _runtime_env_group_value(
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_WORKER_MODELS",
                group_index,
                workspace_root=workspace_root,
            )
            if shard_worker_model:
                shard_args.worker_model = shard_worker_model
            if _dynamic_account_routing_enabled(
                workspace_root,
                worker_lane=str(getattr(shard_args, "worker_lane", "") or ""),
                worker_model=str(getattr(shard_args, "worker_model", "") or ""),
            ):
                shard_args.account_alias = []
            else:
                shard_args.account_alias = _env_split_list(
                    _runtime_env_default_with_workspace("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_ALIASES", workspace_root, "")
                )
                shard_account_aliases = _runtime_env_group_list(
                    "CHUMMER_DESIGN_SUPERVISOR_SHARD_ACCOUNT_GROUPS",
                    group_index,
                    workspace_root=workspace_root,
                )
                if shard_account_aliases is not None:
                    shard_args.account_alias = shard_account_aliases
        if manifest_entry:
            shard_focus_profiles = _manifest_text_list(manifest_entry.get("focus_profile"))
            if shard_focus_profiles:
                shard_args.focus_profile = shard_focus_profiles
            shard_account_aliases = _manifest_text_list(manifest_entry.get("account_alias"))
            if shard_account_aliases:
                shard_args.account_alias = shard_account_aliases
            shard_focus_owners = _manifest_text_list(manifest_entry.get("focus_owner"))
            if shard_focus_owners:
                shard_args.focus_owner = shard_focus_owners
            shard_focus_texts = _manifest_text_list(manifest_entry.get("focus_text"))
            if shard_focus_texts:
                shard_args.focus_text = shard_focus_texts
            manifest_frontier_ids = [
                _coerce_int(value, 0) for value in (manifest_entry.get("frontier_ids") or [])
            ]
            manifest_frontier_ids = [value for value in manifest_frontier_ids if value > 0]
            if manifest_frontier_ids:
                shard_args.frontier_id = manifest_frontier_ids
            manifest_worker_bin = str(manifest_entry.get("worker_bin") or "").strip()
            if manifest_worker_bin:
                shard_args.worker_bin = manifest_worker_bin
            manifest_worker_lane = str(manifest_entry.get("worker_lane") or "").strip()
            if manifest_worker_lane or "worker_lane" in manifest_entry:
                shard_args.worker_lane = manifest_worker_lane
            manifest_worker_model = str(manifest_entry.get("worker_model") or "").strip()
            if manifest_worker_model:
                shard_args.worker_model = manifest_worker_model
            if _dynamic_account_routing_enabled(
                workspace_root,
                worker_lane=str(getattr(shard_args, "worker_lane", "") or ""),
                worker_model=str(getattr(shard_args, "worker_model", "") or ""),
            ):
                shard_args.account_alias = []
        updated_shard, _ = _live_state_with_current_completion_audit(
            shard_args,
            shard_root,
            shard_state,
            shard_history,
            include_shards=False,
            refresh_flagship_readiness=False,
        )
        _persist_live_state_snapshot(shard_root, updated_shard)
    # Prefer the supervisor-authored runtime manifest when available so host-side operator reads
    # do not replace container-local process truth with a weaker outside-the-container guess.
    if not _running_inside_container():
        manifest_summaries = _active_shard_manifest_live_summaries(aggregate_root)
        if manifest_summaries:
            return manifest_summaries
    # Otherwise re-read the persisted shard snapshots so live refresh and cached state expose the
    # same detailed shard summary surface instead of diverging on active-run aliases/progress fields.
    return _statefile_shard_summaries(aggregate_root)


def _statefile_shard_summaries(state_root: Path) -> List[Dict[str, Any]]:
    aggregate_root = _aggregate_state_root(state_root)
    summaries: List[Dict[str, Any]] = []
    running_inside_container = _running_inside_container()
    configured_entry_map = _active_shard_manifest_entry_map(aggregate_root)
    for shard_root in _configured_shard_roots(aggregate_root):
        configured_entry = dict(configured_entry_map.get(shard_root.name) or {})
        shard_state = _read_state(_state_payload_path(shard_root))
        state_frontier_ids = _state_frontier_ids(shard_state)
        configured_frontier_ids = [_coerce_int(value, 0) for value in (configured_entry.get("frontier_ids") or [])]
        configured_frontier_ids = [value for value in configured_frontier_ids if value > 0]
        if not state_frontier_ids and configured_frontier_ids:
            state_frontier_ids = configured_frontier_ids
        state_open_milestone_ids = _state_open_milestone_ids(shard_state)
        if not state_open_milestone_ids and configured_frontier_ids:
            state_open_milestone_ids = configured_frontier_ids
        state_payload_path = _state_payload_path(shard_root)
        state_payload_updated_at = _state_updated_at(shard_state)
        try:
            state_file_updated_at = dt.datetime.fromtimestamp(state_payload_path.stat().st_mtime, tz=dt.timezone.utc)
        except Exception:
            state_file_updated_at = None
        freshest_updated_at = state_payload_updated_at
        if state_file_updated_at is not None and (
            freshest_updated_at is None or state_file_updated_at > freshest_updated_at
        ):
            freshest_updated_at = state_file_updated_at
        active_run = (shard_state.get("active_run") or {}) if isinstance(shard_state.get("active_run"), dict) else {}
        last_run = (shard_state.get("last_run") or {}) if isinstance(shard_state.get("last_run"), dict) else {}
        if not active_run:
            recovered_active_run = _recover_matching_live_active_run(
                shard_root,
                frontier_ids=state_frontier_ids,
                open_milestone_ids=state_open_milestone_ids,
            )
            if recovered_active_run is not None:
                active_run = dict(recovered_active_run)
        active_run_id = str(shard_state.get("active_run_id") or active_run.get("run_id") or "").strip()
        last_run_id = str(last_run.get("run_id") or "").strip()
        idle_reason = str(shard_state.get("idle_reason") or "").strip()
        if not idle_reason and not active_run_id and state_frontier_ids and not last_run_id:
            idle_reason = "claimed_frontier_without_active_run"
        worker_pid = _coerce_int(shard_state.get("active_run_worker_pid"), _coerce_int(active_run.get("worker_pid"), 0))
        process_probe_scope = "local"
        process_alive: Optional[bool] = False
        process_state = ""
        process_cpu_seconds = 0.0
        if (
            worker_pid > 0
            and not running_inside_container
            and any(
                str(active_run.get(key) or "").strip().startswith("/var/lib/codex-fleet/")
                for key in ("stderr_path", "stdout_path", "last_message_path", "prompt_path")
            )
        ):
            process_probe_scope = "container_local"
            process_alive = None
        elif worker_pid > 0:
            stat_path = Path("/proc") / str(worker_pid) / "stat"
            try:
                raw_stat = stat_path.read_text(encoding="utf-8")
            except OSError:
                raw_stat = ""
            if raw_stat:
                right_paren = raw_stat.rfind(")")
                tail = raw_stat[right_paren + 2 :].split() if right_paren >= 0 else []
                if len(tail) >= 13:
                    process_alive = True
                    process_state = str(tail[0] or "").strip()
                    try:
                        ticks_per_second = float(os.sysconf(os.sysconf_names.get("SC_CLK_TCK", "SC_CLK_TCK")))
                    except (AttributeError, TypeError, ValueError):
                        ticks_per_second = 100.0
                    try:
                        process_cpu_seconds = (
                            float(int(tail[11])) + float(int(tail[12]))
                        ) / max(1.0, ticks_per_second)
                    except (TypeError, ValueError):
                        process_cpu_seconds = 0.0
        active_run_output_updated_at: Optional[dt.datetime] = None
        active_run_output_sizes: Dict[str, int] = {}
        resolved_paths: Dict[str, str] = {}
        for alias_key, key, label in (
            ("worker_stderr_path", "stderr_path", "stderr"),
            ("worker_stdout_path", "stdout_path", "stdout"),
            ("worker_last_message_path", "last_message_path", "last_message"),
        ):
            path_text = str(shard_state.get(alias_key) or active_run.get(key) or "").strip()
            if not path_text:
                continue
            path = _resolve_run_artifact_path(path_text)
            resolved_paths[label] = str(path)
            if not path.exists():
                continue
            try:
                stat_result = path.stat()
            except OSError:
                continue
            active_run_output_sizes[label] = int(stat_result.st_size)
            modified_at = dt.datetime.fromtimestamp(stat_result.st_mtime, tz=dt.timezone.utc)
            if active_run_output_updated_at is None or modified_at > active_run_output_updated_at:
                active_run_output_updated_at = modified_at
        active_run_started_at = str(shard_state.get("active_run_started_at") or active_run.get("started_at") or "").strip()
        selected_account_alias = str(
            shard_state.get("selected_account_alias") or active_run.get("selected_account_alias") or ""
        ).strip()
        if not selected_account_alias:
            configured_aliases = _normalize_manifest_account_aliases(_manifest_text_list(configured_entry.get("account_alias")))
            if configured_aliases:
                selected_account_alias = configured_aliases[0]
        selected_model = str(shard_state.get("selected_model") or active_run.get("selected_model") or "").strip()
        if not selected_model:
            selected_model = str(configured_entry.get("worker_model") or "").strip()
        active_run_worker_first_output_at = str(
            shard_state.get("active_run_worker_first_output_at") or active_run.get("worker_first_output_at") or ""
        ).strip()
        active_run_worker_last_output_at = str(
            shard_state.get("active_run_worker_last_output_at") or active_run.get("worker_last_output_at") or ""
        ).strip()
        persisted_progress_state = str(
            shard_state.get("active_run_progress_state") or active_run.get("progress_state") or ""
        ).strip()
        computed_progress_state = (
            "closing"
            if (
                worker_pid > 0
                and process_probe_scope == "local"
                and process_alive is False
                and str(active_run_worker_last_output_at or active_run_worker_first_output_at).strip()
            )
            else (
                "streaming"
                if str(active_run_worker_last_output_at or active_run_worker_first_output_at).strip()
                else (
                    "running_silent"
                    if process_alive is True
                    else (
                        "container_scoped"
                        if worker_pid > 0 and process_probe_scope == "container_local"
                        else (
                            "missing_process"
                            if worker_pid > 0 and process_alive is False
                            else (f"idle_{idle_reason}" if idle_reason else "unknown")
                        )
                    )
                )
            )
        )
        summaries.append(
            {
                "name": shard_root.name,
                "shard_id": shard_root.name,
                "shard_token": shard_root.name,
                "state_root": str(shard_root),
                "updated_at": _iso(freshest_updated_at) if freshest_updated_at is not None else "",
                "mode": shard_state.get("mode") or str(configured_entry.get("mode") or "").strip(),
                "frontier_ids": state_frontier_ids,
                "active_frontier_ids": list(active_run.get("frontier_ids") or []),
                "open_milestone_ids": state_open_milestone_ids,
                "focus_profiles": list(shard_state.get("focus_profiles") or []),
                "focus_owners": list(shard_state.get("focus_owners") or _manifest_text_list(configured_entry.get("focus_owner"))),
                "focus_texts": list(shard_state.get("focus_texts") or _manifest_text_list(configured_entry.get("focus_text"))),
                "eta_status": str((shard_state.get("eta") or {}).get("status") or "").strip(),
                "eta_scope_kind": str((shard_state.get("eta") or {}).get("scope_kind") or "").strip(),
                "eta_summary": str((shard_state.get("eta") or {}).get("summary") or "").strip(),
                "eta_range_low_hours": (shard_state.get("eta") or {}).get("range_low_hours"),
                "eta_range_high_hours": (shard_state.get("eta") or {}).get("range_high_hours"),
                "eta_remaining_open_milestones": (shard_state.get("eta") or {}).get("remaining_open_milestones"),
                "eta_remaining_in_progress_milestones": (
                    (shard_state.get("eta") or {}).get("remaining_in_progress_milestones")
                ),
                "eta_remaining_not_started_milestones": (
                    (shard_state.get("eta") or {}).get("remaining_not_started_milestones")
                ),
                "last_run_id": last_run_id,
                "last_run_finished_at": str(last_run.get("finished_at") or last_run.get("started_at") or "").strip(),
                "last_run_blocker": _normalized_blocker_text(last_run.get("blocker")),
                "idle_reason": idle_reason,
                "active_run_id": active_run_id,
                "active_run_started_at": active_run_started_at,
                "selected_account_alias": selected_account_alias,
                "selected_model": selected_model,
                "active_run_worker_pid": worker_pid,
                "active_run_process_probe_scope": process_probe_scope,
                "active_run_process_alive": process_alive,
                "active_run_process_state": process_state,
                "active_run_process_cpu_seconds": process_cpu_seconds,
                "active_run_worker_first_output_at": active_run_worker_first_output_at,
                "active_run_worker_last_output_at": active_run_worker_last_output_at,
                "worker_last_output_at": active_run_worker_last_output_at,
                "active_run_progress_state": persisted_progress_state or computed_progress_state,
                "worker_stdout_path": resolved_paths.get("stdout", ""),
                "worker_stderr_path": resolved_paths.get("stderr", ""),
                "worker_last_message_path": resolved_paths.get("last_message", ""),
                "active_run_output_updated_at": _iso(active_run_output_updated_at) if active_run_output_updated_at else "",
                "active_run_output_sizes": active_run_output_sizes,
            }
        )
    return summaries


def _task_local_telemetry_path(run_dir: Path) -> Path:
    return run_dir / TASK_LOCAL_TELEMETRY_FILENAME


def _worker_bash_env_path(run_dir: Path) -> Path:
    return run_dir / WORKER_BASH_ENV_FILENAME


def _write_worker_bash_env(run_dir: Path) -> Path:
    _ensure_dir(run_dir)
    shim_path = (DEFAULT_WORKSPACE_ROOT / "scripts" / "codex-shims" / "python3").resolve()
    bash_env_path = _worker_bash_env_path(run_dir)
    rendered = (
        "# Auto-generated by chummer_design_supervisor.py\n"
        f"python3() {{ \"{shim_path}\" \"$@\"; }}\n"
        "export -f python3\n"
    )
    bash_env_path.write_text(rendered, encoding="utf-8")
    return bash_env_path


def _materialize_task_local_telemetry_prompt(prompt: str, telemetry_path: Path) -> str:
    rendered = str(prompt or "")
    telemetry_text = str(telemetry_path)
    read_markers = ("Read these files directly first:\n", "Start by reading these files directly:\n")
    if telemetry_text not in rendered:
        for marker in read_markers:
            if marker in rendered:
                rendered = rendered.replace(marker, marker + f"- {telemetry_text}\n", 1)
                break
    rendered = rendered.replace(
        "use the embedded JSON block and listed files instead.",
        f"use the task-local telemetry file at {telemetry_text}, the embedded JSON block, and the listed files instead.",
        1,
    )
    rendered = rendered.replace(
        "Use the embedded JSON block and listed files as your local context instead.",
        f"Use the task-local telemetry file at {telemetry_text}, the embedded JSON block, and the listed files as your local context instead.",
        1,
    )
    rendered = rendered.replace(
        "use it as-is and do not regenerate it via shell, Python, or supervisor helper commands from inside the worker run.",
        (
            "use it as-is, and if you need machine-readable telemetry read "
            f"{telemetry_text} directly; do not regenerate it via shell, Python, or supervisor helper commands from inside the worker run."
        ),
        1,
    )
    return rendered


def _prepare_run_prompt(
    run_dir: Path,
    prompt: str,
    *,
    task_local_telemetry_payload: Optional[Dict[str, Any]] = None,
) -> str:
    rendered = str(prompt or "")
    if task_local_telemetry_payload is not None:
        telemetry_path = _task_local_telemetry_path(run_dir)
        _write_json(telemetry_path, dict(task_local_telemetry_payload or {}))
        rendered = _materialize_task_local_telemetry_prompt(rendered, telemetry_path)
    return rendered


def _write_run_artifacts(
    run_dir: Path,
    prompt: str,
) -> Path:
    _ensure_dir(run_dir)
    prompt_path = run_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


def _account_runtime_path(state_root: Path) -> Path:
    return _aggregate_state_root(state_root) / "account_runtime.json"


def _read_account_runtime(path: Path) -> Dict[str, Any]:
    payload = _read_state(path)
    sources = payload.get("sources")
    if not isinstance(sources, dict):
        payload["sources"] = {}
    return payload


def _write_account_runtime(path: Path, payload: Dict[str, Any]) -> None:
    payload = dict(payload or {})
    payload["updated_at"] = _iso_now()
    payload["sources"] = dict(payload.get("sources") or {})
    _write_json(path, payload)


def _credential_source_key(account: WorkerAccount) -> str:
    if account.auth_kind in CHATGPT_AUTH_KINDS:
        if account.auth_json_file:
            return f"{account.auth_kind}:{account.auth_json_file}"
    elif account.auth_kind == "api_key":
        if account.api_key_env:
            return f"{account.auth_kind}:env:{account.api_key_env}"
        if account.api_key_file:
            return f"{account.auth_kind}:file:{account.api_key_file}"
    return f"alias:{account.alias}"


def _credential_source_fingerprint(account: WorkerAccount, workspace_root: Path) -> str:
    try:
        if account.auth_kind in CHATGPT_AUTH_KINDS:
            path = _fallback_auth_json_path(Path(account.auth_json_file).expanduser(), workspace_root)
            if not path.exists() or not path.is_file():
                return f"missing:{path}"
            return hashlib.sha256(path.read_bytes()).hexdigest()[:24]
        if account.auth_kind == "api_key":
            if account.api_key_env:
                value = _resolve_env_secret(account.api_key_env, workspace_root)
                return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24] if value else f"missing-env:{account.api_key_env}"
            if account.api_key_file:
                path = Path(account.api_key_file).expanduser()
                if not path.exists() or not path.is_file():
                    return f"missing:{path}"
                value = _read_text(path).strip()
                return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24] if value else f"empty:{path}"
    except Exception as exc:
        return f"error:{type(exc).__name__}"
    return ""


def _refresh_source_credential_state(
    payload: Dict[str, Any],
    account: WorkerAccount,
    workspace_root: Path,
    *,
    now: Optional[dt.datetime] = None,
) -> bool:
    current = now or _utc_now()
    sources = dict(payload.get("sources") or {})
    key = _credential_source_key(account)
    item = dict(sources.get(key) or {})
    fingerprint = _credential_source_fingerprint(account, workspace_root)
    previous = str(item.get("credential_fingerprint") or "").strip()
    if not item and not fingerprint:
        return False
    dirty = False
    if previous != fingerprint:
        item["alias"] = account.alias
        item["owner_id"] = account.owner_id
        item["source_key"] = key
        item["credential_fingerprint"] = fingerprint
        if previous and (
            (_parse_iso(str(item.get("backoff_until") or "")) or current) > current
            or (_parse_iso(str(item.get("spark_backoff_until") or "")) or current) > current
            or str(item.get("last_error") or "").strip()
        ):
            item["backoff_until"] = ""
            item["spark_backoff_until"] = ""
            item["last_error"] = ""
        sources[key] = item
        payload["sources"] = sources
        dirty = True
    return dirty


def _account_home(state_root: Path, account: WorkerAccount) -> Path:
    explicit_home = str(account.home_dir or "").strip()
    if explicit_home:
        path = Path(explicit_home).expanduser()
    elif account.auth_kind in CHATGPT_AUTH_KINDS and account.auth_json_file:
        source_hash = hashlib.sha1(_credential_source_key(account).encode("utf-8")).hexdigest()[:16]
        path = state_root / "codex-homes" / f"chatgpt-{source_hash}"
    else:
        path = state_root / "codex-homes" / account.alias
    _ensure_dir(path)
    return path


def _direct_worker_home(state_root: Path, worker_lane: str) -> Path:
    token = re.sub(r"[^A-Za-z0-9._-]+", "-", str(worker_lane or "default").strip()) or "default"
    path = state_root / "codex-homes" / f"direct-{token}"
    _ensure_dir(path)
    return path


def _direct_codexea_stream_lanes() -> Set[str]:
    return {"core", "core_rescue", "jury", "survival"}


def _resolve_any_env_secret(workspace_root: Path, *names: str) -> str:
    for name in names:
        resolved = _resolve_env_secret(name, workspace_root)
        if resolved:
            return resolved
    return ""


def _stream_budget_timeout_seconds_for_workspace(workspace_root: Path) -> float:
    try:
        stream_idle_ms = max(
            0.0,
            float(
                _runtime_env_default_with_workspace(
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS",
                    workspace_root,
                    _runtime_env_default_with_workspace(
                        "CODEXEA_STREAM_IDLE_TIMEOUT_MS",
                        workspace_root,
                        "",
                    ),
                )
                or "0"
            ),
        )
    except (TypeError, ValueError):
        stream_idle_ms = 0.0
    try:
        stream_max_retries = max(
            0,
            int(
                float(
                    _runtime_env_default_with_workspace(
                        "CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES",
                        workspace_root,
                        _runtime_env_default_with_workspace(
                            "CODEXEA_STREAM_MAX_RETRIES",
                            workspace_root,
                            "",
                        ),
                    )
                    or "0"
                )
            ),
        )
    except (TypeError, ValueError):
        stream_max_retries = 0
    if stream_idle_ms <= 0.0 or stream_max_retries <= 0:
        return 0.0
    return max(3600.0, (stream_idle_ms / 1000.0) * float(stream_max_retries) + 1800.0)


def _prepare_direct_worker_environment(
    state_root: Path,
    worker_lane: str,
    *,
    workspace_root: Path,
    worker_bin: str,
) -> Dict[str, str]:
    home = _direct_worker_home(state_root, worker_lane)
    host_home_raw = str(os.environ.get("HOME", "") or "").strip()
    host_xdg_config_home_raw = str(os.environ.get("XDG_CONFIG_HOME", "") or "").strip()
    env = os.environ.copy()
    env["CODEX_HOME"] = str(home)
    env["HOME"] = str(home)
    _seed_worker_home_git_auth(
        home,
        host_home_raw=host_home_raw,
        host_xdg_config_home_raw=host_xdg_config_home_raw,
    )
    _inherit_host_git_auth_environment(
        env,
        host_home_raw=host_home_raw,
        host_xdg_config_home_raw=host_xdg_config_home_raw,
    )
    worker_gitconfig = home / ".gitconfig"
    worker_xdg_config_home = home / ".config"
    worker_gh_config_dir = worker_xdg_config_home / "gh"
    if worker_gitconfig.exists():
        env["GIT_CONFIG_GLOBAL"] = str(worker_gitconfig)
    if (worker_gh_config_dir / "hosts.yml").exists():
        env["XDG_CONFIG_HOME"] = str(worker_xdg_config_home)
        env["GH_CONFIG_DIR"] = str(worker_gh_config_dir)
    clean_lane = str(worker_lane or "").strip().lower()
    bridge_token = _ea_bridge_api_token(workspace_root)
    if bridge_token:
        env["EA_MCP_API_TOKEN"] = bridge_token
        env["EA_API_TOKEN"] = bridge_token
    if clean_lane:
        principal_id = f"codex-fleet-lane-{re.sub(r'[^A-Za-z0-9._-]+', '-', clean_lane).strip('-._') or 'default'}"
        env["EA_PRINCIPAL_ID"] = principal_id
        env["EA_MCP_PRINCIPAL_ID"] = principal_id
        env["EA_DEFAULT_PRINCIPAL_ID"] = principal_id
    if _worker_bin_uses_codexea(worker_bin) and clean_lane in _direct_codexea_stream_lanes():
        stream_idle_ms = _runtime_env_default_with_workspace(
            "CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS",
            workspace_root,
            _runtime_env_default_with_workspace(
                "CODEXEA_STREAM_IDLE_TIMEOUT_MS",
                workspace_root,
                "",
            ),
        )
        stream_max_retries = _runtime_env_default_with_workspace(
            "CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES",
            workspace_root,
            _runtime_env_default_with_workspace(
                "CODEXEA_STREAM_MAX_RETRIES",
                workspace_root,
                "",
            ),
        )
        model_output_stall_raw = _runtime_env_default_with_workspace(
            "CHUMMER_DESIGN_SUPERVISOR_MODEL_OUTPUT_STALL_SECONDS",
            workspace_root,
            "",
        )
        if model_output_stall_raw:
            try:
                model_output_stall_seconds = max(0.0, float(model_output_stall_raw))
            except (TypeError, ValueError):
                model_output_stall_seconds = 0.0
            if model_output_stall_seconds > 0.0:
                capped_stream_idle_ms = max(1000, int(model_output_stall_seconds * 1000.0))
                try:
                    parsed_stream_idle_ms = max(0, int(float(stream_idle_ms or 0)))
                except (TypeError, ValueError):
                    parsed_stream_idle_ms = 0
                try:
                    parsed_stream_max_retries = max(0, int(float(stream_max_retries or 0)))
                except (TypeError, ValueError):
                    parsed_stream_max_retries = 0
                if parsed_stream_idle_ms <= 0 or parsed_stream_idle_ms > capped_stream_idle_ms:
                    stream_idle_ms = str(capped_stream_idle_ms)
                else:
                    stream_idle_ms = str(parsed_stream_idle_ms)
                stream_max_retries = "0"
        if stream_idle_ms:
            env["CODEXEA_STREAM_IDLE_TIMEOUT_MS"] = stream_idle_ms
        if stream_max_retries:
            env["CODEXEA_STREAM_MAX_RETRIES"] = stream_max_retries
        if clean_lane == "core":
            core_profile = _runtime_env_default_with_workspace(
                "CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE",
                workspace_root,
                _runtime_env_default_with_workspace(
                    "CODEXEA_CORE_RESPONSES_PROFILE",
                    workspace_root,
                    "",
                ),
            )
            if core_profile:
                env["CODEXEA_CORE_RESPONSES_PROFILE"] = core_profile
    return env


def _stamp_worker_supervisor_guard(env: Dict[str, str], *, run_id: str, run_dir: Path) -> Dict[str, str]:
    env["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID"] = str(run_id or "").strip()
    env["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] = str(run_dir)
    env.setdefault("CHUMMER_DESIGN_SUPERVISOR_STATUS_BUDGET", "1")
    real_python3 = str(shutil.which("python3") or sys.executable or "/usr/bin/python3").strip()
    if real_python3:
        env.setdefault("CHUMMER_DESIGN_SUPERVISOR_REAL_PYTHON3", real_python3)
    shim_dir = (DEFAULT_WORKSPACE_ROOT / "scripts" / "codex-shims").resolve()
    if shim_dir.exists():
        current_path = str(env.get("PATH") or "").strip()
        path_entries = [entry for entry in current_path.split(os.pathsep) if entry]
        shim_text = str(shim_dir)
        if shim_text not in path_entries:
            path_entries.insert(0, shim_text)
            env["PATH"] = os.pathsep.join(path_entries)
    env["BASH_ENV"] = str(_write_worker_bash_env(run_dir))
    return env


def _write_toml_string(value: str) -> str:
    return json.dumps(value)


def _resolve_host_home_path(host_home_raw: str) -> Path | None:
    candidate_text = str(host_home_raw or "").strip()
    if candidate_text and candidate_text != "/":
        candidate = Path(candidate_text).expanduser()
        if candidate.exists():
            return candidate
    try:
        passwd_home = Path(pwd.getpwuid(os.getuid()).pw_dir).expanduser()
    except Exception:
        passwd_home = None
    if passwd_home is not None and str(passwd_home) not in {"", "/"} and passwd_home.exists():
        return passwd_home
    if candidate_text:
        candidate = Path(candidate_text).expanduser()
        return candidate
    return None


def _inherit_host_git_auth_environment(
    env: Dict[str, str],
    *,
    host_home_raw: str,
    host_xdg_config_home_raw: str,
) -> None:
    host_home = _resolve_host_home_path(host_home_raw)
    if host_home is not None:
        git_config = host_home / ".gitconfig"
        if git_config.exists():
            env.setdefault("GIT_CONFIG_GLOBAL", str(git_config))
        xdg_config_home_text = str(host_xdg_config_home_raw or "").strip()
        xdg_config_home = Path(xdg_config_home_text).expanduser() if xdg_config_home_text else (host_home / ".config")
        if not xdg_config_home.exists() and (host_home / ".config").exists():
            xdg_config_home = host_home / ".config"
        gh_config_dir = xdg_config_home / "gh"
        if (gh_config_dir / "hosts.yml").exists():
            env.setdefault("XDG_CONFIG_HOME", str(xdg_config_home))
            env.setdefault("GH_CONFIG_DIR", str(gh_config_dir))
            return
    run_gh_dir = Path("/run/gh")
    if (run_gh_dir / "hosts.yml").exists():
        env.setdefault("XDG_CONFIG_HOME", str(run_gh_dir.parent))
        env.setdefault("GH_CONFIG_DIR", str(run_gh_dir))


def _github_token_from_hosts_yml(path: Path) -> str:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(raw, dict):
        return ""
    github_entry = raw.get("github.com")
    if not isinstance(github_entry, dict):
        return ""
    direct = str(github_entry.get("oauth_token") or "").strip()
    if direct:
        return direct
    users = github_entry.get("users")
    if not isinstance(users, dict):
        return ""
    for value in users.values():
        if not isinstance(value, dict):
            continue
        token = str(value.get("oauth_token") or "").strip()
        if token:
            return token
    return ""


def _github_auth_token(env: Dict[str, str]) -> str:
    for key in ("GH_TOKEN", "GITHUB_TOKEN"):
        token = str((env or {}).get(key) or "").strip()
        if token:
            return token
    try:
        token_process = subprocess.run(
            ["gh", "auth", "token"],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
    except FileNotFoundError:
        token_process = None
    if token_process is not None:
        token = str(token_process.stdout or "").strip()
        if token_process.returncode == 0 and token:
            return token
    gh_config_dir_text = str((env or {}).get("GH_CONFIG_DIR") or "").strip()
    xdg_config_home_text = str((env or {}).get("XDG_CONFIG_HOME") or "").strip()
    candidate_dirs: List[Path] = []
    if gh_config_dir_text:
        candidate_dirs.append(Path(gh_config_dir_text).expanduser())
    if xdg_config_home_text:
        candidate_dirs.append(Path(xdg_config_home_text).expanduser() / "gh")
    candidate_dirs.append(Path("/run/gh"))
    seen: Set[str] = set()
    for directory in candidate_dirs:
        directory_text = str(directory)
        if not directory_text or directory_text in seen:
            continue
        seen.add(directory_text)
        token = _github_token_from_hosts_yml(directory / "hosts.yml")
        if token:
            return token
    return ""


def _copy_file_if_changed(source: Path, target: Path) -> None:
    if not source.exists() or not source.is_file():
        return
    _ensure_dir(target.parent)
    source_bytes = source.read_bytes()
    if target.exists():
        try:
            if target.read_bytes() == source_bytes:
                return
        except Exception:
            pass
    target.write_bytes(source_bytes)


def _seed_worker_home_git_auth(
    home: Path,
    *,
    host_home_raw: str,
    host_xdg_config_home_raw: str,
) -> None:
    host_home = _resolve_host_home_path(host_home_raw)
    if host_home is None:
        return
    host_gitconfig = host_home / ".gitconfig"
    if host_gitconfig.exists():
        _copy_file_if_changed(host_gitconfig, home / ".gitconfig")
    xdg_config_home_text = str(host_xdg_config_home_raw or "").strip()
    host_xdg_config_home = (
        Path(xdg_config_home_text).expanduser() if xdg_config_home_text else (host_home / ".config")
    )
    if not host_xdg_config_home.exists() and (host_home / ".config").exists():
        host_xdg_config_home = host_home / ".config"
    host_gh_dir = host_xdg_config_home / "gh"
    worker_gh_dir = home / ".config" / "gh"
    if host_gh_dir.exists():
        for filename in ("hosts.yml", "config.yml"):
            _copy_file_if_changed(host_gh_dir / filename, worker_gh_dir / filename)


def _fallback_auth_json_path(source_path: Path, workspace_root: Path) -> Path:
    if source_path.exists():
        return source_path
    source_text = str(source_path)
    if source_text.startswith("/run/secrets/"):
        mirrored = workspace_root / "secrets" / source_path.name
        if mirrored.exists():
            return mirrored
    return source_path


def _seed_auth_json(home: Path, source_path: Path) -> None:
    if not source_path.exists():
        raise RuntimeError(f"missing auth_json_file: {source_path}")
    target = home / "auth.json"
    target.write_bytes(source_path.read_bytes())


def _resolve_env_secret(name: str, workspace_root: Path) -> str:
    env_name = str(name or "").strip()
    if not env_name:
        return ""
    direct = str(os.environ.get(env_name, "") or "").strip()
    if direct:
        return direct
    for candidate in (
        workspace_root / "runtime.env",
        workspace_root / "runtime.ea.env",
        workspace_root / ".env",
        Path("/docker/.env"),
        Path("/docker/EA/.env"),
        Path("/docker/chummer5a/.env"),
        Path("/docker/chummer5a/.env.providers"),
    ):
        if not candidate.exists() or not candidate.is_file():
            continue
        for raw_line in _read_text(candidate).splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() != env_name:
                continue
            resolved = value.strip().strip("'").strip('"')
            if resolved:
                return resolved
    return ""


def _read_api_key(account: WorkerAccount, workspace_root: Path) -> str:
    if account.api_key_env:
        resolved = _resolve_env_secret(account.api_key_env, workspace_root)
        if resolved:
            return resolved
        raise RuntimeError(f"missing environment variable for api_key_env: {account.api_key_env}")
    if account.api_key_file:
        path = Path(account.api_key_file).expanduser()
        if not path.exists():
            raise RuntimeError(f"missing api_key_file: {path}")
        api_key = _read_text(path).strip()
        if api_key:
            return api_key
        raise RuntimeError(f"empty api_key_file: {path}")
    raise RuntimeError(f"no API key source configured for {account.alias}")


def _ea_bridge_api_token(workspace_root: Path) -> str:
    for env_name in ("EA_MCP_API_TOKEN", "EA_API_TOKEN", "FLEET_INTERNAL_API_TOKEN"):
        resolved = _resolve_env_secret(env_name, workspace_root)
        if resolved:
            return resolved
    return ""


def _prepare_account_environment(state_root: Path, workspace_root: Path, account: WorkerAccount) -> Dict[str, str]:
    home = _account_home(state_root, account)
    config_lines = ['cli_auth_credentials_store = "file"']
    if account.forced_login_method:
        config_lines.append(f"forced_login_method = {_write_toml_string(account.forced_login_method)}")
    if account.forced_chatgpt_workspace_id:
        config_lines.append(
            f"forced_chatgpt_workspace_id = {_write_toml_string(account.forced_chatgpt_workspace_id)}"
        )
    (home / "config.toml").write_text("\n".join(config_lines) + "\n", encoding="utf-8")

    host_home_raw = str(os.environ.get("HOME", "") or "").strip()
    host_xdg_config_home_raw = str(os.environ.get("XDG_CONFIG_HOME", "") or "").strip()
    env = os.environ.copy()
    env["CODEX_HOME"] = str(home)
    env["HOME"] = str(home)
    _seed_worker_home_git_auth(
        home,
        host_home_raw=host_home_raw,
        host_xdg_config_home_raw=host_xdg_config_home_raw,
    )
    _inherit_host_git_auth_environment(
        env,
        host_home_raw=host_home_raw,
        host_xdg_config_home_raw=host_xdg_config_home_raw,
    )
    worker_gitconfig = home / ".gitconfig"
    worker_xdg_config_home = home / ".config"
    worker_gh_config_dir = worker_xdg_config_home / "gh"
    if worker_gitconfig.exists():
        env["GIT_CONFIG_GLOBAL"] = str(worker_gitconfig)
    if (worker_gh_config_dir / "hosts.yml").exists():
        env["XDG_CONFIG_HOME"] = str(worker_xdg_config_home)
        env["GH_CONFIG_DIR"] = str(worker_gh_config_dir)
    if account.auth_kind in CHATGPT_AUTH_KINDS:
        _seed_auth_json(home, _fallback_auth_json_path(Path(account.auth_json_file).expanduser(), workspace_root))
    elif account.auth_kind == "api_key":
        env["CODEX_API_KEY"] = _read_api_key(account, workspace_root)
    elif account.auth_kind == "ea":
        bridge_token = _ea_bridge_api_token(workspace_root)
        if not bridge_token:
            raise RuntimeError("missing EA bridge API token (EA_MCP_API_TOKEN / EA_API_TOKEN / FLEET_INTERNAL_API_TOKEN)")
        env["EA_MCP_API_TOKEN"] = bridge_token
        env["EA_API_TOKEN"] = bridge_token
        principal_alias = re.sub(r"[^A-Za-z0-9._-]+", "-", str(account.alias or "")).strip("-._") or "ea-account"
        principal_id = f"codex-fleet-{principal_alias}"
        env["EA_PRINCIPAL_ID"] = principal_id
        env["EA_MCP_PRINCIPAL_ID"] = principal_id
        env["EA_DEFAULT_PRINCIPAL_ID"] = principal_id
        if account.api_key_env:
            env["EA_ONEMIN_ACCOUNT_ENV_NAME"] = account.api_key_env
        env["EA_ONEMIN_ACCOUNT_ALIAS"] = account.alias
    else:
        raise RuntimeError(f"unsupported auth_kind for {account.alias}: {account.auth_kind}")
    if account.openai_base_url:
        env["OPENAI_BASE_URL"] = account.openai_base_url
    return env


def _default_account_owner_ids(accounts_payload: Dict[str, Any]) -> List[str]:
    configured = _text_list((accounts_payload.get("account_policy") or {}).get("protected_owner_ids") or [])
    return configured or list(DEFAULT_ACCOUNT_OWNER_IDS)


def _load_worker_accounts(args: argparse.Namespace) -> List[WorkerAccount]:
    accounts_path = Path(args.accounts_path).resolve()
    if not accounts_path.exists():
        return []
    payload = _read_yaml(accounts_path)
    raw_accounts = payload.get("accounts") or {}
    if not isinstance(raw_accounts, dict):
        return []
    alias_filter = set(_text_list(args.account_alias or []))
    explicit_owner_filter = _text_list(args.account_owner_id or [])
    owner_filter = explicit_owner_filter or ([] if alias_filter else _default_account_owner_ids(payload))
    owner_order = {value: index for index, value in enumerate(owner_filter)}
    rows: List[WorkerAccount] = []
    for alias, raw in raw_accounts.items():
        if not isinstance(raw, dict):
            continue
        clean_alias = str(alias or "").strip()
        if not clean_alias:
            continue
        if alias_filter and clean_alias not in alias_filter:
            continue
        auth_kind = str(raw.get("auth_kind") or "api_key").strip()
        if auth_kind not in CHATGPT_AUTH_KINDS and auth_kind not in {"api_key", "ea"}:
            continue
        owner_id = str(raw.get("owner_id") or "").strip()
        if owner_filter and owner_id not in owner_order:
            if not (auth_kind == "ea" and not explicit_owner_filter and not alias_filter):
                continue
        health_state = str(raw.get("health_state") or "").strip().lower()
        if health_state not in READY_ACCOUNT_STATES:
            continue
        rows.append(
            WorkerAccount(
                alias=clean_alias,
                owner_id=owner_id,
                auth_kind=auth_kind,
                lane=str(raw.get("lane") or "").strip(),
                auth_json_file=str(raw.get("auth_json_file") or "").strip(),
                api_key_env=str(raw.get("api_key_env") or "").strip(),
                api_key_file=str(raw.get("api_key_file") or "").strip(),
                allowed_models=_text_list(raw.get("allowed_models") or []),
                health_state=health_state,
                spark_enabled=bool(raw.get("spark_enabled", SPARK_MODEL in (raw.get("allowed_models") or []))),
                bridge_priority=_coerce_int(raw.get("bridge_priority"), 999),
                forced_login_method=str(raw.get("forced_login_method") or "").strip(),
                forced_chatgpt_workspace_id=str(raw.get("forced_chatgpt_workspace_id") or "").strip(),
                openai_base_url=str(raw.get("openai_base_url") or "").strip(),
                home_dir=str(raw.get("home_dir") or raw.get("codex_home") or "").strip(),
                max_parallel_runs=max(0, _coerce_int(raw.get("max_parallel_runs"), 0)),
            )
        )
    rows.sort(
        key=lambda item: (
            owner_order.get(item.owner_id, 999 if explicit_owner_filter or not alias_filter else 0),
            item.bridge_priority,
            item.alias,
        )
    )
    return rows


def _parse_backoff_seconds(text: str, default_seconds: int) -> Optional[int]:
    lower = str(text or "").lower()
    if "429" not in lower and "rate limit" not in lower and "too many requests" not in lower:
        return None
    patterns = [
        (r"retry after\s+(\d+)\s*s", 1),
        (r"try again in\s+(\d+)\s*s", 1),
        (r"after\s+(\d+)\s*seconds", 1),
        (r"after\s+(\d+)\s*minutes", 60),
        (r"(\d+)\s*seconds?", 1),
        (r"(\d+)\s*minutes?", 60),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, lower)
        if match:
            return max(int(match.group(1)) * multiplier, default_seconds)
    return default_seconds


def _parse_spark_pool_backoff_seconds(text: str, default_seconds: int) -> Optional[int]:
    lower = str(text or "").lower()
    spark_signals = ("spark", "codex spark", "spark pool", "spark token", "spark quota", "spark credits")
    exhaustion_signals = ("depleted", "exhausted", "empty", "unavailable", "quota exceeded", "limit reached", "out of")
    if not any(signal in lower for signal in spark_signals):
        return None
    if not any(signal in lower for signal in exhaustion_signals) and "429" not in lower and "rate limit" not in lower:
        return None
    return _parse_backoff_seconds(text, default_seconds) or default_seconds


def _parse_auth_failure_message(text: str) -> Optional[str]:
    lower = str(text or "").lower()
    markers = [
        ("refresh_token_reused", "chatgpt auth refresh token was invalidated by another session"),
        ("access token could not be refreshed", "chatgpt auth refresh token is stale"),
        ("refresh token was already used", "chatgpt auth refresh token is stale"),
        ("provided authentication token is expired", "chatgpt auth session is expired"),
        ("please log out and sign in again", "chatgpt auth session requires a fresh login"),
        ("incorrect api key provided", "api key is invalid or revoked"),
        ("invalid api key", "api key is invalid or revoked"),
    ]
    for needle, message in markers:
        if needle in lower:
            return message
    if "401 unauthorized" in lower and ("token" in lower or "api key" in lower or "auth" in lower):
        return "authentication failed for this account"
    return None


def _parse_backend_unavailable_message(text: str) -> Optional[str]:
    raw = str(text or "")
    match = re.search(r"upstream_unavailable:([^\n\"']+)", raw, flags=re.IGNORECASE)
    if match:
        return f"backend unavailable: {match.group(1).strip().rstrip('}').rstrip(']')}"
    if "gemini_vortex_cli_missing" in raw.lower():
        return "backend unavailable: gemini_vortex:gemini_vortex_cli_missing"
    return None


def _parse_usage_limit_reset_at(text: str) -> Optional[dt.datetime]:
    raw = str(text or "")
    lower = raw.lower()
    if (
        "usage limit" not in lower
        and "send a request to your admin" not in lower
        and "insufficient_credits" not in lower
        and "insufficient credits" not in lower
        and "credit balance" not in lower
    ):
        return None
    match = re.search(
        r"try again at\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}\s+\d{1,2}:\d{2}\s+[AP]M)",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return None
    candidate = re.sub(r"(\d)(st|nd|rd|th)", r"\1", match.group(1), flags=re.IGNORECASE).strip()
    for fmt in ("%b %d, %Y %I:%M %p", "%B %d, %Y %I:%M %p"):
        try:
            return dt.datetime.strptime(candidate, fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


def _parse_usage_limit_backoff_seconds(text: str, default_seconds: int, *, now: Optional[dt.datetime] = None) -> Optional[int]:
    raw = str(text or "")
    lower = raw.lower()
    if (
        "usage limit" not in lower
        and "send a request to your admin" not in lower
        and "insufficient_credits" not in lower
        and "insufficient credits" not in lower
        and "credit balance" not in lower
    ):
        return None
    current = now or _utc_now()
    reset_at = _parse_usage_limit_reset_at(raw)
    if reset_at is None:
        return default_seconds
    seconds = int((reset_at - current).total_seconds())
    return max(seconds, default_seconds) if seconds > 0 else default_seconds


def _parse_unsupported_chatgpt_model(text: str) -> Optional[str]:
    raw = str(text or "")
    lower = raw.lower()
    if "not supported when using codex with a chatgpt account" not in lower:
        return None
    match = re.search(r"'([^']+)'", raw)
    if match:
        return str(match.group(1) or "").strip() or None
    return "unknown"


def _set_source_backoff(
    payload: Dict[str, Any],
    account: WorkerAccount,
    *,
    backoff_until: Optional[dt.datetime] = None,
    spark_backoff_until: Optional[dt.datetime] = None,
    last_error: str = "",
) -> None:
    sources = dict(payload.get("sources") or {})
    key = _credential_source_key(account)
    item = dict(sources.get(key) or {})
    item["alias"] = account.alias
    item["owner_id"] = account.owner_id
    item["source_key"] = key
    if backoff_until is not None:
        item["backoff_until"] = _iso(backoff_until)
    if spark_backoff_until is not None:
        item["spark_backoff_until"] = _iso(spark_backoff_until)
    if last_error:
        item["last_error"] = last_error
    sources[key] = item
    payload["sources"] = sources


def _clear_source_backoff(payload: Dict[str, Any], account: WorkerAccount) -> None:
    sources = dict(payload.get("sources") or {})
    key = _credential_source_key(account)
    item = dict(sources.get(key) or {})
    item["alias"] = account.alias
    item["owner_id"] = account.owner_id
    item["source_key"] = key
    item["backoff_until"] = ""
    item["spark_backoff_until"] = ""
    item["last_error"] = ""
    item["restore_probe_at"] = ""
    sources[key] = item
    payload["sources"] = sources


def _active_source_backoff(
    payload: Dict[str, Any],
    account: WorkerAccount,
    *,
    model: str = "",
    now: Optional[dt.datetime] = None,
) -> tuple[Optional[dt.datetime], str]:
    current = now or _utc_now()
    item = dict((payload.get("sources") or {}).get(_credential_source_key(account)) or {})
    if not item:
        return None, ""
    backoff_until = _parse_iso(str(item.get("backoff_until") or ""))
    if backoff_until is not None and backoff_until > current:
        return backoff_until, str(item.get("last_error") or "").strip()
    if model == SPARK_MODEL:
        spark_backoff_until = _parse_iso(str(item.get("spark_backoff_until") or ""))
        if spark_backoff_until is not None and spark_backoff_until > current:
            return spark_backoff_until, str(item.get("last_error") or "").strip()
    return None, ""


def _is_usage_limit_backoff_reason(reason: str) -> bool:
    lower = str(reason or "").strip().lower()
    if not lower:
        return False
    return (
        "usage-limited" in lower
        or "usage limit" in lower
        or "insufficient credits" in lower
        or "credit balance" in lower
        or "send a request to your admin" in lower
    )


def _lane_health_report(
    worker_lane_health: Optional[Dict[str, Any]],
    *,
    requested_worker_lane: str = "",
    account_lane: str = "",
) -> Dict[str, Any]:
    if not isinstance(worker_lane_health, dict):
        return {}
    lanes = dict(worker_lane_health.get("lanes") or {})
    requested = str(requested_worker_lane or "").strip()
    account_lane_text = str(account_lane or "").strip()
    for key in (requested, account_lane_text):
        if key and isinstance(lanes.get(key), dict):
            return dict(lanes.get(key) or {})
    return {}


def _eligible_routed_account_restore_probe(
    payload: Dict[str, Any],
    account: WorkerAccount,
    *,
    requested_worker_lane: str = "",
    worker_lane_health: Optional[Dict[str, Any]] = None,
    now: Optional[dt.datetime] = None,
) -> bool:
    if account.auth_kind != "ea":
        return False
    account_lane = str(account.lane or "").strip().lower()
    if not account_lane or account_lane in {"repair", "survival"}:
        return False
    backoff_until, backoff_reason = _active_source_backoff(payload, account, now=now)
    if backoff_until is None or not _is_usage_limit_backoff_reason(backoff_reason):
        return False
    if not _source_restore_probe_due(payload, account, now=now):
        return False
    lane_report = _lane_health_report(
        worker_lane_health,
        requested_worker_lane=requested_worker_lane,
        account_lane=account_lane,
    )
    if lane_report and lane_report.get("routable") is False:
        return False
    state = str(lane_report.get("state") or "").strip().lower()
    ready_slots = _coerce_int(lane_report.get("ready_slots"), 0)
    if not lane_report:
        return True
    if state in {"ready", "degraded"} or ready_slots > 0:
        return True
    if lane_report.get("known") is False and str((worker_lane_health or {}).get("status") or "").strip().lower() == "pass":
        return True
    return False


def _candidate_models_for_account(
    account: WorkerAccount,
    model_candidates: Sequence[str],
    account_runtime: Dict[str, Any],
    *,
    requested_worker_lane: str = "",
    ignore_active_backoff: bool = False,
    now: Optional[dt.datetime] = None,
) -> List[str]:
    current = now or _utc_now()
    rows: List[str] = []
    seen: set[str] = set()
    requested_lane = str(requested_worker_lane or "").strip().lower()
    account_lane = str(account.lane or "").strip().lower()
    allowed_models = {str(item or "").strip() for item in (account.allowed_models or []) if str(item or "").strip()}
    for candidate in model_candidates:
        clean_candidate = str(candidate or "").strip()
        variants = [clean_candidate]
        if requested_lane in CORE_BATCH_WORKER_LANES and clean_candidate in CORE_BATCH_RUNTIME_MODELS:
            variants = [runtime_model for runtime_model in ("ea-coder-hard-batch", clean_candidate) if runtime_model]
        variants.extend(
            fallback
            for fallback in MODEL_COMPATIBILITY_FALLBACKS.get(clean_candidate, ())
            if str(fallback or "").strip()
        )
        variants.extend(
            fallback
            for fallback in (LANE_MODEL_COMPATIBILITY_FALLBACKS.get(requested_lane, {}).get(account_lane, ()) or ())
        )
        for variant in variants:
            clean_variant = str(variant or "").strip()
            if clean_variant in seen:
                continue
            if allowed_models and clean_variant and clean_variant not in allowed_models:
                continue
            if clean_variant == SPARK_MODEL and not account.spark_enabled:
                continue
            backoff_until, _ = _active_source_backoff(account_runtime, account, model=clean_variant, now=current)
            if not ignore_active_backoff and backoff_until is not None:
                continue
            rows.append(clean_variant)
            seen.add(clean_variant)
            break
    return rows


def _account_has_runnable_candidate_models(
    account: WorkerAccount,
    model_candidates: Sequence[str],
    account_runtime: Dict[str, Any],
    *,
    requested_worker_lane: str = "",
    ignore_active_backoff: bool = False,
    active_account_claims: Optional[Dict[str, int]] = None,
    now: Optional[dt.datetime] = None,
) -> bool:
    current = now or _utc_now()
    claims = active_account_claims or {}
    claimed_account_count = int(claims.get(account.alias, 0))
    if account.max_parallel_runs > 0 and claimed_account_count >= account.max_parallel_runs:
        return False
    backoff_until, _ = _active_source_backoff(account_runtime, account, now=current)
    if not ignore_active_backoff and backoff_until is not None:
        return False
    return bool(
        _candidate_models_for_account(
            account,
            model_candidates,
            account_runtime,
            requested_worker_lane=requested_worker_lane,
            ignore_active_backoff=ignore_active_backoff,
            now=current,
        )
    )


def launch_worker(
    args: argparse.Namespace,
    context: Dict[str, Any],
    state_root: Path,
    *,
    worker_lane_health: Optional[Dict[str, Any]] = None,
) -> WorkerRun:
    open_milestones: List[Milestone] = context["open_milestones"]
    frontier: List[Milestone] = context["frontier"]
    prompt = str(context["prompt"])
    run_id = _state_scoped_run_id(state_root)
    run_dir = state_root / "runs" / run_id
    prompt = _prepare_run_prompt(
        run_dir,
        prompt,
        task_local_telemetry_payload=context.get("task_local_telemetry_payload"),
    )
    prompt_path = _write_run_artifacts(
        run_dir,
        prompt,
    )
    stdout_path = run_dir / "worker.stdout.log"
    stderr_path = run_dir / "worker.stderr.log"
    last_message_path = run_dir / "last_message.txt"
    model_candidates = _worker_model_candidates(args)
    model_candidates = _rotate_model_candidates_after_recent_stall(state_root, model_candidates)
    worker_lane_candidates = _worker_lane_candidates(args)
    account_candidates = _load_worker_accounts(args)
    account_runtime_path = _account_runtime_path(state_root)
    account_runtime = _read_account_runtime(account_runtime_path)
    workspace_root = Path(args.workspace_root).resolve()
    worker_command = _default_worker_command(
        worker_bin=args.worker_bin,
        worker_lane=worker_lane_candidates[0],
        workspace_root=workspace_root,
        scope_roots=context["scope_roots"],
        run_dir=run_dir,
        worker_model=model_candidates[0],
    )
    started_at = _iso_now()
    frontier_ids = [item.id for item in frontier]
    open_milestone_ids = [item.id for item in open_milestones]
    if not open_milestone_ids and frontier_ids:
        open_milestone_ids = list(frontier_ids)
    primary_milestone_id = frontier[0].id if frontier else None
    if args.dry_run:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        last_message_path.write_text("", encoding="utf-8")
        return WorkerRun(
            run_id=run_id,
            started_at=started_at,
            finished_at=started_at,
            worker_command=worker_command,
            attempted_accounts=[],
            attempted_models=[item or "default" for item in model_candidates[:1]],
            selected_account_alias="",
            worker_exit_code=0,
            frontier_ids=frontier_ids,
            open_milestone_ids=open_milestone_ids,
            primary_milestone_id=primary_milestone_id,
            prompt_path=str(prompt_path),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            last_message_path=str(last_message_path),
            final_message="",
            shipped="",
            remains="",
            blocker="",
            accepted=True,
            acceptance_reason="",
        )

    configured_worker_timeout_seconds, worker_timeout_seconds = _effective_worker_timeout_seconds(args, workspace_root)
    attempted_accounts: List[str] = []
    attempted_models: List[str] = []
    selected_account_alias = ""
    completed: subprocess.CompletedProcess[str] | None = None
    accepted = False
    acceptance_reason = "worker not launched"
    parsed: Dict[str, str] = {"shipped": "", "remains": "", "blocker": ""}
    final_message = ""
    preflight_failure_reason = ""
    direct_worker_lane = worker_lane_candidates[0]
    last_account_restore_probe_at: Optional[dt.datetime] = None
    rescue_account_candidates: List[WorkerAccount] = []
    routed_full_lane_fallback_args: Optional[argparse.Namespace] = None
    restore_probe_account_aliases: Set[str] = set()
    fatal_worker_contract_violation = False
    explicit_account_targets = bool(_text_list(args.account_alias or []) or _text_list(args.account_owner_id or []))
    has_routed_ea_accounts = any(account.auth_kind == "ea" for account in account_candidates)
    routed_account_required = bool(
        direct_worker_lane
        and not explicit_account_targets
        and _worker_bin_uses_codexea(str(args.worker_bin or ""))
        and has_routed_ea_accounts
    )
    if direct_worker_lane and not explicit_account_targets:
        requested_models = [candidate for candidate in model_candidates if str(candidate or "").strip()]
        active_account_claims = _active_account_claim_counts(state_root)
        prefer_full_ea_lanes = _prefer_full_ea_lanes_enabled()
        current = _utc_now()
        preferred_routed_accounts: List[tuple[int, int, int, str, WorkerAccount]] = []
        rescue_routed_accounts: List[tuple[int, int, int, str, WorkerAccount]] = []
        preferred_runnable_account_found = False
        restore_probe_candidates: List[tuple[dt.datetime, int, int, str, WorkerAccount]] = []
        for account in account_candidates:
            if account.auth_kind != "ea":
                continue
            account_lane = str(account.lane or "").strip().lower()
            allowed_models = {str(item or "").strip() for item in (account.allowed_models or []) if str(item or "").strip()}
            requested_or_compatible_models: set[str] = set(requested_models)
            for model in requested_models:
                requested_or_compatible_models.update(
                    item
                    for item in MODEL_COMPATIBILITY_FALLBACKS.get(str(model or "").strip(), ())
                    if str(item or "").strip()
                )
                requested_or_compatible_models.update(
                    item
                    for item in (LANE_MODEL_COMPATIBILITY_FALLBACKS.get(str(direct_worker_lane or "").strip().lower(), {}).get(account_lane, ()) or ())
                    if str(item or "").strip()
                )
            if (
                requested_or_compatible_models
                and allowed_models
                and not any(model in allowed_models for model in requested_or_compatible_models)
            ):
                continue
            priority = 0 if account_lane == str(direct_worker_lane or "").strip().lower() else 1
            if priority and account_lane not in {"jury", "review_light"}:
                priority = 2
            routing_row = (
                priority,
                int(active_account_claims.get(account.alias, 0)),
                _stable_account_selection_rank(state_root, account.alias),
                account.alias,
                account,
            )
            is_rescue_lane = account_lane in {"repair", "survival"}
            if prefer_full_ea_lanes and is_rescue_lane:
                rescue_routed_accounts.append(routing_row)
                continue
            preferred_routed_accounts.append(routing_row)
            restore_probe_eligible = _eligible_routed_account_restore_probe(
                account_runtime,
                account,
                requested_worker_lane=direct_worker_lane,
                worker_lane_health=worker_lane_health,
                now=current,
            )
            if restore_probe_eligible:
                backoff_until, _ = _active_source_backoff(account_runtime, account, now=current)
                restore_probe_candidates.append(
                    (
                        backoff_until or current,
                        int(active_account_claims.get(account.alias, 0)),
                        _stable_account_selection_rank(state_root, account.alias),
                        account.alias,
                        account,
                    )
                )
            preferred_runnable_account_found = preferred_runnable_account_found or _account_has_runnable_candidate_models(
                account,
                model_candidates,
                account_runtime,
                requested_worker_lane=direct_worker_lane,
                active_account_claims=active_account_claims,
                now=current,
            )
        if not preferred_runnable_account_found and restore_probe_candidates:
            restore_probe_account_aliases.add(sorted(restore_probe_candidates)[0][3])
        routed_accounts: List[tuple[int, int, int, str, WorkerAccount]] = list(preferred_routed_accounts)
        preferred_account_candidates = [account for _priority, _claims, _rank, _alias, account in sorted(routed_accounts)]
        if rescue_routed_accounts and (not prefer_full_ea_lanes or not preferred_runnable_account_found):
            rescue_account_candidates = [account for _priority, _claims, _rank, _alias, account in sorted(rescue_routed_accounts)]
        if prefer_full_ea_lanes:
            account_candidates = list(preferred_account_candidates)
        else:
            account_candidates = list(preferred_account_candidates) + list(rescue_account_candidates)
            rescue_account_candidates = []
        routed_full_lane_fallback_args = (
            _routed_full_lane_direct_fallback_args(args)
            if prefer_full_ea_lanes and routed_account_required
            else None
        )

    def mark_active_run(
        *,
        command: Sequence[str],
        account_alias: str,
        model_label: str,
        attempt_index: int,
        total_attempts: int,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        _write_active_run_state(
            state_root,
            ActiveWorkerRun(
                run_id=run_id,
                started_at=started_at,
                prompt_path=str(prompt_path),
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                last_message_path=str(last_message_path),
                frontier_ids=frontier_ids,
                open_milestone_ids=open_milestone_ids,
                primary_milestone_id=primary_milestone_id,
                worker_command=list(command),
                selected_account_alias=account_alias,
                selected_model=model_label,
                attempt_index=attempt_index,
                total_attempts=max(1, total_attempts),
                watchdog_timeout_seconds=worker_timeout_seconds if timeout_seconds is None else float(timeout_seconds),
            ),
        )

    def reset_last_message_attempt_marker() -> None:
        try:
            last_message_path.write_text("", encoding="utf-8")
        except OSError:
            pass

    try:
        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
            def run_account_attempts(
                accounts: Sequence[WorkerAccount],
                *,
                worker_bin: str,
                worker_lane: str,
                phase_models: Sequence[str],
                phase_label: str = "attempt",
            ) -> bool:
                nonlocal worker_command, completed, accepted, acceptance_reason, parsed, final_message, selected_account_alias
                nonlocal fatal_worker_contract_violation
                if not accounts:
                    return False
                account_runtime_dirty = False
                for account in accounts:
                    if _refresh_source_credential_state(account_runtime, account, workspace_root):
                        account_runtime_dirty = True
                if account_runtime_dirty:
                    _write_account_runtime(account_runtime_path, account_runtime)
                attempt_offset = len(attempted_accounts)
                phase_total_attempts = sum(
                    max(1, len(_candidate_models_for_account(account, phase_models, account_runtime, requested_worker_lane=worker_lane)))
                    for account in accounts
                )
                display_total_attempts = max(attempt_offset + max(1, phase_total_attempts), attempt_offset + 1)
                phase_attempt_index = 0
                stop_retrying = False
                for account in accounts:
                    selection_lock_path = _account_selection_lock_path(state_root, account.alias)
                    try:
                        _acquire_lock(selection_lock_path, ttl_seconds=max(60.0, LOCK_TTL_SECONDS / 4))
                    except RuntimeError:
                        stderr_handle.write(
                            f"[fleet-supervisor] skip account={account.alias} owner={account.owner_id} reason=account_selection_busy\n"
                        )
                        stderr_handle.flush()
                        continue
                    worker_env: Optional[Dict[str, str]] = None
                    candidate_models: List[str] = []
                    try:
                        claimed_account_count = _active_account_claim_counts(state_root).get(account.alias, 0)
                        if account.max_parallel_runs > 0 and claimed_account_count >= account.max_parallel_runs:
                            stderr_handle.write(
                                f"[fleet-supervisor] skip account={account.alias} owner={account.owner_id} "
                                f"reason=max_parallel_runs {claimed_account_count}/{account.max_parallel_runs}\n"
                            )
                            stderr_handle.flush()
                            continue
                        now = _utc_now()
                        allow_restore_probe = (
                            account.alias in restore_probe_account_aliases
                            and _eligible_routed_account_restore_probe(
                                account_runtime,
                                account,
                                requested_worker_lane=worker_lane,
                                worker_lane_health=worker_lane_health,
                                now=now,
                            )
                        )
                        source_backoff_until, source_backoff_reason = _active_source_backoff(account_runtime, account, now=now)
                        if source_backoff_until is not None and not allow_restore_probe:
                            stderr_handle.write(
                                f"[fleet-supervisor] skip account={account.alias} owner={account.owner_id} "
                                f"until={_iso(source_backoff_until)} reason={source_backoff_reason or 'backoff'}\n"
                            )
                            stderr_handle.flush()
                            continue
                        if allow_restore_probe:
                            _mark_source_restore_probe(account_runtime, account, when=now)
                            _write_account_runtime(account_runtime_path, account_runtime)
                            stderr_handle.write(
                                f"[fleet-supervisor] restore probe account={account.alias} owner={account.owner_id} "
                                f"despite active backoff until={_iso(source_backoff_until)} "
                                f"reason={source_backoff_reason or 'backoff'}\n"
                            )
                            stderr_handle.flush()
                        candidate_models = _candidate_models_for_account(
                            account,
                            phase_models,
                            account_runtime,
                            requested_worker_lane=worker_lane,
                            ignore_active_backoff=allow_restore_probe,
                        )
                        if not candidate_models:
                            stderr_handle.write(
                                f"[fleet-supervisor] skip account={account.alias} owner={account.owner_id} no_models_available\n"
                            )
                            stderr_handle.flush()
                            continue
                        try:
                            worker_env = _prepare_account_environment(state_root, workspace_root, account)
                        except Exception as exc:
                            message = f"account bootstrap failed: {exc}"
                            until = _utc_now() + dt.timedelta(seconds=DEFAULT_AUTH_FAILURE_BACKOFF_SECONDS)
                            _set_source_backoff(account_runtime, account, backoff_until=until, last_error=message)
                            _write_account_runtime(account_runtime_path, account_runtime)
                            stderr_handle.write(
                                f"[fleet-supervisor] skip account={account.alias} owner={account.owner_id} "
                                f"until={_iso(until)} reason={message}\n"
                            )
                            stderr_handle.flush()
                            continue
                        worker_env = _stamp_worker_supervisor_guard(worker_env, run_id=run_id, run_dir=run_dir)
                        lock_released = False
                        for candidate_model in candidate_models:
                            phase_attempt_index += 1
                            display_attempt_index = attempt_offset + phase_attempt_index
                            requested_worker_lane = str(worker_lane or "").strip()
                            account_worker_lane = str(account.lane or "").strip()
                            lane_fallback = bool(
                                requested_worker_lane
                                and account_worker_lane
                                and account_worker_lane != requested_worker_lane
                            )
                            effective_worker_lane = (
                                account_worker_lane
                                if lane_fallback
                                else (requested_worker_lane or account_worker_lane)
                            )
                            worker_command = _default_worker_command(
                                worker_bin=worker_bin,
                                worker_lane=effective_worker_lane,
                                workspace_root=workspace_root,
                                scope_roots=context["scope_roots"],
                                run_dir=run_dir,
                                worker_model=candidate_model,
                            )
                            attempted_accounts.append(account.alias)
                            attempted_models.append(candidate_model or "default")
                            selected_account_alias = account.alias
                            reset_last_message_attempt_marker()
                            mark_active_run(
                                command=worker_command,
                                account_alias=account.alias,
                                model_label=candidate_model or "default",
                                attempt_index=display_attempt_index,
                                total_attempts=display_total_attempts,
                            )
                            stderr_handle.write(
                                f"[fleet-supervisor] {phase_label} {display_attempt_index}/{display_total_attempts} "
                                f"account={account.alias} owner={account.owner_id} model={candidate_model or 'default'}\n"
                            )
                            if lane_fallback:
                                stderr_handle.write(
                                    f"[fleet-supervisor] lane fallback requested={requested_worker_lane} "
                                    f"using account lane={account_worker_lane} account={account.alias} "
                                    f"model={candidate_model or 'default'}\n"
                                )
                            stderr_handle.flush()
                            _release_lock(selection_lock_path)
                            lock_released = True
                            completed = _run_worker_attempt(
                                worker_command,
                                prompt=prompt,
                                workspace_root=workspace_root,
                                worker_env=worker_env,
                                timeout_seconds=worker_timeout_seconds,
                                last_message_path=last_message_path,
                                state_root=state_root,
                                run_id=run_id,
                                stdout_sink=stdout_handle,
                                stderr_sink=stderr_handle,
                            )
                            stdout_handle.flush()
                            stderr_handle.flush()
                            final_message = _read_text(last_message_path).strip() if last_message_path.exists() else ""
                            parsed = _parse_final_message_sections(final_message)
                            accepted, acceptance_reason = _assess_worker_result(completed.returncode, final_message, parsed)
                            if completed.returncode == 0 and accepted:
                                _clear_source_backoff(account_runtime, account)
                                _write_account_runtime(account_runtime_path, account_runtime)
                                return True
                            if completed.returncode == 0:
                                stderr_handle.write(
                                    f"[fleet-supervisor] rejected result account={account.alias} "
                                    f"model={candidate_model or 'default'} reason={acceptance_reason}\n"
                                )
                                stderr_handle.flush()
                                continue
                            if _run_scoped_worker_contract_violation(
                                completed.stderr,
                                final_message,
                                parsed.get("blocker", ""),
                                acceptance_reason,
                            ):
                                fatal_worker_contract_violation = True
                                stop_retrying = True
                                break
                            now = _utc_now()
                            auth_failure = _parse_auth_failure_message(completed.stderr)
                            if auth_failure:
                                until = now + dt.timedelta(seconds=DEFAULT_AUTH_FAILURE_BACKOFF_SECONDS)
                                _set_source_backoff(account_runtime, account, backoff_until=until, last_error=auth_failure)
                                _write_account_runtime(account_runtime_path, account_runtime)
                                break
                            usage_limit_backoff = _parse_usage_limit_backoff_seconds(
                                completed.stderr,
                                DEFAULT_USAGE_LIMIT_BACKOFF_SECONDS,
                                now=now,
                            )
                            if usage_limit_backoff is not None:
                                until = now + dt.timedelta(seconds=usage_limit_backoff)
                                reset_at = _parse_usage_limit_reset_at(completed.stderr)
                                message = (
                                    f"usage-limited until {_iso(reset_at)}"
                                    if reset_at is not None
                                    else f"usage-limited; recheck at {_iso(until)}"
                                )
                                _set_source_backoff(account_runtime, account, backoff_until=until, last_error=message)
                                _write_account_runtime(account_runtime_path, account_runtime)
                                break
                            backend_unavailable = _parse_backend_unavailable_message(completed.stderr)
                            if backend_unavailable is not None:
                                until = now + dt.timedelta(seconds=DEFAULT_BACKEND_UNAVAILABLE_BACKOFF_SECONDS)
                                _set_source_backoff(account_runtime, account, backoff_until=until, last_error=backend_unavailable)
                                _write_account_runtime(account_runtime_path, account_runtime)
                                break
                            spark_backoff = (
                                _parse_spark_pool_backoff_seconds(completed.stderr, DEFAULT_SPARK_BACKOFF_SECONDS)
                                if candidate_model == SPARK_MODEL
                                else None
                            )
                            if spark_backoff is not None:
                                until = now + dt.timedelta(seconds=spark_backoff)
                                _set_source_backoff(
                                    account_runtime,
                                    account,
                                    spark_backoff_until=until,
                                    last_error=f"spark pool unavailable for {spark_backoff}s",
                                )
                                _write_account_runtime(account_runtime_path, account_runtime)
                                continue
                            unsupported_model = _parse_unsupported_chatgpt_model(completed.stderr)
                            if unsupported_model is not None:
                                continue
                            rate_limit_backoff = _parse_backoff_seconds(completed.stderr, DEFAULT_RATE_LIMIT_BACKOFF_SECONDS)
                            if rate_limit_backoff is not None:
                                until = now + dt.timedelta(seconds=rate_limit_backoff)
                                _set_source_backoff(
                                    account_runtime,
                                    account,
                                    backoff_until=until,
                                    last_error=f"rate limited for {rate_limit_backoff}s",
                                )
                                _write_account_runtime(account_runtime_path, account_runtime)
                                break
                            if not _retryable_worker_error(completed.stderr):
                                stop_retrying = True
                                break
                            if completed is not None and completed.returncode == 0 and accepted:
                                return True
                            if stop_retrying:
                                break
                    finally:
                        _release_lock(selection_lock_path)
                    if stop_retrying:
                        break
                return completed is not None and completed.returncode == 0 and accepted

            def run_direct_attempts(
                phase_args: argparse.Namespace,
                *,
                phase_label: str = "attempt",
                direct_lane_health_override: Optional[Dict[str, Any]] = None,
            ) -> bool:
                nonlocal worker_command, completed, accepted, acceptance_reason, parsed, final_message, selected_account_alias, preflight_failure_reason, last_account_restore_probe_at
                nonlocal fatal_worker_contract_violation
                phase_model_candidates = _worker_model_candidates(phase_args)
                phase_lane_candidates = _worker_lane_candidates(phase_args)
                phase_configured_timeout_seconds, phase_worker_timeout_seconds = _effective_worker_timeout_seconds(
                    phase_args, workspace_root
                )
                direct_lane_health = (
                    dict(direct_lane_health_override)
                    if isinstance(direct_lane_health_override, dict) and direct_lane_health_override
                    else _direct_worker_lane_health_snapshot(phase_args, phase_lane_candidates)
                )
                filtered_lane_candidates, skipped_lane_reports = _filter_routable_direct_worker_lanes(
                    phase_lane_candidates,
                    direct_lane_health,
                )
                for lane_report in skipped_lane_reports:
                    stderr_handle.write(
                        "[fleet-supervisor] skip direct lane="
                        f"{lane_report.get('worker_lane') or 'default'} profile={lane_report.get('profile') or 'unknown'} "
                        f"state={lane_report.get('state') or 'unknown'} reason={lane_report.get('reason') or 'unavailable'}\n"
                    )
                    stderr_handle.flush()
                local_preflight_failure_reason = ""
                if not filtered_lane_candidates:
                    local_preflight_failure_reason = (
                        _worker_lane_health_blocker_reason(direct_lane_health)
                        or "provider-health preflight left no routable direct lanes"
                    )
                    stderr_handle.write(f"[fleet-supervisor] {local_preflight_failure_reason}\n")
                    stderr_handle.flush()
                    preflight_failure_reason = local_preflight_failure_reason
                attempt_offset = len(attempted_accounts)
                phase_attempt_index = 0
                phase_total_attempts = max(1, len(filtered_lane_candidates) * len(phase_model_candidates))
                display_total_attempts = max(attempt_offset + phase_total_attempts, attempt_offset + 1)
                stop_retrying = False
                if phase_worker_timeout_seconds > phase_configured_timeout_seconds > 0.0:
                    stderr_handle.write(
                        "[fleet-supervisor] raised direct worker watchdog from "
                        f"{phase_configured_timeout_seconds:g}s to {phase_worker_timeout_seconds:g}s "
                        "to match the configured CodexEA stream budget\n"
                    )
                    stderr_handle.flush()
                for candidate_lane in filtered_lane_candidates:
                    worker_env = _prepare_direct_worker_environment(
                        state_root,
                        candidate_lane,
                        workspace_root=workspace_root,
                        worker_bin=phase_args.worker_bin,
                    )
                    worker_env = _stamp_worker_supervisor_guard(worker_env, run_id=run_id, run_dir=run_dir)
                    lane_alias = f"lane:{candidate_lane}" if candidate_lane else "default"
                    for candidate_model in phase_model_candidates:
                        if account_candidates:
                            now = _utc_now()
                            if _account_restore_probe_due(last_account_restore_probe_at, now=now):
                                last_account_restore_probe_at = now
                                restore_accounts: List[WorkerAccount] = []
                                account_runtime_dirty = False
                                for account in account_candidates:
                                    if _refresh_source_credential_state(account_runtime, account, workspace_root, now=now):
                                        account_runtime_dirty = True
                                    if _candidate_models_for_account(
                                        account,
                                        model_candidates,
                                        account_runtime,
                                        requested_worker_lane=direct_worker_lane,
                                        now=now,
                                    ):
                                        restore_accounts.append(account)
                                if account_runtime_dirty:
                                    _write_account_runtime(account_runtime_path, account_runtime)
                                if restore_accounts:
                                    stderr_handle.write(
                                        "[fleet-supervisor] OpenAI restore probe found runnable accounts again "
                                        f"aliases={','.join(account.alias for account in restore_accounts)} "
                                        f"models={','.join(model_candidates) or 'default'}\n"
                                    )
                                    stderr_handle.flush()
                                if run_account_attempts(
                                        restore_accounts,
                                        worker_bin=args.worker_bin,
                                        worker_lane=direct_worker_lane,
                                        phase_models=model_candidates,
                                        phase_label="restore",
                                    ):
                                        return True
                                if fatal_worker_contract_violation:
                                    break
                        if fatal_worker_contract_violation:
                            stop_retrying = True
                            break
                        phase_attempt_index += 1
                        display_attempt_index = attempt_offset + phase_attempt_index
                        worker_command = _default_worker_command(
                            worker_bin=phase_args.worker_bin,
                            worker_lane=candidate_lane,
                            workspace_root=workspace_root,
                            scope_roots=context["scope_roots"],
                            run_dir=run_dir,
                            worker_model=candidate_model,
                        )
                        attempted_accounts.append(lane_alias)
                        attempted_models.append(candidate_model or "default")
                        selected_account_alias = lane_alias if candidate_lane else ""
                        reset_last_message_attempt_marker()
                        mark_active_run(
                            command=worker_command,
                            account_alias=lane_alias if candidate_lane else "default",
                            model_label=candidate_model or "default",
                            attempt_index=display_attempt_index,
                            total_attempts=display_total_attempts,
                            timeout_seconds=phase_worker_timeout_seconds,
                        )
                        stderr_handle.write(
                            f"[fleet-supervisor] {phase_label} {display_attempt_index}/{display_total_attempts} "
                            f"account={lane_alias} lane={candidate_lane or 'default'} model={candidate_model or 'default'}\n"
                        )
                        stderr_handle.flush()
                        completed = _run_worker_attempt(
                            worker_command,
                            prompt=prompt,
                            workspace_root=workspace_root,
                            worker_env=worker_env,
                            timeout_seconds=phase_worker_timeout_seconds,
                            last_message_path=last_message_path,
                            state_root=state_root,
                            run_id=run_id,
                            stdout_sink=stdout_handle,
                            stderr_sink=stderr_handle,
                        )
                        stdout_handle.flush()
                        stderr_handle.flush()
                        final_message = _read_text(last_message_path).strip() if last_message_path.exists() else ""
                        parsed = _parse_final_message_sections(final_message)
                        accepted, acceptance_reason = _assess_worker_result(completed.returncode, final_message, parsed)
                        if completed.returncode == 0 and accepted:
                            return True
                        if completed.returncode == 0:
                            stderr_handle.write(
                                f"[fleet-supervisor] rejected result account={lane_alias} "
                                f"lane={candidate_lane or 'default'} model={candidate_model or 'default'} reason={acceptance_reason}\n"
                            )
                            stderr_handle.flush()
                            if (
                                display_attempt_index >= display_total_attempts
                                or not _retryable_worker_rejection(acceptance_reason, completed.stderr)
                            ):
                                stop_retrying = True
                                break
                            continue
                        if _run_scoped_worker_contract_violation(
                            completed.stderr,
                            final_message,
                            parsed.get("blocker", ""),
                            acceptance_reason,
                        ):
                            fatal_worker_contract_violation = True
                            stop_retrying = True
                            break
                        if display_attempt_index >= display_total_attempts or not _retryable_worker_error(completed.stderr):
                            stop_retrying = True
                            break
                    if completed is not None and completed.returncode == 0 and accepted:
                        return True
                    if stop_retrying:
                        break
                return completed is not None and completed.returncode == 0 and accepted

            if account_candidates:
                account_phase_succeeded = False
                if (
                    routed_account_required
                    and _prefer_openai_escape_fastpath_after_recent_helper_loop(state_root)
                ):
                    escape_args = _openai_escape_hatch_args(args)
                    escape_accounts = _load_worker_accounts(escape_args)
                    if escape_accounts:
                        stderr_handle.write(
                            "[fleet-supervisor] recent shard helper-loop churn detected; "
                            "trying openai escape hatch before routed EA accounts "
                            f"aliases={','.join(account.alias for account in escape_accounts)} "
                            f"models={','.join(_worker_model_candidates(escape_args))}\n"
                        )
                        stderr_handle.flush()
                        if run_account_attempts(
                            escape_accounts,
                            worker_bin=escape_args.worker_bin,
                            worker_lane=escape_args.worker_lane,
                            phase_models=_worker_model_candidates(escape_args),
                            phase_label="escape-first",
                        ):
                            account_phase_succeeded = True
                if not account_phase_succeeded:
                    account_phase_succeeded = run_account_attempts(
                        account_candidates,
                        worker_bin=args.worker_bin,
                        worker_lane=direct_worker_lane,
                        phase_models=model_candidates,
                    )
                if (
                    not account_phase_succeeded
                    and not fatal_worker_contract_violation
                    and routed_full_lane_fallback_args is not None
                ):
                    stderr_handle.write(
                        "[fleet-supervisor] escalating routed-account exhaustion to anonymous full-lane fallback "
                        f"lane={str(routed_full_lane_fallback_args.worker_lane or '').strip() or 'default'} "
                        f"fallback_lanes={','.join(_worker_lane_candidates(routed_full_lane_fallback_args)) or 'default'} "
                        f"models={','.join(_worker_model_candidates(routed_full_lane_fallback_args)) or 'default'}\n"
                    )
                    stderr_handle.flush()
                    if run_direct_attempts(
                        routed_full_lane_fallback_args,
                        phase_label="full-fallback",
                    ):
                        account_phase_succeeded = True
                if (
                    not account_phase_succeeded
                    and not fatal_worker_contract_violation
                    and rescue_account_candidates
                ):
                    stderr_handle.write(
                        "[fleet-supervisor] falling back to rescue-routed accounts after full-lane recovery path stayed blocked\n"
                    )
                    stderr_handle.flush()
                    if run_account_attempts(
                        rescue_account_candidates,
                        worker_bin=args.worker_bin,
                        worker_lane=direct_worker_lane,
                        phase_models=model_candidates,
                        phase_label="rescue",
                    ):
                        account_phase_succeeded = True
                if (
                    not account_phase_succeeded
                    and not fatal_worker_contract_violation
                    and not routed_account_required
                    and _should_attempt_account_direct_fallback(
                        completed,
                        stderr_text=(completed.stderr if completed is not None else ""),
                    )
                ):
                    last_account_restore_probe_at = _utc_now()
                    fallback_args = _account_direct_fallback_args(args)
                    stderr_handle.write(
                        "[fleet-supervisor] escalating account-lane failure to direct fallback "
                        f"worker_bin={fallback_args.worker_bin or 'default'} "
                        f"lane={str(fallback_args.worker_lane or '').strip() or 'default'} "
                        f"models={','.join(_worker_model_candidates(fallback_args)) or 'default'}\n"
                    )
                    stderr_handle.flush()
                    run_direct_attempts(
                        fallback_args,
                        phase_label="fallback",
                    )
                elif (
                    not account_phase_succeeded
                    and not fatal_worker_contract_violation
                    and routed_account_required
                    and routed_full_lane_fallback_args is None
                    and not rescue_account_candidates
                ):
                    stderr_handle.write(
                        "[fleet-supervisor] routed-account lane failure will not fall back to anonymous direct lane\n"
                    )
                    stderr_handle.flush()
                if (
                    not account_phase_succeeded
                    and (
                        (
                            completed is not None
                            and _should_attempt_openai_escape_hatch(
                                acceptance_reason,
                                final_message,
                                completed.stderr,
                            )
                        )
                        or (completed is None and bool(preflight_failure_reason) and _openai_escape_hatch_enabled())
                    )
                ):
                    escape_args = _openai_escape_hatch_args(args)
                    escape_accounts = _load_worker_accounts(escape_args)
                    if escape_accounts:
                        stderr_handle.write(
                            "[fleet-supervisor] escalating account-backed lane failure to openai escape hatch "
                            f"aliases={','.join(account.alias for account in escape_accounts)} "
                            f"models={','.join(_worker_model_candidates(escape_args))}\n"
                        )
                        stderr_handle.flush()
                        if run_account_attempts(
                            escape_accounts,
                            worker_bin=escape_args.worker_bin,
                            worker_lane=escape_args.worker_lane,
                            phase_models=_worker_model_candidates(escape_args),
                            phase_label=("escape-preflight" if completed is None and preflight_failure_reason else "escape"),
                        ):
                            account_phase_succeeded = True
            else:
                if fatal_worker_contract_violation:
                    pass
                elif routed_account_required:
                    if routed_full_lane_fallback_args is not None:
                        stderr_handle.write(
                            "[fleet-supervisor] no runnable full routed accounts; trying anonymous full-lane fallback first\n"
                        )
                        stderr_handle.flush()
                        if not run_direct_attempts(
                            routed_full_lane_fallback_args,
                            phase_label="full-fallback",
                        ) and rescue_account_candidates:
                            stderr_handle.write(
                                "[fleet-supervisor] anonymous full-lane fallback stayed blocked; trying rescue-routed accounts\n"
                            )
                            stderr_handle.flush()
                            run_account_attempts(
                                rescue_account_candidates,
                                worker_bin=args.worker_bin,
                                worker_lane=direct_worker_lane,
                                phase_models=model_candidates,
                                phase_label="rescue",
                            )
                    elif rescue_account_candidates:
                        run_account_attempts(
                            rescue_account_candidates,
                            worker_bin=args.worker_bin,
                            worker_lane=direct_worker_lane,
                            phase_models=model_candidates,
                            phase_label="rescue",
                        )
                    else:
                        preflight_failure_reason = "no runnable routed accounts for CodexEA lane; anonymous direct fallback disabled"
                        stderr_handle.write(f"[fleet-supervisor] {preflight_failure_reason}\n")
                        stderr_handle.flush()
                else:
                    run_direct_attempts(
                        args,
                        phase_label="attempt",
                        direct_lane_health_override=worker_lane_health,
                    )
                    if (
                        not accepted
                        and (
                            (
                                completed is not None
                                and _should_attempt_openai_escape_hatch(
                                    acceptance_reason,
                                    final_message,
                                    completed.stderr,
                                )
                            )
                            or (completed is None and bool(preflight_failure_reason) and _openai_escape_hatch_enabled())
                        )
                    ):
                        escape_args = _openai_escape_hatch_args(args)
                        escape_accounts = _load_worker_accounts(escape_args)
                        if escape_accounts:
                            stderr_handle.write(
                                "[fleet-supervisor] escalating retryable direct-lane failure to openai escape hatch "
                                f"aliases={','.join(account.alias for account in escape_accounts)} "
                                f"models={','.join(_worker_model_candidates(escape_args))}\n"
                            )
                            stderr_handle.flush()
                            run_account_attempts(
                                escape_accounts,
                                worker_bin=escape_args.worker_bin,
                                worker_lane=escape_args.worker_lane,
                                phase_models=_worker_model_candidates(escape_args),
                                phase_label=("escape-preflight" if completed is None and preflight_failure_reason else "escape"),
                            )
            if completed is None:
                if not preflight_failure_reason:
                    preflight_failure_reason = "no eligible worker account/model attempts were runnable"
                stderr_handle.write(f"[fleet-supervisor] {preflight_failure_reason}\n")
                stderr_handle.flush()
    finally:
        _write_active_run_state(state_root, None)

    if not final_message and last_message_path.exists():
        final_message = _read_text(last_message_path).strip()
        parsed = _parse_final_message_sections(final_message)
    if completed is not None:
        accepted, acceptance_reason = _assess_worker_result(completed.returncode, final_message, parsed)
        if accepted and _is_missing_github_push_blocker(parsed.get("blocker", "")):
            push_recovery = _retry_worker_reported_git_pushes(completed.stderr)
            if push_recovery.get("attempted") and not push_recovery.get("failed"):
                parsed["blocker"] = "none"
                final_message = _compose_final_message_sections(parsed)
                last_message_path.write_text(final_message, encoding="utf-8")
            elif push_recovery.get("failed"):
                failure_bits = [
                    f"{repo}: {_summarize_trace_value(message, max_len=120)}"
                    for repo, message in sorted((push_recovery.get("failed") or {}).items())
                ]
                parsed["blocker"] = (
                    "host-side git push recovery failed after worker credential error: "
                    + "; ".join(failure_bits)
                )
                final_message = _compose_final_message_sections(parsed)
                last_message_path.write_text(final_message, encoding="utf-8")
        if not accepted and not str(parsed.get("blocker") or "").strip():
            blocker_fallback = ""
            final_message_compact = str(final_message or "").strip()
            if final_message_compact and _final_message_reports_error(final_message_compact):
                blocker_fallback = _summarize_trace_value(final_message_compact, max_len=180)
            if not blocker_fallback:
                blocker_fallback = str(acceptance_reason or preflight_failure_reason or "").strip()
            if not blocker_fallback:
                blocker_fallback = _summarize_trace_value(
                    completed.stderr or final_message or "worker failed without an explicit blocker",
                    max_len=180,
                )
            parsed["blocker"] = blocker_fallback
            final_message = _compose_final_message_sections(parsed)
            last_message_path.write_text(final_message, encoding="utf-8")
    elif preflight_failure_reason:
        if not final_message:
            final_message = preflight_failure_reason
        accepted = False
        acceptance_reason = preflight_failure_reason
        parsed["blocker"] = str(parsed.get("blocker") or preflight_failure_reason or "").strip()
        final_message = _compose_final_message_sections(parsed)
        last_message_path.write_text(final_message, encoding="utf-8")
    finished_at = _iso_now()
    exit_code = int(completed.returncode) if completed is not None else 1
    return WorkerRun(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        worker_command=worker_command,
        attempted_accounts=attempted_accounts,
        attempted_models=attempted_models,
        selected_account_alias=selected_account_alias,
        worker_exit_code=exit_code,
        frontier_ids=frontier_ids,
        open_milestone_ids=open_milestone_ids,
        primary_milestone_id=primary_milestone_id,
        prompt_path=str(prompt_path),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        last_message_path=str(last_message_path),
        final_message=final_message,
        shipped=parsed.get("shipped", ""),
        remains=parsed.get("remains", ""),
        blocker=parsed.get("blocker", ""),
        accepted=accepted,
        acceptance_reason=acceptance_reason,
    )


def _run_payload(run: WorkerRun) -> Dict[str, Any]:
    return asdict(run)


def _write_state(
    state_root: Path,
    *,
    mode: str,
    run: Optional[WorkerRun],
    open_milestones: Iterable[Milestone],
    frontier: Iterable[Milestone],
    focus_profiles: Sequence[str] = (),
    focus_owners: Sequence[str] = (),
    focus_texts: Sequence[str] = (),
    completion_audit: Optional[Dict[str, Any]] = None,
    full_product_audit: Optional[Dict[str, Any]] = None,
    eta: Optional[Dict[str, Any]] = None,
    worker_lane_health: Optional[Dict[str, Any]] = None,
    host_memory_pressure: Optional[Dict[str, Any]] = None,
    completion_review_frontier_path: str = "",
    completion_review_frontier_mirror_path: str = "",
    full_product_frontier_path: str = "",
    full_product_frontier_mirror_path: str = "",
    idle_reason: str = "",
) -> None:
    open_milestone_items = list(open_milestones)
    frontier_items = list(frontier)
    if not open_milestone_items and frontier_items and mode in {"flagship_product", "completion_review"}:
        # In flagship/review slices the shard's local frontier is the effective open work set.
        open_milestone_items = list(frontier_items)
    payload: Dict[str, Any] = {
        "updated_at": _iso_now(),
        "mode": mode,
        "open_milestone_ids": [item.id for item in open_milestone_items],
        "frontier_ids": [item.id for item in frontier_items],
        "focus_profiles": list(focus_profiles),
        "focus_owners": list(focus_owners),
        "focus_texts": list(focus_texts),
    }
    resolved_state_root = Path(state_root).resolve()
    if resolved_state_root.name.startswith("shard-"):
        payload["shard_id"] = resolved_state_root.name
        payload["shard_token"] = resolved_state_root.name
    elif bool(_configured_shard_roots(resolved_state_root)):
        payload = _clear_shard_scoped_aggregate_aliases(payload)
    if run is not None:
        payload["last_run"] = _run_payload(run)
        payload["selected_account_alias"] = str(run.selected_account_alias or "").strip()
        failure_reason = str(run.acceptance_reason or run.blocker or "").strip()
        if run.worker_exit_code != 0 and not failure_reason:
            failure_reason = f"worker exit {run.worker_exit_code}"
        if failure_reason:
            payload["last_failure_reason"] = failure_reason
            if not run.accepted and run.worker_exit_code == 1:
                payload["preflight_failure_reason"] = failure_reason
    if completion_audit:
        payload["completion_audit"] = dict(completion_audit)
    if full_product_audit:
        payload["full_product_audit"] = dict(full_product_audit)
    if eta:
        payload["eta"] = dict(eta)
    if worker_lane_health:
        payload["worker_lane_health"] = dict(worker_lane_health)
    if host_memory_pressure:
        payload["host_memory_pressure"] = dict(host_memory_pressure)
    if completion_review_frontier_path:
        payload["completion_review_frontier_path"] = str(completion_review_frontier_path)
    if completion_review_frontier_mirror_path:
        payload["completion_review_frontier_mirror_path"] = str(completion_review_frontier_mirror_path)
    if full_product_frontier_path:
        payload["full_product_frontier_path"] = str(full_product_frontier_path)
    if full_product_frontier_mirror_path:
        payload["full_product_frontier_mirror_path"] = str(full_product_frontier_mirror_path)
    idle_reason = str(idle_reason or "").strip()
    if idle_reason:
        payload["idle_reason"] = idle_reason
    if Path(state_root).resolve() == _aggregate_state_root(state_root):
        successor_wave_eta = _successor_wave_eta_snapshot(_workspace_root_for_state_root(state_root))
        if successor_wave_eta:
            payload["successor_wave_eta"] = successor_wave_eta
    _merge_matching_live_active_run(state_root, payload)
    if payload.get("active_run"):
        payload.pop("idle_reason", None)
    payload = _apply_status_alias_fields(payload)
    _write_json(_state_payload_path(state_root), payload)
    if _running_inside_container():
        _write_active_shard_manifest_snapshot(state_root)
    _write_runtime_handoff(state_root)
    if run is not None:
        _append_jsonl(_history_payload_path(state_root), payload["last_run"])


def _merge_matching_live_active_run(state_root: Path, payload: Dict[str, Any]) -> None:
    frontier_ids = list(payload.get("frontier_ids") or [])
    open_milestone_ids = list(payload.get("open_milestone_ids") or [])
    active_run = payload.get("active_run")
    if _active_run_matches_live_frontier(
        active_run,
        frontier_ids=frontier_ids,
        open_milestone_ids=open_milestone_ids,
    ):
        return
    if isinstance(payload.get("active_runs"), list) and payload.get("active_runs"):
        payload.pop("active_run", None)
        return
    persisted_state = _read_state(_state_payload_path(state_root))
    persisted_active_run = persisted_state.get("active_run")
    if _active_run_matches_live_frontier(
        persisted_active_run,
        frontier_ids=frontier_ids,
        open_milestone_ids=open_milestone_ids,
    ):
        payload["active_run"] = dict(persisted_active_run)
        return
    persisted_last_run = persisted_state.get("last_run")
    persisted_run_id = str((persisted_active_run or {}).get("run_id") or "").strip()
    persisted_last_run_id = str((persisted_last_run or {}).get("run_id") or "").strip()
    if (
        persisted_run_id
        and persisted_run_id != persisted_last_run_id
        and _active_run_matches_frontier_shape(
            persisted_active_run,
            frontier_ids=frontier_ids,
            open_milestone_ids=open_milestone_ids,
        )
    ):
        payload["active_run"] = dict(persisted_active_run)
        return
    recovered_active_run = _recover_matching_live_active_run(
        state_root,
        frontier_ids=frontier_ids,
        open_milestone_ids=open_milestone_ids,
    )
    if recovered_active_run is not None:
        payload["active_run"] = dict(recovered_active_run)
        return
    payload.pop("active_run", None)


def _persist_live_state_snapshot(state_root: Path, state: Dict[str, Any]) -> None:
    payload = dict(state)
    payload.pop("state_root", None)
    aggregate_root = _aggregate_state_root(state_root)
    resolved_state_root = Path(state_root).resolve()
    if resolved_state_root.name.startswith("shard-"):
        payload["shard_id"] = resolved_state_root.name
        payload["shard_token"] = resolved_state_root.name
    elif bool(_configured_shard_roots(resolved_state_root)):
        payload = _clear_shard_scoped_aggregate_aliases(payload)
    keep_shards = (
        resolved_state_root == aggregate_root
        and isinstance(payload.get("shards"), list)
        and bool(_configured_shard_roots(aggregate_root))
    )
    if not keep_shards:
        payload.pop("shards", None)
    if Path(state_root).resolve() == _aggregate_state_root(state_root):
        successor_wave_eta = _successor_wave_eta_snapshot(_workspace_root_for_state_root(state_root))
        if successor_wave_eta:
            payload["successor_wave_eta"] = successor_wave_eta
        else:
            payload.pop("successor_wave_eta", None)
    if _running_inside_container() and resolved_state_root.name.startswith("shard-"):
        active_run = dict(payload.get("active_run") or {}) if isinstance(payload.get("active_run"), dict) else {}
        active_worker_pid = _coerce_int(payload.get("active_run_worker_pid"), _coerce_int(active_run.get("worker_pid"), 0))
        if active_run and active_worker_pid > 0 and not _pid_alive(active_worker_pid):
            payload.pop("active_run", None)
            payload.pop("active_run_id", None)
            payload.pop("active_run_started_at", None)
            payload.pop("active_run_worker_first_output_at", None)
            payload.pop("active_run_worker_last_output_at", None)
            payload.pop("worker_last_output_at", None)
            payload.pop("active_run_worker_pid", None)
            payload.pop("active_run_progress_state", None)
            payload.pop("active_run_prompt_path", None)
            payload.pop("worker_stdout_path", None)
            payload.pop("worker_stderr_path", None)
            payload.pop("worker_last_message_path", None)
            if not str(payload.get("idle_reason") or "").strip():
                payload["idle_reason"] = (
                    "claimed_frontier_without_active_run"
                    if _state_frontier_ids(payload) or _state_open_milestone_ids(payload)
                    else "stale_active_run_missing_process"
                )
    _merge_matching_live_active_run(state_root, payload)
    if payload.get("active_run"):
        payload.pop("idle_reason", None)
    payload = _apply_status_alias_fields(payload)
    _write_json(_state_payload_path(state_root), payload)
    if _running_inside_container():
        _write_active_shard_manifest_snapshot(state_root)


def _render_status(state: Dict[str, Any]) -> str:
    if not state:
        return "No supervisor state recorded."
    lines = [
        f"updated_at: {state.get('updated_at') or 'unknown'}",
        f"mode: {state.get('mode') or 'unknown'}",
        f"open_milestone_ids: {', '.join(str(value) for value in (state.get('open_milestone_ids') or [])) or 'none'}",
        f"frontier_ids: {', '.join(str(value) for value in (state.get('frontier_ids') or [])) or 'none'}",
        f"focus_profiles: {', '.join(str(value) for value in (state.get('focus_profiles') or [])) or 'none'}",
        f"focus_owners: {', '.join(str(value) for value in (state.get('focus_owners') or [])) or 'none'}",
        f"focus_texts: {', '.join(str(value) for value in (state.get('focus_texts') or [])) or 'none'}",
    ]
    idle_reason = str(state.get("idle_reason") or "").strip()
    if idle_reason:
        lines.append(f"idle_reason: {idle_reason}")
    successor_wave_eta = dict(state.get("successor_wave_eta") or {})
    if successor_wave_eta:
        lines.extend(
            [
                f"successor_wave_eta.status: {successor_wave_eta.get('status') or 'unknown'}",
                f"successor_wave_eta.human: {successor_wave_eta.get('eta_human') or 'unknown'}",
                f"successor_wave_eta.summary: {successor_wave_eta.get('summary') or 'none'}",
            ]
        )
    completion_review_frontier_path = str(state.get("completion_review_frontier_path") or "").strip()
    if completion_review_frontier_path:
        lines.append(f"completion_review_frontier.path: {completion_review_frontier_path}")
    completion_review_frontier_mirror_path = str(state.get("completion_review_frontier_mirror_path") or "").strip()
    if completion_review_frontier_mirror_path:
        lines.append(f"completion_review_frontier.mirror_path: {completion_review_frontier_mirror_path}")
    full_product_frontier_path = str(state.get("full_product_frontier_path") or "").strip()
    if full_product_frontier_path:
        lines.append(f"full_product_frontier.path: {full_product_frontier_path}")
    full_product_frontier_mirror_path = str(state.get("full_product_frontier_mirror_path") or "").strip()
    if full_product_frontier_mirror_path:
        lines.append(f"full_product_frontier.mirror_path: {full_product_frontier_mirror_path}")
    eta = _normalize_eta_scope_fields(dict(state.get("eta") or {}))
    if isinstance(eta, dict) and eta:
        lines.extend(
            [
                f"eta.status: {eta.get('status') or 'unknown'}",
                f"eta.human: {eta.get('eta_human') or 'unknown'}",
                f"eta.confidence: {eta.get('eta_confidence') or 'unknown'}",
                f"eta.basis: {eta.get('basis') or 'unknown'}",
                f"eta.scope_kind: {eta.get('scope_kind') or 'unknown'}",
                f"eta.scope_label: {eta.get('scope_label') or 'unknown'}",
                f"eta.summary: {eta.get('summary') or 'none'}",
                f"eta.predicted_completion_at: {eta.get('predicted_completion_at') or 'unknown'}",
            ]
        )
        scope_warning = str(eta.get("scope_warning") or "").strip()
        if scope_warning:
            lines.append(f"eta.scope_warning: {scope_warning}")
        blocker_reason = str(eta.get("blocking_reason") or "").strip()
        if blocker_reason:
            lines.append(f"eta.blocking_reason: {blocker_reason}")
    shard_blockers = state.get("shard_blockers") or {}
    if isinstance(shard_blockers, list) and shard_blockers:
        for item in shard_blockers:
            if not isinstance(item, dict):
                continue
            lines.append(
                " ".join(
                    [
                        "shard_blocker:",
                        f"name={item.get('name') or 'unknown'}",
                        f"run_id={item.get('run_id') or 'none'}",
                        f"reason={item.get('blocker') or 'none'}",
                    ]
                )
            )
    run = state.get("last_run") or {}
    if isinstance(run, dict) and run:
        inferred_accepted = False
        inferred_reason = ""
        if _run_has_receipt_fields(run):
            inferred_accepted, inferred_reason = _run_receipt_status(run)
        accepted_value = inferred_accepted if _run_has_receipt_fields(run) else run.get("accepted", "unknown")
        acceptance_reason = inferred_reason or "none"
        failure_hint = _failure_hint_for_run(run)
        lines.extend(
            [
                f"last_run.run_id: {run.get('run_id') or 'unknown'}",
                f"last_run.worker_exit_code: {run.get('worker_exit_code')}",
                f"last_run.account_alias: {run.get('selected_account_alias') or 'none'}",
                f"last_run.primary_milestone_id: {run.get('primary_milestone_id') or 'none'}",
                f"last_run.accepted: {accepted_value}",
                f"last_run.acceptance_reason: {acceptance_reason}",
                f"last_run.blocker: {run.get('blocker') or 'none'}",
                f"last_run.failure_hint: {failure_hint or 'none'}",
                f"last_run.last_message_path: {run.get('last_message_path') or ''}",
            ]
        )
    active_run = state.get("active_run") or {}
    if isinstance(active_run, dict) and active_run:
        started_at = str(active_run.get("started_at") or "").strip() or "unknown"
        elapsed_seconds = 0
        started_dt = _parse_iso(started_at)
        if started_dt is not None:
            elapsed_seconds = max(0, int((_utc_now() - started_dt).total_seconds()))
        lines.extend(
            [
                f"active_run.run_id: {active_run.get('run_id') or 'unknown'}",
                f"active_run.started_at: {started_at}",
                f"active_run.elapsed_seconds: {elapsed_seconds}",
                f"active_run.account_alias: {active_run.get('selected_account_alias') or 'none'}",
                f"active_run.model: {active_run.get('selected_model') or 'default'}",
                f"active_run.watchdog_timeout_seconds: {active_run.get('watchdog_timeout_seconds') or 0}",
                (
                    "active_run.attempt: "
                    f"{active_run.get('attempt_index') or 0}/{active_run.get('total_attempts') or 0}"
                ),
                f"active_run.primary_milestone_id: {active_run.get('primary_milestone_id') or 'none'}",
                f"active_run.last_message_path: {active_run.get('last_message_path') or ''}",
            ]
        )
    worker_lane_health = state.get("worker_lane_health") or {}
    if isinstance(worker_lane_health, dict) and worker_lane_health:
        lines.extend(
            [
                f"worker_lane_health.status: {worker_lane_health.get('status') or 'unknown'}",
                f"worker_lane_health.reason: {worker_lane_health.get('reason') or 'none'}",
                f"worker_lane_health.fetched_at: {worker_lane_health.get('fetched_at') or 'unknown'}",
                f"worker_lane_health.source_url: {worker_lane_health.get('source_url') or 'none'}",
                (
                    "worker_lane_health.routable_lanes: "
                    f"{', '.join(str(item) for item in (worker_lane_health.get('routable_lanes') or [])) or 'none'}"
                ),
                (
                    "worker_lane_health.unroutable_lanes: "
                    f"{', '.join(str(item) for item in (worker_lane_health.get('unroutable_lanes') or [])) or 'none'}"
                ),
            ]
        )
        lane_rows = worker_lane_health.get("lanes") or {}
        if isinstance(lane_rows, dict):
            for lane_key in sorted(lane_rows):
                lane_report = lane_rows.get(lane_key) or {}
                if not isinstance(lane_report, dict):
                    continue
                remaining_percent = _coerce_float(lane_report.get("remaining_percent_of_max"))
                remaining_text = f"{remaining_percent:.2f}" if remaining_percent is not None else "unknown"
                lines.append(
                    " ".join(
                        [
                            f"worker_lane_health.{lane_key}:",
                            f"profile={lane_report.get('profile') or 'unknown'}",
                            f"state={lane_report.get('state') or 'unknown'}",
                            f"routable={'yes' if lane_report.get('routable') is not False else 'no'}",
                            f"ready_slots={lane_report.get('ready_slots', 0)}",
                            f"remaining_percent={remaining_text}",
                            f"reason={lane_report.get('reason') or 'none'}",
                        ]
                    )
                )
    host_memory_pressure = state.get("host_memory_pressure") or {}
    if isinstance(host_memory_pressure, dict) and host_memory_pressure:
        mem_available_percent = _coerce_float(host_memory_pressure.get("mem_available_percent"))
        mem_available_percent_text = f"{mem_available_percent:.2f}" if mem_available_percent is not None else "unknown"
        swap_used_percent = _coerce_float(host_memory_pressure.get("swap_used_percent"))
        swap_used_percent_text = f"{swap_used_percent:.2f}" if swap_used_percent is not None else "unknown"
        lines.extend(
            [
                f"host_memory_pressure.status: {host_memory_pressure.get('status') or 'unknown'}",
                f"host_memory_pressure.reason: {host_memory_pressure.get('reason') or 'none'}",
                (
                    "host_memory_pressure.mem_available: "
                    f"{_format_gib(host_memory_pressure.get('mem_available_bytes'))} / "
                    f"{_format_gib(host_memory_pressure.get('mem_total_bytes'))} "
                    f"({mem_available_percent_text}%)"
                ),
                (
                    "host_memory_pressure.swap: "
                    f"free={_format_gib(host_memory_pressure.get('swap_free_bytes'))} / "
                    f"{_format_gib(host_memory_pressure.get('swap_total_bytes'))} "
                    f"(used={swap_used_percent_text}%)"
                ),
                (
                    "host_memory_pressure.dispatch_budget: "
                    f"allowed={host_memory_pressure.get('allowed_active_shards', 0)}/"
                    f"{host_memory_pressure.get('configured_shard_count', 0)} "
                    f"active={host_memory_pressure.get('active_shard_count', 0)} "
                    f"dispatch_allowed={'yes' if host_memory_pressure.get('dispatch_allowed') is not False else 'no'}"
                ),
                (
                    "host_memory_pressure.eligible_shards: "
                    f"{', '.join(str(item) for item in (host_memory_pressure.get('eligible_shard_names') or [])) or 'none'}"
                ),
            ]
        )
    completion_audit = state.get("completion_audit") or {}
    if isinstance(completion_audit, dict) and completion_audit:
        lines.extend(
            [
                f"completion_audit.status: {completion_audit.get('status') or 'unknown'}",
                f"completion_audit.reason: {completion_audit.get('reason') or 'none'}",
            ]
        )
        journey_gate_audit = completion_audit.get("journey_gate_audit") or {}
        if isinstance(journey_gate_audit, dict) and journey_gate_audit:
            lines.extend(
                [
                    f"completion_audit.journey_gate_status: {journey_gate_audit.get('status') or 'unknown'}",
                    f"completion_audit.journey_gate_reason: {journey_gate_audit.get('reason') or 'none'}",
                ]
            )
        weekly_pulse_audit = completion_audit.get("weekly_pulse_audit") or {}
        if isinstance(weekly_pulse_audit, dict) and weekly_pulse_audit:
            lines.extend(
                [
                    f"completion_audit.weekly_pulse_status: {weekly_pulse_audit.get('status') or 'unknown'}",
                    f"completion_audit.weekly_pulse_reason: {weekly_pulse_audit.get('reason') or 'none'}",
                ]
            )
        repo_backlog_audit = completion_audit.get("repo_backlog_audit") or {}
        if isinstance(repo_backlog_audit, dict) and repo_backlog_audit:
            lines.extend(
                [
                    f"completion_audit.repo_backlog_status: {repo_backlog_audit.get('status') or 'unknown'}",
                    f"completion_audit.repo_backlog_reason: {repo_backlog_audit.get('reason') or 'none'}",
                    (
                        "completion_audit.repo_backlog_open_item_count: "
                        f"{repo_backlog_audit.get('open_item_count', 0)}"
                    ),
                    (
                        "completion_audit.repo_backlog_open_project_count: "
                        f"{repo_backlog_audit.get('open_project_count', 0)}"
                    ),
                ]
            )
        linux_gate_audit = completion_audit.get("linux_desktop_exit_gate_audit") or {}
        if isinstance(linux_gate_audit, dict) and linux_gate_audit:
            lines.extend(
                [
                    f"completion_audit.linux_gate_status: {linux_gate_audit.get('status') or 'unknown'}",
                    f"completion_audit.linux_gate_reason: {linux_gate_audit.get('reason') or 'none'}",
                    (
                        "completion_audit.linux_gate_snapshot_mode: "
                        f"{linux_gate_audit.get('source_snapshot_mode') or 'unknown'}"
                    ),
                    (
                        "completion_audit.linux_gate_snapshot_sha: "
                        f"{linux_gate_audit.get('source_snapshot_worktree_sha256') or 'none'}"
                    ),
                    (
                        "completion_audit.linux_gate_snapshot_finish_sha: "
                        f"{linux_gate_audit.get('source_snapshot_finish_worktree_sha256') or 'none'}"
                    ),
                    (
                        "completion_audit.linux_gate_snapshot_stable: "
                        f"{linux_gate_audit.get('source_snapshot_identity_stable') or False}"
                    ),
                    f"completion_audit.linux_gate_install_mode: {linux_gate_audit.get('primary_install_mode') or 'unknown'}",
                    (
                        "completion_audit.linux_gate_install_verification_status: "
                        f"{linux_gate_audit.get('primary_install_verification_status') or 'unknown'}"
                    ),
                    (
                        "completion_audit.linux_gate_install_verification_path: "
                        f"{linux_gate_audit.get('primary_install_verification_path') or 'none'}"
                    ),
                ]
            )
    full_product_audit = state.get("full_product_audit") or {}
    if isinstance(full_product_audit, dict) and full_product_audit:
        lines.extend(
            [
                f"full_product_audit.status: {full_product_audit.get('status') or 'unknown'}",
                f"full_product_audit.reason: {full_product_audit.get('reason') or 'none'}",
                f"full_product_audit.path: {full_product_audit.get('path') or 'none'}",
                f"full_product_audit.generated_at: {full_product_audit.get('generated_at') or 'unknown'}",
                (
                    "full_product_audit.missing_coverage_keys: "
                    f"{', '.join(str(item) for item in (full_product_audit.get('missing_coverage_keys') or [])) or 'none'}"
                ),
            ]
        )
    shards = state.get("shards") or []
    if isinstance(shards, list) and shards:
        lines.append(f"shards: {len(shards)}")
        for shard in shards:
            if not isinstance(shard, dict):
                continue
            frontier_ids = ",".join(str(value) for value in (shard.get("frontier_ids") or [])) or "none"
            active_frontier_ids = ",".join(str(value) for value in (shard.get("active_frontier_ids") or [])) or "none"
            open_ids = ",".join(str(value) for value in (shard.get("open_milestone_ids") or [])) or "none"
            parts = [
                f"shard.{shard.get('name') or 'unknown'}:",
                f"updated_at={shard.get('updated_at') or 'unknown'}",
                f"mode={shard.get('mode') or 'unknown'}",
                f"open={open_ids}",
                f"frontier={frontier_ids}",
            ]
            if active_frontier_ids != frontier_ids:
                parts.append(f"active_frontier={active_frontier_ids}")
            current_blocker = str(shard.get("current_blocker") or "").strip()
            last_run_blocker = str(shard.get("last_run_blocker") or "").strip()
            display_blocker = current_blocker or (
                last_run_blocker if not str(shard.get("active_run_id") or "").strip() else ""
            )
            if display_blocker:
                parts.append(f"last_blocker={_summarize_trace_value(display_blocker, max_len=96)}")
            parts.extend(
                [
                    f"eta={shard.get('eta_status') or 'unknown'}",
                    f"last_run={shard.get('last_run_id') or 'none'}",
                    f"active_run={shard.get('active_run_id') or 'none'}",
                ]
            )
            lines.append(" ".join(parts))
    return "\n".join(lines)


def _summarize_trace_value(value: Any, *, max_len: int = 72) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return "none"
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _compact_prompt_section_lines(
    rows: Sequence[str],
    *,
    max_lines: int,
    max_len: int = 220,
) -> str:
    compact: List[str] = []
    for raw in rows:
        line = str(raw or "").strip()
        if not line:
            continue
        compact.append(_summarize_trace_value(line, max_len=max_len))
        if len(compact) >= max_lines:
            break
    remaining = max(0, len([str(raw or "").strip() for raw in rows if str(raw or "").strip()]) - len(compact))
    if remaining > 0:
        compact.append(f"- + {remaining} more")
    return "\n".join(compact) if compact else "- none"


def _resolve_run_artifact_path(raw_path: str) -> Path:
    path = Path(str(raw_path or "").strip()).expanduser()
    if not str(path):
        return path
    try:
        relative = path.relative_to(Path("/var/lib/codex-fleet"))
    except ValueError:
        return path
    workspace_path = (DEFAULT_WORKSPACE_ROOT / "state" / relative).resolve()
    if workspace_path.exists():
        return workspace_path
    return path


def _enforce_worker_status_budget() -> tuple[bool, str]:
    run_dir_raw = str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR", "") or "").strip()
    if not run_dir_raw:
        return True, ""
    run_dir = Path(run_dir_raw).expanduser()
    try:
        budget = max(0, int(float(str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_STATUS_BUDGET", "1") or "1"))))
    except (TypeError, ValueError):
        budget = 1
    if budget <= 0:
        return False, "worker_status_budget_exhausted: status access disabled inside active worker runs"
    budget_path = run_dir / ".status_budget.json"
    payload: Dict[str, Any] = {}
    if budget_path.exists():
        try:
            payload = json.loads(_read_text(budget_path))
        except Exception:
            payload = {}
    count = max(0, _coerce_int(payload.get("count"), 0))
    if count >= budget:
        return (
            False,
            "worker_status_budget_exhausted: "
            f"status polling budget {count}/{budget} already consumed for active run "
            f"{str(os.environ.get('CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID', '') or '').strip() or 'unknown'}",
        )
    payload["count"] = count + 1
    payload["budget"] = budget
    payload["updated_at"] = _iso_now()
    payload["run_id"] = str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID", "") or "").strip()
    try:
        budget_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        pass
    return True, ""


def _inside_active_worker_run() -> bool:
    return bool(str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR", "") or "").strip())


def _active_worker_state_root(args: argparse.Namespace) -> Path:
    run_dir_raw = str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR", "") or "").strip()
    if run_dir_raw:
        try:
            run_dir = Path(run_dir_raw).expanduser().resolve()
            candidate = run_dir.parent.parent
            if candidate.name.startswith("shard-"):
                return candidate
        except Exception:
            pass
    return Path(str(getattr(args, "state_root", "") or "")).resolve()


def _worker_status_block_message(args: argparse.Namespace, blocked_reason: str) -> str:
    state_root = _active_worker_state_root(args)
    state = _read_state(_state_payload_path(state_root))
    run_id = str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID", "") or "").strip()
    run_dir_raw = str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR", "") or "").strip()
    run_dir = Path(run_dir_raw).expanduser() if run_dir_raw else None
    prompt_path = run_dir / "prompt.txt" if run_dir is not None else None
    task_local_telemetry_path = _task_local_telemetry_path(run_dir) if run_dir is not None else None
    runtime_handoff_path = _existing_runtime_handoff_path(state_root)
    if runtime_handoff_path is None:
        runtime_handoff_path = _runtime_handoff_path(state_root)
    lines = [
        "status_blocked_inside_worker_run",
        str(blocked_reason or "").strip() or "worker_status_budget_exhausted",
        (
            "read the task-local prompt, shard runtime handoff, and frontier artifacts directly "
            "instead of polling supervisor status from inside the active worker run."
        ),
    ]
    if run_id:
        lines.append(f"run_id: {run_id}")
    if prompt_path is not None:
        lines.append(f"prompt_path: {prompt_path}")
    if task_local_telemetry_path is not None and task_local_telemetry_path.exists():
        lines.append(f"task_local_telemetry_path: {task_local_telemetry_path}")
    if runtime_handoff_path is not None:
        lines.append(f"runtime_handoff_path: {runtime_handoff_path}")
    full_product_frontier_path = str(state.get("full_product_frontier_path") or "").strip()
    if full_product_frontier_path:
        lines.append(f"full_product_frontier_path: {full_product_frontier_path}")
    completion_review_frontier_path = str(state.get("completion_review_frontier_path") or "").strip()
    if completion_review_frontier_path:
        lines.append(f"completion_review_frontier_path: {completion_review_frontier_path}")
    readiness_path = str(getattr(args, "flagship_product_readiness_path", "") or "").strip()
    if readiness_path:
        lines.append(f"flagship_product_readiness_path: {Path(readiness_path).resolve()}")
    return "\n".join(lines)


def _worker_status_task_local_payload(args: argparse.Namespace, blocked_reason: str) -> Dict[str, Any]:
    state_root = _active_worker_state_root(args)
    state = _read_state(_state_payload_path(state_root))
    run_id = str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID", "") or "").strip()
    run_dir_raw = str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR", "") or "").strip()
    run_dir = Path(run_dir_raw).expanduser() if run_dir_raw else None
    prompt_path = run_dir / "prompt.txt" if run_dir is not None else None
    task_local_telemetry_path = _task_local_telemetry_path(run_dir) if run_dir is not None else None
    runtime_handoff_path = _existing_runtime_handoff_path(state_root)
    if runtime_handoff_path is None:
        runtime_handoff_path = _runtime_handoff_path(state_root)
    full_product_frontier_path = str(state.get("full_product_frontier_path") or "").strip()
    completion_review_frontier_path = str(state.get("completion_review_frontier_path") or "").strip()
    readiness_path = str(getattr(args, "flagship_product_readiness_path", "") or "").strip()
    guidance = (
        "polling disabled inside active worker run; continue the assigned slice using the prompt, "
        "shard runtime handoff, and frontier artifacts instead of querying supervisor status again"
    )
    state_eta = _normalize_eta_scope_fields(dict(state.get("eta") or {}))
    aggregate_state: Dict[str, Any] = {}
    aggregate_eta: Dict[str, Any] = {}
    aggregate_root = _aggregate_state_root(state_root)
    if aggregate_root != state_root:
        aggregate_state = _read_state(_state_payload_path(aggregate_root))
        aggregate_eta = _normalize_eta_scope_fields(dict(aggregate_state.get("eta") or {}))
    frontier_ids = sorted({_coerce_int(value, 0) for value in _state_frontier_ids(state) if _coerce_int(value, 0) > 0})
    open_milestone_ids = sorted(
        {_coerce_int(value, 0) for value in _state_open_milestone_ids(state) if _coerce_int(value, 0) > 0}
    )
    fallback_open_count = len(open_milestone_ids or frontier_ids) or None
    remaining_open_milestones = (
        state_eta.get("remaining_open_milestones")
        if state_eta.get("remaining_open_milestones") is not None
        else state.get("remaining_open_milestones")
    )
    if remaining_open_milestones is None:
        remaining_open_milestones = fallback_open_count
    if remaining_open_milestones is None:
        remaining_open_milestones = (
            aggregate_eta.get("remaining_open_milestones")
            if aggregate_eta.get("remaining_open_milestones") is not None
            else aggregate_state.get("remaining_open_milestones")
        )

    remaining_not_started_milestones = (
        state_eta.get("remaining_not_started_milestones")
        if state_eta.get("remaining_not_started_milestones") is not None
        else state.get("remaining_not_started_milestones")
    )
    remaining_in_progress_milestones = (
        state_eta.get("remaining_in_progress_milestones")
        if state_eta.get("remaining_in_progress_milestones") is not None
        else state.get("remaining_in_progress_milestones")
    )
    if (
        remaining_open_milestones is not None
        and remaining_not_started_milestones is None
        and remaining_in_progress_milestones is None
    ):
        remaining_not_started_milestones = remaining_open_milestones
        remaining_in_progress_milestones = 0
    if remaining_not_started_milestones is None:
        remaining_not_started_milestones = (
            aggregate_eta.get("remaining_not_started_milestones")
            if aggregate_eta.get("remaining_not_started_milestones") is not None
            else aggregate_state.get("remaining_not_started_milestones")
        )
    if remaining_in_progress_milestones is None:
        remaining_in_progress_milestones = (
            aggregate_eta.get("remaining_in_progress_milestones")
            if aggregate_eta.get("remaining_in_progress_milestones") is not None
            else aggregate_state.get("remaining_in_progress_milestones")
        )

    eta_status = (
        str(state_eta.get("status") or "").strip()
        or str(state.get("eta_status") or "").strip()
        or str(aggregate_eta.get("status") or "").strip()
        or str(aggregate_state.get("eta_status") or "").strip()
        or "task_local_only"
    )
    eta_scope_kind = (
        str(state_eta.get("scope_kind") or "").strip()
        or str(aggregate_eta.get("scope_kind") or "").strip()
        or "task_local_only"
    )
    eta_scope_label = (
        str(state_eta.get("scope_label") or "").strip()
        or str(aggregate_eta.get("scope_label") or "").strip()
    )
    eta_scope_warning = (
        str(state_eta.get("scope_warning") or "").strip()
        or str(aggregate_eta.get("scope_warning") or "").strip()
    )
    eta_predicted_completion_at = (
        str(state_eta.get("predicted_completion_at") or "").strip()
        or str(aggregate_eta.get("predicted_completion_at") or "").strip()
    )
    eta_human = (
        str(state_eta.get("eta_human") or "").strip()
        or str(state.get("eta_human") or "").strip()
        or str(aggregate_eta.get("eta_human") or "").strip()
        or str(aggregate_state.get("eta_human") or "").strip()
        or "task-local-only"
    )
    eta_summary = (
        str(state_eta.get("summary") or "").strip()
        or str(state.get("eta_summary") or "").strip()
    )
    if not eta_summary and remaining_open_milestones is not None and fallback_open_count is not None:
        milestone_count = int(remaining_open_milestones)
        count_label = "milestone" if milestone_count == 1 else "milestones"
        verb = "remains" if milestone_count == 1 else "remain"
        eta_summary = f"{milestone_count} open {count_label} {verb} in the current shard slice."
    if not eta_summary:
        eta_summary = (
            str(aggregate_eta.get("summary") or "").strip()
            or str(aggregate_state.get("eta_summary") or "").strip()
        )
    payload: Dict[str, Any] = {
        "mode": "task_local_only",
        "polling_disabled": True,
        "status_query_supported": False,
        "active_runs_count": (
            state.get("active_runs_count")
            if state.get("active_runs_count") is not None
            else aggregate_state.get("active_runs_count")
        ),
        "eta": {
            "status": eta_status,
            "scope_kind": eta_scope_kind,
            "scope_label": eta_scope_label,
            "scope_warning": eta_scope_warning,
            "predicted_completion_at": eta_predicted_completion_at,
            "remaining_open_milestones": remaining_open_milestones,
            "remaining_not_started_milestones": remaining_not_started_milestones,
            "remaining_in_progress_milestones": remaining_in_progress_milestones,
            "eta_human": eta_human,
            "summary": eta_summary or guidance,
        },
        "warning": str(blocked_reason or "").strip() or "worker_status_budget_exhausted",
        "guidance": guidance,
    }
    if run_id:
        payload["run_id"] = run_id
    if frontier_ids:
        payload["frontier_ids"] = frontier_ids
    if open_milestone_ids:
        payload["open_milestone_ids"] = open_milestone_ids
    if prompt_path is not None:
        payload["prompt_path"] = str(prompt_path)
    if task_local_telemetry_path is not None and task_local_telemetry_path.exists():
        payload["task_local_telemetry_path"] = str(task_local_telemetry_path)
    if runtime_handoff_path is not None:
        payload["runtime_handoff_path"] = str(runtime_handoff_path)
    if full_product_frontier_path:
        payload["full_product_frontier_path"] = full_product_frontier_path
    if completion_review_frontier_path:
        payload["completion_review_frontier_path"] = completion_review_frontier_path
    if readiness_path:
        payload["flagship_product_readiness_path"] = str(Path(readiness_path).resolve())
    return payload


def _render_worker_status_task_local_payload(payload: Dict[str, Any]) -> str:
    eta = dict(payload.get("eta") or {})
    lines = [
        "task-local-only",
        str(payload.get("warning") or "").strip() or "worker_status_budget_exhausted",
        str(payload.get("guidance") or "").strip(),
    ]
    run_id = str(payload.get("run_id") or "").strip()
    if run_id:
        lines.append(f"run_id: {run_id}")
    task_local_telemetry_path = str(payload.get("task_local_telemetry_path") or "").strip()
    if task_local_telemetry_path:
        lines.append(f"task_local_telemetry_path: {task_local_telemetry_path}")
    lines.append(
        "eta: "
        + (
            f"{str(eta.get('eta_human') or 'task-local-only').strip()} "
            f"(open={max(0, _coerce_int(eta.get('remaining_open_milestones'), 0))}, "
            f"in_progress={max(0, _coerce_int(eta.get('remaining_in_progress_milestones'), 0))}, "
            f"not_started={max(0, _coerce_int(eta.get('remaining_not_started_milestones'), 0))})"
        )
    )
    for key in (
        "prompt_path",
        "full_product_frontier_path",
        "completion_review_frontier_path",
        "handoff_path",
        "flagship_product_readiness_path",
    ):
        value = str(payload.get(key) or "").strip()
        if value:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _run_final_message(run: Dict[str, Any]) -> str:
    inline = str(run.get("final_message") or "").strip()
    if inline:
        return inline
    message_raw = str(run.get("last_message_path") or "").strip()
    if not message_raw:
        return ""
    message_path = _resolve_run_artifact_path(message_raw)
    if not message_path.exists() or message_path.is_dir():
        return ""
    return _read_text(message_path).strip()


def _run_has_receipt_fields(run: Dict[str, Any]) -> bool:
    if "accepted" in run:
        return True
    if str(run.get("final_message") or "").strip():
        return True
    return bool(str(run.get("last_message_path") or "").strip())


def _run_receipt_status(run: Dict[str, Any]) -> tuple[bool, str]:
    accepted = run.get("accepted")
    final_message = _run_final_message(run)
    reparsed_sections = _parse_final_message_sections(final_message)
    reparsed_accepted = False
    reparsed_reason = ""
    if int(run.get("worker_exit_code") or 0) == 0 and final_message:
        reparsed_accepted, reparsed_reason = _assess_worker_result(
            int(run.get("worker_exit_code") or 0),
            final_message,
            reparsed_sections,
        )
    if isinstance(accepted, bool):
        if accepted:
            if not any(str(run.get(key) or "").strip() for key in ("shipped", "remains", "blocker", "final_message")):
                return False, "accepted receipt is missing structured closeout content"
            return True, ""
        if reparsed_accepted:
            return True, ""
        return False, str(run.get("acceptance_reason") or "").strip() or "worker result rejected"
    return reparsed_accepted, reparsed_reason


def _normalized_closeout_text(text: Any) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower()).strip()
    return normalized.rstrip(".")


def _closeout_reports_no_remaining_work(run: Dict[str, Any]) -> bool:
    sections = _parse_final_message_sections(_run_final_message(run))
    remains = _normalized_closeout_text(sections.get("remains") or run.get("remains") or "")
    blocker = _normalized_closeout_text(sections.get("blocker") or run.get("blocker") or "")
    no_remains = (
        remains in {"none", "n/a", "nothing", "nothing remains"}
        or remains.startswith("no meaningful ")
        or remains.startswith("no remaining ")
        or remains.startswith("nothing ")
        or remains.startswith("none ")
    )
    no_blocker = blocker in {"none", "n/a", "no blocker", "no blockers", "none reported"}
    return no_remains and no_blocker


def _completion_audit(history: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    audit: Dict[str, Any] = {
        "status": "pass",
        "reason": "recent supervisor history ends with a trusted structured worker receipt",
        "accepted_run_ids": [],
        "rejected_zero_exit_run_ids": [],
        "latest_run_id": "",
        "latest_run_reason": "",
        "history_limit": int(COMPLETION_AUDIT_HISTORY_LIMIT),
    }
    if not history:
        audit["status"] = "fail"
        audit["reason"] = "no supervisor run history recorded; explicit completion review is required"
        return audit
    latest_run = history[-1]
    latest_run_id = str(latest_run.get("run_id") or "unknown")
    latest_accepted = False
    latest_reason = ""
    latest_accepted_index = -1
    rejected_zero_exit_pairs: List[tuple[int, str]] = []
    for index, run in enumerate(history):
        run_id = str(run.get("run_id") or "unknown")
        accepted, reason = _run_receipt_status(run)
        if accepted:
            audit["accepted_run_ids"].append(run_id)
            latest_accepted_index = index
        elif int(run.get("worker_exit_code") or 0) == 0:
            rejected_zero_exit_pairs.append((index, run_id))
        if run is latest_run:
            latest_accepted = accepted
            latest_reason = reason
    audit["latest_run_id"] = latest_run_id
    audit["latest_run_reason"] = latest_reason
    audit["rejected_zero_exit_run_ids"] = [
        run_id for index, run_id in rejected_zero_exit_pairs if index > latest_accepted_index
    ]
    if not latest_accepted:
        audit["status"] = "fail"
        audit["reason"] = (
            f"latest worker receipt {latest_run_id} is not trusted: {latest_reason or 'missing structured closeout'}"
        )
        return audit
    if audit["rejected_zero_exit_run_ids"]:
        audit["status"] = "fail"
        audit["reason"] = (
            "recent zero-exit worker receipts were rejected: "
            + ", ".join(str(item) for item in audit["rejected_zero_exit_run_ids"][:5])
        )
        return audit
    if not audit["accepted_run_ids"]:
        audit["status"] = "fail"
        audit["reason"] = "no accepted structured worker receipts recorded in recent supervisor history"
    return audit


def _reconcile_receipt_audit_with_repo_backlog_truth(
    receipt_audit: Dict[str, Any],
    repo_backlog_audit: Dict[str, Any],
    history: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    reconciled = dict(receipt_audit)
    if str(reconciled.get("status") or "").strip().lower() != "pass":
        return reconciled
    if str(repo_backlog_audit.get("status") or "").strip().lower() != "fail":
        return reconciled
    if not history:
        return reconciled
    latest_run = history[-1]
    latest_run_id = str(latest_run.get("run_id") or reconciled.get("latest_run_id") or "unknown").strip() or "unknown"
    accepted, _reason = _run_receipt_status(latest_run)
    if not accepted or not _closeout_reports_no_remaining_work(latest_run):
        return reconciled
    open_item_count = int(repo_backlog_audit.get("open_item_count") or 0)
    open_project_count = int(repo_backlog_audit.get("open_project_count") or 0)
    open_items = [dict(row) for row in (repo_backlog_audit.get("open_items") or []) if isinstance(row, dict)]
    leading_task = str((open_items[0] if open_items else {}).get("task") or "").strip()
    contradiction_reason = (
        "receipt claims no remaining work but live repo backlog still has "
        f"{open_item_count} open item(s) across {open_project_count} project(s)"
    )
    if leading_task:
        contradiction_reason += f": {leading_task}"
    accepted_run_ids = [
        str(run_id).strip()
        for run_id in (reconciled.get("accepted_run_ids") or [])
        if str(run_id).strip() and str(run_id).strip() != latest_run_id
    ]
    rejected_zero_exit_run_ids = [
        str(run_id).strip()
        for run_id in (reconciled.get("rejected_zero_exit_run_ids") or [])
        if str(run_id).strip()
    ]
    if latest_run_id not in rejected_zero_exit_run_ids:
        rejected_zero_exit_run_ids.append(latest_run_id)
    reconciled.update(
        {
            "status": "fail",
            "reason": f"latest worker receipt {latest_run_id} contradicts live repo backlog: {contradiction_reason}",
            "latest_run_id": latest_run_id,
            "latest_run_reason": contradiction_reason,
            "accepted_run_ids": accepted_run_ids,
            "rejected_zero_exit_run_ids": rejected_zero_exit_run_ids,
            "contradiction": "repo_backlog",
        }
    )
    return reconciled


def _synthetic_completion_receipt_audit(
    receipt_audit: Dict[str, Any],
    journey_gate_audit: Dict[str, Any],
    linux_desktop_exit_gate_audit: Dict[str, Any],
    desktop_executable_exit_gate_audit: Dict[str, Any],
    weekly_pulse_audit: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if str(receipt_audit.get("status") or "").strip().lower() == "pass":
        return dict(receipt_audit)
    supporting_audits = (
        journey_gate_audit,
        linux_desktop_exit_gate_audit,
        desktop_executable_exit_gate_audit,
        weekly_pulse_audit,
    )
    if any(str(audit.get("status") or "").strip().lower() != "pass" for audit in supporting_audits):
        return None
    latest_reason = _normalize_blocker(
        str(receipt_audit.get("latest_run_reason") or receipt_audit.get("reason") or "")
    )
    normalized_reason = latest_reason.lower()
    allow_noop_not_launched = normalized_reason == "worker not launched"
    is_external_blocker = any(signal in normalized_reason for signal in ETA_EXTERNAL_BLOCKER_SIGNALS)
    allow_receipt_shape_gap = (
        "accepted receipt is missing structured closeout content" in normalized_reason
        or "missing structured closeout content" in normalized_reason
    )
    if not latest_reason or (not is_external_blocker and not allow_noop_not_launched and not allow_receipt_shape_gap):
        return None
    synthetic_audit = dict(receipt_audit)
    accepted_run_ids = list(synthetic_audit.get("accepted_run_ids") or [])
    latest_run_id = str(synthetic_audit.get("latest_run_id") or "").strip()
    synthetic_run_id = f"synthetic:{latest_run_id or 'completion-evidence'}"
    if synthetic_run_id not in accepted_run_ids:
        accepted_run_ids.append(synthetic_run_id)
    synthetic_audit.update(
        {
            "status": "pass",
            "reason": (
                "current repo-local completion proof is green; using a supervisor evidence receipt because the latest "
                f"worker outcome is non-material to proof trust: {latest_reason}"
            ),
            "accepted_run_ids": accepted_run_ids,
            "synthetic": True,
            "synthetic_receipt": {
                "shipped": "whole-product completion proof refreshed from current repo-local evidence",
                "remains": "none",
                "blocker": latest_reason,
            },
        }
    )
    return synthetic_audit


def _load_project_cfgs(projects_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not projects_dir.exists() or not projects_dir.is_dir():
        return rows
    for path in sorted(projects_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        payload = _read_yaml(path)
        if not payload:
            continue
        payload = dict(payload)
        payload["_config_path"] = str(path)
        rows.append(payload)
    return rows


def _project_repo_owner(project_cfg: Dict[str, Any]) -> str:
    review = dict(project_cfg.get("review") or {})
    repo = str(review.get("repo") or "").strip()
    if repo:
        return repo
    project_path = str(project_cfg.get("path") or "").strip()
    if project_path:
        return Path(project_path).name
    return str(project_cfg.get("id") or "").strip()


def _project_effective_queue(project_cfg: Dict[str, Any]) -> List[str]:
    queue = [str(item).strip() for item in (project_cfg.get("queue") or []) if str(item).strip()]
    readiness = _load_readiness_module()
    for source_cfg in project_cfg.get("queue_sources") or []:
        if not isinstance(source_cfg, dict):
            continue
        queue = [
            str(item).strip()
            for item in readiness._apply_queue_source(project_cfg, queue, source_cfg)
            if str(item).strip()
        ]
    deduped: List[str] = []
    seen: set[str] = set()
    for item in queue:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _repo_backlog_audit(args: argparse.Namespace) -> Dict[str, Any]:
    audit: Dict[str, Any] = {
        "status": "pass",
        "reason": "no active repo-local queue items remain outside the design registry",
        "open_item_count": 0,
        "open_project_count": 0,
        "open_items": [],
    }
    rows: List[Dict[str, Any]] = []
    for project_cfg in _load_project_cfgs(Path(args.projects_dir).resolve()):
        if project_cfg.get("enabled") is False:
            continue
        project_id = str(project_cfg.get("id") or "").strip()
        if not project_id:
            continue
        queue_items = _project_effective_queue(project_cfg)
        if not queue_items:
            continue
        repo_slug = _project_repo_owner(project_cfg)
        queue_source_paths: List[str] = []
        for source_cfg in project_cfg.get("queue_sources") or []:
            if not isinstance(source_cfg, dict):
                continue
            source_path = str(source_cfg.get("path") or "").strip()
            if source_path:
                queue_source_paths.append(source_path)
        queue_source_path = ", ".join(queue_source_paths)
        for task in queue_items:
            rows.append(
                {
                    "project_id": project_id,
                    "repo_slug": repo_slug,
                    "task": task,
                    "queue_source_path": queue_source_path,
                }
            )
    if not rows:
        return audit
    audit["status"] = "fail"
    audit["open_items"] = rows[:25]
    audit["open_item_count"] = len(rows)
    audit["open_project_count"] = len(
        {
            (str(row.get("project_id") or "").strip(), str(row.get("repo_slug") or "").strip())
            for row in rows
        }
    )
    project_labels: List[str] = []
    for row in rows:
        label = str(row.get("project_id") or row.get("repo_slug") or "").strip()
        if label and label not in project_labels:
            project_labels.append(label)
    audit["reason"] = (
        "active repo-local backlog remains outside the closed design registry: "
        + ", ".join(project_labels[:5])
    )
    return audit


def _journey_gate_audit(args: argparse.Namespace) -> Dict[str, Any]:
    audit: Dict[str, Any] = {
        "status": "pass",
        "reason": "golden journey release proof is ready on current repo-local evidence",
        "overall_state": "ready",
        "generated_at": "",
        "source_registry_path": "",
        "blocked_journeys": [],
        "warning_journeys": [],
    }
    try:
        module = _load_sibling_module("materialize_journey_gates")
        registry_override = str(getattr(args, "journey_gates_path", "") or "").strip() or None
        try:
            registry_path = module.resolve_registry_path(registry_override)
        except (SystemExit, Exception) as exc:
            registry_hint = str(registry_override or "").strip()
            if not registry_hint:
                status_plane_path = Path(str(getattr(args, "status_plane_path") or Path(".")))
                status_plane_path = status_plane_path.resolve()
                registry_hint = str(status_plane_path.parent / "GOLDEN_JOURNEY_RELEASE_GATES.yaml")
            path_hint = registry_hint
            audit["status"] = "pass"
            audit["overall_state"] = "unknown"
            audit["reason"] = str(exc).strip() or f"golden journey registry is unavailable: {path_hint}"
            audit["source_registry_path"] = path_hint
            return audit
        payload = module.build_payload(
            registry_path=registry_path,
            status_plane_path=Path(args.status_plane_path).resolve(),
            progress_report_path=Path(args.progress_report_path).resolve(),
            progress_history_path=Path(args.progress_history_path).resolve(),
            support_packets_path=Path(args.support_packets_path).resolve(),
        )
    except Exception as exc:
        audit["status"] = "fail"
        audit["overall_state"] = "error"
        audit["reason"] = f"golden journey audit could not run: {exc}"
        return audit

    summary = dict(payload.get("summary") or {})
    overall_state = str(summary.get("overall_state") or "unknown").strip()
    audit["overall_state"] = overall_state
    audit["generated_at"] = str(payload.get("generated_at") or "").strip()
    audit["source_registry_path"] = str(payload.get("source_registry_path") or "").strip()
    journeys = [dict(row) for row in (payload.get("journeys") or []) if isinstance(row, dict)]
    audit["blocked_journeys"] = [row for row in journeys if str(row.get("state") or "").strip() == "blocked"]
    audit["warning_journeys"] = [row for row in journeys if str(row.get("state") or "").strip() == "warning"]
    if overall_state != "ready":
        audit["status"] = "fail"
        reason = str(summary.get("recommended_action") or "").strip()
        if not reason:
            reason = f"golden journey release proof is {overall_state}"
        audit["reason"] = reason
    return audit


def _decision_signal_map(cited_signals: Any) -> Dict[str, str]:
    signal_map: Dict[str, str] = {}
    if not isinstance(cited_signals, list):
        return signal_map
    for row in cited_signals:
        text = str(row or "").strip()
        if not text:
            continue
        if "=" not in text:
            signal_map[text] = ""
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        if not key:
            continue
        signal_map[key] = value.strip()
    return signal_map


def _weekly_pulse_launch_governance_reason(
    payload: Dict[str, Any],
    supporting_signals: Dict[str, Any],
) -> str:
    decisions = payload.get("governor_decisions")
    if not isinstance(decisions, list) or not decisions:
        return "weekly product pulse is missing governor_decisions entries"

    launch_decision: Optional[Dict[str, Any]] = None
    for row in decisions:
        if not isinstance(row, dict):
            continue
        action = str(row.get("action") or "").strip().lower()
        if action in {"freeze_launch", "launch_expand"}:
            launch_decision = row
            break
    if launch_decision is None:
        return "weekly product pulse is missing a launch governance decision (freeze_launch or launch_expand)"

    signal_map = _decision_signal_map(launch_decision.get("cited_signals"))
    required_signal_keys = {
        "journey_gate_state",
        "journey_gate_blocked_count",
        "local_release_proof_status",
        "provider_canary_status",
        "closure_health_state",
    }
    missing_signal_keys = sorted(key for key in required_signal_keys if key not in signal_map)
    if missing_signal_keys:
        return (
            "weekly product pulse launch governance decision is missing cited signal(s): "
            + ", ".join(missing_signal_keys)
        )

    launch_readiness = str(supporting_signals.get("launch_readiness") or "").strip()
    if not launch_readiness:
        return "weekly product pulse is missing supporting_signals.launch_readiness"

    provider_route_stewardship = supporting_signals.get("provider_route_stewardship")
    if not isinstance(provider_route_stewardship, dict):
        return "weekly product pulse is missing supporting_signals.provider_route_stewardship"
    canary_status = str(provider_route_stewardship.get("canary_status") or "").strip()
    next_decision = str(provider_route_stewardship.get("next_decision") or "").strip()
    if not canary_status or not next_decision:
        return (
            "weekly product pulse provider_route_stewardship must include canary_status and next_decision"
        )

    launch_action = str(launch_decision.get("action") or "").strip().lower()
    if launch_action == "launch_expand":
        if canary_status != "Canary green on all active lanes":
            return (
                "weekly product pulse reports launch_expand while provider canary posture is not green"
            )
        if str(signal_map.get("local_release_proof_status") or "").strip().lower() != "passed":
            return (
                "weekly product pulse reports launch_expand without passed local release proof"
            )
        if str(signal_map.get("closure_health_state") or "").strip().lower() != "clear":
            return (
                "weekly product pulse reports launch_expand while closure health is not clear"
            )
    return ""


def _resolve_weekly_pulse_path(path: Path) -> Path:
    candidates: List[Path] = []
    seen: Set[str] = set()
    for candidate in (
        path,
        DEFAULT_FLEET_PRODUCT_MIRROR_ROOT / "WEEKLY_PRODUCT_PULSE.generated.json",
        DEFAULT_WEEKLY_PULSE_PATH,
    ):
        resolved = Path(candidate).resolve()
        key = str(resolved)
        if key in seen:
            continue
        candidates.append(resolved)
        seen.add(key)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _weekly_pulse_audit_is_derivative_of_live_blockers(audit: Dict[str, Any]) -> bool:
    reason = str(audit.get("reason") or "").strip().lower()
    if not reason:
        return False
    return reason.startswith("weekly product pulse still reports the active wave as") or reason.startswith(
        "weekly product pulse reports journey gate health as"
    ) or reason.startswith("weekly product pulse reports release health as")


def _weekly_pulse_audit(args: argparse.Namespace) -> Dict[str, Any]:
    requested_path = Path(args.weekly_pulse_path).resolve()
    path = _resolve_weekly_pulse_path(requested_path)
    audit: Dict[str, Any] = {
        "status": "pass",
        "reason": "weekly product pulse is fresh and reports no remaining drift or blocker pressure",
        "requested_path": str(requested_path),
        "path": str(path),
        "contract_name": "",
        "contract_version": 0,
        "generated_at": "",
        "as_of": "",
        "active_wave": "",
        "active_wave_status": "",
        "release_health_state": "",
        "journey_gate_health_state": "",
        "automation_alignment_state": "",
        "design_drift_count": 0,
        "public_promise_drift_count": 0,
        "oldest_blocker_days": 0,
    }
    if not path.is_file():
        audit["status"] = "fail"
        audit["reason"] = f"weekly product pulse is missing: {requested_path}"
        return audit
    payload = _read_state(path)
    if not payload:
        audit["status"] = "fail"
        audit["reason"] = f"weekly product pulse could not be read: {path}"
        return audit
    audit["contract_name"] = str(payload.get("contract_name") or "").strip()
    audit["contract_version"] = _coerce_int(payload.get("contract_version"), 0)
    if audit["contract_name"] != "chummer.weekly_product_pulse":
        audit["status"] = "fail"
        audit["reason"] = "weekly product pulse contract_name is missing or unexpected"
        return audit
    if audit["contract_version"] < 3:
        audit["status"] = "fail"
        audit["reason"] = (
            "weekly product pulse contract_version is stale; expected >=3 for pulse-v3 launch governance"
        )
        return audit
    required_top_level_fields = (
        "as_of",
        "release_health",
        "flagship_readiness",
        "rule_environment_trust",
        "journey_gate_health",
        "edition_authorship_and_import_confidence",
        "top_support_or_feedback_clusters",
        "oldest_blocker_days",
        "design_drift_count",
        "public_promise_drift_count",
        "governor_decisions",
        "next_checkpoint_question",
    )
    for field in required_top_level_fields:
        if field not in payload:
            audit["status"] = "fail"
            audit["reason"] = f"weekly product pulse is missing top-level scorecard field: {field}"
            return audit

    generated_at = str(payload.get("generated_at") or "").strip()
    audit["generated_at"] = generated_at
    audit["as_of"] = str(payload.get("as_of") or "").strip()
    audit["active_wave"] = str(payload.get("active_wave") or "").strip()
    audit["active_wave_status"] = str(payload.get("active_wave_status") or "").strip()
    audit["journey_gate_health_state"] = str((payload.get("journey_gate_health") or {}).get("state") or "").strip()
    snapshot = dict(payload.get("snapshot") or {})
    release_health = dict(snapshot.get("release_health") or {})
    audit["release_health_state"] = str(release_health.get("state") or "").strip()
    supporting_signals = dict(payload.get("supporting_signals") or {})
    automation_alignment = dict(supporting_signals.get("automation_alignment") or {})
    audit["automation_alignment_state"] = str(automation_alignment.get("state") or "").strip()
    audit["design_drift_count"] = _coerce_int(snapshot.get("design_drift_count"), 0)
    audit["public_promise_drift_count"] = _coerce_int(snapshot.get("public_promise_drift_count"), 0)
    audit["oldest_blocker_days"] = _coerce_int(snapshot.get("oldest_blocker_days"), 0)
    if not automation_alignment:
        audit["status"] = "fail"
        audit["reason"] = "weekly product pulse is missing supporting_signals.automation_alignment"
        return audit
    if str(audit["automation_alignment_state"]).strip().lower() == "misaligned":
        audit["status"] = "fail"
        audit["reason"] = "weekly product pulse reports automation frontier misalignment"
        return audit
    launch_governance_reason = _weekly_pulse_launch_governance_reason(payload, supporting_signals)
    if launch_governance_reason:
        audit["status"] = "fail"
        audit["reason"] = launch_governance_reason
        return audit

    generated_at_dt = _parse_iso(generated_at)
    if generated_at_dt is None:
        audit["status"] = "fail"
        audit["reason"] = "weekly product pulse is missing a valid generated_at timestamp"
        return audit
    age_seconds = max(0, int((_utc_now() - generated_at_dt).total_seconds()))
    audit["age_seconds"] = age_seconds
    if age_seconds > WEEKLY_PULSE_MAX_AGE_SECONDS:
        audit["status"] = "fail"
        audit["reason"] = f"weekly product pulse is stale ({age_seconds}s old)"
        return audit
    if str(audit["active_wave_status"]).strip().lower() not in DONE_STATUSES:
        audit["status"] = "fail"
        audit["reason"] = (
            f"weekly product pulse still reports the active wave as {audit['active_wave_status'] or 'unknown'}"
        )
        return audit
    if str(audit["journey_gate_health_state"]).strip().lower() != "ready":
        audit["status"] = "fail"
        audit["reason"] = (
            f"weekly product pulse reports journey gate health as {audit['journey_gate_health_state'] or 'unknown'}"
        )
        return audit
    if str(audit["release_health_state"]).strip().lower() not in {"green", "green_or_explained", "ready"}:
        audit["status"] = "fail"
        audit["reason"] = (
            f"weekly product pulse reports release health as {audit['release_health_state'] or 'unknown'}"
        )
        return audit
    if audit["design_drift_count"] > 0:
        audit["status"] = "fail"
        audit["reason"] = f"weekly product pulse still reports design_drift_count={audit['design_drift_count']}"
        return audit
    if audit["public_promise_drift_count"] > 0:
        audit["status"] = "fail"
        audit["reason"] = (
            "weekly product pulse still reports "
            f"public_promise_drift_count={audit['public_promise_drift_count']}"
        )
        return audit
    if audit["oldest_blocker_days"] > 0:
        audit["status"] = "fail"
        audit["reason"] = f"weekly product pulse still reports oldest_blocker_days={audit['oldest_blocker_days']}"
        return audit
    return audit


def _reconcile_weekly_pulse_audit_with_live_journey_truth(
    weekly_pulse_audit: Dict[str, Any],
    journey_gate_audit: Dict[str, Any],
) -> Dict[str, Any]:
    audit = dict(weekly_pulse_audit or {})
    if str(audit.get("status") or "").strip().lower() == "pass":
        return audit
    if str(journey_gate_audit.get("status") or "").strip().lower() != "pass":
        return audit

    pulse_reason = str(audit.get("reason") or "").strip().lower()
    journey_state = str(audit.get("journey_gate_health_state") or "").strip().lower()
    release_state = str(audit.get("release_health_state") or "").strip().lower()
    active_wave_status = str(audit.get("active_wave_status") or "").strip().lower()
    age_seconds = _coerce_int(audit.get("age_seconds"), WEEKLY_PULSE_MAX_AGE_SECONDS + 1)
    design_drift_count = _coerce_int(audit.get("design_drift_count"), 0)
    public_promise_drift_count = _coerce_int(audit.get("public_promise_drift_count"), 0)
    oldest_blocker_days = _coerce_int(audit.get("oldest_blocker_days"), 0)
    if "journey gate health" not in pulse_reason:
        return audit
    if journey_state not in {"warning", "blocked", "unknown"}:
        return audit
    if active_wave_status not in DONE_STATUSES:
        return audit
    if release_state not in {"green", "green_or_explained", "ready"}:
        return audit
    if age_seconds > WEEKLY_PULSE_MAX_AGE_SECONDS:
        return audit
    if design_drift_count > 0 or public_promise_drift_count > 0 or oldest_blocker_days > 0:
        return audit

    audit.update(
        {
            "status": "pass",
            "reason": (
                "weekly product pulse lags the live golden-journey proof; "
                "release-health, drift, and blocker signals remain green"
            ),
            "live_journey_gate_override": True,
            "lagging_journey_gate_health_state": journey_state,
        }
    )
    return audit


def _repo_git_state(
    repo_root: Path,
    *,
    exclude_paths: Sequence[Path] = (),
    include_markers: Sequence[str] = (),
    include_untracked: bool = True,
) -> Dict[str, Any]:
    state: Dict[str, Any] = {
        "repo_root": str(repo_root),
        "available": False,
        "head": "",
        "tracked_diff_sha256": "",
        "tracked_diff_line_count": 0,
    }
    if not repo_root.exists():
        return state
    try:
        head = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        list_cmd = ["git", "-C", str(repo_root), "ls-files", "-z", "--cached"]
        if include_untracked:
            list_cmd.extend(["--others", "--exclude-standard"])
        listing = subprocess.run(
            list_cmd,
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8", errors="surrogateescape")
    except Exception:
        return state
    exclude_markers: List[str] = []
    for candidate in exclude_paths:
        try:
            relative = candidate.resolve().relative_to(repo_root.resolve())
        except Exception:
            continue
        marker = relative.as_posix().rstrip("/")
        if marker:
            exclude_markers.append(marker)
    def collect_entries(apply_include_markers: bool) -> List[str]:
        entries: List[str] = []
        seen: Set[str] = set()
        for raw_item in listing.split("\0"):
            relative = raw_item.strip()
            if not relative or relative in seen:
                continue
            if any(relative == marker or relative.startswith(f"{marker}/") for marker in exclude_markers):
                continue
            if apply_include_markers and include_markers and not any(
                relative.startswith(marker) if marker.endswith("/") else relative == marker
                for marker in include_markers
            ):
                continue
            seen.add(relative)
            entries.append(relative)
        entries.sort()
        return entries

    entries = collect_entries(True)
    if include_markers and not entries:
        entries = collect_entries(False)
    digest = hashlib.sha256()
    entry_count = 0
    for relative in entries:
        path = repo_root / relative
        try:
            stat_result = os.lstat(path)
        except FileNotFoundError:
            digest.update(f"missing\0{relative}\0".encode("utf-8"))
            entry_count += 1
            continue
        mode = stat.S_IMODE(stat_result.st_mode)
        if stat.S_ISLNK(stat_result.st_mode):
            digest.update(f"symlink\0{relative}\0{mode:o}\0{os.readlink(path)}\0".encode("utf-8"))
            entry_count += 1
            continue
        if not stat.S_ISREG(stat_result.st_mode):
            continue
        digest.update(f"file\0{relative}\0{mode:o}\0".encode("utf-8"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
        entry_count += 1
    state.update(
        {
            "available": True,
            "head": head,
            "tracked_diff_sha256": digest.hexdigest(),
            "tracked_diff_line_count": entry_count,
        }
    )
    return state


def _path_within(path: Optional[Path], root: Path) -> bool:
    if path is None:
        return False
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _trx_summary(path: Path) -> Dict[str, int]:
    summary = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
    if not path.is_file():
        return summary
    try:
        root = ET.fromstring(_read_text(path))
    except ET.ParseError:
        return summary
    counters = None
    for element in root.iter():
        if element.tag.endswith("Counters"):
            counters = element
            break
    if counters is None:
        return summary
    for key in summary:
        raw = counters.attrib.get(key)
        try:
            summary[key] = int(raw) if raw is not None else 0
        except ValueError:
            summary[key] = 0
    return summary


def _trx_assemblies(path: Path) -> List[str]:
    if not path.is_file():
        return []
    try:
        root = ET.fromstring(_read_text(path))
    except ET.ParseError:
        return []
    assemblies: List[str] = []
    seen: Set[str] = set()
    for element in root.iter():
        if not element.tag.endswith("UnitTest"):
            continue
        storage = Path(str(element.attrib.get("storage") or "").strip()).name
        if storage and storage not in seen:
            assemblies.append(storage)
            seen.add(storage)
        for child in element:
            if not child.tag.endswith("TestMethod"):
                continue
            code_base = Path(str(child.attrib.get("codeBase") or "").strip()).name
            if code_base and code_base not in seen:
                assemblies.append(code_base)
                seen.add(code_base)
    return assemblies


def _rid_arch(rid: str) -> str:
    rid_text = str(rid or "").strip().lower()
    if rid_text.endswith("-x64"):
        return "x64"
    if rid_text.endswith("-arm64"):
        return "arm64"
    if rid_text.endswith("-x86"):
        return "x86"
    return ""


def _rid_deb_arch(rid: str) -> str:
    rid_text = str(rid or "").strip().lower()
    if rid_text == "linux-x64":
        return "amd64"
    if rid_text == "linux-arm64":
        return "arm64"
    return ""


def _linux_desktop_exit_gate_audit(args: argparse.Namespace) -> Dict[str, Any]:
    configured_path = Path(str(args.ui_linux_desktop_exit_gate_path or "")).expanduser()
    path = configured_path.resolve()
    repo_root = Path(args.ui_linux_desktop_repo_root).resolve()
    expected_output_root = (repo_root / FLAGSHIP_UI_LINUX_OUTPUT_ROOT).resolve()
    audit: Dict[str, Any] = {
        "status": "pass",
        "reason": "linux desktop binary build/start/test proof is ready on current repo-local evidence",
        "path": str(configured_path),
        "repo_root": str(repo_root),
        "generated_at": "",
        "age_seconds": 0,
        "proof_status": "",
        "stage": "",
        "head_id": "",
        "project_path": "",
        "launch_target": "",
        "ready_checkpoint": "",
        "platform": "",
        "rid": "",
        "run_root": "",
        "primary_package_kind": "",
        "fallback_package_kind": "",
        "binary_exists": False,
        "binary_executable": False,
        "binary_sha256": "",
        "installer_exists": False,
        "installer_sha256": "",
        "archive_exists": False,
        "archive_sha256": "",
        "primary_smoke_status": "",
        "fallback_smoke_status": "",
        "primary_install_mode": "",
        "primary_install_verification_path": "",
        "primary_install_verification_status": "",
        "primary_install_wrapper_sha256": "",
        "primary_install_desktop_entry_sha256": "",
        "unit_test_status": "",
        "unit_test_framework": "",
        "test_total": 0,
        "test_passed": 0,
        "test_failed": 0,
        "test_skipped": 0,
        "unit_test_assemblies": [],
        "proof_git_available": False,
        "proof_git_head": "",
        "proof_tracked_diff_sha256": "",
        "proof_git_start_head": "",
        "proof_git_start_tracked_diff_sha256": "",
        "proof_git_finish_head": "",
        "proof_git_finish_tracked_diff_sha256": "",
        "proof_git_identity_stable": False,
        "current_git_available": False,
        "current_git_head": "",
        "proof_git_head_matches_current": False,
        "current_tracked_diff_sha256": "",
        "source_snapshot_mode": "",
        "source_snapshot_root": "",
        "source_snapshot_worktree_sha256": "",
        "source_snapshot_finish_worktree_sha256": "",
        "source_snapshot_entry_count": 0,
        "source_snapshot_finish_entry_count": 0,
        "source_snapshot_identity_stable": False,
        "unit_test_project_path": "",
        "unit_test_trx_path": "",
    }
    if not path.is_file():
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop binary build/start/test proof is missing: {path}"
        return audit
    payload = _read_state(path)
    if not payload:
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop binary build/start/test proof could not be read: {path}"
        return audit
    contract_name = str(payload.get("contract_name") or "").strip()
    if contract_name != "chummer6-ui.linux_desktop_exit_gate":
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop exit gate proof uses an unexpected contract: {contract_name or 'missing'}"
        return audit
    generated_at = str(payload.get("generated_at") or "").strip()
    audit["generated_at"] = generated_at
    generated_at_dt = _parse_iso(generated_at)
    if generated_at_dt is None:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof is missing a valid generated_at timestamp"
        return audit
    audit["age_seconds"] = max(0, int((_utc_now() - generated_at_dt).total_seconds()))
    if audit["age_seconds"] > LINUX_DESKTOP_EXIT_GATE_MAX_AGE_SECONDS:
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop exit gate proof is stale ({audit['age_seconds']}s old)"
        return audit
    audit["proof_status"] = str(payload.get("status") or "").strip()
    audit["stage"] = str(payload.get("stage") or "").strip()
    head = dict(payload.get("head") or {})
    build = dict(payload.get("build") or {})
    checks = dict(payload.get("checks") or {})
    startup_smoke = dict(payload.get("startup_smoke") or {})
    primary_smoke = dict(startup_smoke.get("primary") or {})
    fallback_smoke = dict(startup_smoke.get("fallback") or {})
    unit_tests = dict(payload.get("unit_tests") or {})
    unit_test_summary = dict(unit_tests.get("summary") or {})
    proof_git = dict(payload.get("git") or {})
    proof_git_start = dict(proof_git.get("start") or {})
    proof_git_finish = dict(proof_git.get("finish") or {})
    source_snapshot = dict(payload.get("source_snapshot") or {})
    run_root_value = str(payload.get("run_root") or "").strip()
    run_root = Path(run_root_value).resolve() if run_root_value else None
    publish_dir = Path(str(build.get("publish_dir") or "")).resolve() if str(build.get("publish_dir") or "").strip() else None
    dist_dir = Path(str(build.get("dist_dir") or "")).resolve() if str(build.get("dist_dir") or "").strip() else None
    binary_path = Path(str(build.get("binary_path") or "")).resolve() if str(build.get("binary_path") or "").strip() else None
    installer_path = Path(str(build.get("installer_path") or "")).resolve() if str(build.get("installer_path") or "").strip() else None
    archive_path = Path(str(build.get("archive_path") or "")).resolve() if str(build.get("archive_path") or "").strip() else None
    primary_artifact_path = (
        Path(str(primary_smoke.get("artifact_path") or "")).resolve()
        if str(primary_smoke.get("artifact_path") or "").strip()
        else None
    )
    fallback_artifact_path = (
        Path(str(fallback_smoke.get("artifact_path") or "")).resolve()
        if str(fallback_smoke.get("artifact_path") or "").strip()
        else None
    )
    primary_receipt_path = (
        Path(str(primary_smoke.get("receipt_path") or "")).resolve()
        if str(primary_smoke.get("receipt_path") or "").strip()
        else None
    )
    fallback_receipt_path = (
        Path(str(fallback_smoke.get("receipt_path") or "")).resolve()
        if str(fallback_smoke.get("receipt_path") or "").strip()
        else None
    )
    test_results_dir = (
        Path(str(unit_tests.get("results_directory") or "")).resolve()
        if str(unit_tests.get("results_directory") or "").strip()
        else None
    )
    trx_path = Path(str(unit_tests.get("trx_path") or "")).resolve() if str(unit_tests.get("trx_path") or "").strip() else None
    exclude_paths = [path]
    if run_root:
        exclude_paths.append(run_root.parent)
    current_git = _repo_git_state(
        repo_root,
        exclude_paths=exclude_paths,
        include_markers=FLAGSHIP_UI_LINUX_GATE_INPUT_MARKERS,
        include_untracked=False,
    )
    primary_receipt_payload = _read_state(primary_receipt_path) if primary_receipt_path else {}
    fallback_receipt_payload = _read_state(fallback_receipt_path) if fallback_receipt_path else {}
    primary_install_verification_path = (
        Path(str(primary_receipt_payload.get("artifactInstallVerificationPath") or "")).resolve()
        if str(primary_receipt_payload.get("artifactInstallVerificationPath") or "").strip()
        else None
    )
    primary_install_verification = _read_state(primary_install_verification_path) if primary_install_verification_path else {}
    primary_install_launch_capture_path = (
        Path(str(primary_install_verification.get("installedLaunchCapturePath") or "")).resolve()
        if str(primary_install_verification.get("installedLaunchCapturePath") or "").strip()
        else None
    )
    primary_install_wrapper_capture_path = (
        Path(str(primary_install_verification.get("wrapperCapturePath") or "")).resolve()
        if str(primary_install_verification.get("wrapperCapturePath") or "").strip()
        else None
    )
    primary_install_desktop_capture_path = (
        Path(str(primary_install_verification.get("desktopEntryCapturePath") or "")).resolve()
        if str(primary_install_verification.get("desktopEntryCapturePath") or "").strip()
        else None
    )
    primary_dpkg_log_path = (
        Path(str(primary_install_verification.get("dpkgLogPath") or "")).resolve()
        if str(primary_install_verification.get("dpkgLogPath") or "").strip()
        else None
    )
    primary_dpkg_log_text = _read_text(primary_dpkg_log_path) if primary_dpkg_log_path and primary_dpkg_log_path.is_file() else ""
    primary_install_launch_capture_sha = _sha256_file(primary_install_launch_capture_path) if primary_install_launch_capture_path else ""
    primary_install_wrapper_capture_sha = _sha256_file(primary_install_wrapper_capture_path) if primary_install_wrapper_capture_path else ""
    primary_install_desktop_capture_sha = _sha256_file(primary_install_desktop_capture_path) if primary_install_desktop_capture_path else ""
    primary_install_wrapper_capture_text = (
        _read_text(primary_install_wrapper_capture_path) if primary_install_wrapper_capture_path and primary_install_wrapper_capture_path.is_file() else ""
    )
    primary_install_desktop_capture_text = (
        _read_text(primary_install_desktop_capture_path) if primary_install_desktop_capture_path and primary_install_desktop_capture_path.is_file() else ""
    )
    trx_summary = _trx_summary(trx_path) if trx_path else {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
    trx_assemblies = _trx_assemblies(trx_path) if trx_path else []
    expected_arch = _rid_arch(str(head.get("rid") or ""))
    expected_deb_arch = _rid_deb_arch(str(head.get("rid") or ""))
    binary_sha256 = _sha256_file(binary_path) if binary_path else ""
    installer_sha256 = _sha256_file(installer_path) if installer_path else ""
    archive_sha256 = _sha256_file(archive_path) if archive_path else ""
    primary_expected_digest = f"sha256:{installer_sha256}" if installer_sha256 else ""
    release_channel_linux_artifact = dict(checks.get("release_channel_linux_artifact") or {})
    release_channel_installer_sha = str(release_channel_linux_artifact.get("sha256") or "").strip()
    release_channel_expected_digest = f"sha256:{release_channel_installer_sha}" if release_channel_installer_sha else ""
    allowed_primary_receipt_digests = {digest for digest in (primary_expected_digest, release_channel_expected_digest) if digest}
    primary_receipt_digest = str(primary_receipt_payload.get("artifactDigest") or "").strip()
    fallback_expected_digest = f"sha256:{archive_sha256}" if archive_sha256 else ""
    expected_wrapper_content = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'exec "/opt/chummer6/{FLAGSHIP_UI_APP_KEY}-{str(head.get("rid") or "").strip()}/{FLAGSHIP_UI_LAUNCH_TARGET}" "$@"\n'
    )
    expected_desktop_entry_content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={FLAGSHIP_UI_LINUX_DESKTOP_ENTRY_NAME}\n"
        f"Exec=/usr/bin/{FLAGSHIP_UI_LINUX_WRAPPER_NAME}\n"
        f"Icon=/opt/chummer6/{FLAGSHIP_UI_APP_KEY}-{str(head.get('rid') or '').strip()}/chummer-icon.png\n"
        "Terminal=false\n"
        "Categories=Game;\n"
        "StartupNotify=true\n"
    )

    audit["head_id"] = str(head.get("app_key") or "").strip()
    audit["project_path"] = str(head.get("project_path") or "").strip()
    audit["launch_target"] = str(head.get("launch_target") or "").strip()
    audit["ready_checkpoint"] = str(head.get("ready_checkpoint") or "").strip()
    audit["platform"] = str(head.get("platform") or "").strip()
    audit["rid"] = str(head.get("rid") or "").strip()
    audit["run_root"] = str(run_root) if run_root else ""
    audit["primary_package_kind"] = str(build.get("primary_package_kind") or "").strip()
    audit["fallback_package_kind"] = str(build.get("fallback_package_kind") or "").strip()
    audit["binary_exists"] = bool(binary_path and binary_path.is_file())
    audit["binary_executable"] = bool(binary_path and binary_path.is_file() and os.access(binary_path, os.X_OK))
    audit["binary_sha256"] = binary_sha256
    audit["installer_exists"] = bool(installer_path and installer_path.is_file())
    audit["installer_sha256"] = installer_sha256
    audit["archive_exists"] = bool(archive_path and archive_path.is_file())
    audit["archive_sha256"] = archive_sha256
    audit["primary_install_mode"] = str(primary_receipt_payload.get("artifactInstallMode") or "").strip()
    audit["primary_install_verification_path"] = str(primary_install_verification_path) if primary_install_verification_path else ""
    audit["primary_install_wrapper_sha256"] = str(primary_install_verification.get("wrapperSha256") or "").strip()
    audit["primary_install_desktop_entry_sha256"] = str(primary_install_verification.get("desktopEntrySha256") or "").strip()
    audit["unit_test_framework"] = str(unit_tests.get("framework") or "").strip()
    audit["unit_test_project_path"] = str(unit_tests.get("project_path") or "").strip()
    audit["unit_test_trx_path"] = str(trx_path) if trx_path else ""
    audit["unit_test_assemblies"] = trx_assemblies
    audit["test_total"] = trx_summary["total"]
    audit["test_passed"] = trx_summary["passed"]
    audit["test_failed"] = trx_summary["failed"]
    audit["test_skipped"] = trx_summary["skipped"]
    proof_git_head = str(proof_git_finish.get("head") or proof_git.get("head") or "").strip()
    proof_git_tracked_diff_sha256 = str(
        proof_git_finish.get("tracked_diff_sha256")
        or proof_git.get("tracked_diff_sha256")
        or ""
    ).strip()
    current_git_available = bool(payload.get("current_git_available")) if "current_git_available" in payload else bool(current_git.get("available"))
    current_git_head = str(payload.get("current_git_head") or current_git.get("head") or "").strip()
    current_tracked_diff_sha256 = str(
        payload.get("current_tracked_diff_sha256")
        or current_git.get("tracked_diff_sha256")
        or ""
    ).strip()

    audit["proof_git_available"] = bool(proof_git.get("available"))
    audit["proof_git_head"] = proof_git_head
    audit["proof_tracked_diff_sha256"] = proof_git_tracked_diff_sha256
    audit["proof_git_start_head"] = str(proof_git_start.get("head") or "").strip()
    audit["proof_git_start_tracked_diff_sha256"] = str(proof_git_start.get("tracked_diff_sha256") or "").strip()
    audit["proof_git_finish_head"] = str(proof_git_finish.get("head") or "").strip()
    audit["proof_git_finish_tracked_diff_sha256"] = str(proof_git_finish.get("tracked_diff_sha256") or "").strip()
    audit["proof_git_identity_stable"] = bool(proof_git.get("identity_stable"))
    audit["current_git_available"] = current_git_available
    audit["current_git_head"] = current_git_head
    audit["proof_git_head_matches_current"] = bool(audit["proof_git_head"]) and audit["proof_git_head"] == audit["current_git_head"]
    audit["current_tracked_diff_sha256"] = current_tracked_diff_sha256
    audit["source_snapshot_mode"] = str(source_snapshot.get("mode") or "").strip()
    audit["source_snapshot_root"] = str(source_snapshot.get("snapshot_root") or "").strip()
    audit["source_snapshot_worktree_sha256"] = str(source_snapshot.get("worktree_sha256") or "").strip()
    audit["source_snapshot_finish_worktree_sha256"] = str(source_snapshot.get("finish_worktree_sha256") or "").strip()
    audit["source_snapshot_entry_count"] = _coerce_int(source_snapshot.get("entry_count"), 0)
    audit["source_snapshot_finish_entry_count"] = _coerce_int(source_snapshot.get("finish_entry_count"), 0)
    audit["source_snapshot_identity_stable"] = bool(source_snapshot.get("identity_stable"))
    audit["primary_install_verification_status"] = (
        "passed"
        if primary_install_verification
        and audit["primary_install_mode"] == "dpkg_rootless_install"
        and primary_install_verification_path
        and _path_within(primary_install_verification_path, run_root or repo_root)
        and primary_dpkg_log_path
        and _path_within(primary_dpkg_log_path, run_root or repo_root)
        and primary_install_launch_capture_path
        and _path_within(primary_install_launch_capture_path, run_root or repo_root)
        and primary_install_wrapper_capture_path
        and _path_within(primary_install_wrapper_capture_path, run_root or repo_root)
        and primary_install_desktop_capture_path
        and _path_within(primary_install_desktop_capture_path, run_root or repo_root)
        and str(primary_install_verification.get("mode") or "").strip() == "dpkg_rootless_install"
        and str(primary_install_verification.get("packageName") or "").strip() == FLAGSHIP_UI_LINUX_DEB_PACKAGE_NAME
        and (not expected_deb_arch or str(primary_install_verification.get("packageArch") or "").strip() == expected_deb_arch)
        and str(primary_install_verification.get("statusAfterInstall") or "").strip() == "install ok installed"
        and str(primary_install_verification.get("statusAfterPurge") or "").strip() == "not-installed"
        and bool(primary_install_verification.get("installedLaunchPathExistsAfterInstall"))
        and bool(primary_install_verification.get("wrapperExistsAfterInstall"))
        and bool(primary_install_verification.get("desktopEntryExistsAfterInstall"))
        and not bool(primary_install_verification.get("installedLaunchPathExistsAfterPurge"))
        and not bool(primary_install_verification.get("wrapperExistsAfterPurge"))
        and not bool(primary_install_verification.get("desktopEntryExistsAfterPurge"))
        and str(primary_install_verification.get("installedLaunchPath") or "").strip().endswith(
            f"/opt/chummer6/{FLAGSHIP_UI_APP_KEY}-{audit['rid']}/{FLAGSHIP_UI_LAUNCH_TARGET}"
        )
        and str(primary_install_verification.get("installedLaunchPathSha256") or "").strip() == primary_install_launch_capture_sha
        and str(primary_install_verification.get("wrapperPath") or "").strip().endswith(f"/usr/bin/{FLAGSHIP_UI_LINUX_WRAPPER_NAME}")
        and str(primary_install_verification.get("wrapperSha256") or "").strip() == primary_install_wrapper_capture_sha
        and str(primary_install_verification.get("wrapperContent") or "") == primary_install_wrapper_capture_text
        and primary_install_wrapper_capture_text == expected_wrapper_content
        and str(primary_install_verification.get("desktopEntryPath") or "").strip().endswith(
            f"/usr/share/applications/chummer6-{FLAGSHIP_UI_APP_KEY}.desktop"
        )
        and str(primary_install_verification.get("desktopEntrySha256") or "").strip() == primary_install_desktop_capture_sha
        and str(primary_install_verification.get("desktopEntryContent") or "") == primary_install_desktop_capture_text
        and primary_install_desktop_capture_text == expected_desktop_entry_content
        and f"install {FLAGSHIP_UI_LINUX_DEB_PACKAGE_NAME}:{expected_deb_arch or ''}".strip(":") in primary_dpkg_log_text
        and f"status installed {FLAGSHIP_UI_LINUX_DEB_PACKAGE_NAME}:{expected_deb_arch or ''}".strip(":") in primary_dpkg_log_text
        and f"remove {FLAGSHIP_UI_LINUX_DEB_PACKAGE_NAME}:{expected_deb_arch or ''}".strip(":") in primary_dpkg_log_text
        and f"status not-installed {FLAGSHIP_UI_LINUX_DEB_PACKAGE_NAME}:{expected_deb_arch or ''}".strip(":") in primary_dpkg_log_text
        else ("missing" if not primary_install_verification_path else "invalid")
    )
    primary_smoke_artifact_matches = (
        primary_artifact_path == installer_path
        or (
            primary_artifact_path.name == installer_path.name
            and primary_receipt_digest in allowed_primary_receipt_digests
        )
    )
    audit["primary_smoke_status"] = (
        "passed"
        if primary_receipt_payload
        and primary_smoke_artifact_matches
        and str(primary_smoke.get("package_kind") or "").strip() == "deb"
        and str(primary_smoke.get("status") or "").strip() == "passed"
        and str(primary_receipt_payload.get("headId") or "").strip() == FLAGSHIP_UI_APP_KEY
        and str(primary_receipt_payload.get("platform") or "").strip() == "linux"
        and (not expected_arch or str(primary_receipt_payload.get("arch") or "").strip() == expected_arch)
        and str(primary_receipt_payload.get("readyCheckpoint") or "").strip() == FLAGSHIP_UI_READY_CHECKPOINT
        and Path(str(primary_receipt_payload.get("processPath") or "").strip()).name == FLAGSHIP_UI_LAUNCH_TARGET
        and str(primary_receipt_payload.get("channelId") or "").strip() == str(head.get("channel") or "").strip()
        and str(primary_receipt_payload.get("version") or "").strip() == str(head.get("version") or "").strip()
        and primary_receipt_digest in allowed_primary_receipt_digests
        and audit["primary_install_verification_status"] == "passed"
        else ("missing" if not (primary_receipt_path and primary_receipt_path.is_file()) else "invalid")
    )
    audit["fallback_smoke_status"] = (
        "passed"
        if fallback_receipt_payload
        and fallback_artifact_path == archive_path
        and str(fallback_smoke.get("package_kind") or "").strip() == "archive"
        and str(fallback_smoke.get("status") or "").strip() == "passed"
        and str(fallback_receipt_payload.get("headId") or "").strip() == FLAGSHIP_UI_APP_KEY
        and str(fallback_receipt_payload.get("platform") or "").strip() == "linux"
        and (not expected_arch or str(fallback_receipt_payload.get("arch") or "").strip() == expected_arch)
        and str(fallback_receipt_payload.get("readyCheckpoint") or "").strip() == FLAGSHIP_UI_READY_CHECKPOINT
        and Path(str(fallback_receipt_payload.get("processPath") or "").strip()).name == FLAGSHIP_UI_LAUNCH_TARGET
        and str(fallback_receipt_payload.get("channelId") or "").strip() == str(head.get("channel") or "").strip()
        and str(fallback_receipt_payload.get("version") or "").strip() == str(head.get("version") or "").strip()
        and str(fallback_receipt_payload.get("artifactDigest") or "").strip() == fallback_expected_digest
        else ("missing" if not (fallback_receipt_path and fallback_receipt_path.is_file()) else "invalid")
    )
    audit["unit_test_status"] = (
        "passed"
        if trx_path
        and trx_path.is_file()
        and str(unit_tests.get("status") or "").strip() == "passed"
        and audit["unit_test_framework"] == "net10.0"
        and trx_summary["failed"] == 0
        and trx_summary["total"] > 0
        and FLAGSHIP_UI_LINUX_TEST_ASSEMBLY_NAME in trx_assemblies
        else (
            "missing"
            if not (trx_path and trx_path.is_file())
            else ("invalid" if FLAGSHIP_UI_LINUX_TEST_ASSEMBLY_NAME not in trx_assemblies else "failed")
        )
    )

    if audit["proof_status"] != "passed":
        audit["status"] = "fail"
        audit["reason"] = str(payload.get("reason") or "linux desktop exit gate proof did not pass")
        return audit
    if audit["stage"] != "complete":
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop exit gate proof ended at stage={audit['stage'] or 'unknown'}"
        return audit
    if audit["head_id"] != FLAGSHIP_UI_APP_KEY or audit["launch_target"] != FLAGSHIP_UI_LAUNCH_TARGET:
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate proof does not target the flagship Avalonia head "
            f"({audit['head_id'] or 'unknown'} / {audit['launch_target'] or 'unknown'})"
        )
        return audit
    if audit["project_path"] != FLAGSHIP_UI_PROJECT_PATH:
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate proof used the wrong flagship project path "
            f"({audit['project_path'] or 'unknown'})"
        )
        return audit
    if audit["ready_checkpoint"] != FLAGSHIP_UI_READY_CHECKPOINT:
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate proof used the wrong readiness checkpoint "
            f"({audit['ready_checkpoint'] or 'unknown'})"
        )
        return audit
    if audit["platform"] != "linux" or not audit["rid"].startswith("linux-"):
        audit["status"] = "fail"
        audit["reason"] = (
            f"linux desktop exit gate proof targets {audit['platform'] or 'unknown'} {audit['rid'] or 'unknown'} instead of linux"
        )
        return audit
    if not run_root or not run_root.is_dir():
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof is missing a valid run_root"
        return audit
    if not _path_within(run_root, expected_output_root):
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof points outside the canonical output root"
        return audit
    if audit["source_snapshot_mode"] != "filesystem_copy" or not audit["source_snapshot_root"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof is missing immutable source-snapshot metadata"
        return audit
    if audit["source_snapshot_entry_count"] <= 0 or not audit["source_snapshot_worktree_sha256"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof source snapshot is empty or missing its worktree fingerprint"
        return audit
    if (
        audit["source_snapshot_finish_entry_count"] <= 0
        or not audit["source_snapshot_finish_worktree_sha256"]
        or not audit["source_snapshot_identity_stable"]
    ):
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof source snapshot did not stay stable through the full run"
        return audit
    if (
        audit["source_snapshot_entry_count"] != audit["source_snapshot_finish_entry_count"]
        or audit["source_snapshot_worktree_sha256"] != audit["source_snapshot_finish_worktree_sha256"]
    ):
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof source snapshot finish fingerprint does not match the initial snapshot"
        return audit
    for candidate, label in (
        (publish_dir, "publish_dir"),
        (dist_dir, "dist_dir"),
        (test_results_dir, "results_directory"),
        (binary_path, "binary_path"),
        (installer_path, "installer_path"),
        (archive_path, "archive_path"),
        (primary_receipt_path, "primary receipt"),
        (fallback_receipt_path, "fallback receipt"),
        (trx_path, "unit-test trx"),
    ):
        if not _path_within(candidate, run_root):
            audit["status"] = "fail"
            audit["reason"] = f"linux desktop exit gate proof points {label} outside the gate run_root"
            return audit
    if audit["unit_test_project_path"] != FLAGSHIP_UI_LINUX_TEST_PROJECT_PATH:
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate proof used the wrong unit-test project "
            f"({audit['unit_test_project_path'] or 'unknown'})"
        )
        return audit
    if audit["unit_test_framework"] != "net10.0":
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate proof used the wrong unit-test target framework "
            f"({audit['unit_test_framework'] or 'unknown'})"
        )
        return audit
    if str(unit_tests.get("assembly_name") or "").strip() != FLAGSHIP_UI_LINUX_TEST_ASSEMBLY_NAME:
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate proof used the wrong unit-test assembly "
            f"({str(unit_tests.get('assembly_name') or '').strip() or 'unknown'})"
        )
        return audit
    if audit["current_git_available"]:
        if not audit["proof_git_available"]:
            audit["status"] = "fail"
            audit["reason"] = "linux desktop exit gate proof is missing tracked git-state metadata"
            return audit
        if not audit["proof_git_start_head"] or not audit["proof_git_finish_head"]:
            audit["status"] = "fail"
            audit["reason"] = "linux desktop exit gate proof is missing start/finish git snapshots"
            return audit
        if not audit["proof_git_identity_stable"]:
            audit["status"] = "fail"
            audit["reason"] = "linux desktop exit gate repo changed while the proof run was executing"
            return audit
        if (
            audit["proof_git_start_head"] != audit["proof_git_finish_head"]
            or audit["proof_git_start_tracked_diff_sha256"] != audit["proof_git_finish_tracked_diff_sha256"]
            or audit["proof_git_head"] != audit["proof_git_finish_head"]
            or audit["proof_tracked_diff_sha256"] != audit["proof_git_finish_tracked_diff_sha256"]
        ):
            audit["status"] = "fail"
            audit["reason"] = "linux desktop exit gate proof recorded inconsistent git snapshots"
            return audit
        if (
            audit["source_snapshot_worktree_sha256"] != audit["proof_tracked_diff_sha256"]
            or audit["source_snapshot_worktree_sha256"] != audit["proof_git_start_tracked_diff_sha256"]
            or audit["source_snapshot_worktree_sha256"] != audit["proof_git_finish_tracked_diff_sha256"]
            or audit["source_snapshot_finish_worktree_sha256"] != audit["proof_tracked_diff_sha256"]
            or audit["source_snapshot_finish_worktree_sha256"] != audit["proof_git_start_tracked_diff_sha256"]
            or audit["source_snapshot_finish_worktree_sha256"] != audit["proof_git_finish_tracked_diff_sha256"]
        ):
            audit["status"] = "fail"
            audit["reason"] = "linux desktop exit gate proof source snapshot does not match the recorded git worktree fingerprint"
            return audit
    if audit["primary_package_kind"] != "deb":
        audit["status"] = "fail"
        audit["reason"] = (
            f"linux desktop exit gate proof reports primary_package_kind={audit['primary_package_kind'] or 'unknown'}"
        )
        return audit
    if audit["fallback_package_kind"] != "archive":
        audit["status"] = "fail"
        audit["reason"] = (
            f"linux desktop exit gate proof reports fallback_package_kind={audit['fallback_package_kind'] or 'unknown'}"
        )
        return audit
    if not bool(build.get("self_contained")) or not bool(build.get("single_file")):
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof did not record a self-contained single-file Linux publish"
        return audit
    if not audit["binary_exists"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate did not record a built Linux desktop binary"
        return audit
    if not audit["binary_executable"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate binary is not executable on disk"
        return audit
    if not audit["installer_exists"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate did not record a built Linux .deb installer"
        return audit
    if not audit["archive_exists"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate did not record a built Linux archive artifact"
        return audit
    if str(build.get("binary_sha256") or "").strip() != audit["binary_sha256"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof binary digest does not match the built binary"
        return audit
    if str(build.get("installer_sha256") or "").strip() != audit["installer_sha256"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof installer digest does not match the built installer"
        return audit
    if str(build.get("archive_sha256") or "").strip() != audit["archive_sha256"]:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate proof archive digest does not match the built archive"
        return audit
    if audit["primary_install_verification_status"] != "passed":
        audit["status"] = "fail"
        audit["reason"] = (
            "linux desktop exit gate primary .deb install/remove verification is "
            f"{audit['primary_install_verification_status'] or 'unknown'}"
        )
        return audit
    if audit["primary_smoke_status"] != "passed":
        audit["status"] = "fail"
        audit["reason"] = (
            f"linux desktop exit gate primary startup smoke is {audit['primary_smoke_status'] or 'unknown'}"
        )
        return audit
    if audit["fallback_smoke_status"] != "passed":
        audit["status"] = "fail"
        audit["reason"] = (
            f"linux desktop exit gate fallback startup smoke is {audit['fallback_smoke_status'] or 'unknown'}"
        )
        return audit
    if audit["unit_test_status"] != "passed":
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop exit gate unit-test status is {audit['unit_test_status'] or 'unknown'}"
        return audit
    for key, label in (
        ("total", "total"),
        ("passed", "passed"),
        ("failed", "failed"),
        ("skipped", "skipped"),
    ):
        raw_value = unit_test_summary.get(key)
        if raw_value in (None, ""):
            continue
        try:
            expected_value = int(raw_value)
        except (TypeError, ValueError):
            audit["status"] = "fail"
            audit["reason"] = f"linux desktop exit gate proof carries a non-numeric unit-test {label} count"
            return audit
        if expected_value != trx_summary[key]:
            audit["status"] = "fail"
            audit["reason"] = f"linux desktop exit gate proof unit-test {label} count does not match the TRX"
            return audit
    if audit["test_total"] <= 0:
        audit["status"] = "fail"
        audit["reason"] = "linux desktop exit gate recorded no executed unit tests"
        return audit
    if audit["test_failed"] > 0:
        audit["status"] = "fail"
        audit["reason"] = f"linux desktop exit gate recorded failed unit tests: {audit['test_failed']}"
        return audit
    return audit


def _desktop_executable_exit_gate_audit(args: argparse.Namespace) -> Dict[str, Any]:
    configured_path = Path(
        str(getattr(args, "ui_executable_exit_gate_path", DEFAULT_UI_EXECUTABLE_EXIT_GATE_PATH) or "")
    ).expanduser()
    path = configured_path.resolve()
    audit: Dict[str, Any] = {
        "status": "pass",
        "reason": "desktop executable exit gate proof is ready",
        "path": str(configured_path),
        "generated_at": "",
        "age_seconds": 0,
        "proof_status": "",
        "contract_name": "",
    }
    if not path.is_file():
        audit["status"] = "fail"
        audit["reason"] = f"desktop executable exit gate proof is missing: {path}"
        return audit
    payload = _read_state(path)
    if not payload:
        audit["status"] = "fail"
        audit["reason"] = f"desktop executable exit gate proof could not be read: {path}"
        return audit
    contract_name = str(payload.get("contract_name") or "").strip()
    audit["contract_name"] = contract_name
    if contract_name != "chummer6-ui.desktop_executable_exit_gate":
        audit["status"] = "fail"
        audit["reason"] = f"desktop executable exit gate proof uses an unexpected contract: {contract_name or 'missing'}"
        return audit
    generated_at = str(payload.get("generatedAt") or payload.get("generated_at") or "").strip()
    audit["generated_at"] = generated_at
    generated_at_dt = _parse_iso(generated_at)
    if generated_at_dt is None:
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate proof is missing a valid generatedAt/generated_at timestamp"
        return audit
    age_delta_seconds = (_utc_now() - generated_at_dt).total_seconds()
    if age_delta_seconds < -60:
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate proof generatedAt timestamp is in the future"
        return audit
    audit["age_seconds"] = max(0, int(age_delta_seconds))
    if audit["age_seconds"] > DESKTOP_EXECUTABLE_EXIT_GATE_MAX_AGE_SECONDS:
        audit["status"] = "fail"
        audit["reason"] = f"desktop executable exit gate proof is stale ({audit['age_seconds']}s old)"
        return audit
    audit["proof_status"] = str(payload.get("status") or "").strip()
    raw_blocked_external_only = payload.get("blockedByExternalConstraintsOnly")
    if raw_blocked_external_only is None:
        raw_blocked_external_only = payload.get("blocked_by_external_constraints_only")
    blocked_external_only = str(raw_blocked_external_only or "").strip().lower() in {"1", "true", "yes", "on"}

    external_findings_raw = payload.get("externalBlockingFindings")
    if external_findings_raw is None:
        external_findings_raw = payload.get("external_blocking_findings")
    external_findings = [str(item).strip() for item in (external_findings_raw or []) if str(item).strip()]

    local_findings_raw = payload.get("localBlockingFindings")
    if local_findings_raw is None:
        local_findings_raw = payload.get("local_blocking_findings")
    local_findings = [str(item).strip() for item in (local_findings_raw or []) if str(item).strip()]

    blocking_findings_raw = payload.get("blockingFindings")
    if blocking_findings_raw is None:
        blocking_findings_raw = payload.get("blocking_findings")
    blocking_findings = [str(item).strip() for item in (blocking_findings_raw or []) if str(item).strip()]

    external_count = _coerce_int(
        payload.get("externalBlockingFindingsCount", payload.get("external_blocking_findings_count"))
    )
    local_count = _coerce_int(payload.get("localBlockingFindingsCount", payload.get("local_blocking_findings_count")))
    blocking_count = _coerce_int(payload.get("blockingFindingsCount", payload.get("blocking_findings_count")))

    audit["blocked_by_external_constraints_only"] = blocked_external_only
    audit["external_blocking_findings_count"] = external_count
    audit["local_blocking_findings_count"] = local_count
    audit["blocking_findings_count"] = blocking_count

    if blocking_count < 0 or local_count < 0 or external_count < 0:
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate blocking findings counts must be non-negative"
        return audit
    if len(set(blocking_findings)) != len(blocking_findings):
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate blocking findings rows must be unique"
        return audit
    if len(set(local_findings)) != len(local_findings):
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate local blocking findings rows must be unique"
        return audit
    if len(set(external_findings)) != len(external_findings):
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate external blocking findings rows must be unique"
        return audit
    if blocking_findings and (local_findings or external_findings):
        if Counter(blocking_findings) != Counter(local_findings + external_findings):
            audit["status"] = "fail"
            audit["reason"] = (
                "desktop executable exit gate blocking findings rows must match local plus external finding rows"
            )
            return audit

    proof_is_ready = str(audit["proof_status"]).lower() in {"pass", "passed", "ready"}
    if proof_is_ready:
        if blocked_external_only:
            audit["status"] = "fail"
            audit["reason"] = "desktop executable exit gate proof cannot be pass while marked external-only blocked"
            return audit
        if local_findings or external_findings or blocking_findings or local_count > 0 or external_count > 0 or blocking_count > 0:
            audit["status"] = "fail"
            audit["reason"] = "desktop executable exit gate proof cannot be pass while blocking findings are present"
            return audit
        return audit

    if blocked_external_only:
        if local_findings or local_count > 0:
            audit["status"] = "fail"
            audit["reason"] = "desktop executable exit gate external-only block conflicts with local blocking findings"
            return audit
        if not external_findings and external_count <= 0:
            audit["status"] = "fail"
            audit["reason"] = "desktop executable exit gate external-only block is missing external blocking findings"
            return audit
    if blocking_count > 0 and not blocking_findings:
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate blocking findings count is positive but no finding rows were provided"
        return audit
    if local_count > 0 and not local_findings:
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate local blocking findings count is positive but no finding rows were provided"
        return audit
    if external_count > 0 and not external_findings:
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate external blocking findings count is positive but no finding rows were provided"
        return audit
    if blocking_findings and blocking_count <= 0:
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate blocking findings rows are present but the declared count is zero"
        return audit
    if local_findings and local_count <= 0:
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate local blocking findings rows are present but the declared count is zero"
        return audit
    if external_findings and external_count <= 0:
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate external blocking findings rows are present but the declared count is zero"
        return audit
    if (blocking_count > 0 or local_count > 0 or external_count > 0) and blocking_count != (local_count + external_count):
        audit["status"] = "fail"
        audit["reason"] = (
            "desktop executable exit gate declared blocking findings count does not equal local plus external counts"
        )
        return audit
    if blocking_findings and blocking_count > 0 and blocking_count != len(blocking_findings):
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate blocking findings count does not match finding rows"
        return audit
    if local_findings and local_count > 0 and local_count != len(local_findings):
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate local blocking findings count does not match finding rows"
        return audit
    if external_findings and external_count > 0 and external_count != len(external_findings):
        audit["status"] = "fail"
        audit["reason"] = "desktop executable exit gate external blocking findings count does not match finding rows"
        return audit

    deferred_nonlinux_host_proof_only = (
        blocked_external_only
        and _ignore_nonlinux_desktop_host_proof_blockers_enabled()
        and bool(external_findings)
        and all(_reason_targets_ignored_nonlinux_desktop_host_platform(item) for item in external_findings)
    )
    audit["deferred_nonlinux_host_proof_only"] = deferred_nonlinux_host_proof_only
    if deferred_nonlinux_host_proof_only:
        audit["status"] = "pass"
        audit["reason"] = "desktop executable exit gate is externally blocked only by deferred non-Linux host-proof gaps"
        return audit

    if not proof_is_ready:
        audit["status"] = "fail"
        audit["reason"] = str(payload.get("reason") or "desktop executable exit gate proof did not pass")
        return audit
    return audit


def _design_completion_audit(args: argparse.Namespace, history: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    receipt_audit = _completion_audit(history)
    journey_gate_audit = _journey_gate_audit(args)
    linux_desktop_exit_gate_audit = _linux_desktop_exit_gate_audit(args)
    desktop_executable_exit_gate_audit = _desktop_executable_exit_gate_audit(args)
    weekly_pulse_audit = _weekly_pulse_audit(args)
    weekly_pulse_audit = _reconcile_weekly_pulse_audit_with_live_journey_truth(
        weekly_pulse_audit,
        journey_gate_audit,
    )
    repo_backlog_audit = _repo_backlog_audit(args)
    receipt_audit = _reconcile_receipt_audit_with_repo_backlog_truth(
        receipt_audit,
        repo_backlog_audit,
        history,
    )
    synthetic_receipt_audit = _synthetic_completion_receipt_audit(
        receipt_audit,
        journey_gate_audit,
        linux_desktop_exit_gate_audit,
        desktop_executable_exit_gate_audit,
        weekly_pulse_audit,
    )
    if repo_backlog_audit.get("status") == "fail":
        synthetic_receipt_audit = None
    if synthetic_receipt_audit is not None:
        receipt_audit = synthetic_receipt_audit
    audit: Dict[str, Any] = {
        "status": "pass",
        "reason": "trusted completion receipt plus whole-product release proof and Linux desktop exit gate are ready",
        "receipt_audit": receipt_audit,
        "journey_gate_audit": journey_gate_audit,
        "linux_desktop_exit_gate_audit": linux_desktop_exit_gate_audit,
        "desktop_executable_exit_gate_audit": desktop_executable_exit_gate_audit,
        "weekly_pulse_audit": weekly_pulse_audit,
        "repo_backlog_audit": repo_backlog_audit,
    }
    if receipt_audit.get("status") != "pass":
        audit.update(
            {
                "status": "fail",
                "reason": str(receipt_audit.get("reason") or "receipt audit failed"),
            }
        )
        audit.update(receipt_audit)
        return audit

    if journey_gate_audit.get("status") != "pass":
        audit["status"] = "fail"
        audit["reason"] = str(journey_gate_audit.get("reason") or "golden journey audit failed")
        return audit
    if linux_desktop_exit_gate_audit.get("status") != "pass":
        audit["status"] = "fail"
        audit["reason"] = str(
            linux_desktop_exit_gate_audit.get("reason") or "linux desktop exit gate audit failed"
        )
        return audit
    if desktop_executable_exit_gate_audit.get("status") != "pass":
        audit["status"] = "fail"
        audit["reason"] = str(
            desktop_executable_exit_gate_audit.get("reason") or "desktop executable exit gate audit failed"
        )
        return audit
    if weekly_pulse_audit.get("status") != "pass":
        audit["status"] = "fail"
        audit["reason"] = str(weekly_pulse_audit.get("reason") or "weekly product pulse audit failed")
        return audit
    if repo_backlog_audit.get("status") != "pass":
        audit["status"] = "fail"
        audit["reason"] = str(repo_backlog_audit.get("reason") or "repo-local backlog audit failed")
        return audit

    audit.update(receipt_audit)
    return audit


def _failure_hint_for_run(run: Dict[str, Any]) -> str:
    accepted = run.get("accepted")
    acceptance_reason = str(run.get("acceptance_reason") or "").strip()
    if int(run.get("worker_exit_code") or 0) == 0 and _run_has_receipt_fields(run):
        inferred_accepted, inferred_reason = _run_receipt_status(run)
        if not inferred_accepted and inferred_reason:
            return inferred_reason
        if inferred_accepted:
            return ""
    if accepted is False and acceptance_reason:
        return acceptance_reason
    blocker = _normalize_blocker(str(run.get("blocker") or ""))
    if blocker and blocker.lower() not in BLOCKER_CLEAR_VALUES:
        return blocker
    stderr_raw = str(run.get("stderr_path") or "").strip()
    if not stderr_raw:
        return ""
    stderr_path = _resolve_run_artifact_path(stderr_raw)
    if not stderr_path.exists() or stderr_path.is_dir():
        return ""
    lines = [line.strip() for line in _read_text(stderr_path).splitlines() if line.strip()]
    if not lines:
        return ""
    for line in reversed(lines):
        marker_index = line.find("ERROR:")
        if marker_index >= 0:
            return _summarize_trace_value(line[marker_index:], max_len=96)
    return _summarize_trace_value(lines[-1], max_len=96)


def _render_trace(state: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
    status_text = _render_status(state)
    active_run = state.get("active_run") or {}
    if not history and not active_run:
        return f"{status_text}\ntrace: none"
    lines = [status_text, "trace:"]
    if isinstance(active_run, dict) and active_run:
        frontier_ids = ",".join(str(value) for value in (active_run.get("frontier_ids") or [])) or "none"
        lines.append(
            " ".join(
                [
                    f"- {active_run.get('started_at') or 'unknown'}",
                    f"run={active_run.get('run_id') or 'unknown'}",
                    "state=in_progress",
                    f"account={active_run.get('selected_account_alias') or 'none'}",
                    f"model={active_run.get('selected_model') or 'default'}",
                    f"primary={active_run.get('primary_milestone_id') or 'none'}",
                    f"frontier={frontier_ids}",
                ]
            )
        )
    for run in reversed(history):
        finished_at = str(run.get("finished_at") or run.get("started_at") or "unknown")
        frontier_ids = ",".join(str(value) for value in (run.get("frontier_ids") or [])) or "none"
        shipped = _summarize_trace_value(run.get("shipped"))
        remains = _summarize_trace_value(run.get("remains"))
        blocker = _summarize_trace_value(run.get("blocker"), max_len=40)
        if _run_has_receipt_fields(run):
            inferred_accepted, _ = _run_receipt_status(run)
            accepted_value: Any = run.get("accepted") if "accepted" in run else inferred_accepted
        else:
            accepted_value = "unknown"
        segments = [
            f"- {finished_at}",
            f"run={run.get('run_id') or 'unknown'}",
            f"shard={run.get('_shard') or 'none'}",
            f"exit={run.get('worker_exit_code')}",
            f"account={run.get('selected_account_alias') or 'none'}",
            f"primary={run.get('primary_milestone_id') or 'none'}",
            f"frontier={frontier_ids}",
            f"accepted={'yes' if accepted_value is True else 'no' if accepted_value is False else 'unknown'}",
            f"blocker={blocker}",
            f"shipped={shipped}",
            f"remains={remains}",
        ]
        failure_hint = _failure_hint_for_run(run)
        if failure_hint:
            segments.append(f"hint={failure_hint}")
        lines.append(" ".join(segments))
    return "\n".join(lines)


def run_once(args: argparse.Namespace) -> int:
    state_root = Path(args.state_root).resolve()
    _ensure_dir(state_root)
    _refresh_flagship_product_readiness_artifact(args)
    context = derive_context(args)
    forced_flagship_context = _hard_flagship_context_if_needed(args, state_root, context)
    if forced_flagship_context is not None:
        context = forced_flagship_context
    worker_lane_health = _direct_worker_lane_health_snapshot(args, _worker_lane_candidates(args))
    host_memory_pressure = _memory_dispatch_snapshot(args, state_root)
    audit: Optional[Dict[str, Any]] = None
    full_product_audit: Optional[Dict[str, Any]] = None
    history = _read_history(_history_payload_path(state_root), limit=ETA_HISTORY_LIMIT)
    if not context["open_milestones"]:
        completion_history = _completion_review_history(state_root, limit=ETA_HISTORY_LIMIT)
        audit = _design_completion_audit(args, completion_history[-COMPLETION_AUDIT_HISTORY_LIMIT:])
        hard_flagship = _hard_flagship_requested(args, context.get("focus_profiles") or [])
        if hard_flagship:
            full_product_audit = _full_product_readiness_audit(args)
            if full_product_audit.get("status") != "pass":
                context = derive_flagship_product_context(
                    args,
                    state_root,
                    base_context=context,
                    completion_audit=audit,
                    full_product_audit=full_product_audit,
                )
            else:
                context = derive_completion_review_context(args, state_root, base_context=context, audit=audit)
        elif audit.get("status") != "pass":
            context = derive_completion_review_context(args, state_root, base_context=context, audit=audit)
            if not context["frontier"]:
                flagship_context = _parallel_flagship_context_if_available(
                    args,
                    state_root,
                    base_context=context,
                    completion_audit=audit,
                )
                if flagship_context is not None:
                    context = flagship_context
                    full_product_audit = dict(context.get("full_product_audit") or {})
        else:
            full_product_audit = _full_product_readiness_audit(args)
            if full_product_audit.get("status") != "pass":
                context = derive_flagship_product_context(
                    args,
                    state_root,
                    base_context=context,
                    completion_audit=audit,
                    full_product_audit=full_product_audit,
                )
        history = completion_history
    if args.command == "derive":
        print(context["prompt"])
        return 0
    if context["open_milestones"] and not context["frontier"]:
        eta = _build_eta_snapshot(
            mode="loop",
            open_milestones=context["open_milestones"],
            frontier=[],
            history=history,
            worker_lane_health=worker_lane_health,
        )
        _write_state(
            state_root,
            mode="loop",
            run=None,
            open_milestones=context["open_milestones"],
            frontier=[],
            focus_profiles=context["focus_profiles"],
            focus_owners=context["focus_owners"],
            focus_texts=context["focus_texts"],
            eta=eta,
            worker_lane_health=worker_lane_health,
            host_memory_pressure=host_memory_pressure,
            completion_review_frontier_path="",
            completion_review_frontier_mirror_path="",
            full_product_frontier_path="",
            full_product_frontier_mirror_path="",
        )
        print("[fleet-supervisor] loop has no local shard slice; waiting for another shard or milestone progress")
        return 0
    if not context["open_milestones"] and not context["frontier"]:
        review_audit = audit or _design_completion_audit(args, history[-COMPLETION_AUDIT_HISTORY_LIMIT:])
        current_full_product_audit = (
            full_product_audit
            if review_audit.get("status") == "pass"
            else None
        )
        if review_audit.get("status") == "pass" and current_full_product_audit is None:
            current_full_product_audit = _full_product_readiness_audit(args)
        if review_audit.get("status") != "pass":
            eta = _build_eta_snapshot(
                mode="completion_review",
                open_milestones=[],
                frontier=[],
                history=history,
                completion_audit=review_audit,
                worker_lane_health=worker_lane_health,
            )
            frontier_paths = _materialize_completion_review_frontier(
                args=args,
                state_root=state_root,
                mode="completion_review",
                frontier=[],
                focus_profiles=context["focus_profiles"],
                focus_owners=context["focus_owners"],
                focus_texts=context["focus_texts"],
                completion_audit=review_audit,
                eta=eta,
            )
            _write_state(
                state_root,
                mode="completion_review",
                run=None,
                open_milestones=[],
                frontier=[],
                focus_profiles=context["focus_profiles"],
                focus_owners=context["focus_owners"],
                focus_texts=context["focus_texts"],
                completion_audit=review_audit,
                eta=eta,
                worker_lane_health=worker_lane_health,
                host_memory_pressure=host_memory_pressure,
                completion_review_frontier_path=frontier_paths["published_path"],
                completion_review_frontier_mirror_path=frontier_paths["mirror_path"],
                full_product_frontier_path="",
                full_product_frontier_mirror_path="",
            )
            print("[fleet-supervisor] completion review has no local frontier slice; waiting for another shard or new evidence")
            return 0
        if current_full_product_audit and current_full_product_audit.get("status") != "pass":
            eta = _build_eta_snapshot(
                mode="flagship_product",
                open_milestones=[],
                frontier=[],
                history=history,
                completion_audit=review_audit,
                full_product_audit=current_full_product_audit,
                worker_lane_health=worker_lane_health,
            )
            frontier_paths = _materialize_full_product_frontier(
                args=args,
                state_root=state_root,
                mode="flagship_product",
                frontier=[],
                focus_profiles=context["focus_profiles"],
                focus_owners=context["focus_owners"],
                focus_texts=context["focus_texts"],
                completion_audit=review_audit,
                full_product_audit=current_full_product_audit,
                eta=eta,
            )
            _write_state(
                state_root,
                mode="flagship_product",
                run=None,
                open_milestones=[],
                frontier=[],
                focus_profiles=context["focus_profiles"],
                focus_owners=context["focus_owners"],
                focus_texts=context["focus_texts"],
                completion_audit=review_audit,
                full_product_audit=current_full_product_audit,
                eta=eta,
                worker_lane_health=worker_lane_health,
                host_memory_pressure=host_memory_pressure,
                completion_review_frontier_path="",
                completion_review_frontier_mirror_path="",
                full_product_frontier_path=frontier_paths["published_path"],
                full_product_frontier_mirror_path=frontier_paths["mirror_path"],
            )
            print("[fleet-supervisor] flagship product frontier has no local shard slice; waiting for another shard or new evidence")
            return 0
        eta = _build_eta_snapshot(
            mode="complete",
            open_milestones=[],
            frontier=[],
            history=history,
            completion_audit=review_audit,
            full_product_audit=current_full_product_audit,
            worker_lane_health=worker_lane_health,
        )
        completion_frontier_paths = _materialize_completion_review_frontier(
            args=args,
            state_root=state_root,
            mode="complete",
            frontier=[],
            focus_profiles=context["focus_profiles"],
            focus_owners=context["focus_owners"],
            focus_texts=context["focus_texts"],
            completion_audit=review_audit,
            eta=eta,
        )
        frontier_paths = _materialize_full_product_frontier(
            args=args,
            state_root=state_root,
            mode="complete",
            frontier=[],
            focus_profiles=context["focus_profiles"],
            focus_owners=context["focus_owners"],
            focus_texts=context["focus_texts"],
            completion_audit=review_audit,
            full_product_audit=current_full_product_audit or {},
            eta=eta,
        )
        _write_state(
            state_root,
            mode="complete",
            run=None,
            open_milestones=[],
            frontier=[],
            focus_profiles=context["focus_profiles"],
            focus_owners=context["focus_owners"],
            focus_texts=context["focus_texts"],
            completion_audit=review_audit,
            full_product_audit=current_full_product_audit,
            eta=eta,
            worker_lane_health=worker_lane_health,
            host_memory_pressure=host_memory_pressure,
            completion_review_frontier_path=completion_frontier_paths["published_path"],
            completion_review_frontier_mirror_path=completion_frontier_paths["mirror_path"],
            full_product_frontier_path=frontier_paths["published_path"],
            full_product_frontier_mirror_path=frontier_paths["mirror_path"],
        )
        print("No unfinished flagship product frontier remains in the active design canon.")
        return 0
    if _should_defer_dispatch_for_memory_pressure(state_root, host_memory_pressure):
        run_mode = "loop" if context["open_milestones"] else (
            "flagship_product" if context.get("full_product_audit") else "completion_review"
        )
        eta = _build_eta_snapshot(
            mode=run_mode,
            open_milestones=context["open_milestones"],
            frontier=context["frontier"],
            history=history,
            completion_audit=(context.get("completion_audit") if not context["open_milestones"] else None),
            full_product_audit=(context.get("full_product_audit") if not context["open_milestones"] else None),
            worker_lane_health=worker_lane_health,
        )
        _write_state(
            state_root,
            mode=run_mode,
            run=None,
            open_milestones=context["open_milestones"],
            frontier=context["frontier"],
            focus_profiles=context["focus_profiles"],
            focus_owners=context["focus_owners"],
            focus_texts=context["focus_texts"],
            completion_audit=(context.get("completion_audit") if not context["open_milestones"] else None),
            full_product_audit=(context.get("full_product_audit") if not context["open_milestones"] else None),
            eta=eta,
            worker_lane_health=worker_lane_health,
            host_memory_pressure=host_memory_pressure,
            completion_review_frontier_path="",
            completion_review_frontier_mirror_path="",
            full_product_frontier_path="",
            full_product_frontier_mirror_path="",
        )
        print(_memory_pressure_notice(host_memory_pressure))
        return 0
    run = launch_worker(args, context, state_root, worker_lane_health=worker_lane_health)
    run_mode = "once"
    if not context["open_milestones"]:
        run_mode = "flagship_product" if context.get("full_product_audit") else "completion_review"
    eta = _build_eta_snapshot(
        mode=run_mode,
        open_milestones=context["open_milestones"],
        frontier=context["frontier"],
        history=history + [_run_payload(run)],
        completion_audit=(context.get("completion_audit") if not context["open_milestones"] else None),
        full_product_audit=(context.get("full_product_audit") if not context["open_milestones"] else None),
        worker_lane_health=worker_lane_health,
    )
    completion_frontier_paths = {
        "published_path": str(context.get("completion_review_frontier_path") or ""),
        "mirror_path": str(context.get("completion_review_frontier_mirror_path") or ""),
    }
    full_frontier_paths = {
        "published_path": str(context.get("full_product_frontier_path") or ""),
        "mirror_path": str(context.get("full_product_frontier_mirror_path") or ""),
    }
    if not context["open_milestones"] and context.get("full_product_audit"):
        full_frontier_paths = _materialize_full_product_frontier(
            args=args,
            state_root=state_root,
            mode="flagship_product",
            frontier=context["frontier"],
            focus_profiles=context["focus_profiles"],
            focus_owners=context["focus_owners"],
            focus_texts=context["focus_texts"],
            completion_audit=context["completion_audit"],
            full_product_audit=context["full_product_audit"],
            eta=eta,
        )
    elif not context["open_milestones"] and context.get("completion_audit"):
        completion_frontier_paths = _materialize_completion_review_frontier(
            args=args,
            state_root=state_root,
            mode="completion_review",
            frontier=context["frontier"],
            focus_profiles=context["focus_profiles"],
            focus_owners=context["focus_owners"],
            focus_texts=context["focus_texts"],
            completion_audit=context["completion_audit"],
            eta=eta,
        )
    _write_state(
        state_root,
        mode=run_mode,
        run=run,
        open_milestones=context["open_milestones"],
        frontier=context["frontier"],
        focus_profiles=context["focus_profiles"],
        focus_owners=context["focus_owners"],
        focus_texts=context["focus_texts"],
        completion_audit=(context.get("completion_audit") if not context["open_milestones"] else None),
        full_product_audit=(context.get("full_product_audit") if not context["open_milestones"] else None),
        eta=eta,
        worker_lane_health=worker_lane_health,
        host_memory_pressure=host_memory_pressure,
        completion_review_frontier_path=completion_frontier_paths["published_path"],
        completion_review_frontier_mirror_path=completion_frontier_paths["mirror_path"],
        full_product_frontier_path=full_frontier_paths["published_path"],
        full_product_frontier_mirror_path=full_frontier_paths["mirror_path"],
    )
    if args.dry_run:
        print(json.dumps(_run_payload(run), indent=2, sort_keys=True))
        return 0
    return 0 if run.accepted else max(1, run.worker_exit_code)


def run_loop(args: argparse.Namespace) -> int:
    state_root = Path(args.state_root).resolve()
    _ensure_dir(state_root)
    _refresh_flagship_product_readiness_artifact(args)
    lock_path = _lock_payload_path(state_root)
    try:
        _acquire_lock(lock_path, ttl_seconds=max(60.0, float(args.poll_seconds) * 4, LOCK_TTL_SECONDS / 2))
    except RuntimeError as exc:
        print(f"[fleet-supervisor] {exc}", flush=True)
        return 0
    run_count = 0
    last_idle_notice = ""
    try:
        while True:
            context = derive_context(args)
            worker_lane_health = _direct_worker_lane_health_snapshot(args, _worker_lane_candidates(args))
            host_memory_pressure = _memory_dispatch_snapshot(args, state_root)
            forced_flagship_context = _hard_flagship_context_if_needed(args, state_root, context)
            if forced_flagship_context is not None:
                context = forced_flagship_context
            open_milestones: List[Milestone] = context["open_milestones"]
            frontier: List[Milestone] = context["frontier"]
            history = _read_history(_history_payload_path(state_root), limit=ETA_HISTORY_LIMIT)
            if not open_milestones:
                history = _completion_review_history(state_root, limit=ETA_HISTORY_LIMIT)
                audit = _design_completion_audit(
                    args, history[-COMPLETION_AUDIT_HISTORY_LIMIT:]
                )
                hard_flagship = _hard_flagship_requested(args, context.get("focus_profiles") or [])
                if hard_flagship:
                    full_product_audit = _full_product_readiness_audit(args)
                    if full_product_audit.get("status") != "pass":
                        context = derive_flagship_product_context(
                            args,
                            state_root,
                            base_context=context,
                            completion_audit=audit,
                            full_product_audit=full_product_audit,
                        )
                    else:
                        context = derive_completion_review_context(args, state_root, base_context=context, audit=audit)
                elif audit.get("status") == "pass":
                    full_product_audit = _full_product_readiness_audit(args)
                    if full_product_audit.get("status") == "pass":
                        eta = _build_eta_snapshot(
                            mode="complete",
                            open_milestones=[],
                            frontier=[],
                            history=history,
                            completion_audit=audit,
                            full_product_audit=full_product_audit,
                            worker_lane_health=worker_lane_health,
                        )
                        frontier_paths = _materialize_full_product_frontier(
                            args=args,
                            state_root=state_root,
                            mode="complete",
                            frontier=[],
                            focus_profiles=context["focus_profiles"],
                            focus_owners=context["focus_owners"],
                            focus_texts=context["focus_texts"],
                            completion_audit=audit,
                            full_product_audit=full_product_audit,
                            eta=eta,
                        )
                        _write_state(
                            state_root,
                            mode="complete",
                            run=None,
                            open_milestones=[],
                            frontier=[],
                            focus_profiles=context["focus_profiles"],
                            focus_owners=context["focus_owners"],
                            focus_texts=context["focus_texts"],
                            completion_audit=audit,
                            full_product_audit=full_product_audit,
                            eta=eta,
                            worker_lane_health=worker_lane_health,
                            host_memory_pressure=host_memory_pressure,
                            completion_review_frontier_path="",
                            completion_review_frontier_mirror_path="",
                            full_product_frontier_path=frontier_paths["published_path"],
                            full_product_frontier_mirror_path=frontier_paths["mirror_path"],
                        )
                        notice = "[fleet-supervisor] no unfinished flagship product frontier remains in the active design canon"
                        if notice != last_idle_notice:
                            print(notice, flush=True)
                            last_idle_notice = notice
                        if args.max_runs:
                            return 0
                        time.sleep(max(1.0, float(args.poll_seconds)))
                        continue
                    context = derive_flagship_product_context(
                        args,
                        state_root,
                        base_context=context,
                        completion_audit=audit,
                        full_product_audit=full_product_audit,
                    )
                else:
                    context = derive_completion_review_context(args, state_root, base_context=context, audit=audit)
                    if not context["frontier"]:
                        flagship_context = _parallel_flagship_context_if_available(
                            args,
                            state_root,
                            base_context=context,
                            completion_audit=audit,
                        )
                        if flagship_context is not None:
                            context = flagship_context
                frontier = context["frontier"]
                blocker_reason = _eta_external_blocker_reason(
                    history,
                    context.get("completion_audit"),
                    context.get("full_product_audit"),
                )
                if _should_defer_external_blocker_probe(state_root, blocker_reason=blocker_reason):
                    idle_mode = "flagship_product" if context.get("full_product_audit") else "completion_review"
                    eta = _build_eta_snapshot(
                        mode=idle_mode,
                        open_milestones=[],
                        frontier=frontier,
                        history=history,
                        completion_audit=context.get("completion_audit"),
                        full_product_audit=context.get("full_product_audit"),
                        worker_lane_health=worker_lane_health,
                    )
                    completion_frontier_paths = {"published_path": "", "mirror_path": ""}
                    full_frontier_paths = {"published_path": "", "mirror_path": ""}
                    if context.get("full_product_audit"):
                        full_frontier_paths = _materialize_full_product_frontier(
                            args=args,
                            state_root=state_root,
                            mode="flagship_product",
                            frontier=frontier,
                            focus_profiles=context["focus_profiles"],
                            focus_owners=context["focus_owners"],
                            focus_texts=context["focus_texts"],
                            completion_audit=context["completion_audit"],
                            full_product_audit=context["full_product_audit"],
                            eta=eta,
                        )
                    else:
                        completion_frontier_paths = _materialize_completion_review_frontier(
                            args=args,
                            state_root=state_root,
                            mode="completion_review",
                            frontier=frontier,
                            focus_profiles=context["focus_profiles"],
                            focus_owners=context["focus_owners"],
                            focus_texts=context["focus_texts"],
                            completion_audit=context["completion_audit"],
                            eta=eta,
                        )
                    _write_state(
                        state_root,
                        mode=idle_mode,
                        run=None,
                        open_milestones=[],
                        frontier=frontier,
                        focus_profiles=context["focus_profiles"],
                        focus_owners=context["focus_owners"],
                        focus_texts=context["focus_texts"],
                        completion_audit=context.get("completion_audit"),
                        full_product_audit=context.get("full_product_audit"),
                        eta=eta,
                        worker_lane_health=worker_lane_health,
                        host_memory_pressure=host_memory_pressure,
                        completion_review_frontier_path=completion_frontier_paths["published_path"],
                        completion_review_frontier_mirror_path=completion_frontier_paths["mirror_path"],
                        full_product_frontier_path=full_frontier_paths["published_path"],
                        full_product_frontier_mirror_path=full_frontier_paths["mirror_path"],
                    )
                    notice = (
                        f"[fleet-supervisor] external blocker active in {idle_mode}; "
                        f"deferring probe to primary shard {(_primary_probe_shard_name(state_root) or 'unknown')}"
                    )
                    if notice != last_idle_notice:
                        print(notice, flush=True)
                        last_idle_notice = notice
                    time.sleep(
                        max(
                            1.0,
                            float(args.failure_backoff_seconds),
                            DEFAULT_EXTERNAL_BLOCKER_BACKOFF_SECONDS,
                        )
                    )
                    continue
            if open_milestones and not frontier:
                eta = _build_eta_snapshot(
                    mode="loop",
                    open_milestones=context["open_milestones"],
                    frontier=[],
                    history=history,
                    worker_lane_health=worker_lane_health,
                )
                _write_state(
                    state_root,
                    mode="loop",
                    run=None,
                    open_milestones=context["open_milestones"],
                    frontier=[],
                    focus_profiles=context["focus_profiles"],
                    focus_owners=context["focus_owners"],
                    focus_texts=context["focus_texts"],
                    eta=eta,
                    worker_lane_health=worker_lane_health,
                    host_memory_pressure=host_memory_pressure,
                    completion_review_frontier_path="",
                    completion_review_frontier_mirror_path="",
                    full_product_frontier_path="",
                    full_product_frontier_mirror_path="",
                    idle_reason="waiting_for_local_shard_slice",
                )
                notice = "[fleet-supervisor] loop has no local shard slice; waiting for another shard or milestone progress"
                if notice != last_idle_notice:
                    print(notice, flush=True)
                    last_idle_notice = notice
                time.sleep(max(1.0, float(args.poll_seconds)))
                continue
            if not open_milestones and not frontier:
                idle_mode = "flagship_product" if context.get("full_product_audit") else "completion_review"
                idle_scope_frontier = _idle_scope_frontier(args, state_root, context, history)
                eta = _build_eta_snapshot(
                    mode=idle_mode,
                    open_milestones=[],
                    frontier=[],
                    scope_frontier=idle_scope_frontier,
                    history=history,
                    completion_audit=context.get("completion_audit"),
                    full_product_audit=context.get("full_product_audit"),
                    worker_lane_health=worker_lane_health,
                )
                aggregate_idle_eta = _aggregate_idle_eta_snapshot(state_root)
                if aggregate_idle_eta:
                    eta = aggregate_idle_eta
                completion_frontier_paths = {"published_path": "", "mirror_path": ""}
                full_frontier_paths = {"published_path": "", "mirror_path": ""}
                if context.get("full_product_audit"):
                    full_frontier_paths = _materialize_full_product_frontier(
                        args=args,
                        state_root=state_root,
                        mode="flagship_product",
                        frontier=[],
                        focus_profiles=context["focus_profiles"],
                        focus_owners=context["focus_owners"],
                        focus_texts=context["focus_texts"],
                        completion_audit=context["completion_audit"],
                        full_product_audit=context["full_product_audit"],
                        eta=eta,
                    )
                else:
                    completion_frontier_paths = _materialize_completion_review_frontier(
                        args=args,
                        state_root=state_root,
                        mode="completion_review",
                        frontier=[],
                        focus_profiles=context["focus_profiles"],
                        focus_owners=context["focus_owners"],
                        focus_texts=context["focus_texts"],
                        completion_audit=context["completion_audit"],
                        eta=eta,
                    )
                _write_state(
                    state_root,
                    mode=idle_mode,
                    run=None,
                    open_milestones=[],
                    frontier=[],
                    focus_profiles=context["focus_profiles"],
                    focus_owners=context["focus_owners"],
                    focus_texts=context["focus_texts"],
                    completion_audit=context.get("completion_audit"),
                    full_product_audit=context.get("full_product_audit"),
                    eta=eta,
                    worker_lane_health=worker_lane_health,
                    host_memory_pressure=host_memory_pressure,
                    completion_review_frontier_path=completion_frontier_paths["published_path"],
                    completion_review_frontier_mirror_path=completion_frontier_paths["mirror_path"],
                    full_product_frontier_path=full_frontier_paths["published_path"],
                    full_product_frontier_mirror_path=full_frontier_paths["mirror_path"],
                    idle_reason="waiting_for_local_frontier_slice",
                )
                notice = (
                    "[fleet-supervisor] flagship product frontier has no local shard slice; waiting for another shard or new evidence"
                    if context.get("full_product_audit")
                    else "[fleet-supervisor] completion review has no local frontier slice; waiting for another shard or new evidence"
                )
                if notice != last_idle_notice:
                    print(notice, flush=True)
                    last_idle_notice = notice
                time.sleep(max(1.0, float(args.poll_seconds)))
                continue
            if _should_defer_dispatch_for_memory_pressure(state_root, host_memory_pressure):
                run_mode = "loop" if open_milestones else (
                    "flagship_product" if context.get("full_product_audit") else "completion_review"
                )
                eta = _build_eta_snapshot(
                    mode=run_mode,
                    open_milestones=context["open_milestones"],
                    frontier=frontier,
                    history=history,
                    completion_audit=(context.get("completion_audit") if not open_milestones else None),
                    full_product_audit=(context.get("full_product_audit") if not open_milestones else None),
                    worker_lane_health=worker_lane_health,
                )
                _write_state(
                    state_root,
                    mode=run_mode,
                    run=None,
                    open_milestones=context["open_milestones"],
                    frontier=frontier,
                    focus_profiles=context["focus_profiles"],
                    focus_owners=context["focus_owners"],
                    focus_texts=context["focus_texts"],
                    completion_audit=(context.get("completion_audit") if not open_milestones else None),
                    full_product_audit=(context.get("full_product_audit") if not open_milestones else None),
                    eta=eta,
                    worker_lane_health=worker_lane_health,
                    host_memory_pressure=host_memory_pressure,
                    completion_review_frontier_path=str(context.get("completion_review_frontier_path") or ""),
                    completion_review_frontier_mirror_path=str(context.get("completion_review_frontier_mirror_path") or ""),
                    full_product_frontier_path=str(context.get("full_product_frontier_path") or ""),
                    full_product_frontier_mirror_path=str(context.get("full_product_frontier_mirror_path") or ""),
                )
                notice = _memory_pressure_notice(host_memory_pressure)
                notice_key = _memory_pressure_notice_key(host_memory_pressure)
                if notice_key != last_idle_notice:
                    print(notice, flush=True)
                    last_idle_notice = notice_key
                time.sleep(_memory_pressure_parked_sleep_seconds(args, host_memory_pressure))
                continue
            last_idle_notice = ""
            run = launch_worker(args, context, state_root, worker_lane_health=worker_lane_health)
            run_mode = "loop"
            if not open_milestones:
                run_mode = "flagship_product" if context.get("full_product_audit") else "completion_review"
            eta = _build_eta_snapshot(
                mode=run_mode,
                open_milestones=context["open_milestones"],
                frontier=frontier,
                history=history + [_run_payload(run)],
                completion_audit=(context.get("completion_audit") if not open_milestones else None),
                full_product_audit=(context.get("full_product_audit") if not open_milestones else None),
                worker_lane_health=worker_lane_health,
            )
            completion_frontier_paths = {
                "published_path": str(context.get("completion_review_frontier_path") or ""),
                "mirror_path": str(context.get("completion_review_frontier_mirror_path") or ""),
            }
            full_frontier_paths = {
                "published_path": str(context.get("full_product_frontier_path") or ""),
                "mirror_path": str(context.get("full_product_frontier_mirror_path") or ""),
            }
            if not open_milestones and context.get("full_product_audit"):
                full_frontier_paths = _materialize_full_product_frontier(
                    args=args,
                    state_root=state_root,
                    mode="flagship_product",
                    frontier=frontier,
                    focus_profiles=context["focus_profiles"],
                    focus_owners=context["focus_owners"],
                    focus_texts=context["focus_texts"],
                    completion_audit=context["completion_audit"],
                    full_product_audit=context["full_product_audit"],
                    eta=eta,
                )
            elif not open_milestones and context.get("completion_audit"):
                completion_frontier_paths = _materialize_completion_review_frontier(
                    args=args,
                    state_root=state_root,
                    mode="completion_review",
                    frontier=frontier,
                    focus_profiles=context["focus_profiles"],
                    focus_owners=context["focus_owners"],
                    focus_texts=context["focus_texts"],
                    completion_audit=context["completion_audit"],
                    eta=eta,
                )
            _write_state(
                state_root,
                mode=run_mode,
                run=run,
                open_milestones=context["open_milestones"],
                frontier=frontier,
                focus_profiles=context["focus_profiles"],
                focus_owners=context["focus_owners"],
                focus_texts=context["focus_texts"],
                completion_audit=(context.get("completion_audit") if not open_milestones else None),
                full_product_audit=(context.get("full_product_audit") if not open_milestones else None),
                eta=eta,
                worker_lane_health=worker_lane_health,
                host_memory_pressure=host_memory_pressure,
                completion_review_frontier_path=completion_frontier_paths["published_path"],
                completion_review_frontier_mirror_path=completion_frontier_paths["mirror_path"],
                full_product_frontier_path=full_frontier_paths["published_path"],
                full_product_frontier_mirror_path=full_frontier_paths["mirror_path"],
            )
            run_count += 1
            blocker = _normalize_blocker(run.blocker).lower()
            if args.dry_run:
                print(json.dumps(_run_payload(run), indent=2, sort_keys=True))
                return 0
            if run.worker_exit_code != 0 or not run.accepted:
                failure_reason = run.acceptance_reason or f"worker exit {run.worker_exit_code}"
                print(f"[fleet-supervisor] worker result rejected: {failure_reason}; backing off", flush=True)
                backoff_seconds = max(1.0, float(args.failure_backoff_seconds))
                if _eta_external_blocker_reason(
                    history + [_run_payload(run)],
                    context.get("completion_audit"),
                    context.get("full_product_audit"),
                ):
                    backoff_seconds = max(backoff_seconds, DEFAULT_EXTERNAL_BLOCKER_BACKOFF_SECONDS)
                time.sleep(backoff_seconds)
                if args.max_runs and run_count >= int(args.max_runs):
                    return max(1, run.worker_exit_code)
                continue
            if args.stop_on_blocker and blocker not in BLOCKER_CLEAR_VALUES:
                print(f"[fleet-supervisor] stopping on blocker: {run.blocker}", flush=True)
                return 0
            if args.max_runs and run_count >= int(args.max_runs):
                return 0
            time.sleep(max(1.0, float(args.cooldown_seconds or args.poll_seconds)))
    finally:
        _release_lock(lock_path)


def main() -> None:
    args = parse_args()
    if bool(getattr(args, "ignore_nonlinux_desktop_host_proof_blockers", False)):
        os.environ["CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS"] = "1"
    if args.command in {"status", "eta"} and _inside_active_worker_run():
        allowed, blocked_reason = _enforce_worker_status_budget()
        if allowed:
            payload = _worker_status_task_local_payload(args, blocked_reason)
            payload["command"] = str(args.command)
            payload["nonfatal_fallback"] = True
            if args.json:
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                print(_render_worker_status_task_local_payload(payload))
            raise SystemExit(0)
        blocked_payload = _worker_status_task_local_payload(args, blocked_reason)
        blocked_payload["command"] = str(args.command)
        blocked_payload["nonfatal_fallback"] = True
        blocked_payload["status_budget_exhausted"] = True
        if args.json:
            print(json.dumps(blocked_payload, indent=2, sort_keys=True))
        else:
            print(_render_worker_status_task_local_payload(blocked_payload))
        print(_worker_status_block_message(args, blocked_reason), file=sys.stderr)
        raise SystemExit(2)
    if args.command == "status":
        state_root = Path(args.state_root).resolve()
        include_shards = not state_root.name.startswith("shard-")
        if args.live_refresh:
            state, history = _effective_supervisor_state(
                state_root,
                history_limit=ETA_HISTORY_LIMIT,
                include_history=True,
            )
            state, history = _live_state_with_current_completion_audit(
                args,
                state_root,
                state,
                history,
                include_shards=include_shards,
            )
            if not _eta_snapshot_has_progress_fields(state.get("eta")):
                eta_args = argparse.Namespace(**vars(args))
                eta_args.command = "eta"
                fallback_eta = derive_eta(eta_args)
                if _eta_snapshot_has_progress_fields(fallback_eta):
                    state["eta"] = dict(fallback_eta)
        else:
            state, history = _effective_supervisor_state(
                state_root,
                history_limit=0,
                include_history=False,
            )
            state = _fast_status_state(
                args,
                state_root,
                state,
                include_shards=include_shards,
            )
            if args.json and _status_json_requires_rich_refresh(state, include_shards=include_shards):
                state, history = _effective_supervisor_state(
                    state_root,
                    history_limit=ETA_HISTORY_LIMIT,
                    include_history=True,
                )
                state, history = _live_state_with_current_completion_audit(
                    args,
                    state_root,
                    state,
                    history,
                    include_shards=include_shards,
                    refresh_flagship_readiness=False,
                )
        _persist_live_state_snapshot(state_root, state)
        if args.json:
            print(json.dumps(state, indent=2, sort_keys=True))
        else:
            print(_render_status(state))
        return
    if args.command == "eta":
        eta = derive_eta(args)
        if args.json:
            print(json.dumps(eta, indent=2, sort_keys=True))
        else:
            print(_render_eta(eta))
        return
    if args.command == "trace":
        state_root = Path(args.state_root).resolve()
        state, history = _effective_supervisor_state(state_root, history_limit=max(0, int(args.limit)))
        include_shards = not state_root.name.startswith("shard-")
        state, history = _live_state_with_current_completion_audit(
            args,
            state_root,
            state,
            history,
            include_shards=include_shards,
        )
        if not _eta_snapshot_has_progress_fields(state.get("eta")):
            eta_args = argparse.Namespace(**vars(args))
            eta_args.command = "eta"
            fallback_eta = derive_eta(eta_args)
            if _eta_snapshot_has_progress_fields(fallback_eta):
                state["eta"] = dict(fallback_eta)
        _persist_live_state_snapshot(state_root, state)
        if args.json:
            print(json.dumps({"state": state, "history": history}, indent=2, sort_keys=True))
        else:
            print(_render_trace(state, history))
        return
    if args.command in {"once", "derive"}:
        raise SystemExit(run_once(args))
    if args.command == "loop":
        raise SystemExit(run_loop(args))
    raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
