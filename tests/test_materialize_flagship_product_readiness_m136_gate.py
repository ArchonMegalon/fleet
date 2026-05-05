from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location


_SPEC = spec_from_file_location(
    "materialize_flagship_product_readiness",
    "/docker/fleet/scripts/materialize_flagship_product_readiness.py",
)
assert _SPEC and _SPEC.loader
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
_m136_aggregate_readiness_gate_audit = _MODULE._m136_aggregate_readiness_gate_audit


def test_m136_aggregate_readiness_gate_audit_requires_passing_package_and_monitor() -> None:
    audit = _m136_aggregate_readiness_gate_audit(
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "monitor_summary": {"aggregate_readiness_status": "blocked"},
        }
    )

    assert audit["ready"] is False
    assert "blocked runtime proof" in audit["reasons"][0]


def test_m136_aggregate_readiness_gate_audit_accepts_passing_payload() -> None:
    audit = _m136_aggregate_readiness_gate_audit(
        {
            "generated_at": "2026-05-05T12:00:00Z",
            "status": "pass",
            "monitor_summary": {"aggregate_readiness_status": "pass"},
        }
    )

    assert audit["ready"] is True
    assert audit["reasons"] == []
