#!/usr/bin/env python3
from __future__ import annotations

import textwrap
from pathlib import Path


DESIGN_ROOT = Path("/docker/chummercomplete/chummer-design")
GROUP_FEEDBACK_ROOT = Path("/docker/fleet/state/groups/chummer-vnext/feedback")

REPO_ROOTS = {
    "chummer-core-engine": Path("/docker/chummercomplete/chummer-core-engine"),
    "chummer-presentation": Path("/docker/chummercomplete/chummer-presentation"),
    "chummer.run-services": Path("/docker/chummercomplete/chummer.run-services"),
    "chummer-play": Path("/docker/chummercomplete/chummer-play"),
    "chummer-ui-kit": Path("/docker/chummercomplete/chummer-ui-kit"),
    "chummer-hub-registry": Path("/docker/chummercomplete/chummer-hub-registry"),
    "chummer-media-factory": Path("/docker/fleet/repos/chummer-media-factory"),
}

FILENAME = "2026-03-10-public-repo-graph-audit.md"


FULL_AUDIT = textwrap.dedent(
    """
    # Public Chummer repo audit

    Date: 2026-03-10
    Audience: `chummer-design` and the `chummer-vnext` group
    Status: injected fleet feedback

    ## Summary

    The public Chummer repo split is now materially real:

    * `chummer-design`
    * `chummer-core-engine`
    * `chummer-presentation`
    * `chummer.run-services`
    * `chummer-play`
    * `chummer-ui-kit`
    * `chummer-hub-registry`
    * `chummer-media-factory`

    The remaining architectural problem is not whether the split exists. It does.

    The problem is that the code graph has moved farther than the central design graph. The program is still design-led in theory and code-led in practice because `chummer-design` continues to publish a stale pre-split worldview while the code repos have already crossed that line.

    ## Improvements confirmed

    * `chummer-design` now has the right skeleton: root README, `products/chummer/*`, repo scopes, review templates, and a sync manifest.
    * `chummer-play` now has a real `src/` tree instead of being docs-only.
    * `chummer-ui-kit` and `chummer-hub-registry` both look like healthy seed splits with `.codex-design` mirrors and scoped source trees.
    * `chummer-presentation` now has the most honest README in the graph and explicitly says the shipped `/session` and `/coach` heads belong to `chummer-play`.

    ## Main problems

    1. `chummer-design` still publishes stale truth.
       - Active repo coverage still lags the real public graph.
       - The product README and milestone/blocker/contract truth still describe parts of the split as future work.
       - Canonical files are still too thin to steer the rest of the program safely.

    2. `chummer-design` still violates its own canonical-tree rule.
       - Root-level media-factory-specific docs and folders still exist outside `products/chummer/*`.
       - `chummer-media-factory` is still not fully onboarded into the central design/mirror system.

    3. Package canon is still drifting.
       - `chummer-play` still has `Chummer.Contracts` versus `Chummer.Engine.Contracts` naming drift.
       - `chummer.run-services` still duplicates session relay/runtime bundle DTO families across play and run packages.

    4. The newest split repos still have asymmetric maturity.
       - `chummer-ui-kit` and `chummer-hub-registry` are healthy seed repos.
       - `chummer-media-factory` is still scaffold-stage and the least integrated split repo.

    ## Repo-by-repo assessment

    ### `chummer-design` - red

    Good skeleton, weak canon.

    * Fix the repo graph first.
    * Replace the stub or near-stub canonical files with real design truth.
    * Onboard `chummer-media-factory` everywhere central canon enumerates active repos, mirrors, scopes, ownership, milestones, blockers, and contracts.
    * Move orphan product docs out of the repo root and into the canonical `products/chummer/*` tree.

    ### `chummer-play` - red/yellow

    The repo is past the docs-only stage, but it still has package and mirror drift.

    * Resolve `Chummer.Contracts` versus `Chummer.Engine.Contracts` immediately.
    * Make `.codex-design` mirror coverage visible and current.
    * Keep the repo focused on becoming the first serious consumer-test of the package plane.

    ### `chummer-media-factory` - red

    The mission is right, but the repo is still mostly a placeholder split.

    * Add a real source tree.
    * Add full mirror coverage.
    * Turn `Chummer.Media.Contracts` into a real package seam.
    * Stop leaving media contract ownership ambiguous between media-factory and run-services.

    ### `chummer-ui-kit` - green/yellow

    Healthy seed split.

    * Keep scope narrow and package-only.
    * Use the design repo to publish the roadmap and component taxonomy that this repo itself should not invent ad hoc.

    ### `chummer-hub-registry` - green/yellow

    Healthy seed split.

    * Keep growing it from contract seed to real registry behavior.
    * Make `chummer-design` describe it as an active governed repo, not a future recommendation.

    ### `chummer.run-services` - red/yellow

    Real structural progress exists, but the repo is still too wide and still duplicates semantic transport families.

    * Collapse the duplicate `SessionEventEnvelope` / runtime bundle / relay DTO families across play and run packages.
    * Untangle `MediaContracts.cs` so run-services stops carrying mixed downstream media and play surface types.
    * Rewrite the README to stop narrating the old multi-head runtime story.

    ### `chummer-core-engine` - red/yellow

    Boundary purification is still not done.

    * Remove obvious cross-boundary source leaks.
    * Rewrite the README so it stops narrating `/hub`, `/session`, and `/coach` as part of the current core world.
    * Keep quarantining legacy utility/app surface out of the active engine boundary.

    ### `chummer-presentation` - yellow

    This repo is ahead of central design truth.

    * Keep aligning local scope to the split the README already acknowledges.
    * Narrow the broad legacy root surface over time.
    * Keep `Chummer.Ui.Kit` consumption as a hard package-only rule.

    ## Priority order

    1. Fix `chummer-design` first.
    2. Fix `chummer-play` package canon and mirror coverage.
    3. Fix `chummer-media-factory` onboarding.
    4. Collapse `chummer.run-services` contract duplication.
    5. Keep purifying core and narrowing presentation.

    ## Worker instruction

    Do not assume the current central design canon is fully current just because the repo exists.

    When the code graph and the design repo disagree:

    * update `chummer-design` first
    * freeze package names before adding more seams
    * prefer package-only and mirror-first corrections over local repo improvisation
    """
).strip() + "\n"


