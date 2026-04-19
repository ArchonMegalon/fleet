from __future__ import annotations

import json
from pathlib import Path

import yaml


PRODUCT_ROOT = Path("/docker/fleet/.codex-design/product")
REPO_ROOT = Path("/docker/fleet/.codex-design/repo")
REVIEW_ROOT = Path("/docker/fleet/.codex-design/review")
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


def test_design_mirror_includes_governor_feedback_and_public_install_policy_docs() -> None:
    required = {
        "LEAD_DESIGNER_OPERATING_MODEL.md",
        "PRODUCT_GOVERNOR_AND_AUTOPILOT_LOOP.md",
        "PRODUCT_HEALTH_SCORECARD.yaml",
        "PUBLIC_DOWNLOADS_POLICY.md",
        "PUBLIC_AUTO_UPDATE_POLICY.md",
        "FEEDBACK_AND_CRASH_REPORTING_SYSTEM.md",
        "FEEDBACK_AND_SIGNAL_OODA_LOOP.md",
        "FEEDBACK_AND_CRASH_STATUS_MODEL.md",
    }

    for name in required:
        assert (PRODUCT_ROOT / name).exists(), name

    governor = (PRODUCT_ROOT / "PRODUCT_GOVERNOR_AND_AUTOPILOT_LOOP.md").read_text(encoding="utf-8")
    feedback_loop = (PRODUCT_ROOT / "FEEDBACK_AND_SIGNAL_OODA_LOOP.md").read_text(encoding="utf-8")
    downloads = (PRODUCT_ROOT / "PUBLIC_DOWNLOADS_POLICY.md").read_text(encoding="utf-8")
    auto_update = (PRODUCT_ROOT / "PUBLIC_AUTO_UPDATE_POLICY.md").read_text(encoding="utf-8")

    assert "Product governor" in governor
    assert "Hub owns the raw inbox" in feedback_loop
    assert "Get preview build" in downloads
    assert "Registry owns promoted desktop head" in auto_update


def test_design_mirror_readme_front_door_points_at_flagship_desktop_canon() -> None:
    readme = (PRODUCT_ROOT / "README.md").read_text(encoding="utf-8")
    future_lane_block = readme.split("5. Future lanes and public explainer posture:", 1)[1].split("### Full canonical set", 1)[0]
    canonical_set_block = readme.split("### Full canonical set", 1)[1].split("`HORIZON_REGISTRY.yaml` is the machine-readable source", 1)[0]

    assert "FLAGSHIP_PRODUCT_BAR.md" in readme
    assert "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md" in readme
    assert "CHUMMER5A_FAMILIARITY_BRIDGE.md" in readme
    assert "DESKTOP_EXECUTABLE_EXIT_GATES.md" in readme
    assert "FLAGSHIP_RELEASE_ACCEPTANCE.yaml" in readme
    assert "LEGACY_CLIENT_AND_ADJACENT_PARITY.md" in readme
    assert "LEGACY_CLIENT_AND_ADJACENT_PARITY_REGISTRY.yaml" in readme
    assert "PUBLIC_RELEASE_EXPERIENCE.yaml" in readme
    assert "GOLDEN_JOURNEY_RELEASE_GATES.yaml" in readme
    assert future_lane_block.index("SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md") < future_lane_block.index("CHUMMER5A_FAMILIARITY_BRIDGE.md")
    assert future_lane_block.index("CHUMMER5A_FAMILIARITY_BRIDGE.md") < future_lane_block.index("DESKTOP_EXECUTABLE_EXIT_GATES.md")
    assert future_lane_block.index("DESKTOP_EXECUTABLE_EXIT_GATES.md") < future_lane_block.index("FLAGSHIP_RELEASE_ACCEPTANCE.yaml")
    assert canonical_set_block.index("SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md") < canonical_set_block.index("CHUMMER5A_FAMILIARITY_BRIDGE.md")
    assert canonical_set_block.index("CHUMMER5A_FAMILIARITY_BRIDGE.md") < canonical_set_block.index("DESKTOP_EXECUTABLE_EXIT_GATES.md")
    assert canonical_set_block.index("DESKTOP_EXECUTABLE_EXIT_GATES.md") < canonical_set_block.index("LEGACY_CLIENT_AND_ADJACENT_PARITY.md")
    assert "veteran-orientation bridge for install, first-run, and workbench familiarity" in readme
    assert "machine-checked desktop flagship gates for installer coherence" in readme


