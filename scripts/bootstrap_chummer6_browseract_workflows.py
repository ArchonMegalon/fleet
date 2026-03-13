#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


STATE_DIR = Path("/docker/fleet/state/chummer6/browseract")


REFINE_BRIEF = """# Chummer6 BrowserAct Workflow: Prompting Systems Refine

Workflow name:
`chummer6 prompting systems refine`

Purpose:
- open Prompting Systems
- turn a raw Chummer6 section visual brief into a tighter image-generation prompt
- return plain refined prompt text, not markdown, not JSON code fences

Inputs:
- `prompt`
- `target`

Required behavior:
1. Go to the Prompting Systems prompt-generation tool.
2. Treat `prompt` as the source brief and `target` as the page/asset role.
3. Produce one refined prompt for image generation.
4. Keep it cinematic, context-aware, Shadowrun-flavored, and suitable for GitHub-facing banner art.
5. Do not output explanations, bullets, or labels.
6. Do not output any text intended to appear on the image.
7. Return only the final refined prompt text.

Style rules:
- Scene must understand the page role.
- No generic neon wallpaper.
- No SVG/diagram language.
- No visible prompt text, OODA labels, or resolution labels in the image.
- Favor lived-in cyberpunk scenes over abstract infographics.
"""


MAGIX_BRIEF = """# Chummer6 BrowserAct Workflow: AI Magicx Render

Workflow name:
`chummer6 magicx render`

Purpose:
- open AI Magicx through BrowserAct
- render one Chummer6 image from the refined prompt
- return a downloadable image URL

Inputs:
- `prompt`
- `target`
- `width`
- `height`
- `output_path`

Required behavior:
1. Open AI Magicx image generation.
2. Paste the final prompt into the generator.
3. Use a wide banner composition suitable for README/page hero art.
4. Prefer one strong focal scene, not icon soup.
5. Generate the image and expose the final downloadable image URL.
6. Return a payload that includes the image URL.

Negative constraints:
- no visible prompt text
- no OODA or metadata overlays
- no resolution labels
- no watermark
- no generic stock-poster framing
"""

HUMANIZER_BRIEF = """# Chummer6 BrowserAct Workflow: Undetectable Humanizer

Workflow name:
`chummer6 undetectable humanizer`

Purpose:
- open the Undetectable AI humanizer through BrowserAct
- rewrite one Chummer6 copy block into more natural, less robotic language
- return only the rewritten text

Inputs:
- `text`
- `target`

Required behavior:
1. Open the Undetectable AI humanizer page.
2. Paste `text` into the main source textarea.
3. Treat `target` as the page/section role and preserve the original intent.
4. Return one clean rewritten text block.
5. Do not return explanations, bullets, labels, or JSON wrappers.
6. Keep product meaning intact while making the wording feel more human.

Negative constraints:
- no markdown fences
- no prefatory labels
- no policy/meta commentary
- no invented claims
"""


MANIFEST = {
    "workflows": [
        {
            "kind": "refine",
            "query": "chummer6 prompting systems refine",
            "brief_file": "prompting-systems-refine.md",
            "inputs": ["prompt", "target"],
            "expected_output": "plain refined prompt text",
        },
        {
            "kind": "magixai_render",
            "query": "chummer6 magicx render",
            "brief_file": "aimagicx-render.md",
            "inputs": ["prompt", "target", "width", "height", "output_path"],
            "expected_output": "downloadable image URL",
        },
        {
            "kind": "humanizer",
            "query": "chummer6 undetectable humanizer",
            "brief_file": "undetectable-humanizer.md",
            "inputs": ["text", "target"],
            "expected_output": "plain rewritten text",
        },
    ]
}


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "prompting-systems-refine.md").write_text(REFINE_BRIEF, encoding="utf-8")
    (STATE_DIR / "aimagicx-render.md").write_text(MAGIX_BRIEF, encoding="utf-8")
    (STATE_DIR / "undetectable-humanizer.md").write_text(HUMANIZER_BRIEF, encoding="utf-8")
    (STATE_DIR / "manifest.json").write_text(json.dumps(MANIFEST, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "written",
                "state_dir": str(STATE_DIR),
                "manifest": str(STATE_DIR / "manifest.json"),
                "workflows": MANIFEST["workflows"],
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
