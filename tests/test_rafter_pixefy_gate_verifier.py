from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/scripts/verify_committed_rafter_pixefy_ci_receipt.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_committed_rafter_pixefy_ci_receipt", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gate(version: str = "run-20260601-070650") -> dict:
    return {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "active_release_binding": {
            "verification_status": "pass",
            "base_url": "https://chummer.run",
            "channelId": "public_stable",
            "status": "published",
            "rolloutState": "public_stable",
            "version": version,
            "missingRequiredPlatformHeadRidTuples": [],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:osx-arm64:macos",
                "avalonia:win-x64:windows",
            ],
        },
    }


def _live_manifest(version: str = "run-20260601-070650") -> dict:
    return {
        "channel": "public_stable",
        "version": version,
        "status": "published",
        "rolloutState": "public_stable",
        "desktopTupleCoverage": {
            "missingRequiredPlatformHeadRidTuples": [],
            "promotedPlatformHeadRidTuples": [
                "avalonia:linux-x64:linux",
                "avalonia:osx-arm64:macos",
                "avalonia:win-x64:windows",
            ],
        },
    }


def test_live_release_alignment_rejects_version_drift(monkeypatch) -> None:
    module = _load_module()
    failures: list[str] = []
    monkeypatch.setattr(module, "fetch_json", lambda url: _live_manifest("run-older"))
    monkeypatch.setattr(module, "fetch_text", lambda url: "Gold-ready on Public release Build run-older")

    module.require_live_release_alignment(_gate("run-current"), failures)

    assert "live_release_version_mismatch" in failures
    assert "live_status_page_missing_bound_version" in failures


def test_live_release_alignment_accepts_matching_public_stable_manifest(monkeypatch) -> None:
    module = _load_module()
    failures: list[str] = []
    monkeypatch.setattr(module, "fetch_json", lambda url: _live_manifest())
    monkeypatch.setattr(module, "fetch_text", lambda url: "Gold-ready on Public release Build run-20260601-070650")

    module.require_live_release_alignment(_gate(), failures)

    assert failures == []


def test_pixefy_screenshot_verifier_rejects_missing_capture_file(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    index = tmp_path / "index.json"
    index.write_text(
        json.dumps(
            {
                "status": "pass",
                "routes": [
                    {
                        "route_id": "home",
                        "captures": [
                            {
                                "device_id": "iphone_se",
                                "status": "captured",
                                "screenshot_path": "screenshots/home__iphone_se.png",
                            }
                        ],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    failures: list[str] = []

    module.require_pixefy_screenshots(
        {"screenshot_index_path": index},
        {"coverage": {"captured_device_route_pairs": 110, "missing_device_route_pairs": []}},
        failures,
    )

    assert "pixefy_screenshot_index_pair_count_not_110" in failures
    assert "pixefy_screenshot_files_missing_or_empty" in failures
