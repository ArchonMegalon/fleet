#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


OWNER = "ArchonMegalon"
REPO_NAME = "Chummer6"
REPO_SLUG = f"{OWNER}/{REPO_NAME}"
REPO_URL = f"https://github.com/{REPO_SLUG}.git"
GUIDE_REPO = Path("/docker/chummercomplete/Chummer6")
DESIGN_SCOPE = Path("/docker/chummercomplete/chummer-design/products/chummer/projects/guide.md")
TODAY = "2026-03-11"

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


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def ensure_github_repo() -> None:
    view = run("gh", "repo", "view", REPO_SLUG, check=False)
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
    run(
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
    )


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def derived_footer(*sources: str) -> str:
    joined = ", ".join(sources)
    return f"\nLast synced: {TODAY}\nDerived from: {joined}\nCanonical source: chummer6-design\n"


def horizon_page(title: str, idea: str, problem: str, foundations: str, repos: str, not_now: str) -> str:
    return f"""# {title}

> **Horizon only**
> This page explains a possible future direction.
> It is not canonical design.
> It is not an active queue.
> It is not dispatchable.
> It does not authorize implementation by itself.

## What is the idea?
{idea}

## What problem does it solve?
{problem}

## Why would it be wow?
It would make Chummer feel dramatically more coherent, inspectable, and personal without breaking deterministic runtime truth.

## What foundations does it need first?
{foundations}

## Which repos would be affected later?
{repos}

## Why is it not now?
{not_now}

## Current status
Horizon only.
{derived_footer("chummer6-design horizon guidance", "Fleet group state")}
"""


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
    for rel in FORBIDDEN:
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


