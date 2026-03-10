#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
import sys
import textwrap
from collections import Counter
from pathlib import Path

import yaml


DESIGN_ROOT = Path("/docker/chummercomplete/chummer-design")
PRODUCT_ROOT = DESIGN_ROOT / "products" / "chummer"
GROUP_FEEDBACK_ROOT = Path("/docker/fleet/state/groups/chummer-vnext/feedback")
NEW_POLICY_FILE = "EXTERNAL_TOOLS_PLANE.md"
OLD_POLICY_FILE = "EXTERNAL_INTEGRATIONS_AND_LTD_POLICY.md"

REPO_ROOTS = {
    "chummer-core-engine": Path("/docker/chummercomplete/chummer-core-engine"),
    "chummer-presentation": Path("/docker/chummercomplete/chummer-presentation"),
    "chummer.run-services": Path("/docker/chummercomplete/chummer.run-services"),
    "chummer-play": Path("/docker/chummercomplete/chummer-play"),
    "chummer-ui-kit": Path("/docker/chummercomplete/chummer-ui-kit"),
    "chummer-hub-registry": Path("/docker/chummercomplete/chummer-hub-registry"),
    "chummer-media-factory": Path("/docker/fleet/repos/chummer-media-factory"),
}


EXTERNAL_TOOLS_PLANE = textwrap.dedent(
    """
    # External tools plane

    ## Purpose

    Project Chummer has a meaningful owned external-tool inventory.
    Those tools are now considered part of the program's integration capability set.

    This document defines how Chummer may use those tools for:

    * Hub orchestration
    * help/docs
    * approval routing
    * ops dashboards
    * user feedback loops
    * research/evaluation
    * media creation
    * route visualization
    * archive and retention support

    without allowing any external tool to become canonical product truth.

    ## Core rule

    External tools may assist, route, render, summarize, visualize, archive, notify, or project. They may not become the canonical source of rules truth, session truth, approval truth, registry truth, media truth, or canon truth.

    Chummer-owned repos and Chummer-owned manifests/stores remain authoritative.

    ## Tool inventory posture

    Current known external-tool inventory includes:

    * 1min.AI
    * Prompting Systems
    * ChatPlayground AI
    * AI Magicx
    * FastestVPN PRO
    * OneAir
    * Headway
    * Internxt Cloud Storage
    * ApiX-Drive
    * ApproveThis
    * AvoMap
    * BrowserAct
    * Documentation.AI
    * Invoiless
    * MarkupGo
    * MetaSurvey
    * Mootion
    * Paperguide
    * PeekShot
    * Teable
    * Vizologi

    Current internal posture assumes every listed LTD is redeemed and activated.
    Public inventory snapshots may lag that internal state, so activation verification still gates runtime approval.

    ## Workspace integration tiers versus vendor plan tiers

    Product plan tier and Chummer workspace integration tier are not the same thing.

    Important current distinctions:

    * 1min.AI - workspace integration Tier 1
    * BrowserAct - workspace integration Tier 1
    * Teable - workspace integration Tier 2, vendor license plan Tier 4
    * Paperguide - workspace integration Tier 3, vendor license plan Tier 4

    Chummer routing, rollout, and architectural ownership should follow workspace integration tier and system-of-record safety rules, not marketing or license-plan tier labels.

    ## Classification model

    ### Class A - Runtime-adjacent orchestration integrations

    These may participate in hosted workflows, but only through controlled adapters and receipts.

    Examples:

    * reasoning provider routes
    * approval bridges
    * docs/help bridges
    * automation bridges
    * survey bridges
    * route visualization orchestration
    * media orchestration

    ### Class B - Runtime-adjacent media integrations

    These may render or transform artifacts, but only behind media-factory adapters.

    Examples:

    * document render providers
    * preview/thumbnail providers
    * image/portrait providers
    * bounded video providers
    * map/route visualization providers
    * archive providers

    ### Class C - Human-ops / projection integrations

    These support operators and curators off the hot path.

    Examples:

    * projection boards
    * moderation boards
    * support/help desks
    * review inboxes
    * release dashboards

    ### Class D - Research / eval / prompt-tooling integrations

    These inform product quality, content quality, or design quality, but they do not directly own end-user truth.

    Examples:

    * evaluation labs
    * prompt research
    * cited synthesis
    * product strategy ideation

    ### Class E - Non-product utilities

    Useful to the team, but outside the product architecture.

    ## System-of-record rule

    The following remain Chummer-owned:

    * rules math
    * runtime fingerprints
    * explain provenance
    * reducer truth
    * session event truth
    * approval state
    * moderation state
    * publication state
    * install state
    * artifact manifests
    * media lifecycle state
    * delivery state
    * memory/canon state

    External tools may receive a prepared request and may return a receipt-bearing result.
    They do not become the owner of any of the truths above.

    ## Universal integration rules

    ### Rule 1 - adapter-only access

    Every external tool sits behind a Chummer-owned adapter.

    ### Rule 2 - prepared payloads only

    External tools receive prepared requests, not raw unrestricted database access.

    ### Rule 3 - receipt and provenance required

    Anything that re-enters Chummer from an external tool must carry:

    * provider identity
    * route or adapter class
    * request or plan hash
    * created-at timestamp
    * source refs where applicable
    * moderation/safety result where applicable
    * Chummer-side correlation id

    ### Rule 4 - kill switch required

    Every integration must be disableable without corrupting product truth.

    ### Rule 5 - no client-side vendor coupling

    No browser, mobile, or desktop repo may embed vendor credentials or call vendor SDKs directly.

    ### Rule 6 - archive is not canon

    Vendor-hosted copies or vendor-side asset persistence are never the canonical archive.
    Canonical manifests remain Chummer-owned.

    ### Rule 7 - activation is not trust

    A redeemed or activated tool is merely eligible for integration.
    It is not automatically approved for canonical runtime use.

    ## Repo ownership

    ### `chummer-design`

    Owns:

    * classification policy
    * allowed-usage policy
    * external-tools governance
    * rollout sequencing
    * blocker publication
    * provenance requirements
    * kill-switch requirements

    Must not own:

    * provider SDK code
    * runtime keys
    * implementation adapters

    ### `chummer.run-services`

    Owns:

    * orchestration-side integrations
    * reasoning provider routing
    * approval bridges
    * docs/help bridges
    * survey bridges
    * automation bridges
    * research/eval toolchain integrations
    * user-facing projection shaping for external-tool outputs

    Must not own:

    * media rendering internals
    * client-side provider access
    * duplicate engine semantics
    * canonical registry persistence
    * canonical media lifecycle

    ### `chummer-media-factory`

    Owns:

    * render/provider adapters
    * preview/thumbnail adapters
    * route-render adapters
    * image and video adapters
    * archive adapters
    * media provider receipts
    * media provenance capture
    * media retention/archive execution

    Must not own:

    * campaign meaning
    * approvals policy
    * canon policy
    * registry truth
    * client UX
    * general AI orchestration

    ### `chummer-hub-registry`

    May own:

    * references to reusable template/style/help artifacts
    * references to published previews
    * compatibility metadata for reusable template/style packs

    Must not own:

    * provider execution
    * media job orchestration
    * reasoning provider routing

    ### `chummer-presentation` and `chummer-play`

    May render upstream projections that refer to external outputs.

    Must not own:

    * vendor keys
    * vendor SDKs
    * direct third-party orchestration

    ## Integration map by tool

    ## 1min.AI

    ### Role

    Low-cost reasoning and multimodal provider route.

    ### Architectural use

    * fallback reasoning provider in Hub/Coach routes
    * multimodal summarization where policy allows
    * optional low-cost assist route for structured drafting
    * optional media prompt-assist upstream of media-factory

    ### Owner

    * `chummer.run-services`
    * optional media-prompt-assist only via `chummer.run-services`

    ### Hard boundary

    * not canonical truth
    * not direct-to-client
    * not direct canon writer

    ## AI Magicx

    ### Role

    Primary or alternate structured AI provider route.

    ### Architectural use

    * governed Coach / Director / helper routes
    * structured drafting
    * composition assistance for media briefs
    * operator-facing assistant routes

    ### Owner

    * `chummer.run-services`

    ### Hard boundary

    * no direct player/client access
    * no storage truth
    * no approval truth

    ## Prompting Systems

    ### Role

    Prompt/style/persona authoring support.

    ### Architectural use

    * prompt-template authoring
    * style-template drafting
    * reusable assistant instruction experimentation
    * future publishable prompt/style artifacts after curation

    ### Owner

    * `chummer.run-services` for orchestration-side prompt toolchain
    * possible future publication via `chummer-hub-registry`

    ### Hard boundary

    * not runtime truth by itself
    * not a substitute for Chummer prompt/version registry

    ## ChatPlayground AI

    ### Role

    Evaluation lab only.

    ### Architectural use

    * provider comparison
    * regression evaluation
    * output-shape evaluation
    * cost/quality route testing

    ### Owner

    * `chummer.run-services`

    ### Hard boundary

    * not production runtime
    * not canonical prompt home

    ## BrowserAct

    ### Role

    Automation fallback and account-fact discovery.

    ### Architectural use

    * external account verification
    * no-API automation fallback
    * tool inventory refresh
    * operational bridge where no first-class API exists

    ### Owner

    * `chummer.run-services`

    ### Hard boundary

    * never a critical hot-path requirement
    * never a canonical runtime store
    * never direct user-facing truth

    ## ApproveThis

    ### Role

    Approval inbox bridge.

    ### Architectural use

    * review inbox forwarding
    * publication approval bridge
    * media approval bridge
    * canon-write approval bridge
    * recap approval bridge

    ### Owner

    * `chummer.run-services`

    ### Hard boundary

    * Chummer approval state remains canonical
    * ApproveThis is a notification / inbox surface, not approval truth

    ## Documentation.AI

    ### Role

    Docs/help plane.

    ### Architectural use

    * public docs/help center
    * API docs
    * cited help assistant
    * operator and publisher documentation
    * onboarding docs

    ### Owner

    * integration/orchestration: `chummer.run-services`
    * canonical source material: `chummer-design`, `chummer-hub-registry`, approved docs exports

    ### Hard boundary

    * not the canonical architecture repo
    * not the only docs store
    * not an unreviewed source of policy

    ## MetaSurvey

    ### Role

    Feedback loop.

    ### Architectural use

    * player/GM feedback
    * creator/publisher feedback
    * Coach usefulness ratings
    * recap/video quality ratings
    * moderation/registry quality surveys

    ### Owner

    * `chummer.run-services`

    ### Hard boundary

    * not canonical analytics warehouse
    * not canonical moderation state

    ## Teable

    ### Role

    Curated projection surface.

    ### Architectural use

    * moderation projection board
    * curation board
    * campaign-ops board
    * release-status or triage board
    * back-office operator surface

    ### Owner

    * `chummer.run-services`

    ### Hard boundary

    * not runtime DB
    * not session truth
    * not registry truth
    * not approval truth

    ## ApiX-Drive

    ### Role

    Automation bridge.

    ### Architectural use

    * low-risk outbound automations
    * mirrored notifications to ops systems
    * non-critical workflow glue
    * integration experiments before first-party adapters exist

    ### Owner

    * `chummer.run-services`

    ### Hard boundary

    * not a required hop for session relay
    * not a required hop for approval truth
    * not a required hop for media truth

    ## Paperguide

    ### Role

    Cited research and synthesis support.

    ### Architectural use

    * internal research
    * design-research support
    * authoring support for docs/help
    * lore/reference curation support for human operators

    ### Owner

    * `chummer-design` for design research
    * `chummer.run-services` for internal operator help/research assist

    ### Hard boundary

    * not live rules truth
    * not canon writer

    ## Vizologi

    ### Role

    Strategy and ideation tool.

    ### Architectural use

    * product strategy
    * packaging/channel strategy
    * creator-program ideation
    * roadmap research

    ### Owner

    * `chummer-design`

    ### Hard boundary

    * not runtime
    * not product truth
    * not session/path logic

    ## MarkupGo

    ### Role

    Document-render adapter.

    ### Architectural use

    * packets
    * briefs
    * dossiers
    * invoices/manifests
    * bulletins
    * PDF/image document outputs

    ### Owner

    * `chummer-media-factory`

    ### Hard boundary

    * not content author
    * not manifest owner
    * not archive truth

    ## PeekShot

    ### Role

    Preview/thumbnail/share-card adapter.

    ### Architectural use

    * previews
    * thumbnails
    * share cards
    * preview derivatives for docs, portraits, and video

    ### Owner

    * `chummer-media-factory`

    ### Hard boundary

    * not canonical parent asset
    * not canonical manifest

    ## Mootion

    ### Role

    Bounded video-render adapter.

    ### Architectural use

    * NPC message videos
    * recap/news videos
    * route explainer clips
    * short ambient or briefing clips

    ### Owner

    * `chummer-media-factory`

    ### Hard boundary

    * no unbounded long-form runtime dependency
    * no bypass of preview-first or approval policy
    * no canonical archive ownership

    ## AvoMap

    ### Role

    Route visualization / route-render adapter.

    ### Architectural use

    * route previews
    * travel/exfil visualizations
    * movement recap assets
    * map-backed route clips

    ### Owner

    * orchestration-side route semantics: `chummer.run-services`
    * render-side output execution: `chummer-media-factory`

    ### Hard boundary

    * not source of route truth
    * not source of campaign geography semantics

    ## Internxt Cloud Storage

    ### Role

    Cold archive adapter.

    ### Architectural use

    * cold archive for media artifacts
    * deep retention storage
    * non-hot restore source

    ### Owner

    * `chummer-media-factory`

    ### Hard boundary

    * not hot asset serving
    * not canonical manifest source

    ## Invoiless

    ### Role

    Back-office only.

    ### Architectural use

    * future vendor/admin invoicing
    * possible future creator-marketplace back-office

    ### Owner

    * future `chummer.run-services` back-office scope only if needed

    ### Hard boundary

    * not current product dependency
    * not monetization truth today

    ## FastestVPN PRO

    ### Role

    Ops utility only.

    Out of core product architecture.

    ## OneAir

    ### Role

    Out of product architecture.

    ## Headway

    ### Role

    Out of core runtime architecture.
    May be used as a team knowledge utility only.

    ## Activation verification rule

    Because these tools are owned and assumed available, the gating rule changes from redemption gating to activation verification gating.

    A tool may be architecturally planned, but it is not runtime-approved until:

    * the owning repo is assigned
    * the adapter boundary is defined
    * the Chummer receipt model exists
    * the kill switch exists
    * the provenance model exists
    * fallback behavior exists
    * secrets handling is defined
    * the integration is reflected in milestones

    ## Contract additions

    ### In `Chummer.Run.Contracts`

    Add:

    * `ProviderRouteReceipt`
    * `ProviderRouteRef`
    * `ApprovalBridgeReceipt`
    * `DocsHelpRef`
    * `SurveyRef`
    * `AutomationBridgeReceipt`
    * `ResearchAssistReceipt`
    * `PromptTemplateRef`
    * `PromptRouteRef`

    ### In `Chummer.Media.Contracts`

    Add:

    * `MediaProviderReceipt`
    * `MediaProviderRef`
    * `MediaPlanHash`
    * `MediaInputRef`
    * `MediaSafetyResult`
    * `MediaPreviewRef`
    * `MediaArchiveRef`
    * `MediaRetentionOverrideRef`
    * `MediaRouteVisualizationRef`

    ### In `Chummer.Hub.Registry.Contracts`

    Add only when promoted into reusable registry truth:

    * `TemplatePackRef`
    * `StylePackRef`
    * `PublishedHelpRef`
    * `ArtifactExternalPreviewRef`

    ## Release-gate rule

    No external integration reaches production use until:

    * adapter exists
    * Chummer receipt exists
    * Chummer kill switch exists
    * Chummer provenance rules exist
    * system-of-record rule is preserved
    * owning repo is explicit
    * milestone rollout is published
    * client-side secret exposure is impossible
    """
).strip() + "\n"

