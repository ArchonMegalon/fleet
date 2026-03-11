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

    The public Chummer repo split is real, but the design repo is still behind the actual program state.

    ## Main findings

    * `chummer-design` still trails the public repo graph and still keeps orphan product docs at repo root instead of fully canonicalizing under `products/chummer/*`.
    * `products/chummer/README.md`, `ARCHITECTURE.md`, `PROGRAM_MILESTONES.yaml`, and `GROUP_BLOCKERS.md` still describe older split sequencing and older extraction status.
    * mirror coverage still lags the live repo graph, especially around `chummer-media-factory`
    * downstream package truth still drifts in `chummer-play` and `chummer.run-services`
    * LTD ownership and activation truth has moved ahead of the public inventory, which now creates design debt of its own

    ## Design direction

    The missing layer is an explicit external tools plane owned by `chummer-design`.

    Required rules:

    1. `chummer-design` owns classification, system-of-record rules, provenance rules, rollout rules, and kill-switch rules for external tools.
    2. `chummer.run-services` owns orchestration-side adapters.
    3. `chummer-media-factory` owns render and archive adapters.
    4. client repos do not get vendor keys or direct vendor SDKs.
    5. third-party-assisted outputs that re-enter Chummer get Chummer receipts and provenance.

    ## Concrete Chummer repo follow-up

    1. replace thin canonical files in `products/chummer/*`
    2. add `chummer-media-factory` everywhere central canon enumerates active repos and mirrors
    3. remove root-level orphan product docs from `chummer-design`
    4. freeze package canon for play and relay contracts
    5. give `chummer-media-factory` stronger central mirror and review coverage

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
