#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROADMAP_PATH = Path("/docker/chummercomplete/chummer-design/products/chummer/ROADMAP.md")
CONFIDENCE_GUIDE_PATH = Path("/docker/chummercomplete/chummer-design/products/chummer/CONFIDENCE_READINESS_AND_CONTINUITY_GUIDE.md")
LIVING_GUIDE_PATH = Path("/docker/chummercomplete/chummer-design/products/chummer/LIVING_CAMPAIGN_LOOP_MATERIALIZATION_GUIDE.md")
LOST_POTENTIAL_PATH = Path("/docker/chummercomplete/chummer-design/products/chummer/LOST_POTENTIAL_MATERIALIZATION_WAVE.md")
NEXT90_PATH = Path("/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml")
HUB_REGISTRY_PATH = Path("/docker/chummercomplete/chummer-design/products/chummer/projects/hub-registry.md")
MEDIA_FACTORY_PATH = Path("/docker/fleet/repos/chummer-media-factory/docs/chummer-media-factory.design.v1.md")
READINESS_PATH = Path("/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json")
STATE_PATH = Path("/docker/fleet/state/chummer_design_supervisor/state.json")
FRONTIER_PATH = Path("/docker/fleet/.codex-studio/published/FULL_PRODUCT_FRONTIER.generated.yaml")
UI_PARITY_PATH = Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published/CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json")
REPORT_JSON_PATH = Path("/docker/fleet/.codex-studio/published/CHUMMER6_PRODUCT_VISION_AUDIT.generated.json")
REPORT_MD_PATH = Path("/docker/fleet/.codex-studio/published/CHUMMER6_PRODUCT_VISION_AUDIT.generated.md")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _coverage_details(readiness: dict[str, Any], key: str) -> tuple[str, list[str]]:
    coverage = readiness.get("coverage") if isinstance(readiness.get("coverage"), dict) else {}
    coverage_details = readiness.get("coverage_details") if isinstance(readiness.get("coverage_details"), dict) else {}
    detail = coverage_details.get(key) if isinstance(coverage_details.get(key), dict) else {}
    status = str(coverage.get(key) or "").strip().lower()
    reasons = [str(item).strip() for item in (detail.get("reasons") or []) if str(item).strip()]
    return status, reasons


def _state_shards(state: dict[str, Any]) -> list[dict[str, Any]]:
    shards = state.get("shards")
    return [item for item in shards if isinstance(item, dict)] if isinstance(shards, list) else []


def _owner_shards(state: dict[str, Any], keywords: tuple[str, ...]) -> list[str]:
    matches: list[str] = []
    lowered_keywords = [str(item).lower() for item in keywords if str(item).strip()]
    if not lowered_keywords:
        return matches
    for shard in _state_shards(state):
        name = str(shard.get("name") or "").strip()
        focus_texts = [str(item).strip() for item in (shard.get("focus_texts") or []) if str(item).strip()]
        haystack = " | ".join(focus_texts).lower()
        if not name or not haystack:
            continue
        if any(keyword in haystack for keyword in lowered_keywords):
            matches.append(name)
    deduped: list[str] = []
    for item in matches:
        if item not in deduped:
            deduped.append(item)
    return deduped[:4]


def _open_frontier_ids(frontier: Any) -> list[int]:
    frontier_items = frontier.get("frontier") if isinstance(frontier, dict) else []
    if not isinstance(frontier_items, list):
        return []
    result: list[int] = []
    for item in frontier_items:
        if not isinstance(item, dict):
            continue
        value = item.get("id")
        if isinstance(value, int):
            result.append(value)
    return result


def _missing_frontier_ids(state: dict[str, Any], frontier: Any) -> list[int]:
    open_ids = {int(item) for item in (state.get("open_milestone_ids") or []) if isinstance(item, int)}
    return [item for item in _open_frontier_ids(frontier) if item not in open_ids]


def _finding(
    *,
    rank: int,
    severity: str,
    category: str,
    title: str,
    reason: str,
    user_impact: str,
    what_users_want_or_miss: list[str],
    owner_keywords: tuple[str, ...],
    milestone_area: str,
    evidence_paths: list[Path],
    workflow_gates: list[str],
    repo_grounded: bool,
    state: dict[str, Any],
) -> dict[str, Any]:
    return {
        "rank": rank,
        "severity": severity,
        "category": category,
        "repo_grounded": repo_grounded,
        "title": title,
        "reason": reason,
        "user_impact": user_impact,
        "what_users_want_or_miss": what_users_want_or_miss,
        "owner_shards": _owner_shards(state, owner_keywords),
        "milestone_area": milestone_area,
        "evidence_paths": [str(path) for path in evidence_paths],
        "workflow_gates": workflow_gates,
    }


