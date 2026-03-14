#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import random
import re
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

IMAGE_TITLES = {
    "assets/hero/chummer6-hero.png": "table truth, wet sleeves, and one troll charm the dev better not lose again.",
    "assets/hero/poc-warning.png": "the build may survive your evening. Your patience is less certain.",
    "assets/pages/start-here.png": "pick the lane that solves tonight's problem before the repo tries to hand you a topology lecture.",
    "assets/pages/what-chummer6-is.png": "product story first, architecture sermon later, assuming the dev can resist lecturing for five minutes.",
    "assets/pages/where-to-go-deeper.png": "this is the part where curiosity becomes paperwork with better lighting.",
    "assets/pages/current-phase.png": "no confetti, just structural honesty and fewer expensive lies.",
    "assets/pages/current-status.png": "real enough to click, honest enough to admit where the duct tape still lives.",
    "assets/pages/public-surfaces.png": "preview means the shape can move, not that the dev imagined the whole thing after lunch.",
    "assets/pages/parts-index.png": "choose your lane before the repo names start sounding like a committee hallucination.",
    "assets/pages/horizons-index.png": "future districts for table pain, because the dev collects rabbit holes like contraband.",
    "../assets/parts/core.png": "if the math looks cursed, this is where the curse gets cross-examined.",
    "../assets/parts/ui.png": "where you lovingly inspect every choice before the run and then blame the dice anyway.",
    "../assets/parts/mobile.png": "the session shell for when your table refuses to stay in one physical century.",
    "../assets/parts/hub.png": "hosted coordination, because apparently some chaos really does need adult supervision.",
    "../assets/parts/ui-kit.png": "the bit that stops the split from dressing like eight unrelated crimes.",
    "../assets/parts/hub-registry.png": "compatibility truth, so your install flow does not become cursed zip roulette.",
    "../assets/parts/media-factory.png": "render jobs belong here, not taped to whatever repo the dev had open at 2 a.m.",
    "../assets/parts/design.png": "the long-range planning room, still dangerously attractive to people who enjoy scope diagrams.",
    "../assets/horizons/karma-forge.png": "house rules with receipts, not forked-code folklore and a group chat apology.",
    "../assets/horizons/nexus-pan.png": "Wi-Fi died; the table did not. That is the fantasy.",
    "../assets/horizons/alice.png": "the simulation is here to hurt your feelings before reality does.",
    "../assets/horizons/jackpoint.png": "coffee stains optional, evidence boundaries not.",
    "../assets/horizons/ghostwire.png": "memory is a liar; event logs are just meaner about it.",
    "../assets/horizons/rule-x-ray.png": "every modifier gets dragged into the light like it owes the table money.",
    "../assets/horizons/heat-web.png": "campaign consequences, now with fewer GM memory miracles and more receipts.",
    "../assets/horizons/mirrorshard.png": "compare both bad ideas before the dev asks you to commit to one.",
    "../assets/horizons/run-passport.png": "crossing rule borders without smuggling cursed assumptions in your coat.",
    "../assets/horizons/threadcutter.png": "because every clever overlay eventually meets another clever overlay in a dark alley.",
    "../assets/horizons/blackbox-loadout.png": "the software notices you forgot ammo before the NPCs do.",
    "../assets/horizons/command-casket.png": "somebody definitely called this a tiny admin tweak right before it needed a coffin.",
    "../assets/horizons/evidence-room.png": "proof, provenance, and one coffee cup that has seen too much.",
    "../assets/horizons/persona-echo.png": "continuity without letting the software become your runner's lying publicist.",
    "../assets/horizons/shadow-market.png": "shopping, but with enough trust signals to survive the dev's taste in plugins.",
    "../assets/horizons/tactical-pulse.png": "shared situational awareness for the exact moment everyone swears they were paying attention.",
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
    "VISUAL_OVERRIDES.json",
    "VISUAL_PROMPTS.md",
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
            "engine packages other parts can trust",
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
            "shared pieces that should come from one real source",
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
        "tagline": "The long-range plan and ownership map.",
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
            "The active design work is keeping the long-range plan current enough that the rest of the program can stop free-styling."
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
            "clean shared boundaries",
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
    "command-casket": {
        "title": "Command Casket",
        "hook": "Controlled operator actions with receipts and rollback.",
        "problem": (
            "Important operator actions need to be explainable, reviewable, and reversible instead of dissolving into mystery-admin folklore."
        ),
        "brutal_truth": (
            "The moment nobody can answer who approved the change, every serious admin action starts smelling like haunted button mashing."
        ),
        "use_case": (
            "A sensitive change gets wrapped as an auditable command capsule with requester, approval state, outcome, and rollback attached in one place."
        ),
        "foundations": [
            "approval-aware workflows",
            "preview, apply, and rollback receipts",
            "auditable command capsules",
        ],
        "repos": ["hub", "hub-registry", "design"],
        "not_now": (
            "Because rollback and approval seams have to be genuinely trustworthy before operator control can stop being a nicer-looking trust fall."
        ),
        "accent": "#0f766e",
        "glow": "#99f6e4",
        "prompt": (
            "Wide cyberpunk operator-control scene with a coffin-shaped secure command case, approval seals, rollback controls, and a tense but grounded control room mood, cinematic concept art, no text, no watermark, 16:9"
        ),
    },
    "evidence-room": {
        "title": "Evidence Room",
        "hook": "A grounded review room for explain and provenance output.",
        "problem": (
            "Proof only helps if humans can review it without excavating six layers of trace noise and raw logs."
        ),
        "brutal_truth": (
            "If the evidence exists but nobody can read it sanely, the system still feels like it is hiding behind complexity."
        ),
        "use_case": (
            "Explain receipts, provenance, and approval-aware review get grouped into a readable inspection room instead of spilling out as debug archaeology."
        ),
        "foundations": [
            "evidence receipts",
            "source classification",
            "approvals",
            "preview and apply separation",
        ],
        "repos": ["core", "hub", "ui", "design"],
        "not_now": (
            "Because the base evidence model still has to become fully canonical first. Pretty review chrome on drifting evidence would just make drift look more professional."
        ),
        "accent": "#334155",
        "glow": "#93c5fd",
        "prompt": (
            "Wide cyberpunk evidence review room with organized dossier cards, provenance tags, layered proof panes, and one exhausted coffee cup, atmospheric concept art, no text, no watermark, 16:9"
        ),
    },
    "persona-echo": {
        "title": "Persona Echo",
        "hook": "Continuity without losing provenance.",
        "problem": (
            "Players want characters to accumulate memory and identity across runs without the software quietly laundering legend into canon."
        ),
        "brutal_truth": (
            "Continuity gets fake fast when the system starts sounding like a hype man instead of a witness."
        ),
        "use_case": (
            "A runner’s ongoing dossier carries approved facts forward, labels inference honestly, and keeps the cool parts grounded."
        ),
        "foundations": [
            "grounded evidence",
            "approval states",
            "clean hub and media ownership",
        ],
        "repos": ["hub", "hub-registry", "media-factory", "design"],
        "not_now": (
            "Because evidence flow and media boundaries still need to mature before continuity artifacts can be trusted instead of merely admired."
        ),
        "accent": "#7c3aed",
        "glow": "#c4b5fd",
        "prompt": (
            "Wide cyberpunk continuity portrait scene with one runner echoed across multiple missions, verified memories and inferred legend clearly contrasted, cinematic concept art, no text, no watermark, 16:9"
        ),
    },
    "shadow-market": {
        "title": "Shadow Market",
        "hook": "A future discovery lane for packs and artifacts.",
        "problem": (
            "Discovery and publication eventually need a trustworthy place to live, but not one that lies about compatibility, moderation, or promotion state."
        ),
        "brutal_truth": (
            "A cool package browser becomes a scam mall the moment trust signals and compatibility truth stop showing up together."
        ),
        "use_case": (
            "A future discovery surface shows package cards, compatibility projections, moderation state, and promotion stage before somebody installs cursed nonsense."
        ),
        "foundations": [
            "registry metadata",
            "moderation states",
            "compatibility projections",
            "promotion staging",
        ],
        "repos": ["hub-registry", "hub", "media-factory", "design"],
        "not_now": (
            "Because marketplace polish is explicitly downstream of honest registry, moderation, and compatibility seams."
        ),
        "accent": "#b91c1c",
        "glow": "#fda4af",
        "prompt": (
            "Wide cyberpunk neon bazaar of digital packages and artifacts with trust lights, moderation tags, and suspiciously stylish vendor stalls, grounded concept art, no text, no watermark, 16:9"
        ),
    },
    "tactical-pulse": {
        "title": "Tactical Pulse",
        "hook": "Shared situational awareness during active sessions.",
        "problem": (
            "A live table needs a shared picture of threats, allies, penalties, and state changes while the scene is still moving."
        ),
        "brutal_truth": (
            "Half of combat confusion is not strategy. It is four people losing track of what the team already knows."
        ),
        "use_case": (
            "Live session state gets summarized into a shared tactical view so players stop asking everybody to repeat the last three important things."
        ),
        "foundations": [
            "session authority",
            "event envelopes",
            "local-first sync",
            "evidence-grounded summaries",
        ],
        "repos": ["mobile", "hub", "core", "design"],
        "not_now": (
            "Because shared awareness features only make sense once session authority, sync, and grounded summaries are already dependable."
        ),
        "accent": "#1d4ed8",
        "glow": "#7dd3fc",
        "prompt": (
            "Wide cyberpunk live-table tactical scene with shared combat HUD, team statuses, threat markers, and coordinated runners under pressure, cinematic concept art, no text, no watermark, 16:9"
        ),
    },
}


