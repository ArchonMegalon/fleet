#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
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


def require_public_route_manifest(spec: dict[str, Any], provider_name: str, failures: list[str]) -> None:
    manifest = load_json(spec["route_manifest_path"])
    if str(manifest.get("status") or "").lower() != "pass":
        failures.append("route_manifest_not_pass")
    binding = manifest.get("active_release_binding")
    if provider_name == "Pixefy" and not isinstance(binding, dict):
        failures.append("pixefy_route_manifest_missing_active_release_binding")

    if provider_name == "Rafter":
        urls = set(manifest.get("required_live_routes") or []) | set(manifest.get("scanned_live_routes") or [])
        if manifest.get("missing_live_routes"):
            failures.append("rafter_route_manifest_has_missing_live_routes")
    else:
        urls = {str(route.get("url") or "") for route in manifest.get("routes") or [] if isinstance(route, dict)}
    if not REQUIRED_PUBLIC_ROUTES.issubset(urls):
        failures.append("route_manifest_missing_required_public_routes")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify committed Rafter/Pixefy CI receipts without local provider secrets.")
    parser.add_argument("provider", choices=sorted(PROVIDERS))
    args = parser.parse_args()

    spec = PROVIDERS[args.provider]
    provider = load_json(spec["provider_path"])
    gate = load_json(spec["gate_path"])
    failures: list[str] = []

    if str(provider.get("service") or "").strip() != args.provider:
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
    require_public_route_manifest(spec, args.provider, failures)

    if failures:
        print(f"{args.provider} committed CI receipt failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"{args.provider} committed CI receipt verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