DESIGN_FEEDBACK = textwrap.dedent(
    """
    # Lead-dev feedback: external tools plane and repo maturity

    Date: 2026-03-10

    This feedback consolidates the latest lead-dev direction for the Chummer split.

    ## External tools plane

    The LTD inventory is now large enough to matter architecturally.
    Treat owned tools as an explicit External Tools Plane, not as repo-local improvisation.

    Key posture:

    * all tracked LTDs are internally redeemed and activated
    * activation verification still gates runtime approval
    * no third-party tool becomes a system of record
    * orchestration-side vendor ownership lives in `chummer.run-services`
    * render/archive vendor ownership lives in `chummer-media-factory`
    * policy, rollout, provenance, and blocker publication live in `chummer-design`

    Tier distinctions to preserve:

    * `1min.AI` and `BrowserAct` are workspace integration Tier 1
    * `Teable` is workspace integration Tier 2 even though its vendor plan is License Tier 4
    * `Paperguide` is workspace integration Tier 3 even though its vendor plan is License Tier 4

    The repo should reason from workspace integration tier, kill-switchability, provenance, and system-of-record rules, not from vendor-plan labels.

    ## Architectural directives

    1. Make the external tools plane canonical in design before expanding repo-local adapter work.
    2. Keep clients free of vendor credentials and direct SDK coupling.
    3. Require Chummer-side receipts and provenance for every external-provider-assisted artifact or response.
    4. Treat Teable as a curated projection board only, never as runtime or registry truth.
    5. Treat Paperguide as cited design/operator research support only, never as live rules or canon truth.
    6. Keep media providers behind `chummer-media-factory` adapters with manifest-first provenance.

    ## Repo-specific emphasis

    * `chummer.run-services`: own reasoning, approval, docs/help, survey, automation, and research adapters behind receipts and kill switches.
    * `chummer-media-factory`: own document, preview, video, route-visualization, and archive adapters with retention and provenance rules.
    * `chummer-hub-registry`: only reference promoted reusable help/template/style/preview artifacts; do not run vendor adapters.
    * `chummer-presentation` and `chummer-play`: render upstream projections only; never own vendor keys or direct provider orchestration.
    * `chummer-core-engine`: remain external-tool agnostic except for deterministic inputs and outputs.
    * `chummer-ui-kit`: remain vendor-free and package-only.

    ## OODA questions for design

    * Which integrations are runtime-approved versus merely activation-verified?
    * Which receipts must land in `Chummer.Run.Contracts` versus `Chummer.Media.Contracts`?
    * Which integrations are projection-only and must never appear on hot paths?
    * Which milestones should gate rollout of docs/help, survey, approval bridge, route-render, and archive capabilities?
    """
).strip() + "\n"

