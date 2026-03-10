#!/usr/bin/env python3
from __future__ import annotations

import textwrap
from pathlib import Path


DESIGN_FEEDBACK_ROOT = Path("/docker/chummercomplete/chummer-design/feedback")
GROUP_FEEDBACK_ROOT = Path("/docker/fleet/state/groups/chummer-vnext/feedback")
FILENAME = "2026-03-10-chummer-master-designer-handoff.md"


HANDOFF_TEXT = textwrap.dedent(
    """
    # Chummer Master Designer Handoff Report

    Prepared for: a new “master designer” chat that oversees the whole Chummer program
    Audience: human Chummer developers and architecture oversight

    ## 1. Executive summary

    The project has moved beyond “port the old app” and is now best understood as a multi-repo Shadowrun platform with three active product and engineering streams:

    1. `chummer-core-engine`
       The authoritative rules, import/export, parsing, runtime-lock, and Explain-engine layer.

    2. `chummer-presentation`
       The Avalonia, browser, and session-facing presentation layer that renders workflows, explain traces, browse surfaces, Build Lab, and GM/session UX.

    3. `chummer.run-services`
       The hosted service layer for identity, registry, session relay, runtime bundles, AI orchestration, lore retrieval, publication/review, and generated media.

    These three repos are intended to be coordinated by a shared contract surface and an architecture-first development process. The local development setup now includes a fleet of Codex agents plus watchdog, autosave, and feedback-queue orchestration. That is not the product itself, but it is now part of the engineering operating model.

    The project vision is no longer just “make Chummer work in a browser.” The target is:

    - a trusted rules/runtime engine
    - a strong workbench and session experience
    - a campaign operating system
    - a future GM Director / Spider assistant
    - a creative artifact pipeline for dossiers, portraits, recaps, route videos, and scene assets
    - a public platform surface under `chummer.run`

    ## 2. What exists now

    ### 2.1 Legacy + Docker-branch architecture

    The `Docker` branch of `ArchonMegalon/chummer5a` already describes a split between the legacy WinForms reference path and a current multi-head runtime. In that current runtime, the active architecture is:

    - `Chummer.Api` as the HTTP host
    - shared seam: `Chummer.Application`, `Chummer.Contracts`, `Chummer.Infrastructure`, `Chummer.Presentation`
    - active heads: `Chummer.Blazor`, `Chummer.Avalonia`, `Chummer.Blazor.Desktop`, `Chummer.Avalonia.Browser`
    - `Chummer.Portal` as the public gateway surface

    The README also makes it clear that `Chummer` and `Chummer.Web` are retained only as oracle/parity assets and are not part of the active product path. The Docker runtime is validated on Linux with .NET 10 containers and exposes portal, API, browser, downloads, and content-overlay seams.

    ### 2.2 Current public-facing direction

    The active public-facing shape in the repo is already portal-first:

    - API
    - browser/web head
    - Avalonia browser route
    - downloads/release manifest
    - content overlays / amend packs
    - API docs / OpenAPI
    - owner-scoped test/development bridges

    This means the repo is already moving toward a platform, not just a desktop rewrite.

    ### 2.3 Current development operating model

    Per the current local setup, development is now being parallelized into three repo-local Codex instances with:

    - repo-specific `instructions.md`
    - `.agent-memory.md`
    - compatibility shim `AGENT_MEMORY.md`
    - repo-local `feedback/`
    - repo-local `scripts/ai/*`
    - `.agent-state.json` heartbeat/status
    - `tmux` sessions for `core`, `ui`, `hub`
    - a watchdog for restart/nudge/autosave
    - autosave branches and ordered feedback injection

    That local orchestration layer is important because it changes how the architecture should be documented: the design has to be machine-readable enough for multiple autonomous coding agents, but also stable enough for human review.

    ## 3. The overall product vision

    The whole platform should be treated as four major layers.

    ### 3.1 Authoritative Chummer Core

    This is the trusted source of:
    - Shadowrun rules behavior
    - ruleset support (SR4 / SR5 / SR6)
    - XML/data ingestion and normalization
    - RulePack application
    - deterministic runtime locks
    - structured Explain traces
    - validation and derived-value truth

    This layer must remain deterministic, testable, and language-agnostic.

    ### 3.2 Workbench

    This is the full “builder/career manager” surface:
    - character creation
    - career editing
    - browse/search surfaces
    - Build Lab
    - Explain Everywhere
    - NPC Vault and Encounter Builder
    - ledger / timeline / calendar / relationship graph
    - exports / dossiers / printable assets

    ### 3.3 Session Operations

    This is the lighter play-at-the-table surface:
    - mobile/session app
    - quick trackers
    - GM board
    - Spider Feed
    - local-first/offline-friendly session state
    - session event relay
    - campaign recap and continuity support

    ### 3.4 Creative / Companion Layer

    This is the future “delight” layer:
    - portraits
    - fake corp documents
    - route/travel videos
    - scene packets
    - recap videos
    - contact/NPC messages
    - world/news feeds
    - GM Director / Spider AI

    The most important architectural rule is that this layer should produce drafts, cues, and artifacts, not hidden mutations of campaign canon.

    ## 4. The three repos: target responsibilities

    ## 4.1 `chummer-core-engine`

    ### Purpose
    The engine repo should be the single authoritative rules and state implementation.

    ### Owns
    - rulesets and domain logic
    - XML/data parsing and normalization
    - SR4/SR5/SR6 support
    - RulePack compilation/application on the engine side
    - runtime-lock inputs
    - Explain API source structures
    - deterministic calculations and validation
    - character/workspace immutable state transitions
    - import/export upgrade paths
    - engine-side tests

    ### Must not own
    - Avalonia / Blazor / browser rendering
    - HTTP controllers or portal concerns
    - hosted identity/auth
    - AI orchestration
    - GM Director logic
    - media generation
    - object-store / CDN concerns

    ### Design goal
    This repo should become the headless, deterministic, language-agnostic RPG engine.
    It must emit structured explanation payloads (keys/codes/parameters), not baked user prose.

    ### Planned feature foundations
    - structured Explain traces
    - RuntimeLock generation
    - deterministic RulePack resolution
    - localization-ready reason keys
    - engine-side primitives for Build Lab, ledger, timeline, and relationship/consequence state

    ## 4.2 `chummer-presentation`

    ### Purpose
    The presentation repo should become the human-facing UX layer for desktop, browser, and session play.

    ### Owns
    - Avalonia desktop UI
    - browser/WASM UI
    - session/mobile shell
    - design tokens and scaling
    - browse/search workspaces
    - Explain Everywhere rendering
    - Build Lab UX
    - Runtime Inspector UX
    - GM board / Spider Feed UX
    - generated asset viewers and approval surfaces

    ### Must not own
    - Shadowrun mechanics implementation
    - direct XML parsing
    - RulePack engine implementation
    - hosted auth / AI orchestration internals

    ### Design goal
    This repo should become the renderer and workflow orchestrator, never the rules engine.

    ### Planned feature foundations
    - virtualized browse surfaces
    - session shell and quick actions
    - Build Lab
    - NPC Vault / Encounter Builder UX
    - relationship and ledger UX
    - runtime/pack inspector
    - generated asset viewers (portrait, dossier, recap, route)

    ## 4.3 `chummer.run-services`

    ### Purpose
    This repo should become the hosted service layer behind `chummer.run`.

    ### Owns
    - API route groups
    - auth / identity / GM-player roles
    - RulePack / RuleProfile / BuildKit hosted registry
    - publication / moderation / review workflow
    - session relay / runtime bundle delivery
    - AI gateway and provider routing
    - lore retrieval / RAG
    - GM Director / Spider orchestration
    - generated asset job orchestration
    - object-store / TTL / CDN-style asset lifecycle
    - NPC persona registry and messaging orchestration

    ### Must not own
    - GPL-derived mechanics
    - Shadowrun math
    - legacy XML parsing
    - engine internals
    - UI rendering

    ### Design goal
    This repo should become the clean-room platform and companion service.

    ## 5. Shared cross-repo invariants

    The whole program depends on a few invariants.

    ### 5.1 RuntimeLock is sacred
    A character/session must be explainable in terms of:
    - ruleset
    - active packs/profiles
    - engine API
    - resolved providers
    - runtime fingerprint

    ### 5.2 Explain traces are structured
    Human-readable language is applied in presentation, not baked into engine truth.

    ### 5.3 Session state is event/delta based
    No “current value overwrite” model for live play. Session and offline sync should operate through append-only or mergeable delta/event semantics.

    ### 5.4 Generated content is not automatically canon
    AI/media outputs are:
    - ephemeral
    - reviewable
    - canonical only after approval

    ### 5.5 Hub/runtime artifacts must be durable
    Published and installed artifacts should be immutable or delisted, not hard-deleted.

    ## 6. What capabilities the Codex fleet gives us now

    The fleet changes what is realistic.

    ### 6.1 What the fleet can do
    - parallel repo work
    - persistent repo-local instructions
    - repo-local feedback queues
    - silent slice chaining
    - watchdog restarts
    - autosave branches
    - compile/restore/test loops
    - repo-local heartbeats

    ### 6.2 What the fleet is good at
    - repo isolation and compile recovery
    - repetitive refactors
    - solution restructuring
    - contract-driven rewiring
    - route scaffolding
    - UI shell work
    - moving legacy code toward boundaries

    ### 6.3 What still needs human oversight
    - repo boundary decisions
    - licensing boundaries
    - contract changes
    - final architecture decisions
    - risky destructive changes
    - priorities across repos
    - product/design tradeoffs

    The fleet is a force multiplier, not a substitute for architecture leadership.

    ## 7. Executive Assistant repo as a design reference for a GM companion AI

    The `tiborgirschele/executive-assistant` repo is highly relevant, not because it is a game engine, but because it already models many of the control-plane concepts a GM companion needs.

    ### 7.1 What the EA repo already demonstrates
    The README describes a durable executive-assistant runtime with:
    - principal-scoped API surfaces
    - queued execution
    - policy/approval gates
    - human-task routing
    - observations / recent-ingest flows
    - delivery outbox
    - tool registry and tool execution
    - connector bindings
    - task contracts
    - skills layered on top of task contracts
    - plan compile/execute
    - memory candidates and long-term memory items
    - entities, relationships, commitments
    - authority bindings
    - delivery preferences
    - follow-ups
    - deadline windows
    - stakeholders
    - decision windows
    - communication policies
    - follow-up rules
    - interruption budgets

    This is already close to the operating model needed for a GM Director / Spider.

    ### 7.2 How that maps to Chummer

    #### Observation ingest
    EA observation ingest maps naturally to:
    - session transcript chunks
    - GM quick notes
    - Spider Feed triggers
    - player/session events

    #### Delivery outbox
    EA delivery outbox maps to:
    - NPC messages
    - GM-only prompts
    - scene cards
    - generated reports
    - player-facing recap or contact notes

    #### Human task routing
    EA human-task routing maps to:
    - GM approval of canon changes
    - approval of generated dossiers/videos/messages
    - moderation/publication workflows in Hub

    #### Memory domains
    EA memory primitives map to:
    - contacts
    - NPC personas
    - faction relationships
    - campaign obligations
    - unresolved favors
    - scene history
    - interruption budget for Spider prompts

    #### Communication policy
    EA communication policy maps to:
    - what the Spider may send automatically
    - which NPCs may message players
    - channel restrictions
    - spoiler boundaries
    - GM override/autonomy settings

    ### 7.3 What should be borrowed directly
    The GM companion design should strongly borrow these patterns:
    - observation ingest
    - queued plan execution
    - approval gates
    - delivery outbox
    - memory entities / relationships / commitments
    - communication policy
    - interruption budgets

    ### 7.4 What should not be copied blindly
    The GM companion should not inherit enterprise/business assumptions that do not fit play:
    - overcomplicated approval hierarchies
    - enterprise principal models everywhere
    - too much ceremony for simple table actions

    The idea is to adapt the EA kernel into a campaign ops assistant, not to turn the game into office software.

    ## 8. Planned repo-by-repo roadmap

    ## 8.1 Core engine roadmap
    1. Isolation and compile recovery
    2. contract hardening
    3. localization-ready Explain API
    4. deterministic runtime / RulePack resolution
    5. SR4/SR5/SR6 engine parity foundations
    6. Build Lab / ledger / timeline / relationship primitives

    ## 8.2 Presentation roadmap
    1. Isolation and compile recovery
    2. contract-only engine integration
    3. Explain Everywhere
    4. browse/search workspaces
    5. Build Lab + Runtime Inspector
    6. session shell
    7. GM board / Spider Feed
    8. generated asset viewers

    ## 8.3 Run-services roadmap
    1. Clean-room scaffold and compile recovery
    2. contracts-first API hardening
    3. identity / roles
    4. RulePack / RuleProfile / BuildKit registry
    5. session relay and runtime bundle delivery
    6. AI gateway / provider router
    7. lore retrieval and persona memory
    8. generated asset orchestration
    9. publication / review / moderation workflows

    ## 9. High-value product features to keep centered

    These are the features most likely to establish Chummer strongly.

    ### Base Chummer / workbench
    - Explain Everywhere
    - Build Lab
    - Browse workspaces with virtualization
    - Runtime Inspector
    - NPC Vault + Encounter Builder
    - Ledger / timeline / relationship graph
    - dossier export

    ### Companion / chummer.run
    - Chummer Coach
    - GM Spider / Spider Feed
    - Session Memory Engine
    - Johnson’s Briefcase
    - Portrait Forge
    - Route Cinema
    - Shadowfeed / in-world news
    - NPC Persona Studio

    ## 10. Strategic conclusion

    What exists now is no longer “just a repo in migration.”

    It is now:
    - a split platform architecture,
    - a multi-agent development factory,
    - a clear separation between trusted mechanics and hosted companion services,
    - and a credible path toward a full Shadowrun campaign operating system.

    The most important design leadership task for the next master-designer instance is:

    1. keep the three repos sharply bounded,
    2. keep the contracts stable,
    3. keep the runtime truth deterministic,
    4. keep generated content reviewable and non-magical,
    5. and keep the GM companion grounded in useful table operations rather than generic chatbot behavior.

    ## 11. Immediate guidance for the new “master designer” chat

    The next designer instance should act as:

    - architecture overseer of all three repos
    - contract/change-control owner
    - feature-priority governor
    - design consistency reviewer
    - campaign-OS vision keeper

    It should not primarily write implementation code.
    It should:
    - reconcile repo boundaries
    - update design docs
    - review drift
    - define shared contracts and invariants
    - break new feature families into repo-specific deliverables
    - use the Executive Assistant repo as the main design reference for the GM companion’s control plane

    ## 12. Suggested first questions for the new master-designer instance

    1. What is the minimum stable contract set between the three repos?
    2. What are the top 5 cross-repo invariants that may not be violated?
    3. Which Wave 1 features are required to establish trust and adoption?
    4. What should the GM companion do in v1, and what must remain manual?
    5. How should Build Lab, Explain Everywhere, and Runtime Inspector interact?
    6. What pieces of the Executive Assistant runtime should be adapted directly into the Spider layer?
    """
).strip() + "\n"


def publish(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    target = root / FILENAME
    target.write_text(HANDOFF_TEXT, encoding="utf-8")
    return target


def main() -> None:
    paths = [
        publish(DESIGN_FEEDBACK_ROOT),
        publish(GROUP_FEEDBACK_ROOT),
    ]
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