def raw_dedent(text: str) -> str:
    return textwrap.dedent(text).strip()


HORIZON_FALLBACK_COPY = {
    "karma-forge": {
        "table_scene": raw_dedent(
            """
            The table wants one spicy house rule and zero repo divorces.

            **GM:** "I want recoil changed, but I do not want a fork, a feud, and three mystery regressions."
            **Player:** "Can we keep our weird initiative patch too?"
            **Chummer6:** "Overlay stack loaded. Conflict report ready. Rollback available if the dev gets creative again."
            **GM:** "Good. Homebrew with receipts, not folklore with combat boots."
            """
        ),
        "meanwhile": "- layering rule overlays in a controlled stack\n- surfacing conflicts before they hit the table\n- keeping every tweak attached to a readable receipt\n- making rollback possible when the experiment catches fire",
        "why_great": "Your table gets to customize aggressively without turning every rules call into archaeology and blame assignment.",
        "pitch_line": "If your table pain is not fork chaos with style, head back to the [Horizons index](README.md) and pitch a sharper headache.",
    },
    "nexus-pan": {
        "table_scene": raw_dedent(
            """
            Rain hits the windows, one phone just rejoined, and nobody wants a sync argument.

            **GM:** "Rain comes down hard. Visibility drops. Security just woke up."
            **Decker:** "My phone died. I missed the last two actions. It chose performance art."
            **Street Sam:** "I already burned one Edge and took 3 stun, right?"
            **Mage:** "And I am still sustaining that spell. Probably."
            **Chummer6:** "Decker device rejoined. Replayed 6 missed events. Current initiative: 11. Rain penalty applied."
            **GM:** "Good. Nobody do forensic accounting. Keep going."
            """
        ),
        "meanwhile": "- keeping session state as one shared event stream\n- recording who changed what and when\n- replaying missed turns onto the rejoined device\n- showing the same initiative, resources, and effects to everyone",
        "why_great": "Less desync, fewer trust fights, faster recovery from bad signal, and more time actually playing the scene instead of rebuilding it from memory.",
        "pitch_line": "If your table pain is different, head back to the [Horizons index](README.md) and pitch a better future mess.",
    },
    "alice": {
        "table_scene": raw_dedent(
            """
            The player is bragging. The sim bench is about to take that personally.

            **Player:** "My infiltrator is unstoppable."
            **GM:** "Last run you got flash-banged by a rent-a-cop and cried."
            **Player:** "That was tactical sorrow."
            **Chummer6:** "Ran 500 seeded breach sims. In 71 percent of them, you fold the moment the hallway goes loud."
            **Player:** "Rude."
            **Chummer6:** "Suggested fixes: stop treating Body as decorative."
            """
        ),
        "meanwhile": "- replaying a seeded scenario with the same inputs\n- holding the runtime stack constant between runs\n- tracing the collapse point instead of just reporting failure\n- showing which rule path, modifier, or choice killed the build",
        "why_great": "Players could find weak assumptions before session night, and GMs could test scenarios without pretending vibes are coverage.",
        "pitch_line": "If your table pain is not bad builds exploding in public, go back to the [Horizons index](README.md) and drag a different problem into the light.",
    },
    "jackpoint": {
        "table_scene": raw_dedent(
            """
            The GM wants a brief. The table wants style without lies.

            **GM:** "Give me a mission brief for tonight."
            **Player:** "But no made-up nonsense this time."
            **Chummer6:** "Compiled from session notes, character facts, and approved evidence."
            **Player:** "What about the red labels?"
            **Chummer6:** "Red is inferred. White is verified. Coffee stains remain optional."
            **GM:** "Good. Now the team can tell style from certainty."
            """
        ),
        "meanwhile": "- pulling together notes, facts, and approved artifacts\n- labeling source class and approval state\n- keeping inferred material visibly separate from grounded evidence\n- preserving provenance instead of laundering guesses into fact",
        "why_great": "You get stylish dossiers and recaps without quietly training the table to trust fiction wearing a tie.",
        "pitch_line": "If your table pain is not briefing-by-vibes, the [Horizons index](README.md) has other future crimes on the shelf.",
    },
    "ghostwire": {
        "table_scene": raw_dedent(
            """
            Everybody remembers the alarm differently, which is exactly how lies are born.

            **GM:** "Who tripped the host?"
            **Player:** "Not me."
            **Other Player:** "That sounds guilty in three different rules eras."
            **Chummer6:** "Replaying event history. Alarm cascade started after the maglock spoof, not the drone jam."
            **GM:** "Perfect. The receipts are snitching for me."
            """
        ),
        "meanwhile": "- replaying stamped event history in order\n- showing state changes around the critical turn\n- tying receipts to the exact moment things went sideways\n- keeping memory contests from becoming rules policy",
        "why_great": "Post-run disputes become recoverable instead of devolving into six confident but incompatible witness statements.",
        "pitch_line": "If your table pain is not memory lying with confidence, take a different alley in the [Horizons index](README.md).",
    },
    "rule-x-ray": {
        "table_scene": raw_dedent(
            """
            The dice pool changed, so naturally the room became a courtroom.

            **Player:** "Why did I drop from 12 to 9?"
            **GM:** "Weather, wounds, and recoil."
            **Player:** "That sounds suspiciously fast."
            **Chummer6:** "Base 12. Rain -1. Wounds -1. Recoil -1. Final 9."
            **GM:** "Look at that. The machine brought receipts and the dev brought nothing."
            """
        ),
        "meanwhile": "- tracing every modifier back to a concrete source\n- exposing the chain of causes behind the total\n- separating core math from scripted edge cases\n- making the final number explain itself on demand",
        "why_great": "Opaque math stops being table poison when the answer can show its work fast enough to keep the scene moving.",
        "pitch_line": "If your table pain is not mystery math, the [Horizons index](README.md) has other elegant disasters ready.",
    },
    "heat-web": {
        "table_scene": raw_dedent(
            """
            The crew thinks last run vanished into the rain. The city disagrees.

            **Player:** "That gang probably forgot about us."
            **GM:** "That is adorable."
            **Chummer6:** "Heat graph updated. You now owe favors in two districts and a bartender wants you gently dead."
            **Player:** "So consequences are a service now?"
            **GM:** "Apparently, and the dev made them searchable."
            """
        ),
        "meanwhile": "- linking events, factions, debts, and witnesses into one graph\n- tracking delayed fallout instead of waiting for GM memory miracles\n- grounding future pressure in recorded actions\n- surfacing who is mad, why, and how soon it matters",
        "why_great": "Campaign consequences stop evaporating and start feeling like a living city with receipts and grudges.",
        "pitch_line": "If your table pain is not forgotten consequences, browse the other bad futures in the [Horizons index](README.md).",
    },
    "mirrorshard": {
        "table_scene": raw_dedent(
            """
            The player wants both futures until one of them costs karma.

            **Player:** "What if I go cyberarm now instead of magic cleanup?"
            **GM:** "Pick a lane."
            **Chummer6:** "Compared both paths. Future A hits harder. Future B survives longer. Future C is what happens when the dev lets scope vote."
            **Player:** "I suddenly respect previews."
            """
        ),
        "meanwhile": "- holding two candidate futures side by side\n- diffing the rules and consequences that diverge\n- keeping provenance visible across both branches\n- making previews feel like informed choices instead of romantic mistakes",
        "why_great": "Big choices get easier to trust when you can compare the damage before you marry one timeline.",
        "pitch_line": "If your table pain is not commitment with receipts, the [Horizons index](README.md) still has plenty of future trouble.",
    },
    "run-passport": {
        "table_scene": raw_dedent(
            """
            The character crossed a rules border and customs is in a bad mood.

            **Player:** "Can I move this runner into the new environment?"
            **GM:** "Depends whether the gear is legal or eldritch."
            **Chummer6:** "Migration preview ready. Two loadout items fail. One quality mutates. One habit survives because the dev forgot to kill it."
            **Player:** "So this is a passport and a threat assessment."
            """
        ),
        "meanwhile": "- carrying runtime identity and lineage with the character\n- projecting compatibility before the jump happens\n- flagging illegal or drifting interactions early\n- making migration a previewable process instead of a leap of faith",
        "why_great": "Portability gets honest: less surprise breakage, less hidden drift, and fewer characters smuggling cursed assumptions across borders.",
        "pitch_line": "If your table pain is not cross-era customs enforcement, the [Horizons index](README.md) has different paperwork nightmares.",
    },
    "threadcutter": {
        "table_scene": raw_dedent(
            """
            Two clever overlays just met and both think they are the main character.

            **GM:** "Can we run both mod packs?"
            **Player:** "Probably."
            **Chummer6:** "Conflict report generated. Both overlays modify the same recoil rule. One of them also lies about load order."
            **GM:** "Excellent. The software found the duel before the table did."
            """
        ),
        "meanwhile": "- comparing overlays before they collide at runtime\n- surfacing competing claims on the same seam\n- showing what breaks, what wins, and what rolls back\n- making conflict analysis a tool instead of a postmortem",
        "why_great": "Customization gets safer when the fight happens in a report first instead of in front of a live session.",
        "pitch_line": "If your table pain is not clever mods drawing knives, the [Horizons index](README.md) has other future messes to browse.",
    },
    "blackbox-loadout": {
        "table_scene": raw_dedent(
            """
            The run starts in ten minutes and the software just became a judgmental quartermaster.

            **Player:** "I am ready."
            **GM:** "You said that last week without ammo."
            **Chummer6:** "Run-readiness check failed. Missing medkit, spare magazine, fake SIN coverage, and self-respect."
            **Player:** "The last one feels personal."
            """
        ),
        "meanwhile": "- checking essentials against the active runtime stack\n- projecting likely weak points before the first scene lands\n- comparing the loadout against mission context\n- shaming preventable mistakes with evidence instead of vibes",
        "why_great": "The tool catches stupid-prep deaths before the NPCs do, which is an unusually kind form of cruelty.",
        "pitch_line": "If your table pain is not pre-run idiocy with receipts, the [Horizons index](README.md) offers different embarrassments.",
    },
    "command-casket": {
        "table_scene": raw_dedent(
            """
            A supposedly tiny admin tweak just grew a receipt trail and rollback drama.

            **GM:** "Who approved that roster change?"
            **Player:** "I thought it just happened."
            **Chummer6:** "Operator action capsule found. Requested by GM. Approved at 19:42. Rollback available."
            **GM:** "Good. I want controlled changes, not mystery buttons."
            """
        ),
        "meanwhile": "- wrapping sensitive actions in auditable command capsules\n- storing requester, approval, and outcome data together\n- attaching preview and rollback to the action\n- making 'who did what?' answerable without guesswork",
        "why_great": "Important changes become inspectable and reversible instead of turning into admin folklore with a bad memory.",
        "pitch_line": "If operator mystery meat is not your table pain, the [Horizons index](README.md) has other unfinished schemes.",
    },
    "evidence-room": {
        "table_scene": raw_dedent(
            """
            The proof exists. The problem is that humans still have to read it.

            **Reviewer:** "Can I see the explain chain without opening six cursed tabs?"
            **GM:** "Aim high."
            **Chummer6:** "Evidence room assembled. Provenance grouped. Approval state visible. Coffee strength not included."
            **Reviewer:** "Now this looks less like debug archaeology and more like a case file."
            """
        ),
        "meanwhile": "- grouping receipts into a readable review room\n- separating grounded evidence from decorative trace noise\n- keeping approval state attached to the proof\n- making inspection feel like review instead of excavation",
        "why_great": "Proof becomes something humans can actually inspect without treating complexity as authority.",
        "pitch_line": "If your table pain is not readable evidence, the [Horizons index](README.md) still has plenty of future nonsense.",
    },
    "persona-echo": {
        "table_scene": raw_dedent(
            """
            The player wants continuity, not software-written fan fiction.

            **Player:** "Can my runner's legend carry forward without turning fake?"
            **GM:** "Only if the machine knows the difference between witness and hype man."
            **Chummer6:** "Continuity artifact ready. Approved facts kept. Inferred legend labeled. Embarrassing failures preserved for character growth."
            **Player:** "Cruel. Honest. Acceptable."
            """
        ),
        "meanwhile": "- carrying approved continuity across runs\n- labeling inference instead of laundering it into canon\n- grounding the cool parts in evidence and provenance\n- keeping character myth from mutating into unreviewed fanfic",
        "why_great": "Characters get memory and identity across runs without the software quietly lying on their behalf.",
        "pitch_line": "If continuity with receipts is not your table pain, the [Horizons index](README.md) has other future temptations.",
    },
    "shadow-market": {
        "table_scene": raw_dedent(
            """
            The package browser is either a helpful market or a scam mall with neon trim.

            **Player:** "This one looks cool."
            **GM:** "That is not evidence."
            **Chummer6:** "Package card loaded. Compatibility partial. Moderation pending. Promotion state: not ready for your bad ideas yet."
            **Player:** "So the marketplace finally learned to say no."
            """
        ),
        "meanwhile": "- surfacing trust signals next to the shiny thing\n- projecting compatibility before installation\n- keeping moderation and promotion state visible\n- making discovery feel less like cursed zip roulette",
        "why_great": "Discovery stops being a trap door when compatibility, moderation, and promotion truth show up on the same card.",
        "pitch_line": "If your table pain is not plugin bazaar trust, the [Horizons index](README.md) has other future appetites.",
    },
    "tactical-pulse": {
        "table_scene": raw_dedent(
            """
            Everyone swears they are paying attention. The combat state says otherwise.

            **GM:** "The drone is flanking, the mage is lit, and the hallway is worse now."
            **Player:** "Can somebody repeat the last three important things?"
            **Chummer6:** "Shared pulse updated. Threat icons, ally states, active penalties, and priorities are live."
            **GM:** "Finally. Situational awareness as a service."
            """
        ),
        "meanwhile": "- summarizing live state into one shared tactical view\n- tracking threats, allies, penalties, and shifting priorities\n- grounding summaries in actual session authority\n- helping the table stop re-asking the same urgent question",
        "why_great": "Shared awareness turns combat confusion back into tactics instead of repeated recap labor.",
        "pitch_line": "If your table pain is not collective amnesia under fire, the [Horizons index](README.md) holds other future fixes.",
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
    return dedent(
        f"""
        ---

        <sub>Updated: {TODAY}</sub>
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
    nodes: list[tuple[int, int]] | None = None,
) -> None:
    active_nodes = nodes or [(220, 210), (430, 170), (610, 280), (770, 150), (930, 245), (1080, 180)]
    for idx, (x, y) in enumerate(active_nodes):
        overlay_circle(pixels, width, height, cx=x, cy=y, radius=18 if idx % 2 else 14, color=glow, alpha=0.45)
        if idx:
            px, py = active_nodes[idx - 1]
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


def audit_ea_media_manifest() -> None:
    if not EA_MEDIA_MANIFEST_PATH.exists():
        return
    try:
        loaded = json.loads(EA_MEDIA_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        raise ValueError("EA media manifest is unreadable") from None
    if not isinstance(loaded, dict):
        raise ValueError("EA media manifest has invalid shape")
    pack_audit = loaded.get("pack_audit")
    if isinstance(pack_audit, dict):
        tableau_count = int(pack_audit.get("tableau_count") or 0)
        adjacent_repeat_count = int(pack_audit.get("adjacent_repeat_count") or 0)
        if tableau_count > 2:
            raise ValueError(f"EA media pack audit failed: tableau_count={tableau_count}")
        if adjacent_repeat_count > 0:
            raise ValueError(f"EA media pack audit failed: adjacent_repeat_count={adjacent_repeat_count}")
    assets = loaded.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("EA media manifest is missing assets")
    failures: list[str] = []
    for row in assets:
        if not isinstance(row, dict):
            continue
        target = str(row.get("target") or "").strip()
        status = str(row.get("status") or "").strip()
        output = str(row.get("output") or "").strip()
        if target and (status.startswith("rejected") or "rendered" not in status or not output):
            failures.append(f"{target}:{status or 'missing_status'}")
    if failures:
        raise ValueError(f"EA media manifest contains non-rendered assets: {', '.join(failures[:6])}")


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
        if path.exists() and path.is_file():
            return path.read_bytes()
        raise ValueError(f"missing EA-generated media asset: {path.relative_to(GUIDE_REPO).as_posix()}")
    return media_bytes


def write_assets() -> None:
    audit_ea_media_manifest()
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
        detail_target = GUIDE_REPO / "assets" / "horizons" / "details" / f"{slug}-scene.png"
        write_binary(detail_target, require_ea_media_bytes(detail_target, media_manifest))


def page_markdown(title: str, body: str) -> str:
    return f"# {title}\n\n{body.strip()}\n"


def image_markdown(alt: str, path: str) -> str:
    title = IMAGE_TITLES.get(path, "").strip()
    if title:
        return f'![{alt}]({path} "{title}")'
    return f"![{alt}]({path})"


def image_banner(alt: str, path: str) -> str:
    image = image_markdown(alt, path)
    title = IMAGE_TITLES.get(path, "").strip()
    if not title:
        return image
    return f"{image}<br>_[{title}]({path})_"


def format_dialogue_markdown(text: str) -> str:
    lines: list[str] = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if line.startswith("> "):
            line = line[2:].strip()
        match = re.match(r"\*\*([^:\n*]+):\*\*\s*(.+)", line)
        if match:
            speaker, speech = match.groups()
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(f"> **{speaker}**<br>")
            lines.append(f"> {speech}")
            continue
        match = re.match(r"([A-Za-z][A-Za-z0-9 '\\-]{0,30}):\\s*(.+)", line)
        if match:
            speaker, speech = match.groups()
            if speaker.strip().lower() not in {"tonight", "scene", "at the table"}:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.append(f"> **{speaker.strip()}**<br>")
                lines.append(f"> {speech.strip()}")
                continue
        if raw.lstrip().startswith(">"):
            lines.append(f"> {line}")
        else:
            lines.append(line)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines).strip()


def part_page(name: str, item: dict[str, object]) -> str:
    owns = "\n".join(f"- {line}" for line in item["owns"])
    not_owns = "\n".join(f"- {line}" for line in item["not_owns"])
    at_table = str(item.get("use_case") or item.get("at_table") or "").strip()
    why_block = str(item["why"]).strip()
    if at_table:
        why_block += f"\n\nAt the table: {at_table}"
    banner = image_banner(f"{item['title']} banner", f"../assets/parts/{name}.png")
    body = (
        f"{banner}\n\n"
        f"**{item['tagline']}**\n\n"
        f"{item['intro']}\n\n"
        "## You touch this when...\n\n"
        f"{why_block}\n\n"
        "## What it owns\n\n"
        f"{owns}\n\n"
        "## What it does not own\n\n"
        f"{not_owns}\n\n"
        "## What is happening now\n\n"
        f"{item['now']}\n\n"
        "## Go deeper\n\n"
        "- [Program map](README.md)\n"
        "- [Current phase](../NOW/current-phase.md)\n"
        "- [Where to go deeper](../WHERE_TO_GO_DEEPER.md)\n"
        + footer("chummer6-design ownership map", "current public shape", "owning repo READMEs")
    )
    return page_markdown(str(item["title"]), body)


def horizon_page(slug: str, item: dict[str, object]) -> str:
    fallback = HORIZON_FALLBACK_COPY.get(slug, {})
    title = str(item["title"])
    foundations = "\n".join(f"- {line}" for line in item["foundations"])
    problem = str(item.get("problem") or item.get("brutal_truth") or fallback.get("problem") or "").strip()
    scene = format_dialogue_markdown(
        str(item.get("table_scene") or item.get("scene") or fallback.get("table_scene") or item.get("use_case") or "").strip()
    )
    meanwhile = str(item.get("meanwhile") or fallback.get("meanwhile") or "").strip()
    why_great = str(item.get("why_great") or fallback.get("why_great") or item.get("brutal_truth") or item.get("hook") or "").strip()
    why_waits = str(item.get("why_waits") or item.get("not_now") or "It stays parked in the garage until the current foundation work is actually done.").strip()
    pitch_line = str(
        item.get("pitch_line")
        or fallback.get("pitch_line")
        or "If your table pain is different, head back to the [Horizons index](README.md) and pitch a better future mess."
    ).strip()
    meanwhile_block = (
        "\n## Meanwhile, Chummer is doing this\n\n"
        f"{meanwhile}\n"
        if meanwhile
        else ""
    )
    scene_detail = (
        '<p align="center">'
        f'<img src="../assets/horizons/details/{slug}-scene.png" alt="{title} dialogue scene still" width="420">'
        "</p>\n\n"
    )
    body = (
        f"{image_banner(f'{title} banner', f'../assets/horizons/{slug}.png')}\n\n"
        f"**{item['hook']}**\n\n"
        "_Status: Horizon only — future idea, not active build work._\n\n"
        "## What problem does this solve?\n\n"
        f"{problem}\n\n"
        "## A real table scene\n\n"
        f"{scene}\n\n"
        f"{scene_detail}"
        f"{meanwhile_block}\n"
        "## Why that would be great\n\n"
        f"{why_great}\n\n"
        "## Why it is still a Horizon\n\n"
        f"{why_waits}\n\n"
        "## What would need to exist first\n\n"
        f"{foundations}\n\n"
        "## Pitch your own future\n\n"
        f"{pitch_line}\n"
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
                {image_banner("Chummer6 hero banner", "assets/hero/chummer6-hero.png")}

                > **{landing_tagline}**
                >
                > {readme_intro}

                If you only need the one-sentence pitch, it is this: Chummer6 is trying to help players and GMs answer "what just happened?" fast enough that the run keeps moving.

                ## Pick your path

                - **I am new here:** [Start Here](START_HERE.md)
                - **Give me the product story:** [What Chummer6 is](WHAT_CHUMMER6_IS.md)
                - **Tell me what is real today:** [Current status](NOW/current-status.md)
                - **Show me the parts when I actually care:** [Program map](PARTS/README.md)
                - **Show me the future rabbit holes:** [Horizons](HORIZONS/README.md)
                - **Point me at the deeper source material:** [Where to go deeper](WHERE_TO_GO_DEEPER.md)

                ## What this means at a real table

                > **GM**<br>
                > "Rain, noise, and recoil all apply here."

                > **Player**<br>
                > "Then why did my pool drop to 9?"

                > **Chummer6**<br>
                > "Base 11. Rain -1. Wounds -1. Recoil -1. Final 9."

                {readme_body}

                ## Why this is worth watching

                {watch_intro}

{why_care_lines}

                If that sounds like your kind of software, the next stop is [What Chummer6 is](WHAT_CHUMMER6_IS.md).

                ## What is happening right now

                Right now the crew is doing trust work, not bolting neon spoilers onto half-built engines.
                {tension}

                Current focus:
{current_focus_lines}
                - keep public previews honestly labeled until they become the real thing

                - [Current phase](NOW/current-phase.md)
                - [Current status](NOW/current-status.md)
                - [Public surfaces](NOW/public-surfaces.md)

                ## When you want the map

                You do not need the seam map first, but it is here when you need it:

                - **Rules truth** lives in [Core](PARTS/core.md)
                - **Prep and inspect** lives in [UI](PARTS/ui.md)
                - **Table play** lives in [Mobile](PARTS/mobile.md)
                - **Online coordination** lives in [Hub](PARTS/hub.md)
                - **Shared chrome** lives in [UI Kit](PARTS/ui-kit.md)
                - **Artifacts and compatibility** live in [Hub Registry](PARTS/hub-registry.md)
                - **Render jobs** live in [Media Factory](PARTS/media-factory.md)
                - **Long-range plan** lives in [Design](PARTS/design.md)

                If you want the full guided version, read the [Program map](PARTS/README.md).

                ## Future rabbit holes

                {horizon_intro}

                - [Horizons index](HORIZONS/README.md)

                ## POC shelf

                {image_banner("POC warning banner", "assets/hero/poc-warning.png")}

                Want to know whether all this talk cashes out into real software? This is the shelf where you stop reading and start risking your evening.

                - [Chummer6 Releases](https://github.com/ArchonMegalon/Chummer6/releases)

                > **Street warning:** POC builds are for curious chummers, not cautious wageslaves.<br>
                > They may be unstable, unfinished, weird, or one bad click away from getting your deck **marked, hacked, or bricked**.<br>
                > Install at your own risk.

                The binaries come from the active Chummer6 codebase, not from this guide repo.

                Need the long-range plan or implementation trail after that? [Where to go deeper](WHERE_TO_GO_DEEPER.md).
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
                {image_banner("Start here banner", "assets/pages/start-here.png")}

                Start with the problem you have tonight, not with a lecture about how the software is arranged.

                Chummer6 is here for four common moments: you need to run a live session, prove why a number changed, support a cursed house rule, or peek at the future rabbit holes.

                You do not need the internal map first. You need the shortest path to the page that tells you whether this can run a session, explain a weird number, support a cursed table rule, or show you what the project is trying to become.

                ## I want to run a session

                You want the table-facing reality: what is usable now, what is still preview, and how local-first play is supposed to behave when the signal gets stupid.

                Tonight: game night starts in twenty minutes, somebody is on a phone, somebody else is on a laptop, and you need the shortest path to "yes, this can carry the session."

                Start here: [NOW/public-surfaces.md](NOW/public-surfaces.md)

                ## I want to check whether the math is right

                You want proof, not vibes: where the modifier came from, why the total changed, and what kind of trust Chummer6 is trying to earn at the table.

                Tonight: two players disagree about a dice pool and nobody wants to solve it with volume.

                Start here: [PARTS/core.md](PARTS/core.md)

                ## I want to bend the rules for my table

                You want the lane that handles scripted edge cases, multi-era weirdness, and the deeper docs behind custom behavior.

                Tonight: your table has a house rule, an SR4 habit, or a cursed exception that needs a real home instead of a sticky note.

                Start here: [WHERE_TO_GO_DEEPER.md](WHERE_TO_GO_DEEPER.md)

                ## I want to see where the project is going

                You want the future-facing ideas: the problems the project wants to solve later, the table pain behind them, and the stuff that is still firmly in dream territory.

                Tonight: you already get the current pitch and now want to know what the next rabbit holes could be.

                Start here: [HORIZONS/README.md](HORIZONS/README.md)

                ## If you want the two-minute product story first

                Read [WHAT_CHUMMER6_IS.md](WHAT_CHUMMER6_IS.md).

                ## If you want the full map later

                Read [PARTS/README.md](PARTS/README.md) when you actually care how the parts fit together.
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
                {image_banner("What Chummer6 is banner", "assets/pages/what-chummer6-is.png")}

                {what_intro}

                {what_body}

                ## What it is becoming for players and GMs

                Chummer6 is not just trying to be a character manager with nicer chrome. It is trying to become a toolkit that helps players and GMs:

                - get a ruling quickly
                - see why that ruling happened
                - keep playing when the network misbehaves
                - carry different rules eras without pretending they are identical
                - handle odd table logic in code instead of folklore

                ## A real table moment

                > **GM**<br>
                > "You are wounded, sustaining, and standing in bad weather. Roll it."

                > **Player**<br>
                > "Why is my pool lower than I expected?"

                > **Chummer6**<br>
                > "Base 11. Wounds -1. Sustaining -1. Weather -1. Final 8."

                > **GM**<br>
                > "Good. We move."

                That is the product story in miniature. Not "trust me, bro." Not "dig through source." Just a fast answer with enough proof to keep the table moving.

                ## Why that matters at the table

                When the number moves, the table should not have to stop and reverse-engineer folklore. When the network gets stupid, the session should not die. When a table uses a weird era mix or one cursed house rule, that weirdness should have a real home instead of a pile of "remember this next time" notes.

                ## What feels different from older opaque tool behavior

                The project is leaning harder into explicit trust:

                - same inputs should produce the same result
                - the result should come with a readable receipt
                - the session should survive local or offline reality
                - the active rules and config stack should be visible
                - the ugly edge cases should have a real extension lane

                ## The kinds of trust it wants to earn

                - **Math trust:** the number should be reproducible.
                - **Receipt trust:** the path to the number should be visible.
                - **Session trust:** your table should not collapse because Wi-Fi had a mood.
                - **Change trust:** custom rules, era differences, and future expansions should be legible instead of spooky.

                ## What you would actually notice on game night

                - fewer "wait, why did that number move?" pauses
                - fewer arguments that depend on memory or volume
                - faster recovery when one device falls out of the session
                - clearer separation between verified facts, inferred summaries, and made-up nonsense
                - more honest labels about what is real now versus still moving

                ## Why there are multiple parts

                The project has multiple parts because each job is different. Rules truth, prep, live play, online coordination, shared UI, artifact handling, render jobs, and the long-range plan all need room to do their work without turning into one giant haunted monolith.

                If you want that map, go to [PARTS/README.md](PARTS/README.md).

                Need the long-range plan or implementation trail after the product story? Start with [PARTS/README.md](PARTS/README.md) or [WHERE_TO_GO_DEEPER.md](WHERE_TO_GO_DEEPER.md).
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
                {image_banner("Where to go deeper banner", "assets/pages/where-to-go-deeper.png")}

                This is the path for when the friendly tour stops being enough.

                If you want the long-range plan, the actual software, or the place to call out stale/confusing guide copy, start here instead of guessing which repo corner is secretly in charge.

                ## Start here when you want more than the tour

                - Start with `chummer6-design` when you want the long-range plan.
                - Go to the owning code repos when you want the software itself.
                - Come back to Chummer6 when you want the friendly guided version again.

                ## What each place is for

                - `chummer6-design`: the long-range plan and deeper design notes
                - owning repos: the working software and repo-specific detail
                - Chummer6: the friendly guide, examples, and public-facing orientation

                ## If you want the source of truth

                Chummer6 is the friendly guide.

                - `chummer6-design` holds the long-range plan
                - the owning repos hold the software
                - if this guide feels stale or confusing, call it out here so it can be fixed
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
                {image_banner("Current phase banner", "../assets/pages/current-phase.png")}

                {current_phase_intro}

                {current_phase_body}

                ## The focus right now

                - lock in the rules and session boundaries
                - keep live play and prep from bleeding into each other
                - make the shared UI pieces feel consistent instead of improvised
                - finish the registry and media services that support the public surfaces
                - keep public previews honestly labeled until they become the real thing

                ## What this means for your next session

                If you are using Chummer6 at the table tonight, read this phase as: trust work first. The important promise is that the math should be traceable and the session should not die just because Wi-Fi did. If a page still says preview, read that as "shape can move," not "the engine is fake."

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
                {image_banner("Current status banner", "../assets/pages/current-status.png")}

                {current_status_intro}

                ## The short version

                - the parts are real
                - the public surfaces are still preview, not the final public shape
                - play is still the next major product seam to finish
                - UI kit, registry, and media exist, but are still becoming fully real boundaries
                - a few deeper plan docs are still catching up

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
                {image_banner("Public surfaces banner", "../assets/pages/public-surfaces.png")}

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

                It means the surface is there, but the software, release, and support story do not line up cleanly enough yet to call it the real promoted version.
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
                {image_banner("Parts overview banner", "../assets/pages/parts-index.png")}

                {parts_index_intro}

                {parts_index_body}

                ## What you actually notice first

                Most people do not care about the internal map first. They care about the symptom.

                Read the parts like this:

                - **Core** = when you need the math to stop bluffing
                - **UI** = when you are building or inspecting before the run
                - **Mobile** = when the session is already live
                - **Hub** = when being online actually helps instead of getting in the way
                - **UI Kit** = when shared chrome should stop being copy-pasted improv
                - **Hub Registry** = when artifacts and compatibility need to be real
                - **Media Factory** = when generated output needs a dedicated pipeline
                - **Design** = when you want the long-range plan and ownership map

                ## How to read this folder

                Each page starts with the moment that would make you care:

                - when you touch this part
                - why it matters
                - what it owns
                - what it does not own
                - what is happening now

                ## Where to start

                If you want the most important seam for live sessions right now, read [mobile](mobile.md).

                If you want the strongest answer to "why should I trust the math?", read [core](core.md).

                If you want the whole-program ownership map, read [design](design.md).
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
                {image_banner("Horizons overview banner", "../assets/pages/horizons-index.png")}

                {horizons_index_intro}

                {horizons_index_body}

                > **Reality check from the troll behind the curtain**
                > These are horizon ideas, not signed blood contracts. Some may ship. Some may mutate. Some may remain beautiful nonsense forever.
                > If your table pain is different, pitch a better future. Later there should be a better way for chummers to help signal which rabbit holes deserve the next flashlight.
                >
                > Also, if the dev says all of these are "basically done," check whether he also says "one tiny refactor" before setting a repo on fire.

                ## Pick the pain, then the codename

                - **My table desyncs and devices go weird.** [NEXUS-PAN](nexus-pan.md)
                - **We argue about why the math did that.** [RULE X-RAY](rule-x-ray.md)
                - **We only find weak builds after they die.** [ALICE](alice.md)
                - **We want house rules without fork chaos.** [KARMA FORGE](karma-forge.md)
                - **We want dossiers and recaps without made-up nonsense.** [JACKPOINT](jackpoint.md)
                - **We need to replay what actually happened after a run goes sideways.** [GHOSTWIRE](ghostwire.md)
                - **We keep forgetting campaign consequences until the GM remembers them dramatically.** [HEAT WEB](heat-web.md)
                - **We want honest migration between rule environments.** [RUN PASSPORT](run-passport.md)
                - **Our clever mods keep trying to stab each other.** [THREADCUTTER](threadcutter.md)
                - **We want to compare two futures before we commit to one.** [MIRRORSHARD](mirrorshard.md)
                - **We need a brutal pre-run idiot check.** [BLACKBOX LOADOUT](blackbox-loadout.md)

                ## Other rabbit holes still on the shelf

                - **We need controlled operator actions with receipts and undo.** [COMMAND CASKET](command-casket.md)
                - **We want a grounded review room for explain and provenance.** [EVIDENCE ROOM](evidence-room.md)
                - **We want continuity artifacts without fake authority.** [PERSONA ECHO](persona-echo.md)
                - **We may eventually need a discovery lane for packs and artifacts.** [SHADOW MARKET](shadow-market.md)
                - **We want shared situational awareness during live sessions.** [TACTICAL PULSE](tactical-pulse.md)

                ## What you get on each page

                - the table pain
                - a short scene so you can feel it
                - what Chummer would be doing while the table keeps playing
                - the payoff if it ever lands
                - the reason it is still parked
                - the foundations that have to exist first

                ## Pitch your own future

                If your table pain is not on this list, good. Horizons is not holy scripture. Bring a better problem and a sharper idea.
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

                That means the interesting work is not “ship a thousand flashy features” but “make the boundaries honest enough that future features stop being expensive lies.”

                ## What moved

                - the multi-part program is visible in public now
                - Chummer6 exists as the human guide
                - the guide is getting stricter about what is preview and what is actually ready
                - the play/session boundary is still the next major seam to finish

                ## What is still not finished

                - shared rules and interfaces still need cleanup
                - the full live-play separation is not done
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
                - **receipt**: the readable explanation of how a ruling or modifier was calculated
                - **provenance**: where each rule, modifier, or artifact fact came from
                - **local-first**: the important stuff keeps working even when the network gets stupid
                - **preview**: visible and usable, but still moving toward its final public shape
                - **runtime stack**: the exact rules, options, and package mix the session is using
                - **ruleset**: the era or package of Shadowrun rules currently in play
                - **POC**: a build or surface that is real enough to try, but still rough enough to bite
                - **horizon**: a future idea that is being explored, not promised
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
                ## Using Chummer6

                ### Can I actually use this now?

                Yes, with honest caveats. There are usable public surfaces and a real POC shelf, but several surfaces are still explicitly marked preview. Read that as "real but still moving," not "imaginary."

                ### Is it offline-safe?

                That is one of the main promises. Local-first and offline-ready behavior are part of the product story, and the current public docs explicitly treat surviving bad connectivity as a real requirement.

                ### Why would I trust it more than old opaque tool behavior?

                Because the project is pushing toward deterministic outcomes plus readable receipts and provenance. The goal is not just to hand you a number, but to show how the number happened.

                ### Is this replacing older Chummer habits?

                It is the next Chummer-shaped toolkit, not just a fresh coat of paint on older habits. If you are coming from older Chummer use, expect familiar goals with a stronger push toward receipts, local-first session flow, and clearer seams between parts.

                ### Can I keep my old habits?

                Some habits, yes. But the project is trying to make more of the stack explicit: what rules are active, where a modifier came from, what is preview, and which part owns which responsibility.

                ### If I only care about one thing, what is the one thing it does better?

                Rules truth with receipts. The standout promise is that a rules call should be explainable fast enough to help the table keep moving.

                ### What should I show a skeptical GM or player first?

                Start with [WHAT_CHUMMER6_IS.md](WHAT_CHUMMER6_IS.md) for the product pitch, then [NOW/current-status.md](NOW/current-status.md) for the honest caveats, then [PARTS/core.md](PARTS/core.md) if the argument is really about trust in the math.

                ## If you want the deeper sources

                ### Where does the deeper plan live?

                In `chummer6-design`, which carries the long-range plan.

                ### Where does the actual code live?

                In the owning code repos. This guide is here so you do not need to reverse-engineer the product story from commit archaeology.

                ### Why are there so many repos?

                Because different jobs need different homes: rules truth, prep, live play, online coordination, shared UI, artifacts, generated media, and the long-range plan.

                ### What is live right now?

                The multi-repo program is live, but several public surfaces are still preview rather than the final promoted shape.

                ### Where do I propose design changes?

                In the [Chummer6 issue tracker](https://github.com/ArchonMegalon/Chummer6/issues). That keeps public feature requests and guide feedback in the public front door instead of throwing normal users into the design repo.

                ### What should I include in a bug report?

                The useful stuff: what you installed, what you clicked, what you expected, what actually happened, and any screenshot or log that helps track the gremlin back to its nest.

                ### Can I help test or suggest future features?

                Yes. Use the [Chummer6 issue tracker](https://github.com/ArchonMegalon/Chummer6/issues) for public feedback, bug reports, and future-feature suggestions. If a horizon idea sounds better than what is on the page, say so.
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
    required.extend(GUIDE_REPO / "assets" / "horizons" / "details" / f"{slug}-scene.png" for slug in HORIZONS)
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
        "## What this means at a real table",
        "## Why this is worth watching",
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
