#!/usr/bin/env python3
from __future__ import annotations

import textwrap
from pathlib import Path


DESIGN_FEEDBACK_ROOT = Path("/docker/chummercomplete/chummer-design/feedback")
GROUP_FEEDBACK_ROOT = Path("/docker/fleet/state/groups/chummer-vnext/feedback")
FILENAME = "2026-03-11-chummer-public-design-and-ltd-audit.md"


CONTENT = textwrap.dedent(
    """
    # Chummer public design and LTD audit

    Date: 2026-03-11
    Audience: `chummer-design` and `chummer-vnext`
    Status: injected fleet feedback

    The public Chummer repo split is real, but `chummer-design` is still behind the actual program state and is not yet safe enough to act as a trustworthy lead-designer repo without manual correction.

    ## Main findings

    * `chummer-design` still keeps orphan product docs and a top-level `chummer-media-factory/` folder at repo root instead of fully canonicalizing under `products/chummer/*`.
    * `products/chummer/README.md` still omits `chummer-media-factory` from active repo truth and still frames `ui-kit`, `hub-registry`, and `media-factory` as future extractions.
    * `VISION.md`, `ARCHITECTURE.md`, `OWNERSHIP_MATRIX.md`, `PROGRAM_MILESTONES.yaml`, `CONTRACT_SETS.yaml`, and `GROUP_BLOCKERS.md` are still too thin or still describe older bootstrap/extraction realities.
    * mirror coverage still lags the live repo graph, especially around `chummer-media-factory`, and `chummer-play` still lacks visible `.codex-design` mirror coverage in the public repo view.
    * package and contract truth still drifts downstream: `chummer-play` README naming still diverges from package canon, and `chummer.run-services` still duplicates relay/runtime DTO families and mixes media/play concerns.
    * `chummer-media-factory` is still the least mature split repo and is also the least centrally governed.
    * LTD ownership and activation truth has moved ahead of the public inventory, which now creates design debt of its own.

    ## Audit grade

    * structure: yellow
    * repo-graph truth: red
    * milestone/blocker truth: red
    * mirror completeness: red
    * package/contract governance: yellow-red
    * ability to steer workers safely: yellow-red

    ## Design direction

    The missing layer is an explicit external tools plane owned by `chummer-design`, plus a much stronger canonical product tree that describes the repo graph that actually exists today.

    Required rules:

    1. `chummer-design` owns classification, system-of-record rules, provenance rules, rollout rules, and kill-switch rules for external tools.
    2. `chummer.run-services` owns orchestration-side adapters.
    3. `chummer-media-factory` owns render and archive adapters.
    4. client repos do not get vendor keys or direct vendor SDKs.
    5. third-party-assisted outputs that re-enter Chummer get Chummer receipts and provenance.

    ## Concrete Chummer repo follow-up

    1. make central canon describe the repo graph that actually exists: add `chummer-media-factory` everywhere and stop describing `ui-kit`, `hub-registry`, and `media-factory` as future extractions
    2. replace thin canonical files in `products/chummer/*`, especially milestones, blockers, ownership, and contract registry
    3. remove root-level orphan product docs from `chummer-design`
    4. add `chummer-media-factory` to `sync-manifest.yaml`, create `products/chummer/projects/media-factory.md`, and ensure media-factory review coverage exists
    5. mirror `.codex-design` into `chummer-play`
    6. freeze package canon for `chummer-play` and collapse duplicated relay/runtime DTO families in `chummer.run-services`
    7. give `chummer-media-factory` stronger central mirror and review coverage before increasing worker autonomy

    ## LTD integration guidance

    Orchestration-side fits:
    * 1min.AI
    * AI Magicx
    * Prompting Systems
    * ChatPlayground AI
    * BrowserAct
    * ApproveThis
    * Documentation.AI
    * MetaSurvey
    * Teable
    * ApiX-Drive
    * Paperguide
    * Vizologi

    Media-side fits:
    * MarkupGo
    * PeekShot
    * Mootion
    * AvoMap
    * Internxt
    * Unmixr

    ## Unmixr-specific note

    Unmixr is a strong fit for `chummer-media-factory` as a TTS and voice-clone adapter. Treat it as an audio-generation adapter with Chummer-owned manifests, receipts, retention rules, and optional capability discovery rather than as a fixed entitlement assumption.

    ## Bottom line

    `chummer-design` is still a bootstrap governance repo, not yet a trustworthy lead-designer repo. The scaffolding is there; the canonical truth is still behind the actual program.
    """
).strip() + "\n"


def write(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / FILENAME).write_text(CONTENT, encoding="utf-8")


def main() -> None:
    write(DESIGN_FEEDBACK_ROOT)
    write(GROUP_FEEDBACK_ROOT)
    print("Injected Chummer public design/LTD audit into design and group feedback lanes.")


if __name__ == "__main__":
    main()
