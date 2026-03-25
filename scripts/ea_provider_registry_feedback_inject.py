#!/usr/bin/env python3
from __future__ import annotations

import textwrap
from pathlib import Path


EA_ROOT = Path("/docker/EA")
GROUP_FEEDBACK_ROOT = Path("/docker/fleet/state/groups/control-plane/feedback")
FILENAME = "2026-03-11-ea-provider-registry-and-unmixr.md"


CONTENT = textwrap.dedent(
    """
    # EA provider registry and Unmixr feedback

    Date: 2026-03-11
    Audience: `executive-assistant` and `control-plane`
    Status: injected fleet feedback

    The runtime kernel is still the strongest part of EA, and the product surface is now materially ahead of the remaining code boundaries. The missing bounded context is a typed provider registry plus typed catalog metadata.

    ## Main findings

    * the product surface is materially stronger: LTD inventory, first-class skills, skill-aware plan compile/execute, BrowserAct-backed LTD refresh, workflow templates, and a broad contract-heavy test surface are all real improvements.
    * `create_app()` now exposes a real product interface across channels, connectors, delivery, evidence, human, memory, observations, plans, policy, rewrite, skills, task contracts, and tools.
    * execution maturity is real now: dependency-aware plans, queue retries, human-review steps, evidence packs, and generic plan execution all run through the same queued runtime.
    * LTD truth still lives in multiple places at once: `LTDs.md`, `SKILLS.md`, env scaffolding, provider hints, and JSON policy bags.
    * the existing `skill_key -> task_key -> planner -> tools -> artifact -> dispatch/memory` runtime is already strong enough; a second integration framework is not needed.
    * auth still fails open too easily in dev-like configurations when `EA_API_TOKEN` is blank and caller-supplied principals are still accepted.
    * bootstrap/runtime profile can still drift into mixed durability modes because subsystem fallback is resolved independently instead of from one runtime profile.
    * task/skill metadata is still effectively sourced from free-form `budget_policy_json`.
    * the provider layer is still mostly conceptual; provider hints exist, but runtime execution is still built around hardcoded built-ins and BrowserAct-specific pre-artifact logic.
    * docs and deployment surfaces still lag the runtime: `ARCHITECTURE_MAP.md`, env examples, compose overlays, and the duplicate root-running Dockerfiles are behind the actual router/provider surface.
    * `orchestrator.py` remains too large, and the skill catalog still piggybacks on task-contract storage and read-time synthesis instead of a real projection.

    ## Recommended bounded context

    Add typed provider models:

    * `ProviderProfile`
    * `ProviderBinding`
    * `ProviderCapabilityProbe`
    * `SkillProviderBinding`

    Then move providers through:

    * `tracked`
    * `auth_configured`
    * `discovered`
    * `capability_verified`
    * `skill_bound`
    * `operational`

    `LTDs.md` should become a rendered report, not the source of truth. The real schema should stop leaking through `budget_policy_json`.

    ## Runtime direction

    Keep the existing execution path:

    * `skill_key -> task_key -> planner -> tools -> artifact -> dispatch/memory`

    Route by capability, not vendor name.

    Add typed metadata alongside the provider registry:

    * `WorkflowConfig`
    * `RetryPolicy`
    * `HumanReviewPolicy`
    * `MemoryCandidatePolicy`
    * `ArtifactOutputPolicy`
    * `SkillCatalogMeta`

    The missing operational layer is no longer just "execution cleanup". It is provider registry plus typed catalog metadata.

    ## First operational providers

    * BrowserAct
    * 1min.AI
    * Unmixr
    * ApiX-Drive
    * ApproveThis

    Evidence/content providers:

    * Paperguide
    * Documentation.AI

    Projection/storage surfaces:

    * Teable
    * Internxt

    ## Unmixr-first guidance

    Unmixr is the cleanest next provider because its API is concrete today.

    First provider tools:

    * `unmixr.voice_list`
    * `unmixr.voice_detail`
    * `unmixr.tts_generate`
    * `unmixr.clone_voice`
    * `unmixr.cloned_voice_list`
    * `unmixr.credit_balance`

    `unmixr.tts_generate` should:

    * chunk below the documented request limits
    * persist audio into the existing artifact repository
    * emit receipts with voice, locale, usage, and request metadata
    * support optional secondary secret refs when an extra upstream key is required

    ## Small cleanup

    * add Unmixr env placeholders to local env examples
    * replace stale `EA_LEDGER_BACKEND=memory` overlays with `EA_STORAGE_BACKEND=memory`
    * keep Teable out of the hot-path runtime DB role
    * update `ARCHITECTURE_MAP.md` to reflect the current router/runtime surface
    * collapse the duplicate Dockerfiles or generate one from the other
    * add a non-root user and a real API healthcheck

    ## Recommended implementation order

    1. add `validate_settings_or_raise()` in `create_app()` and fail fast in prod unless `EA_API_TOKEN`, `EA_STORAGE_BACKEND=postgres`, and `DATABASE_URL` are coherent; when auth is disabled locally, force the default principal and ignore caller-supplied `x-ea-principal-id`
    2. resolve one `RuntimeProfile` at startup and report that exact profile in readiness instead of letting services fall back independently; in prod, partial fallback should fail fast
    3. parse task/skill metadata into typed models so planner and skill code stop reading raw `budget_policy_json`
    4. build a real provider registry and provider/plugin interface; move BrowserAct behind it first and land Unmixr as the first API-native provider
    5. split orchestration execution from orchestration read models and stop synthesizing skills entirely on read
    6. bring `ARCHITECTURE_MAP.md`, compose, env examples, and Dockerfiles back into sync with the runtime surface

    ## Bottom line

    The runtime kernel is good enough to keep. The highest-leverage next commit is startup validation plus a single resolved `RuntimeProfile`; after that, the provider layer can be expanded without carrying operational ambiguity forward. What is still missing overall is a canonical provider layer that turns LTDs/providers from markdown notes and provider hints into executable, capability-addressable provider bindings.
    """
).strip() + "\n"


def write(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / FILENAME).write_text(CONTENT, encoding="utf-8")


def main() -> None:
    write(EA_ROOT / "feedback")
    write(GROUP_FEEDBACK_ROOT)
    print("Injected EA provider registry and Unmixr feedback into repo and group lanes.")


if __name__ == "__main__":
    main()