PROJECT_FEEDBACK = {
    "chummer-core-engine": textwrap.dedent(
        """
        # Lead-dev feedback: core external-tools boundary

        Date: 2026-03-10

        Core stays external-tool agnostic.

        Hold the line on these rules:

        * no provider SDKs or direct vendor orchestration in core
        * no external tool becomes engine truth, reducer truth, explain truth, or runtime truth
        * only consume approved deterministic inputs or emit canonical DTOs for downstream repos to use

        If a feature requires provider routing, approvals, docs/help, survey, previews, route rendering, or archive handling, it belongs elsewhere.
        """
    ).strip() + "\n",
    "chummer-presentation": textwrap.dedent(
        """
        # Lead-dev feedback: presentation external-tools boundary

        Date: 2026-03-10

        Presentation may render upstream projections that refer to external-tool outputs, but it must not own vendor keys, vendor SDKs, or direct third-party orchestration.

        Keep docs/help, approval, preview, and media execution behind hosted or media-factory surfaces.
        """
    ).strip() + "\n",
    "chummer.run-services": textwrap.dedent(
        """
        # Lead-dev feedback: run-services external integrations

        Date: 2026-03-10

        Run-services is the orchestration owner for non-render external integrations.

        Priorities:

        * own reasoning-provider routing and receipts
        * own approval, docs/help, survey, automation, and research bridges
        * keep Teable as a projection board only
        * keep Paperguide as cited research assistance only
        * emit Chummer receipts, provenance, and kill switches for every provider route
        * never let external vendors become approval truth, registry truth, or canonical runtime truth
        """
    ).strip() + "\n",
    "chummer-play": textwrap.dedent(
        """
        # Lead-dev feedback: play external-tools boundary

        Date: 2026-03-10

        Play may render upstream projections that refer to external outputs, but it must never own vendor keys, vendor SDKs, or direct provider orchestration.

        Preserve the client-local ledger boundary and keep all third-party access server-side or worker-side.
        """
    ).strip() + "\n",
    "chummer-ui-kit": textwrap.dedent(
        """
        # Lead-dev feedback: ui-kit external-tools boundary

        Date: 2026-03-10

        UI kit remains vendor-free and package-only.

        Do not introduce provider SDKs, network clients, or external-tool-specific business logic into the shared UI boundary.
        """
    ).strip() + "\n",
    "chummer-hub-registry": textwrap.dedent(
        """
        # Lead-dev feedback: hub-registry external-tools boundary

        Date: 2026-03-10

        Hub-registry may reference promoted reusable help, template, style, and preview artifacts once they become registry truth.

        It must not own provider adapters, approval bridges, docs/help vendor execution, or render execution.
        """
    ).strip() + "\n",
    "chummer-media-factory": textwrap.dedent(
        """
        # Lead-dev feedback: media-factory external integrations

        Date: 2026-03-10

        Media-factory is the only repo allowed to own media/render/archive adapters.

        Initial vendor map to preserve:

        * MarkupGo - document render
        * PeekShot - preview and thumbnail generation
        * Mootion - bounded video
        * AvoMap - route visualization
        * Internxt - cold archive

        Required rules:

        * every media job produces a Chummer manifest
        * provider output is never the canonical asset record by itself
        * provenance, safety, retention, and archive decisions are captured explicitly
        * provider choice remains adapter-private and kill-switchable
        """
    ).strip() + "\n",
}

