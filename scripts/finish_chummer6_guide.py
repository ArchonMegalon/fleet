#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import random
import struct
import subprocess
import sys
import tempfile
import textwrap
import urllib.parse
import urllib.request
import zlib
from pathlib import Path


OWNER = "ArchonMegalon"
REPO_NAME = "Chummer6"
REPO_SLUG = f"{OWNER}/{REPO_NAME}"
REPO_URL = f"https://github.com/{REPO_SLUG}.git"
GUIDE_REPO = Path("/docker/chummercomplete/Chummer6")
DESIGN_SCOPE = Path("/docker/chummercomplete/chummer-design/products/chummer/projects/guide.md")
EA_OVERRIDE_PATH = Path("/docker/fleet/state/chummer6/ea_overrides.json")
EA_MEDIA_MANIFEST_PATH = Path("/docker/fleet/state/chummer6/ea_media_manifest.json")
TODAY = "2026-03-13"
POLICY_PATH = Path("/docker/fleet/.chummer6_local_policy.json")

DEFAULT_POLICY = {
    "forbidden_origin_mentions": [],
    "forbidden_guide_terms": [
        "fleet is mission control",
        "operational truth lives in fleet",
        "where the real truth lives",
        "where_the_real_truth_lives",
        "openai key",
        "lua-scripted rules",
        "preview debt",
        "contract plane",
        "design/control layer",
        "every fleet view",
        "parts/fleet.md",
        "executive-assistant",
        "operational truth lives in ea",
    ],
    "forbidden_hotlinks": [
        "image.pollinations.ai",
        "cdn.openai.com",
    ],
    "image_generation": {
        "enabled": False,
        "provider": "",
        "command": [],
        "url_template": "",
    },
}

LEGACY_PART_SLUGS = {
    "ui": "presentation",
    "mobile": "play",
    "hub": "run-services",
}

MEDIA_TARGET_ALIASES = {
    "assets/parts/ui.png": "assets/parts/presentation.png",
    "assets/parts/mobile.png": "assets/parts/play.png",
    "assets/parts/hub.png": "assets/parts/run-services.png",
}

FORBIDDEN = [
    "VISION.md",
    "ROADMAP.md",
    "ARCHITECTURE.md",
    "WORKLIST.md",
    "CONTRACT_SETS.yaml",
    "GROUP_BLOCKERS.md",
    "runtime-instructions.generated.md",
    "QUEUE.generated.yaml",
]

RETIRED = [
    "WHERE_THE_REAL_TRUTH_LIVES.md",
    "PARTS/fleet.md",
    "PARTS/presentation.md",
    "PARTS/play.md",
    "PARTS/run-services.md",
    "assets/chummer6-hero.svg",
    "assets/poc-warning.svg",
    "assets/hero/chummer6-hero.svg",
    "assets/hero/poc-warning.svg",
    "assets/hero/poc-warning.gif",
    "assets/diagrams/program-map.png",
    "assets/diagrams/status-strip.png",
    "assets/diagrams/program-map.svg",
    "assets/diagrams/status-strip.svg",
    "assets/pages/start-here.svg",
    "assets/pages/what-chummer6-is.svg",
    "assets/pages/where-to-go-deeper.svg",
    "assets/pages/current-phase.svg",
    "assets/pages/current-status.svg",
    "assets/pages/public-surfaces.svg",
    "assets/pages/parts-index.svg",
    "assets/pages/horizons-index.svg",
    "assets/parts/presentation.png",
    "assets/parts/play.png",
    "assets/parts/run-services.png",
    "assets/horizons/alice.svg",
    "assets/horizons/blackbox-loadout.svg",
    "assets/horizons/ghostwire.svg",
    "assets/horizons/heat-web.svg",
    "assets/horizons/jackpoint.svg",
    "assets/horizons/karma-forge.svg",
    "assets/horizons/mirrorshard.svg",
    "assets/horizons/nexus-pan.svg",
    "assets/horizons/rule-x-ray.svg",
    "assets/horizons/run-passport.svg",
    "assets/horizons/threadcutter.svg",
]

PARTS = {
    "core": {
        "title": "Core",
        "tagline": "The deterministic rules engine.",
        "intro": (
            "Core is where the numbers stop bluffing. It owns the engine behavior, "
            "the reducer logic, and the boringly reliable parts that let the rest of "
            "Chummer stop arguing about what a rule actually means."
        ),
        "why": (
            "When a dice pool feels wrong or a result needs explaining, this is the "
            "part that should be able to say exactly why."
        ),
        "owns": [
            "engine runtime and reducer truth",
            "explain receipts and deterministic evaluation",
            "engine-facing shared interfaces",
        ],
        "not_owns": [
            "the hosted service layer",
            "the at-the-table shell",
            "render-only media work",
        ],
        "now": (
            "The current mission is purification: keep the engine mean, lean, and "
            "predictable until it obviously means engine truth and not a junk drawer."
        ),
    },
    "ui": {
        "title": "UI",
        "tagline": "The workbench and big-screen UX.",
        "intro": (
            "UI is where the heavy chrome lives: inspectors, builders, deep "
            "views, and the workbench-side experience for people who like staring at "
            "their gear until the gears stare back."
        ),
        "why": (
            "This is the part that makes Chummer feel inspectable instead of mystical."
        ),
        "owns": [
            "browser and desktop workbench UX",
            "inspectors, builders, and shared workbench seams",
            "big-screen authoring and review flows",
        ],
        "not_owns": [
            "the player-first play shell",
            "hosted orchestration",
            "render-only asset jobs",
        ],
        "now": (
            "The cleanup job here is deletion: keep workbench power, shed any lingering "
            "claims over play-first or hosted concerns."
        ),
    },
    "mobile": {
        "title": "Mobile",
        "tagline": "The part you feel at the table.",
        "intro": (
            "Mobile is the shell for players and GMs during actual sessions: mobile/PWA "
            "use, local-first state, runtime bundles, sync, replay, and the moment where "
            "the tool stops being prep and starts being live play."
        ),
        "why": (
            "If Chummer is going to become more than a character builder, this is the jump."
        ),
        "owns": [
            "player and GM play shell",
            "local-first session state",
            "runtime stack consumption",
            "sync-friendly play flows",
        ],
        "not_owns": [
            "builder/workbench UX",
            "provider secrets",
            "copied shared interfaces",
        ],
        "now": (
            "This is still the next big seam to make real. The current work is less about "
            "flash and more about event logs, runtime cache, offline queueing, and sync."
        ),
    },
    "hub": {
        "title": "Hub",
        "tagline": "The hosted API and orchestration layer.",
        "intro": (
            "Hub is the network backbone: identity, relay, approvals, memory, "
            "hosted play APIs, previews, and the clever server-side machinery that should "
            "eventually feel completely unremarkable."
        ),
        "why": (
            "When Chummer needs to coordinate, publish, preview, or synchronize, this is "
            "where the adult supervision lives."
        ),
        "owns": [
            "identity, relay, approvals, and memory",
            "hosted play APIs and orchestration",
            "preview/apply/rollback style server workflows",
        ],
        "not_owns": [
            "engine math truth",
            "the long-term play shell",
            "render-only media execution",
        ],
        "now": (
            "The mission is shrink-to-fit: keep the hosted boundary sharp and stop letting "
            "it impersonate every other part of the program."
        ),
    },
    "ui-kit": {
        "title": "UI Kit",
        "tagline": "Shared chrome, themes, and visual primitives.",
        "intro": (
            "UI Kit is the visual vocabulary: tokens, themes, shell chrome, badges, banners, "
            "and accessibility-friendly primitives that the other heads should consume instead "
            "of rebuilding with duct tape and mood swings."
        ),
        "why": (
            "This is how the split becomes coherent instead of looking like seven gangs met in a parking lot."
        ),
        "owns": [
            "tokens and themes",
            "shared chrome and accessibility primitives",
            "UI-only preview and gallery surfaces",
        ],
        "not_owns": [
            "domain DTOs",
            "HTTP clients",
            "rules math",
        ],
        "now": (
            "UI Kit only counts as real when the rest of the codebase gets visibly smaller because it exists."
        ),
    },
    "hub-registry": {
        "title": "Hub Registry",
        "tagline": "Artifacts, publication, installs, compatibility.",
        "intro": (
            "Hub Registry is the artifact brain: what exists, what is published, what can be "
            "installed, and which bundles, previews, or compatibility signals belong on the record."
        ),
        "why": (
            "Without this, the growing pile of artifacts turns into an unlabeled warehouse full of cursed boxes."
        ),
        "owns": [
            "artifact metadata",
            "publication and moderation workflow metadata",
            "install and compatibility projections",
        ],
        "not_owns": [
            "AI routing",
            "rules computation",
            "media rendering",
        ],
        "now": (
            "This seam is narrow on purpose. The work is consumer migration and cleanup, not feature sprawl."
        ),
    },
    "media-factory": {
        "title": "Media Factory",
        "tagline": "Render-only asset lifecycle.",
        "intro": (
            "Media Factory is where render jobs, previews, signed URLs, dedupe, retry, and asset "
            "lifecycle management are supposed to live without dragging story policy, rules math, "
            "or provider soup along for the ride."
        ),
        "why": (
            "If Chummer gets more visual and media-heavy, this is the repo that stops the rest of the architecture from melting."
        ),
        "owns": [
            "render queues",
            "signed URLs and storage adapters",
            "dedupe/retry and asset lifecycle receipts",
        ],
        "not_owns": [
            "lore generation",
            "session relay",
            "provider routing and rules math",
        ],
        "now": (
            "It is still scaffold-stage. The correct move is to keep it narrow until the seam is boringly stable."
        ),
    },
    "design": {
        "title": "Design",
        "tagline": "The canonical blueprint room.",
        "intro": (
            "Design is the long-range map: ownership, milestones, split order, guidance, mirror rules, "
            "and the grown-up version of where the program is actually trying to go."
        ),
        "why": (
            "When the rest of the program argues about what is supposed to be true, this is where the answer should come from."
        ),
        "owns": [
            "cross-repo architecture and ownership",
            "milestone framing and split order",
            "review guidance and mirror rules",
        ],
        "not_owns": [
            "implementation",
            "dispatchable coding work",
            "human-only storytelling",
        ],
        "now": (
            "The active design work is making the blueprint current enough that the rest of the program can stop free-styling."
        ),
    },
}

