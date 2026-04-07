from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/materialize_flagship_product_readiness.py")
SPEC = importlib.util.spec_from_file_location("materialize_flagship_product_readiness_module", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_external_proof_backlog_dedupe_prefers_tuple_identity() -> None:
    request_a = {
        "tuple_id": "avalonia:win-x64:windows",
        "required_host": "windows",
        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
    }
    request_b = {
        "tupleId": "avalonia:win-x64:windows",
        "requiredHost": "windows",
        "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
    }
    request_c = {
        "tuple_id": "blazor-desktop:osx-arm64:macos",
        "required_host": "macos",
        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json",
    }

    deduped, duplicate_count = MODULE._dedupe_external_proof_requests([request_a, request_b, request_c])

    assert duplicate_count == 1
    assert len(deduped) == 2
    tuple_ids = {
        str(item.get("tuple_id") or item.get("tupleId") or "").strip().lower()
        for item in deduped
    }
    assert tuple_ids == {"avalonia:win-x64:windows", "blazor-desktop:osx-arm64:macos"}