ARCHITECTURE_SECTION = textwrap.dedent(
    """
    ## External tools plane

    Project Chummer has an explicit External Tools Plane.

    This plane exists to integrate owned third-party capabilities without allowing any third-party capability to become canonical Chummer truth.

    ### External tools plane rules

    1. External tools always sit behind Chummer-owned adapters.
    2. External tools may assist, project, notify, visualize, render, or archive.
    3. External tools may not own:

       * rules truth
       * reducer truth
       * runtime truth
       * session truth
       * approval truth
       * registry truth
       * artifact truth
       * memory/canon truth
    4. No client repo may access third-party tools directly.
    5. All external-provider-assisted outputs that re-enter Chummer must carry Chummer-side provenance and receipts.
    6. `chummer.run-services` owns orchestration-side integrations.
    7. `chummer-media-factory` owns render/archive integrations.
    8. `chummer-design` owns external-tools policy and rollout governance.

    ### External tools plane by repo

    * `chummer.run-services`

      * reasoning providers
      * approval bridges
      * docs/help bridges
      * survey bridges
      * automation bridges
      * research/eval tooling

    * `chummer-media-factory`

      * document render adapters
      * preview/thumbnail adapters
      * image/video adapters
      * route visualization adapters
      * cold-archive adapters

    * `chummer-hub-registry`

      * references to promoted reusable template/style/help/preview artifacts only

    ### Non-goals

    * no third-party tool is a required hop for live session relay
    * no third-party tool holds canonical approval state
    * no third-party tool owns Chummer media manifests
    * no third-party tool bypasses Chummer moderation or canonization
    """
).strip() + "\n"

