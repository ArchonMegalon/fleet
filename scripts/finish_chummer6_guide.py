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
TODAY = "2026-03-11"
POLICY_PATH = Path("/docker/fleet/.chummer6_local_policy.json")

DEFAULT_POLICY = {
    "forbidden_origin_mentions": [],
    "forbidden_guide_terms": [
        "fleet is mission control",
        "operational truth lives in fleet",
        "where the real truth lives",
        "where_the_real_truth_lives",
        "preview debt",
        "contract plane",
        "design/control layer",
        "every fleet view",
        "parts/fleet.md",
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
    "assets/chummer6-hero.svg",
    "assets/poc-warning.svg",
    "assets/program-map.svg",
    "assets/status-strip.svg",
    "assets/hero/chummer6-hero.svg",
    "assets/hero/poc-warning.svg",
    "assets/diagrams/program-map.svg",
    "assets/diagrams/status-strip.svg",
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
    "presentation": {
        "title": "Presentation",
        "tagline": "The workbench and big-screen UX.",
        "intro": (
            "Presentation is where the heavy chrome lives: inspectors, builders, deep "
            "views, and the workbench-side experience for people who like staring at "
            "their gear until the gears stare back."
        ),
        "why": (
            "This is the part that makes Chummer feel inspectable instead of mystical."
        ),
        "owns": [
            "browser and desktop workbench UX",
            "inspectors, builders, and shared presentation seams",
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
    "play": {
        "title": "Play",
        "tagline": "The part you feel at the table.",
        "intro": (
            "Play is the shell for players and GMs during actual sessions: mobile/PWA "
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
    "run-services": {
        "title": "Run Services",
        "tagline": "The hosted API and orchestration layer.",
        "intro": (
            "Run Services is the network backbone: identity, relay, approvals, memory, "
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
        "repos": ["core", "play", "run-services", "hub-registry", "design"],
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
        "repos": ["play", "run-services", "core", "design"],
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
        "repos": ["core", "run-services", "design"],
        "not_now": (
            "Because the engine and explain seams still need to become cleaner before simulation gets to wear a lab coat."
        ),
        "accent": "#7c3aed",
        "glow": "#c084fc",
        "prompt": (
            "Wide cyberpunk simulation-lab banner, a crash-test dummy in runner gear inside a glowing combat simulation grid while multiple outcomes branch around it, statistical danger with dark humor, original concept art, no text, no logo, no watermark, 16:9"
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
        "repos": ["run-services", "hub-registry", "media-factory", "design"],
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
        "repos": ["play", "run-services", "design"],
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
        "repos": ["core", "presentation", "design"],
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
        "repos": ["run-services", "play", "presentation", "design"],
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
        "repos": ["presentation", "run-services", "design"],
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
        "repos": ["hub-registry", "play", "run-services", "design"],
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
        "repos": ["run-services", "play", "design"],
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
        "repos": ["play", "hub-registry", "design"],
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


def load_ea_overrides() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    parts_override: dict[str, object] = {}
    horizons_override: dict[str, object] = {}
    ooda_override: dict[str, object] = {}
    if EA_OVERRIDE_PATH.exists():
        loaded = json.loads(EA_OVERRIDE_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            raw_parts = loaded.get("parts")
            raw_horizons = loaded.get("horizons")
            raw_ooda = loaded.get("ooda")
            if isinstance(raw_parts, dict):
                parts_override = raw_parts
            if isinstance(raw_horizons, dict):
                horizons_override = raw_horizons
            if isinstance(raw_ooda, dict):
                ooda_override = raw_ooda
    return parts_override, horizons_override, ooda_override


EA_PART_OVERRIDES, EA_HORIZON_OVERRIDES, EA_OODA = load_ea_overrides()


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
    seed = int(hashlib.sha256(f"{title}:{accent}:{glow}:{layout}".encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    bg_a = (8, 10, 18)
    bg_b = hex_rgb(accent)
    glow_rgb = hex_rgb(glow)
    panel_rgb = (242, 248, 252)
    pixels = bytearray(width * height * 4)
    orbs: list[tuple[float, float, float, float]] = []
    orb_count = 3 if layout == "banner" else 5
    for _ in range(orb_count):
        orbs.append(
            (
                rng.uniform(0.15, 0.85) * width,
                rng.uniform(0.12, 0.78) * height,
                rng.uniform(width * 0.14, width * 0.28),
                rng.uniform(0.35, 0.85),
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

    for y in range(height):
        u = y / max(1, height - 1)
        for x in range(width):
            t = x / max(1, width - 1)
            base = mix(bg_a, bg_b, 0.55 * t + 0.45 * u)
            r, g, b = [float(c) for c in base]
            vignette = 1.0 - 0.5 * (((t - 0.5) ** 2) + ((u - 0.5) ** 2))
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

            diag = math.sin((x * 0.012) + (y * 0.006) + phase)
            if diag > 0.92:
                r += glow_rgb[0] * 0.25
                g += glow_rgb[1] * 0.25
                b += glow_rgb[2] * 0.25

            scan = 0.9 + 0.1 * math.sin((y * 0.09) + phase * 2.0)
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
                        alpha = 0.52
                        r = r * (1.0 - alpha) + c[0] * alpha
                        g = g * (1.0 - alpha) + c[1] * alpha
                        b = b * (1.0 - alpha) + c[2] * alpha

            idx = (y * width + x) * 4
            pixels[idx] = clamp8(r)
            pixels[idx + 1] = clamp8(g)
            pixels[idx + 2] = clamp8(b)
            pixels[idx + 3] = 255
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
        return None
    output = Path(str(row.get("output", ""))).expanduser()
    if not output.exists() or not output.is_file():
        return None
    try:
        return output.read_bytes()
    except Exception:
        return None


def write_asset(path: Path, fallback_bytes: bytes, *, prompt: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered: bytes | None = None
    if prompt:
        try:
            rendered = try_provider_image(prompt, width=1280, height=720)
        except Exception:
            rendered = None
    write_binary(path, rendered or fallback_bytes)


def write_poc_warning_gif(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for index in range(6):
            frame = synth_cyberpunk_png(
                "POC Shelf",
                "#7c2d12",
                "#fb923c",
                layout="banner",
                phase=index * 0.65,
            )
            write_binary(tmp / f"frame-{index:02d}.png", frame)
        run(
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            "4",
            "-i",
            str(tmp / "frame-%02d.png"),
            "-vf",
            "scale=1280:720:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            str(path),
        )


def write_assets() -> None:
    media_manifest = load_ea_media_manifest()
    hero_path = GUIDE_REPO / "assets" / "hero" / "chummer6-hero.png"
    poc_path = GUIDE_REPO / "assets" / "hero" / "poc-warning.gif"
    map_path = GUIDE_REPO / "assets" / "diagrams" / "program-map.png"
    strip_path = GUIDE_REPO / "assets" / "diagrams" / "status-strip.png"
    hero_override = ea_media_bytes_for(hero_path, media_manifest)
    if hero_override:
        write_binary(hero_path, hero_override)
    else:
        write_asset(
            hero_path,
            hero_png(),
            prompt=(
                "Wide cinematic cyberpunk concept-art banner for a software guide repo called Chummer6, shadowrun-inspired but original, a battered commlink and cyberdeck on a rainy alley crate, holographic character sheets and repo cards floating above it, gritty neon cyan and magenta lighting, dark humor, dangerous but inviting, strong center composition, no text, no logo, no watermark, 16:9"
            ),
        )
    write_poc_warning_gif(poc_path)
    write_asset(
        map_path,
        program_map_png(),
    )
    write_asset(
        strip_path,
        status_strip_png(),
    )
    for slug, item in HORIZONS.items():
        target = GUIDE_REPO / "assets" / "horizons" / f"{slug}.png"
        media_override = ea_media_bytes_for(target, media_manifest)
        if media_override:
            write_binary(target, media_override)
        else:
            write_asset(
                target,
                horizon_fallback_png(item["title"], item["hook"], item["accent"], item["glow"]),
                prompt=item["prompt"],
            )


def page_markdown(title: str, body: str) -> str:
    return f"# {title}\n\n{body.strip()}\n"


def part_page(name: str, item: dict[str, object]) -> str:
    owns = "\n".join(f"- {line}" for line in item["owns"])
    not_owns = "\n".join(f"- {line}" for line in item["not_owns"])
    body = dedent(
        f"""
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
    body = (
        f"![{title} banner](../assets/horizons/{slug}.png)\n\n"
        f"**{item['hook']}**\n\n"
        "_Status: Horizon only — future idea, not active build work._\n\n"
        "## Why this would be wiz\n\n"
        f"{item['hook']} That means less duct-taped nonsense, more readable chrome, and one more way for Chummer to feel like the tool you brag about instead of the one you apologize for.\n\n"
        "## The brutal truth\n\n"
        f"{item['brutal_truth']}\n\n"
        "## The use case\n\n"
        f"{item['use_case']}\n\n"
        "## What is the idea?\n\n"
        f"{title} is a future rabbit hole worth documenting because it solves a real problem in a way that could make Chummer feel sharper, weirder, and more alive.\n\n"
        "## What problem does it solve?\n\n"
        f"{item['problem']}\n\n"
        "## Foundations first\n\n"
        f"{foundations}\n\n"
        "## Which parts would it touch later?\n\n"
        f"{repos}\n\n"
        "## Why it waits\n\n"
        f"{item['not_now']}\n"
        + footer("chummer6-design horizon guidance", "current public shape")
    )
    return page_markdown(title, body)


def write_guide_repo() -> None:
    write_assets()
    why_care_lines = indented_bullets((ooda_list("why_care")[:4] or [
        "Lua-scripted rules keep the future moddable without turning every table into a code fork.",
        "The project is chasing SR4, SR5, and SR6 support instead of pretending only one era matters.",
        "Play is being built local-first so the table does not fold the moment the network gets weird.",
        "Explain work is aiming for actual receipts, not vibes and hand-waving.",
    ]))
    current_focus_lines = indented_bullets((ooda_list("current_focus")[:5] or [
        "clean up the shared rules and interfaces",
        "finish the play/session boundary",
        "make the shared UI kit real",
        "finish registry and media splits",
    ]))
    promise = ooda_text(
        "promise",
        "Chummer6 should make the project feel exciting, legible, and worth following without making readers chew through internal machinery.",
    )
    tension = ooda_text(
        "tension",
        "The future is exciting, but the current job is still foundations, cleanup, and making the split real.",
    )
    landing_tagline = ooda_text("landing_tagline", "Same shadows. Bigger future. Less confusion.")
    landing_intro = ooda_text(
        "landing_intro",
        "Chummer6 is the readable guide to the next Chummer: what it is becoming, how the parts fit together, what is happening right now, and which future ideas are still parked in the garage.",
    )
    what_it_is = ooda_text(
        "what_it_is",
        "Chummer6 is the friendly guide to the next Chummer, built for curious chummers who want the lay of the land without spelunking through every repo.",
    )
    watch_intro = ooda_text("watch_intro", "People who care about Shadowrun tools should probably care because:")
    horizon_intro = ooda_text(
        "horizon_intro",
        "Some ideas are too fun not to document. They are real possibilities, but they are not active build commitments.",
    )

    write_text(
        GUIDE_REPO / "README.md",
        page_markdown(
            "Chummer6",
            dedent(
                f"""
                ![Chummer6 hero banner](assets/hero/chummer6-hero.png)

                > **{landing_tagline}**
                >
                > {landing_intro}

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

                ![Current status strip](assets/diagrams/status-strip.png)

                Right now the crew is doing foundation work, not bolting neon spoilers onto half-built engines.
                {tension}

                Current focus:
{current_focus_lines}
                - keep public previews honestly labeled until they become the real thing

                Read more: [Current phase](NOW/current-phase.md)

                ## Meet the parts

                ![Program map](assets/diagrams/program-map.png)

                | Part | What it does | Read more |
                | --- | --- | --- |
                | Core | The deterministic rules engine | [core](PARTS/core.md) |
                | Presentation | The workbench and big-screen UX | [presentation](PARTS/presentation.md) |
                | Play | The player/GM shell for sessions and mobile use | [play](PARTS/play.md) |
                | Run services | The hosted API and orchestration layer | [run-services](PARTS/run-services.md) |
                | UI kit | Shared components, themes, and visual primitives | [ui-kit](PARTS/ui-kit.md) |
                | Hub registry | Artifacts, publication, installs, compatibility | [hub-registry](PARTS/hub-registry.md) |
                | Media factory | Render jobs, previews, and asset lifecycle | [media-factory](PARTS/media-factory.md) |
                | Design | The long-range blueprint room | [design](PARTS/design.md) |

                ## Horizon ideas

                {horizon_intro}

                - [Karma Forge](HORIZONS/karma-forge.md) — personalized rules without fork chaos
                - [NEXUS-PAN](HORIZONS/nexus-pan.md) — a live synced table instead of lonely files
                - [ALICE](HORIZONS/alice.md) — stress-test a build before the run
                - [JACKPOINT](HORIZONS/jackpoint.md) — turn grounded data into dossiers and briefings
                - [GHOSTWIRE](HORIZONS/ghostwire.md) — replay a run like a forensic sim
                - [RULE X-RAY](HORIZONS/rule-x-ray.md) — click any number and see where it came from

                See all: [Horizon index](HORIZONS/README.md)

                ## What you can do

                If this repo helped you get your bearings, here’s how to help back:

                - **Give Chummer6 a star** if this guide saved you from digging through half the Matrix just to understand what is going on.
                - **Be my test dummy and install the software.**
                - **Grab the latest POC build from [Releases](https://github.com/ArchonMegalon/Chummer6/releases)** when one is available.
                - **Seriously: never trust software. Never trust a dev.**
                - **Give us an OpenAI API key** — absolutely not. Keep your secrets. If the dev forgot the obvious thing again, that is a dev problem, not a credential problem.
                - **If a build glitches, breaks, crashes, or does something cursed, tell me exactly how you got there.**
                - **If this repo is stale, confusing, or reads like corp training material, call it out.**

                > **Street warning:** POC builds are for curious chummers, not cautious wageslaves.  
                > They may be unstable, unfinished, weird, or one bad click away from getting your deck **marked, hacked, or bricked**.  
                > Install at your own risk.

                In other words: kick the tires, break the thing, and tell me where the smoke came out.

                ## POC shelf

                ![POC warning banner](assets/hero/poc-warning.gif)

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
                """
                Welcome to Chummer6.

                If you just landed here and are wondering why one Shadowrun tool suddenly seems to have a small constellation of repos around it, you are in the right place.

                Chummer is growing from one legacy app into a set of focused parts: a rules engine, a workbench, a play shell, hosted services, a shared UI layer, an artifact registry, a media pipeline, and a blueprint repo that keeps the long game straight.

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
                """
                Chummer6 is the human guide to the next Chummer.

                It exists because the real program is already split across multiple repos, active previews, and one canonical blueprint repo. That is powerful, but it is also a lot to dump on someone who just wants the lay of the land.

                ## The short version

                Chummer6 is here to answer the human questions first:

                - What is this thing becoming?
                - Why are there so many moving parts?
                - What is actually happening right now?
                - Which ideas are real work, and which ones are still parked in the garage?

                ## Why this repo exists

                This repo gives you the plain-language version of the program:

                - what Chummer is becoming
                - what the main parts are
                - what is happening now
                - what ideas are parked in the horizon
                - and, when necessary, a gentle roast of the dev who shipped something weird

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
                """
                This page is the map legend.

                Chummer6 is here to explain the program clearly. It is not allowed to become a second blueprint.

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
                """
                The current phase is foundation work, not fireworks.

                In plain language: the team is trying to make the split **real**, not just visible.

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
                """
                Chummer is already a live multi-repo program, but it is still much earlier in completion than in visible shape.

                ## The short version

                - the split is real
                - the public surfaces are still preview, not the final public shape
                - play is still the next major product seam to finish
                - UI kit, registry, and media exist, but are still becoming fully real boundaries
                - the blueprint is still catching up in a few places

                ## What that means for normal humans

                You can already see the shape of the future.
                You just should not mistake preview surfaces or repo existence for “done.”
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
                """
                Some things are visible. That does **not** mean they are the final public shape yet.

                ## Current public reality

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
                """
                This is the field guide to the main moving parts.

                If Chummer6 is the visitor center, this folder is the wall of labeled drawers.

                ## The quick picture

                - `core` keeps the deterministic rules truth
                - `presentation` keeps the workbench experience
                - `play` is the at-the-table shell
                - `run-services` is the hosted API and orchestration layer
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

                If you want the most important seam right now, read [play](play.md).  
                If you want the cleanest big-picture answer, read [design](design.md).  
                If you want the current visible shape, read [../NOW/current-status.md](../NOW/current-status.md).
                """
            )
            + footer("chummer6-design ownership map", "public repo READMEs", "current public shape"),
        ),
    )

    for name, item in PARTS.items():
        effective = deep_merge(item, EA_PART_OVERRIDES.get(name, {}))
        write_text(GUIDE_REPO / "PARTS" / f"{name}.md", part_page(name, effective))

    write_text(
        GUIDE_REPO / "HORIZONS" / "README.md",
        page_markdown(
            "Horizons",
            dedent(
                """
                These are possible future directions for Chummer.

                They are here because they are exciting, useful, or strategically important.  
                They are **not** active build commitments.

                Think of this folder as the garage: some of these projects may become real later, but none of them are the thing the team is racing today.

                ## Pick a future rabbit hole

                - [Karma Forge](karma-forge.md) — personalized rule stacks without fork chaos
                - [NEXUS-PAN](nexus-pan.md) — a live synced table experience
                - [ALICE](alice.md) — simulation and build stress-testing
                - [JACKPOINT](jackpoint.md) — grounded dossier and story artifact generation
                - [GHOSTWIRE](ghostwire.md) — forensic replay for runs
                - [MIRRORSHARD](mirrorshard.md) — compare alternate character futures
                - [RULE X-RAY](rule-x-ray.md) — click any number and see where it came from
                - [HEAT WEB](heat-web.md) — campaign consequences as a living graph
                - [RUN PASSPORT](run-passport.md) — move a character across rule environments
                - [THREADCUTTER](threadcutter.md) — conflict analysis for overlay packs
                - [BLACKBOX LOADOUT](blackbox-loadout.md) — the idiot-check before the run

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

                ## Should I paste an OpenAI API key into an issue to help out?
                Absolutely not. Keep your secrets, keep your nuyen, and assume the dev can survive one more bug report without you donating credentials to the Matrix.

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
        GUIDE_REPO / "assets" / "hero" / "poc-warning.gif",
        GUIDE_REPO / "assets" / "diagrams" / "program-map.png",
        GUIDE_REPO / "assets" / "diagrams" / "status-strip.png",
    ]
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
    loaded_overrides = json.loads(EA_OVERRIDE_PATH.read_text(encoding="utf-8")) if EA_OVERRIDE_PATH.exists() else {}
    meta = loaded_overrides.get("meta") if isinstance(loaded_overrides, dict) else {}
    if not isinstance(meta, dict) or str(meta.get("ooda_version", "")).strip() != "v2":
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
