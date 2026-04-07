# ALICE

## The problem

Players often discover bad builds, illegal interactions, or weak upgrade paths only after the run has already gone sideways. That cost is real: a player can lose trust in a build before the system has shown its work.

## What it would do

Chummer would compare builds, catch trouble before play, and explain tradeoffs without making up rules or legality. The move is bounded: compare, explain, and warn early, not invent new rules advice or become a general-purpose coach.

## Horizon discipline

| Field | Horizon discipline |
| --- | --- |
| Pain | Build mistakes, illegal interactions, and weak upgrade paths are usually found too late, after the run has already absorbed the cost. |
| Bounded product move | Add a compare-and-explain layer that surfaces trouble early and stays inside engine-owned semantics. |
| Owning repos | `chummer6-core`, `chummer6-ui`, `chummer6-hub` |
| LTD/tool posture | Research and assistive drafting tools may help draft operator-facing explanations, but they do not own legality, verdicts, or rule interpretation. |
| Dependency foundations | Explain views that show their work; deterministic runtime data; strong comparison flows. |
| Current state | Comparison and explanation surfaces exist only in partial form, and they are not yet reliable enough to carry higher-level build advice. |
| Eventual build path | `chummer6-core` computes the comparison truth, `chummer6-ui` presents the reasons and deltas, and `chummer6-hub` carries the experience and distribution surface around that capability. |
| Why it is still a horizon | The product still lacks enough comparison depth, explainability, and legality confidence to make this a flagship advice surface. |
| Flagship handoff gate | Promote only when the same build can be compared, the legality and tradeoff reasons are visible, no rules are invented, and the live flagship head passes release acceptance with deterministic engine output underneath. |

## Why it is not ready yet

The product still needs reliable comparison and explanation surfaces before it should hand out higher-level build advice. Until that gate is passed, ALICE remains a horizon rather than a flagship feature.