HORIZONS = {
    "karma-forge": {
        "title": "Karma Forge",
        "hook": "Personalized rules without forked-code chaos.",
        "problem": (
            "Players want house rules, variants, and personalized rule stacks without turning every table into a private fork nobody else can inspect."
        ),
        "brutal_truth": (
            "People love customizing the rules right up until those rules stop agreeing with each other and nobody can explain the damage calculation."
        ),
        "use_case": (
            "You want a custom rules layer for your table. Instead of forking the app and praying, you slot in a controlled overlay stack that can be inspected, explained, previewed, and rolled back."
        ),
        "foundations": [
            "runtime stack and fingerprint DTOs",
            "overlay receipts and conflict reports",
            "explain/provenance receipts",
            "clean shared interfaces",
        ],
        "repos": ["core", "mobile", "hub", "hub-registry", "design"],
        "not_now": (
            "Because the split still needs its contract reset and seam cleanup. Fancy overlay power on top of fuzzy foundations is how you summon haunted software."
        ),
        "accent": "#0f766e",
        "glow": "#34d399",
        "prompt": (
            "Wide cyberpunk forge banner, a massive cybernetic troll smith in welding goggles hammering a glowing rules shard on an anvil while green code sparks scatter through a grimy neon workshop, humorous but powerful, original concept art, no text, no logo, no watermark, 16:9"
        ),
    },
    "nexus-pan": {
        "title": "NEXUS-PAN",
        "hook": "A live synced table instead of lonely files.",
        "problem": (
            "Sessions want shared authority, resilient sync, and live state that survives dodgy networks and chaotic tables."
        ),
        "brutal_truth": (
            "A folder full of character files is not a live table. It is a very quiet argument waiting to happen."
        ),
        "use_case": (
            "The GM, players, and devices all see the same session state, even if a phone dips offline for a minute and then claws its way back into the run."
        ),
        "foundations": [
            "session authority profile",
            "append-only session events",
            "local-first sync and replay",
            "clean play API seams",
        ],
        "repos": ["mobile", "hub", "core", "design"],
        "not_now": (
            "Because the play split still needs its event-log, cache, and sync foundations to become real before the dream gets chrome."
        ),
        "accent": "#1d4ed8",
        "glow": "#60a5fa",
        "prompt": (
            "Wide grounded cyberpunk scene of a shadowrunner team around a table using phones and commlinks while a GM controls AR overlays, live weather and matrix effects changing across multiple screens, gritty neon bar backroom, cinematic lighting, believable gear, no text, no logo, no watermark, 16:9"
        ),
    },
    "alice": {
        "title": "ALICE",
        "hook": "Stress-test your build before the run.",
        "problem": (
            "People want to know how a build behaves under pressure without needing a real disaster as the benchmark."
        ),
        "brutal_truth": (
            "Everybody thinks their build is invincible until a simulation calmly explains that they die in round two because they brought swagger instead of resistance dice."
        ),
        "use_case": (
            "You hit test drive, run a deterministic lab harness, and get a replayable answer about why your build survives, folds, or explodes."
        ),
        "foundations": [
            "deterministic engine truth",
            "scenario harnesses with reproducible seeds",
            "explain receipts",
            "stable runtime stack fingerprints",
        ],
        "repos": ["core", "hub", "design"],
        "not_now": (
            "Because the engine and explain seams still need to become cleaner before simulation gets to wear a lab coat."
        ),
        "accent": "#7c3aed",
        "glow": "#c084fc",
        "prompt": (
            "Wide cyberpunk simulation-lab banner, a sharp-eyed cyberpunk woman in runner gear inside a glowing combat simulation grid while multiple outcomes branch around her, statistical danger with dark humor, original concept art, no text, no logo, no watermark, 16:9"
        ),
    },
    "jackpoint": {
        "title": "JACKPOINT",
        "hook": "Turn grounded data into dossiers and briefings.",
        "problem": (
            "Narrative output gets dangerous fast when nobody can tell the difference between grounded evidence and cool-looking guesswork."
        ),
        "brutal_truth": (
            "A stylish dossier is great right up until it starts inventing facts with the confidence of a corp spokesman."
        ),
        "use_case": (
            "You collect grounded character data, session notes, and receipts, then turn them into dossiers and briefings that can still explain where the facts came from."
        ),
        "foundations": [
            "grounded evidence receipts",
            "approval states",
            "clean registry/media seams",
            "source classification",
        ],
        "repos": ["hub", "hub-registry", "media-factory", "design"],
        "not_now": (
            "Because grounded evidence and render boundaries need to settle first. Style without receipts is just prettier confusion."
        ),
        "accent": "#7c2d12",
        "glow": "#fb923c",
        "prompt": (
            "Wide cyberpunk dossier-generation concept art, a cluttered desk with a glowing police case file, blurred mugshot display, redacted pages, coffee stains, evidence strings, holographic overlays and data fragments, moody noir lighting, grounded and atmospheric, no text, no logo, no watermark, 16:9"
        ),
    },
    "ghostwire": {
        "title": "GHOSTWIRE",
        "hook": "Replay a run like a forensic sim.",
        "problem": (
            "After a chaotic session, everybody remembers events differently and everybody suddenly becomes a professional liar."
        ),
        "brutal_truth": (
            "If nobody can replay the action history, every rules dispute becomes a memory contest with worse lighting."
        ),
        "use_case": (
            "You scrub through a run, see event echoes and state changes, and figure out which move actually tripped the alarms before the shouting starts."
        ),
        "foundations": [
            "session authority and event history",
            "evidence labeling",
            "replayable receipts",
            "clean sync seams",
        ],
        "repos": ["mobile", "hub", "design"],
        "not_now": (
            "Because replay only works if the session/event model is first-class instead of implied."
        ),
        "accent": "#334155",
        "glow": "#94a3b8",
        "prompt": (
            "Wide cyberpunk replay-forensics banner, a run scene frozen in layered time slices with transparent past actions ghosting over the present, evidence trails and action echoes, analytical and dramatic, original concept art, no text, no logo, no watermark, 16:9"
        ),
    },
    "rule-x-ray": {
        "title": "RULE X-RAY",
        "hook": "Click any number and see where it came from.",
        "problem": (
            "Opaque math is one of the fastest ways for a rules tool to lose trust at the table."
        ),
        "brutal_truth": (
            "Shadowrun math feels like witchcraft until the machine can point at every buff, wound, penalty, and bad life choice in the stack."
        ),
        "use_case": (
            "A dice pool looks wrong, you crack open the x-ray view, and the whole chain of causes lights up without hand-waving."
        ),
        "foundations": [
            "explain canon",
            "provenance receipts",
            "deterministic engine evaluation",
        ],
        "repos": ["core", "ui", "design"],
        "not_now": (
            "Because the explain/provenance line still needs to finish becoming boringly canonical first."
        ),
        "accent": "#0f766e",
        "glow": "#2dd4bf",
        "prompt": (
            "Wide cyberpunk x-ray visualization of numbers and rules sources, transparent layered holograms showing dice, modifiers, wires, code fragments, and highlighted causes flowing into one final result, dark background, cyan and green glow, sharp readable composition, no text, no logo, no watermark, 16:9"
        ),
    },
    "heat-web": {
        "title": "HEAT WEB",
        "hook": "Campaign consequences as a living graph.",
        "problem": (
            "Campaign fallout is easy to forget, hard to track, and exactly the kind of thing that gets interesting once it starts sticking."
        ),
        "brutal_truth": (
            "Players always assume yesterday’s mess vanished into the rain unless the system remembers exactly who they annoyed."
        ),
        "use_case": (
            "A bad decision sparks faction pressure, social fallout, and delayed consequences that show up as a readable network instead of GM memory homework."
        ),
        "foundations": [
            "grounded event streams",
            "durable evidence receipts",
            "stable artifact publication",
        ],
        "repos": ["hub", "mobile", "ui", "design"],
        "not_now": (
            "Because consequence graphs are downstream of good event/evidence plumbing, not a substitute for it."
        ),
        "accent": "#be123c",
        "glow": "#fb7185",
        "prompt": (
            "Wide cyberpunk conspiracy-graph banner, a living network of factions, enemies, debts, and consequences glowing across a city map wall, dangerous connective tissue everywhere, original concept art, no text, no logo, no watermark, 16:9"
        ),
    },
    "mirrorshard": {
        "title": "MIRRORSHARD",
        "hook": "Compare alternate character futures before you commit.",
        "problem": (
            "Big choices are easier to trust when you can compare forks without turning the program into a pile of permanent branches."
        ),
        "brutal_truth": (
            "Everyone says they want meaningful choices. What they usually mean is: let me compare both mistakes before I marry one."
        ),
        "use_case": (
            "You compare two alternate versions of a build or run plan side by side, with a readable diff instead of crossed fingers."
        ),
        "foundations": [
            "preview/apply/rollback receipts",
            "comparison-ready provenance",
            "migration previews",
        ],
        "repos": ["ui", "hub", "design"],
        "not_now": (
            "Because comparison tooling depends on clean receipts, and those receipts are still being forged."
        ),
        "accent": "#4338ca",
        "glow": "#818cf8",
        "prompt": (
            "Wide cyberpunk alternate-timeline banner, mirrored character silhouettes and branching decision shards floating over a dark cityscape, reflective glass, elegant purple-blue glow, original concept art, no text, no logo, no watermark, 16:9"
        ),
    },
    "run-passport": {
        "title": "RUN PASSPORT",
        "hook": "Move a character across rule environments safely.",
        "problem": (
            "Portability is easy to promise and painful to implement once compatibility actually matters."
        ),
        "brutal_truth": (
            "Moving a character between environments sounds cool until one ruleset calls it legal and another calls it eldritch contraband."
        ),
        "use_case": (
            "A character carries a readable runtime identity, compatibility notes, and migration preview instead of raw hope."
        ),
        "foundations": [
            "runtime stack profile",
            "fingerprint and lineage",
            "compatibility projections",
        ],
        "repos": ["hub-registry", "mobile", "hub", "design"],
        "not_now": (
            "Because the registry seam and runtime stack model still need to harden before portability can stop being wishful thinking."
        ),
        "accent": "#0f766e",
        "glow": "#5eead4",
        "prompt": (
            "Wide cyberpunk passport-and-transit banner, a shadowrunner dossier and digital travel credential crossing between glowing rule environments and security checkpoints, sleek but dangerous, no text, no logo, no watermark, 16:9"
        ),
    },
    "threadcutter": {
        "title": "THREADCUTTER",
        "hook": "Conflict analysis for overlay packs and runtime changes.",
        "problem": (
            "Sooner or later, two clever changes will try to claim the same space at the same time."
        ),
        "brutal_truth": (
            "Every cool customization story eventually ends with two mods both insisting they are the chosen one."
        ),
        "use_case": (
            "You get a conflict report before two overlays collide in production and turn your rule stack into abstract art."
        ),
        "foundations": [
            "conflict reports",
            "migration previews",
            "apply and rollback receipts",
        ],
        "repos": ["hub", "mobile", "design"],
        "not_now": (
            "Because the runtime stack model and migration receipts must exist before conflict analysis has anything honest to inspect."
        ),
        "accent": "#92400e",
        "glow": "#f59e0b",
        "prompt": (
            "Wide cyberpunk conflict-analysis banner, tangled glowing data threads being cut apart over a dark tactical console, sharp orange sparks, original concept art, no text, no logo, no watermark, 16:9"
        ),
    },
    "blackbox-loadout": {
        "title": "BLACKBOX LOADOUT",
        "hook": "The idiot-check before the run.",
        "problem": (
            "Runner prep fails more often from missing essentials than from heroic intent."
        ),
        "brutal_truth": (
            "People do not die because they forgot courage. They die because they forgot ammo, rope, and basic self-respect."
        ),
        "use_case": (
            "You hit run-ready, and the system points at the exact gear, resources, and prep holes most likely to get you folded in the first scene."
        ),
        "foundations": [
            "runtime stack manifests",
            "compatibility checks",
            "preview receipts",
        ],
        "repos": ["mobile", "hub-registry", "design"],
        "not_now": (
            "Because the stack/loadout model still needs to exist before the repo can shame you with confidence."
        ),
        "accent": "#b45309",
        "glow": "#fbbf24",
        "prompt": (
            "Wide cyberpunk prep-check banner, gear trays, ammo, spells, hacking tools, medkits, and mission tags arranged for a run while a warning light highlights missing essentials, tactical and clever, original concept art, no text, no logo, no watermark, 16:9"
        ),
    },
}


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def load_policy() -> dict[str, object]:
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    if POLICY_PATH.exists():
        loaded = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            for key, value in loaded.items():
                if isinstance(value, dict) and isinstance(policy.get(key), dict):
                    merged = dict(policy[key])  # type: ignore[index]
                    merged.update(value)
                    policy[key] = merged
                else:
                    policy[key] = value
    return policy


GUIDE_POLICY = load_policy()


def deep_merge(base: object, override: object) -> object:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, value in override.items():
            merged[key] = deep_merge(merged[key], value) if key in merged else value
        return merged
    return override


def load_ea_overrides() -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    parts_override: dict[str, object] = {}
    horizons_override: dict[str, object] = {}
    ooda_override: dict[str, object] = {}
    pages_override: dict[str, object] = {}
    section_ooda_override: dict[str, object] = {}
    if EA_OVERRIDE_PATH.exists():
        loaded = json.loads(EA_OVERRIDE_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            raw_parts = loaded.get("parts")
            raw_horizons = loaded.get("horizons")
            raw_ooda = loaded.get("ooda")
            raw_pages = loaded.get("pages")
            raw_section_ooda = loaded.get("section_ooda")
            if isinstance(raw_parts, dict):
                parts_override = raw_parts
            if isinstance(raw_horizons, dict):
                horizons_override = raw_horizons
            if isinstance(raw_ooda, dict):
                ooda_override = raw_ooda
            if isinstance(raw_pages, dict):
                pages_override = raw_pages
            if isinstance(raw_section_ooda, dict):
                section_ooda_override = raw_section_ooda
    return parts_override, horizons_override, ooda_override, pages_override, section_ooda_override


EA_PART_OVERRIDES, EA_HORIZON_OVERRIDES, EA_OODA, EA_PAGE_OVERRIDES, EA_SECTION_OODA = load_ea_overrides()


def part_override_for(name: str) -> dict[str, object]:
    override = EA_PART_OVERRIDES.get(name)
    if isinstance(override, dict):
        source = override
    else:
        legacy_name = LEGACY_PART_SLUGS.get(name)
        legacy = EA_PART_OVERRIDES.get(legacy_name or "")
        if isinstance(legacy, dict):
            source = legacy
        else:
            return {}
    if name == "ui":
        replacements = {
            "Presentation": "UI",
            "`presentation`": "`ui`",
        }
    elif name == "mobile":
        replacements = {
            "Play": "Mobile",
            "`play`": "`mobile`",
        }
    elif name == "hub":
        replacements = {
            "Run Services": "Hub",
            "`run-services`": "`hub`",
        }
    else:
        replacements = {}
    normalized: dict[str, object] = {}
    for key, value in source.items():
        if isinstance(value, str):
            text = value
            for old, new in replacements.items():
                text = text.replace(old, new)
            normalized[key] = text
        else:
            normalized[key] = value
    return normalized


OODA_ALIASES = {
    "audience": ("orient", "audience"),
    "promise": ("orient", "promise"),
    "tension": ("orient", "tension"),
    "why_care": ("orient", "why_care"),
    "current_focus": ("orient", "current_focus"),
    "visual_direction": ("orient", "visual_direction"),
    "humor_line": ("orient", "humor_line"),
    "signals_to_highlight": ("orient", "signals_to_highlight"),
    "banned_terms": ("orient", "banned_terms"),
    "landing_tagline": ("act", "landing_tagline"),
    "landing_intro": ("act", "landing_intro"),
    "what_it_is": ("act", "what_it_is"),
    "watch_intro": ("act", "watch_intro"),
    "horizon_intro": ("act", "horizon_intro"),
}


def ooda_value(key: str) -> object | None:
    direct = EA_OODA.get(key)
    if direct not in (None, "", [], {}):
        return direct
    path = OODA_ALIASES.get(key)
    current: object = EA_OODA
    if not path:
        return None
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def ooda_list(key: str) -> list[str]:
    raw = ooda_value(key)
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def ooda_text(key: str, default: str = "") -> str:
    raw = ooda_value(key)
    value = str(raw if raw is not None else "").strip()
    return value or default


def required_ooda_text(key: str) -> str:
    value = ooda_text(key).strip()
    if not value:
        raise ValueError(f"missing required EA OODA text: {key}")
    return value


def required_ooda_list(key: str) -> list[str]:
    values = ooda_list(key)
    if not values:
        raise ValueError(f"missing required EA OODA list: {key}")
    return values


def page_override_text(page_id: str, field: str, default: str = "") -> str:
    page = EA_PAGE_OVERRIDES.get(page_id)
    if isinstance(page, dict):
        value = str(page.get(field, "")).strip()
        if value:
            return value
    return default


def required_page_override_text(page_id: str, field: str) -> str:
    value = page_override_text(page_id, field).strip()
    if not value:
        raise ValueError(f"missing required EA page override: {page_id}.{field}")
    return value


def require_section_ooda(section_group: str, section_id: str) -> None:
    group = EA_SECTION_OODA.get(section_group)
    if not isinstance(group, dict):
        raise ValueError(f"EA section OODA group is missing: {section_group}")
    entry = group.get(section_id)
    if not isinstance(entry, dict) and section_group == "parts":
        legacy_id = LEGACY_PART_SLUGS.get(section_id)
        if legacy_id:
            entry = group.get(legacy_id)
    if not isinstance(entry, dict):
        raise ValueError(f"EA section OODA is missing: {section_group}.{section_id}")
    for stage, fields in {
        "observe": ["reader_question", "likely_interest", "concrete_signals", "risks"],
        "orient": ["emotional_goal", "sales_angle", "focal_subject", "scene_logic", "visual_devices", "tone_rule", "banned_literalizations"],
        "decide": ["copy_priority", "image_priority", "overlay_priority", "subject_rule", "hype_limit"],
        "act": ["one_liner", "paragraph_seed", "visual_prompt_seed"],
    }.items():
        stage_value = entry.get(stage)
        if not isinstance(stage_value, dict):
            raise ValueError(f"EA section OODA stage is missing: {section_group}.{section_id}.{stage}")
        for field in fields:
            value = stage_value.get(field)
            if value in (None, "", [], {}):
                raise ValueError(f"EA section OODA field is missing: {section_group}.{section_id}.{stage}.{field}")


def require_ooda_stage(name: str, fields: list[str]) -> None:
    stage = EA_OODA.get(name)
    if not isinstance(stage, dict):
        raise ValueError(f"EA OODA stage is missing: {name}")
    for field in fields:
        value = stage.get(field)
        if value in (None, "", [], {}):
            raise ValueError(f"EA OODA field is missing: {name}.{field}")


def indented_bullets(items: list[str], *, spaces: int = 16) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}- {item}" for item in items if str(item).strip())


