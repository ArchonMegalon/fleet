#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path
import json


OWNER = "ArchonMegalon"
REPO_NAME = "Chummer6"
REPO_SLUG = f"{OWNER}/{REPO_NAME}"
REPO_URL = f"https://github.com/{REPO_SLUG}.git"
GUIDE_REPO = Path("/docker/chummercomplete/Chummer6")
DESIGN_SCOPE = Path("/docker/chummercomplete/chummer-design/products/chummer/projects/guide.md")
TODAY = "2026-03-11"
POLICY_PATH = Path("/docker/fleet/.chummer6_local_policy.json")
DEFAULT_POLICY = {
    "forbidden_origin_mentions": [],
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
]


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
    policy = dict(DEFAULT_POLICY)
    if POLICY_PATH.exists():
        loaded = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            policy.update(loaded)
    return policy


GUIDE_POLICY = load_policy()


def assert_clean(text: str, *, label: str) -> None:
    lowered = text.lower()
    for item in GUIDE_POLICY.get("forbidden_origin_mentions", []):
        token = str(item).strip()
        if token and token.lower() in lowered:
            raise ValueError(f"{label} contains forbidden Chummer6 provenance text: {token}")


def ensure_github_repo() -> None:
    view = run("gh", "repo", "view", REPO_SLUG, check=False)
    stderr = (view.stderr or "").lower()
    stdout = (view.stdout or "").lower()
    throttled = "rate limit exceeded" in stderr or "rate limit exceeded" in stdout
    if throttled and (GUIDE_REPO / ".git").exists():
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
    patch_err = (patch.stderr or "").lower()
    patch_out = (patch.stdout or "").lower()
    if patch.returncode != 0 and "rate limit exceeded" not in patch_err and "rate limit exceeded" not in patch_out:
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