OWNERSHIP_SECTION = textwrap.dedent(
    """
    ## External integration ownership

    ### `chummer-design`

    Owns:

    * external-tool classification
    * approved usage policy
    * system-of-record rules
    * rollout governance
    * provenance requirements

    Must not own:

    * provider SDK implementations
    * runtime secrets
    * vendor adapters

    ### `chummer.run-services`

    Owns:

    * orchestration-side external integrations
    * reasoning-provider routing
    * approval bridges
    * docs/help bridges
    * survey bridges
    * automation bridges
    * research/eval/prompt-tooling integrations

    Must not own:

    * media rendering internals
    * client-side vendor access
    * duplicate engine semantics

    ### `chummer-media-factory`

    Owns:

    * render/archive adapters
    * provider-run receipts for media work
    * media provenance capture
    * media archive execution

    Must not own:

    * approvals policy
    * campaign/session meaning
    * client UX
    * registry truth

    ### `chummer-presentation` and `chummer-play`

    Must not own:

    * vendor credentials
    * direct provider SDK access
    * direct third-party orchestration
    """
).strip() + "\n"

RUN_SERVICES_SECTION = textwrap.dedent(
    """
    ## External integrations scope

    `chummer.run-services` is the orchestration owner for all non-render external-tool integrations.

    ### Owns

    * `IReasoningProviderRoute`
    * `IApprovalBridge`
    * `IDocumentationBridge`
    * `ISurveyBridge`
    * `IAutomationBridge`
    * `IEvalLabAdapter`
    * `IResearchAssistAdapter`
    * prompt/style/persona toolchain orchestration
    * provider-route receipts for non-media operations

    ### Initial vendor mapping

    * 1min.AI - fallback reasoning and multimodal route
    * AI Magicx - structured AI route
    * Prompting Systems - prompt/style authoring support
    * ChatPlayground AI - eval lab only
    * BrowserAct - no-API automation fallback, off critical path
    * ApproveThis - approval bridge
    * Documentation.AI - docs/help bridge
    * MetaSurvey - survey bridge
    * Teable - curated ops projection bridge
    * ApiX-Drive - low-risk automation bridge
    * Paperguide - cited research assist
    * Vizologi - design/program strategy support only

    ### Must not own

    * document/image/video rendering internals
    * media binary lifecycle
    * direct provider use from clients
    * canonical rules math
    * registry truth

    ### Required design rules

    * every provider route emits a Chummer receipt
    * every provider route is kill-switchable
    * every provider route degrades gracefully
    * every provider route preserves Chummer as system of record
    """
).strip() + "\n"

