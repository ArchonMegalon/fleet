from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V17 = ROOT / "_completion" / "full_product_reaudit_v17"
V18 = ROOT / "_completion" / "full_product_reaudit_v18"


def check_verdict(filename: str, token: str) -> int:
    path = V18 / filename
    if not path.is_file():
        path = V17 / filename
    if not path.is_file():
        print(f"missing:{filename}")
        return 1
    text = path.read_text(encoding="utf-8")
    if token not in text:
        print(f"failing:{filename}")
        return 1
    print(token)
    return 0
