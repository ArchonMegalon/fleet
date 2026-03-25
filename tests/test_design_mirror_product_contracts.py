from __future__ import annotations

import json
from pathlib import Path

import yaml


PRODUCT_ROOT = Path("/docker/fleet/.codex-design/product")
JOURNEYS_ROOT = PRODUCT_ROOT / "journeys"


def _yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def test_design_mirror_includes_public_navigation_and_progress_contract_inputs() -> None:
    navigation = _yaml(PRODUCT_ROOT / "PUBLIC_NAVIGATION.yaml")
    assets = _yaml(PRODUCT_ROOT / "PUBLIC_LANDING_ASSET_REGISTRY.yaml")
    progress = _yaml(PRODUCT_ROOT / "PUBLIC_PROGRESS_PARTS.yaml")

    assert navigation["surface"] == "chummer.run"
    assert isinstance(navigation.get("primary_nav"), list) and navigation["primary_nav"]
    assert isinstance(navigation.get("secondary_nav"), list) and navigation["secondary_nav"]
    assert assets["surface"] == "chummer.run"
    assert isinstance(assets.get("assets"), list) and assets["assets"]
    assert progress["brand"] == "Chummer6"
    assert isinstance(progress.get("parts"), list) and progress["parts"]


def test_design_mirror_journey_files_live_under_journeys_directory() -> None:
    required = {
        "build-and-inspect-a-character.md",
        "install-and-update.md",
        "publish-a-grounded-artifact.md",
        "recover-from-sync-conflict.md",
        "rejoin-after-disconnect.md",
    }

    listed = {path.name for path in JOURNEYS_ROOT.glob("*.md") if path.is_file() and path.name != "README.md"}
    assert listed == required
    for name in required:
        assert not (PRODUCT_ROOT / name).exists()


def test_design_mirror_progress_bundle_files_parse_and_expose_contract_names() -> None:
    report = _json(PRODUCT_ROOT / "PROGRESS_REPORT.generated.json")
    history = _json(PRODUCT_ROOT / "PROGRESS_HISTORY.generated.json")
    html = (PRODUCT_ROOT / "PROGRESS_REPORT.generated.html").read_text(encoding="utf-8")
    poster = (PRODUCT_ROOT / "PROGRESS_REPORT_POSTER.svg").read_text(encoding="utf-8")

    assert report["contract_name"] == "fleet.public_progress_report"
    assert history["contract_name"] == "fleet.public_progress_history"
    assert int(history.get("snapshot_count") or 0) >= 1
    assert "How to participate" in html
    assert "<svg" in poster
