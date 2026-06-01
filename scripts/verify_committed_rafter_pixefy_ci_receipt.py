#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PROMOTED_PLATFORM_HEAD_RID_TUPLES = {
    "avalonia:linux-x64:linux",
    "avalonia:osx-arm64:macos",
    "avalonia:win-x64:windows",
}
REQUIRED_PUBLIC_ROUTES = {
    "https://chummer.run/",
    "https://chummer.run/downloads",
    "https://chummer.run/status",
}

PROVIDERS = {
    "Rafter": {
        "provider_path": ROOT / "_completion" / "rafter" / "RAFTER_PROVIDER_VERIFICATION.generated.json",
        "gate_path": ROOT / "_completion" / "rafter" / "RAFTER_SECURITY_GOLD_GATE.generated.json",
        "provider_status": "verified",
        "gate_status": "pass",
        "gate_name": "RAFTER_SECURITY_GOLD_GATE",
        "route_manifest_path": ROOT / "_completion" / "rafter" / "RAFTER_LIVE_SITE_SCAN.generated.json",
    },
    "Pixefy": {
        "provider_path": ROOT / "_completion" / "pixefy" / "PIXEFY_PROVIDER_VERIFICATION.generated.json",
        "gate_path": ROOT / "_completion" / "pixefy" / "PIXEFY_RESPONSIVE_VISUAL_QA.generated.json",
        "provider_status": "verified",
        "gate_status": "pass",
        "gate_name": "PIXEFY_RESPONSIVE_VISUAL_QA",
        "route_manifest_path": ROOT / "_completion" / "pixefy" / "PIXEFY_ROUTE_CAPTURE_MANIFEST.generated.json",
        "screenshot_index_path": ROOT / "_completion" / "pixefy" / "PIXEFY_SCREENSHOT_INDEX.generated.json",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"missing receipt: {path.relative_to(ROOT)}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid receipt json: {path.relative_to(ROOT)}: {exc}") from None
    if not isinstance(payload, dict):
        raise SystemExit(f"receipt must be a JSON object: {path.relative_to(ROOT)}")
    return payload


def parse_timestamp(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "chummer-rafter-pixefy-ci-live-binding/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        if not (200 <= int(response.status) < 400):
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return response.read(1_500_000).decode("utf-8", "ignore")


def fetch_json(url: str) -> dict[str, Any]:
    payload = json.loads(fetch_text(url))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{url} did not return a JSON object")
    return payload


def require_active_release_binding(gate: dict[str, Any], failures: list[str]) -> None:
    binding = gate.get("active_release_binding")
    if not isinstance(binding, dict):
        failures.append("gate_missing_active_release_binding")
        return

    if binding.get("verification_status") != "pass":
        failures.append("active_release_binding_not_pass")
    if binding.get("base_url") != "https://chummer.run":
        failures.append("active_release_binding_base_url_mismatch")
    if binding.get("channelId") != "public_stable":
        failures.append("active_release_binding_channel_not_public_stable")
    if binding.get("status") != "published":
        failures.append("active_release_binding_status_not_published")
    if binding.get("rolloutState") != "public_stable":
        failures.append("active_release_binding_rollout_not_public_stable")
    if not str(binding.get("version") or "").startswith("run-"):
        failures.append("active_release_binding_version_missing_or_invalid")
    if binding.get("missingRequiredPlatformHeadRidTuples"):
        failures.append("active_release_binding_missing_platform_tuples")
    promoted = set(binding.get("promotedPlatformHeadRidTuples") or [])
    if not REQUIRED_PROMOTED_PLATFORM_HEAD_RID_TUPLES.issubset(promoted):
        failures.append("active_release_binding_required_tuple_not_promoted")

    generated_at = parse_timestamp(gate.get("generated_at_utc") or gate.get("generated_at"))
    if generated_at is None:
        failures.append("gate_generation_timestamp_not_parseable")
    else:
        age_hours = (datetime.now(timezone.utc) - generated_at.astimezone(timezone.utc)).total_seconds() / 3600
        if age_hours > 72:
            failures.append("gate_receipt_older_than_72h")


def require_live_release_alignment(gate: dict[str, Any], failures: list[str]) -> None:
    binding = gate.get("active_release_binding")
    if not isinstance(binding, dict):
        return
    version = str(binding.get("version") or "").strip()
    try:
        release_manifest = fetch_json("https://chummer.run/downloads/releases.json")
        status_html = fetch_text("https://chummer.run/status")
    except Exception as exc:  # noqa: BLE001 - receipt verifier should report the exact live-proof failure.
        failures.append(f"live_release_alignment_fetch_failed:{type(exc).__name__}")
        return

    live_channel = str(release_manifest.get("channelId") or release_manifest.get("channel") or "").strip()
    live_version = str(release_manifest.get("version") or release_manifest.get("releaseVersion") or "").strip()
    live_status = str(release_manifest.get("status") or "").strip()
    live_rollout = str(release_manifest.get("rolloutState") or "").strip()
    live_coverage = release_manifest.get("desktopTupleCoverage") if isinstance(release_manifest.get("desktopTupleCoverage"), dict) else {}
    live_promoted = set(live_coverage.get("promotedPlatformHeadRidTuples") or [])
    live_missing = live_coverage.get("missingRequiredPlatformHeadRidTuples") or []

    if live_channel != "public_stable":
        failures.append("live_release_channel_not_public_stable")
    if live_version != version:
        failures.append("live_release_version_mismatch")
    if live_status != "published":
        failures.append("live_release_status_not_published")
    if live_rollout != "public_stable":
        failures.append("live_release_rollout_not_public_stable")
    if live_missing:
        failures.append("live_release_missing_platform_tuples")
    if not REQUIRED_PROMOTED_PLATFORM_HEAD_RID_TUPLES.issubset(live_promoted):
        failures.append("live_release_required_tuple_not_promoted")
    if version not in status_html:
        failures.append("live_status_page_missing_bound_version")
    if "Gold-ready on Public release Build" not in status_html:
        failures.append("live_status_page_missing_gold_ready_public_release_phrase")


def require_public_route_manifest(spec: dict[str, Any], provider_name: str, gate: dict[str, Any], failures: list[str]) -> None:
    manifest = load_json(spec["route_manifest_path"])
    if str(manifest.get("status") or "").lower() != "pass":
        failures.append("route_manifest_not_pass")
    manifest_binding = manifest.get("active_release_binding")
    gate_binding = gate.get("active_release_binding")
    if not isinstance(manifest_binding, dict):
        failures.append("route_manifest_missing_active_release_binding")
    else:
        if manifest_binding.get("verification_status") != "pass":
            failures.append("route_manifest_active_release_binding_not_pass")
        if isinstance(gate_binding, dict) and manifest_binding.get("version") != gate_binding.get("version"):
            failures.append("route_manifest_active_release_binding_version_mismatch")

    if provider_name == "Rafter":
        urls = set(manifest.get("required_live_routes") or []) | set(manifest.get("scanned_live_routes") or [])
        if manifest.get("missing_live_routes"):
            failures.append("rafter_route_manifest_has_missing_live_routes")
        if manifest.get("forbidden_public_copy_routes"):
            failures.append("rafter_route_manifest_has_forbidden_public_copy")
        for row in manifest.get("route_results") or []:
            if isinstance(row, dict) and not row.get("ok"):
                failures.append("rafter_route_manifest_contains_non_ok_route")
                break
    else:
        urls = {str(route.get("url") or "") for route in manifest.get("routes") or [] if isinstance(route, dict)}
    if not REQUIRED_PUBLIC_ROUTES.issubset(urls):
        failures.append("route_manifest_missing_required_public_routes")


def require_pixefy_screenshots(spec: dict[str, Any], gate: dict[str, Any], failures: list[str]) -> None:
    if "screenshot_index_path" not in spec:
        return
    index = load_json(spec["screenshot_index_path"])
    if str(index.get("status") or "").lower() != "pass":
        failures.append("pixefy_screenshot_index_not_pass")

    coverage = gate.get("coverage") if isinstance(gate.get("coverage"), dict) else {}
    if coverage.get("captured_device_route_pairs") != 110:
        failures.append("pixefy_captured_pair_count_not_110")
    if coverage.get("missing_device_route_pairs"):
        failures.append("pixefy_missing_device_route_pairs")

    seen_pairs = 0
    missing_files: list[str] = []
    for route in index.get("routes") or []:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("route_id") or "")
        for capture in route.get("captures") or []:
            if not isinstance(capture, dict):
                continue
            seen_pairs += 1
            if capture.get("status") != "captured":
                missing_files.append(f"{route_id}:{capture.get('device_id')}:not_captured")
                continue
            screenshot_path = ROOT / "_completion" / "pixefy" / str(capture.get("screenshot_path") or "")
            if not screenshot_path.is_file() or screenshot_path.stat().st_size <= 0:
                missing_files.append(f"{route_id}:{capture.get('device_id')}:missing_file")

    if seen_pairs != 110:
        failures.append("pixefy_screenshot_index_pair_count_not_110")
    if missing_files:
        failures.append("pixefy_screenshot_files_missing_or_empty")


def collect_provider_failures(provider_name: str) -> list[str]:
    spec = PROVIDERS[provider_name]
    provider = load_json(spec["provider_path"])
    gate = load_json(spec["gate_path"])
    failures: list[str] = []

    if str(provider.get("service") or "").strip() != provider_name:
        failures.append("provider_service_mismatch")
    if str(provider.get("status") or "").strip().lower() != spec["provider_status"]:
        failures.append("provider_not_verified")
    if provider.get("failures"):
        failures.append("provider_receipt_has_failures")
    if str(gate.get("gate") or "").strip() != spec["gate_name"]:
        failures.append("gate_name_mismatch")
    if str(gate.get("status") or "").strip().lower() != spec["gate_status"]:
        failures.append("gate_not_pass")
    if gate.get("failures"):
        failures.append("gate_receipt_has_failures")
    if not str(gate.get("generated_at_utc") or gate.get("generated_at") or "").strip():
        failures.append("gate_missing_generation_timestamp")
    require_active_release_binding(gate, failures)
    require_live_release_alignment(gate, failures)
    require_public_route_manifest(spec, provider_name, gate, failures)
    require_pixefy_screenshots(spec, gate, failures)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify committed Rafter/Pixefy CI receipts without local provider secrets.")
    parser.add_argument("provider", choices=sorted(PROVIDERS))
    args = parser.parse_args()

    failures = collect_provider_failures(args.provider)
    if failures:
        print(f"{args.provider} committed CI receipt failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"{args.provider} committed CI receipt verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
