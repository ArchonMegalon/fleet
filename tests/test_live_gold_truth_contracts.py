from __future__ import annotations

from argparse import Namespace
import importlib.util
from pathlib import Path
import sys


ROOT = Path("/docker/fleet")


def _load_final_gold_janitor_module():
    script = ROOT / "scripts" / "final_gold_janitor.py"
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("final_gold_janitor_under_test", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_live_backed_release_truth_matrix_rejects_preview_and_archive_copy() -> None:
    script = (ROOT / "scripts" / "verify_live_backed_release_truth_matrix.py").read_text(encoding="utf-8")
    for token in (
        "public archive preview",
        "preview channel",
        "current preview channel",
        "still manual",
        "archive package",
        "mobile play shell preview",
        "RELEASE_CHANNEL.generated.json",
        "releases.json",
    ):
        assert token in script


def test_materialize_full_product_reaudit_v18_live_truth_matches_release_channel_contract() -> None:
    script = (ROOT / "scripts" / "materialize_full_product_reaudit_v18.py").read_text(encoding="utf-8")
    for token in (
        'RELEASE_CHANNEL_ROUTE = "/downloads/RELEASE_CHANNEL.generated.json"',
        'RELEASES_ROUTE = "/downloads/releases.json"',
        "release_channel_not_public_stable",
        "release_channel_not_gold_supported",
        "status_build_mismatch:",
        "downloads_caution:",
        "home_caution:",
    ):
        assert token in script


def test_final_gold_janitor_defaults_to_strict_live_backed_mode() -> None:
    script = (ROOT / "scripts" / "final_gold_janitor.py").read_text(encoding="utf-8")
    assert "parser.set_defaults(require_durable_artifacts=True, live_backed=True, recrawl_live=True)" in script
    assert '--allow-non-durable-artifacts' in script
    assert '--allow-non-live-backed' in script
    assert '--skip-live-recrawl' in script
    assert "CHUMMER_COMPLETION_ROOT" in script
    assert "CHUMMER_FINAL_GOLD_ARTIFACT_ROOT" in script
    assert "full_product_reaudit_v20" in script
    assert "full_product_reaudit_v18" not in script
    assert "CONTRACT_NAME" in script
    assert 'ROOT.parent / "chummercomplete"' not in script


def test_final_gold_janitor_rejects_stale_modern_live_recrawl(monkeypatch) -> None:
    janitor = _load_final_gold_janitor_module()
    monkeypatch.setenv("RAFTER_PIXEFY_GENERATED_AT_UTC", "2026-06-21T03:00:00Z")
    args = Namespace(require_durable_artifacts=True, live_backed=True, recrawl_live=True)
    payload = {
        "contract_name": "chummer.final_gold_janitor",
        "generated_at_utc": "2026-06-21T02:00:00Z",
        "status": "pass",
        "verdict": "GOLD_READY",
        "durable_artifacts_required": True,
        "live_backed_required": True,
        "live_recrawl_required": True,
        "recrawl_max_age_hours": 24,
        "required_gates": {
            "live_public_web_recrawl": {
                "status": "pass",
                "pass": True,
                "fresh_within_hours": 24,
                "generated_at_utc": "2026-06-19T23:00:00Z",
            },
        },
    }

    reasons = janitor.modern_janitor_reasons(payload, args)

    assert "source_live_recrawl_generated_at_stale" in reasons


def test_final_gold_janitor_rejects_stale_modern_source_payload(monkeypatch) -> None:
    janitor = _load_final_gold_janitor_module()
    monkeypatch.setenv("RAFTER_PIXEFY_GENERATED_AT_UTC", "2026-06-21T03:00:00Z")
    args = Namespace(require_durable_artifacts=True, live_backed=True, recrawl_live=True)
    payload = {
        "contract_name": "chummer.final_gold_janitor",
        "generated_at_utc": "2026-06-19T02:00:00Z",
        "status": "pass",
        "verdict": "GOLD_READY",
        "durable_artifacts_required": True,
        "live_backed_required": True,
        "live_recrawl_required": True,
        "recrawl_max_age_hours": 24,
        "required_gates": {
            "live_public_web_recrawl": {
                "status": "pass",
                "pass": True,
                "fresh_within_hours": 1,
                "generated_at_utc": "2026-06-21T02:30:00Z",
            },
        },
    }

    reasons = janitor.modern_janitor_reasons(payload, args)

    assert "source_janitor_stale" in reasons


def test_flagship_readiness_consumes_current_live_gold_truth() -> None:
    script = (ROOT / "scripts" / "materialize_flagship_product_readiness.py").read_text(encoding="utf-8")
    assert "DEFAULT_FINAL_GOLD_JANITOR" in script
    assert "DEFAULT_LIVE_BACKED_RELEASE_TRUTH_MATRIX" in script
    assert "_janitor_has_modern_live_truth" in script
    assert "_modern_janitor_live_truth_ready" in script
    assert "CHUMMER_COMPLETION_ROOT" in script
    assert "CHUMMER_FINAL_GOLD_ARTIFACT_ROOT" in script
    assert "full_product_reaudit_v20" in script
    assert 'return ROOT / "_completion" / "full_product_reaudit_v18"' not in script
    assert "Live-backed release truth matrix does not currently allow a gold claim for chummer.run." in script
    assert "operator diagnosis" in script
    assert "proof graph becomes circular" in script
