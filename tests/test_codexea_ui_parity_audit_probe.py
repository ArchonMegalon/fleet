from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/codex-shims/codexea_ui_parity_audit_probe.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("codexea_ui_parity_audit_probe", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dynamic_artifact_statuses_promote_live_proven_tokens() -> None:
    module = _load_module()

    workflow_gate = module._load_json(module.WORKFLOW_GATE_PATH)
    workflow_parity = module._load_json(module.WORKFLOW_PARITY_PATH)
    m142_direct_workflow_proof = module._load_json(module.M142_DIRECT_WORKFLOW_PROOF_PATH)
    generated_dialog_parity = module._load_json(module.GENERATED_DIALOG_PARITY_PATH)
    section_host_parity = module._load_json(module.SECTION_HOST_PARITY_PATH)
    import_parity_cert = module._load_json(module.IMPORT_PARITY_CERT_PATH)
    visual_gate = module._load_json(module.VISUAL_GATE_PATH)
    visual_evidence = visual_gate.get("evidence") if isinstance(visual_gate.get("evidence"), dict) else {}

    statuses, _ = module._dynamic_artifact_statuses(
        workflow_gate,
        workflow_parity,
        m142_direct_workflow_proof,
        generated_dialog_parity,
        section_host_parity,
        import_parity_cert,
        visual_evidence,
        catalog_text=module._load_text(module.CATALOG_TESTS_PATH),
        dialog_factory_text=module._load_text(module.DIALOG_FACTORY_TESTS_PATH),
        dual_head_text=module._load_text(module.DUAL_HEAD_TESTS_PATH),
        presenter_text=module._load_text(module.PRESENTER_TESTS_PATH),
        avalonia_gate_text=module._load_text(module.AVALONIA_GATE_TESTS_PATH),
        dialog_coordinator_text=module._load_text(module.DIALOG_COORDINATOR_TESTS_PATH),
    )

    assert statuses["oracle:tabs"] is True
    assert statuses["oracle:workspace_actions"] is True
    assert statuses["workflow:build_explain_publish"] is True
    assert statuses["menu:translator"] is True
    assert statuses["menu:xml_editor"] is True
    assert statuses["menu:hero_lab_importer"] is True
    assert statuses["menu:dice_roller"] is True
    assert statuses["workflow:initiative"] is True
    assert statuses["workflow:lifestyles"] is True
    assert statuses["menu:open_for_printing"] is True
    assert statuses["menu:open_for_export"] is True
    assert statuses["menu:file_print_multiple"] is True
    assert statuses["workflow:import_oracle"] is True
    assert statuses["workflow:sr6_supplements"] is True


def test_dynamic_artifact_statuses_keep_unproven_tokens_closed() -> None:
    module = _load_module()

    workflow_gate = module._load_json(module.WORKFLOW_GATE_PATH)
    workflow_parity = module._load_json(module.WORKFLOW_PARITY_PATH)
    m142_direct_workflow_proof = module._load_json(module.M142_DIRECT_WORKFLOW_PROOF_PATH)
    generated_dialog_parity = module._load_json(module.GENERATED_DIALOG_PARITY_PATH)
    section_host_parity = module._load_json(module.SECTION_HOST_PARITY_PATH)
    import_parity_cert = module._load_json(module.IMPORT_PARITY_CERT_PATH)
    visual_gate = module._load_json(module.VISUAL_GATE_PATH)
    visual_evidence = visual_gate.get("evidence") if isinstance(visual_gate.get("evidence"), dict) else {}

    statuses, _ = module._dynamic_artifact_statuses(
        workflow_gate,
        workflow_parity,
        m142_direct_workflow_proof,
        generated_dialog_parity,
        section_host_parity,
        import_parity_cert,
        visual_evidence,
        catalog_text=module._load_text(module.CATALOG_TESTS_PATH),
        dialog_factory_text=module._load_text(module.DIALOG_FACTORY_TESTS_PATH),
        dual_head_text=module._load_text(module.DUAL_HEAD_TESTS_PATH),
        presenter_text=module._load_text(module.PRESENTER_TESTS_PATH),
        avalonia_gate_text=module._load_text(module.AVALONIA_GATE_TESTS_PATH),
        dialog_coordinator_text=module._load_text(module.DIALOG_COORDINATOR_TESTS_PATH),
    )

    assert statuses["workflow:import_oracle"] is True
    assert statuses["workflow:sr6_supplements"] is True
    assert statuses["menu:file_print_multiple"] is True


def test_direct_family_proof_rows_use_route_local_evidence_when_fully_proven() -> None:
    module = _load_module()

    direct = module.DIRECT_FAMILY_PROOF["dense_builder_and_career_workflows"]
    assert direct["reason"].startswith("Route-local dense workbench proof cites")
    assert any(item.endswith("UI_FLAGSHIP_RELEASE_GATE.generated.json") for item in direct["evidence"])

    dice = module.DIRECT_FAMILY_PROOF["dice_initiative_and_table_utilities"]
    assert any(item.endswith("NEXT90_M121_UI_GM_RUNBOARD_ROUTE.generated.json") for item in dice["evidence"])
    assert any(item.endswith("NEXT90_M142_DENSE_WORKBENCH_RECEIPTS.md") for item in dice["evidence"])


def test_direct_family_proof_routes_m142_families_to_runtime_receipts() -> None:
    module = _load_module()

    proof = module.DIRECT_FAMILY_PROOF

    dense = proof["dense_builder_and_career_workflows"]
    assert "Route-local dense workbench proof" in dense["reason"]
    assert any(item.endswith("SECTION_HOST_RULESET_PARITY.generated.json") for item in dense["evidence"])
    assert any(item.endswith("CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json") for item in dense["evidence"])
    assert any(item.endswith("NEXT90_M142_UI_DIRECT_WORKFLOW_PROOF.generated.json") for item in dense["evidence"])

    dice = proof["dice_initiative_and_table_utilities"]
    assert "Route-local dice and initiative proof" in dice["reason"]
    assert any(item.endswith("GENERATED_DIALOG_ELEMENT_PARITY.generated.json") for item in dice["evidence"])
    assert any(item.endswith("NEXT90_M121_UI_GM_RUNBOARD_ROUTE.generated.json") for item in dice["evidence"])
    assert any(item.endswith("NEXT90_M142_DENSE_WORKBENCH_RECEIPTS.md") for item in dice["evidence"])

    identity = proof["identity_contacts_lifestyles_history"]
    assert "Route-local contacts, lifestyles, and history proof" in identity["reason"]
    assert any(item.endswith("SECTION_HOST_RULESET_PARITY.generated.json") for item in identity["evidence"])
    assert any(item.endswith("NEXT90_M142_DENSE_WORKBENCH_RECEIPTS.md") for item in identity["evidence"])

    exchange = proof["sheet_export_print_viewer_and_exchange"]
    assert "Route-local print, export, and exchange proof" in exchange["reason"]
    assert any(item.endswith("GENERATED_DIALOG_ELEMENT_PARITY.generated.json") for item in exchange["evidence"])
    assert any(item.endswith("CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json") for item in exchange["evidence"])
    assert any(item.endswith("NEXT90_M143_EXPORT_PRINT_SUPPLEMENT_RULE_ENVIRONMENT_RECEIPTS.md") for item in exchange["evidence"])

    sr6 = proof["sr6_supplements_designers_and_house_rules"]
    assert "Route-local SR6 supplement" in sr6["reason"]
    assert any(item.endswith("NEXT90_M114_UI_RULE_STUDIO.generated.json") for item in sr6["evidence"])
    assert any(item.endswith("CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json") for item in sr6["evidence"])
    assert any(item.endswith("NEXT90_M143_EXPORT_PRINT_SUPPLEMENT_RULE_ENVIRONMENT_RECEIPTS.md") for item in sr6["evidence"])
