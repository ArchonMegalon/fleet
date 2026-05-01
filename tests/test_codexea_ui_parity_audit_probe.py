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
    generated_dialog_parity = module._load_json(module.GENERATED_DIALOG_PARITY_PATH)
    section_host_parity = module._load_json(module.SECTION_HOST_PARITY_PATH)
    import_parity_cert = module._load_json(module.IMPORT_PARITY_CERT_PATH)
    visual_gate = module._load_json(module.VISUAL_GATE_PATH)
    visual_evidence = visual_gate.get("evidence") if isinstance(visual_gate.get("evidence"), dict) else {}

    statuses, _ = module._dynamic_artifact_statuses(
        workflow_gate,
        workflow_parity,
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
    generated_dialog_parity = module._load_json(module.GENERATED_DIALOG_PARITY_PATH)
    section_host_parity = module._load_json(module.SECTION_HOST_PARITY_PATH)
    import_parity_cert = module._load_json(module.IMPORT_PARITY_CERT_PATH)
    visual_gate = module._load_json(module.VISUAL_GATE_PATH)
    visual_evidence = visual_gate.get("evidence") if isinstance(visual_gate.get("evidence"), dict) else {}

    statuses, _ = module._dynamic_artifact_statuses(
        workflow_gate,
        workflow_parity,
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