PROJECT_FEEDBACK = {
    "chummer-core-engine": textwrap.dedent(
        """
        # Lead-dev feedback: core boundary purification

        Public audit status: `red/yellow`

        Main issues:

        * visible cross-boundary source leaks still exist
        * README still narrates the old multi-head runtime story
        * the repo root is still materially wider than the intended engine boundary

        Required next steps:

        1. Remove or quarantine `Chummer.Presentation.Contracts`, `Chummer.RunServices.Contracts`, and other non-engine authority surfaces.
        2. Rewrite the README so the engine owns mechanics, reducer truth, runtime bundles, and explain canon only.
        3. Continue shrinking legacy utility/app residue out of the active engine solution.
        """
    ).strip()
    + "\n",
    "chummer-presentation": textwrap.dedent(
        """
        # Lead-dev feedback: presentation alignment

        Public audit status: `yellow`

        Good news:

        * the README now honestly says shipped `/session` and `/coach` live in `chummer-play`

        Remaining issues:

        * the root is still broad with legacy utility/app surface
        * central design truth is behind the repo README

        Required next steps:

        1. Keep workbench/browser/desktop ownership crisp.
        2. Treat `Chummer.Ui.Kit` as a hard package-only dependency.
        3. Keep pruning stale play-host assumptions from local docs and code structure.
        """
    ).strip()
    + "\n",
    "chummer.run-services": textwrap.dedent(
        """
        # Lead-dev feedback: run-services contract dedupe

        Public audit status: `red/yellow`

        Main issues:

        * play and run packages still duplicate semantic relay/runtime DTO families
        * `MediaContracts.cs` still mixes play-surface and media ownership concerns
        * README still narrates the old multi-head runtime
        * the repo root is still too wide

        Required next steps:

        1. Pick one semantic owner for session event and runtime bundle meaning.
        2. Leave transport/projection wrappers in play/run contracts only after engine semantic ownership is frozen.
        3. Untangle media execution contracts from hosted orchestration contracts.
        4. Rewrite the README to the current split architecture.
        """
    ).strip()
    + "\n",
    "chummer-play": textwrap.dedent(
        """
        # Lead-dev feedback: play package canon and mirror coverage

        Public audit status: `red/yellow`

        Main issues:

        * package naming still drifts between README text and build/package usage
        * `.codex-design` mirror coverage is still expected to be obvious and current
        * the repo is no longer docs-only and now needs to become a real package consumer

        Required next steps:

        1. Freeze on `Chummer.Engine.Contracts`, `Chummer.Play.Contracts`, and `Chummer.Ui.Kit`.
        2. Remove legacy `Chummer.Contracts` language from README and related docs.
        3. Keep pushing from scaffold behavior toward real play API, ledger, and sync seams.
        """
    ).strip()
    + "\n",
    "chummer-ui-kit": textwrap.dedent(
        """
        # Lead-dev feedback: ui-kit seed health

        Public audit status: `green/yellow`

        This is one of the healthiest seed splits in the graph.

        Keep doing:

        * package-only shared UI ownership
        * no domain DTOs
        * no HTTP clients

        Next expectation:

        * central design truth must publish the roadmap and component taxonomy this repo will grow into
        """
    ).strip()
    + "\n",
    "chummer-hub-registry": textwrap.dedent(
        """
        # Lead-dev feedback: hub-registry seed health

        Public audit status: `green/yellow`

        This is a healthy seed split.

        Keep doing:

        * immutable artifact metadata and publication/install/compatibility scope
        * dedicated contract ownership
        * verify-harness discipline

        Next expectation:

        * central design truth must stop describing hub-registry as future work and treat it as an active governed repo
        """
    ).strip()
    + "\n",
    "chummer-media-factory": textwrap.dedent(
        """
        # Lead-dev feedback: media-factory onboarding

        Public audit status: `red`

        Main issues:

        * scaffold-stage repo shape
        * no durable evidence yet of real source-first execution maturity
        * mirror and central design onboarding still lag
        * contract ownership is still too ambiguous with run-services

        Required next steps:

        1. Add a real source tree and make the repo source-first.
        2. Make `.codex-design` mirror coverage current and visible.
        3. Land `Chummer.Media.Contracts` as a real package seam.
        4. Keep render-only and asset-lifecycle scope crisp.
        """
    ).strip()
    + "\n",
}


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_feedback(repo_root: Path, filename: str, content: str) -> None:
    write(repo_root / "feedback" / filename, content)


def main() -> None:
    write(GROUP_FEEDBACK_ROOT / FILENAME, FULL_AUDIT)
    write_feedback(DESIGN_ROOT, FILENAME, FULL_AUDIT)
    for repo_name, content in PROJECT_FEEDBACK.items():
        repo_root = REPO_ROOTS.get(repo_name)
        if repo_root:
            write_feedback(repo_root, FILENAME, content)
    print("Injected Chummer public repo audit feedback into group state and repo feedback lanes.")


if __name__ == "__main__":
    main()
