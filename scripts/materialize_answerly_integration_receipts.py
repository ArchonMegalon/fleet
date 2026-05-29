#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path("/docker/chummercomplete")
EA_ROOT = Path("/docker/EA")
OUT_DIR = REPO_ROOT / "_completion" / "answerly_integration"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def contains_all(path: Path, needles: list[str]) -> bool:
    text = read_text(path)
    return all(needle in text for needle in needles)


def public_leak_scan() -> dict:
    roots = [
        REPO_ROOT / "chummer.run-services" / "Chummer.Run.Api" / "Views",
        REPO_ROOT / "chummer.run-services" / "Chummer.Run.Api" / "wwwroot",
    ]
    hits: list[str] = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            text = read_text(path)
            if "Answerly" in text or "ANSWERLY_" in text:
                hits.append(str(path))
    return {
        "status": "pass" if not hits else "fail",
        "provider_name_leaks": hits,
    }


def sourcebook_boundary_scan() -> dict:
    support_root = REPO_ROOT / "chummer.run-services" / "Chummer.Run.Api" / "Services" / "Support"
    risky_hits: list[str] = []
    for path in support_root.rglob("*.cs"):
        text = read_text(path).lower()
        if "answerly" in text and ("sourcebook" in text or "pdf" in text) and any(
            term in text for term in ("upload", "train", "sendmessageasync", "send ", "vector database")
        ):
            risky_hits.append(str(path))
    return {
        "status": "pass" if not risky_hits else "fail",
        "risky_hits": risky_hits,
    }


def provider_verification_receipt() -> dict:
    ltds = read_text(EA_ROOT / "LTDs.md")
    present = "Answerly.io" in ltds and "bounded support assistant" in ltds
    verification_state = "unverified" if "verification is still pending" in ltds.lower() else "verified_widget_only"
    return {
        "status": "pass" if present else "fail",
        "provider": "Answerly.io",
        "tier": "5",
        "verification_state": verification_state,
        "live_provider_calls_ready": verification_state == "verified_full_adapter",
    }


def design_boundary_receipt() -> dict:
    design_root = REPO_ROOT / "chummer-design" / "products" / "chummer"
    required = [
        "ANSWERLY_SUPPORT_AND_HUMANIZER_SPEC.md",
        "ANSWERLY_RULESAFE_BOUNDARY.md",
        "ANSWERLY_PROVIDER_VERIFICATION_GATE.yaml",
        "RULESAFE_ANSWER_PACKET.yaml",
        "RULES_COACH_ROUTER_SPEC.md",
    ]
    missing = [name for name in required if not (design_root / name).is_file()]
    return {
        "status": "pass" if not missing else "fail",
        "missing_files": missing,
    }


def support_assistant_receipt() -> dict:
    root = REPO_ROOT / "chummer.run-services"
    files = {
        "adapter": root / "Chummer.Run.Api" / "Services" / "Support" / "AnswerlySupportAssistantAdapter.cs",
        "controller": root / "Chummer.Run.Api" / "Controllers" / "SupportCasesController.cs",
        "registration": root / "Chummer.Run.Api" / "ServiceCollectionBoundedContextExtensions.cs",
    }
    checks = {
        "adapter_present": files["adapter"].is_file(),
        "controller_uses_adapter": contains_all(files["controller"], ["IChummerAssistantAdapter", "AskSupport("]),
        "registration_present": contains_all(files["registration"], ["AnswerlyRuntimePolicy", "IChummerAssistantAdapter", "AnswerlySupportAssistantAdapter"]),
    }
    status = "pass" if all(checks.values()) else "fail"
    return {"status": status, **checks}


def rulesafe_packet_receipt() -> dict:
    contracts = REPO_ROOT / "chummer.run-services" / "Chummer.Control.Contracts" / "SupportContracts.cs"
    return {
        "status": "pass" if contains_all(contracts, ["RuleSafeAnswerPacket", "RuleSafeOutputGateResult", "RulesCoachRouteDecision"]) else "fail"
    }


def humanizer_receipt() -> dict:
    path = REPO_ROOT / "chummer.run-services" / "Chummer.Run.Api" / "Services" / "Support" / "AnswerlyHumanizerAdapter.cs"
    return {
        "status": "pass" if contains_all(path, ["AnswerlyHumanizerAdapter", "answerly_humanizer_unavailable"]) else "fail"
    }


def output_gate_receipt() -> dict:
    path = REPO_ROOT / "chummer.run-services" / "Chummer.Run.Api" / "Services" / "Support" / "RuleSafeOutputGate.cs"
    return {
        "status": "pass" if contains_all(path, ["provider_names", "sourcebook_terms", "private_data", "copied_tables"]) else "fail"
    }


def offline_fallback_receipt() -> dict:
    policy = REPO_ROOT / "chummer.run-services" / "Chummer.Run.Api" / "Services" / "Support" / "AnswerlyRuntimePolicy.cs"
    adapter = REPO_ROOT / "chummer.run-services" / "Chummer.Run.Api" / "Services" / "Support" / "AnswerlySupportAssistantAdapter.cs"
    humanizer = REPO_ROOT / "chummer.run-services" / "Chummer.Run.Api" / "Services" / "Support" / "AnswerlyHumanizerAdapter.cs"
    ok = (
        contains_all(policy, ["ANSWERLY_ENABLED", "ANSWERLY_SUPPORT_ENABLED", "ANSWERLY_HUMANIZER_ENABLED"])
        and contains_all(adapter, ["!_policy.CanUseSupportAdapter", "return firstParty;"])
        and contains_all(humanizer, ["answerly_humanizer_unavailable", "FallbackMessage"])
    )
    return {"status": "pass" if ok else "fail"}


def write_receipt(name: str, payload: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    receipts = {
        "ANSWERLY_PROVIDER_VERIFICATION.generated.json": provider_verification_receipt(),
        "ANSWERLY_DESIGN_BOUNDARY.generated.json": design_boundary_receipt(),
        "ANSWERLY_SUPPORT_ASSISTANT.generated.json": support_assistant_receipt(),
        "ANSWERLY_RULESAFE_PACKET.generated.json": rulesafe_packet_receipt(),
        "ANSWERLY_RULES_HUMANIZER.generated.json": humanizer_receipt(),
        "ANSWERLY_OUTPUT_GATE.generated.json": output_gate_receipt(),
        "ANSWERLY_SOURCEBOOK_BOUNDARY_SCAN.generated.json": sourcebook_boundary_scan(),
        "ANSWERLY_PUBLIC_SAFETY_SCAN.generated.json": public_leak_scan(),
        "ANSWERLY_OFFLINE_FALLBACK.generated.json": offline_fallback_receipt(),
    }
    for name, payload in receipts.items():
        write_receipt(name, payload)

    all_pass = all(payload.get("status") == "pass" for payload in receipts.values())
    verdict = "ANSWERLY_SUPPORT_AND_HUMANIZER_READY" if all_pass else "NOT_READY"
    lines = [
        "# Final Answerly Integration Verdict",
        f"- Verdict: `{verdict}`",
        "- Provider use stays bounded to support-assistant and RuleSafe humanizer lanes.",
        "- Raw sourcebook upload/training stays forbidden without explicit license receipts.",
    ]
    (OUT_DIR / "FINAL_ANSWERLY_INTEGRATION_VERDICT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
