#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

from rafter_pixefy_common import COMPLETION, now_utc, write_json


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_NAME = "chummer.final_gold_janitor"
JANITOR_ARTIFACT_NAME = "FINAL_GOLD_JANITOR.generated.json"
DEFAULT_REAUDIT_ROOT_NAME = os.environ.get("CHUMMER_FINAL_GOLD_ARTIFACT_ROOT", "full_product_reaudit_v20")


def _dedupe_paths(paths: list[Path]) -> tuple[Path, ...]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(resolved)
    return tuple(result)


def _completion_root_candidates() -> tuple[Path, ...]:
    configured = os.environ.get("CHUMMER_COMPLETION_ROOT")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    candidates.append(ROOT / "_completion")
    return _dedupe_paths(candidates)


def _read_selection_json_payload(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _is_modern_selection_janitor_payload(payload: dict[str, object]) -> bool:
    gates = payload.get("required_gates")
    return (
        str(payload.get("contract_name") or "") == CONTRACT_NAME
        and isinstance(gates, dict)
        and bool(gates)
    )


def _latest_reaudit_dir() -> Path:
    pattern = re.compile(r"full_product_reaudit_v(\d+)$")
    eligible: list[tuple[int, int, int, int, float, int, Path]] = []
    fallback: list[tuple[int, float, int, Path]] = []
    for root_index, completion_root in enumerate(_completion_root_candidates()):
        if not completion_root.is_dir():
            continue
        for child in completion_root.iterdir():
            if not child.is_dir():
                continue
            match = pattern.match(child.name)
            if not match:
                continue
            resolved = child.resolve()
            version = int(match.group(1))
            try:
                mtime = max(
                    (candidate.stat().st_mtime for candidate in resolved.iterdir() if candidate.is_file()),
                    default=0.0,
                )
            except OSError:
                mtime = 0.0
            fallback.append((version, mtime, -root_index, resolved))
            janitor_payload = _read_selection_json_payload(resolved / JANITOR_ARTIFACT_NAME)
            gates = janitor_payload.get("required_gates")
            gate_count = len(gates) if isinstance(gates, dict) else 0
            modern_contract = int(_is_modern_selection_janitor_payload(janitor_payload))
            has_manifest = int((resolved / "FULL_ESTATE_DURABLE_ARTIFACT_MANIFEST.generated.json").is_file())
            if (
                (resolved / "FULL_ESTATE_DURABLE_ARTIFACT_MANIFEST.generated.json").is_file()
                or (resolved / JANITOR_ARTIFACT_NAME).is_file()
            ):
                eligible.append((version, modern_contract, has_manifest, gate_count, mtime, -root_index, resolved))
    if eligible:
        return max(eligible, key=lambda item: item[:-1])[-1]
    if fallback:
        return max(fallback, key=lambda item: item[:-1])[-1]
    return ROOT / "_completion" / DEFAULT_REAUDIT_ROOT_NAME


REAUDIT = _latest_reaudit_dir()
MANIFEST = REAUDIT / "FULL_ESTATE_DURABLE_ARTIFACT_MANIFEST.generated.json"
SOURCE_JANITOR = REAUDIT / JANITOR_ARTIFACT_NAME

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
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT.resolve()))
    except ValueError:
        return str(resolved)


def has_forbidden_absolute_root(path_text: str) -> bool:
    forbidden = ("/docker/", "/tmp/", "/mnt/", "/home/", "C:\\")
    return path_text.startswith(forbidden)