def write_guide_repo() -> None:
    write_text(
        GUIDE_REPO / "README.md",
        f"""# Chummer6

Chummer6 is the human guide to the next Chummer.

It explains the vision in plain language, shows how the parts fit together, tracks what is happening now, and collects the longer-range horizon ideas in one place.

Chummer6 is not the canonical design source, not a coding repo, and not a work queue.

Canonical design lives in `chummer6-design`.
Operational truth lives in Fleet.
Implementation lives in the owning code repos.
{derived_footer("chummer6-design", "Fleet group state", "owning repo READMEs")}
""",
    )

    write_text(
        GUIDE_REPO / "START_HERE.md",
        f"""# Start Here

Chummer6 exists because the program already spans multiple repos and multiple public previews, while the real design and execution truth live elsewhere.

## Why are there multiple repos?
- `core` owns deterministic engine truth.
- `ui` owns workbench/browser/desktop presentation.
- `hub` owns hosted orchestration and play APIs.
- `mobile` owns the play shell and local-first session experience.
- `ui-kit`, `hub-registry`, and `media-factory` are the narrow split boundaries still becoming real.
- `design` is the canonical cross-repo design front door.
- Fleet is the operational control plane.

## Why does Chummer6 exist?
To explain all of that in plain language without becoming a second design source.

## What should you trust first?
1. `chummer6-design`
2. Fleet live state
3. The owning code repo
4. Chummer6 only as the human summary
{derived_footer("chummer6-design README", "Fleet README", "groups.yaml")}
""",
    )

    write_text(
        GUIDE_REPO / "WHAT_CHUMMER6_IS.md",
        f"""# What Chummer6 Is

Chummer6 is the public visitor center for the next Chummer.

It explains the current split, the current phase, the purpose of each repo, what is genuinely live, and which horizon concepts exist for later.

It is downstream-only:
- no code
- no contracts
- no queues
- no milestones
- no worker mirrors
- no design authority
{derived_footer("chummer6-design", "Fleet status")}
""",
    )

    write_text(
        GUIDE_REPO / "WHERE_THE_REAL_TRUTH_LIVES.md",
        f"""# Where The Real Truth Lives

If two things disagree, fix Chummer6. Do not treat Chummer6 as the source of truth.

## Truth order
1. `chummer6-design`
2. Fleet live state
3. The owning code repo
4. `Chummer6`

## What each source owns
- `chummer6-design`: canonical architecture, ownership, phases, milestone truth, horizon framing
- Fleet: operational truth, current group status, public-surface debt, dispatchable state
- Owning repos: actual implementation and repo-local scope
- Chummer6: human-readable summaries only
{derived_footer("chummer6-design project guide scope", "Fleet status payloads")}
""",
    )

    write_text(
        GUIDE_REPO / "NOW/current-phase.md",
        f"""# Current Phase

The current phase is truth-layer work, not feature sprawl.

The active program focus is:
- contract canon
- repo purification
- the next clean split wave

In practical terms that means:
- stabilize `Chummer.Engine.Contracts` and `Chummer.Play.Contracts`
- finish the real `chummer6-mobile` play boundary
- make `chummer6-ui-kit` package-real
- finish narrow registry and media seams
- keep public previews labeled as preview debt until promoted
{derived_footer("chummer6-design VISION", "chummer6-design README", "Fleet groups.yaml")}
""",
    )

    write_text(
        GUIDE_REPO / "NOW/current-status.md",
        f"""# Current Status

Chummer is already a live multi-repo program under Fleet, but it is not design-complete.

Current truth in plain language:
- the split is real
- the public surfaces are still preview debt
- the play split is still not fully complete
- the UI kit, registry, and media splits exist but are still becoming real boundaries
- design completion is much farther away than runtime queue completion
{derived_footer("Fleet group status", "program_milestones.yaml")}
""",
    )

    write_text(
        GUIDE_REPO / "NOW/public-surfaces.md",
        f"""# Public Surfaces

The public URLs are still previews, not proof that the split is complete.

Current preview debt:
- portal root
- hub preview
- workbench preview
- play preview
- coach preview

Fleet currently treats these as `stale_preview`, which means they are visible but not yet aligned with the promoted split truth.
{derived_footer("Fleet groups.yaml public surface status")}
""",
    )

    parts = {
        "core": ("Deterministic engine/runtime truth.", "Engine runtime, reducer truth, explain canon, engine contracts.", "Hosted orchestration, play shell, media execution."),
        "presentation": ("Workbench/browser/desktop UX.", "Workbench heads, inspectors, builders, browser/desktop UX.", "Play shell ownership, provider logic, render execution."),
        "run-services": ("Hosted orchestration boundary.", "Identity, relay, approvals, memory, AI orchestration, play APIs.", "Engine truth, player shell ownership, render-only media execution."),
        "play": ("Player and GM shell.", "Play shell, offline ledger, runtime bundle consumption, local-first sync.", "Builder UX, provider secrets, copied shared contracts."),
        "ui-kit": ("Shared UI primitives.", "Tokens, themes, shell chrome, accessibility primitives.", "DTOs, HTTP clients, rules math."),
        "hub-registry": ("Artifact and publication boundary.", "Artifact metadata, publication, moderation, installs, compatibility projections.", "AI routing, Spider, media rendering."),
        "media-factory": ("Render-only media lifecycle.", "Render queues, storage adapters, signed URLs, dedupe/retry, rendered-asset lifecycle.", "Lore retrieval, session relay, provider routing, rules math."),
        "design": ("Canonical design front door.", "Cross-repo design truth, ownership, milestone framing, review guidance.", "Implementation ownership, dispatch queues, code authority."),
        "fleet": ("Operational control plane.", "Live status, compile stages, review gates, worker routing, operator truth.", "Canonical design authorship or code ownership."),
    }
    for name, (purpose, owns, not_owns) in parts.items():
        write_text(
            GUIDE_REPO / "PARTS" / f"{name}.md",
            f"""# {name}

## Summary
{purpose}

## What it owns
{owns}

## What it does not own
{not_owns}

## Why it matters now
This part exists to make the Chummer split real by shrinking old ownership and moving toward package-real or API-real boundaries.
{derived_footer("chummer6-design ownership matrix", "owning repo README", "Fleet state")}
""",
        )

    horizons = {
        "karma-forge": (
            "A future overlay and runtime-stack capability for controlled rule and experience variation.",
            "It would solve the need for deterministic variation without forked codebases.",
            "Runtime stack truth, overlay manifests, explain/provenance receipts, and contract canon.",
            "Likely touches `mobile`, `hub`, `hub-registry`, `core`, and `design`.",
            "The contract reset, play split, UI kit, and registry/media seams are still not clean enough yet.",
        ),
        "nexus-pan": (
            "A future session authority and synchronized tactical play layer.",
            "It would solve shared live-state coordination across hosts, players, and devices.",
            "Session authority profile, append-only session events, local-first sync, and play API canon.",
            "Likely touches `mobile`, `hub`, `core`, and `design`.",
            "The program still needs the real play split and session event canon first.",
        ),
        "alice": (
            "A future deterministic simulation and scenario lab.",
            "It would solve explainable experiment and balance testing over a stable runtime stack.",
            "Deterministic engine truth, replayable scenarios, and explain/provenance receipts.",
            "Likely touches `core`, `hub`, `design`, and maybe `fleet` for reporting.",
            "The engine and explain canon still need to be stabilized before simulation becomes a product surface.",
        ),
        "jackpoint": (
            "A future grounded intelligence and narrative export layer.",
            "It would solve evidence-grounded briefings, dossiers, and digest-style outputs.",
            "Grounded artifact receipts, provenance labels, approval states, and clean media boundaries.",
            "Likely touches `hub`, `hub-registry`, `media-factory`, and `design`.",
            "Narrative/export work must stay downstream of grounded evidence and render-only media seams.",
        ),
        "ghostwire": (
            "A future clandestine operations and shadow-routing concept.",
            "It would solve stealthy coordination and mission-layer framing.",
            "Runtime stack truth, session authority, evidence labeling, and explain-safe routing.",
            "Likely touches `mobile`, `hub`, `design`.",
            "The platform still needs truth and seam cleanup before a thematic layer like this is safe.",
        ),
        "mirrorshard": (
            "A future reflection and divergence analysis surface.",
            "It would solve comparison between runtime stacks, variants, and migration paths.",
            "Preview/apply/rollback receipts and comparison-ready provenance.",
            "Likely touches `ui`, `hub`, `design`.",
            "Comparison tooling depends on stable contracts and explain receipts first.",
        ),
        "rule-x-ray": (
            "A future deep explain and rule-inspection surface.",
            "It would solve visibility into why the runtime reached a given outcome.",
            "Explain canon, provenance receipts, and engine determinism.",
            "Likely touches `core`, `ui`, `design`.",
            "Explain/provenance alignment is still active foundational work.",
        ),
        "heat-web": (
            "A future continuity and consequence graph for factions, heat, and fallout.",
            "It would solve long-running state visibility across sessions and actors.",
            "Grounded event streams, evidence receipts, and durable registry/publishable artifacts.",
            "Likely touches `hub`, `mobile`, `ui`, `design`.",
            "The current program still needs its base session and explain seams stabilized first.",
        ),
        "run-passport": (
            "A future signed profile of a runtime stack or campaign-safe configuration.",
            "It would solve reproducible installs and compatibility communication.",
            "Runtime stack profile, fingerprint, lineage, and compatibility projections.",
            "Likely touches `hub-registry`, `mobile`, `hub`, `design`.",
            "The registry and stack model are not stable enough yet.",
        ),
        "command-casket": (
            "A future controlled command and approval capsule.",
            "It would solve explainable operator actions with receipts and rollback paths.",
            "Approval-aware workflow states and preview/apply/rollback receipts.",
            "Likely touches `hub`, `fleet`, `design`.",
            "The program still needs foundational workflow and provenance truth before that is safe.",
        ),
        "tactical-pulse": (
            "A future live tactical awareness layer.",
            "It would solve synchronized situational understanding across active sessions.",
            "Session authority, event envelopes, local-first sync, and evidence-grounded summaries.",
            "Likely touches `mobile`, `hub`, `ui`.",
            "The current play split is still foundational work, not product embellishment time.",
        ),
        "blackbox-loadout": (
            "A future portable rules-and-state bundle concept.",
            "It would solve portable session-safe configuration and restore flows.",
            "Runtime stack manifests, fingerprints, and migration previews.",
            "Likely touches `mobile`, `hub-registry`, `design`.",
            "The underlying stack and contract model is not complete enough yet.",
        ),
        "persona-echo": (
            "A future persona continuity and reflection layer.",
            "It would solve durable explainable narrative/persona memory without losing provenance.",
            "Grounded evidence, approval states, and clean ownership across hub and media seams.",
            "Likely touches `hub`, `media-factory`, `design`.",
            "Provider/media boundaries are still too early to widen safely.",
        ),
        "shadow-market": (
            "A future registry or marketplace-like discovery layer.",
            "It would solve controlled publication and discovery of future overlay or pack artifacts.",
            "Registry metadata, moderation states, compatibility projections, and promotion staging.",
            "Likely touches `hub-registry`, `hub`, `design`.",
            "Marketplace-like work is explicitly not current program focus.",
        ),
        "evidence-room": (
            "A future grounded evidence review space.",
            "It would solve human-readable review and arbitration over explain/provenance outputs.",
            "Evidence receipts, source classification, approvals, and preview/apply separation.",
            "Likely touches `hub`, `ui`, `design`, maybe `fleet` reporting.",
            "The base evidence/provenance model still needs to finish becoming canonical.",
        ),
        "threadcutter": (
            "A future conflict-resolution and rollback capability.",
            "It would solve safe divergence, migration, and conflict handling.",
            "Conflict reports, migration previews, apply receipts, and rollback receipts.",
            "Likely touches `hub`, `mobile`, `design`.",
            "The program must first finish the runtime stack and session/event seams.",
        ),
    }
    write_text(
        GUIDE_REPO / "HORIZONS" / "README.md",
        f"""# Horizons

This folder collects possible future directions for Chummer.

These pages are for understanding and inspiration only.

They are not:
- canonical design
- active queue items
- dispatchable product truth
- permission to start implementation by themselves
{derived_footer("chummer6-design horizon guidance", "Fleet group policy")}
""",
    )
    for slug, values in horizons.items():
        write_text(GUIDE_REPO / "HORIZONS" / f"{slug}.md", horizon_page(slug.replace("-", " ").title(), *values))

    write_text(
        GUIDE_REPO / "UPDATES" / "2026-03.md",
        f"""# March 2026 Updates

## Summary
Chummer is in a truth-first phase: contract canon, play split completion, UI kit, registry, media seams, and design-governance cleanup.

## Notable state
- public surfaces still count as preview debt
- the split is real, but not design-complete
- Fleet tracks operational truth, while Chummer6 explains it downstream
{derived_footer("Fleet status", "chummer6-design")}
""",
    )

    write_text(
        GUIDE_REPO / "GLOSSARY.md",
        f"""# Glossary

- **contract**: the package or API seam shared across repo boundaries
- **split**: moving real ownership from one repo to another and deleting the old ownership
- **runtime bundle**: the packaged runtime state or configuration used by play/runtime flows
- **lockstep**: Fleet group mode where member progression is coordinated as one program wave
- **stale preview**: a public surface that exists but does not yet represent promoted architecture truth
- **workbench**: the browser/desktop authoring and inspection head
- **play shell**: the player/GM/mobile head
- **signoff only**: visible to the program, but not dispatchable for coding work
- **horizon**: a future concept intentionally kept out of the active work queue
{derived_footer("chummer6-design", "Fleet README")}
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
No. Fleet owns operational truth and dispatchable work.

## Why are there so many repos?
Because Chummer is already split into engine, hosted orchestration, play shell, shared UI, registry, media, design, and fleet control-plane responsibilities.

## What is live right now?
The multi-repo program is live under Fleet, but the public surfaces are still preview debt.

## What is only preview?
Portal root, hub preview, workbench preview, play preview, and coach preview are still treated as preview debt until promoted.

## Where do I propose design changes?
In `chummer6-design`.

## Why does Chummer6 exist if it is not truth?
To make the program understandable for humans without creating a second truth source.
{derived_footer("chummer6-design", "Fleet group status")}
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
