#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.request
from pathlib import Path

from rafter_pixefy_common import COMPLETION, now_utc, write_json


ROOT = Path(__file__).resolve().parents[1]
V18 = ROOT / "_completion" / "full_product_reaudit_v18"
MANIFEST = V18 / "FULL_ESTATE_DURABLE_ARTIFACT_MANIFEST.generated.json"
BASE_URL = "https://chummer.run"
LIVE_RECHECK_ROUTES = [
    "/",
    "/downloads",
    "/status",
    "/ledger",
    "/ledger/map",
    "/ledger/factions",
    "/ledger/newsroom",
    "/play",
    "/mobile",
    "/help",
    "/feedback",
    "/artifacts",
]
FORBIDDEN_LIVE_TOKENS = {
    "/downloads": ("load demo runner", "demo runner"),
    "/status": ("review-required", "not gold", "not-gold", "incomplete", "unavailable", "stale"),
}

REQUIRED_GATES = {
    "LIVE_BACKED_RELEASE_TRUTH_MATRIX.generated.json": "json_pass",
    "LIVE_STATUS_RELEASE_ALIGNMENT.generated.json": "json_pass",
    "LIVE_CHUMMER_RUN_ROUTE_PROOF.generated.json": "json_pass",
    "CLASSIC_FORMPORT_FUNCTIONAL_PARITY_AUDIT.generated.json": "json_pass",
    "FINAL_SR4_RULE_AUTHORITY_VERDICT.md": "SR4_RULE_AUTHORITY_READY",
    "FINAL_SR5_RULE_AUTHORITY_VERDICT.md": "SR5_RULE_AUTHORITY_READY",
    "FINAL_SR6_RULE_AUTHORITY_VERDICT.md": "SR6_RULE_AUTHORITY_READY",
    "FINAL_MAGICFIT_PROVIDER_ADAPTER_VERDICT.md": "MAGICFIT_PROVIDER_ADAPTER_READY",
    "FINAL_RAFTER_PIXEFY_QA_STACK_VERDICT.md": "RAFTER_PIXEFY_QA_STACK_READY",
    "FINAL_BLACK_LEDGER_VIDEO_GLOBE_VERDICT.md": "BLACK_LEDGER_VIDEO_GLOBE_READY",
    "FINAL_FACTION_VIDEO_SERIES_VERDICT.md": "FACTION_VIDEO_SERIES_READY",
    "FINAL_BLACK_LEDGER_NEWSROOM_VERDICT.md": "BLACK_LEDGER_NEWSROOM_READY",
    "FINAL_PWA_GOLD_VERDICT.md": "GOLD_READY",
    "FINAL_TABLE_PULSE_OPTOUT_REMOTE_REACTION_VERDICT.md": "GOLD_READY",
}


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def has_forbidden_absolute_root(path_text: str) -> bool:
    forbidden = ("/docker/", "/tmp/", "/mnt/", "/home/", "C:\\")
    return path_text.startswith(forbidden)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_status(path: Path) -> str:
    if not path.is_file():
        return "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "invalid_json"
    return str(payload.get("status") or "missing")


