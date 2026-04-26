#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

GUIDE_ROOT = Path("/docker/chummercomplete/Chummer6")
README_PATH = GUIDE_ROOT / "README.md"
OVERRIDES_PATH = Path("/docker/fleet/state/chummer6/ea_overrides.json")
MEDIA_MANIFEST_PATH = Path("/docker/fleet/state/chummer6/ea_media_manifest.json")

PARTICIPATE_URL = "https://chummer.run/participate"

FLAGSHIP_PAGE_COPY: dict[str, dict[str, str]] = {
    "readme": {
        "intro": "Chummer6 is the human-facing Shadowrun campaign OS for rulings, prep, and campaign continuity that show their work instead of hiding the math.",
        "body": "The project is building visible reasoning instead of trust-me table lore. The public surface gives you the guide, the status readout, future lanes, support paths, and proof artifacts where they are ready to inspect.",
        "kicker": "Start with the guide, inspect the visible surfaces, and decide whether the direction earns your trust.",
    },
    "what_chummer6_is": {
        "intro": "Chummer6 is Shadowrun campaign-OS tooling aimed at making rulings, prep, and table state inspectable instead of mystical.",
        "body": "The pitch is visible reasoning, clearer modifier trails, grounded campaign artifacts, and a more trustworthy prep-to-play surface. The public preview is still moving, but the value proposition is concrete enough to judge on its merits instead of waiting for folklore or wishful thinking.",
        "kicker": "Judge the promise by the receipts, not by mystery or vibes.",
    },
    "current_phase": {
        "intro": "The current phase is public preview with the trust surface moving into focus.",
        "body": "The product is earning confidence through a sharper guide, a clearer status readout, stronger support paths, and proof artifacts that are becoming easier to inspect. That is still an unfinished phase, but it is no longer just abstract concept framing.",
        "kicker": "Read the guide, inspect what is live, and expect the visible proof surface to keep tightening.",
    },
    "current_status": {
        "intro": "Status first: the guide, support surface, and visible proof lanes are live enough to inspect honestly.",
        "body": "What is visible today is the guide, the horizon shelf, support and contact paths, and a growing set of proof artifacts. Some surfaces are still moving, but there is enough in public to evaluate the product direction without pretending nothing exists.",
        "kicker": "Treat the status pages as current truth and the product surface as a preview that should keep getting sharper.",
    },
    "public_surfaces": {
        "intro": "The deliberate public surfaces are the guide, support paths, status readout, horizon shelf, issue flow, and visible proof artifacts.",
        "body": "If a build, screenshot, or proof asset is public, treat it as part of the preview surface and judge it by clarity, trust, and follow-through. Do not mistake preview for finished polish, but do not downplay visible work into nonexistence either.",
        "kicker": "The right question is whether the preview is becoming more legible and trustworthy each pass.",
    },
}