def _integration_opportunity(
    *,
    rank: int,
    title: str,
    thesis: str,
    why_fit: str,
    owner_keywords: tuple[str, ...],
    evidence_paths: list[Path],
    repo_grounded: bool,
    state: dict[str, Any],
) -> dict[str, Any]:
    return {
        "rank": rank,
        "repo_grounded": repo_grounded,
        "title": title,
        "thesis": thesis,
        "why_fit": why_fit,
        "owner_shards": _owner_shards(state, owner_keywords),
        "evidence_paths": [str(path) for path in evidence_paths],
    }


def _write_report(report: dict[str, Any]) -> None:
    REPORT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON_PATH.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    findings = report.get("repo_grounded_findings") if isinstance(report.get("repo_grounded_findings"), list) else []
    opportunities = report.get("speculative_integration_opportunities") if isinstance(report.get("speculative_integration_opportunities"), list) else []
    user_wants = [str(item).strip() for item in (report.get("user_wants_or_misses") or []) if str(item).strip()]
    gate_recs = report.get("gate_recommendations") if isinstance(report.get("gate_recommendations"), list) else []
    notes = [str(item).strip() for item in (report.get("notes") or []) if str(item).strip()]

    lines: list[str] = [
        "# Chummer6 Product Vision Audit",
        "",
        f"- generated_at: {report.get('generated_at')}",
        f"- active_runs_count: {summary.get('active_runs_count')}",
        f"- productive_active_runs_count: {summary.get('productive_active_runs_count')}",
        f"- nonproductive_active_runs_count: {summary.get('nonproductive_active_runs_count')}",
        f"- remaining_open_milestones: {summary.get('remaining_open_milestones')}",
        f"- missing_frontier_ids: {summary.get('missing_frontier_ids')}",
        f"- ui_parity_visual_yes_no: {summary.get('visual_yes_count')}/{summary.get('visual_no_count')}",
        f"- ui_parity_behavioral_yes_no: {summary.get('behavioral_yes_count')}/{summary.get('behavioral_no_count')}",
        "",
        "## What Users Still Want Or Miss",
        "",
    ]
    for item in user_wants:
        lines.append(f"- {item}")

    lines.extend(["", "## Repo-Grounded Lost Potential Findings", ""])
    for item in findings:
        if not isinstance(item, dict):
            continue
        lines.append(f"### {item.get('rank')}. {item.get('title')}")
        lines.append("")
        lines.append(f"- severity: {item.get('severity')}")
        lines.append(f"- category: {item.get('category')}")
        lines.append(f"- owner_shards: {item.get('owner_shards')}")
        lines.append(f"- milestone_area: {item.get('milestone_area')}")
        lines.append(f"- reason: {item.get('reason')}")
        lines.append(f"- user_impact: {item.get('user_impact')}")
        lines.append(f"- users_want_or_miss: {item.get('what_users_want_or_miss')}")
        lines.append(f"- gates_to_close: {item.get('workflow_gates')}")
        lines.append(f"- evidence_paths: {item.get('evidence_paths')}")
        lines.append("")

    lines.extend(["## Integration Opportunities", ""])
    for item in opportunities:
        if not isinstance(item, dict):
            continue
        lines.append(f"### {item.get('rank')}. {item.get('title')}")
        lines.append("")
        lines.append(f"- repo_grounded: {item.get('repo_grounded')}")
        lines.append(f"- owner_shards: {item.get('owner_shards')}")
        lines.append(f"- thesis: {item.get('thesis')}")
        lines.append(f"- why_fit: {item.get('why_fit')}")
        lines.append(f"- evidence_paths: {item.get('evidence_paths')}")
        lines.append("")

    lines.extend(["## Gate Recommendations", ""])
    for item in gate_recs:
        if not isinstance(item, dict):
            continue
        lines.append(f"- {item.get('title')}: {item.get('reason')}")

    if notes:
        lines.extend(["", "## Notes", ""])
        for note in notes:
            lines.append(f"- {note}")

    REPORT_MD_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    roadmap_text = _load_text(ROADMAP_PATH)
    confidence_text = _load_text(CONFIDENCE_GUIDE_PATH)
    living_text = _load_text(LIVING_GUIDE_PATH)
    lost_potential_text = _load_text(LOST_POTENTIAL_PATH)
    next90_text = _load_text(NEXT90_PATH)
    hub_registry_text = _load_text(HUB_REGISTRY_PATH)
    media_factory_text = _load_text(MEDIA_FACTORY_PATH)
    readiness = _load_json(READINESS_PATH)
    state = _load_json(STATE_PATH)
    frontier = _load_yaml(FRONTIER_PATH)
    ui_parity = _load_json(UI_PARITY_PATH)

    parity_summary = ui_parity.get("summary") if isinstance(ui_parity.get("summary"), dict) else {}
    parity_findings = ui_parity.get("findings") if isinstance(ui_parity.get("findings"), list) else []
    visual_no_count = int(parity_summary.get("visual_no_count") or 0)
    behavioral_no_count = int(parity_summary.get("behavioral_no_count") or 0)
    coverage_gap_keys = [str(item).strip() for item in (parity_summary.get("coverage_gap_keys") or []) if str(item).strip()]
    missing_frontier_ids = _missing_frontier_ids(state, frontier)
    active_runs_count = int(state.get("active_runs_count") or 0)
    productive_active_runs_count = int(state.get("productive_active_runs_count") or 0)
    nonproductive_active_runs_count = int(state.get("nonproductive_active_runs_count") or 0)
    remaining_open_milestones = int(state.get("remaining_open_milestones") or 0)

    desktop_status, desktop_reasons = _coverage_details(readiness, "desktop_client")
    mobile_status, mobile_reasons = _coverage_details(readiness, "mobile_play_shell")
    polish_status, polish_reasons = _coverage_details(readiness, "ui_kit_and_flagship_polish")
    media_status, media_reasons = _coverage_details(readiness, "media_artifacts")

    repo_grounded_findings = [
        _finding(
            rank=1,
            severity="high",
            category="lost_potential",
            title="The campaign OS promise still does not land at the table in the moments the canon says should feel magical.",
            reason=(
                "The canon explicitly says Chummer should feel like an explainable campaign OS with action help, local rule anchors, "
                "campaign adoption, runner goals, prep packets, and BLACK LEDGER consequence loops, but those loops still sit in "
                "open readiness or successor-wave posture rather than feeling closed in flagship truth."
            ),
            user_impact=(
                "Players and GMs do not yet get the calm-under-pressure payoff: what can I do right now, why, and what changed because of the last run."
            ),
            what_users_want_or_miss=[
                "tell me what I can still do right now",
                "open the exact source or rule anchor without breaking flow",
                "adopt my existing campaign without rebuilding everything",
                "close a run and immediately see approved consequences",
            ],
            owner_keywords=("campaign", "continuity", "gm", "prep", "mobile", "dice", "initiative", "rule-environment"),
            milestone_area="Living campaign loop / lost-potential wave / mobile play shell",
            evidence_paths=[ROADMAP_PATH, CONFIDENCE_GUIDE_PATH, LIVING_GUIDE_PATH, LOST_POTENTIAL_PATH, NEXT90_PATH, READINESS_PATH],
            workflow_gates=[
                "live combat round with action budgets",
                "local source or rule anchor open",
                "existing campaign adoption",
                "runner goal update",
                "GM prep packet",
                "ResolutionReport to WorldTick to player-safe news",
            ],
            repo_grounded=True,
            state=state,
        ),
        _finding(
            rank=2,
            severity="high",
            category="visual_and_behavioral_parity",
            title="Veteran replacement still leaks on dense sub-workflows, so trust is broader than it is deep.",
            reason=(
                f"The current parity matrix is still visual {int(parity_summary.get('visual_yes_count') or 0)}/{visual_no_count} and "
                f"behavioral {int(parity_summary.get('behavioral_yes_count') or 0)}/{behavioral_no_count}, with open families around "
                "translator/XML, dense builder and career flows, dice and initiative, import oracles, Hero Lab, contacts, lifestyles, history, and print/export surfaces."
            ),
            user_impact=(
                "A veteran Chummer5A user can still hit moments where the flow is slower, less familiar, or less trusted than the old tool."
            ),
            what_users_want_or_miss=[
                "the same dense builder rhythm as Chummer5A",
                "fast import and migration rails",
                "trusted dice, initiative, and table utility moments",
                "full roster, contacts, lifestyles, and history comfort",
            ],
            owner_keywords=("xml", "translator", "import", "hero lab", "contacts", "dice", "initiative", "build lab", "chummer5a"),
            milestone_area="Chummer5A parity closure and veteran replacement",
            evidence_paths=[UI_PARITY_PATH, CONFIDENCE_GUIDE_PATH, ROADMAP_PATH],
            workflow_gates=[
                "translator route screenshot/runtime proof",
                "xml amendment editor screenshot/runtime proof",
                "dense builder and career workflow proof",
                "dice and initiative workflow proof",
                "contacts and lifestyles proof",
                "import oracles and Hero Lab proof",
            ],
            repo_grounded=True,
            state=state,
        ),
        _finding(
            rank=3,
            severity="high",
            category="trust_and_release_proof",
            title="The trust story is stronger in canon than in the executable proof shelf.",
            reason=(
                "The product canon emphasizes confidence, boring trust, and public proof shelf discipline, but desktop release closure still "
                "depends on stale or mismatched Windows startup-smoke proof and a still-open desktop-client readiness key."
            ),
            user_impact=(
                "Users may believe the product promise less at exactly the moments where they need confidence most: install, update, restore, and first-launch recovery."
            ),
            what_users_want_or_miss=[
                "a boring installer and update path",
                "honest proof that the promoted build actually launches",
                "confidence that recovery and restore really work",
            ],
            owner_keywords=("desktop-client", "release-proof", "install", "update", "recovery", "trust", "support"),
            milestone_area="Desktop release proof, installer truth, and restore confidence",
            evidence_paths=[READINESS_PATH, ROADMAP_PATH, CONFIDENCE_GUIDE_PATH],
            workflow_gates=[
                "Windows startup smoke against promoted bytes",
                "desktop executable exit gate",
                "release-channel and proof-shelf freshness",
            ],
            repo_grounded=True,
            state=state,
        ),
        _finding(
            rank=4,
            severity="medium",
            category="mobile_continuity",
            title="Mobile and companion continuity are still warnings even though the canon makes them part of the moat.",
            reason=(
                f"Readiness still carries `mobile_play_shell={mobile_status or 'unknown'}` while the canon says mobile should become the "
                "player and GM shell for table return, recap, continuity, and travel moments."
                + (f" Current leading reason: {mobile_reasons[0]}." if mobile_reasons else "")
            ),
            user_impact=(
                "The product is still strongest at the desk, not in the between-session and at-table moments that actually drive habit and return."
            ),
            what_users_want_or_miss=[
                "phone-safe recap and next-step continuity",
                "player-safe consequence feed",
                "offline or degraded-network companion moments",
            ],
            owner_keywords=("mobile", "offline", "companion", "continuity", "travel"),
            milestone_area="Mobile play shell and return-moment continuity",
            evidence_paths=[CONFIDENCE_GUIDE_PATH, ROADMAP_PATH, READINESS_PATH, NEXT90_PATH],
            workflow_gates=[
                "mobile recap and briefing continuity",
                "player-safe consequence feed",
                "travel and degraded-network companion views",
            ],
            repo_grounded=True,
            state=state,
        ),
        _finding(
            rank=5,
            severity="medium",
            category="horizon_integration",
            title="The horizon brands and community surfaces are named, but they are not yet woven back into the core product loop.",
            reason=(
                "The successor wave explicitly defines JACKPOINT, RUNBOOK PRESS, GHOSTWIRE, RUNSITE, TABLE PULSE, and Community Hub, "
                "but today they still read more like deferred horizons than like emotional extensions of build, play, campaign, recap, and trust."
            ),
            user_impact=(
                "Users miss the feeling that campaign artifacts, recaps, prep packets, route packs, and community moments belong to one coherent ecosystem."
            ),
            what_users_want_or_miss=[
                "shareable recap and publication artifacts",
                "community-safe open-run and roster formation loops",
                "route, travel, and observer moments tied to real campaign truth",
            ],
            owner_keywords=("exchange", "recap", "export", "pulse", "launch", "governance"),
            milestone_area="Media and social horizon tranche / artifact and community loop",
            evidence_paths=[ROADMAP_PATH, NEXT90_PATH, HUB_REGISTRY_PATH, MEDIA_FACTORY_PATH],
            workflow_gates=[
                "artifact studio and press workflow",
                "open runs and Community Hub formation",
                "route pack and travel continuity proof",
                "bounded table-pulse and replay surfaces",
            ],
            repo_grounded=True,
            state=state,
        ),
        _finding(
            rank=6,
            severity="medium",
            category="workflow_gate_discipline",
            title="The gating workflow still proves broad readiness more easily than the exact sub-flows that matter to humans.",
            reason=(
                "The repo now has real parity and readiness gates, but the remaining UI families are still unproven because those exact sub-dialogs "
                "and workflow moments are not all under direct screenshot/runtime contract yet."
            ),
            user_impact=(
                "A product manager or veteran tester can still feel that something is off even while the global readiness story looks healthier."
            ),
            what_users_want_or_miss=[
                "proof for the exact dialogs they actually use",
                "behavioral parity, not just route existence",
                "fewer places where visual drift hides behind aggregate green status",
            ],
            owner_keywords=("flagship-readiness", "materializer", "desktop-client", "feedback", "automatic bugfixing"),
            milestone_area="Journey gates, screenshot packs, runtime-backed parity contracts",
            evidence_paths=[UI_PARITY_PATH, READINESS_PATH, ROADMAP_PATH],
            workflow_gates=[
                "sub-dialog screenshot packs",
                "behavioral parity assertions for veteran flows",
                "proof-shelf freshness for promoted artifacts",
            ],
            repo_grounded=True,
            state=state,
        ),
    ]

    speculative_integration_opportunities = [
        _integration_opportunity(
            rank=1,
            title="Community scheduling or roster-formation LTD",
            thesis="An acquisition or deeper integration around scheduling, campaign-group movement, and community roster formation would slot cleanly into Open Runs and Community Hub.",
            why_fit="The canon already defines Open Runs, Community Hub, campaign-group movement, and organizer operations; what is missing is a truly great social and logistics layer around them.",
            owner_keywords=("event", "roster", "campaign", "launch", "governance"),
            evidence_paths=[NEXT90_PATH, CONFIDENCE_GUIDE_PATH],
            repo_grounded=False,
            state=state,
        ),
        _integration_opportunity(
            rank=2,
            title="Creator publication or editorial LTD",
            thesis="A creator-publication, editorial, or print-oriented acquisition would fit RUNBOOK PRESS, JACKPOINT, and artifact shelf v2.",
            why_fit="The repo already wants discovery, lineage, moderation, trust ranking, publication, and press-like artifact flows; an existing publishing asset could accelerate that lane materially.",
            owner_keywords=("exchange", "export", "pulse", "launch"),
            evidence_paths=[NEXT90_PATH, HUB_REGISTRY_PATH, MEDIA_FACTORY_PATH],
            repo_grounded=False,
            state=state,
        ),
        _integration_opportunity(
            rank=3,
            title="Travel, route, or venue-intelligence LTD",
            thesis="A route-pack or travel-operations acquisition would strengthen RUNSITE and mobile travel continuity.",
            why_fit="The canon already names route packs, travel moments, mobile continuity, and observer views; the missing leverage is a stronger real-world travel and location intelligence substrate.",
            owner_keywords=("travel", "mobile", "offline", "continuity"),
            evidence_paths=[NEXT90_PATH, ROADMAP_PATH],
            repo_grounded=False,
            state=state,
        ),
        _integration_opportunity(
            rank=4,
            title="Privacy-safe coaching or post-session analytics LTD",
            thesis="A bounded coaching or after-action analytics asset would accelerate TABLE PULSE without making it a second campaign truth source.",
            why_fit="The canon explicitly wants bounded, privacy-safe post-session coaching; the hard part is productizing that loop without becoming creepy or authoritative.",
            owner_keywords=("pulse", "governance", "operator", "support"),
            evidence_paths=[ROADMAP_PATH, NEXT90_PATH, CONFIDENCE_GUIDE_PATH],
            repo_grounded=False,
            state=state,
        ),
        _integration_opportunity(
            rank=5,
            title="Manual-intake or migration-confidence LTD",
            thesis="A scanning, migration, or import-normalization asset would make manual intake and veteran migration much less expensive.",
            why_fit="Confidence guide canon makes manual intake and migration confidence a core promise, and the current parity matrix still shows import/oracle and Hero Lab proof gaps.",
            owner_keywords=("import", "oracle", "hero lab", "custom-data", "xml", "translator"),
            evidence_paths=[CONFIDENCE_GUIDE_PATH, UI_PARITY_PATH, ROADMAP_PATH],
            repo_grounded=False,
            state=state,
        ),
    ]

    gate_recommendations = [
        {
            "title": "Materialize the lost-potential wave as real screenshot and runtime journeys",
            "reason": "The canon already names eight concrete loops; they should become visible release gates, not just roadmap language.",
        },
        {
            "title": "Split parity proof by family instead of one broad veteran-replacement story",
            "reason": "Translator/XML, import/oracles, dense builder, dice, contacts/lifestyles, and print/export need independent screenshot/runtime proof.",
        },
        {
            "title": "Make promoted Windows bytes the only allowed desktop-proof target",
            "reason": "That removes the stale-proof class of failure and aligns install truth with what users actually download.",
        },
        {
            "title": "Gate community and horizon surfaces against core campaign truth",
            "reason": "JACKPOINT, RUNBOOK PRESS, RUNSITE, TABLE PULSE, GHOSTWIRE, and Community Hub should enrich campaign truth, never fork it.",
        },
    ]

    notes = [
        "No missing flagship frontier milestone IDs were found in the live open milestone aggregate." if not missing_frontier_ids else f"Missing frontier IDs are still present: {missing_frontier_ids}",
        "The current parity audit reports zero currently-present removable Chummer6-only extras." if int(parity_summary.get("removable_extra_present_count") or 0) == 0 else "The current parity audit still reports removable Chummer6-only extras.",
        f"Desktop readiness remains `{desktop_status or 'unknown'}`." + (f" Leading reason: {desktop_reasons[0]}" if desktop_reasons else ""),
        f"Other current readiness warnings: mobile={mobile_status or 'unknown'}, ui_kit_and_flagship_polish={polish_status or 'unknown'}, media_artifacts={media_status or 'unknown'}."
        + (f" mobile reason: {mobile_reasons[0]}." if mobile_reasons else "")
        + (f" polish reason: {polish_reasons[0]}." if polish_reasons else "")
        + (f" media reason: {media_reasons[0]}." if media_reasons else ""),
        "The current opportunity audit is repo-grounded first and marks speculative acquisition or integration ideas explicitly as speculative.",
    ]

    user_wants_or_misses = [
        "Tell me what I can do right now, why, and what rule or source backs it.",
        "Adopt my current campaign without rebuilding my table from scratch.",
        "Keep campaign memory, consequences, and runner goals alive between sessions.",
        "Make the dense veteran workflows feel as fast and familiar as Chummer5A.",
        "Give me trusted mobile or companion continuity for travel, recap, and return moments.",
        "Let me publish, recap, share, and form tables from the same canonical campaign truth.",
    ]

    report = {
        "generated_at": _now_iso(),
        "probe_kind": "vision_audit",
        "summary": {
            "repo_grounded_findings_count": len(repo_grounded_findings),
            "speculative_integration_opportunity_count": len(speculative_integration_opportunities),
            "active_runs_count": active_runs_count,
            "productive_active_runs_count": productive_active_runs_count,
            "nonproductive_active_runs_count": nonproductive_active_runs_count,
            "remaining_open_milestones": remaining_open_milestones,
            "missing_frontier_ids": missing_frontier_ids,
            "coverage_gap_keys": coverage_gap_keys,
            "visual_yes_count": int(parity_summary.get("visual_yes_count") or 0),
            "visual_no_count": visual_no_count,
            "behavioral_yes_count": int(parity_summary.get("behavioral_yes_count") or 0),
            "behavioral_no_count": behavioral_no_count,
            "removable_extra_present_count": int(parity_summary.get("removable_extra_present_count") or 0),
            "desktop_client_status": desktop_status,
        },
        "repo_grounded_findings": repo_grounded_findings,
        "speculative_integration_opportunities": speculative_integration_opportunities,
        "user_wants_or_misses": user_wants_or_misses,
        "gate_recommendations": gate_recommendations,
        "notes": notes,
        "supporting_signals": {
            "readiness_status": str(readiness.get("status") or "").strip(),
            "roadmap_loaded": bool(roadmap_text),
            "confidence_guide_loaded": bool(confidence_text),
            "living_campaign_guide_loaded": bool(living_text),
            "lost_potential_wave_loaded": bool(lost_potential_text),
            "next90_registry_loaded": bool(next90_text),
            "hub_registry_loaded": bool(hub_registry_text),
            "media_factory_design_loaded": bool(media_factory_text),
            "ui_parity_findings_count": len(parity_findings),
        },
    }
    _write_report(report)

    payload = {
        "probe_kind": "vision_audit",
        "generated_at": report["generated_at"],
        "report_json_path": str(REPORT_JSON_PATH),
        "report_markdown_path": str(REPORT_MD_PATH),
        "summary": report["summary"],
        "top_findings": repo_grounded_findings[:5],
        "top_integration_opportunities": speculative_integration_opportunities[:4],
        "user_wants_or_misses": user_wants_or_misses,
        "notes": notes[:4],
    }
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
