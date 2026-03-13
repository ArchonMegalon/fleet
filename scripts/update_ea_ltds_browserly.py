#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import pathlib
import re
import sys


EA_ROOT = pathlib.Path("/docker/EA")
EA_LTDS_PATH = EA_ROOT / "LTDs.md"
EA_ENV_EXAMPLE_PATH = EA_ROOT / ".env.example"
EA_ENV_LOCAL_EXAMPLE_PATH = EA_ROOT / ".env.local.example"
EA_PROVIDER_REGISTRY_PATH = EA_ROOT / "ea/app/services/provider_registry.py"
EA_PROVIDER_TEST_PATH = EA_ROOT / "tests/test_provider_registry.py"

LTD_ROW = (
    "| `Browserly` | `Plan pending verification` | `1 account` | `Owned` |  | `Tier 2` | "
    "EA provider-registry catalog hint, Browserly env placeholders, and media-factory vendor-map reservation | "
    "Tracked as a browser-assisted capture/reference vendor; exact deal tier and account facts still need verification before runtime promotion. |"
)

DISCOVERY_ROW = (
    "| `Browserly` |  | `missing` | `manual_inventory` |  | "
    "Deal/account facts still need verification; Browserly is reserved as a browser-assisted capture/reference vendor. |"
)

BROWSERLY_ENV_BLOCK = """# Optional Browserly browser/capture adapter
BROWSERLY_API_KEY=
CHUMMER6_BROWSERLY_CAPTURE_COMMAND=
CHUMMER6_BROWSERLY_CAPTURE_URL_TEMPLATE=

"""

BROWSERLY_PROVIDER_BLOCK = """
            ProviderBinding(
                provider_key="browserly",
                display_name="Browserly",
                executable=False,
                capabilities=(
                    ProviderCapability(
                        provider_key="browserly",
                        capability_key="browser_capture",
                        tool_name="provider.browserly.browser_capture",
                        executable=False,
                    ),
                ),
                source="catalog",
            ),
"""


def replace_first(text: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    return updated if count else text


def upsert_row_in_section(text: str, section_header: str, service_name: str, row: str, *, before_service: str) -> str:
    start = text.find(section_header)
    if start < 0:
        return text
    next_heading = text.find("\n## ", start + len(section_header))
    if next_heading < 0:
        next_heading = len(text)
    section = text[start:next_heading]
    pattern = re.compile(rf"^\| `{re.escape(service_name)}` \|.*$", re.MULTILINE)
    if pattern.search(section):
        section = pattern.sub(row, section, count=1)
    else:
        anchor = f"| `{before_service}` |"
        if anchor in section:
            section = section.replace(anchor, row + "\n" + anchor, 1)
    return text[:start] + section + text[next_heading:]


def ensure_insert_after(text: str, anchor: str, insertion: str) -> str:
    if insertion.strip() in text:
        return text
    if anchor not in text:
        return text
    return text.replace(anchor, anchor + insertion, 1)


def update_ltds() -> None:
    if not EA_LTDS_PATH.exists():
        raise SystemExit(f"missing file: {EA_LTDS_PATH}")
    text = EA_LTDS_PATH.read_text(encoding="utf-8")
    today = dt.date.today().isoformat()
    text = replace_first(text, r"^Updated:\s+\d{4}-\d{2}-\d{2}$", f"Updated: {today}")
    text = replace_first(text, r"- `\d+` total LTD products tracked", "- `23` total LTD products tracked")
    text = upsert_row_in_section(text, "## Non-AppSumo / Other LTDs", "Browserly", LTD_ROW, before_service="FastestVPN PRO")
    text = upsert_row_in_section(text, "## Discovery Tracking", "Browserly", DISCOVERY_ROW, before_service="FastestVPN PRO")
    EA_LTDS_PATH.write_text(text, encoding="utf-8")


def update_env_example(path: pathlib.Path) -> None:
    if not path.exists():
        raise SystemExit(f"missing file: {path}")
    text = path.read_text(encoding="utf-8")
    anchor = "# Optional Chummer6 guide media provider hooks (local .env only; keep real keys and adapters out of git)\n"
    updated = ensure_insert_after(text, "UNMIXR_API_KEY=\n", "\n" + BROWSERLY_ENV_BLOCK)
    if updated == text:
        updated = ensure_insert_after(text, anchor, BROWSERLY_ENV_BLOCK)
    path.write_text(updated, encoding="utf-8")


def update_provider_registry() -> None:
    if not EA_PROVIDER_REGISTRY_PATH.exists():
        raise SystemExit(f"missing file: {EA_PROVIDER_REGISTRY_PATH}")
    text = EA_PROVIDER_REGISTRY_PATH.read_text(encoding="utf-8")
    if 'provider_key="browserly"' not in text:
        anchor = """            ProviderBinding(
                provider_key="teable",
"""
        if anchor not in text:
            raise SystemExit("provider registry anchor not found")
        text = text.replace(anchor, BROWSERLY_PROVIDER_BLOCK + anchor, 1)
    aliases_old = '''        aliases = {
            "1min.ai": "onemin",
            "1min_ai": "onemin",
            "ai_magicx": "magixai",
            "aimagicx": "magixai",
            "prompting.systems": "prompting_systems",
        }
'''
    aliases_new = '''        aliases = {
            "1min.ai": "onemin",
            "1min_ai": "onemin",
            "ai_magicx": "magixai",
            "aimagicx": "magixai",
            "browserly.ai": "browserly",
            "browsely": "browserly",
            "prompting.systems": "prompting_systems",
        }
'''
    if aliases_old in text:
        text = text.replace(aliases_old, aliases_new, 1)
    EA_PROVIDER_REGISTRY_PATH.write_text(text, encoding="utf-8")


def update_provider_test() -> None:
    if not EA_PROVIDER_TEST_PATH.exists():
        raise SystemExit(f"missing file: {EA_PROVIDER_TEST_PATH}")
    text = EA_PROVIDER_TEST_PATH.read_text(encoding="utf-8")
    old_hints = '        provider_hints_json={"preferred": ["browseract"]},\n'
    new_hints = '        provider_hints_json={"preferred": ["browseract"], "research": ["browserly"]},\n'
    if old_hints in text:
        text = text.replace(old_hints, new_hints, 1)
    if 'assert "browserly" in keys' not in text:
        text = text.replace('    assert "browseract" in keys\n', '    assert "browseract" in keys\n    assert "browserly" in keys\n', 1)
    EA_PROVIDER_TEST_PATH.write_text(text, encoding="utf-8")


def main() -> int:
    update_ltds()
    update_env_example(EA_ENV_EXAMPLE_PATH)
    update_env_example(EA_ENV_LOCAL_EXAMPLE_PATH)
    update_provider_registry()
    update_provider_test()
    print(f"updated {EA_LTDS_PATH}")
    print(f"updated {EA_ENV_EXAMPLE_PATH}")
    print(f"updated {EA_ENV_LOCAL_EXAMPLE_PATH}")
    print(f"updated {EA_PROVIDER_REGISTRY_PATH}")
    print(f"updated {EA_PROVIDER_TEST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
