from __future__ import annotations

from pathlib import Path

import yaml


PRODUCT_ROOT = Path("/docker/fleet/.codex-design/product")
REPO_ROOT = Path("/docker/fleet/.codex-design/repo")
REVIEW_ROOT = Path("/docker/fleet/.codex-design/review")


def _yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def test_flagship_desktop_non_negotiables_stay_consistent_across_acceptance_release_scope_and_review() -> None:
    acceptance = _yaml(PRODUCT_ROOT / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml")
    public_release = _yaml(PRODUCT_ROOT / "PUBLIC_RELEASE_EXPERIENCE.yaml")
    journeys = _yaml(PRODUCT_ROOT / "GOLDEN_JOURNEY_RELEASE_GATES.yaml")
    flagship_bar = (PRODUCT_ROOT / "FLAGSHIP_PRODUCT_BAR.md").read_text(encoding="utf-8")
    familiarity = (PRODUCT_ROOT / "CHUMMER5A_FAMILIARITY_BRIDGE.md").read_text(encoding="utf-8")
    executable_gates = (PRODUCT_ROOT / "DESKTOP_EXECUTABLE_EXIT_GATES.md").read_text(encoding="utf-8")
    implementation_scope = (REPO_ROOT / "IMPLEMENTATION_SCOPE.md").read_text(encoding="utf-8")
    review_context = (REVIEW_ROOT / "REVIEW_CONTEXT.md").read_text(encoding="utf-8")

    desktop_surface = next(item for item in (acceptance.get("surfaces") or []) if item.get("id") == "desktop_workbench")
    desktop_must_prove = " ".join(str(item) for item in (desktop_surface.get("must_prove") or []))
    release_rules = " ".join(str(item) for item in (public_release.get("flagship_release_rules") or []))
    install_gate = next(item for item in (journeys.get("journey_gates") or []) if item.get("id") == "install_claim_restore_continue")
    install_proof = list((((install_gate.get("fleet_gate") or {}).get("repo_source_proof")) or []))
    ui_gate = next(
        item
        for item in install_proof
        if item.get("repo") == "chummer6-ui" and str(item.get("path") or "").endswith("DESKTOP_EXECUTABLE_EXIT_GATE.generated.json")
    )
    ui_equals = dict(ui_gate.get("json_must_equal") or {})

    assert "guided product installer path" in desktop_must_prove
    assert "installer or app" in desktop_must_prove
    assert "workbench or restore continuation flow" in desktop_must_prove
    assert "real `File` menu" in desktop_must_prove
    assert "master index" in desktop_must_prove
    assert "character roster" in desktop_must_prove

    assert "guided Chummer product installer path first" in release_rules
    assert "browser to copy or paste a claim code by hand" in release_rules
    assert "opens the real workbench or restore continuation flow" in release_rules

    assert ui_equals.get("evidence.desktop_familiarity.file_menu_live") is True
    assert ui_equals.get("evidence.desktop_familiarity.master_index_first_class") is True
    assert ui_equals.get("evidence.desktop_familiarity.character_roster_first_class") is True
    assert ui_equals.get("evidence.desktop_familiarity.startup_opens_workbench_not_landing") is True
    assert ui_equals.get("evidence.install_experience.manual_browser_claim_code_required") is False
    assert ui_equals.get("evidence.install_experience.claim_flow_surface") == "installer_or_in_app"
    assert ui_equals.get("evidence.install_experience.product_installer_guides_head_choice") is True

    assert "Install and first-run experience must feel like one product" in flagship_bar
    assert "Desktop familiarity must still read as Chummer5a" in flagship_bar

    assert "framework-first installer choice" in familiarity
    assert "decorative landing page before the workbench" in familiarity

    assert "browser-only claim-code entry" in executable_gates
    assert "landing-page/mainframe/dashboard-first startup" in executable_gates

    assert "fail-closed completion evidence when desktop flagship proof is missing real workbench-first startup" in implementation_scope
    assert "first-class master index or character roster" in implementation_scope
    assert "in-product claim/recovery handling" in implementation_scope

    assert "a real `File` menu" in review_context
    assert "first-class master-index and character-roster routes" in review_context
    assert "workbench-first startup instead of decorative landing or mainframe shell" in review_context
    assert "browser-only claim-code ritual" in review_context