MEDIA_FACTORY_SECTION = textwrap.dedent(
    """
    ## External media integrations scope

    `chummer-media-factory` is the only repo allowed to own media/render/archive adapters.

    ### Owns

    * `IDocumentRenderAdapter`
    * `IPreviewRenderAdapter`
    * `IImageRenderAdapter`
    * `IVideoRenderAdapter`
    * `IRouteRenderAdapter`
    * `IArchiveAdapter`
    * media provider receipts
    * media provider provenance
    * media safety/moderation result capture
    * media archive execution
    * media retention/archive policy execution

    ### Initial vendor mapping

    * MarkupGo - document-render adapter
    * PeekShot - preview/thumbnail/share-card adapter
    * Mootion - bounded video adapter
    * AvoMap - route-render adapter
    * Internxt - cold-archive adapter
    * optional 1min.AI / AI Magicx image assistance only when wrapped behind media-factory adapters and governed by provenance rules

    ### Must not own

    * campaign/session meaning
    * approval policy
    * canon policy
    * registry publication
    * client UX
    * general AI orchestration

    ### Required design rules

    * every media job produces a Chummer manifest
    * provider outputs are never the canonical asset record alone
    * previews and thumbnails are linked assets
    * archive providers are never the hot path
    * provider choice is adapter-private and switchable
    """
).strip() + "\n"

DESIGN_SECTION = textwrap.dedent(
    """
    ## External tools governance

    `chummer-design` must classify each external tool as:

    * runtime-adjacent orchestration
    * runtime-adjacent media
    * human-ops / projection
    * research / eval
    * non-product utility

    No external tool is architecturally accepted until:

    * owning repo is assigned
    * adapter boundary is defined
    * provenance requirements are defined
    * system-of-record rule is defined
    * kill-switch rule is defined
    * rollout milestone is defined
    """
).strip() + "\n"