def read_json_payload(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def reaudit_version(path: Path) -> int | None:
    match = re.match(r"full_product_reaudit_v(\d+)$", path.name)
    return int(match.group(1)) if match else None


def reaudit_is_local() -> bool:
    try:
        REAUDIT.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return False
    return True


def is_modern_janitor_payload(payload: dict[str, object]) -> bool:
    gates = payload.get("required_gates")
    return (
        str(payload.get("contract_name") or "") == CONTRACT_NAME
        and isinstance(gates, dict)
        and bool(gates)
    )


def parse_utc(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def utc_now() -> datetime:
    parsed = parse_utc(now_utc())
    return parsed or datetime.now(timezone.utc).replace(microsecond=0)


def age_hours(generated_at_utc: object, *, now: datetime | None = None) -> float | None:
    generated = parse_utc(generated_at_utc)
    if generated is None:
        return None
    reference = now or utc_now()
    return max(0.0, (reference - generated).total_seconds() / 3600.0)


def modern_gate_pass(gate: object) -> bool:
    if not isinstance(gate, dict):
        return False
    if "pass" in gate:
        return gate.get("pass") is True
    return str(gate.get("status") or "").strip().lower() == "pass"


def modern_janitor_reasons(payload: dict[str, object], args: argparse.Namespace) -> list[str]:
    reasons: list[str] = []
    max_hours = payload.get("recrawl_max_age_hours")
    reference_now = utc_now()
    if str(payload.get("status") or "").strip().lower() != "pass":
        reasons.append("source_janitor_status_not_pass")
    if str(payload.get("verdict") or "").strip() != "GOLD_READY":
        reasons.append("source_janitor_not_gold_ready")
    if args.live_backed and args.recrawl_live and isinstance(max_hours, (int, float)):
        source_age = age_hours(payload.get("generated_at_utc"), now=reference_now)
        if source_age is None:
            reasons.append("source_janitor_generated_at_missing")
        elif source_age > float(max_hours):
            reasons.append("source_janitor_stale")
    gates = payload.get("required_gates")
    if not isinstance(gates, dict) or not gates:
        reasons.append("source_janitor_required_gates_missing")
        return reasons
    for name, gate in gates.items():
        if not modern_gate_pass(gate):
            reasons.append(f"failing:{name}")
    if args.require_durable_artifacts and payload.get("durable_artifacts_required") is not True:
        reasons.append("source_janitor_not_durable")
    if args.live_backed and payload.get("live_backed_required") is not True:
        reasons.append("source_janitor_not_live_backed")
    if args.live_backed and args.recrawl_live and payload.get("live_recrawl_required") is not True:
        reasons.append("source_janitor_not_live_recrawled")
    if args.live_backed and args.recrawl_live:
        live_gate = gates.get("live_public_web_recrawl")
        if not modern_gate_pass(live_gate):
            reasons.append("source_live_recrawl_not_pass")
        elif isinstance(live_gate, dict):
            fresh_hours = live_gate.get("fresh_within_hours")
            if isinstance(fresh_hours, (int, float)) and isinstance(max_hours, (int, float)):
                if fresh_hours > max_hours:
                    reasons.append("source_live_recrawl_stale")
            live_age = age_hours(live_gate.get("generated_at_utc"), now=reference_now)
            if live_age is None:
                reasons.append("source_live_recrawl_generated_at_missing")
            elif isinstance(max_hours, (int, float)) and live_age > float(max_hours):
                reasons.append("source_live_recrawl_generated_at_stale")
    return reasons


def modern_janitor_output(
    payload: dict[str, object],
    args: argparse.Namespace,
) -> tuple[dict[str, object], str]:
    reasons = modern_janitor_reasons(payload, args)
    final = "GOLD_READY" if not reasons else "NOT_GOLD"
    if args.allow_local_dry_run and final == "GOLD_READY":
        reasons.append("local_dry_run_cannot_write_gold")
        final = "NOT_GOLD"
    output = {
        "contract_name": CONTRACT_NAME,
        "generated_at_utc": now_utc(),
        "status": "pass" if final == "GOLD_READY" else "fail",
        "verdict": final,
        "scope": str(payload.get("scope") or f"full_estate_v{reaudit_version(REAUDIT) or 'current'}"),
        "artifact_root": str(payload.get("artifact_root") or rel(REAUDIT)),
        "artifact_manifest": rel(MANIFEST) if MANIFEST.is_file() else "",
        "source_artifact": rel(SOURCE_JANITOR),
        "modern_contract_source": True,
        "legacy_manifest_required": False,
        "durable_artifacts_required": bool(args.require_durable_artifacts),
        "live_backed_required": bool(args.live_backed),
        "live_recrawl_required": bool(args.live_backed and args.recrawl_live),
        "recrawl_max_age_hours": payload.get("recrawl_max_age_hours"),
        "required_gates": payload.get("required_gates") if isinstance(payload.get("required_gates"), dict) else {},
        "missing_gates": [],
        "untracked_gates": [],
        "local_absolute_path_gates": [],
        "sha256_mismatch_gates": [],
        "failing_gates": [reason.removeprefix("failing:") for reason in reasons if reason.startswith("failing:")],
        "live_recrawl": (
            dict(payload.get("required_gates", {}).get("live_public_web_recrawl") or {})
            if isinstance(payload.get("required_gates"), dict)
            else None
        ),
        "reasons": reasons,
    }
    return output, final


def write_final_janitor(output: dict[str, object], final: str) -> None:
    write_json(COMPLETION / JANITOR_ARTIFACT_NAME, output)
    if reaudit_is_local():
        write_json(SOURCE_JANITOR, output)
        (REAUDIT / "FINAL_GOLD_VERDICT.md").write_text(final + "\n", encoding="utf-8")


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
    resolved = path.resolve()
    try:
        rel_path = str(resolved.relative_to(ROOT.resolve()))
    except ValueError:
        return False
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel_path],
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

    source_janitor_payload = read_json_payload(SOURCE_JANITOR)
    if is_modern_janitor_payload(source_janitor_payload):
        output, final = modern_janitor_output(source_janitor_payload, args)
        write_final_janitor(output, final)
        print(final)
        return 0 if final == "GOLD_READY" else 1

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
        path = REAUDIT / name
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
        matrix_path = REAUDIT / "LIVE_BACKED_RELEASE_TRUTH_MATRIX.generated.json"
        route_path = REAUDIT / "LIVE_CHUMMER_RUN_ROUTE_PROOF.generated.json"
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
        "scope": f"full_estate_v{reaudit_version(REAUDIT) or 'legacy'}",
        "artifact_root": rel(REAUDIT),
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
    write_final_janitor(output, final)
    print(final)
    return 0 if final == "GOLD_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