def dedent(text: str) -> str:
    return textwrap.dedent(text).strip() + "\n"


def footer(*sources: str) -> str:
    joined = ", ".join(sources)
    return dedent(
        f"""
        ---

        _Last synced: {TODAY}_  
        _Derived from: {joined}_  
        _Canonical source: chummer6-design_
        """
    ).rstrip() + "\n"


def assert_clean(text: str, *, label: str) -> None:
    lowered = text.lower()
    for item in GUIDE_POLICY.get("forbidden_origin_mentions", []):
        token = str(item).strip()
        if token and token.lower() in lowered:
            raise ValueError(f"{label} contains forbidden provenance text: {token}")


def write_text(path: Path, content: str) -> None:
    assert_clean(content, label=str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def ensure_github_repo() -> None:
    view = run("gh", "repo", "view", REPO_SLUG, check=False)
    stderr = (view.stderr or "").lower()
    stdout = (view.stdout or "").lower()
    if "rate limit exceeded" in stderr or "rate limit exceeded" in stdout:
        if (GUIDE_REPO / ".git").exists():
            return
    if view.returncode != 0:
        run(
            "gh",
            "repo",
            "create",
            REPO_SLUG,
            "--public",
            "--description",
            "Human guide to the next Chummer: vision, parts, horizons, and progress. Not canonical design.",
            "--disable-issues",
        )
    patch = run(
        "gh",
        "api",
        "-X",
        "PATCH",
        f"repos/{REPO_SLUG}",
        "-F",
        "name=Chummer6",
        "-F",
        "description=Human guide to the next Chummer: vision, parts, horizons, and progress. Not canonical design.",
        "-F",
        "homepage=",
        "-F",
        "has_issues=false",
        "-F",
        "has_projects=false",
        "-F",
        "has_wiki=false",
        "-F",
        "has_discussions=false",
        check=False,
    )
    if patch.returncode != 0:
        lowered = f"{patch.stdout}\n{patch.stderr}".lower()
        if "rate limit exceeded" not in lowered:
            raise subprocess.CalledProcessError(patch.returncode, patch.args, patch.stdout, patch.stderr)


def ensure_local_repo() -> None:
    GUIDE_REPO.mkdir(parents=True, exist_ok=True)
    if not (GUIDE_REPO / ".git").exists():
        run("git", "init", "-b", "main", cwd=GUIDE_REPO)
    remotes = run("git", "remote", cwd=GUIDE_REPO, check=False)
    if "origin" in remotes.stdout.split():
        run("git", "remote", "set-url", "origin", REPO_URL, cwd=GUIDE_REPO)
    else:
        run("git", "remote", "add", "origin", REPO_URL, cwd=GUIDE_REPO)


def remove_forbidden() -> None:
    for rel in [*FORBIDDEN, *RETIRED]:
        target = GUIDE_REPO / rel
        if target.exists():
            if target.is_dir():
                for child in sorted(target.rglob("*"), reverse=True):
                    if child.is_file():
                        child.unlink()
                for child in sorted(target.rglob("*"), reverse=True):
                    if child.is_dir():
                        child.rmdir()
                target.rmdir()
            else:
                target.unlink()


def image_policy() -> dict[str, object]:
    return GUIDE_POLICY.get("image_generation", {}) if isinstance(GUIDE_POLICY.get("image_generation"), dict) else {}


def format_command(template: list[str], *, prompt: str, output: str, width: int, height: int) -> list[str]:
    return [
        part.format(prompt=prompt, output=output, width=width, height=height)
        for part in template
    ]


def try_provider_image(prompt: str, *, width: int, height: int) -> bytes | None:
    cfg = image_policy()
    if not cfg.get("enabled"):
        return None

    provider = str(cfg.get("provider", "")).strip().lower()
    command = cfg.get("command")
    if provider in {"markuptogo", "markupgo", "markup-to-go"} and (not isinstance(command, list) or not command):
        binary = str(cfg.get("binary") or "markuptogo").strip()
        if binary:
            command = [
                binary,
                "--prompt",
                "{prompt}",
                "--output",
                "{output}",
                "--width",
                "{width}",
                "--height",
                "{height}",
            ]
    if provider in {"oneminai", "1min.ai", "1minai", "ai magicx", "aimagicx", "ai-magicx"} and (
        not isinstance(command, list) or not command
    ):
        command = None
    if isinstance(command, list) and command:
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            run(*format_command(command, prompt=prompt, output=tmp_path, width=width, height=height))
            data = Path(tmp_path).read_bytes()
            if data:
                return data
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass

    url_template = cfg.get("url_template")
    if isinstance(url_template, str) and url_template.strip():
        url = url_template.format(
            prompt=urllib.parse.quote(prompt, safe=""),
            width=width,
            height=height,
        )
        request = urllib.request.Request(url, headers={"User-Agent": "Chummer6Guide/1.0"})
        with urllib.request.urlopen(request, timeout=int(cfg.get("timeout_seconds", 30))) as response:
            data = response.read()
        if data:
            return data
    return None


def clamp8(value: float) -> int:
    return max(0, min(255, int(value)))


def hex_rgb(value: str) -> tuple[int, int, int]:
    raw = value.lstrip("#")
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        clamp8(a[0] + (b[0] - a[0]) * t),
        clamp8(a[1] + (b[1] - a[1]) * t),
        clamp8(a[2] + (b[2] - a[2]) * t),
    )