HUB_REGISTRY_SECTION = textwrap.dedent(
    """
    ## External integration note

    `chummer-hub-registry` may reference reusable external-facing help, preview, template, and style artifacts only when they have been promoted into registry truth.

    It must not:

    * run provider adapters
    * own approval bridges
    * own docs/help vendor execution
    * own render execution
    """
).strip() + "\n"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_section(path: Path, heading: str, block: str) -> None:
    content = read(path)
    pattern = re.compile(rf"(?ms)^## {re.escape(heading)}\n.*?(?=^## |\Z)")
    replacement = block.rstrip() + "\n\n"
    if pattern.search(content):
        content = pattern.sub(replacement, content, count=1)
    else:
        if not content.endswith("\n"):
            content += "\n"
        content += "\n" + replacement
    write(path, content)


def update_read_order(path: Path) -> None:
    content = read(path)
    old_name = OLD_POLICY_FILE
    new_name = NEW_POLICY_FILE
    content = content.replace(old_name, new_name)
    if new_name not in content:
        anchor = "2. `ARCHITECTURE.md`"
        replacement = "2. `ARCHITECTURE.md`\n3. `EXTERNAL_TOOLS_PLANE.md`"
        content = content.replace(anchor, replacement)
    content = re.sub(r"\n([4-9])\. `OWNERSHIP_MATRIX\.md`", "\n4. `OWNERSHIP_MATRIX.md`", content)
    content = re.sub(r"\n([5-9])\. `PROGRAM_MILESTONES\.yaml`", "\n5. `PROGRAM_MILESTONES.yaml`", content)
    content = re.sub(r"\n([6-9])\. `CONTRACT_SETS\.yaml`", "\n6. `CONTRACT_SETS.yaml`", content)
    content = re.sub(r"\n([7-9])\. `GROUP_BLOCKERS\.md`", "\n7. `GROUP_BLOCKERS.md`", content)
    content = re.sub(r"\n([8-9])\. `projects/\*\.md` for repo-specific scope", "\n8. `projects/*.md` for repo-specific scope", content)
    write(path, content)


def update_program_milestones(path: Path) -> None:
    data = yaml.safe_load(read(path))
    phases = data.get("program_phases") or []

    def upsert(phase_id: str, milestone: dict, after_id: str | None = None) -> None:
        for phase in phases:
            if phase.get("id") != phase_id:
                continue
            milestones = phase.setdefault("milestones", [])
            for index, item in enumerate(milestones):
                if item.get("id") == milestone["id"]:
                    milestones[index] = milestone
                    return
            insert_at = len(milestones)
            if after_id:
                for index, item in enumerate(milestones):
                    if item.get("id") == after_id:
                        insert_at = index + 1
                        break
            milestones.insert(insert_at, milestone)
            return
        raise RuntimeError(f"missing phase {phase_id}")

    upsert(
        "A",
        {
            "id": "A4",
            "title": "External tools plane canon",
            "owners": ["chummer-design", "chummer.run-services", "chummer-media-factory"],
            "status": "open",
            "exit": [
                "External tools policy exists centrally.",
                "All owned tools are classified by architectural role.",
                "System-of-record rules are documented.",
                "External integrations are assigned to owning repos.",
            ],
        },
        after_id="A3",
    )
    upsert(
        "C",
        {
            "id": "C1b",
            "title": "Orchestration-side external adapters",
            "owners": ["chummer.run-services"],
            "status": "open",
            "exit": [
                "Approval, docs/help, survey, research, and automation bridges are adapter-based.",
                "Provider routes emit Chummer receipts.",
                "No client repo owns third-party provider access.",
            ],
        },
        after_id="C1",
    )
    upsert(
        "C",
        {
            "id": "C1c",
            "title": "Media-side external adapters",
            "owners": ["chummer-media-factory"],
            "status": "open",
            "exit": [
                "Document, preview, route, video, and archive adapters exist behind media-factory.",
                "Media provenance is captured in manifests.",
                "Provider choice remains switchable and kill-switchable.",
            ],
        },
        after_id="C1b",
    )
    upsert(
        "E",
        {
            "id": "E2b",
            "title": "Docs, feedback, and operator projection plane complete",
            "owners": ["chummer.run-services", "chummer-design"],
            "status": "open",
            "exit": [
                "Docs/help surfaces are integrated.",
                "Feedback collection loops are integrated.",
                "Operator projection boards exist without becoming systems of record.",
            ],
        },
        after_id="E2",
    )
    write(path, yaml.safe_dump(data, sort_keys=False))


