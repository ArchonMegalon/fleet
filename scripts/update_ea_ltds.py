#!/usr/bin/env python3
from pathlib import Path


def main() -> None:
    path = Path("/docker/EA/LTDs.md")
    text = path.read_text(encoding="utf-8")
    replacements = {
        "Updated: 2026-03-07": "Updated: 2026-03-10",
        "| `AvoMap` | `10x code-based` | `10 codes` | `9 redeemed / 1 pending` | `2026-05-02` | `Tier 3` | None | One remaining code must be redeemed by May 2, 2026. |": "| `AvoMap` | `10x code-based` | `10 codes` | `Activated` |  | `Tier 3` | None | All codes redeemed and activated; local runtime integration is still optional. |",
        "| `Invoiless` | `1x code-based` | `1 code` | `Pending redemption` | `2026-04-29` | `Tier 3` | None | Redeem by April 29, 2026. |": "| `Invoiless` | `1x code-based` | `1 code` | `Activated` |  | `Tier 3` | None | Redeemed and activated; still out of the current hot-path product architecture. |",
        "| `MarkupGo` | `7x code-based` | `7 codes` | `Pending redemption` | `2026-04-28` | `Tier 3` | None | Redeem by April 28, 2026. |": "| `MarkupGo` | `7x code-based` | `7 codes` | `Activated` |  | `Tier 3` | None | Redeemed and activated; ready for adapter-first media use when needed. |",
        "| `MetaSurvey` | `Plus exclusive / 3x code-based` | `3 codes` | `Pending redemption` | `2026-04-29` | `Tier 3` | None | Redeem by April 29, 2026. |": "| `MetaSurvey` | `Plus exclusive / 3x code-based` | `3 codes` | `Activated` |  | `Tier 3` | None | Redeemed and activated; reserved for structured feedback collection. |",
        "| `PeekShot` | `3x code-based` | `3 codes` | `Pending redemption` | `2026-04-30` | `Tier 3` | None | Redeem by April 30, 2026. |": "| `PeekShot` | `3x code-based` | `3 codes` | `Activated` |  | `Tier 3` | None | Redeemed and activated; suitable for preview/thumbnail adapter work when wired. |",
        "| `Vizologi` | `Plus exclusive / 4x code-based` | `4 codes` | `Pending redemption` | `2026-04-30` | `Tier 3` | None | Redeem by April 30, 2026. |": "| `Vizologi` | `Plus exclusive / 4x code-based` | `4 codes` | `Activated` |  | `Tier 3` | None | Redeemed and activated; retained for strategy/research support only. |",
        "| `AvoMap` |  | `missing` | `manual_inventory` |  | Remaining redemption work still blocks final account verification. |": "| `AvoMap` |  | `missing` | `manual_inventory` |  | Activated; account-level verification details are still not documented here. |",
        "| `Invoiless` |  | `missing` | `manual_inventory` |  | Pending redemption before account verification. |": "| `Invoiless` |  | `missing` | `manual_inventory` |  | Activated; account-level verification details are still not documented here. |",
        "| `MarkupGo` |  | `missing` | `manual_inventory` |  | Pending redemption before account verification. |": "| `MarkupGo` |  | `missing` | `manual_inventory` |  | Activated; account-level verification details are still not documented here. |",
        "| `MetaSurvey` |  | `missing` | `manual_inventory` |  | Pending redemption before account verification. |": "| `MetaSurvey` |  | `missing` | `manual_inventory` |  | Activated; account-level verification details are still not documented here. |",
        "| `PeekShot` |  | `missing` | `manual_inventory` |  | Pending redemption before account verification. |": "| `PeekShot` |  | `missing` | `manual_inventory` |  | Activated; account-level verification details are still not documented here. |",
        "| `Vizologi` |  | `missing` | `manual_inventory` |  | Pending redemption before account verification. |": "| `Vizologi` |  | `missing` | `manual_inventory` |  | Activated; account-level verification details are still not documented here. |",
        "## Attention Items\n\n| Service | Action Needed | Deadline |\n|---|---|---|\n| `MarkupGo` | Redeem pending codes | `2026-04-28` |\n| `Invoiless` | Redeem pending code | `2026-04-29` |\n| `MetaSurvey` | Redeem pending codes | `2026-04-29` |\n| `PeekShot` | Redeem pending codes | `2026-04-30` |\n| `Vizologi` | Redeem pending codes | `2026-04-30` |\n| `AvoMap` | Redeem 1 remaining code | `2026-05-02` |": "## Attention Items\n\nNone right now. All tracked LTDs are redeemed and activated; remaining follow-up is only account-detail verification and any later runtime wiring.",
    }
    for old, new in replacements.items():
        if old not in text:
            raise SystemExit(f"missing expected text: {old}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