def png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag)
    crc = zlib.crc32(data, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def rgba_png(width: int, height: int, pixels: bytes) -> bytes:
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    stride = width * 4
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        start = y * stride
        rows.extend(pixels[start : start + stride])
    compressed = zlib.compress(bytes(rows), level=9)
    return header + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", compressed) + png_chunk(b"IEND", b"")


def blend_pixel(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    if x < 0 or y < 0 or x >= width or y >= height or alpha <= 0.0:
        return
    idx = (y * width + x) * 4
    inv = max(0.0, min(1.0, 1.0 - alpha))
    pixels[idx] = clamp8(pixels[idx] * inv + color[0] * alpha)
    pixels[idx + 1] = clamp8(pixels[idx + 1] * inv + color[1] * alpha)
    pixels[idx + 2] = clamp8(pixels[idx + 2] * inv + color[2] * alpha)
    pixels[idx + 3] = 255


def overlay_rect(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    x: int,
    y: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    for yy in range(max(0, y), min(height, y + h)):
        for xx in range(max(0, x), min(width, x + w)):
            blend_pixel(pixels, width, height, xx, yy, color, alpha)


def overlay_circle(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    cx: float,
    cy: float,
    radius: float,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    x0 = max(0, int(cx - radius - 1))
    x1 = min(width, int(cx + radius + 1))
    y0 = max(0, int(cy - radius - 1))
    y1 = min(height, int(cy + radius + 1))
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            dx = xx - cx
            dy = yy - cy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > radius:
                continue
            falloff = 1.0 - (dist / max(1.0, radius))
            blend_pixel(pixels, width, height, xx, yy, color, alpha * (0.2 + 0.8 * falloff))


def overlay_line(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: tuple[int, int, int],
    alpha: float,
    thickness: int = 3,
) -> None:
    steps = max(int(abs(x2 - x1)), int(abs(y2 - y1)), 1)
    for step in range(steps + 1):
        t = step / steps
        x = x1 + (x2 - x1) * t
        y = y1 + (y2 - y1) * t
        overlay_circle(
            pixels,
            width,
            height,
            cx=x,
            cy=y,
            radius=max(1.0, thickness / 2.0),
            color=color,
            alpha=alpha,
        )


def synth_cyberpunk_pixels(
    title: str,
    accent: str,
    glow: str,
    *,
    width: int = 1280,
    height: int = 720,
    phase: float = 0.0,
    layout: str = "banner",
) -> bytearray:
    seed = int(hashlib.sha256(f"{title}:{accent}:{glow}:{layout}".encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    bg_a = (8, 10, 18)
    bg_b = hex_rgb(accent)
    glow_rgb = hex_rgb(glow)
    panel_rgb = (242, 248, 252)
    pixels = bytearray(width * height * 4)
    orbs: list[tuple[float, float, float, float]] = []
    orb_count = 1 if layout == "scene" else 3 if layout == "banner" else 5
    for _ in range(orb_count):
        if layout == "scene":
            radius_lo = width * 0.08
            radius_hi = width * 0.14
            strength_lo = 0.08
            strength_hi = 0.18
        else:
            radius_lo = width * 0.14
            radius_hi = width * 0.28
            strength_lo = 0.35
            strength_hi = 0.85
        orbs.append(
            (
                rng.uniform(0.15, 0.85) * width,
                rng.uniform(0.12, 0.78) * height,
                rng.uniform(radius_lo, radius_hi),
                rng.uniform(strength_lo, strength_hi),
            )
        )
    panel = None
    if layout == "banner":
        panel = (
            int(width * 0.38),
            int(height * 0.13),
            int(width * 0.54),
            int(height * 0.72),
        )
    elif layout == "grid":
        panel = (
            int(width * 0.06),
            int(height * 0.14),
            int(width * 0.88),
            int(height * 0.72),
        )
    elif layout == "scene":
        panel = None

    for y in range(height):
        u = y / max(1, height - 1)
        for x in range(width):
            t = x / max(1, width - 1)
            base_mix = 0.38 * t + 0.26 * u if layout == "scene" else 0.55 * t + 0.45 * u
            base = mix(bg_a, bg_b, base_mix)
            r, g, b = [float(c) for c in base]
            vignette = 1.0 - (0.34 if layout == "scene" else 0.5) * (((t - 0.5) ** 2) + ((u - 0.5) ** 2))
            r *= vignette
            g *= vignette
            b *= vignette
            for cx, cy, radius, strength in orbs:
                dx = x - cx
                dy = y - cy
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < radius:
                    w = (1.0 - dist / radius) ** 2 * strength
                    r += glow_rgb[0] * w
                    g += glow_rgb[1] * w
                    b += glow_rgb[2] * w

            if layout != "scene":
                diag = math.sin((x * 0.012) + (y * 0.006) + phase)
                if diag > 0.92:
                    r += glow_rgb[0] * 0.25
                    g += glow_rgb[1] * 0.25
                    b += glow_rgb[2] * 0.25

            scan = (0.99 + 0.01 * math.sin((y * 0.04) + phase * 0.8)) if layout == "scene" else (0.9 + 0.1 * math.sin((y * 0.09) + phase * 2.0))
            r *= scan
            g *= scan
            b *= scan

            if panel:
                px, py, pw, ph = panel
                if px <= x <= px + pw and py <= y <= py + ph:
                    overlay = 0.82 if layout == "banner" else 0.42
                    r = r * (1.0 - overlay) + panel_rgb[0] * overlay
                    g = g * (1.0 - overlay) + panel_rgb[1] * overlay
                    b = b * (1.0 - overlay) + panel_rgb[2] * overlay

            if layout == "status":
                thirds = [0.05, 0.365, 0.68]
                colors = [hex_rgb("#0f766e"), hex_rgb("#b45309"), hex_rgb("#4338ca")]
                for idx, start in enumerate(thirds):
                    tile_x = int(start * width)
                    tile_w = int(width * 0.26)
                    tile_y = int(height * 0.18)
                    tile_h = int(height * 0.58)
                    if tile_x <= x <= tile_x + tile_w and tile_y <= y <= tile_y + tile_h:
                        c = colors[idx]
                        overlay = 0.52
                        r = r * (1.0 - overlay) + c[0] * overlay
                        g = g * (1.0 - overlay) + c[1] * overlay
                        b = b * (1.0 - overlay) + c[2] * overlay

            idx = (y * width + x) * 4
            pixels[idx] = clamp8(r)
            pixels[idx + 1] = clamp8(g)
            pixels[idx + 2] = clamp8(b)
            pixels[idx + 3] = 255
    return pixels


def _scene_hits(*values: object) -> set[str]:
    lowered = " ".join(str(value or "").lower() for value in values)
    hits: set[str] = set()
    for token, label in (
        ("receipt", "receipt"),
        ("provenance", "receipt"),
        ("modifier", "receipt"),
        ("fingerprint", "receipt"),
        ("signal", "signal"),
        ("x-ray", "xray"),
        ("xray", "xray"),
        ("simulation", "simulation"),
        ("alice", "simulation"),
        ("ghost", "ghost"),
        ("replay", "ghost"),
        ("dossier", "dossier"),
        ("jackpoint", "dossier"),
        ("forge", "forge"),
        ("karma forge", "forge"),
        ("network", "network"),
        ("heat web", "network"),
        ("thread", "network"),
        ("mirror", "mirror"),
        ("passport", "passport"),
        ("blackbox", "blackbox"),
        ("loadout", "blackbox"),
        ("archive", "archive"),
        ("workshop", "workshop"),
        ("table", "table"),
        ("gm", "table"),
        ("phone", "phone"),
        ("train", "train"),
        ("bench", "workshop"),
        ("blueprint", "archive"),
        ("runner", "runner"),
        ("woman", "woman"),
        ("girl", "woman"),
        ("troll", "troll"),
        ("city", "city"),
        ("boulevard", "city"),
        ("street", "street"),
        ("storefront", "street"),
        ("map", "district"),
        ("district", "district"),
    ):
        if token in lowered:
            hits.add(label)
    return hits


def _composition_kind(raw: object) -> str:
    text = str(raw or "").lower().strip()
    if not text:
        return "single_protagonist"
    if "boulevard" in text or "avenue" in text:
        return "horizon_boulevard"
    if "district" in text or "map" in text:
        return "district_map"
    if "safehouse" in text:
        return "safehouse_table"
    if "simulation" in text:
        return "simulation_lab"
    if "xray" in text or "x-ray" in text:
        return "rule_xray"
    if "replay" in text or "forensic" in text:
        return "forensic_replay"
    if "dossier" in text:
        return "dossier_desk"
    if "passport" in text:
        return "passport_gate"
    if "loadout" in text or "blackbox" in text:
        return "loadout_table"
    if "mirror" in text:
        return "mirror_split"
    if "conspiracy" in text or "heat" in text:
        return "conspiracy_wall"
    if "group" in text or "table" in text:
        return "group_table"
    if "desk" in text or "still" in text:
        return "desk_still_life"
    if "archive" in text:
        return "archive_room"
    if "workshop" in text or "bench" in text:
        return "workshop"
    if "street" in text or "front" in text or "city" in text:
        return "street_front"
    if "single" in text or "hero" in text or "close" in text or "protagonist" in text:
        return "single_protagonist"
    return text


def _draw_person(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    x: float,
    y: float,
    scale: float,
    color: tuple[int, int, int],
    alpha: float,
    female: bool = False,
    troll: bool = False,
) -> None:
    head_radius = 24 * scale if troll else 18 * scale
    shoulder_w = 74 * scale if troll else 58 * scale if female else 64 * scale
    torso_w = 46 * scale if female else 54 * scale
    torso_h = 124 * scale if troll else 102 * scale
    coat_w = torso_w + (24 * scale if female else 18 * scale)
    hip_y = y + 52 * scale
    overlay_circle(pixels, width, height, cx=x, cy=y - 58 * scale, radius=head_radius, color=color, alpha=alpha * 0.96)
    if female:
        overlay_line(pixels, width, height, x1=x - 10 * scale, y1=y - 74 * scale, x2=x - 28 * scale, y2=y - 18 * scale, color=color, alpha=alpha * 0.48, thickness=max(2, int(7 * scale)))
        overlay_line(pixels, width, height, x1=x + 10 * scale, y1=y - 74 * scale, x2=x + 28 * scale, y2=y - 18 * scale, color=color, alpha=alpha * 0.48, thickness=max(2, int(7 * scale)))
    overlay_rect(pixels, width, height, x=int(x - shoulder_w / 2), y=int(y - 26 * scale), w=int(shoulder_w), h=int(22 * scale), color=color, alpha=alpha * 0.36)
    overlay_rect(
        pixels,
        width,
        height,
        x=int(x - torso_w / 2),
        y=int(y - 2 * scale),
        w=int(torso_w),
        h=int(torso_h * 0.78),
        color=color,
        alpha=alpha * 0.82,
    )
    overlay_line(pixels, width, height, x1=x - coat_w / 2, y1=y + 18 * scale, x2=x, y2=y + torso_h, color=color, alpha=alpha * 0.40, thickness=max(2, int(7 * scale)))
    overlay_line(pixels, width, height, x1=x + coat_w / 2, y1=y + 18 * scale, x2=x, y2=y + torso_h, color=color, alpha=alpha * 0.40, thickness=max(2, int(7 * scale)))
    overlay_line(pixels, width, height, x1=x - shoulder_w / 2, y1=y - 8 * scale, x2=x - 72 * scale, y2=y + 30 * scale, color=color, alpha=alpha * 0.88, thickness=max(2, int(7 * scale)))
    overlay_line(pixels, width, height, x1=x + shoulder_w / 2, y1=y - 12 * scale, x2=x + 68 * scale, y2=y + 12 * scale, color=color, alpha=alpha * 0.88, thickness=max(2, int(7 * scale)))
    overlay_rect(pixels, width, height, x=int(x - 22 * scale), y=int(hip_y), w=int(13 * scale), h=int(80 * scale), color=color, alpha=alpha * 0.88)
    overlay_rect(pixels, width, height, x=int(x + 9 * scale), y=int(hip_y), w=int(13 * scale), h=int(76 * scale), color=color, alpha=alpha * 0.88)
    overlay_rect(pixels, width, height, x=int(x - 24 * scale), y=int(hip_y + 78 * scale), w=int(20 * scale), h=int(8 * scale), color=color, alpha=alpha * 0.52)
    overlay_rect(pixels, width, height, x=int(x + 6 * scale), y=int(hip_y + 74 * scale), w=int(20 * scale), h=int(8 * scale), color=color, alpha=alpha * 0.52)
    if female:
        overlay_line(pixels, width, height, x1=x - 14 * scale, y1=y - 46 * scale, x2=x - 30 * scale, y2=y + 8 * scale, color=color, alpha=alpha * 0.62, thickness=max(2, int(7 * scale)))
        overlay_line(pixels, width, height, x1=x + 14 * scale, y1=y - 46 * scale, x2=x + 30 * scale, y2=y + 8 * scale, color=color, alpha=alpha * 0.62, thickness=max(2, int(7 * scale)))
        overlay_line(pixels, width, height, x1=x - 18 * scale, y1=hip_y - 4 * scale, x2=x, y2=y + 104 * scale, color=color, alpha=alpha * 0.48, thickness=max(2, int(5 * scale)))
        overlay_line(pixels, width, height, x1=x + 18 * scale, y1=hip_y - 4 * scale, x2=x, y2=y + 104 * scale, color=color, alpha=alpha * 0.48, thickness=max(2, int(5 * scale)))
    if troll:
        overlay_line(pixels, width, height, x1=x - 16 * scale, y1=y - 76 * scale, x2=x - 32 * scale, y2=y - 88 * scale, color=color, alpha=alpha * 0.72, thickness=max(2, int(5 * scale)))
        overlay_line(pixels, width, height, x1=x + 16 * scale, y1=y - 76 * scale, x2=x + 32 * scale, y2=y - 88 * scale, color=color, alpha=alpha * 0.72, thickness=max(2, int(5 * scale)))


def _draw_terminal(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    x: int,
    y: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
    alpha: float = 0.18,
) -> None:
    overlay_rect(pixels, width, height, x=x, y=y, w=w, h=h, color=(18, 20, 34), alpha=min(0.92, alpha + 0.44))
    overlay_rect(pixels, width, height, x=x + 4, y=y + 4, w=max(18, w - 8), h=max(16, h - 8), color=color, alpha=alpha * 0.42)
    overlay_rect(pixels, width, height, x=x + 12, y=y + 12, w=max(16, w - 24), h=max(12, h - 26), color=glow, alpha=alpha * 0.56)
    overlay_rect(pixels, width, height, x=x + 18, y=y + 18, w=max(12, w - 80), h=8, color=(242, 248, 252), alpha=min(0.34, alpha + 0.10))
    overlay_line(pixels, width, height, x1=x + w * 0.18, y1=y + h, x2=x + w * 0.12, y2=y + h + 26, color=color, alpha=alpha * 0.9, thickness=3)
    overlay_line(pixels, width, height, x1=x + w * 0.82, y1=y + h, x2=x + w * 0.88, y2=y + h + 26, color=color, alpha=alpha * 0.9, thickness=3)


def _draw_card(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    x: int,
    y: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
    alpha: float = 0.18,
) -> None:
    overlay_rect(pixels, width, height, x=x, y=y, w=w, h=h, color=(22, 24, 38), alpha=0.78)
    overlay_rect(pixels, width, height, x=x + 4, y=y + 4, w=max(12, w - 8), h=max(12, h - 8), color=color, alpha=alpha)
    overlay_rect(pixels, width, height, x=x + 12, y=y + 14, w=max(16, w - 24), h=8, color=(242, 248, 252), alpha=0.24)
    overlay_rect(pixels, width, height, x=x + 12, y=y + h - 18, w=max(12, w - 44), h=6, color=glow, alpha=0.20)


def _draw_device(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    x: int,
    y: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    overlay_rect(pixels, width, height, x=x, y=y, w=w, h=h, color=(14, 16, 28), alpha=0.88)
    overlay_rect(pixels, width, height, x=x + 6, y=y + 6, w=max(20, w - 12), h=max(20, h - 12), color=color, alpha=0.36)
    overlay_rect(pixels, width, height, x=x + 18, y=y + 18, w=max(16, w - 36), h=max(16, h - 36), color=glow, alpha=0.34)
    overlay_rect(pixels, width, height, x=x + 14, y=y + h - 10, w=max(10, w - 28), h=4, color=(242, 248, 252), alpha=0.14)


def _draw_receipt_traces(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    glow: tuple[int, int, int],
    anchor: tuple[float, float],
    nodes: list[tuple[float, float]],
    alpha: float = 0.22,
) -> None:
    px, py = anchor
    for x, y in nodes:
        overlay_line(pixels, width, height, x1=px, y1=py, x2=x, y2=y, color=glow, alpha=alpha, thickness=3)
        overlay_circle(pixels, width, height, cx=x, cy=y, radius=10, color=glow, alpha=alpha * 1.6)
        px, py = x, y


def _draw_group_table(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    table_x = width * 0.54
    table_y = height * 0.60
    overlay_circle(pixels, width, height, cx=table_x, cy=table_y, radius=210, color=glow, alpha=0.10)
    overlay_rect(pixels, width, height, x=int(table_x - 250), y=int(table_y - 62), w=500, h=124, color=color, alpha=0.22)
    _draw_terminal(pixels, width, height, x=int(table_x - 110), y=int(table_y - 36), w=220, h=86, color=color, glow=glow, alpha=0.16)
    _draw_person(pixels, width, height, x=width * 0.34, y=height * 0.64, scale=1.04, color=color, alpha=0.66)
    _draw_person(pixels, width, height, x=width * 0.74, y=height * 0.58, scale=0.88, color=color, alpha=0.56)
    _draw_person(pixels, width, height, x=width * 0.56, y=height * 0.36, scale=0.94, color=color, alpha=0.54, female=True)
    _draw_receipt_traces(
        pixels,
        width,
        height,
        glow=glow,
        anchor=(table_x - 90, table_y - 6),
        nodes=[(table_x - 8, table_y - 18), (table_x + 82, table_y + 6)],
        alpha=0.22,
    )


def _draw_skyline(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    baseline = int(height * 0.72)
    widths = [70, 92, 58, 110, 76, 64, 90, 52]
    heights = [180, 230, 140, 280, 190, 160, 220, 130]
    x = 36
    for idx, (w, h) in enumerate(zip(widths, heights)):
        overlay_rect(pixels, width, height, x=x, y=baseline - h, w=w, h=h, color=color, alpha=0.28)
        overlay_rect(pixels, width, height, x=x + 10, y=baseline - h + 18, w=max(10, w - 20), h=8, color=glow, alpha=0.26)
        if idx % 2 == 0:
            overlay_line(pixels, width, height, x1=x + w / 2, y1=baseline - h, x2=x + w / 2, y2=baseline - h - 36, color=glow, alpha=0.22, thickness=2)
        x += w + 24
    for sx, sy, sw in ((170, baseline - 250, 92), (468, baseline - 206, 108), (840, baseline - 238, 116)):
        overlay_rect(pixels, width, height, x=sx, y=sy, w=sw, h=24, color=glow, alpha=0.18)


def _draw_boulevard(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    horizon_y = int(height * 0.38)
    vanishing_x = width * 0.52
    overlay_rect(pixels, width, height, x=0, y=horizon_y + 150, w=width, h=height - horizon_y - 150, color=(20, 18, 34), alpha=0.72)
    for start_x, end_x in ((120, vanishing_x - 36), (280, vanishing_x - 14), (width - 120, vanishing_x + 36), (width - 280, vanishing_x + 14)):
        overlay_line(pixels, width, height, x1=start_x, y1=height - 8, x2=end_x, y2=horizon_y, color=glow, alpha=0.18, thickness=6)
    _draw_skyline(pixels, width, height, color=color, glow=glow)
    storefronts = [
        (96, 180, 162, 208),
        (292, 150, 196, 226),
        (540, 194, 170, 170),
        (760, 160, 182, 210),
        (974, 134, 172, 238),
    ]
    for x, y, w, h in storefronts:
        overlay_rect(pixels, width, height, x=x, y=y, w=w, h=h, color=(18, 20, 36), alpha=0.74)
        overlay_rect(pixels, width, height, x=x + 8, y=y + 12, w=w - 16, h=18, color=glow, alpha=0.26)
        overlay_rect(pixels, width, height, x=x + 10, y=y + 40, w=w - 20, h=h - 54, color=color, alpha=0.18)
        overlay_rect(pixels, width, height, x=x + int(w * 0.18), y=y + h - 78, w=int(w * 0.16), h=54, color=glow, alpha=0.18)
        overlay_rect(pixels, width, height, x=x + int(w * 0.62), y=y + h - 86, w=int(w * 0.16), h=62, color=glow, alpha=0.14)


def _draw_safehouse_operator_scene(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
    female: bool = False,
) -> None:
    overlay_rect(pixels, width, height, x=120, y=454, w=1040, h=84, color=(20, 16, 32), alpha=0.80)
    overlay_rect(pixels, width, height, x=900, y=120, w=204, h=252, color=(18, 16, 28), alpha=0.42)
    overlay_rect(pixels, width, height, x=918, y=142, w=168, h=214, color=color, alpha=0.10)
    _draw_device(pixels, width, height, x=554, y=286, w=282, h=124, color=color, glow=glow)
    _draw_device(pixels, width, height, x=394, y=338, w=138, h=86, color=color, glow=glow)
    _draw_card(pixels, width, height, x=728, y=352, w=148, h=70, color=color, glow=glow, alpha=0.16)
    _draw_card(pixels, width, height, x=852, y=330, w=116, h=64, color=color, glow=glow, alpha=0.14)
    _draw_person(pixels, width, height, x=340, y=330, scale=1.26, color=color, alpha=0.78, female=female)
    _draw_person(pixels, width, height, x=860, y=350, scale=0.98, color=color, alpha=0.22, female=False)
    _draw_person(pixels, width, height, x=980, y=330, scale=0.88, color=color, alpha=0.14, female=True)
    _draw_receipt_traces(
        pixels,
        width,
        height,
        glow=glow,
        anchor=(470, 352),
        nodes=[(620, 332), (720, 316), (784, 340)],
        alpha=0.24,
    )
    overlay_circle(pixels, width, height, cx=438, cy=314, radius=10, color=glow, alpha=0.30)
    overlay_circle(pixels, width, height, cx=820, cy=274, radius=8, color=glow, alpha=0.24)
    overlay_rect(pixels, width, height, x=222, y=386, w=84, h=16, color=glow, alpha=0.14)
    overlay_rect(pixels, width, height, x=304, y=384, w=22, h=22, color=(252, 108, 133), alpha=0.24)


def _draw_simulation_lab_scene(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
    female: bool = True,
) -> None:
    _draw_grid(pixels, width, height, color=color, glow=glow)
    _draw_person(pixels, width, height, x=width * 0.44, y=height * 0.54, scale=1.22, color=color, alpha=0.82, female=female)
    _draw_person(pixels, width, height, x=width * 0.62, y=height * 0.48, scale=0.96, color=glow, alpha=0.22, female=female)
    _draw_person(pixels, width, height, x=width * 0.78, y=height * 0.42, scale=0.90, color=(252, 108, 133), alpha=0.18, female=female)
    _draw_device(pixels, width, height, x=164, y=214, w=150, h=86, color=color, glow=glow)
    _draw_card(pixels, width, height, x=726, y=244, w=184, h=94, color=color, glow=glow, alpha=0.18)
    _draw_card(pixels, width, height, x=922, y=228, w=152, h=92, color=color, glow=glow, alpha=0.16)
    _draw_receipt_traces(
        pixels,
        width,
        height,
        glow=glow,
        anchor=(468, 430),
        nodes=[(610, 330), (744, 390), (936, 250)],
        alpha=0.24,
    )


def _draw_rule_xray_scene(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    overlay_rect(pixels, width, height, x=132, y=392, w=1012, h=118, color=(18, 20, 34), alpha=0.78)
    _draw_person(pixels, width, height, x=332, y=318, scale=1.20, color=color, alpha=0.76)
    _draw_device(pixels, width, height, x=514, y=290, w=230, h=108, color=color, glow=glow)
    overlay_circle(pixels, width, height, cx=338, cy=262, radius=126, color=glow, alpha=0.08)
    _draw_xray(pixels, width, height, glow=glow)
    _draw_receipt_traces(
        pixels,
        width,
        height,
        glow=glow,
        anchor=(534, 344),
        nodes=[(648, 328), (780, 290), (900, 250)],
        alpha=0.20,
    )


def _draw_mirror_split_scene(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    _draw_person(pixels, width, height, x=width * 0.36, y=height * 0.48, scale=1.08, color=color, alpha=0.66, female=True)
    for x1, y1, x2, y2 in ((640, 118, 918, 602), (706, 130, 1088, 612), (820, 104, 1180, 582)):
        overlay_line(pixels, width, height, x1=x1, y1=y1, x2=x2, y2=y2, color=glow, alpha=0.18, thickness=4)
    _draw_person(pixels, width, height, x=width * 0.74, y=height * 0.42, scale=0.88, color=glow, alpha=0.20, female=True)
    _draw_person(pixels, width, height, x=width * 0.82, y=height * 0.46, scale=0.78, color=glow, alpha=0.12, female=True)


def _draw_loadout_scene(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    overlay_rect(pixels, width, height, x=130, y=330, w=1020, h=220, color=(18, 20, 32), alpha=0.74)
    for x, y, w, h in ((180, 360, 180, 70), (404, 368, 142, 60), (612, 354, 170, 86), (842, 362, 210, 72), (310, 456, 160, 58), (620, 458, 240, 58)):
        _draw_card(pixels, width, height, x=x, y=y, w=w, h=h, color=color, glow=glow, alpha=0.14)
    overlay_circle(pixels, width, height, cx=972, cy=396, radius=18, color=(252, 108, 133), alpha=0.32)


def _draw_conspiracy_wall(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    overlay_rect(pixels, width, height, x=148, y=126, w=964, h=436, color=(18, 20, 32), alpha=0.72)
    for x, y, w, h in ((190, 168, 164, 94), (418, 142, 188, 102), (708, 176, 160, 88), (940, 146, 132, 94), (278, 332, 176, 94), (566, 346, 208, 102), (860, 324, 152, 92)):
        _draw_card(pixels, width, height, x=x, y=y, w=w, h=h, color=color, glow=glow, alpha=0.14)
    _draw_network(
        pixels,
        width,
        height,
        color=(252, 108, 133),
        glow=glow,
        nodes=[(272, 208), (516, 194), (792, 220), (980, 194), (366, 380), (668, 396), (924, 372)],
    )


def _draw_passport_scene(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    _draw_terminal(pixels, width, height, x=180, y=220, w=230, h=300, color=color, glow=glow, alpha=0.14)
    _draw_person(pixels, width, height, x=720, y=340, scale=1.02, color=color, alpha=0.62, female=False)
    overlay_line(pixels, width, height, x1=480, y1=180, x2=840, y2=180, color=glow, alpha=0.24, thickness=4)
    overlay_line(pixels, width, height, x1=840, y1=180, x2=980, y2=320, color=glow, alpha=0.24, thickness=4)
    overlay_circle(pixels, width, height, cx=980, cy=320, radius=12, color=glow, alpha=0.30)


def _draw_forensic_replay_scene(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    _draw_person(pixels, width, height, x=width * 0.36, y=height * 0.50, scale=0.96, color=color, alpha=0.18)
    _draw_person(pixels, width, height, x=width * 0.42, y=height * 0.46, scale=0.96, color=color, alpha=0.34)
    _draw_person(pixels, width, height, x=width * 0.50, y=height * 0.42, scale=0.96, color=color, alpha=0.62)
    _draw_receipt_traces(
        pixels,
        width,
        height,
        glow=glow,
        anchor=(520, 340),
        nodes=[(646, 300), (772, 272), (938, 222)],
        alpha=0.18,
    )


def _draw_archive_room(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    overlay_rect(pixels, width, height, x=120, y=150, w=1040, h=410, color=color, alpha=0.10)
    for x in (150, 300, 950, 1100):
        overlay_rect(pixels, width, height, x=x, y=170, w=70, h=320, color=color, alpha=0.22)
    overlay_rect(pixels, width, height, x=500, y=170, w=280, h=320, color=glow, alpha=0.10)
    overlay_rect(pixels, width, height, x=548, y=220, w=184, h=222, color=(244, 248, 252), alpha=0.10)
    for y in (210, 270, 330, 390):
        overlay_rect(pixels, width, height, x=180, y=y, w=80, h=16, color=glow, alpha=0.16)
        overlay_rect(pixels, width, height, x=990, y=y, w=80, h=16, color=glow, alpha=0.16)


def _draw_workshop_scene(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
    female: bool = False,
) -> None:
    overlay_rect(pixels, width, height, x=150, y=430, w=980, h=120, color=color, alpha=0.20)
    overlay_rect(pixels, width, height, x=890, y=160, w=170, h=200, color=glow, alpha=0.10)
    _draw_person(pixels, width, height, x=360, y=352, scale=1.08, color=color, alpha=0.64, female=female)
    for x, y in ((640, 320), (688, 292), (740, 346), (792, 302), (852, 338), (914, 280)):
        overlay_line(pixels, width, height, x1=612, y1=404, x2=x, y2=y, color=glow, alpha=0.34, thickness=4)
        overlay_circle(pixels, width, height, cx=x, cy=y, radius=8, color=glow, alpha=0.50)


def _draw_district_map(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    overlay_rect(pixels, width, height, x=160, y=160, w=960, h=420, color=(28, 34, 42), alpha=0.42)
    districts = [
        (220, 220, 180, 120),
        (450, 200, 210, 140),
        (730, 210, 200, 120),
        (260, 390, 220, 130),
        (560, 380, 260, 120),
    ]
    centers = []
    for x, y, w, h in districts:
        overlay_rect(pixels, width, height, x=x, y=y, w=w, h=h, color=color, alpha=0.22)
        overlay_rect(pixels, width, height, x=x + 14, y=y + 14, w=w - 28, h=20, color=glow, alpha=0.18)
        centers.append((x + w / 2, y + h / 2))
    for (x1, y1), (x2, y2) in zip(centers, centers[1:]):
        overlay_line(pixels, width, height, x1=x1, y1=y1, x2=x2, y2=y2, color=glow, alpha=0.26, thickness=4)
        overlay_circle(pixels, width, height, cx=x2, cy=y2, radius=10, color=glow, alpha=0.28)


def _draw_single_protagonist_scene(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
    female: bool = False,
    troll: bool = False,
) -> None:
    _draw_person(pixels, width, height, x=width * 0.40, y=height * 0.43, scale=1.26, color=color, alpha=0.68, female=female, troll=troll)
    overlay_rect(pixels, width, height, x=680, y=250, w=250, h=140, color=glow, alpha=0.12)
    overlay_rect(pixels, width, height, x=720, y=430, w=180, h=80, color=color, alpha=0.18)
    overlay_line(pixels, width, height, x1=520, y1=330, x2=740, y2=318, color=glow, alpha=0.24, thickness=4)
    overlay_circle(pixels, width, height, cx=740, cy=318, radius=14, color=glow, alpha=0.34)


def _draw_receipt_overlays(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    glow: tuple[int, int, int],
    hits: set[str],
) -> None:
    if "receipt" not in hits and "signal" not in hits and "xray" not in hits:
        return
    _draw_receipt_traces(
        pixels,
        width,
        height,
        glow=glow,
        anchor=(width * 0.48, height * 0.48),
        nodes=[(width * 0.60, height * 0.38), (width * 0.72, height * 0.44), (width * 0.82, height * 0.32)],
        alpha=0.12,
    )


def _draw_desk(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    overlay_rect(pixels, width, height, x=140, y=360, w=980, h=220, color=color, alpha=0.18)
    cards = [(220, 260, 160, 110), (450, 300, 180, 120), (720, 245, 210, 128), (950, 315, 150, 105)]
    centers: list[tuple[float, float]] = []
    for x, y, w, h in cards:
        overlay_rect(pixels, width, height, x=x, y=y, w=w, h=h, color=(236, 244, 248), alpha=0.18)
        overlay_rect(pixels, width, height, x=x + 10, y=y + 10, w=w - 20, h=12, color=glow, alpha=0.22)
        centers.append((x + w / 2, y + h / 2))
    for idx in range(len(centers) - 1):
        x1, y1 = centers[idx]
        x2, y2 = centers[idx + 1]
        overlay_line(pixels, width, height, x1=x1, y1=y1, x2=x2, y2=y2, color=glow, alpha=0.22, thickness=3)


def _draw_network(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    nodes = [(220, 210), (430, 170), (610, 280), (770, 150), (930, 245), (1080, 180)]
    for idx, (x, y) in enumerate(nodes):
        overlay_circle(pixels, width, height, cx=x, cy=y, radius=18 if idx % 2 else 14, color=glow, alpha=0.45)
        if idx:
            px, py = nodes[idx - 1]
            overlay_line(pixels, width, height, x1=px, y1=py, x2=x, y2=y, color=color, alpha=0.26, thickness=4)


def _draw_grid(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    for x in range(150, width - 90, 110):
        overlay_line(pixels, width, height, x1=x, y1=120, x2=x, y2=height - 110, color=color, alpha=0.10, thickness=2)
    for y in range(120, height - 110, 80):
        overlay_line(pixels, width, height, x1=140, y1=y, x2=width - 90, y2=y, color=color, alpha=0.10, thickness=2)
    for x1, y1, x2, y2 in ((320, 500, 520, 330), (520, 330, 760, 390), (760, 390, 980, 250)):
        overlay_line(pixels, width, height, x1=x1, y1=y1, x2=x2, y2=y2, color=glow, alpha=0.25, thickness=5)
        overlay_circle(pixels, width, height, cx=x2, cy=y2, radius=12, color=glow, alpha=0.42)
    _draw_person(pixels, width, height, x=width * 0.34, y=height * 0.50, scale=0.86, color=color, alpha=0.24, female=True)
    _draw_person(pixels, width, height, x=width * 0.68, y=height * 0.50, scale=0.86, color=color, alpha=0.16, female=True)
    overlay_rect(pixels, width, height, x=220, y=214, w=132, h=72, color=(252, 108, 133), alpha=0.10)
    overlay_rect(pixels, width, height, x=890, y=226, w=136, h=72, color=(64, 214, 164), alpha=0.12)


def _draw_xray(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    glow: tuple[int, int, int],
) -> None:
    cx = width * 0.44
    cy = height * 0.48
    overlay_circle(pixels, width, height, cx=cx, cy=cy - 120, radius=34, color=glow, alpha=0.22)
    overlay_line(pixels, width, height, x1=cx, y1=cy - 80, x2=cx, y2=cy + 150, color=glow, alpha=0.32, thickness=4)
    for offset in (-80, -46, -18, 18, 46, 80):
        overlay_line(pixels, width, height, x1=cx - 86, y1=cy + offset, x2=cx + 86, y2=cy + offset, color=glow, alpha=0.18, thickness=3)
    for x, y, w, h in ((760, 210, 170, 54), (820, 330, 148, 50), (720, 450, 160, 52)):
        overlay_rect(pixels, width, height, x=x, y=y, w=w, h=h, color=(236, 244, 248), alpha=0.10)
        overlay_rect(pixels, width, height, x=x + 8, y=y + 8, w=w - 16, h=10, color=glow, alpha=0.20)
        overlay_line(pixels, width, height, x1=cx + 20, y1=cy + 20, x2=x + 18, y2=y + h / 2, color=glow, alpha=0.22, thickness=3)


def _draw_forge(
    pixels: bytearray,
    width: int,
    height: int,
    *,
    color: tuple[int, int, int],
    glow: tuple[int, int, int],
) -> None:
    overlay_rect(pixels, width, height, x=420, y=470, w=220, h=70, color=color, alpha=0.26)
    overlay_rect(pixels, width, height, x=470, y=430, w=120, h=48, color=glow, alpha=0.22)
    for x, y in ((670, 330), (710, 295), (760, 360), (808, 305), (860, 345)):
        overlay_line(pixels, width, height, x1=620, y1=420, x2=x, y2=y, color=glow, alpha=0.35, thickness=4)
        overlay_circle(pixels, width, height, cx=x, cy=y, radius=6, color=glow, alpha=0.52)


def synth_context_scene_png(
    title: str,
    accent: str,
    glow: str,
    scene_contract: dict[str, object],
    *,
    scene_row: dict[str, object] | None = None,
    width: int = 1280,
    height: int = 720,
    layout: str = "banner",
) -> bytes:
    scene_layout = "status" if layout == "status" else "scene"
    pixels = synth_cyberpunk_pixels(title, accent, glow, width=width, height=height, layout=scene_layout)
    accent_rgb = hex_rgb(accent)
    glow_rgb = hex_rgb(glow)
    motifs = scene_row.get("visual_motifs", []) if isinstance(scene_row, dict) else []
    callouts = scene_row.get("overlay_callouts", []) if isinstance(scene_row, dict) else []
    hits = _scene_hits(
        title,
        scene_contract.get("subject", ""),
        scene_contract.get("environment", ""),
        scene_contract.get("action", ""),
        scene_contract.get("metaphor", ""),
        scene_contract.get("visual_prompt", ""),
        " ".join(str(entry) for entry in motifs if str(entry).strip()),
        " ".join(str(entry) for entry in callouts if str(entry).strip()),
    )
    composition = _composition_kind(scene_contract.get("composition", ""))
    female = "woman" in hits or title.strip().lower() == "alice"
    troll = "troll" in hits
    if composition == "safehouse_table":
        _draw_safehouse_operator_scene(pixels, width, height, color=accent_rgb, glow=glow_rgb, female=female)
    elif composition == "simulation_lab" or "simulation" in hits:
        _draw_simulation_lab_scene(pixels, width, height, color=accent_rgb, glow=glow_rgb, female=True)
    elif composition == "rule_xray" or "xray" in hits:
        _draw_rule_xray_scene(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    elif composition == "forensic_replay" or "ghost" in hits:
        _draw_forensic_replay_scene(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    elif composition == "mirror_split" or "mirror" in hits:
        _draw_mirror_split_scene(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    elif composition == "passport_gate" or "passport" in hits:
        _draw_passport_scene(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    elif composition == "loadout_table" or "blackbox" in hits:
        _draw_loadout_scene(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    elif composition == "dossier_desk":
        _draw_desk(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    elif composition == "conspiracy_wall":
        _draw_conspiracy_wall(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    elif composition == "group_table" and "forge" not in hits:
        _draw_safehouse_operator_scene(pixels, width, height, color=accent_rgb, glow=glow_rgb, female=female)
    elif composition == "group_table" and "forge" in hits:
        _draw_group_table(pixels, width, height, color=accent_rgb, glow=glow_rgb)
        _draw_forge(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    elif composition == "group_table" and "simulation" not in hits and "xray" not in hits:
        _draw_group_table(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    elif composition in {"desk_still_life"}:
        _draw_desk(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    elif composition == "archive_room":
        _draw_archive_room(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    elif composition == "district_map":
        _draw_district_map(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    elif composition in {"city_edge", "horizon_boulevard"}:
        _draw_boulevard(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    elif composition == "street_front":
        _draw_skyline(pixels, width, height, color=accent_rgb, glow=glow_rgb)
        _draw_skyline(pixels, width, height, color=accent_rgb, glow=glow_rgb)
        _draw_single_protagonist_scene(pixels, width, height, color=accent_rgb, glow=glow_rgb, female=female, troll=troll)
    elif composition == "workshop":
        _draw_workshop_scene(pixels, width, height, color=accent_rgb, glow=glow_rgb, female=female)
    else:
        _draw_single_protagonist_scene(pixels, width, height, color=accent_rgb, glow=glow_rgb, female=female, troll=troll)
    if "network" in hits:
        _draw_network(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    if "dossier" in hits and "blackbox" not in hits:
        _draw_desk(pixels, width, height, color=accent_rgb, glow=glow_rgb)
    if "forge" in hits:
        _draw_receipt_traces(
            pixels,
            width,
            height,
            glow=glow_rgb,
            anchor=(width * 0.50, height * 0.50),
            nodes=[(width * 0.62, height * 0.40), (width * 0.72, height * 0.46), (width * 0.80, height * 0.34)],
            alpha=0.14,
        )
    elif "receipt" in hits or "signal" in hits:
        _draw_receipt_overlays(pixels, width, height, glow=glow_rgb, hits=hits)

    return rgba_png(width, height, bytes(pixels))


def synth_cyberpunk_png(
    title: str,
    accent: str,
    glow: str,
    *,
    width: int = 1280,
    height: int = 720,
    phase: float = 0.0,
    layout: str = "banner",
) -> bytes:
    pixels = synth_cyberpunk_pixels(title, accent, glow, width=width, height=height, phase=phase, layout=layout)
    return rgba_png(width, height, bytes(pixels))


def hero_png() -> bytes:
    return synth_cyberpunk_png(
        "Chummer6",
        "#0f766e",
        "#34d399",
        layout="banner",
    )


def program_map_png() -> bytes:
    return synth_cyberpunk_png(
        "Program Map",
        "#1d4ed8",
        "#7dd3fc",
        layout="grid",
    )


def status_strip_png() -> bytes:
    return synth_cyberpunk_png(
        "Status Strip",
        "#4338ca",
        "#c084fc",
        layout="status",
    )


def horizon_fallback_png(title: str, subtitle: str, accent: str, glow: str) -> bytes:
    return synth_cyberpunk_png(title, accent, glow, layout="banner")


def write_binary(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def load_ea_media_manifest() -> dict[str, dict[str, object]]:
    if not EA_MEDIA_MANIFEST_PATH.exists():
        return {}
    try:
        loaded = json.loads(EA_MEDIA_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    assets = loaded.get("assets")
    if not isinstance(assets, list):
        return {}
    manifest: dict[str, dict[str, object]] = {}
    for row in assets:
        if not isinstance(row, dict):
            continue
        target = str(row.get("target", "")).strip()
        output = str(row.get("output", "")).strip()
        if not target or not output:
            continue
        manifest[target] = row
    return manifest


def ea_media_bytes_for(path: Path, manifest: dict[str, dict[str, object]]) -> bytes | None:
    try:
        rel = path.relative_to(GUIDE_REPO).as_posix()
    except ValueError:
        return None
    row = manifest.get(rel)
    if not row:
        alias = MEDIA_TARGET_ALIASES.get(rel)
        if alias:
            row = manifest.get(alias)
    if not row:
        return None
    output = Path(str(row.get("output", ""))).expanduser()
    if not output.exists() or not output.is_file():
        return None
    try:
        return output.read_bytes()
    except Exception:
        return None


def require_ea_media_bytes(path: Path, manifest: dict[str, dict[str, object]]) -> bytes:
    media_bytes = ea_media_bytes_for(path, manifest)
    if media_bytes is None:
        raise ValueError(f"missing EA-generated media asset: {path.relative_to(GUIDE_REPO).as_posix()}")
    return media_bytes


def write_assets() -> None:
    media_manifest = load_ea_media_manifest()
    hero_path = GUIDE_REPO / "assets" / "hero" / "chummer6-hero.png"
    poc_path = GUIDE_REPO / "assets" / "hero" / "poc-warning.png"
    write_binary(hero_path, require_ea_media_bytes(hero_path, media_manifest))
    write_binary(poc_path, require_ea_media_bytes(poc_path, media_manifest))
    for page_asset in (
        GUIDE_REPO / "assets" / "pages" / "start-here.png",
        GUIDE_REPO / "assets" / "pages" / "what-chummer6-is.png",
        GUIDE_REPO / "assets" / "pages" / "where-to-go-deeper.png",
        GUIDE_REPO / "assets" / "pages" / "current-phase.png",
        GUIDE_REPO / "assets" / "pages" / "current-status.png",
        GUIDE_REPO / "assets" / "pages" / "public-surfaces.png",
        GUIDE_REPO / "assets" / "pages" / "parts-index.png",
        GUIDE_REPO / "assets" / "pages" / "horizons-index.png",
    ):
        write_binary(page_asset, require_ea_media_bytes(page_asset, media_manifest))
    for part_slug in PARTS:
        target = GUIDE_REPO / "assets" / "parts" / f"{part_slug}.png"
        write_binary(target, require_ea_media_bytes(target, media_manifest))
    for slug, item in HORIZONS.items():
        target = GUIDE_REPO / "assets" / "horizons" / f"{slug}.png"
        write_binary(target, require_ea_media_bytes(target, media_manifest))


def page_markdown(title: str, body: str) -> str:
    return f"# {title}\n\n{body.strip()}\n"


def part_page(name: str, item: dict[str, object]) -> str:
    owns = "\n".join(f"- {line}" for line in item["owns"])
    not_owns = "\n".join(f"- {line}" for line in item["not_owns"])
    body = dedent(
        f"""
        ![{item['title']} banner](../assets/parts/{name}.png)

        **{item['tagline']}**

        {item['intro']}

        ## Why you should care

        {item['why']}

        ## What it owns

        {owns}

        ## What it does not own

        {not_owns}

        ## What is happening now

        {item['now']}

        ## Go deeper

        - [Program map](README.md)
        - [Current phase](../NOW/current-phase.md)
        - [Where to go deeper](../WHERE_TO_GO_DEEPER.md)
        """
    ) + footer("chummer6-design ownership map", "current public shape", "owning repo READMEs")
    return page_markdown(str(item["title"]), body)


def horizon_page(slug: str, item: dict[str, object]) -> str:
    title = str(item["title"])
    foundations = "\n".join(f"- {line}" for line in item["foundations"])
    repos = "\n".join(f"- `{repo}`" for repo in item["repos"])
    why_wiz = str(item.get("why_wiz") or item.get("hook") or "").strip()
    idea = str(item.get("idea") or item.get("hook") or "").strip()
    problem = str(item.get("problem") or item.get("brutal_truth") or "").strip()
    why_waits = str(item.get("why_waits") or item.get("not_now") or "It stays parked in the garage until the current foundation work is actually done.").strip()
    body = (
        f"![{title} banner](../assets/horizons/{slug}.png)\n\n"
        f"**{item['hook']}**\n\n"
        "_Status: Horizon only — future idea, not active build work._\n\n"
        "## Why this would be wiz\n\n"
        f"{why_wiz}\n\n"
        "## The brutal truth\n\n"
        f"{item['brutal_truth']}\n\n"
        "## The use case\n\n"
        f"{item['use_case']}\n\n"
        "## What is the idea?\n\n"
        f"{idea}\n\n"
        "## What problem does it solve?\n\n"
        f"{problem}\n\n"
        "## Foundations first\n\n"
        f"{foundations}\n\n"
        "## Which parts would it touch later?\n\n"
        f"{repos}\n\n"
        "## Why it waits\n\n"
        f"{why_waits}\n"
        + footer("chummer6-design horizon guidance", "current public shape")
    )
    return page_markdown(title, body)


def write_guide_repo() -> None:
    write_assets()
    why_care_lines = indented_bullets(required_ooda_list("why_care")[:4])
    current_focus_lines = indented_bullets(required_ooda_list("current_focus")[:5])
    promise = required_ooda_text("promise")
    tension = required_ooda_text("tension")
    landing_tagline = required_ooda_text("landing_tagline")
    what_it_is = required_ooda_text("what_it_is")
    watch_intro = required_ooda_text("watch_intro")
    horizon_intro = required_ooda_text("horizon_intro")
    readme_intro = required_page_override_text("readme", "intro")
    readme_body = required_page_override_text("readme", "body")
    start_here_intro = required_page_override_text("start_here", "intro")
    start_here_body = required_page_override_text("start_here", "body")
    what_intro = required_page_override_text("what_chummer6_is", "intro")
    what_body = required_page_override_text("what_chummer6_is", "body")
    deeper_intro = required_page_override_text("where_to_go_deeper", "intro")
    deeper_body = required_page_override_text("where_to_go_deeper", "body")
    current_phase_intro = required_page_override_text("current_phase", "intro")
    current_phase_body = required_page_override_text("current_phase", "body")
    current_status_intro = required_page_override_text("current_status", "intro")
    current_status_body = required_page_override_text("current_status", "body")
    public_surfaces_intro = required_page_override_text("public_surfaces", "intro")
    public_surfaces_body = required_page_override_text("public_surfaces", "body")
    parts_index_intro = required_page_override_text("parts_index", "intro")
    parts_index_body = required_page_override_text("parts_index", "body")
    horizons_index_intro = required_page_override_text("horizons_index", "intro")
    horizons_index_body = required_page_override_text("horizons_index", "body")

    write_text(
        GUIDE_REPO / "README.md",
        page_markdown(
            "Chummer6",
            dedent(
                f"""
                ![Chummer6 hero banner](assets/hero/chummer6-hero.png)

                > **{landing_tagline}**
                >
                > {readme_intro}

                {readme_body}

                No, this is not the code repo.  
                No, you do not need a flowchart and three espressos to understand the program.  
                That is the whole reason this repo exists.

                ## Pick your path

                - **I’m new here:** [Start Here](START_HERE.md)
                - **Give me the two-minute version:** [What Chummer6 is](WHAT_CHUMMER6_IS.md)
                - **What is happening right now?** [Current status](NOW/current-status.md)
                - **How do the parts fit together?** [Program map](PARTS/README.md)
                - **What are the future rabbit holes?** [Horizons](HORIZONS/README.md)
                - **Where should I go deeper?** [Where to go deeper](WHERE_TO_GO_DEEPER.md)

                ## What Chummer6 is

                {what_it_is}

                Think of it like this:

                - `chummer6-design` is the blueprint room
                - the code repos are the workshops
                - **Chummer6 is the map on the wall**

                ## Why this is worth watching

                {promise}

                {watch_intro}

{why_care_lines}

                ## What’s happening now

                ![Current status banner](assets/pages/current-status.png)

                Right now the crew is doing foundation work, not bolting neon spoilers onto half-built engines.
                {tension}

                Current focus:
{current_focus_lines}
                - keep public previews honestly labeled until they become the real thing

                Read more: [Current phase](NOW/current-phase.md)

                ## Meet the parts

                ![Parts overview](assets/pages/parts-index.png)

                <table>
                  <tr>
                    <td align="center"><a href="PARTS/core.md"><img src="assets/parts/core.png" alt="Core" width="300"><br><strong>Core</strong><br><em>The deterministic rules engine</em></a></td>
                    <td align="center"><a href="PARTS/ui.md"><img src="assets/parts/ui.png" alt="UI" width="300"><br><strong>UI</strong><br><em>The workbench and big-screen UX</em></a></td>
                    <td align="center"><a href="PARTS/mobile.md"><img src="assets/parts/mobile.png" alt="Mobile" width="300"><br><strong>Mobile</strong><br><em>The player and GM shell</em></a></td>
                    <td align="center"><a href="PARTS/hub.md"><img src="assets/parts/hub.png" alt="Hub" width="300"><br><strong>Hub</strong><br><em>The hosted API and orchestration layer</em></a></td>
                  </tr>
                  <tr>
                    <td align="center"><a href="PARTS/ui-kit.md"><img src="assets/parts/ui-kit.png" alt="UI kit" width="300"><br><strong>UI kit</strong><br><em>Shared chrome and visual primitives</em></a></td>
                    <td align="center"><a href="PARTS/hub-registry.md"><img src="assets/parts/hub-registry.png" alt="Hub registry" width="300"><br><strong>Hub registry</strong><br><em>Artifacts, installs, and compatibility</em></a></td>
                    <td align="center"><a href="PARTS/media-factory.md"><img src="assets/parts/media-factory.png" alt="Media factory" width="300"><br><strong>Media factory</strong><br><em>Render-only asset lifecycle</em></a></td>
                    <td align="center"><a href="PARTS/design.md"><img src="assets/parts/design.png" alt="Design" width="300"><br><strong>Design</strong><br><em>The long-range blueprint room</em></a></td>
                  </tr>
                </table>

                ## Horizon ideas

                ![Horizons overview](assets/pages/horizons-index.png)

                {horizon_intro}

                <table>
                  <tr>
                    <td align="center"><a href="HORIZONS/karma-forge.md"><img src="assets/horizons/karma-forge.png" alt="Karma Forge" width="300"><br><strong>KARMA FORGE</strong><br><em>Personalized rule stacks without fork chaos</em></a></td>
                    <td align="center"><a href="HORIZONS/nexus-pan.md"><img src="assets/horizons/nexus-pan.png" alt="NEXUS-PAN" width="300"><br><strong>NEXUS-PAN</strong><br><em>A live synced table instead of lonely files</em></a></td>
                    <td align="center"><a href="HORIZONS/alice.md"><img src="assets/horizons/alice.png" alt="ALICE" width="300"><br><strong>ALICE</strong><br><em>Stress-test a build before the run</em></a></td>
                  </tr>
                  <tr>
                    <td align="center"><a href="HORIZONS/jackpoint.md"><img src="assets/horizons/jackpoint.png" alt="JACKPOINT" width="300"><br><strong>JACKPOINT</strong><br><em>Turn grounded data into dossiers and briefings</em></a></td>
                    <td align="center"><a href="HORIZONS/ghostwire.md"><img src="assets/horizons/ghostwire.png" alt="GHOSTWIRE" width="300"><br><strong>GHOSTWIRE</strong><br><em>Replay a run like a forensic sim</em></a></td>
                    <td align="center"><a href="HORIZONS/rule-x-ray.md"><img src="assets/horizons/rule-x-ray.png" alt="RULE X-RAY" width="300"><br><strong>RULE X-RAY</strong><br><em>Click any number and see where it came from</em></a></td>
                  </tr>
                </table>

                See all: [Horizon index](HORIZONS/README.md)

                ## What you can do

                If this repo helped you get your bearings, here’s how to help back:

                - **Give Chummer6 a star** if this guide saved you from digging through half the Matrix just to understand what is going on.
                - **Be my test dummy and install the software.**
                - **Grab the latest POC build from [Releases](https://github.com/ArchonMegalon/Chummer6/releases)** when one is available.
                - **Seriously: never trust software. Never trust a dev.**
                - **If the build starts acting like a recruiter for chaos, close the lid and write down the steps.**
                - **If the build does something cursed, tell us exactly which click woke the gremlin.**
                - **If this repo is stale, confusing, or reads like corp training material, call it out.**

                > **Street warning:** POC builds are for curious chummers, not cautious wageslaves.  
                > They may be unstable, unfinished, weird, or one bad click away from getting your deck **marked, hacked, or bricked**.  
                > Install at your own risk.

                In other words: kick the tires, break the thing, and tell me where the smoke came out.

                ## POC shelf

                ![POC warning banner](assets/hero/poc-warning.png)

                If there is a fresh proof-of-concept build ready for brave idiots and helpful test dummies, the shelf is here:

                - [Chummer6 Releases](https://github.com/ArchonMegalon/Chummer6/releases)

                The binaries themselves come from the active Chummer6 codebase, not from this guide repo.

                ## Where to go deeper

                Chummer6 explains. It does not ship code and it does not replace the blueprint.

                - The long-range plan lives in `chummer6-design`
                - The software itself lives in the owning code repos
                - Chummer6 is the friendly guide for humans
                """
            )
            + footer("chummer6-design", "public repo READMEs", "current public shape"),
        ),
    )

    write_text(
        GUIDE_REPO / "START_HERE.md",
        page_markdown(
            "Start Here",
            dedent(
                f"""
                ![Start here banner](assets/pages/start-here.png)

                Welcome to Chummer6.

                {start_here_intro}

                {start_here_body}

                Chummer is already becoming a set of focused parts: a rules engine, a workbench, a play shell, hosted services, a shared UI layer, an artifact registry, a media pipeline, and a blueprint repo that keeps the long game straight.

                You do **not** need to memorize that on day one.

                ## The shortest possible explanation

                Chummer6 exists so you can answer three questions quickly:

                - What is this program becoming?
                - Which part does what?
                - What is real now, and what is still future-looking?

                ## If you only read three pages

                1. [What Chummer6 is](WHAT_CHUMMER6_IS.md)
                2. [What’s happening now](NOW/current-status.md)
                3. [How the parts fit together](PARTS/README.md)

                ## If you are here for the fun stuff

                Go to [Horizons](HORIZONS/README.md).

                ## If you want the blueprint

                Go to [Where to go deeper](WHERE_TO_GO_DEEPER.md).
                """
            )
            + footer("chummer6-design README", "public repo READMEs"),
        ),
    )

    write_text(
        GUIDE_REPO / "WHAT_CHUMMER6_IS.md",
        page_markdown(
            "What Chummer6 Is",
            dedent(
                f"""
                ![What Chummer6 is banner](assets/pages/what-chummer6-is.png)

                {what_intro}

                {what_body}

                ## The short version

                Chummer6 is here to answer the human questions first:

                - What is this thing becoming?
                - Why are there so many moving parts?
                - What is actually happening right now?
                - Which ideas are real work, and which ones are still parked in the garage?

                ## What it does for players and GMs

                This guide exists to make the product legible before you ever need to care about repo boundaries:

                - what Chummer6 is becoming at the table
                - which part solves which kind of problem
                - what is real now versus still horizon material
                - where to go next when you want depth instead of mystery

                ## Why there are multiple parts

                The split is there so each promise can stay honest:

                - `core` keeps the rules truth deterministic
                - `ui` keeps the big-screen workbench clean
                - `mobile` keeps the table-facing shell local-first
                - `hub` keeps hosted coordination from swallowing everything else
                - the supporting repos keep chrome, registry, media, design, and guide duties out of each other’s way

                ## Who this helps

                - curious newcomers
                - returning Chummer users
                - contributors who want the lay of the land before diving into the heavy stuff
                - test dummies brave enough to click the POC shelf

                ## What it intentionally does not do

                Chummer6 is not the blueprint room, not a code repo, and not a place that gets to declare what the software must do next.

                It is the visitor center. The map on the wall. The place you walk through before you wander deeper into the arcology.

                And yes: if the dev does something particularly cursed, the guide is allowed to make fun of them a little.

                ## How to use it

                If you want the quick orientation, start with [Start Here](START_HERE.md).  
                If you want the current shape, go to [NOW/current-status.md](NOW/current-status.md).  
                If you want the weird future stuff, go to [HORIZONS/README.md](HORIZONS/README.md).
                """
            )
            + footer("chummer6-design", "current public shape"),
        ),
    )

    write_text(
        GUIDE_REPO / "WHERE_TO_GO_DEEPER.md",
        page_markdown(
            "Where To Go Deeper",
            dedent(
                f"""
                ![Where to go deeper banner](assets/pages/where-to-go-deeper.png)

                {deeper_intro}

                {deeper_body}

                ## Start here when you want more than the tour

                - Start with `chummer6-design` when you want the long-range plan, the split story, and the blueprint.
                - Go to the owning code repos when you want the software itself.
                - Come back to Chummer6 when you want the human-readable version again.

                ## What each place is for

                - `chummer6-design`: the blueprint room
                - owning repos: the working software and repo-specific detail
                - Chummer6: the visitor center and field guide

                ## What to do when you spot drift

                Fix Chummer6 first.  
                Do **not** “correct” the blueprint because the visitor guide got ahead of itself.
                """
            )
            + footer("chummer6-design scope rules", "current public shape"),
        ),
    )

    write_text(
        GUIDE_REPO / "NOW" / "current-phase.md",
        page_markdown(
            "Current Phase",
            dedent(
                f"""
                ![Current phase banner](../assets/pages/current-phase.png)

                {current_phase_intro}

                {current_phase_body}

                ## The focus right now

                - finish the contract reset
                - finish the play/session boundary
                - make the shared UI kit a real package seam
                - finish the registry and media boundaries
                - keep public previews honestly labeled until they become the real thing

                ## Why that matters

                This is the work that makes later wow-ideas cheap instead of chaotic.

                No neon spoiler matters if the frame is still loose.
                """
            )
            + footer("chummer6-design vision", "current public shape"),
        ),
    )

    write_text(
        GUIDE_REPO / "NOW" / "current-status.md",
        page_markdown(
            "Current Status",
            dedent(
                f"""
                ![Current status banner](../assets/pages/current-status.png)

                {current_status_intro}

                ## The short version

                - the split is real
                - the public surfaces are still preview, not the final public shape
                - play is still the next major product seam to finish
                - UI kit, registry, and media exist, but are still becoming fully real boundaries
                - the blueprint is still catching up in a few places

                ## What that means for normal humans

                {current_status_body}
                """
            )
            + footer("current public shape", "chummer6-design program milestones"),
        ),
    )

    write_text(
        GUIDE_REPO / "NOW" / "public-surfaces.md",
        page_markdown(
            "Public Surfaces",
            dedent(
                f"""
                ![Public surfaces banner](../assets/pages/public-surfaces.png)

                {public_surfaces_intro}

                ## Current public reality

                {public_surfaces_body}

                These are still preview, not the final public shape:

                - portal root
                - hub preview
                - workbench preview
                - play preview
                - coach preview

                ## Why that label exists

                It means the surface is there, but the code, blueprint, ownership, and deployment story do not line up cleanly enough yet to call it the real promoted version.
                """
            )
            + footer("current public surface status"),
        ),
    )

    write_text(
        GUIDE_REPO / "PARTS" / "README.md",
        page_markdown(
            "Program Map",
            dedent(
                f"""
                ![Parts overview banner](../assets/pages/parts-index.png)

                {parts_index_intro}

                {parts_index_body}

                ## The quick picture

                - `core` keeps the deterministic rules truth
                - `ui` keeps the workbench experience
                - `mobile` is the at-the-table shell
                - `hub` is the hosted API and orchestration layer
                - `ui-kit` is the shared visual vocabulary
                - `hub-registry` keeps artifacts and publication metadata
                - `media-factory` handles render-only asset jobs
                - `design` keeps the canonical blueprint

                ## How to read this folder

                Each page answers the same human questions:

                - what this part is for
                - why it matters
                - what it owns
                - what it does not own
                - what is happening with it right now

                ## Where to start

                If you want the most important seam right now, read [mobile](mobile.md).  
                If you want the cleanest big-picture answer, read [design](design.md).  
                If you want the current visible shape, read [../NOW/current-status.md](../NOW/current-status.md).
                """
            )
            + footer("chummer6-design ownership map", "public repo READMEs", "current public shape"),
        ),
    )

    for name, item in PARTS.items():
        effective = deep_merge(item, part_override_for(name))
        write_text(GUIDE_REPO / "PARTS" / f"{name}.md", part_page(name, effective))

    write_text(
        GUIDE_REPO / "HORIZONS" / "README.md",
        page_markdown(
            "Horizons",
            dedent(
                f"""
                ![Horizons overview banner](../assets/pages/horizons-index.png)

                {horizons_index_intro}

                They are here because they are exciting, useful, or strategically important.  
                They are **not** active build commitments.

                {horizons_index_body}

                ## Pick a future rabbit hole

                <table>
                  <tr>
                    <td align="center"><a href="karma-forge.md"><img src="../assets/horizons/karma-forge.png" alt="KARMA FORGE" width="300"><br><strong>KARMA FORGE</strong><br><em>Personalized rule stacks without fork chaos</em></a></td>
                    <td align="center"><a href="nexus-pan.md"><img src="../assets/horizons/nexus-pan.png" alt="NEXUS-PAN" width="300"><br><strong>NEXUS-PAN</strong><br><em>A live synced table experience</em></a></td>
                    <td align="center"><a href="alice.md"><img src="../assets/horizons/alice.png" alt="ALICE" width="300"><br><strong>ALICE</strong><br><em>Simulation and build stress-testing</em></a></td>
                  </tr>
                  <tr>
                    <td align="center"><a href="jackpoint.md"><img src="../assets/horizons/jackpoint.png" alt="JACKPOINT" width="300"><br><strong>JACKPOINT</strong><br><em>Grounded dossiers and story artifacts</em></a></td>
                    <td align="center"><a href="ghostwire.md"><img src="../assets/horizons/ghostwire.png" alt="GHOSTWIRE" width="300"><br><strong>GHOSTWIRE</strong><br><em>Forensic replay for runs</em></a></td>
                    <td align="center"><a href="rule-x-ray.md"><img src="../assets/horizons/rule-x-ray.png" alt="RULE X-RAY" width="300"><br><strong>RULE X-RAY</strong><br><em>Click any number and see where it came from</em></a></td>
                  </tr>
                  <tr>
                    <td align="center"><a href="heat-web.md"><img src="../assets/horizons/heat-web.png" alt="HEAT WEB" width="300"><br><strong>HEAT WEB</strong><br><em>Campaign consequences as a living graph</em></a></td>
                    <td align="center"><a href="run-passport.md"><img src="../assets/horizons/run-passport.png" alt="RUN PASSPORT" width="300"><br><strong>RUN PASSPORT</strong><br><em>Move a character across rule environments</em></a></td>
                    <td align="center"><a href="threadcutter.md"><img src="../assets/horizons/threadcutter.png" alt="THREADCUTTER" width="300"><br><strong>THREADCUTTER</strong><br><em>Conflict analysis for overlay packs</em></a></td>
                  </tr>
                  <tr>
                    <td align="center"><a href="mirrorshard.md"><img src="../assets/horizons/mirrorshard.png" alt="MIRRORSHARD" width="300"><br><strong>MIRRORSHARD</strong><br><em>Compare alternate character futures</em></a></td>
                    <td align="center"><a href="blackbox-loadout.md"><img src="../assets/horizons/blackbox-loadout.png" alt="BLACKBOX LOADOUT" width="300"><br><strong>BLACKBOX LOADOUT</strong><br><em>The idiot-check before the run</em></a></td>
                    <td></td>
                  </tr>
                </table>

                These are the pages where Chummer gets to dream out loud a little:
                sharper tables, smarter builds, cleaner chaos, and fewer moments where a runner has to shrug and say “I dunno, the software just vibes that way.”

                ## Important note

                If you want canonical design or actual implementation truth, this folder is not that.  
                For that, go to [Where to go deeper](../WHERE_TO_GO_DEEPER.md).
                """
            )
            + footer("chummer6-design horizon guidance", "current public shape"),
        ),
    )

    for slug, item in HORIZONS.items():
        effective = deep_merge(item, EA_HORIZON_OVERRIDES.get(slug, {}))
        write_text(GUIDE_REPO / "HORIZONS" / f"{slug}.md", horizon_page(slug, effective))

    write_text(
        GUIDE_REPO / "UPDATES" / "2026-03.md",
        page_markdown(
            "March 2026 Updates",
            dedent(
                """
                ## The quick read

                March is a chassis-tightening month.

                That means the interesting work is not “ship a thousand flashy features” but “make the split honest enough that future features stop being expensive lies.”

                ## What moved

                - the split is visible as a real multi-repo program
                - Chummer6 exists as the human guide
                - the guide is getting stricter about what is preview and what is actually ready
                - the play/session boundary is still the next major seam to finish

                ## What is still not finished

                - shared rules and interfaces still need cleanup
                - the full play split is not done
                - UI kit package realness is still in progress
                - registry and media seams are still maturing
                - public preview surfaces are not yet promoted
                """
            )
            + footer("current public shape", "chummer6-design"),
        ),
    )

    write_text(
        GUIDE_REPO / "GLOSSARY.md",
        page_markdown(
            "Glossary",
            dedent(
                """
                - **shared interface**: the package or API seam used across repo boundaries
                - **split**: moving real ownership from one repo to another and deleting the old ownership
                - **runtime stack**: the rules/config stack a play or hosted flow is actually using
                - **lockstep**: several parts moving together as one wave
                - **preview**: visible to humans, not yet the final public shape
                - **workbench**: the browser/desktop authoring and inspection head
                - **play shell**: the player/GM/mobile head
                - **signoff only**: visible in the program, but not a coding target
                - **horizon**: a future concept intentionally kept out of the active work queue
                - **visitor center**: the human guide layer that explains the program without becoming a second blueprint
                """
            )
            + footer("chummer6-design", "guide conventions"),
        ),
    )

    write_text(
        GUIDE_REPO / "FAQ.md",
        page_markdown(
            "FAQ",
            dedent(
                """
                ## Is Chummer6 a design repo?
                No. `chummer6-design` is the canonical blueprint repo.

                ## Is Chummer6 a code repo?
                No. It is a human guide only.

                ## Is Chummer6 a work queue?
                No. It explains the program. It does not decide the work.

                ## Why are there so many repos?
                Because Chummer is already split into engine, hosted orchestration, play shell, shared UI, registry, media, design, and guide responsibilities.

                ## What is live right now?
                The multi-repo program is live, but the public surfaces are still preview, not the final public shape.

                ## What is only preview?
                Portal root, hub, workbench, play, and coach are still preview until promoted.

                ## Where do I propose design changes?
                In `chummer6-design`.

                ## Is Chummer6 allowed to make fun of the dev?
                Yes. Gently, but absolutely. If the dev ships cursed nonsense, the guide is allowed to say so.

                ## What should I include when I report a bug?
                The useful stuff: what you installed, what you clicked, what you expected, what actually happened, and any screenshot or log that helps track the gremlin back to its nest.

                ## Why does Chummer6 exist if it is not the blueprint?
                To make the program understandable for humans without creating a second blueprint by accident.
                """
            )
            + footer("chummer6-design", "current public shape"),
        ),
    )

    remove_forbidden()


def write_design_scope() -> None:
    write_text(
        DESIGN_SCOPE,
        page_markdown(
            "guide",
            dedent(
                """
                ## Purpose
                `Chummer6` is the downstream human guide repo for the Chummer6 program.

                ## Rules
                - human-only
                - downstream-only
                - not canonical design
                - not a queue source
                - not a contract source
                - not a milestone source
                - not mirrored into code repos
                - not dispatchable

                ## Allowed inputs
                - `chummer6-design`
                - the latest public program status
                - owning repo READMEs
                - approved public-surface summaries

                ## Priority order
                If `Chummer6` disagrees with canonical sources, fix `Chummer6`.

                1. `chummer6-design`
                2. latest public program status
                3. owning repo
                4. `Chummer6`

                ## Out of scope
                - code
                - tests
                - scripts
                - runtime instructions
                - queue files
                - contract files
                - milestone authority
                - ADR authorship
                - review-template authorship
                """
            ),
        ),
    )


def audit_generated_repo() -> None:
    forbidden_terms = [str(term).lower() for term in GUIDE_POLICY.get("forbidden_guide_terms", [])]
    forbidden_hotlinks = [str(term).lower() for term in GUIDE_POLICY.get("forbidden_hotlinks", [])]
    required = [
        GUIDE_REPO / "README.md",
        GUIDE_REPO / "START_HERE.md",
        GUIDE_REPO / "WHAT_CHUMMER6_IS.md",
        GUIDE_REPO / "WHERE_TO_GO_DEEPER.md",
        GUIDE_REPO / "PARTS" / "README.md",
        GUIDE_REPO / "HORIZONS" / "README.md",
        GUIDE_REPO / "assets" / "hero" / "chummer6-hero.png",
        GUIDE_REPO / "assets" / "hero" / "poc-warning.png",
        GUIDE_REPO / "assets" / "pages" / "start-here.png",
        GUIDE_REPO / "assets" / "pages" / "what-chummer6-is.png",
        GUIDE_REPO / "assets" / "pages" / "where-to-go-deeper.png",
        GUIDE_REPO / "assets" / "pages" / "current-phase.png",
        GUIDE_REPO / "assets" / "pages" / "current-status.png",
        GUIDE_REPO / "assets" / "pages" / "public-surfaces.png",
        GUIDE_REPO / "assets" / "pages" / "parts-index.png",
        GUIDE_REPO / "assets" / "pages" / "horizons-index.png",
    ]
    required.extend(GUIDE_REPO / "assets" / "parts" / f"{slug}.png" for slug in PARTS)
    required.extend(GUIDE_REPO / "assets" / "horizons" / f"{slug}.png" for slug in HORIZONS)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Chummer6 generator missed required files: {missing}")

    for rel in [*FORBIDDEN, *RETIRED]:
        if (GUIDE_REPO / rel).exists():
            raise RuntimeError(f"Retired/forbidden Chummer6 path still exists: {rel}")

    for path in sorted(GUIDE_REPO.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".png", ".gif"}:
            continue
        if path.suffix.lower() == ".md":
            text = path.read_text(encoding="utf-8")
            lowered = text.lower()
            assert_clean(text, label=str(path))
            for term in forbidden_terms:
                if term and term in lowered:
                    raise ValueError(f"{path} contains forbidden guide term: {term}")
            for term in forbidden_hotlinks:
                if term and term in lowered:
                    raise ValueError(f"{path} contains forbidden hotlink term: {term}")

    readme = (GUIDE_REPO / "README.md").read_text(encoding="utf-8")
    for needle in [
        "## Pick your path",
        "## Why this is worth watching",
        "## What you can do",
        "## POC shelf",
        "https://github.com/ArchonMegalon/Chummer6/releases",
    ]:
        if needle not in readme:
            raise ValueError(f"README.md is missing required section: {needle}")
    if not isinstance(EA_OODA, dict):
        raise ValueError("EA OODA data is missing for guide generation")
    require_ooda_stage(
        "observe",
        ["source_signal_tags", "source_excerpt_labels", "audience_needs", "user_interest_signals", "risks"],
    )
    require_ooda_stage(
        "orient",
        ["audience", "promise", "tension", "why_care", "current_focus", "visual_direction", "humor_line", "signals_to_highlight", "banned_terms"],
    )
    require_ooda_stage(
        "decide",
        ["information_order", "tone_rules", "horizon_policy", "media_strategy", "overlay_policy", "cta_strategy"],
    )
    require_ooda_stage(
        "act",
        ["landing_tagline", "landing_intro", "what_it_is", "watch_intro", "horizon_intro"],
    )
    for page_id in (
        "readme",
        "start_here",
        "what_chummer6_is",
        "where_to_go_deeper",
        "current_phase",
        "current_status",
        "public_surfaces",
        "parts_index",
        "horizons_index",
    ):
        require_section_ooda("pages", page_id)
        page_row = EA_PAGE_OVERRIDES.get(page_id)
        if not isinstance(page_row, dict):
            raise ValueError(f"EA page override is missing: {page_id}")
        for field in ("intro", "body"):
            value = page_row.get(field)
            if value in (None, "", [], {}):
                raise ValueError(f"EA page override field is missing: {page_id}.{field}")
    require_section_ooda("hero", "hero")
    for section_group, sample_keys in {
        "parts": list(PARTS.keys())[:2],
        "horizons": list(HORIZONS.keys())[:2],
    }.items():
        for sample in sample_keys:
            require_section_ooda(section_group, sample)
    loaded_overrides = json.loads(EA_OVERRIDE_PATH.read_text(encoding="utf-8")) if EA_OVERRIDE_PATH.exists() else {}
    meta = loaded_overrides.get("meta") if isinstance(loaded_overrides, dict) else {}
    if not isinstance(meta, dict) or str(meta.get("ooda_version", "")).strip() != "v3":
        raise ValueError("EA OODA contract version is missing or stale")
    media = loaded_overrides.get("media") if isinstance(loaded_overrides, dict) else {}
    if not isinstance(media, dict):
        raise ValueError("EA media plan is missing for guide generation")
    hero_media = media.get("hero")
    if not isinstance(hero_media, dict) or not hero_media.get("visual_prompt") or not hero_media.get("overlay_callouts"):
        raise ValueError("EA hero media plan is missing OODA-driven prompt or overlays")
    horizon_media = media.get("horizons")
    if not isinstance(horizon_media, dict) or not horizon_media:
        raise ValueError("EA horizon media plan is missing")
    sample_media = next(iter(horizon_media.values()))
    if not isinstance(sample_media, dict) or not sample_media.get("visual_prompt") or not sample_media.get("overlay_callouts"):
        raise ValueError("EA horizon media plan is missing OODA-driven prompt or overlays")


def main() -> int:
    if "--audit-only" in sys.argv:
        ensure_local_repo()
        audit_generated_repo()
        print({"repo": REPO_SLUG, "status": "ooda-audited"})
        return 0
    ensure_github_repo()
    ensure_local_repo()
    write_guide_repo()
    write_design_scope()
    audit_generated_repo()
    print(
        {
            "repo": REPO_SLUG,
            "local_path": str(GUIDE_REPO),
            "design_scope": str(DESIGN_SCOPE),
            "status": "prepared",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
