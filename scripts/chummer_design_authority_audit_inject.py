#!/usr/bin/env python3
from __future__ import annotations

import textwrap
from pathlib import Path


DESIGN_FEEDBACK_ROOT = Path("/docker/chummercomplete/chummer-design/feedback")
GROUP_FEEDBACK_ROOT = Path("/docker/fleet/state/groups/chummer-vnext/feedback")
FILENAME = "2026-03-10-chummer-design-authority-audit.md"


AUDIT_TEXT = textwrap.dedent(
    """
    # chummer-design authority audit follow-up

    Date: 2026-03-10
    Audience: `chummer-design`
    Status: injected fleet feedback

    I audited `chummer-design` again, since that’s the repo we were trying to make authoritative.

    Verdict: it is better scaffolded, but still not caught up enough to be the lead designer without manual correction. The root README and repo map are there, and the repo clearly presents itself as the canonical cross-repo design front door. But the root still carries orphan product docs and a top-level `chummer-media-factory` folder, which means the repo is still violating its own “canon lives under `products/chummer/*`” discipline.

    The biggest problem is still repo-graph truth. `products/chummer/README.md` still lists active repos as core, presentation, run-services, play, ui-kit, and hub-registry, but it still omits `chummer-media-factory`. It also still describes ui-kit, hub-registry, and media-factory as future extraction steps, and `ARCHITECTURE.md` still lists the split order as “finish `chummer-play`, then `chummer-ui-kit`, then `chummer-hub-registry`, then `chummer-media-factory`,” even though those repos already exist publicly.

    The second problem is depth. The canonical files are still far too thin for a repo that is supposed to govern eight active Chummer repos. `VISION.md`, `ARCHITECTURE.md`, and `OWNERSHIP_MATRIX.md` are each effectively a one-paragraph or one-line summary. `PROGRAM_MILESTONES.yaml` still explicitly says milestone coverage is incomplete and still describes play as scaffold-stage, ui-kit as not yet materialized, and registry/media as not yet isolated repo boundaries. `GROUP_BLOCKERS.md` is still publishing “Bootstrap chummer-hub-registry” as a current recommendation even though that repo already exists.

    The third problem is mirror coverage. The sync manifest still mirrors only core, presentation, run-services, play, ui-kit, and hub-registry; it still does not include media-factory. And the live `chummer-play` root still shows no visible `.codex-design` mirror even though the sync manifest says play should receive one. That means worker context is still inconsistent across active repos.

    The fourth problem is that the design repo still is not successfully governing downstream package truth. `chummer-play`’s README still says the repo must consume `Chummer.Contracts`, `Chummer.Play.Contracts`, and `Chummer.Ui.Kit`, while `Directory.Build.props` names `Chummer.Engine.Contracts`, `Chummer.Play.Contracts`, and `Chummer.Ui.Kit`. That package-name drift is exactly the kind of thing `chummer-design` should have already frozen.

    The fifth problem is contract-seam policing in `chummer.run-services`. The play-side relay contracts still define `SessionEventEnvelope`, `SessionRelayConvergenceDiagnostics`, `SessionRelayMergeResponse`, and `SessionEventProjectionDto`, while the run-side relay contracts still define the same semantic family again. On top of that, `MediaContracts.cs` still directly imports `Chummer.Play.Contracts.Memory`, `Chummer.Play.Contracts.Spider`, and `Chummer.Media.Contracts`, which means the design repo still has not forced a clean boundary between orchestration-side media contracts and play-side/runtime-side concerns.

    There is one more design-governance gap: media-factory is still not operationally onboarded. Publicly it is still a 2-commit scaffold repo with docs, feedback, and scripts, no visible `src/` tree, and a README that still says contract-plane and render-only DTO extraction are in progress. That makes the design repo’s omission of media-factory from active-repo truth and sync coverage more serious, because the newest split repo is also the one most in need of strong mirrored guidance.

    Current grade:

    - structure: yellow
    - repo-graph truth: red
    - milestone/blocker truth: red
    - mirror completeness: red
    - package/contract governance: yellow-red
    - ability to steer workers safely: yellow-red

    Shortest fix order:

    1. Replace the stub canon in `products/chummer/*`.
    2. Add media-factory everywhere central canon enumerates active repos and mirrors.
    3. Remove root-level orphan product docs from `chummer-design`.
    4. Force package-name canon in play and contract-family canon in run-services.
    """
).strip() + "\n"


def publish(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    target = root / FILENAME
    target.write_text(AUDIT_TEXT, encoding="utf-8")
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
