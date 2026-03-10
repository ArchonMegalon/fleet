#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "gateway" / "static" / "dashboard" / "index.html"
CSS = ROOT / "gateway" / "static" / "dashboard" / "bridge.css"
JS = ROOT / "gateway" / "static" / "dashboard" / "bridge.js"


def replace_block(text: str, begin: str, end: str, replacement: str) -> str:
    start = text.find(begin)
    if start < 0:
        raise SystemExit(f"missing marker: {begin}")
    stop = text.find(end, start)
    if stop < 0:
        raise SystemExit(f"missing marker: {end}")
    stop += len(end)
    return text[:start] + replacement + text[stop:]


def main() -> None:
    html = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8").rstrip()
    js = JS.read_text(encoding="utf-8").rstrip()

    css_block = "\n".join(
        [
            "    <!-- BEGIN INLINE_BRIDGE_CSS -->",
            '    <style id="bridge-inline-css">',
            css,
            "    </style>",
            "    <!-- END INLINE_BRIDGE_CSS -->",
        ]
    )
    js_block = "\n".join(
        [
            "    <!-- BEGIN INLINE_BRIDGE_JS -->",
            '    <script id="bridge-inline-js">',
            js,
            "    </script>",
            "    <!-- END INLINE_BRIDGE_JS -->",
        ]
    )

    html = replace_block(html, "    <!-- BEGIN INLINE_BRIDGE_CSS -->", "    <!-- END INLINE_BRIDGE_CSS -->", css_block)
    html = replace_block(html, "    <!-- BEGIN INLINE_BRIDGE_JS -->", "    <!-- END INLINE_BRIDGE_JS -->", js_block)
    INDEX.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
