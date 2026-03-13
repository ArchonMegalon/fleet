#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


OUTPUT_DIR = Path("/docker/fleet/state/browseract_bootstrap/runtime")


def build_spec(*, workflow_name: str, text_value: str | None) -> dict[str, object]:
    input_config: dict[str, object] = {
        "selector": "textarea[aria-label='Input text']",
        "description": "Fill the main Undetectable AI textarea in the Input Your AI-Generated Content section.",
    }
    if text_value:
        input_config["value"] = text_value
    else:
        input_config["value_from_input"] = "text"

    return {
        "workflow_name": workflow_name,
        "description": "Humanize Chummer6 copy through the Undetectable AI Humanizer web UI using explicit selectors for the input textarea, humanize button, and live output area.",
        "publish": True,
        "mcp_ready": False,
        "inputs": [
            {
                "name": "text",
                "description": "Original Chummer6 copy block that should be humanized.",
            },
            {
                "name": "target",
                "description": "Optional page or section id used for traceability in the EA run.",
            },
        ],
        "nodes": [
            {
                "id": "open_tool",
                "type": "visit_page",
                "label": "Open Tool",
                "config": {
                    "url": "https://undetectable.ai/ai-humanizer",
                },
            },
            {
                "id": "input_text",
                "type": "input_text",
                "label": "Input Text",
                "config": input_config,
            },
            {
                "id": "humanize",
                "type": "click",
                "label": "Humanize",
                "config": {
                    "selector": "button[type='button']",
                    "description": "Click the primary Humanize AI button below the input area.",
                },
            },
            {
                "id": "wait_result",
                "type": "wait",
                "label": "Wait Result",
                "config": {
                    "selector": "div[aria-live='polite']",
                    "description": "Wait until the main humanized output region is visible and updated after clicking Humanize AI.",
                    "timeout_ms": 60000,
                },
            },
            {
                "id": "extract_result",
                "type": "extract",
                "label": "Extract Result",
                "config": {
                    "selector": "div[aria-live='polite']",
                    "description": "Extract only the humanized output from the main aria-live result region.",
                    "field_name": "humanized_text",
                    "mode": "text",
                },
            },
            {
                "id": "output_result",
                "type": "output",
                "label": "Output Result",
                "config": {
                    "description": "Publish the humanized_text field as the workflow output for API callers.",
                    "field_name": "humanized_text",
                },
            },
        ],
        "edges": [
            ["open_tool", "input_text"],
            ["input_text", "humanize"],
            ["humanize", "wait_result"],
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
    parser = argparse.ArgumentParser(description="Build the BrowserAct Undetectable humanizer workflow spec.")
    parser.add_argument("--workflow-name", default="undetectable_humanizer_v4")
    parser.add_argument("--literal-text", default="")
    parser.add_argument("--output-path", default="")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output_path).expanduser() if args.output_path else OUTPUT_DIR / f"{args.workflow_name}.workflow.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    spec = build_spec(
        workflow_name=str(args.workflow_name).strip() or "undetectable_humanizer_v4",
        text_value=str(args.literal_text).strip() or None,
    )
    output_path.write_text(json.dumps(spec, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "spec": str(output_path), "workflow_name": spec["workflow_name"]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