def text_only(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def fetch_live(path: str) -> dict[str, object]:
    url = BASE_URL + path
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "chummer-v19-final-gold-janitor/1.0",
                "Accept": "text/html,application/xhtml+xml,application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(750_000)
        text = text_only(body.decode("utf-8", "ignore"))
        lowered = text.lower()
        hits = [token for token in FORBIDDEN_LIVE_TOKENS.get(path, ()) if token in lowered]
        return {
            "path": path,
            "url": url,
            "status_code": int(response.status),
            "ok": 200 <= int(response.status) < 400,
            "response_sha256": hashlib.sha256(body).hexdigest(),
            "body_bytes_sampled": len(body),
            "forbidden_hits": hits,
            "excerpt": text[:360],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "path": path,
            "url": url,
            "status_code": None,
            "ok": False,
            "response_sha256": "",
            "body_bytes_sampled": 0,
            "forbidden_hits": [],
            "error": f"{type(exc).__name__}: {exc}",
            "excerpt": "",
        }


def live_recheck() -> tuple[list[str], dict[str, object]]:
    routes = [fetch_live(path) for path in LIVE_RECHECK_ROUTES]
    reasons: list[str] = []
    for row in routes:
        if not row.get("ok"):
            reasons.append(f"live_route_failed:{row.get('path')}")
        for token in row.get("forbidden_hits", []):
            reasons.append(f"live_forbidden_copy:{row.get('path')}:{token}")

    proof_path = V18 / "LIVE_CHUMMER_RUN_ROUTE_PROOF.generated.json"
    if proof_path.is_file():
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        proof_routes = {
            str(item.get("path") or ""): item
            for item in proof.get("routes", [])
            if isinstance(item, dict)
        }
        for row in routes:
            stored = proof_routes.get(str(row.get("path")))
            if stored is None:
                reasons.append(f"live_route_missing_from_proof:{row.get('path')}")
                continue
            if not stored.get("response_sha256"):
                reasons.append(f"live_route_proof_missing_hash:{row.get('path')}")
    else:
        reasons.append("live_route_proof_missing")

    return reasons, {
        "base_url": BASE_URL,
        "route_count": len(routes),
        "status": "pass" if not reasons else "fail",
        "routes": routes,
    }


def gate_pass(path: Path, expected: str) -> bool:
    if expected == "json_pass":
        return read_json_status(path) == "pass"
    return path.is_file() and expected in path.read_text(encoding="utf-8")


def git_tracked(path: Path) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel(path)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-durable-artifacts", action="store_true")
    parser.add_argument("--live-backed", action="store_true")
    parser.add_argument("--allow-local-dry-run", action="store_true")
    args = parser.parse_args()

    manifest_payload: dict[str, object] = {}
    if MANIFEST.is_file():
        manifest_payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest_by_name = {
        str(item.get("name") or ""): item
        for item in manifest_payload.get("artifacts", [])
        if isinstance(item, dict)
    }

    gate_results: dict[str, dict[str, object]] = {}
    for name, expected in REQUIRED_GATES.items():
        path = V18 / name
        manifest_item = manifest_by_name.get(name, {})
        path_text = str(manifest_item.get("path") or rel(path))
        path_forbidden = has_forbidden_absolute_root(path_text)
        result = {
            "required": True,
            "path": path_text,
            "expected": expected,
            "exists": path.is_file(),
            "tracked": git_tracked(path),
            "status": read_json_status(path) if expected == "json_pass" else ("present" if path.is_file() else "missing"),
            "sha256": sha256(path) if path.is_file() else "",
            "manifest_sha256": str(manifest_item.get("sha256") or ""),
            "forbidden_absolute_path": path_forbidden,
            "pass": gate_pass(path, expected),
        }
        if args.require_durable_artifacts:
            result["pass"] = bool(
                result["pass"]
                and result["tracked"]
                and not path_forbidden
                and result["sha256"]
                and result["sha256"] == result["manifest_sha256"]
            )
        gate_results[name] = result

    missing = [name for name, result in gate_results.items() if not result["exists"]]
    untracked = [name for name, result in gate_results.items() if args.require_durable_artifacts and not result["tracked"]]
    bad_paths = [name for name, result in gate_results.items() if result.get("forbidden_absolute_path")]
    bad_sha = [
        name
        for name, result in gate_results.items()
        if args.require_durable_artifacts and result.get("exists") and result.get("sha256") != result.get("manifest_sha256")
    ]
    failing = [name for name, result in gate_results.items() if result["exists"] and not result["pass"] and name not in untracked]
    reasons = [f"missing:{name}" for name in missing]
    reasons += [f"not_durable:{name}" for name in untracked]
    reasons += [f"local_absolute_path:{name}" for name in bad_paths]
    reasons += [f"sha256_mismatch:{name}" for name in bad_sha]
    reasons += [f"failing:{name}" for name in failing]
    if args.live_backed and manifest_payload.get("live_backed") is not True:
        reasons.append("manifest_not_live_backed")
    live_recheck_payload: dict[str, object] = {"status": "skipped"}
    if args.live_backed:
        live_reasons, live_recheck_payload = live_recheck()
        reasons += live_reasons
    final = "GOLD_READY" if not reasons else "NOT_GOLD"
    if args.allow_local_dry_run and final == "GOLD_READY":
        reasons.append("local_dry_run_cannot_write_gold")
        final = "NOT_GOLD"

    output = {
        "generated_at_utc": now_utc(),
        "status": "pass" if final == "GOLD_READY" else "fail",
        "verdict": final,
        "scope": "full_estate_v18",
        "artifact_root": rel(V18),
        "artifact_manifest": rel(MANIFEST),
        "durable_artifacts_required": bool(args.require_durable_artifacts),
        "live_backed_required": bool(args.live_backed),
        "live_recheck": live_recheck_payload,
        "required_gates": gate_results,
        "missing_gates": missing,
        "untracked_gates": untracked,
        "local_absolute_path_gates": bad_paths,
        "sha256_mismatch_gates": bad_sha,
        "failing_gates": failing,
        "reasons": reasons,
    }
    write_json(COMPLETION / "FINAL_GOLD_JANITOR.generated.json", output)
    write_json(V18 / "FINAL_GOLD_JANITOR.generated.json", output)
    (V18 / "FINAL_GOLD_VERDICT.md").write_text(final + "\n", encoding="utf-8")
    print(final)
    return 0 if final == "GOLD_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
