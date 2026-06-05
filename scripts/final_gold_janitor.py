#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import requests

from rafter_pixefy_common import COMPLETION, now_utc, write_json


ROOT = Path(__file__).resolve().parents[1]
V18 = ROOT / "_completion" / "full_product_reaudit_v18"
MANIFEST = V18 / "FULL_ESTATE_DURABLE_ARTIFACT_MANIFEST.generated.json"

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

LIVE_BASE = "https://chummer.run"
LIVE_ROUTES = ["/", "/downloads", "/status", "/ledger", "/ledger/map", "/ledger/factions", "/ledger/newsroom"]
RELEASE_CHANNEL_PATH = "/downloads/RELEASE_CHANNEL.generated.json"
RELEASES_PATH = "/downloads/releases.json"
LIVE_STATUS_BAD_TOKENS = [
    "missing or stale",
    "not yet gold-ready",
    "review is required",
    "preview publication",
    "preview channel",
    "current preview channel",
    "preview posture",
    "public archive preview",
    "still manual",
]
LIVE_DOWNLOADS_BAD_TOKENS = [
    "load demo runner",
    "demo runner",
    "preview channel",
    "public archive preview",
    "still manual",
    "archive package",
]


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


def text_only(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def recrawl_live() -> dict[str, object]:
    routes: list[dict[str, object]] = []
    reasons: list[str] = []
    home_text = ""
    status_text = ""
    downloads_text = ""
    for path in LIVE_ROUTES:
        url = LIVE_BASE + path
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            text = text_only(response.text)
            lowered = text.lower()
            if path == "/":
                home_text = lowered
            elif path == "/status":
                status_text = lowered
            elif path == "/downloads":
                downloads_text = lowered
            detection_hits = [
                token
                for token in [
                    *LIVE_DOWNLOADS_BAD_TOKENS,
                    *LIVE_STATUS_BAD_TOKENS,
                    "mobile play shell preview",
                ]
                if token in lowered
            ]
            routes.append(
                {
                    "path": path,
                    "url": url,
                    "status_code": response.status_code,
                    "response_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "detection_hits": detection_hits,
                    "text_excerpt": " ".join(text.split())[:280],
                }
            )
        except Exception as exc:  # pragma: no cover - network failure path
            routes.append({"path": path, "url": url, "error": str(exc)})
            reasons.append(f"live_fetch_failed:{path}")
    if home_text:
        home_focus = home_text[:2200]
        home_hits = [token for token in ["mobile play shell preview", "preview"] if token in home_focus]
        if home_hits:
            reasons.append("home_caution_hits:" + ",".join(home_hits))
        if "black ledger" not in home_focus or "faction" not in home_focus:
            reasons.append("home_not_black_ledger_first")
    if downloads_text:
        downloads_hits = [token for token in LIVE_DOWNLOADS_BAD_TOKENS if token in downloads_text]
        if downloads_hits:
            reasons.append("downloads_caution:" + ",".join(downloads_hits))
    if status_text:
        status_hits = [token for token in LIVE_STATUS_BAD_TOKENS if token in status_text]
        if status_hits:
            reasons.append("status_caution:" + ",".join(status_hits))
        build_match = re.search(r"run-\d{8}-\d{6}", status_text)
        if not build_match:
            reasons.append("status_build_id_missing")
        try:
            release_channel = requests.get(LIVE_BASE + RELEASE_CHANNEL_PATH, timeout=20).json()
            releases = requests.get(LIVE_BASE + RELEASES_PATH, timeout=20).json()
            release_channel_version = str(release_channel.get("version") or "").strip()
            releases_version = str(releases.get("version") or "").strip()
            if not release_channel_version:
                reasons.append("release_channel_version_missing")
            elif build_match and build_match.group(0) != release_channel_version:
                reasons.append(f"status_build_mismatch:{build_match.group(0)}!={release_channel_version}")
            if not releases_version:
                reasons.append("releases_version_missing")
            elif release_channel_version and releases_version != release_channel_version:
                reasons.append(f"downloads_version_mismatch:{releases_version}!={release_channel_version}")
            if str(release_channel.get("rolloutState") or "").strip() != "public_stable":
                reasons.append("release_channel_not_public_stable")
            if str(release_channel.get("supportabilityState") or "").strip() != "gold_supported":
                reasons.append("release_channel_not_gold_supported")
        except Exception as exc:  # pragma: no cover - network failure path
            reasons.append(f"live_release_json_fetch_failed:{type(exc).__name__}")
    return {"routes": routes, "reasons": reasons}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.set_defaults(require_durable_artifacts=True, live_backed=True, recrawl_live=True)
    parser.add_argument("--require-durable-artifacts", dest="require_durable_artifacts", action="store_true")
    parser.add_argument("--live-backed", dest="live_backed", action="store_true")
    parser.add_argument("--recrawl-live", dest="recrawl_live", action="store_true")
    parser.add_argument("--allow-non-durable-artifacts", dest="require_durable_artifacts", action="store_false")
    parser.add_argument("--allow-non-live-backed", dest="live_backed", action="store_false")
    parser.add_argument("--skip-live-recrawl", dest="recrawl_live", action="store_false")
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
    live_recrawl: dict[str, object] | None = None
    if args.live_backed and args.recrawl_live:
        live_recrawl = recrawl_live()
        reasons.extend(str(reason) for reason in live_recrawl["reasons"])
        matrix_path = V18 / "LIVE_BACKED_RELEASE_TRUTH_MATRIX.generated.json"
        route_path = V18 / "LIVE_CHUMMER_RUN_ROUTE_PROOF.generated.json"
        if matrix_path.is_file():
            matrix_payload = json.loads(matrix_path.read_text(encoding="utf-8"))
            generated_reasons = {str(reason) for reason in matrix_payload.get("reasons", [])}
            live_reasons = set(str(reason) for reason in live_recrawl["reasons"])
            if bool(matrix_payload.get("gold_claim_allowed")) != (not live_reasons):
                reasons.append("live_recrawl_matrix_mismatch")
            if generated_reasons != live_reasons:
                reasons.append("live_recrawl_matrix_reason_mismatch")
        if route_path.is_file():
            route_payload = json.loads(route_path.read_text(encoding="utf-8"))
            generated_by_path = {
                str(item.get("path")): str(item.get("response_sha256") or "")
                for item in route_payload.get("routes", [])
                if isinstance(item, dict)
            }
            for item in live_recrawl["routes"]:
                if not isinstance(item, dict):
                    continue
                path = str(item.get("path") or "")
                response_sha = str(item.get("response_sha256") or "")
                if response_sha and generated_by_path.get(path) and generated_by_path.get(path) != response_sha:
                    reasons.append(f"live_recrawl_route_hash_mismatch:{path}")
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
        "live_recrawl_required": bool(args.live_backed and args.recrawl_live),
        "required_gates": gate_results,
        "missing_gates": missing,
        "untracked_gates": untracked,
        "local_absolute_path_gates": bad_paths,
        "sha256_mismatch_gates": bad_sha,
        "failing_gates": failing,
        "live_recrawl": live_recrawl,
        "reasons": reasons,
    }
    write_json(COMPLETION / "FINAL_GOLD_JANITOR.generated.json", output)
    write_json(V18 / "FINAL_GOLD_JANITOR.generated.json", output)
    (V18 / "FINAL_GOLD_VERDICT.md").write_text(final + "\n", encoding="utf-8")
    print(final)
    return 0 if final == "GOLD_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