CRITICAL_ASSET_ROWS: dict[str, dict[str, object]] = {
    "assets/hero/chummer6-hero.png": {
        "target": "assets/hero/chummer6-hero.png",
        "output": str(GUIDE_ROOT / "assets/hero/chummer6-hero.png"),
        "provider": "flagship_normalizer",
        "status": "published",
        "overlay_hint": "anticipatory medscan AR that surfaces provenance, surgical fit, and the runner's next likely trust checks",
        "visual_motifs": [
            "streetdoc triage under pressure",
            "runner checking whether the chrome install will hold before the next job",
            "decker ghosting provenance receipts through smart-lens AR",
        ],
        "overlay_callouts": [
            "implant fit confidence",
            "provenance trail",
            "next likely stability check",
            "runner risk cue",
        ],
        "scene_contract": {
            "subject": "an ork streetdoc stabilizing a battered troll runner while an elf decker watches the numbers through smart lenses",
            "environment": "an after-hours shadow clinic with patched chrome, hanging med rails, stained gauze, old blood, and scavenged Ares trauma gear",
            "action": "confirming whether a fresh cyberarm install will survive the run that starts in minutes",
            "metaphor": "triage-grade provenance scan before the street catches up",
            "props": [
                "chrome forearm cradle",
                "Ares trauma-kit shell",
                "Blood Orchid specimen card",
                "devil rat field photo",
            ],
            "overlays": [
                "implant fit confidence",
                "provenance trail",
                "next likely stability check",
            ],
            "composition": "clinic_intake",
            "palette": "clinic white, bruise blue, arterial amber, grime-heavy noir",
        },
    },
    "assets/pages/horizons-index.png": {
        "target": "assets/pages/horizons-index.png",
        "output": str(GUIDE_ROOT / "assets/pages/horizons-index.png"),
        "provider": "flagship_normalizer",
        "status": "published",
        "overlay_hint": "anticipatory route-planning AR that predicts which horizon lane a runner would inspect next and why",
        "visual_motifs": [
            "future lanes breaking across a dangerous boulevard",
            "runner team reading the city like a branching mission board",
            "route overlays anchored to real streets and towers",
        ],
        "overlay_callouts": [
            "next lane worth watching",
            "route risk split",
            "district pressure",
            "follow-up angle",
        ],
        "scene_contract": {
            "subject": "a mixed runner crew reading multiple future lanes across a rain-slick boulevard",
            "environment": "a city-edge crossroads with Barrens grime, Arcology shadow, transit glare, and stacked district markers",
            "action": "comparing which future lane is worth following before the city closes the window",
            "metaphor": "branching futures mapped onto a real street",
            "props": [
                "patched commlink map slab",
                "tower-line route glass",
                "district marker pylons",
                "critter warning poster",
            ],
            "overlays": [
                "next lane worth watching",
                "route risk split",
                "district pressure",
            ],
            "composition": "horizon_boulevard",
            "palette": "sodium rain amber, wet cyan, bruised skyline blue",
        },
    },
    "assets/horizons/karma-forge.png": {
        "target": "assets/horizons/karma-forge.png",
        "output": str(GUIDE_ROOT / "assets/horizons/karma-forge.png"),
        "provider": "flagship_normalizer",
        "status": "published",
        "overlay_hint": "anticipatory forge-review AR that predicts the next rule conflict, approval fork, and rollback question a table will care about",
        "visual_motifs": [
            "house-rule review as a dangerous approval rail",
            "table consensus under pressure",
            "rollback clues hovering over a live forge bench",
        ],
        "overlay_callouts": [
            "next rule conflict",
            "approval fork",
            "rollback clue",
            "table trust cue",
        ],
        "scene_contract": {
            "subject": "a runner-smith and analyst pair testing a volatile house-rule build over a scarred forge bench",
            "environment": "an industrial rules forge with heat haze, warning strips, stamped metal, and consensus notes pinned into the work zone",
            "action": "deciding whether a powerful new rules branch earns approval or needs rollback before it splinters the table",
            "metaphor": "house rules tempered like dangerous hardware",
            "props": [
                "forged rules tablets",
                "rollback rail markers",
                "heat-blown approval stamps",
                "workbench consensus notes",
            ],
            "overlays": [
                "next rule conflict",
                "approval fork",
                "rollback clue",
            ],
            "composition": "approval_rail",
            "palette": "forge orange, soot black, ion blue, bruised steel",
        },
    },
}


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def normalize_readme() -> None:
    if not README_PATH.exists():
        return
    text = README_PATH.read_text(encoding="utf-8")
    if "## How can I help?" not in text:
        anchor = "## Start here\n"
        section = (
            "## How can I help?\n\n"
            f"- Report pain, rough edges, or missing clarity through the public participation flow: {PARTICIPATE_URL}\n"
            "- If you need product help first, use [Help](HELP.md) and [Contact](CONTACT.md).\n\n"
        )
        if anchor in text:
            text = text.replace(anchor, section + anchor, 1)
        else:
            text = text.rstrip() + "\n\n" + section
    if PARTICIPATE_URL not in text:
        text = text.rstrip() + f"\n\nFor public participation and product feedback, use {PARTICIPATE_URL}.\n"
    README_PATH.write_text(text, encoding="utf-8")


def normalize_overrides() -> None:
    overrides = _load_json(OVERRIDES_PATH)
    pages = overrides.get("pages")
    if not isinstance(pages, dict):
        pages = {}
        overrides["pages"] = pages
    for page_id, patch in FLAGSHIP_PAGE_COPY.items():
        row = pages.get(page_id)
        if not isinstance(row, dict):
            row = {}
            pages[page_id] = row
        row.update(patch)
    _write_json(OVERRIDES_PATH, overrides)


def normalize_media_manifest() -> None:
    manifest = _load_json(MEDIA_MANIFEST_PATH)
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        assets = []
        manifest["assets"] = assets
    index: dict[str, dict[str, object]] = {}
    for entry in assets:
        if isinstance(entry, dict):
            target = str(entry.get("target") or "").replace("\\", "/").strip()
            if target:
                index[target] = entry
    for target, patch in CRITICAL_ASSET_ROWS.items():
        row = index.get(target)
        if row is None:
            row = {"target": target}
            assets.append(row)
            index[target] = row
        for key, value in patch.items():
            if key in {"overlay_callouts", "visual_motifs"}:
                current = row.get(key)
                if not isinstance(current, list) or not [str(item).strip() for item in current if str(item).strip()]:
                    row[key] = list(value)
            elif key == "scene_contract":
                current = row.get(key)
                if not isinstance(current, dict) or not current:
                    row[key] = dict(value)
            else:
                if not str(row.get(key) or "").strip():
                    row[key] = value
    _write_json(MEDIA_MANIFEST_PATH, manifest)


def main() -> int:
    normalize_readme()
    normalize_overrides()
    normalize_media_manifest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