def update_sync_manifest(path: Path) -> None:
    data = yaml.safe_load(read(path))
    sources = [str(item) for item in data.get("common_product_sources") or []]
    sources = [item for item in sources if item != f"products/chummer/{OLD_POLICY_FILE}"]
    wanted = f"products/chummer/{NEW_POLICY_FILE}"
    if wanted not in sources:
        try:
            index = sources.index("products/chummer/ARCHITECTURE.md") + 1
        except ValueError:
            index = len(sources)
        sources.insert(index, wanted)
    data["common_product_sources"] = sources
    write(path, yaml.safe_dump(data, sort_keys=False))


def delete_stale_policy_file(path: Path) -> None:
    if path.exists():
        path.unlink()


def mirror_design_repo() -> None:
    manifest = yaml.safe_load(read(PRODUCT_ROOT / "sync" / "sync-manifest.yaml"))
    mirrors = manifest.get("mirrors") or []
    for mirror in mirrors:
        repo_name = str(mirror.get("repo") or "").strip()
        repo_root = REPO_ROOTS.get(repo_name)
        if not repo_root:
            continue
        repo_root.mkdir(parents=True, exist_ok=True)
        product_target = str(mirror.get("product_target") or mirror.get("target") or ".codex-design/product").strip()
        product_sources = [str(item) for item in mirror.get("product_sources") or mirror.get("sources") or []]
        duplicate_basenames = {
            name
            for name, count in Counter(Path(source).name for source in product_sources).items()
            if count > 1
        }

        stale_target = repo_root / product_target / OLD_POLICY_FILE
        if stale_target.exists():
            stale_target.unlink()

        def target_rel(source_rel: str) -> Path:
            source_path = Path(source_rel)
            if source_path.name in duplicate_basenames:
                parts = list(source_path.parts)
                if len(parts) >= 2 and parts[0] == "products" and parts[1] == "chummer":
                    relative_source = Path(*parts[2:])
                else:
                    relative_source = source_path
            else:
                relative_source = Path(source_path.name)
            return Path(product_target) / relative_source

        for source_rel in product_sources:
            source = DESIGN_ROOT / source_rel
            if not source.is_file():
                continue
            destination = repo_root / target_rel(source_rel)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)

        repo_source = str(mirror.get("repo_source") or "").strip()
        if repo_source:
            source = DESIGN_ROOT / repo_source
            if source.is_file():
                destination = repo_root / str(mirror.get("repo_target") or ".codex-design/repo/IMPLEMENTATION_SCOPE.md")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)

        review_source = str(mirror.get("review_source") or "").strip()
        if review_source:
            source = DESIGN_ROOT / review_source
            if source.is_file():
                destination = repo_root / str(mirror.get("review_target") or ".codex-design/review/REVIEW_CONTEXT.md")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)


def write_feedback(repo_root: Path, name: str, content: str) -> None:
    target = repo_root / "feedback" / name
    write(target, content)


def inject_feedback_package() -> None:
    filename = "2026-03-10-lead-dev-external-tools-plane-feedback.md"
    write_feedback(DESIGN_ROOT, filename, DESIGN_FEEDBACK)
    write(GROUP_FEEDBACK_ROOT / filename, DESIGN_FEEDBACK)
    for repo_name, content in PROJECT_FEEDBACK.items():
        repo_root = REPO_ROOTS.get(repo_name)
        if repo_root:
            write_feedback(repo_root, filename, content)


def main() -> None:
    write(PRODUCT_ROOT / NEW_POLICY_FILE, EXTERNAL_TOOLS_PLANE)
    delete_stale_policy_file(PRODUCT_ROOT / OLD_POLICY_FILE)
    update_read_order(PRODUCT_ROOT / "README.md")
    replace_section(PRODUCT_ROOT / "ARCHITECTURE.md", "External tools plane", ARCHITECTURE_SECTION)
    replace_section(PRODUCT_ROOT / "OWNERSHIP_MATRIX.md", "External integration ownership", OWNERSHIP_SECTION)
    replace_section(PRODUCT_ROOT / "projects" / "run-services.md", "External integrations scope", RUN_SERVICES_SECTION)
    replace_section(PRODUCT_ROOT / "projects" / "media-factory.md", "External media integrations scope", MEDIA_FACTORY_SECTION)
    replace_section(PRODUCT_ROOT / "projects" / "design.md", "External tools governance", DESIGN_SECTION)
    replace_section(PRODUCT_ROOT / "projects" / "hub-registry.md", "External integration note", HUB_REGISTRY_SECTION)
    update_program_milestones(PRODUCT_ROOT / "PROGRAM_MILESTONES.yaml")
    update_sync_manifest(PRODUCT_ROOT / "sync" / "sync-manifest.yaml")
    mirror_design_repo()
    inject_feedback_package()
    print("Injected revised external tools plane, refreshed mirrors, and published per-repo feedback.")


if __name__ == "__main__":
    main()
