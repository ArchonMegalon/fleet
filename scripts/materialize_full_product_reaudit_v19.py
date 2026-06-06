#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path("/docker/chummercomplete")
FLEET_ROOT = Path("/docker/fleet")
OUT = ROOT / "_completion" / "full_product_reaudit_v19"
MEDIA_OUT = OUT / "live_media"
LIVE_BASE = "https://chummer.run"
RECRAWL_DATE = "20260605"
RECRAWL_MAX_AGE_HOURS = 24

CORE_PUBLISHED = ROOT / "chummer-core-engine" / ".codex-studio" / "published"
RUN_PUBLISHED = ROOT / "chummer.run-services" / ".codex-studio" / "published"
V18 = FLEET_ROOT / "_completion" / "full_product_reaudit_v18"
INTEGRATED_FLEET = ROOT / ".integrated" / "fleet" / "_completion"


def now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch(url: str) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "codex-v19-audit"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, response.read().decode("utf-8", "ignore")


def fetch_json(url: str) -> dict[str, Any]:
    _, body = fetch(url)
    return json.loads(body)


def text_only(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def has_token(text: str, *tokens: str) -> list[str]:
    lowered = text.lower()
    return [token for token in tokens if token.lower() in lowered]


def screenshot_live(route: str, target: Path) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    node_script = (
        "const { chromium } = require('playwright');"
        "(async()=>{"
        f"const browser=await chromium.launch({{headless:true}});"
        "const page=await browser.newPage({viewport:{width:1440,height:900}});"
        f"await page.goto('{LIVE_BASE}{route}',{{waitUntil:'networkidle'}});"
        f"await page.screenshot({{path:'{str(target)}',fullPage:true}});"
        "await browser.close();"
        "})().catch(err=>{console.error(err);process.exit(1);});"
    )
    result = subprocess.run(
        ["node", "-e", node_script],
        cwd=ROOT / "chummer.run-services",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return result.returncode == 0 and target.exists() and target.stat().st_size > 0


def copy_or_placeholder(source: Path, target: Path, placeholder: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        shutil.copyfile(source, target)
    else:
        write_text(target, placeholder)


@dataclass
class VerdictFile:
    source: Path
    target_name: str


def materialize_live_public_web_recrawl() -> dict[str, Any]:
    home_status, home_html = fetch(f"{LIVE_BASE}/")
    status_status, status_html = fetch(f"{LIVE_BASE}/status")
    downloads_status, downloads_html = fetch(f"{LIVE_BASE}/downloads")
    release_channel = fetch_json(f"{LIVE_BASE}/downloads/RELEASE_CHANNEL.generated.json")
    releases = fetch_json(f"{LIVE_BASE}/downloads/releases.json")

    home_text = text_only(home_html)
    status_text = text_only(status_html)
    downloads_text = text_only(downloads_html)

    build_match = re.search(r"run-\d{8}-\d{6}", status_text)
    bad_home = has_token(home_text, "mobile play shell preview", "preview posture", "review required")
    bad_status = has_token(
        status_text,
        "missing or stale",
        "not yet gold-ready",
        "review is required",
        "review-required",
        "preview publication",
        "preview channel",
        "current preview channel",
        "preview posture",
        "public archive preview",
        "still manual",
        "incomplete",
        "unavailable",
    )
    bad_downloads = has_token(
        downloads_text,
        "load demo runner",
        "demo runner",
        "preview channel",
        "public archive preview",
        "still manual",
        "archive package",
    )
    reasons: list[str] = []
    if bad_home:
        reasons.append("home_bad_tokens:" + ",".join(bad_home))
    if bad_status:
        reasons.append("status_bad_tokens:" + ",".join(bad_status))
    if bad_downloads:
        reasons.append("downloads_bad_tokens:" + ",".join(bad_downloads))

    release_channel_version = str(release_channel.get("version") or "").strip()
    releases_version = str(releases.get("version") or "").strip()
    build_id = build_match.group(0) if build_match else ""
    if not build_id:
        reasons.append("status_build_id_missing")
    elif release_channel_version and build_id != release_channel_version:
        reasons.append(f"status_build_mismatch:{build_id}!={release_channel_version}")
    if not release_channel_version:
        reasons.append("release_channel_version_missing")
    if not releases_version:
        reasons.append("releases_version_missing")
    elif release_channel_version and releases_version != release_channel_version:
        reasons.append(f"downloads_version_mismatch:{releases_version}!={release_channel_version}")
    if str(release_channel.get("rolloutState") or "") != "public_stable":
        reasons.append("release_channel_not_public_stable")
    if str(release_channel.get("supportabilityState") or "") != "gold_supported":
        reasons.append("release_channel_not_gold_supported")

    payload = {
        "generated_at_utc": now_utc(),
        "status": "pass" if not reasons else "fail",
        "base_url": LIVE_BASE,
        "durable_artifacts_required": True,
        "live_backed_required": True,
        "live_recrawl_required": True,
        "recrawl_max_age_hours": RECRAWL_MAX_AGE_HOURS,
        "recrawl_age_hours": 0,
        "pages": {
            "home": {
                "url": f"{LIVE_BASE}/",
                "status_code": home_status,
                "bad_tokens": bad_home,
                "text_excerpt": home_text[:800],
            },
            "status": {
                "url": f"{LIVE_BASE}/status",
                "status_code": status_status,
                "bad_tokens": bad_status,
                "build_id": build_id,
                "text_excerpt": status_text[:800],
            },
            "downloads": {
                "url": f"{LIVE_BASE}/downloads",
                "status_code": downloads_status,
                "bad_tokens": bad_downloads,
                "text_excerpt": downloads_text[:800],
            },
        },
        "release_truth": {
            "release_channel_version": release_channel_version,
            "releases_version": releases_version,
            "rollout_state": release_channel.get("rolloutState"),
            "supportability_state": release_channel.get("supportabilityState"),
            "downloads_count": len(releases.get("downloads", [])),
        },
        "reasons": reasons,
    }
    write_json(OUT / f"LIVE_PUBLIC_WEB_RECRAWL_{RECRAWL_DATE}.generated.json", payload)
    return payload


def materialize_rule_authority_minimum_coverage() -> dict[str, Any]:
    registries = {
        "SR4": load_json(CORE_PUBLISHED / "SR4_RULEFACT_REGISTRY.generated.json"),
        "SR5": load_json(CORE_PUBLISHED / "SR5_RULE_AUTHORITY_REGISTRY.generated.json"),
        "SR6": load_json(CORE_PUBLISHED / "SR6_RULEFACT_REGISTRY.generated.json"),
    }
    minimum_rulefacts = 10
    editions: dict[str, Any] = {}
    reasons: list[str] = []
    for edition, registry in registries.items():
        count = int(registry.get("rulefact_count") or len(registry.get("rulefacts", [])))
        current_verdict = str(registry.get("final_verdict") or "")
        ready_overclaim = current_verdict.endswith("_RULE_AUTHORITY_READY") and count < minimum_rulefacts
        status = "pass" if count >= minimum_rulefacts else "fail"
        if edition == "SR5" and count == 0:
            status = "fail"
        if status != "pass":
            reasons.append(f"{edition.lower()}_minimum_rulefacts_not_met:{count}<{minimum_rulefacts}")
        if ready_overclaim:
            reasons.append(f"{edition.lower()}_ready_overclaim")
        editions[edition] = {
            "status": status,
            "current_verdict": current_verdict,
            "minimum_rulefacts_required": minimum_rulefacts,
            "rulefact_count": count,
            "recommended_verdict": f"{edition}_RULE_AUTHORITY_SHAPE_READY" if count > 0 else "NOT_READY",
            "ready_overclaim": ready_overclaim,
        }
    payload = {
        "generated_at_utc": now_utc(),
        "status": "pass" if not reasons else "fail",
        "minimum_rulefacts_required": minimum_rulefacts,
        "editions": editions,
        "reasons": reasons,
    }
    write_json(OUT / "RULE_AUTHORITY_MINIMUM_COVERAGE.generated.json", payload)
    return payload


def materialize_classic_formport_no_generic_row_source() -> dict[str, Any]:
    bridge = ROOT / "chummer-presentation" / "Chummer.Avalonia" / "Controls" / "ClassicFormPorts" / "ClassicFormPortViewModelBridge.cs"
    host = ROOT / "chummer-presentation" / "Chummer.Avalonia" / "Controls" / "ClassicFormPortHostControl.axaml.cs"
    text = bridge.read_text(encoding="utf-8")
    host_text = host.read_text(encoding="utf-8")
    disallowed = {
        "reflect_rows_property": 'GetProperty("Rows")',
        "reflect_display_path": 'GetProperty("DisplayPath")',
        "reflect_display_value": 'GetProperty("DisplayValue")',
    }
    hits = {name: needle for name, needle in disallowed.items() if needle in text}
    typed_domain_model_present = "ClassicFormPortDomainModel domain = state.DomainModel;" in text and "ClassicFormPortDomainModel.CreateFromRows(state.Rows);" in host_text
    payload = {
        "generated_at_utc": now_utc(),
        "status": "pass" if not hits and typed_domain_model_present else "fail",
        "bridge_path": str(bridge),
        "host_path": str(host),
        "typed_domain_model_required": True,
        "typed_domain_model_present": typed_domain_model_present,
        "generic_row_source_forbidden": True,
        "generic_row_source_hits": hits,
        "reason": "Classic FormPort bridge must consume typed domain payloads and command handlers, not reflect Rows/DisplayPath/DisplayValue and classify them heuristically.",
    }
    write_json(OUT / "CLASSIC_FORMPORT_NO_GENERIC_ROW_SOURCE.generated.json", payload)
    return payload


def materialize_black_ledger_live_media_proof() -> dict[str, Any]:
    MEDIA_OUT.mkdir(parents=True, exist_ok=True)
    screenshots = {
        "ledger": MEDIA_OUT / "black_ledger_live_ledger.png",
        "faction": MEDIA_OUT / "black_ledger_live_faction_ashline.png",
        "newsroom": MEDIA_OUT / "black_ledger_live_newsroom_turn1.png",
    }
    capture_results = {
        "ledger": screenshot_live("/ledger", screenshots["ledger"]),
        "faction": screenshot_live("/ledger/factions/ashline-circle", screenshots["faction"]),
        "newsroom": screenshot_live("/ledger/newsroom/turn-1-newsreel", screenshots["newsroom"]),
    }

    _, ledger_html = fetch(f"{LIVE_BASE}/ledger")
    _, newsroom_html = fetch(f"{LIVE_BASE}/ledger/newsroom/turn-1-newsreel")
    promo = fetch_json(f"{LIVE_BASE}/ledger/factions/ashline-circle/promo.json")
    faction_asset_url = f"{LIVE_BASE}/media/ledger/factions/ashline-circle-promo.mp4"
    newsreel_asset_url = f"{LIVE_BASE}/media/ledger/newsreels/turn-1-newsreel.mp4"
    faction_asset_status, _ = fetch(faction_asset_url)
    newsreel_asset_status, _ = fetch(newsreel_asset_url)

    ledger_text = text_only(ledger_html)
    newsroom_text = text_only(newsroom_html)
    title_match = re.search(r"<title>(.*?)</title>", newsroom_html, re.IGNORECASE | re.DOTALL)
    page_title_match = re.search(r'<h1 class="page-title">(.*?)</h1>', newsroom_html, re.IGNORECASE | re.DOTALL)
    eyebrow_match = re.search(r'<p class="eyebrow">(.*?)</p>', newsroom_html, re.IGNORECASE | re.DOTALL)
    newsroom_title = text_only(title_match.group(1)) if title_match else ""
    newsroom_page_title = text_only(page_title_match.group(1)) if page_title_match else ""
    newsroom_eyebrow = text_only(eyebrow_match.group(1)) if eyebrow_match else ""
    reasons: list[str] = []
    if "<video" not in ledger_html.lower():
        reasons.append("ledger_video_tag_missing")
    if "globe" not in ledger_text.lower():
        reasons.append("ledger_globe_language_missing")
    if promo.get("provider_status") != "VERIFIED_PROVIDER":
        reasons.append("faction_provider_not_verified")
    if str(promo.get("render_mode") or "") != "magicfit_cinematic_faction_promo_with_narration":
        reasons.append("faction_render_mode_not_magicfit_cinematic")
    if faction_asset_status != 200:
        reasons.append("faction_mp4_not_live")
    if newsreel_asset_status != 200:
        reasons.append("newsreel_mp4_not_live")
    title_reads_command_map = "command map" in newsroom_title.lower() or "command map" in newsroom_page_title.lower()
    newsroom_identity_present = "newsroom" in newsroom_title.lower() or "newsroom" in newsroom_eyebrow.lower()
    if title_reads_command_map:
        reasons.append("newsroom_route_still_reads_as_command_map")
    if not newsroom_identity_present:
        reasons.append("newsroom_identity_missing")
    if not all(capture_results.values()):
        reasons.append("live_screenshot_capture_incomplete")

    payload = {
        "generated_at_utc": now_utc(),
        "status": "pass" if not reasons else "fail",
        "base_url": LIVE_BASE,
        "globe": {
            "route": f"{LIVE_BASE}/ledger",
            "video_tag_present": "<video" in ledger_html.lower(),
            "globe_language_present": "globe" in ledger_text.lower(),
            "screenshot_path": str(screenshots["ledger"]),
            "screenshot_captured": capture_results["ledger"],
        },
        "faction_video": {
            "route": f"{LIVE_BASE}/ledger/factions/ashline-circle",
            "promo_json": f"{LIVE_BASE}/ledger/factions/ashline-circle/promo.json",
            "provider_status": promo.get("provider_status"),
            "render_mode": promo.get("render_mode"),
            "asset_url": faction_asset_url,
            "asset_status_code": faction_asset_status,
            "screenshot_path": str(screenshots["faction"]),
            "screenshot_captured": capture_results["faction"],
        },
        "newsroom": {
            "route": f"{LIVE_BASE}/ledger/newsroom/turn-1-newsreel",
            "asset_url": newsreel_asset_url,
            "asset_status_code": newsreel_asset_status,
            "title_text": newsroom_title,
            "page_title_text": newsroom_page_title,
            "eyebrow_text": newsroom_eyebrow,
            "title_reads_command_map": title_reads_command_map,
            "newsroom_identity_present": newsroom_identity_present,
            "screenshot_path": str(screenshots["newsroom"]),
            "screenshot_captured": capture_results["newsroom"],
        },
        "reasons": reasons,
    }
    write_json(OUT / "BLACK_LEDGER_LIVE_MEDIA_PROOF.generated.json", payload)
    return payload


def materialize_table_pulse_scenario_replay() -> dict[str, Any]:
    scenario = load_json(RUN_PUBLISHED / "PWA_TABLE_PULSE_SCENARIO_RECEIPTS.generated.json")
    minigame = load_json(V18 / "REMOTE_REACTION_MINIGAME.generated.json")
    adjudication = load_json(V18 / "GM_REMOTE_REACTION_ADJUDICATION.generated.json")
    required_steps = [
        "heat-event",
        "opt-in-policy",
        "remote-notification",
        "remote-choice",
        "gm-adjudication",
        "state-update",
        "receipt",
    ]
    covered = {
        "heat-event": any(item.get("id") == "table_pulse_remote_reaction_gm_adjudication" for item in scenario.get("scenarios", [])),
        "opt-in-policy": any("opt-in" in item.get("steps", []) for item in scenario.get("scenarios", [])),
        "remote-notification": bool(minigame.get("remote_users_notified")),
        "remote-choice": bool(minigame.get("clicked_action")),
        "gm-adjudication": adjudication.get("adjudication_status") == "pass",
        "state-update": adjudication.get("service_receipt_states") is True,
        "receipt": adjudication.get("receipt_status") == "pass",
    }
    reasons = [step for step in required_steps if not covered.get(step)]
    payload = {
        "generated_at_utc": now_utc(),
        "status": "pass" if not reasons else "fail",
        "required_steps": required_steps,
        "covered_steps": covered,
        "source_receipts": {
            "scenario_receipts": str(RUN_PUBLISHED / "PWA_TABLE_PULSE_SCENARIO_RECEIPTS.generated.json"),
            "remote_reaction_minigame": str(V18 / "REMOTE_REACTION_MINIGAME.generated.json"),
            "gm_remote_reaction_adjudication": str(V18 / "GM_REMOTE_REACTION_ADJUDICATION.generated.json"),
        },
        "reasons": reasons,
    }
    write_json(OUT / "TABLE_PULSE_SCENARIO_REPLAY.generated.json", payload)
    return payload


def materialize_external_verdicts() -> dict[str, str]:
    scripts = {
        "payfunnels": ROOT / "chummer.run-services" / "scripts" / "final_payfunnels_test_billing_verdict.py",
        "prompt_architects": ROOT / "chummer.run-services" / "scripts" / "final_prompt_architects_integration_verdict.py",
        "gm_session": ROOT / "chummer.run-services" / "scripts" / "final_gm_session_video_foundry_verdict.py",
        "fliplink": FLEET_ROOT / "scripts" / "materialize_fliplink_document_portal.py",
    }
    for script in scripts.values():
        subprocess.run(["python3", str(script)], cwd=ROOT, check=True)

    sources = {
        "FINAL_PAYFUNNELS_TEST_BILLING_ADAPTER_VERDICT.md": INTEGRATED_FLEET / "payfunnels" / "FINAL_PAYFUNNELS_TEST_BILLING_ADAPTER_VERDICT.md",
        "FINAL_PROMPT_ARCHITECTS_INTEGRATION_VERDICT.md": INTEGRATED_FLEET / "prompt_architects" / "FINAL_PROMPT_ARCHITECTS_INTEGRATION_VERDICT.md",
        "FINAL_GM_SESSION_VIDEO_FOUNDRY_VERDICT.md": INTEGRATED_FLEET / "magicfit_session" / "FINAL_GM_SESSION_VIDEO_FOUNDRY_VERDICT.md",
        "FINAL_FLIPLINK_DOCUMENT_PORTAL_VERDICT.md": FLEET_ROOT / "_completion" / "fliplink" / "FINAL_FLIPLINK_DOCUMENT_PORTAL_VERDICT.md",
    }
    copied: dict[str, str] = {}
    for name, source in sources.items():
        target = OUT / name
        copy_or_placeholder(source, target, "NOT_READY\n")
        copied[name] = target.read_text(encoding="utf-8").strip().splitlines()[0]
    return copied


def materialize_hard_requirements(
    recrawl: dict[str, Any],
    rules: dict[str, Any],
    formport: dict[str, Any],
    black_ledger: dict[str, Any],
    table_pulse: dict[str, Any],
    copied_verdicts: dict[str, str],
) -> dict[str, Any]:
    gates = {
        "live_public_web_recrawl": recrawl.get("status") == "pass",
        "rule_authority_minimum_coverage": rules.get("status") == "pass",
        "classic_formport_no_generic_row_source": formport.get("status") == "pass",
        "payfunnels": "PAYFUNNELS_TEST_BILLING_ADAPTER_READY" in (OUT / "FINAL_PAYFUNNELS_TEST_BILLING_ADAPTER_VERDICT.md").read_text(encoding="utf-8"),
        "prompt_architects": "PROMPT_ARCHITECTS_INTEGRATION_READY" in (OUT / "FINAL_PROMPT_ARCHITECTS_INTEGRATION_VERDICT.md").read_text(encoding="utf-8"),
        "gm_session_video_foundry": "GM_SESSION_VIDEO_FOUNDRY_READY" in (OUT / "FINAL_GM_SESSION_VIDEO_FOUNDRY_VERDICT.md").read_text(encoding="utf-8"),
        "fliplink_document_portal": "FLIPLINK_DOCUMENT_PORTAL_READY" in (OUT / "FINAL_FLIPLINK_DOCUMENT_PORTAL_VERDICT.md").read_text(encoding="utf-8"),
        "black_ledger_live_media_proof": black_ledger.get("status") == "pass",
        "table_pulse_scenario_replay": table_pulse.get("status") == "pass",
    }
    reasons = [name for name, passed in gates.items() if not passed]
    payload = {
        "generated_at_utc": now_utc(),
        "status": "pass" if not reasons else "fail",
        "durable_artifacts_required": True,
        "live_backed_required": True,
        "live_recrawl_required": True,
        "recrawl_max_age_hours": RECRAWL_MAX_AGE_HOURS,
        "gates": gates,
        "reasons": reasons,
    }
    write_json(OUT / "FINAL_GOLD_JANITOR_HARD_REQUIREMENTS.generated.json", payload)
    return payload


def materialize_final_verdict(hard: dict[str, Any]) -> str:
    verdict = "GOLD_READY" if hard.get("status") == "pass" else "NOT_GOLD"
    body = [verdict]
    if verdict != "GOLD_READY":
        body.extend(
            [
                "",
                "Blocking gates:",
                *[f"- {reason}" for reason in hard.get("reasons", [])],
            ]
        )
    write_text(OUT / "FINAL_GOLD_VERDICT.md", "\n".join(body))
    return verdict


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    recrawl = materialize_live_public_web_recrawl()
    rules = materialize_rule_authority_minimum_coverage()
    formport = materialize_classic_formport_no_generic_row_source()
    copied_verdicts = materialize_external_verdicts()
    black_ledger = materialize_black_ledger_live_media_proof()
    table_pulse = materialize_table_pulse_scenario_replay()
    hard = materialize_hard_requirements(recrawl, rules, formport, black_ledger, table_pulse, copied_verdicts)
    verdict = materialize_final_verdict(hard)
    print(verdict)
    return 0 if verdict == "GOLD_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