def test_design_mirror_includes_flagship_desktop_acceptance_canon() -> None:
    required = {
        "FLAGSHIP_PRODUCT_BAR.md",
        "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md",
        "CHUMMER5A_FAMILIARITY_BRIDGE.md",
        "DESKTOP_EXECUTABLE_EXIT_GATES.md",
        "LEGACY_CLIENT_AND_ADJACENT_PARITY.md",
        "LEGACY_CLIENT_AND_ADJACENT_PARITY_REGISTRY.yaml",
        "FLAGSHIP_RELEASE_ACCEPTANCE.yaml",
        "PUBLIC_RELEASE_EXPERIENCE.yaml",
        "GOLDEN_JOURNEY_RELEASE_GATES.yaml",
    }

    for name in required:
        assert (PRODUCT_ROOT / name).exists(), name

    flagship_bar = (PRODUCT_ROOT / "FLAGSHIP_PRODUCT_BAR.md").read_text(encoding="utf-8")
    surface_review = (PRODUCT_ROOT / "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md").read_text(encoding="utf-8")
    familiarity = (PRODUCT_ROOT / "CHUMMER5A_FAMILIARITY_BRIDGE.md").read_text(encoding="utf-8")
    executable_gates = (PRODUCT_ROOT / "DESKTOP_EXECUTABLE_EXIT_GATES.md").read_text(encoding="utf-8")
    parity = (PRODUCT_ROOT / "LEGACY_CLIENT_AND_ADJACENT_PARITY.md").read_text(encoding="utf-8")
    acceptance = _yaml(PRODUCT_ROOT / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml")
    public_release = _yaml(PRODUCT_ROOT / "PUBLIC_RELEASE_EXPERIENCE.yaml")
    journeys = _yaml(PRODUCT_ROOT / "GOLDEN_JOURNEY_RELEASE_GATES.yaml")

    assert "Desktop familiarity must still read as Chummer5a" in flagship_bar
    assert "Install and first-run experience must feel like one product" in flagship_bar
    assert "Desktop install and first-run grammar" in surface_review
    assert "browser to copy a claim code manually" in surface_review
    assert "Install and first-run continuity must not break veteran orientation" in familiarity
    assert "framework-first installer choice" in familiarity
    assert "Product-installer coherence" in executable_gates
    assert "browser-only claim-code entry" in executable_gates
    assert "dashboard-first or browser-ritual detour between install and workbench" in parity
    assert any(axis.get("id") == "desktop_familiarity_and_install_continuity" for axis in (acceptance.get("acceptance_axes") or []))
    desktop_surface = next(item for item in (acceptance.get("surfaces") or []) if item.get("id") == "desktop_workbench")
    must_prove = list(desktop_surface.get("must_prove") or [])
    assert any("guided product installer path" in item for item in must_prove)
    assert any("workbench or restore continuation flow" in item for item in must_prove)
    assert any("real `File` menu" in item for item in must_prove)
    rules = list(public_release.get("flagship_release_rules") or [])
    assert any("guided Chummer product installer path first" in item for item in rules)
    assert any("browser to copy or paste a claim code by hand" in item for item in rules)
    install_gate = next(item for item in (journeys.get("journey_gates") or []) if item.get("id") == "install_claim_restore_continue")
    install_proof = list((((install_gate.get("fleet_gate") or {}).get("repo_source_proof")) or []))
    ui_gate = next(item for item in install_proof if item.get("repo") == "chummer6-ui" and str(item.get("path") or "").endswith("DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"))
    ui_equals = dict(ui_gate.get("json_must_equal") or {})
    assert ui_equals.get("evidence.desktop_familiarity.file_menu_live") is True
    assert ui_equals.get("evidence.desktop_familiarity.master_index_first_class") is True
    assert ui_equals.get("evidence.desktop_familiarity.character_roster_first_class") is True
    assert ui_equals.get("evidence.desktop_familiarity.startup_opens_workbench_not_landing") is True
    assert ui_equals.get("evidence.install_experience.manual_browser_claim_code_required") is False
    assert ui_equals.get("evidence.install_experience.claim_flow_surface") == "installer_or_in_app"
    assert ui_equals.get("evidence.install_experience.product_installer_guides_head_choice") is True


def test_design_mirror_includes_flagship_desktop_scope_and_review_bar() -> None:
    implementation_scope_path = REPO_ROOT / "IMPLEMENTATION_SCOPE.md"
    review_context_path = REVIEW_ROOT / "REVIEW_CONTEXT.md"

    assert implementation_scope_path.exists()
    assert review_context_path.exists()

    implementation_scope = implementation_scope_path.read_text(encoding="utf-8")
    review_context = review_context_path.read_text(encoding="utf-8")

    assert "fail-closed completion evidence when desktop flagship proof is missing real workbench-first startup" in implementation_scope
    assert "first-class master index or character roster" in implementation_scope
    assert "in-product claim/recovery handling" in implementation_scope
    assert "let Fleet mark the desktop flagship as complete while the user still sees a generic shell" in implementation_scope
    assert "framework-first installer choice" in implementation_scope
    assert "a real `File` menu" in review_context
    assert "first-class master-index and character-roster routes" in review_context
    assert "workbench-first startup instead of decorative landing or mainframe shell" in review_context
    assert "in-product installer or first-run claim handling instead of browser-only claim-code ritual" in review_context
    assert "generic dashboard shell or framework-first installer choice as acceptable modernization" in review_context


def test_design_mirror_journey_files_live_under_journeys_directory() -> None:
    required = {
        "build-and-inspect-a-character.md",
        "claim-install-and-close-a-support-case.md",
        "continue-on-a-second-claimed-device.md",
        "install-and-update.md",
        "organize-a-community-and-close-the-loop.md",
        "publish-a-grounded-artifact.md",
        "recover-from-sync-conflict.md",
        "rejoin-after-disconnect.md",
        "run-a-campaign-and-return.md",
    }

    listed = {path.name for path in JOURNEYS_ROOT.glob("*.md") if path.is_file() and path.name != "README.md"}
    assert listed == required
    for name in required:
        assert not (PRODUCT_ROOT / name).exists()


def test_design_mirror_horizon_docs_match_canonical_horizon_set() -> None:
    canonical_root = Path("/docker/chummercomplete/chummer-design/products/chummer/horizons")
    mirror_root = PRODUCT_ROOT / "horizons"

    canonical_docs = {path.name for path in canonical_root.glob("*.md") if path.is_file()}
    mirrored_docs = {path.name for path in mirror_root.glob("*.md") if path.is_file()}

    assert canonical_docs == mirrored_docs


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
