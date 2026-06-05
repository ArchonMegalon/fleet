from __future__ import annotations

from pathlib import Path


ROOT = Path("/docker/fleet")


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


def test_flagship_readiness_consumes_v18_live_gold_truth() -> None:
    script = (ROOT / "scripts" / "materialize_flagship_product_readiness.py").read_text(encoding="utf-8")
    assert "DEFAULT_V18_FINAL_GOLD_JANITOR" in script
    assert "DEFAULT_V18_LIVE_BACKED_RELEASE_TRUTH_MATRIX" in script
    assert "Live-backed release truth matrix does not currently allow a gold claim for chummer.run." in script
    assert "Final gold janitor is not green under durable/live-recrawled rules." in script