def write_text(path: Path, content: str) -> None:
    assert_clean(content, label=str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def footer(*sources: str) -> str:
    joined = ", ".join(sources)
    return (
        "\n---\n\n"
        f"_Last synced: {TODAY}_  \n"
        f"_Derived from: {joined}_  \n"
        "_Canonical source: chummer6-design_\n"
    )


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


def hero_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 420" role="img" aria-labelledby="title desc">
  <title id="title">Chummer6 hero banner</title>
  <desc id="desc">A banner showing legacy Chummer, transition arrows, and the new Chummer6 multi-repo program.</desc>
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#111827"/>
      <stop offset="50%" stop-color="#13293d"/>
      <stop offset="100%" stop-color="#0f5132"/>
    </linearGradient>
    <linearGradient id="panel" x1="0" x2="1">
      <stop offset="0%" stop-color="#fff7ed" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#ecfeff" stop-opacity="0.95"/>
    </linearGradient>
  </defs>
  <rect width="1400" height="420" fill="url(#bg)"/>
  <circle cx="160" cy="160" r="120" fill="#1f2937" opacity="0.45"/>
  <circle cx="1180" cy="120" r="160" fill="#0b7285" opacity="0.18"/>
  <g fill="#f59e0b" opacity="0.9">
    <path d="M355 210h150l-28-30h53l42 46-42 46h-53l28-30H355z"/>
  </g>
  <g fill="url(#panel)">
    <rect x="548" y="62" width="784" height="296" rx="28"/>
  </g>
  <g font-family="Segoe UI, Arial, sans-serif">
    <text x="76" y="120" fill="#f8fafc" font-size="32" font-weight="700">Legacy Chummer</text>
    <text x="76" y="162" fill="#cbd5e1" font-size="20">Same shadows.</text>
    <text x="76" y="192" fill="#cbd5e1" font-size="20">Familiar chrome.</text>
    <text x="76" y="238" fill="#fbbf24" font-size="22" font-weight="700">Transition</text>
    <text x="76" y="268" fill="#e2e8f0" font-size="18">from one giant toolbox</text>
    <text x="76" y="294" fill="#e2e8f0" font-size="18">to a clean split program</text>

    <text x="590" y="118" fill="#0f172a" font-size="48" font-weight="800">Chummer6</text>
    <text x="590" y="158" fill="#0f172a" font-size="24" font-weight="600">Same shadows, bigger future.</text>
    <text x="590" y="198" fill="#334155" font-size="20">Visitor center for the next Chummer:</text>
    <text x="590" y="228" fill="#334155" font-size="20">what it is, what is happening now, and what comes later.</text>
  </g>
  <g font-family="Segoe UI, Arial, sans-serif" font-size="18" font-weight="700">
    <rect x="592" y="268" width="152" height="48" rx="16" fill="#0f766e"/>
    <text x="628" y="298" fill="#f0fdfa">core</text>
    <rect x="760" y="268" width="152" height="48" rx="16" fill="#1d4ed8"/>
    <text x="803" y="298" fill="#eff6ff">play</text>
    <rect x="928" y="268" width="152" height="48" rx="16" fill="#7c3aed"/>
    <text x="970" y="298" fill="#f5f3ff">hub</text>
    <rect x="1096" y="268" width="200" height="48" rx="16" fill="#be123c"/>
    <text x="1142" y="298" fill="#fff1f2">registry + media</text>
  </g>
</svg>
"""


def program_map_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 760" role="img" aria-labelledby="title desc">
  <title id="title">Chummer6 program map</title>
  <desc id="desc">A simple map of Chummer6 repos and their relationships.</desc>
  <rect width="1200" height="760" fill="#f8fafc"/>
  <g font-family="Segoe UI, Arial, sans-serif">
    <text x="60" y="70" fill="#0f172a" font-size="34" font-weight="800">Program map</text>
    <text x="60" y="104" fill="#475569" font-size="18">The parts, at a glance.</text>
  </g>
  <g stroke="#94a3b8" stroke-width="4" fill="none">
    <path d="M355 210h145"/>
    <path d="M355 370h145"/>
    <path d="M355 530h145"/>
    <path d="M700 210h145"/>
    <path d="M700 530h145"/>
    <path d="M620 110v80"/>
  </g>
  <g font-family="Segoe UI, Arial, sans-serif" font-size="18" font-weight="700">
    <rect x="500" y="50" width="240" height="90" rx="20" fill="#111827"/>
    <text x="570" y="92" fill="#f8fafc">chummer6-design</text>
    <text x="570" y="118" fill="#cbd5e1" font-size="15" font-weight="500">canonical design</text>

    <rect x="130" y="165" width="225" height="90" rx="20" fill="#0f766e"/>
    <text x="208" y="206" fill="#f0fdfa">core</text>
    <text x="168" y="232" fill="#ccfbf1" font-size="15" font-weight="500">deterministic engine truth</text>

    <rect x="130" y="325" width="225" height="90" rx="20" fill="#1d4ed8"/>
    <text x="196" y="366" fill="#eff6ff">ui</text>
    <text x="164" y="392" fill="#dbeafe" font-size="15" font-weight="500">workbench + desktop/browser</text>

    <rect x="130" y="485" width="225" height="90" rx="20" fill="#7c3aed"/>
    <text x="188" y="526" fill="#f5f3ff">mobile</text>
    <text x="165" y="552" fill="#ede9fe" font-size="15" font-weight="500">play shell + local-first sync</text>

    <rect x="500" y="165" width="225" height="90" rx="20" fill="#be123c"/>
    <text x="583" y="206" fill="#fff1f2">hub</text>
    <text x="541" y="232" fill="#ffe4e6" font-size="15" font-weight="500">hosted APIs + orchestration</text>

    <rect x="500" y="325" width="225" height="90" rx="20" fill="#0f766e"/>
    <text x="573" y="366" fill="#f0fdfa">ui-kit</text>
    <text x="549" y="392" fill="#ccfbf1" font-size="15" font-weight="500">shared visual primitives</text>

    <rect x="500" y="485" width="225" height="90" rx="20" fill="#7c2d12"/>
    <text x="545" y="526" fill="#ffedd5">hub-registry</text>
    <text x="522" y="552" fill="#fed7aa" font-size="15" font-weight="500">artifacts + publication metadata</text>

    <rect x="845" y="165" width="225" height="90" rx="20" fill="#334155"/>
    <text x="892" y="206" fill="#f8fafc">media-factory</text>
    <text x="899" y="232" fill="#cbd5e1" font-size="15" font-weight="500">render-only asset jobs</text>

    <rect x="845" y="405" width="225" height="90" rx="20" fill="#134e4a"/>
    <text x="915" y="446" fill="#ecfeff">Chummer6</text>
    <text x="862" y="472" fill="#cffafe" font-size="15" font-weight="500">visitor center / human guide</text>
  </g>
</svg>
"""


def status_strip_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 220" role="img" aria-labelledby="title desc">
  <title id="title">Chummer6 status strip</title>
  <desc id="desc">Three tiles showing Now, Preview, and Horizon.</desc>
  <rect width="1200" height="220" fill="#f8fafc"/>
  <g font-family="Segoe UI, Arial, sans-serif">
    <rect x="40" y="36" width="350" height="148" rx="24" fill="#0f766e"/>
    <text x="78" y="88" fill="#f0fdfa" font-size="34" font-weight="800">Now</text>
    <text x="78" y="122" fill="#ccfbf1" font-size="18">contract reset, play split,</text>
    <text x="78" y="148" fill="#ccfbf1" font-size="18">UI kit, registry, media seams</text>

    <rect x="425" y="36" width="350" height="148" rx="24" fill="#b45309"/>
    <text x="463" y="88" fill="#fffbeb" font-size="34" font-weight="800">Preview</text>
    <text x="463" y="122" fill="#fef3c7" font-size="18">public surfaces are visible,</text>
    <text x="463" y="148" fill="#fef3c7" font-size="18">but still marked stale_preview</text>

    <rect x="810" y="36" width="350" height="148" rx="24" fill="#4338ca"/>
    <text x="848" y="88" fill="#eef2ff" font-size="34" font-weight="800">Horizon</text>
    <text x="848" y="122" fill="#e0e7ff" font-size="18">Karma Forge, NEXUS-PAN,</text>
    <text x="848" y="148" fill="#e0e7ff" font-size="18">ALICE, JACKPOINT, and friends</text>
  </g>
</svg>
"""


def poc_warning_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 360" role="img" aria-labelledby="title desc">
  <title id="title">POC warning banner</title>
  <desc id="desc">A playful proof-of-concept warning strip for Chummer6 releases.</desc>
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#1f2937"/>
      <stop offset="100%" stop-color="#7c2d12"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="360" fill="url(#bg)"/>
  <g font-family="Segoe UI, Arial, sans-serif">
    <rect x="70" y="70" width="250" height="220" rx="24" fill="#f59e0b"/>
    <circle cx="195" cy="132" r="38" fill="#1f2937"/>
    <rect x="150" y="176" width="90" height="92" rx="18" fill="#1f2937"/>
    <rect x="355" y="82" width="780" height="196" rx="26" fill="#fff7ed" opacity="0.96"/>
    <text x="405" y="138" fill="#7c2d12" font-size="46" font-weight="800">POC build shelf</text>
    <text x="405" y="182" fill="#431407" font-size="22" font-weight="600">For brave idiots and useful test dummies.</text>
    <text x="405" y="220" fill="#7c2d12" font-size="20">Curious enough to click? Good.</text>
    <text x="405" y="250" fill="#7c2d12" font-size="20">Confident enough to trust it blindly? Please do not.</text>
  </g>
</svg>
"""


def horizon_page(title: str, hook: str, problem: str, foundations: list[str], repos: list[str], not_now: str) -> str:
    foundation_lines = "\n".join(f"- {item}" for item in foundations)
    repo_lines = "\n".join(f"- `{item}`" for item in repos)
    return f"""# {title}

**{hook}**

_Status: Horizon only — future idea, not active build work._

{title} is one of the big future rabbit holes: the kind of idea that makes people lean in, grin, and immediately start asking what it would take to make it real.

## What is the idea?
{hook}

## What problem does it solve?
{problem}

## Why this would be cool
Because it would make Chummer feel more connected, more inspectable, and more alive without giving up deterministic runtime truth.

## What foundations it needs first
{foundation_lines}

## Which repos it would touch later
{repo_lines}

## Why it waits
{not_now}
{footer("chummer6-design horizon guidance", "latest public status")}
"""


def write_assets() -> None:
    write_text(GUIDE_REPO / "assets" / "chummer6-hero.svg", hero_svg())
    write_text(GUIDE_REPO / "assets" / "program-map.svg", program_map_svg())
    write_text(GUIDE_REPO / "assets" / "status-strip.svg", status_strip_svg())
    write_text(GUIDE_REPO / "assets" / "poc-warning.svg", poc_warning_svg())


def write_guide_repo() -> None:
    write_assets()

    write_text(
        GUIDE_REPO / "README.md",
        f"""# Chummer6

![Chummer6 hero banner](assets/chummer6-hero.svg)

> **Same shadows. Bigger future. Less confusion.**
>
> Chummer6 is the readable guide to the next Chummer: what it is becoming, how the parts fit together, what is happening right now, and which wild future ideas are still parked in the garage.

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

Chummer6 is the visitor center for the next Chummer.

It explains the split in plain language, gives you the lay of the land, and helps you follow progress without needing to spelunk through every repo.

Think of it like this:

- `chummer6-design` is the blueprint room
- the code repos are the workshops
- **Chummer6 is the map on the wall**

## What’s happening now

![Current status strip](assets/status-strip.svg)

Right now the team is doing foundation work, not bolting neon spoilers onto half-built engines.

Current focus:
- clean up the shared rules and interfaces
- finish the play/session boundary
- make the shared UI kit real
- finish registry and media splits
- keep preview surfaces honestly labeled until they become the real thing

Read more: [Current phase](NOW/current-phase.md)

## Meet the parts

![Program map](assets/program-map.svg)

| Part | What it does | Read more |
| --- | --- | --- |
| Core | The deterministic rules engine | [core](PARTS/core.md) |
| Presentation | The workbench and big-screen UX | [presentation](PARTS/presentation.md) |
| Play | The player/GM shell for sessions and mobile use | [play](PARTS/play.md) |
| Run services | The hosted API and orchestration layer | [run-services](PARTS/run-services.md) |
| UI kit | Shared components, themes, and visual primitives | [ui-kit](PARTS/ui-kit.md) |
| Hub registry | Artifacts, publication, installs, compatibility | [hub-registry](PARTS/hub-registry.md) |
| Media factory | Render jobs, previews, and asset lifecycle | [media-factory](PARTS/media-factory.md) |
| Design | Canonical design front door | [design](PARTS/design.md) |

## Horizon ideas

Some ideas are too fun not to write down.  
They are real possibilities, but they are **not active build commitments**.

- [Karma Forge](HORIZONS/karma-forge.md) — personalized rule stacks without fork chaos
- [NEXUS-PAN](HORIZONS/nexus-pan.md) — a live synced table instead of isolated character files
- [ALICE](HORIZONS/alice.md) — stress-test a build before the run
- [JACKPOINT](HORIZONS/jackpoint.md) — turn grounded data into dossiers and briefings
- [GHOSTWIRE](HORIZONS/ghostwire.md) — replay a run like a forensic sim
- [RULE X-RAY](HORIZONS/rule-x-ray.md) — click any number and see where it came from

See all: [Horizon index](HORIZONS/README.md)

## What you can do

If this repo helped you get your bearings, here is how to help back:

- **Give Chummer6 a star** if this guide saved you from digging through half the Matrix just to understand what is going on.
- **Be my test dummy and install the software.**
- **Grab the latest POC build from [Releases](../../releases).**
- **Seriously: never trust software. Never trust a dev.**
- **If a build glitches, breaks, crashes, or does something cursed, tell me exactly how you got there.**
- **If this repo is stale, confusing, or reads like corp training material, call it out.**

> **Street warning:** POC builds are for curious chummers, not cautious wageslaves.  
> They may be unstable, unfinished, weird, or one bad click away from getting your deck **marked, hacked, or bricked**.  
> Install at your own risk.

In other words: kick the tires, break the thing, and tell me where the smoke came out.

## POC shelf

![POC warning banner](assets/poc-warning.svg)

If there is a fresh proof-of-concept build ready for brave idiots and helpful test dummies, the shelf is here:

- [Chummer6 Releases](../../releases)

The binaries themselves come from the active Chummer codebase, not from this guide repo.

## Where to go deeper

Chummer6 explains. It does not ship code and it does not replace the blueprint.

- The long-range plan lives in `chummer6-design`
- The software itself lives in the owning code repos
- Chummer6 is the friendly guide for humans
{footer("chummer6-design", "latest public status", "owning repo READMEs")}
""",
    )

    write_text(
        GUIDE_REPO / "START_HERE.md",
        f"""# Start Here

Welcome to Chummer6.

If you just landed here and are wondering why one Shadowrun tool suddenly seems to have a small constellation of repos around it, you are in the right place.

Chummer is growing from one legacy app into a set of focused parts: a rules engine, a workbench, a play shell, hosted services, a shared UI layer, an artifact registry, a media pipeline, and a design/control layer around all of that.

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
{footer("chummer6-design README", "latest public status", "repo READMEs")}
""",
    )

    write_text(
        GUIDE_REPO / "WHAT_CHUMMER6_IS.md",
        f"""# What Chummer6 Is

Chummer6 is the human guide to the next Chummer.

It exists because the real program is already split across multiple repos, active previews, and a canonical design repo. That is powerful, but it is also a lot to throw at someone who just wants the lay of the land.

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

## Who this helps

- curious newcomers
- returning Chummer users
- people following the split program
- contributors who want the lay of the land before diving into the heavy stuff

## How to use it

If you want the quick orientation, start with [Start Here](START_HERE.md).
If you want the current phase, go to [NOW/current-status.md](NOW/current-status.md).
If you want the big future ideas, go to [HORIZONS/README.md](HORIZONS/README.md).

## What Chummer6 does not do

Chummer6 is intentionally **not**:

- the canonical design source
- a coding repo
- a queue source
- a contract source
- a milestone source
- a worker mirror

It is the visitor center, not the engine room.
{footer("chummer6-design", "latest public status")}
""",
    )

    write_text(
        GUIDE_REPO / "WHERE_TO_GO_DEEPER.md",
        f"""# Where To Go Deeper

This page is the map legend.

Chummer6 is here to explain the program clearly. It is **not** allowed to become a second source of truth.

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
{footer("chummer6-design scope rules", "latest public status")}
""",
    )

    write_text(
        GUIDE_REPO / "NOW" / "current-phase.md",
        f"""# Current Phase

The current phase is foundation work, not fireworks.

In plain language: the team is trying to make the split **true**, not just visible.

## The focus right now

- finish the contract reset
- finish the play/session boundary
- make the shared UI kit a real package seam
- finish the registry and media boundaries
- keep public previews honestly labeled until they become the real thing

## Why that matters

This is the work that makes later “wow” ideas cheap instead of chaotic.

Until the truth layer is clean, every future capability would be built on sand.
{footer("chummer6-design VISION", "chummer6-design README", "latest public status")}
""",
    )

    write_text(
        GUIDE_REPO / "NOW" / "current-status.md",
        f"""# Current Status

Chummer is already a live multi-repo program, but it is still much earlier in design completion than in actual finished shape.

## The short version

- the split is real
- the public surfaces are still preview, not the final public shape
- play is still the next major product seam to finish
- UI kit, registry, and media exist, but are still becoming fully real boundaries
- the design truth is still catching up in a few places

## What that means for normal humans

You can already see the shape of the future.
You just should not mistake preview surfaces or repo existence for “done.”
{footer("latest public status", "program_milestones.yaml")}
""",
    )

    write_text(
        GUIDE_REPO / "NOW" / "public-surfaces.md",
        f"""# Public Surfaces

Some things are visible. That does **not** mean they are promoted truth yet.

## Current public reality

These are still preview, not the final public shape:

- portal root
- hub preview
- workbench preview
- play preview
- coach preview

## Why that label exists

It means the surface is there, but the code, design, ownership, and deployment story do not line up cleanly enough yet to call it the real promoted split.
{footer("latest public surface status")}
""",
    )

    write_text(
        GUIDE_REPO / "PARTS" / "README.md",
        f"""# Program Map

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
- `design` keeps canonical cross-repo design truth

## How to read this folder

Each page answers the same human questions:

- what this part is for
- why it matters
- what it owns
- what it does not own
- what is happening with it right now

## Where to start

If you want the most important boundary right now, read [play](play.md).
If you want the cleanest big-picture truth, read [design](design.md).
If you want the current public shape in plain language, read [../NOW/current-status.md](../NOW/current-status.md).
{footer("chummer6-design ownership matrix", "latest public status", "owning repo READMEs")}
""",
    )

    parts = {
        "core": (
            "Core",
            "The deterministic rules engine.",
            "If Chummer is going to stay trustworthy, this is where that trust starts. Core owns the engine truth, the reducer logic, and the contract line that everything else should eventually consume instead of copying.",
            "Core is where the numbers have to stay honest. If this layer drifts, every shiny higher layer becomes harder to trust.",
            [
                "engine runtime and reducer truth",
                "explain canon and deterministic behavior",
                "engine-facing contracts",
            ],
            [
                "hosted orchestration",
                "play shell ownership",
                "render execution",
            ],
            "Core is still carrying some transitional weight. The job now is purification: shrink it until it unmistakably means engine truth and little else.",
        ),
        "presentation": (
            "Presentation",
            "The workbench and big-screen UX.",
            "Presentation is where the heavy browser/desktop authoring experience lives: inspectors, builders, workbench-side flows, and the surfaces for people who want to look deeply under the hood.",
            "This is the place for people who want to poke, inspect, and build. It is the workbench, not the at-the-table shell.",
            [
                "workbench/browser/desktop UX",
                "inspectors, builders, and shared presentation seams",
                "workbench-side launch and deep-link behavior",
            ],
            [
                "the shipped play shell",
                "provider logic",
                "render-only media work",
            ],
            "Presentation is already closer to the target story than some other repos. The next job is to keep it honest and delete ownership that really belongs to play or UI kit.",
        ),
        "play": (
            "Play",
            "The part you feel at the table.",
            "Play is the Chummer shell for players and GMs during actual sessions: mobile/PWA use, local-first state, runtime bundles, sync, and session-safe live features.",
            "If Chummer is going to become more than character prep, this is where that change becomes tangible.",
            [
                "player and GM play shell",
                "local-first session state",
                "runtime bundle consumption",
                "sync-friendly play flows",
            ],
            [
                "builder/workbench UX",
                "provider secrets",
                "copied shared contracts",
            ],
            "If Chummer is going to become more than character prep, this is one of the biggest jumps. The team is turning play from a split idea into a real boundary now.",
        ),
        "run-services": (
            "Run Services",
            "The hosted API and orchestration layer.",
            "Run services is the protected backend seam: identity, relay, approvals, memory, AI orchestration, and the play APIs that should eventually feel obvious and boring.",
            "This is where the system grows a backbone on the network side: not flashy, but vital.",
            [
                "identity, relay, approvals, and memory",
                "AI orchestration and hosted play APIs",
                "preview/apply style hosted workflows",
            ],
            [
                "engine truth",
                "long-term player shell ownership",
                "render-only media execution",
            ],
            "This repo has carried a lot of transitional mass. The job now is to shrink it into a clean hosted boundary and stop letting it impersonate everything else.",
        ),
        "ui-kit": (
            "UI Kit",
            "Shared visual primitives.",
            "UI kit is the design vocabulary: tokens, themes, shell chrome, badges, banners, and accessibility-friendly building blocks that other heads should consume instead of recreating.",
            "If the split is going to feel coherent instead of stitched together, this repo quietly does a lot of the heavy lifting.",
            [
                "tokens and themes",
                "shared chrome and accessibility primitives",
                "UI-only preview/gallery surfaces",
            ],
            [
                "domain DTOs",
                "HTTP clients",
                "rules math",
            ],
            "This repo only becomes real when other repos get smaller because it exists.",
        ),
        "hub-registry": (
            "Hub Registry",
            "Artifacts, publication, installs, compatibility.",
            "Hub registry is the narrow artifact brain of the system: what exists, what is published, what is compatible, and what install or runtime-bundle head metadata should be preserved.",
            "This is the part that keeps the growing artifact world from turning into an unlabeled warehouse.",
            [
                "artifact metadata",
                "publication and moderation workflow contracts",
                "install and compatibility projections",
            ],
            [
                "AI routing",
                "Spider logic",
                "media rendering",
            ],
            "This is one of the cleanest split candidates. The next job is not feature growth; it is consumer migration and deletion of old registry ownership elsewhere.",
        ),
        "media-factory": (
            "Media Factory",
            "Render-only asset lifecycle.",
            "Media factory is where render jobs, previews, signed URLs, and asset lifecycle management should eventually live without dragging narrative policy, rules math, or provider sprawl in with them.",
            "If the program starts making more media, this is the part that keeps it from spilling across the rest of the architecture.",
            [
                "render queues",
                "storage adapters and signed URLs",
                "dedupe/retry and rendered asset lifecycle",
            ],
            [
                "lore retrieval",
                "session relay",
                "provider routing and rules math",
            ],
            "It is still early. The right move is to keep it narrow and get the seam stable before trying to make it impressive.",
        ),
        "design": (
            "Design",
            "Canonical cross-repo design truth.",
            "Design is where the grown-up version of the plan lives: ownership, phases, milestone truth, contract canon, review guidance, and the split story that the rest of the program should eventually stop fighting.",
            "When the rest of the program argues about what is supposed to be true, this is where the answer is supposed to come from.",
            [
                "cross-repo architecture and ownership",
                "milestone and phase framing",
                "review guidance and mirror rules",
            ],
            [
                "implementation ownership",
                "dispatchable work queues",
                "runtime authority",
            ],
            "When Chummer6 sounds friendly, design is why it can still stay honest.",
        ),
    }

    for name, (title, tagline, intro, why_care, owns, not_owns, now_text) in parts.items():
        owns_lines = "\n".join(f"- {item}" for item in owns)
        not_lines = "\n".join(f"- {item}" for item in not_owns)
        write_text(
            GUIDE_REPO / "PARTS" / f"{name}.md",
            f"""# {title}

**{tagline}**

{intro}

## Why you should care

{why_care}

## What it owns

{owns_lines}

## What it does not own

{not_lines}

## What is happening now

{now_text}

## Go deeper

- [Program map](README.md)
- [Current phase](../NOW/current-phase.md)
- [Where to go deeper](../WHERE_TO_GO_DEEPER.md)
{footer("chummer6-design ownership matrix", "owning repo README", "latest public status")}
""",
        )

    write_text(
        GUIDE_REPO / "HORIZONS" / "README.md",
        f"""# Horizons

These are possible future directions for Chummer.

They are here because they are exciting, useful, or strategically important.  
They are **not** active build commitments.

Think of this folder as the garage: some of these projects may become real later, but none of them are the thing the team is racing today.

Start with whichever one makes you grin first.

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

## Important note

If you want canonical design or actual implementation truth, this folder is not that.  
For that, go to [Where to go deeper](../WHERE_TO_GO_DEEPER.md).
{footer("chummer6-design horizon guidance", "current public shape")}
""",
    )

    horizons = {
        "karma-forge": (
            "Personalized rules without forked-code chaos.",
            "People want controlled variation and house-rule power without turning every table into an incompatible code fork.",
            ["runtime stack truth", "overlay manifests", "explain/provenance receipts", "contract canon"],
            ["core", "mobile", "hub", "hub-registry", "design"],
            "The contract reset, play split, UI kit, and registry/media seams still need to become boringly real first.",
        ),
        "nexus-pan": (
            "A live synced table instead of isolated character files.",
            "Sessions want shared state, recoverable authority, and clean handoff between host, players, and devices.",
            ["session authority profile", "append-only session events", "local-first sync", "play API canon"],
            ["mobile", "hub", "core", "design"],
            "The program still needs the real play split and session event canon before this becomes more than a good idea.",
        ),
        "alice": (
            "Stress-test your build before the run.",
            "Players and GMs want reproducible simulation and explainable failure paths, not hand-wavy balance guesses.",
            ["deterministic engine truth", "scenario harnesses", "replayable seeds", "explain receipts"],
            ["core", "hub", "design"],
            "The engine and explain canon still need more cleanup before simulation becomes a product surface.",
        ),
        "jackpoint": (
            "Turn grounded data into dossiers and briefings.",
            "There is a huge difference between cool flavor and trustworthy narrative output. JACKPOINT only works if it stays grounded.",
            ["grounded evidence receipts", "approval states", "clean registry/media boundaries", "source classification"],
            ["hub", "hub-registry", "media-factory", "design"],
            "Narrative/export work must stay downstream of evidence and render-only seams, and those seams are still under construction.",
        ),
        "ghostwire": (
            "Replay a run like a forensic sim.",
            "Campaigns create a lot of state and a lot of questions. Ghostwire would make those replays inspectable instead of mystical.",
            ["runtime stack truth", "session authority", "event history", "evidence labeling"],
            ["mobile", "hub", "design"],
            "The platform still needs truth and seam cleanup before a theme-heavy layer like this is safe to build.",
        ),
        "mirrorshard": (
            "Compare alternate versions of a character or run.",
            "Change is easier to trust when you can compare before and after without losing provenance.",
            ["preview/apply/rollback receipts", "comparison-ready provenance", "migration previews"],
            ["ui", "hub", "design"],
            "Comparison tooling depends on stable contracts and explain receipts first.",
        ),
        "rule-x-ray": (
            "Click any number and see where it came from.",
            "Opaque math is the fastest way to lose trust in a rules tool.",
            ["explain canon", "provenance receipts", "deterministic engine evaluation"],
            ["core", "ui", "design"],
            "Explain/provenance alignment is still active foundational work right now.",
        ),
        "heat-web": (
            "Campaign consequences as a living graph.",
            "Sessions leave social fallout, faction consequences, and pressure trails that would be powerful to visualize.",
            ["grounded event streams", "durable evidence receipts", "publishable state artifacts"],
            ["hub", "mobile", "ui", "design"],
            "The current program still needs its base session and explain seams stabilized first.",
        ),
        "run-passport": (
            "Move a character across rule environments safely.",
            "A portable runtime/profile identity would make compatibility less magical and less painful.",
            ["runtime stack profile", "fingerprint and lineage", "compatibility projections"],
            ["hub-registry", "mobile", "hub", "design"],
            "The registry seam and runtime stack model are not stable enough yet.",
        ),
        "command-casket": (
            "Controlled operator actions with receipts and rollback.",
            "When something important changes, the system should be able to explain who asked for it, why it happened, and how to undo it.",
            ["approval-aware workflows", "preview/apply/rollback receipts", "auditable command capsules"],
            ["hub", "design"],
            "The platform still needs foundational workflow and provenance truth before that is safe to widen.",
        ),
        "tactical-pulse": (
            "Shared situational awareness during active sessions.",
            "A live table wants coordination, not just isolated sheets and guesswork.",
            ["session authority", "event envelopes", "local-first sync", "evidence-grounded summaries"],
            ["mobile", "hub", "ui"],
            "The play split is still foundational work, not embellishment time.",
        ),
        "blackbox-loadout": (
            "Portable rules-and-state bundles.",
            "Portable stack/loadout definitions would make setup, restore, and migration more reproducible.",
            ["runtime stack manifests", "fingerprints", "migration previews"],
            ["mobile", "hub-registry", "design"],
            "The underlying stack and contract model is still incomplete.",
        ),
        "persona-echo": (
            "Continuity without losing provenance.",
            "People want memorable characters and continuity, but not at the cost of blurred truth or made-up authority.",
            ["grounded evidence", "approval states", "clean hub/media ownership"],
            ["hub", "media-factory", "design"],
            "Provider and media boundaries are still too early to widen safely.",
        ),
        "shadow-market": (
            "A discovery layer for future packs and artifacts.",
            "Discovery, publication, and promotion would eventually need a place to live, but not before the underlying seams are real.",
            ["registry metadata", "moderation states", "compatibility projections", "promotion staging"],
            ["hub-registry", "hub", "design"],
            "Marketplace-like work is explicitly not the current program focus.",
        ),
        "evidence-room": (
            "A grounded review room for explain and provenance output.",
            "If Chummer is going to explain itself well, humans need a place to review the evidence without drowning in raw trace noise.",
            ["evidence receipts", "source classification", "approvals", "preview/apply separation"],
            ["hub", "ui", "design"],
            "The base evidence/provenance model still needs to finish becoming canonical.",
        ),
        "threadcutter": (
            "Conflict analysis for overlays and runtime changes.",
            "When multiple changes want to pull the system in different directions, someone needs to explain the collision before it turns into chaos.",
            ["conflict reports", "migration previews", "apply receipts", "rollback receipts"],
            ["hub", "mobile", "design"],
            "The program must first finish the runtime stack and session/event seams.",
        ),
    }
    for slug, values in horizons.items():
        write_text(GUIDE_REPO / "HORIZONS" / f"{slug}.md", horizon_page(slug.replace("-", " ").title(), *values))

    write_text(
        GUIDE_REPO / "UPDATES" / "2026-03.md",
        f"""# March 2026 Updates

## The quick read

March is a truth-layer month.

That means the interesting work is not “ship a thousand flashy features” but “make the split honest enough that future features stop being expensive lies.”

## What moved

- the split is now visible as a real multi-repo program
- Chummer6 exists as the human guide
- the guide is getting stricter about what is preview and what is really ready
- the play/session boundary is still the next major seam to finish

## What is still not finished

- contract canon
- full play split
- UI kit package realness
- registry and media seam maturity
- promotion of public preview surfaces
{footer("latest public status", "chummer6-design")}
""",
    )

    write_text(
        GUIDE_REPO / "GLOSSARY.md",
        f"""# Glossary

- **contract**: the package or API seam shared across repo boundaries
- **split**: moving real ownership from one repo to another and deleting the old ownership
- **runtime bundle**: packaged runtime/configuration consumed by play or hosted flows
- **lockstep**: a program mode where several parts move together as one wave
- **stale preview**: something visible in public that is still not the final promoted shape
- **workbench**: the browser/desktop authoring and inspection head
- **play shell**: the player/GM/mobile head
- **signoff only**: visible to the program, but not dispatchable for coding work
- **horizon**: a future concept intentionally kept out of the active work queue
- **visitor center**: the human guide layer that explains the program without becoming a second source of truth
{footer("chummer6-design", "public guide conventions")}
""",
    )

    write_text(
        GUIDE_REPO / "FAQ.md",
        f"""# FAQ

## Is Chummer6 a design repo?
No. `chummer6-design` is the canonical design repo.

## Is Chummer6 a code repo?
No. It is a human guide only.

## Is Chummer6 a work queue?
No. It explains the program. It does not decide the work.

## Why are there so many repos?
Because Chummer is already split into engine, hosted orchestration, play shell, shared UI, registry, media, design, and control-plane responsibilities.

## What is live right now?
The multi-repo program is live, but the public surfaces are still preview, not the final public shape.

## What is only preview?
Portal root, hub preview, workbench preview, play preview, and coach preview are still previews until promoted.

## Where do I propose design changes?
In `chummer6-design`.

## Why does Chummer6 exist if it is not truth?
To make the program understandable for humans without creating a second truth source.
{footer("chummer6-design", "latest public status")}
""",
    )

    remove_forbidden()


def write_design_scope() -> None:
    write_text(
        DESIGN_SCOPE,
        f"""# guide

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
- Fleet live state
- owning repo READMEs
- approved public-surface summaries

## Conflict rule
If `Chummer6` disagrees with canonical sources, fix `Chummer6`.

Truth order:
1. `chummer6-design`
2. Fleet state
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
""",
    )


def main() -> int:
    ensure_github_repo()
    ensure_local_repo()
    write_guide_repo()
    write_design_scope()
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
