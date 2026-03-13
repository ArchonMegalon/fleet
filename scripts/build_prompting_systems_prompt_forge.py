#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


OUTPUT_DIR = Path("/docker/fleet/state/browseract_bootstrap/runtime")


def build_spec(*, workflow_name: str, prompt_value: str | None) -> dict[str, object]:
    input_config: dict[str, object] = {
        "selector": "textarea[placeholder^='Describe what type of content you want to create']",
        "description": "Type the incoming prompt into the main Prompting Systems AI Prompt Generator textarea and replace any existing content.",
    }
    if prompt_value:
        input_config["value"] = prompt_value
    else:
        input_config["value_from_input"] = "prompt"

    return {
        "workflow_name": workflow_name,
        "description": "Generate stronger image prompts from the Prompting Systems AI Prompt Generator page using explicit selectors for its primary textarea and result card.",
        "publish": True,
        "mcp_ready": False,
        "inputs": [
            {
                "name": "prompt",
                "description": "Raw Chummer6 scene brief that needs refinement into a stronger image prompt.",
            },
            {
                "name": "target",
                "description": "Optional page or asset identifier for traceability in the EA run.",
            },
            {
                "name": "width",
                "description": "Optional requested render width forwarded by the EA pipeline.",
            },
            {
                "name": "height",
                "description": "Optional requested render height forwarded by the EA pipeline.",
            },
            {
                "name": "output_path",
                "description": "Optional downstream output path forwarded by the EA pipeline.",
            },
        ],
        "nodes": [
            {
                "id": "open_tool",
                "type": "visit_page",
                "label": "Open Tool",
                "config": {
                    "url": "https://prompting.systems/free-tool/ai-prompt-generator"
                },
            },
            {
                "id": "wait_form",
                "type": "wait",
                "label": "Wait Form",
                "config": {
                    "selector": "textarea[placeholder^='Describe what type of content you want to create']",
                    "description": "Wait until the main Prompting Systems AI Prompt Generator textarea is visible.",
                    "timeout_ms": 30000,
                },
            },
            {
                "id": "focus_request",
                "type": "click",
                "label": "Focus Request",
                "config": {
                    "selector": "textarea[placeholder^='Describe what type of content you want to create']",
                    "description": "Focus the main Prompting Systems textarea before typing.",
                },
            },
            {
                "id": "type_request",
                "type": "input_text",
                "label": "Input Request",
                "config": input_config,
            },
            {
                "id": "generate",
                "type": "click",
                "label": "Generate",
                "config": {
                    "selector": "button[variant='primary']",
                    "description": "Click the primary generate action for the Prompting Systems form.",
                },
            },
            {
                "id": "wait_result",
                "type": "wait",
                "label": "Wait Result",
                "config": {
                    "selector": "div.sc-kCwqPn",
                    "description": "Wait for the generated prompt result card to settle after the generate click.",
                    "timeout_ms": 30000,
                },
            },
            {
                "id": "extract_result",
                "type": "extract",
                "label": "Extract Result",
                "config": {
                    "selector": "div.sc-kCwqPn",
                    "description": "Extract the main result-card text only, not headers, nav, or FAQs.",
                    "field_name": "generated_prompt",
                    "mode": "text",
                },
            },
            {
                "id": "output_result",
                "type": "output",
                "label": "Output Result",
                "config": {
                    "description": "Publish the generated_prompt field as the workflow output for API callers.",
                    "field_name": "generated_prompt",
                },
            },
        ],
        "edges": [
            ["open_tool", "wait_form"],
            ["wait_form", "focus_request"],
            ["focus_request", "type_request"],
            ["type_request", "generate"],
            ["generate", "wait_result"],
            ["wait_result", "extract_result"],
            ["extract_result", "output_result"],
        ],
        "meta": {
            "slug": workflow_name,
            "output_dir": str(OUTPUT_DIR),
            "status": "pending_browseract_seed",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the BrowserAct Prompting Systems prompt-forge workflow spec.")
    parser.add_argument("--workflow-name", default="prompting_systems_prompt_forge_v15")
    parser.add_argument("--literal-prompt", default="")
    parser.add_argument("--output-path", default="")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output_path).expanduser() if args.output_path else OUTPUT_DIR / f"{args.workflow_name}.workflow.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    spec = build_spec(
        workflow_name=str(args.workflow_name).strip() or "prompting_systems_prompt_forge_v15",
        prompt_value=str(args.literal_prompt).strip() or None,
    )
    output_path.write_text(json.dumps(spec, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "spec": str(output_path), "workflow_name": spec["workflow_name"]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
